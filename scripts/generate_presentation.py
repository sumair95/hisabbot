"""
Generate docs/HISABBOT_PRESENTATION.pdf — a comprehensive document
covering everything built so far, in language that works for both
investors and engineers.

Run from the repo root:
    .venv/Scripts/python scripts/generate_presentation.py
"""
from __future__ import annotations
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, ListFlowable, ListItem,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "HISABBOT_PRESENTATION.pdf"


# ---------------------------------------------------------------------------
# Visual identity
# ---------------------------------------------------------------------------

PRIMARY = colors.HexColor("#1a365d")   # deep navy
ACCENT = colors.HexColor("#2b6cb0")    # blue
TEAL = colors.HexColor("#2c7a7b")
INK = colors.HexColor("#2d3748")
MUTED = colors.HexColor("#718096")
LIGHT = colors.HexColor("#edf2f7")
BG_CALLOUT = colors.HexColor("#fefcbf")  # soft yellow for callouts


def _styles() -> dict:
    base = getSampleStyleSheet()
    s = {
        "Title": ParagraphStyle(
            "Title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=28, textColor=PRIMARY,
            leading=34, alignment=TA_CENTER, spaceAfter=12,
        ),
        "Tagline": ParagraphStyle(
            "Tagline", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=14, textColor=ACCENT,
            leading=20, alignment=TA_CENTER, spaceAfter=22,
        ),
        "CoverMeta": ParagraphStyle(
            "CoverMeta", parent=base["Normal"],
            fontName="Helvetica", fontSize=11, textColor=MUTED,
            leading=16, alignment=TA_CENTER,
        ),
        "H1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=20, textColor=PRIMARY,
            leading=26, spaceBefore=8, spaceAfter=12,
        ),
        "H2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14, textColor=ACCENT,
            leading=20, spaceBefore=12, spaceAfter=6,
        ),
        "H3": ParagraphStyle(
            "H3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=11, textColor=INK,
            leading=15, spaceBefore=8, spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, textColor=INK,
            leading=15, alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "BodyL": ParagraphStyle(
            "BodyL", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, textColor=INK,
            leading=15, alignment=TA_LEFT, spaceAfter=8,
        ),
        "Mono": ParagraphStyle(
            "Mono", parent=base["BodyText"],
            fontName="Courier", fontSize=9, textColor=INK,
            leading=12, alignment=TA_LEFT, spaceAfter=8,
            leftIndent=10, rightIndent=10,
            backColor=LIGHT, borderPadding=6,
        ),
        "Callout": ParagraphStyle(
            "Callout", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, textColor=INK,
            leading=14, alignment=TA_LEFT, spaceAfter=8,
            leftIndent=10, rightIndent=10,
            backColor=BG_CALLOUT, borderPadding=8,
        ),
        "Caption": ParagraphStyle(
            "Caption", parent=base["BodyText"],
            fontName="Helvetica-Oblique", fontSize=9, textColor=MUTED,
            leading=12, alignment=TA_CENTER, spaceAfter=8,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, textColor=INK,
            leading=15, alignment=TA_LEFT, spaceAfter=4,
        ),
        "Footer": ParagraphStyle(
            "Footer", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=MUTED,
            leading=10, alignment=TA_CENTER,
        ),
    }
    return s


# ---------------------------------------------------------------------------
# Story builders — each returns a list of flowables for one section
# ---------------------------------------------------------------------------

def _bullet_list(items: list[str], style) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=12, value="bullet") for t in items],
        bulletType="bullet", start="•", leftIndent=20,
    )


def cover(s: dict) -> list:
    today = date.today().strftime("%B %Y")
    return [
        Spacer(1, 4 * cm),
        Paragraph("HisabBot", s["Title"]),
        Paragraph(
            "A WhatsApp Bookkeeping Assistant for Pakistani Kirana Shops",
            s["Tagline"],
        ),
        Spacer(1, 1 * cm),
        Paragraph(
            "Voice-first, multilingual, self-improving — meet shopkeepers"
            " where they already are.",
            s["BodyL"],
        ),
        Spacer(1, 2.5 * cm),
        _hero_table(s),
        Spacer(1, 3 * cm),
        Paragraph(f"Project status snapshot · {today}", s["CoverMeta"]),
        Paragraph(
            "Author: Sumair · Built with Claude Code"
            " · Repository: github.com/sumair95/hisabbot",
            s["CoverMeta"],
        ),
        PageBreak(),
    ]


