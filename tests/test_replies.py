"""Smoke tests for the reply formatter strings."""
from datetime import date
from app.services import replies


def test_confirm_sale_credit_roman_urdu():
    msg = replies.confirm_sale_credit("Ahmed", 500, 1200)
    assert "Ahmed" in msg
    assert "500" in msg
    assert "1,200" in msg
    assert "undo" in msg.lower()


def test_confirm_sale_cash():
    msg = replies.confirm_sale_cash(300, 12500)
    assert "300" in msg
    assert "12,500" in msg


def test_reply_daily_sales():
    msg = replies.reply_daily_sales(cash=10000, credit=2500)
    assert "10,000" in msg
    assert "2,500" in msg
    assert "12,500" in msg  # total


def test_reply_who_owes_me_empty():
    msg = replies.reply_who_owes_me([])
    assert "nahi" in msg.lower() or "no one" in msg.lower()


def test_reply_who_owes_me_with_rows():
    rows = [
        {"name": "Ahmed", "balance": 1200},
        {"name": "Bilal", "balance": 800},
    ]
    msg = replies.reply_who_owes_me(rows)
    assert "Ahmed" in msg
    assert "Bilal" in msg
    assert "2,000" in msg  # total


def test_customer_balance_owes():
    msg = replies.reply_customer_balance("Ahmed", 500)
    assert "500" in msg


def test_customer_balance_clear():
    msg = replies.reply_customer_balance("Ahmed", 0)
    assert "clear" in msg.lower()


def test_format_daily_summary():
    msg = replies.format_daily_summary(
        summary_date=date(2026, 4, 20),
        cash_sales=12500,
        credit_sales=3200,
        payments_received=1800,
        payments_made=5000,
        top_debtors=[{"name": "Ahmed", "balance": 1200}],
        top_suppliers=[{"name": "Akbar Trader", "balance": -15000}],
    )
    assert "12,500" in msg
    assert "Ahmed" in msg
    assert "Akbar Trader" in msg
    assert "15,000" in msg
    # net = 12500 + 1800 - 5000 = 9300
    assert "9,300" in msg
