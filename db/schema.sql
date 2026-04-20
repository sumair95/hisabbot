-- ============================================================
-- Kirana Bookkeeper — Database Schema (Supabase / Postgres)
-- ============================================================
-- Apply to your Supabase project via the SQL editor, or with:
--   psql "$SUPABASE_DB_URL" -f db/schema.sql
-- This script is idempotent: safe to run multiple times.
-- ============================================================

-- Extensions -------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- for trigram-based fuzzy name search

-- ------------------------------------------------------------
-- shopkeepers: one row per shop / WhatsApp number
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shopkeepers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number          TEXT UNIQUE NOT NULL,          -- E.164, e.g. +923001234567
    shop_name             TEXT,
    owner_name            TEXT,
    language_pref         TEXT NOT NULL DEFAULT 'roman_urdu'
                          CHECK (language_pref IN ('urdu','roman_urdu','english')),
    timezone              TEXT NOT NULL DEFAULT 'Asia/Karachi',
    onboarding_state      TEXT NOT NULL DEFAULT 'new'    -- 'new' | 'awaiting_shop_name' | 'done'
                          CHECK (onboarding_state IN ('new','awaiting_shop_name','awaiting_language','done')),
    subscription_status   TEXT NOT NULL DEFAULT 'trial'  -- 'trial' | 'active' | 'expired' | 'free'
                          CHECK (subscription_status IN ('trial','active','expired','free')),
    trial_ends_at         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shopkeepers_phone ON shopkeepers(phone_number);

-- ------------------------------------------------------------
-- contacts: customers and suppliers per shop
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contacts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopkeeper_id         UUID NOT NULL REFERENCES shopkeepers(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,                 -- display name (what the shopkeeper said)
    normalized_name       TEXT NOT NULL,                 -- lowercased, honorifics stripped, for matching
    type                  TEXT NOT NULL DEFAULT 'customer'
                          CHECK (type IN ('customer','supplier')),
    phone                 TEXT,
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shopkeeper_id, normalized_name, type)
);

CREATE INDEX IF NOT EXISTS idx_contacts_shopkeeper      ON contacts(shopkeeper_id);
CREATE INDEX IF NOT EXISTS idx_contacts_name_trgm       ON contacts USING gin (normalized_name gin_trgm_ops);

-- ------------------------------------------------------------
-- transactions: the core ledger
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopkeeper_id         UUID NOT NULL REFERENCES shopkeepers(id) ON DELETE CASCADE,
    contact_id            UUID REFERENCES contacts(id) ON DELETE SET NULL,
    type                  TEXT NOT NULL
                          CHECK (type IN (
                              'sale_cash',         -- cash sale (no customer tracking needed)
                              'sale_credit',       -- udhaar given to a customer
                              'payment_received',  -- customer paid back some udhaar
                              'payment_made',      -- shopkeeper paid a supplier
                              'supplier_purchase'  -- bought stock on credit from supplier
                          )),
    amount                NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    items                 JSONB,                         -- [{name, qty, unit}] — optional
    notes                 TEXT,
    raw_message           TEXT,                          -- original shopkeeper text
    transcript            TEXT,                          -- STT output if from voice
    source                TEXT NOT NULL DEFAULT 'text'
                          CHECK (source IN ('text','voice')),
    occurred_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at            TIMESTAMPTZ,
    deleted_reason        TEXT
);

CREATE INDEX IF NOT EXISTS idx_txn_shopkeeper_occurred ON transactions(shopkeeper_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_txn_contact             ON transactions(contact_id);
CREATE INDEX IF NOT EXISTS idx_txn_type                ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_txn_active              ON transactions(shopkeeper_id, is_deleted) WHERE is_deleted = FALSE;

-- ------------------------------------------------------------
-- messages: every inbound/outbound WhatsApp message, for audit
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopkeeper_id         UUID REFERENCES shopkeepers(id) ON DELETE CASCADE,
    wa_message_id         TEXT,                          -- Meta's message id for dedupe
    direction             TEXT NOT NULL
                          CHECK (direction IN ('inbound','outbound')),
    kind                  TEXT NOT NULL DEFAULT 'text'
                          CHECK (kind IN ('text','voice','image','system')),
    content               TEXT,
    media_url             TEXT,
    transcript            TEXT,
    intent                TEXT,                          -- 'TRANSACTION' | 'QUERY' | 'CORRECTION' | ...
    extraction_json       JSONB,
    transaction_id        UUID REFERENCES transactions(id) ON DELETE SET NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_shopkeeper_created ON messages(shopkeeper_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_wa_id              ON messages(wa_message_id);

-- ------------------------------------------------------------
-- daily_summaries: cached daily aggregates + formatted summary text
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_summaries (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopkeeper_id               UUID NOT NULL REFERENCES shopkeepers(id) ON DELETE CASCADE,
    summary_date                DATE NOT NULL,
    total_cash_sales            NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_credit_sales          NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_payments_received     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_payments_made         NUMERIC(12,2) NOT NULL DEFAULT 0,
    new_customers_count         INT NOT NULL DEFAULT 0,
    net_for_day                 NUMERIC(12,2) NOT NULL DEFAULT 0,
    summary_text                TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(shopkeeper_id, summary_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_summaries_shop_date
    ON daily_summaries(shopkeeper_id, summary_date DESC);

-- ------------------------------------------------------------
-- Helper view: outstanding balances per contact
-- Positive balance = contact owes the shop.
-- Negative balance = shop owes the contact (supplier).
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_contact_balances AS
SELECT
    c.id                                                AS contact_id,
    c.shopkeeper_id,
    c.name,
    c.normalized_name,
    c.type,
    COALESCE(SUM(
        CASE
            WHEN t.type = 'sale_credit'        THEN  t.amount
            WHEN t.type = 'payment_received'   THEN -t.amount
            WHEN t.type = 'supplier_purchase'  THEN -t.amount
            WHEN t.type = 'payment_made'       THEN  t.amount
            ELSE 0
        END
    ), 0)::NUMERIC(12,2)                                AS balance
FROM contacts c
LEFT JOIN transactions t
    ON t.contact_id = c.id
   AND t.is_deleted = FALSE
GROUP BY c.id, c.shopkeeper_id, c.name, c.normalized_name, c.type;

-- ------------------------------------------------------------
-- Trigger: auto-update updated_at
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shopkeepers_updated_at ON shopkeepers;
CREATE TRIGGER trg_shopkeepers_updated_at
BEFORE UPDATE ON shopkeepers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_contacts_updated_at ON contacts;
CREATE TRIGGER trg_contacts_updated_at
BEFORE UPDATE ON contacts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