def _hero_table(s: dict) -> Table:
    data = [
        ["Stage", "Live, in beta"],
        ["Live URL", "hisabbot-production-aa5a.up.railway.app"],
        ["Tech", "FastAPI · Postgres · Claude · Whisper · WhatsApp"],
        ["Languages", "Urdu · Roman-Urdu · English"],
        ["Target unit cost", "≈ PKR 30 / shop / month"],
        ["Target price", "PKR 299 / shop / month"],
    ]
    rows = [[Paragraph(f"<b>{k}</b>", s["BodyL"]), Paragraph(v, s["BodyL"])] for k, v in data]
    t = Table(rows, colWidths=[5 * cm, 11 * cm], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, MUTED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def executive_summary(s: dict) -> list:
    return [
        Paragraph("Executive Summary", s["H1"]),
        Paragraph(
            "HisabBot is a WhatsApp-native bookkeeping assistant for"
            " Pakistan's 4 million-plus kirana (general store) shopkeepers."
            " They speak to it the way they speak to a clerk — in Urdu,"
            " Roman-Urdu, or English, by voice or by text — and it records"
            " every sale, credit, and payment, tracks per-customer balances,"
            " and sends a complete daily summary at 10 PM.",
            s["Body"],
        ),
        Paragraph(
            "There is no app to install, no buttons to press, no English"
            " forms to fill. The shopkeeper opens WhatsApp — which is"
            " already on their phone and which they already use every day —"
            " and starts talking. The bot understands.",
            s["Body"],
        ),
        Paragraph("What is built and live today", s["H2"]),
        _bullet_list([
            "End-to-end voice + text bookkeeping over WhatsApp Cloud API.",
            "Customer/supplier ledgers with running balances, derived live"
            " from a single source of truth (no double-counting).",
            "Daily 10 PM summary in the shopkeeper's chosen language.",
            "Voice notes pre-cleaned (noise reduction, loudness normalization,"
            " silence trim) before transcription, with rejection of"
            " unintelligible recordings before any API spend.",
            "Self-improving speech recognition: each shop's vocabulary biases"
            " every future transcription, getting more accurate with use.",
            "Smart correction flow with a 60-second window: shopkeepers can"
            " edit or delete a recent entry naturally without hand-holding.",
            "Production-grade observability: structured logs, idempotent"
            " webhook handling, dead-letter queue for failed messages,"
            " full audit trail of every inbound and outbound message.",
        ], s["Bullet"]),
        Paragraph("Why this wins", s["H2"]),
        Paragraph(
            "Existing options for kirana bookkeeping are either "
            "<b>too expensive and complex</b> (full point-of-sale systems"
            " starting at PKR 1,500+ a month, requiring a tablet, training,"
            " and an English-comfortable operator) or "
            "<b>too primitive</b> (a paper rok-bahi that gets lost,"
            " miscalculated, or simply forgotten). HisabBot meets the"
            " shopkeeper at <b>their</b> existing tool, in <b>their</b>"
            " language, with <b>their</b> natural input mode (speaking)."
            " Marginal cost stays under PKR 30 a month per shop while"
            " supporting unlimited transactions.",
            s["Body"],
        ),
        PageBreak(),
    ]


def the_problem(s: dict) -> list:
    return [
        Paragraph("The Problem", s["H1"]),
        Paragraph(
            "Pakistan has more than four million kirana shops — small,"
            " family-run general stores selling everyday groceries,"
            " household goods, and snacks. They are the backbone of urban"
            " and semi-urban retail, and almost every one of them runs on"
            " informal credit (udhaar) extended to regular customers.",
            s["Body"],
        ),
        Paragraph("How shopkeepers currently track money", s["H2"]),
        _bullet_list([
            "<b>Paper ledger (rok-bahi)</b> — handwritten, language-mixed,"
            " sometimes lost or destroyed.",
            "<b>Mental memory</b> — the shopkeeper remembers who owes what;"
            " disputes happen.",
            "<b>WhatsApp messages to themselves</b> — informal notes that"
            " never aggregate into a real summary.",
            "<b>Spreadsheets</b> (rare) — only the most digitally-fluent"
            " shopkeepers, and even they don't fill them in consistently.",
        ], s["Bullet"]),
        Paragraph("Why off-the-shelf tools haven't worked", s["H2"]),
        _bullet_list([
            "<b>POS systems</b> require dedicated hardware (tablet/PC),"
            " training, English-language UIs, and PKR 1,000–3,000+ monthly"
            " fees.",
            "<b>Accounting apps</b> assume the user can read English"
            " interfaces and type with confidence.",
            "<b>Voice assistants</b> built abroad (Alexa, Google) don't"
            " understand Roman-Urdu code-mixed speech and aren't designed"
            " for transactional bookkeeping.",
            "<b>Existing local apps</b> are often little more than a"
            " digital ledger — they replace the rok-bahi but don't reduce"
            " the cognitive load of remembering, calculating, or"
            " summarizing.",
        ], s["Bullet"]),
        Paragraph("Three observations that shaped HisabBot", s["H2"]),
        Paragraph(
            "<b>1. WhatsApp is universal.</b> Every shopkeeper has it,"
            " uses it daily, and trusts it. Nothing has higher penetration"
            " in this segment.",
            s["Body"],
        ),
        Paragraph(
            "<b>2. Voice beats typing.</b> Shopkeepers speak Urdu/Roman-Urdu"
            " comfortably; many would rather not type, especially in a"
            " busy shop. A 5-second voice note is faster than typing the"
            " same transaction.",
            s["Body"],
        ),
        Paragraph(
            "<b>3. The bot must be a clerk, not a form.</b> Successful"
            " digital tools in this market mimic an existing relationship"
            " (a trusted clerk, an accountant) rather than asking the user"
            " to learn a new abstract interface.",
            s["Body"],
        ),
        PageBreak(),
    ]


def the_solution(s: dict) -> list:
    return [
        Paragraph("Our Solution: HisabBot", s["H1"]),
        Paragraph(
            "HisabBot is a WhatsApp number the shopkeeper messages. They"
            " send a quick voice note or text in whatever language and"
            " phrasing comes naturally. The bot listens, understands, and"
            " writes the transaction to a private ledger — then confirms"
            " back in the same language.",
            s["Body"],
        ),
        Paragraph("A typical day with HisabBot", s["H2"]),
        Paragraph(
            "<b>Morning, 9:30 AM</b><br/>"
            "<b>Shopkeeper</b> (voice note): <i>“Ahmed bhai ko 500 ka"
            " udhaar diya, 2 kilo cheeni”</i><br/>"
            "<b>Bot</b>: ✅ Ahmed ko PKR 500 udhaar.<br/>"
            "📦 cheeni 2kg<br/>"
            "Kul udhaar Ahmed ka: PKR 1,200",
            s["Body"],
        ),
        Paragraph(
            "<b>Afternoon, 3:15 PM</b><br/>"
            "<b>Shopkeeper</b> (text): <i>“450 ki coke ki bottle ki sale"
            " hoye”</i><br/>"
            "<b>Bot</b>: ✅ Cash sale PKR 450.<br/>"
            "📦 coke 1 bottle — PKR 450",
            s["Body"],
        ),
        Paragraph(
            "<b>Evening, 6:00 PM</b><br/>"
            "<b>Shopkeeper</b> (voice): <i>“Bilal se 300 wapas mile”</i><br/>"
            "<b>Bot</b>: ✅ Bilal se PKR 300 received.<br/>"
            "Bilal ka baqi udhaar: PKR 0 — hisaab clear ho gaya. ✅",
            s["Body"],
        ),
        Paragraph(
            "<b>10:00 PM — automatic daily summary</b><br/>"
            "🧾 Aaj ka Hisaab — 06 May 2026<br/>"
            "💰 Cash Sales: PKR 8,750<br/>"
            "📝 Udhaar Sales: PKR 3,400<br/>"
            "💵 Paisay Mile: PKR 2,100<br/>"
            "📦 Supplier ko Diye: PKR 4,500<br/>"
            "🔴 Udhaar Lene Wale (Top): Ahmed (1,200), Khalid (800)…<br/>"
            "Kul Sales: PKR 12,150",
            s["Body"],
        ),
        Paragraph("What the shopkeeper does NOT have to do", s["H2"]),
        _bullet_list([
            "Install an app or sign up on a website",
            "Read English forms or fill structured fields",
            "Remember exact phrasings or commands",
            "Manually total daily sales",
            "Look up customer balances on paper",
            "Lose a ledger when a notebook gets damaged",
        ], s["Bullet"]),
        PageBreak(),
    ]


def how_it_works(s: dict) -> list:
    return [
        Paragraph("How It Works", s["H1"]),
        Paragraph(
            "Every WhatsApp message — text or voice — flows through the"
            " same pipeline. Below is the journey of a single voice note,"
            " from the shopkeeper's lips to a row in the database.",
            s["Body"],
        ),
        Paragraph("The voice-note pipeline", s["H2"]),
        Paragraph(
            "1) WhatsApp delivers the voice note (OGG/Opus audio) to our"
            " webhook on Railway.<br/>"
            "2) The bot fetches the audio bytes from WhatsApp, in parallel"
            " with looking up the shopkeeper in the database.<br/>"
            "3) The audio is cleaned: a high-pass filter cuts low-frequency"
            " rumble (fans, traffic), an FFT denoiser suppresses background"
            " noise, loudness normalization brings quiet voices to broadcast"
            " level, and silence is trimmed from start and end.<br/>"
            "4) Voice Activity Detection (VAD) checks whether there is any"
            " actual speech in the cleaned audio. Empty or pure-noise"
            " recordings are rejected immediately — no API spend, polite"
            " reply asking for a re-record.<br/>"
            "5) The bot fetches this shop's vocabulary list (its known"
            " customers, suppliers, and recent products) and feeds it to"
            " Whisper as biasing context. Whisper produces stable, accurate"
            " transcripts of proper nouns it would otherwise mis-spell.<br/>"
            "6) Whisper returns the transcript along with confidence"
            " metrics. If Whisper is uncertain, the transcript is rejected"
            " and the bot asks for a clearer recording.<br/>"
            "7) The transcript goes to Claude Haiku 4.5, an LLM, which"
            " classifies the intent (TRANSACTION, QUERY, REMINDER,"
            " CORRECTION, SETTINGS_CHANGE…) and extracts structured fields"
            " — amount, customer name, items.<br/>"
            "8) The orchestrator resolves customer names against the"
            " existing contact list using fuzzy matching, writes the"
            " transaction to Postgres, and computes the new balance.<br/>"
            "9) A receipt-style confirmation is sent back to the shopkeeper"
            " in their preferred language.",
            s["BodyL"],
        ),
        Paragraph(
            "Total round-trip: roughly 2–3 seconds for a clean voice note.",
            s["Caption"],
        ),
        Paragraph("Architecture diagram", s["H2"]),
        Paragraph(
            "<font color='#1a365d'><b>Shopkeeper (WhatsApp)</b></font><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓&nbsp;voice / text<br/>"
            "<font color='#2b6cb0'>WhatsApp Cloud API webhook</font><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2b6cb0'>FastAPI on Railway</font>"
            " — signature check, dedup, async dispatch<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2c7a7b'>Audio preprocessing</font>"
            " (ffmpeg + webrtcvad) — clean and validate<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2c7a7b'>Whisper-large-v3 on Groq</font>"
            " — STT with per-shop biasing<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2c7a7b'>Claude Haiku 4.5 (Anthropic)</font>"
            " — intent classification + field extraction<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2c7a7b'>Orchestrator</font>"
            " — fuzzy contact match, business rules, state machine<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#1a365d'><b>Postgres on Supabase</b></font>"
            " — single source of truth, view-derived balances<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
            "<font color='#2b6cb0'>Reply via WhatsApp Cloud API</font>",
            s["Body"],
        ),
        PageBreak(),
    ]


def build_journey(s: dict) -> list:
    timeline = [
        ("2026-04-20", "Project scaffold",
         "FastAPI app, Postgres schema, fuzzy name matcher, prompt design,"
         " Roman-Urdu/Urdu/English reply templates. 21 unit tests."),
        ("2026-04-21", "Production deployment",
         "Live on Railway. Supabase schema applied. WhatsApp webhook"
         " registered with Meta. End-to-end test passed."),
        ("2026-04-30", "STT migration to Groq",
         "Switched speech-to-text from OpenAI's older Whisper model to"
         " Groq's whisper-large-v3 — about 3× cheaper, faster, and more"
         " accurate on Urdu."),
        ("2026-05-01", "Daily summary correctness fix",
         "Bottom-line total previously netted borrower repayments and"
         " supplier payments into the headline figure. Changed to show"
         " sales-only total; per-customer payments stay as line items."),
        ("2026-05-02", "Shop-name rename via LLM intent",
         "Initial keyword approach failed on voice transcripts. Added a"
         " new SETTINGS_CHANGE intent to the LLM extractor; both single-"
         "message (\"naam Ahmed Store rakh do\") and two-step (\"naam"
         " galat hai\" → bot asks for new name) flows now work."),
        ("2026-05-04", "Per-shop Whisper vocabulary biasing",
         "Each shop's customer/supplier/product list is fed to Whisper as"
         " biasing context on every call. Self-improving by design — the"
         " bot transcribes more accurately as the shopkeeper logs more"
         " transactions."),
        ("2026-05-04", "Quieter receipts + 60-second correction window",
         "Removed redundant daily-total chatter from per-transaction"
         " replies. Vague \"galat hai\" / \"undo\" never auto-deletes"
         " anymore — bot asks delete-or-change. Multi-message"
         " disambiguation when several entries are recent."),
        ("2026-05-05", "STT noise resilience pipeline",
         "Audio cleaning (ffmpeg: high-pass, FFT denoise, loudness"
         " normalization, silence trim), Voice Activity Detection,"
         " confidence-based rejection. Handles loud kirana environments"
         " gracefully."),
    ]

    rows = [["Date", "Milestone", "What it means"]]
    for d, t, desc in timeline:
        rows.append([
            Paragraph(d, s["BodyL"]),
            Paragraph(f"<b>{t}</b>", s["BodyL"]),
            Paragraph(desc, s["BodyL"]),
        ])
    table = Table(rows, colWidths=[2.7 * cm, 5.0 * cm, 9.0 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, MUTED),
    ]))

    return [
        Paragraph("The Build Journey", s["H1"]),
        Paragraph(
            "Every change below is committed to git and documented in"
            " WORKLOG.md and CHANGELOG.md inside the repository. Versions"
            " run from 0.1.0 (initial scaffold) through 0.4.0 (current).",
            s["Body"],
        ),
        Spacer(1, 4 * mm),
        table,
        PageBreak(),
    ]


