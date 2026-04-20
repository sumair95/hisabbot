# Database Reference

Applied via `db/schema.sql`. Idempotent — safe to re-run.

## Tables

### `shopkeepers`
One row per shop / WhatsApp number.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| phone_number | text UNIQUE | E.164 format, e.g. `+923001234567` |
| shop_name | text | captured during onboarding |
| owner_name | text | optional |
| language_pref | text | `urdu` \| `roman_urdu` (default) \| `english` |
| timezone | text | default `Asia/Karachi` |
| onboarding_state | text | `new` → `awaiting_shop_name` → `done` |
| subscription_status | text | `trial` \| `active` \| `expired` \| `free` |
| trial_ends_at | timestamptz | |
| created_at, updated_at | timestamptz | auto-managed |

### `contacts`
Customers and suppliers. Scoped to one shopkeeper.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| shopkeeper_id | uuid FK → shopkeepers | CASCADE delete |
| name | text | what the shopkeeper said |
| normalized_name | text | honorific-stripped, lowercase (see `utils/names.py`) |
| type | text | `customer` \| `supplier` |
| phone | text | optional |

Unique constraint: `(shopkeeper_id, normalized_name, type)`. A GIN
trigram index on `normalized_name` speeds up fuzzy SQL search if we
ever need it (currently we fuzzy-match in Python with rapidfuzz).

### `transactions`
The ledger. Everything that moves money.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| shopkeeper_id | uuid FK | |
| contact_id | uuid FK \| null | null for anonymous cash sales |
| type | text | see "Transaction types" below |
| amount | numeric(12,2) | always positive; `type` determines sign |
| items | jsonb | `[{"name":"cheeni","quantity":2,"unit":"kg"}]` |
| notes | text | |
| raw_message | text | original shopkeeper text |
| transcript | text | if voice, the Whisper output |
| source | text | `text` \| `voice` |
| occurred_at | timestamptz | default now() |
| is_deleted | boolean | soft-delete flag |
| deleted_at | timestamptz | |
| deleted_reason | text | e.g. `user_undo` |

**Transaction types:**
- `sale_cash` — cash sale. Adds to today's cash total.
- `sale_credit` — udhaar given. Customer's balance +amount.
- `payment_received` — customer paid back. Customer's balance -amount.
- `payment_made` — shop paid supplier. Supplier's balance +amount (for shop).
- `supplier_purchase` — stock on credit. Supplier's balance -amount (for shop).

### `messages`
Every inbound and outbound message, for audit and debugging.

| Column | Type | Notes |
|---|---|---|
| wa_message_id | text | Meta's id; used for dedupe |
| direction | text | `inbound` \| `outbound` |
| kind | text | `text` \| `voice` \| `image` \| `system` |
| content | text | the text, or transcript if voice |
| media_url | text | original WhatsApp media URL |
| transcript | text | Whisper output (voice only) |
| intent | text | classified intent from extraction |
| extraction_json | jsonb | full LLM output for audit |
| transaction_id | uuid FK \| null | if this message produced a txn |

### `daily_summaries`
Snapshot of each day's totals + the formatted WhatsApp message.

Unique constraint: `(shopkeeper_id, summary_date)` so a re-run
overwrites the existing row.

### View: `v_contact_balances`

Balance per contact. **Positive = contact owes the shop.** **Negative =
shop owes the contact (supplier).**

Balance formula:
```
sum(
    +amount  where type = sale_credit        -- customer owes more
    -amount  where type = payment_received   -- customer paid back
    -amount  where type = supplier_purchase  -- shop owes supplier more
    +amount  where type = payment_made       -- shop paid supplier
)
```

Deleted rows (`is_deleted = TRUE`) are excluded.

## Useful queries

```sql
-- Top 10 debtors for a shop
SELECT name, balance
  FROM v_contact_balances
 WHERE shopkeeper_id = :sk
   AND type = 'customer'
   AND balance > 0
 ORDER BY balance DESC
 LIMIT 10;

-- All activity for a customer
SELECT type, amount, occurred_at, raw_message
  FROM transactions
 WHERE contact_id = :cid AND is_deleted = FALSE
 ORDER BY occurred_at DESC;

-- Daily net for last 7 days (shop's local timezone)
SELECT (occurred_at AT TIME ZONE 'Asia/Karachi')::date AS day,
       SUM(CASE WHEN type IN ('sale_cash','payment_received') THEN amount
                WHEN type = 'payment_made'                    THEN -amount
                ELSE 0 END) AS net
  FROM transactions
 WHERE shopkeeper_id = :sk
   AND is_deleted = FALSE
   AND occurred_at > NOW() - INTERVAL '7 days'
 GROUP BY day
 ORDER BY day DESC;
```

## Migrations

For MVP, the schema is one file (`db/schema.sql`) and idempotent. When
we start having more than a handful of shops in production, switch to
a proper migration tool (Alembic or `supabase migrations`). Until then,
edits to the schema should:
1. Be additive (new columns as nullable or with defaults)
2. Never rename or drop columns without a deprecation cycle
3. Be re-runnable on an existing DB without data loss
