"""
Canonical transaction schema and transaction_id generation.

amount is always stored as a string of a Python Decimal to avoid float rounding.
transaction_id is a SHA-256 hash that is stable across re-exports of the same data.
"""

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


# Valid enum values
SOURCE_TYPES = {"bank", "card", "brokerage", "manual"}
DIRECTIONS = {"debit", "credit"}
EXPENSE_TYPES = {"fixed", "variable", "transfer", "investment", "income", "savings"}
REVIEW_STATUSES = {"auto", "llm", "corrected", "needs_review"}


@dataclass
class Transaction:
    # Identity
    transaction_id: str = ""

    # Source
    source_account: str = ""
    source_type: str = ""           # bank | card | brokerage | manual
    source_file: str = ""           # audit trail only — not used in transaction_id
    source_row_id: str = ""

    # Timing
    statement_month: str = ""       # YYYY-MM
    transaction_date: str = ""      # YYYY-MM-DD
    posted_date: str = ""           # YYYY-MM-DD, optional

    # Description
    raw_description: str = ""
    normalized_merchant: str = ""

    # Amount
    amount: str = "0"               # Always positive, stored as Decimal string
    currency: str = "CAD"           # ISO-4217
    direction: str = ""             # debit | credit

    # Classification
    category: str = ""
    subcategory: str = ""
    expense_type: str = ""          # fixed | variable | transfer | investment | income | savings
    split_tag: str = ""             # personal | shared | null

    # Flags
    recurring_flag: bool = False
    transfer_flag: bool = False
    review_status: str = "needs_review"  # auto | llm | corrected | needs_review

    notes: str = ""

    def amount_decimal(self) -> Decimal:
        try:
            return Decimal(self.amount)
        except InvalidOperation:
            raise ValueError(f"Invalid amount: {self.amount!r}")

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "source_account": self.source_account,
            "source_type": self.source_type,
            "source_file": self.source_file,
            "source_row_id": self.source_row_id,
            "statement_month": self.statement_month,
            "transaction_date": self.transaction_date,
            "posted_date": self.posted_date,
            "raw_description": self.raw_description,
            "normalized_merchant": self.normalized_merchant,
            "amount": self.amount,
            "currency": self.currency,
            "direction": self.direction,
            "category": self.category,
            "subcategory": self.subcategory,
            "expense_type": self.expense_type,
            "split_tag": self.split_tag,
            "recurring_flag": str(self.recurring_flag),
            "transfer_flag": str(self.transfer_flag),
            "review_status": self.review_status,
            "notes": self.notes,
        }

    @classmethod
    def csv_headers(cls) -> list[str]:
        return list(cls().to_dict().keys())


def make_transaction_id(source_account: str, transaction_date: str,
                        amount: str, direction: str, raw_description: str) -> str:
    """
    Stable SHA-256 hash for deduplication across re-exports.
    Does NOT include source_file (filename changes between exports).
    Includes direction to distinguish same-day charge/reversal pairs.
    """
    payload = "|".join([
        source_account.strip().lower(),
        transaction_date.strip(),
        str(Decimal(amount)),          # normalize decimal representation
        direction.strip().lower(),
        raw_description.strip().lower(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# RawTransaction: intermediate dict from parsers before normalization
# Fields: source_account, source_type, transaction_date, raw_description,
#         amount (str), direction, source_file, source_row_id
RawTransaction = dict