def innovations(s: dict) -> list:
    callouts = [
        ("Voice-first, multilingual by default",
         "Shopkeepers don't have to learn the bot's language — the bot"
         " learns theirs. Urdu script, Roman-Urdu, English, and natural"
         " code-mixing all work. The bot replies in whichever language the"
         " shopkeeper has set; switching is a one-word command."),
        ("Self-improving speech recognition",
         "On every voice call, Whisper receives a biasing prompt built"
         " live from this shop's known customers, suppliers, and recent"
         " products. As the ledger grows, transcription gets more"
         " accurate for proper nouns. New customers added today appear"
         " in the prompt for tomorrow's voice notes — automatically."),
        ("LLM intent classification, not keyword matching",
         "Early versions tried regex-style keyword detection for"
         " commands like \"change shop name\". Voice transcripts vary"
         " too much for keywords to keep up. We replaced that with"
         " explicit LLM intents (TRANSACTION, QUERY, CORRECTION,"
         " SETTINGS_CHANGE) and few-shot examples. The bot now"
         " understands natural phrasing in any of the three languages."),
        ("Recency-scoped corrections",
         "When a shopkeeper says \"galat hai\" (it's wrong), the bot"
         " never auto-deletes. It looks at transactions from the last 60"
         " seconds, asks delete-or-change, and disambiguates if multiple"
         " recent entries exist. Old entries can still be edited with"
         " specific references (\"Ahmed wala 600 nahi 500 tha\")."),
        ("Noise-resilient audio pipeline",
         "Kirana shops are noisy. Every voice note is cleaned by an"
         " ffmpeg pipeline — high-pass filter, FFT denoiser, loudness"
         " normalization, silence trim — before transcription. A separate"
         " Voice Activity Detection step rejects pocket recordings and"
         " pure-noise audio before any API call is made."),
        ("Confidence-aware transcription",
         "Whisper itself returns confidence metrics on every call. We"
         " refuse low-confidence transcripts (so they never reach the"
         " LLM) and ask the shopkeeper to record again with less"
         " background noise — a safer outcome than logging garbage."),
        ("Cost-optimized model stack",
         "Claude Haiku for primary extraction with prompt caching"
         " (~10× cheaper on cached prefix), OpenAI gpt-4o-mini as a"
         " resilience fallback, Groq's Whisper-large-v3 for STT (3×"
         " cheaper than OpenAI's hosted Whisper). Every component was"
         " chosen on a per-cent-per-message basis."),
        ("Production-grade audit trail",
         "Every inbound and outbound message is logged with the full"
         " extraction JSON, the linked transaction (if any), and the"
         " language detected. Failed messages go to a dead-letter table."
         " A WhatsApp message ID dedupe prevents double-billing on"
         " retried webhooks. Soft-delete only — no transaction is ever"
         " hard-deleted."),
    ]
    out = [Paragraph("Key Innovations", s["H1"])]
    for title, body in callouts:
        out.append(Paragraph(title, s["H3"]))
        out.append(Paragraph(body, s["Body"]))
    out.append(PageBreak())
    return out


def architecture_deep(s: dict) -> list:
    rows = [
        ["Layer", "Technology", "Why this choice"],
        ["Messaging", "WhatsApp Cloud API",
         "Universal reach in target market; official Meta API; no"
         " unofficial workarounds."],
        ["HTTP / Webhook", "FastAPI",
         "Async by default, low latency, cleanest Python framework for"
         " webhooks; native Pydantic validation."],
        ["Database", "Postgres on Supabase",
         "Battle-tested. Balances are derived from a Postgres view"
         " (single source of truth). pg_trgm for fuzzy matching."],
        ["DB driver", "asyncpg + raw SQL",
         "No ORM. Queries are few and read more clearly as SQL than as"
         " query-builder calls."],
        ["LLM (extraction)", "Anthropic Claude Haiku 4.5",
         "Strong Urdu/Roman-Urdu performance, cost-effective with prompt"
         " caching enabled."],
        ["LLM (fallback)", "OpenAI gpt-4o-mini",
         "If Anthropic fails or rate-limits, extraction falls back here"
         " automatically. Same JSON contract."],
        ["TTS", "OpenAI tts-1 (voice replies)",
         "Optional voice replies for shopkeepers who prefer audio."],
        ["STT", "Groq whisper-large-v3",
         "OpenAI-compatible API, ~3× cheaper than OpenAI's hosted"
         " Whisper, 5× faster on Groq's LPU hardware."],
        ["Audio preprocessing", "ffmpeg + webrtcvad",
         "Standard tools, well-understood; ffmpeg's loudnorm and afftdn"
         " are production-grade for noise reduction."],
        ["Fuzzy matching", "rapidfuzz",
         "Pure-Python WRatio scoring — handles Roman-Urdu name spelling"
         " variants without needing embeddings."],
        ["Scheduling", "APScheduler",
         "Daily 10 PM summary. In-process, no external scheduler"
         " required."],
        ["Hosting", "Railway",
         "Container deploy, autoscaling, managed env-var storage,"
         " minimal Ops overhead at this scale."],
    ]
    formatted = [[
        Paragraph(f"<b>{r[0]}</b>", s["BodyL"]),
        Paragraph(r[1], s["BodyL"]),
        Paragraph(r[2], s["BodyL"]),
    ] for r in rows[1:]]
    formatted.insert(0, [
        Paragraph("<b>Layer</b>", s["BodyL"]),
        Paragraph("<b>Technology</b>", s["BodyL"]),
        Paragraph("<b>Why this choice</b>", s["BodyL"]),
    ])
    table = Table(formatted, colWidths=[3.5 * cm, 4.5 * cm, 9 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    return [
        Paragraph("Technical Architecture", s["H1"]),
        Paragraph(
            "Each layer was chosen to optimise for one of: cost,"
            " developer ergonomics, or Pakistan-market suitability. The"
            " overall principle is to use boring, mature tooling wherever"
            " possible and reserve the novel choices for places where"
            " they unlock real wins (LLM-based extraction, voice-as-input,"
            " self-improving vocabulary biasing).",
            s["Body"],
        ),
        Spacer(1, 4 * mm),
        table,
        Paragraph("Reliability and observability", s["H2"]),
        _bullet_list([
            "<b>Idempotency:</b> every WhatsApp message has an ID; we"
            " store IDs we have already processed and ignore duplicates"
            " (Meta retries are common).",
            "<b>Signature verification:</b> X-Hub-Signature-256 HMAC is"
            " validated on every inbound call; bad signatures are rejected"
            " before processing.",
            "<b>Dead-letter queue:</b> any message whose handler fails is"
            " saved to a `failed_messages` table with the original payload"
            " and error, so nothing is silently lost.",
            "<b>Soft delete:</b> transactions are never hard-deleted —"
            " the audit trail is permanent.",
            "<b>Structured logging:</b> JSON logs in production carry"
            " every key field (shop ID, message ID, intent, confidence"
            " metrics, latency).",
            "<b>Health checks:</b> `/healthz` lists missing configuration"
            " and is hit by Railway's deploy verification.",
        ], s["Bullet"]),
        PageBreak(),
    ]


def cost_economics(s: dict) -> list:
    rows = [
        ["Cost driver", "Per-message", "At 10k msg/month/shop", "Notes"],
        ["LLM (extraction)", "≈ PKR 0.40", "≈ PKR 4,000",
         "Cached system prompt drops cost ~10× on cache hits."],
        ["STT (Groq Whisper)",
         "≈ PKR 0.10 / voice min", "≈ PKR 100 (avg shop)",
         "Most messages are text; voice averages ~30s/day."],
        ["Database (Supabase)", "—", "≈ PKR 1,500 / month base",
         "Shared across all shops; per-shop incremental ≈ 0."],
        ["WhatsApp Cloud API",
         "Free for service msgs", "—",
         "Pay only for marketing-template-initiated convos (we don't)."],
        ["Hosting (Railway)", "—", "≈ PKR 1,500 / month base",
         "Single FastAPI container; scales horizontally if needed."],
        ["Total marginal /shop", "—", "≈ PKR 30 / month",
         "Per-shop infra cost at 100-shop fleet, with caching."],
    ]
    formatted = [[Paragraph(c, s["BodyL"]) for c in row] for row in rows]
    t = Table(formatted, colWidths=[4 * cm, 3 * cm, 3.5 * cm, 6.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [
        Paragraph("Cost Economics", s["H1"]),
        Paragraph(
            "Unit economics are healthy from day one, with significant"
            " room to compress as we move down the model and infrastructure"
            " price curves.",
            s["Body"],
        ),
        Spacer(1, 4 * mm),
        t,
        Paragraph("Pricing model", s["H2"]),
        _bullet_list([
            "<b>Basic tier:</b> PKR 299 / shop / month — unlimited"
            " messages, daily summary, voice replies, all current"
            " features.",
            "<b>Free trial:</b> 14 days, no credit card.",
            "<b>Future tiers (post-launch):</b> per-customer reminders,"
            " inventory tracking, multi-employee, weekly/monthly P&L.",
        ], s["Bullet"]),
        Paragraph("Why the margin holds at scale", s["H2"]),
        Paragraph(
            "Anthropic prompt caching makes the per-call LLM cost almost"
            " flat in shop count. STT cost is bounded by voice-minute"
            " usage, which has a natural ceiling per shopkeeper (no one"
            " sends thousands of voice notes a day). Database and hosting"
            " costs amortise across the entire fleet. At 1,000 shops we"
            " expect marginal cost to drop from PKR 30 to roughly PKR 12.",
            s["Body"],
        ),
        PageBreak(),
    ]


def roadmap(s: dict) -> list:
    return [
        Paragraph("Roadmap", s["H1"]),
        Paragraph("Near-term (next 2–4 weeks)", s["H2"]),
        _bullet_list([
            "<b>STT phase 4:</b> A/B test Whisper-large-v3-turbo on Groq"
            " (~2× faster). If accuracy holds, ship for ~600 ms latency"
            " reduction per voice note.",
            "<b>STT phase 5:</b> Phonetic post-processing — catalog the"
            " systematic Whisper errors observed in production traffic"
            " and apply targeted fixes after STT, before LLM.",
            "<b>Two-contact disambiguation:</b> the bot already asks"
            " \"kaun sa Ahmed?\" when fuzzy matching is ambiguous;"
            " refine the threshold based on real shop data.",
            "<b>Customer reminders:</b> shopkeeper says \"Ahmed ko kal"
            " 500 yaad dilana\"; bot pings them at the chosen date."
            " Schema and intent already in place; needs cron wiring.",
        ], s["Bullet"]),
        Paragraph("Medium-term (1–3 months)", s["H2"]),
        _bullet_list([
            "<b>Self-improving phase 2 — dynamic LLM few-shot:</b>"
            " maintain a rolling buffer of each shop's recent successful"
            " extractions and inject them as additional examples in the"
            " LLM prompt. Adapts the bot to each shopkeeper's individual"
            " phrasing.",
            "<b>Self-improving phase 3 — alias dictionary:</b> when a"
            " shopkeeper does fix_customer (\"Ahmed nahi Ali tha\"), log"
            " the (heard, correct) pair. Use it as both a Whisper biasing"
            " hint and an LLM extraction rule.",
            "<b>Weekly and monthly summaries</b> on demand.",
            "<b>Customer-facing reminders</b> sent from the shopkeeper's"
            " number with one-tap approval (highest-value follow-on)."
        ], s["Bullet"]),
        Paragraph("Longer-term (3–9 months)", s["H2"]),
        _bullet_list([
            "<b>Inventory tracking</b> — link sales to a stock"
            " ledger; alert on low stock.",
            "<b>Photo-of-receipt extraction</b> — shopkeeper sends a"
            " supplier invoice as an image; bot extracts line items.",
            "<b>Multi-employee per shop</b> — shop owner assigns one or"
            " more numbers as authorised data-entry phones.",
            "<b>Bank/EasyPaisa integration</b> — auto-reconcile inbound"
            " payments against credit ledger.",
        ], s["Bullet"]),
        Paragraph("Explicitly NOT in scope (yet)", s["H2"]),
        Paragraph(
            "Inventory management, full POS, web/mobile dashboards,"
            " automated invoicing, and real-time payment processing are"
            " each multi-month rabbit holes that don't move the wedge"
            " for our first 1,000 shops. We earn the right to build them"
            " by nailing the bookkeeping core first.",
            s["Body"],
        ),
        PageBreak(),
    ]


def differentiators(s: dict) -> list:
    rows = [
        ["", "Paper rok-bahi", "Local POS apps", "Generic accounting", "HisabBot"],
        ["Cost / month",
         "PKR 0", "PKR 1,000–3,000+", "PKR 1,500+", "PKR 299"],
        ["Hardware needed", "Pen + book", "Tablet/PC", "PC", "Already on phone"],
        ["English required", "No", "Yes", "Yes", "No"],
        ["Voice input", "—", "Rare", "No", "Yes (default)"],
        ["Setup time", "0", "Hours/days", "Days", "1 minute"],
        ["Lost-data risk", "High", "Low", "Low", "Low"],
        ["Daily summary", "Manual", "Yes", "Yes", "Automatic, voice"],
        ["Customer balance", "Memory", "Yes", "Yes", "Always live"],
    ]
    formatted = [[Paragraph(c, s["BodyL"]) for c in row] for row in rows]
    # Bold header row
    formatted[0] = [Paragraph(f"<b>{r}</b>", s["BodyL"]) for r in rows[0]]
    # Bold left column
    for i in range(1, len(formatted)):
        formatted[i][0] = Paragraph(f"<b>{rows[i][0]}</b>", s["BodyL"])

    table = Table(formatted, colWidths=[3.5 * cm, 2.7 * cm, 3.3 * cm, 3.3 * cm, 3.7 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (-1, 0), (-1, -1), colors.HexColor("#e6fffa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, MUTED),
    ]))

    return [
        Paragraph("Why HisabBot Wins", s["H1"]),
        Paragraph(
            "Most digital-bookkeeping efforts in this market die at the"
            " adoption stage — the shopkeeper either can't or won't"
            " switch behaviour. HisabBot wins by not asking them to."
            " Same WhatsApp, same language, same way they already speak"
            " about money. The product is the conversation.",
            s["Body"],
        ),
        Spacer(1, 4 * mm),
        table,
        Paragraph("Defensibility", s["H2"]),
        Paragraph(
            "<b>Network effects of vocabulary:</b> the more transactions"
            " a shop logs, the more accurate the bot becomes for that"
            " specific shop. A new entrant starts from zero and has to"
            " catch up customer by customer.<br/>"
            "<b>Data moat for fine-tuning:</b> we accumulate"
            " (audio, correct-transcript) and (correction, fix) pairs"
            " over time — this becomes a private dataset for future"
            " model tuning that no competitor can replicate cheaply.<br/>"
            "<b>Distribution lock-in:</b> WhatsApp is the entry point;"
            " switching costs for the shopkeeper are real (re-onboarding"
            " all customers, history loss).",
            s["Body"],
        ),
        PageBreak(),
    ]


def glossary(s: dict) -> list:
    terms = [
        ("API",
         "Application Programming Interface. The standard way two"
         " software systems talk to each other over the network."),
        ("Cloud", "A remote server you rent rather than own."),
        ("FastAPI",
         "The Python web framework HisabBot's server is built on."),
        ("Few-shot examples",
         "Sample input/output pairs included in an AI prompt to teach"
         " the model the desired behaviour without retraining it."),
        ("ffmpeg",
         "The standard open-source tool for processing audio and video."
         " HisabBot uses it to clean voice-note audio."),
        ("Fuzzy matching",
         "Matching text that's close-enough rather than exactly equal —"
         " e.g. recognising \"Ahmad\" and \"Ahmed\" as the same person."),
        ("Groq",
         "A company that runs AI models on custom hardware called LPUs"
         " (Language Processing Units), much faster than typical GPUs."),
        ("Idempotent",
         "An operation that can be repeated safely without changing"
         " the outcome — important so retried webhook calls don't"
         " double-charge anyone."),
        ("Intent",
         "The high-level meaning of a message — \"is this a sale, a"
         " query, a correction?\""),
        ("Kirana",
         "Pakistan/India term for a small general/grocery store."),
        ("LLM",
         "Large Language Model — the kind of AI that powers ChatGPT and"
         " Claude. HisabBot uses one to understand what shopkeepers"
         " mean."),
        ("LPU",
         "Language Processing Unit — Groq's custom AI hardware,"
         " optimised for speed."),
        ("Postgres",
         "An open-source database. HisabBot's transactions, customers,"
         " and shopkeeper records live here."),
        ("POS",
         "Point of Sale — the cash-register-and-software system used in"
         " modern retail."),
        ("Prompt caching",
         "An Anthropic feature that stores a long unchanging prompt"
         " prefix on their side, making repeated calls ~10× cheaper."),
        ("rok-bahi (روک بہی)",
         "The traditional handwritten ledger used by Pakistani"
         " shopkeepers."),
        ("STT",
         "Speech-to-Text — the technology that turns spoken words into"
         " written text. Whisper is the model HisabBot uses."),
        ("Soft delete",
         "Marking a database row as \"deleted\" without actually erasing"
         " it. Lets you undo and audit later."),
        ("Supabase",
         "A managed Postgres database service. HisabBot's data lives"
         " on their infrastructure."),
        ("TTS",
         "Text-to-Speech — turning written text into spoken audio."
         " Used for voice replies."),
        ("udhaar (ادھار)",
         "Credit extended to a customer — they take goods now and pay"
         " later."),
        ("VAD",
         "Voice Activity Detection — software that decides whether a"
         " given chunk of audio contains real speech or just silence/"
         "noise."),
        ("Webhook",
         "A URL that another service calls whenever an event happens —"
         " e.g. WhatsApp calls our webhook every time a shopkeeper sends"
         " a message."),
        ("Whisper",
         "OpenAI's open-source speech-recognition model, considered"
         " state of the art for multilingual transcription."),
    ]
    rows = [[Paragraph(f"<b>{term}</b>", s["BodyL"]),
             Paragraph(definition, s["BodyL"])] for term, definition in terms]
    table = Table(rows, colWidths=[4.0 * cm, 12.5 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [
        Paragraph("Glossary — Plain-English Definitions", s["H1"]),
        Paragraph(
            "For readers without a software background. Skip if you've"
            " seen these terms before.",
            s["Caption"],
        ),
        Spacer(1, 4 * mm),
        table,
    ]


# ---------------------------------------------------------------------------
# Page template & build
# ---------------------------------------------------------------------------

def _on_page(canvas, doc):
    """Footer on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    page_w = A4[0]
    canvas.drawCentredString(
        page_w / 2, 1.0 * cm,
        f"HisabBot · Project Status · Page {doc.page}",
    )
    canvas.restoreState()


def build_pdf(output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="HisabBot — Project Status",
        author="Sumair",
        subject="WhatsApp Bookkeeping Assistant for Pakistani Kirana Shops",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="all", frames=frame, onPage=_on_page)])

    s = _styles()
    story: list = []
    story += cover(s)
    story += executive_summary(s)
    story += the_problem(s)
    story += the_solution(s)
    story += how_it_works(s)
    story += build_journey(s)
    story += innovations(s)
    story += architecture_deep(s)
    story += cost_economics(s)
    story += roadmap(s)
    story += differentiators(s)
    story += glossary(s)

    doc.build(story)

    return output_path.stat().st_size


if __name__ == "__main__":
    size = build_pdf(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH} ({size:,} bytes)")
