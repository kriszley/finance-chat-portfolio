# finance-automation

Personal finance automation pipeline for Canadian bank accounts.

## Project layout

- `run.py` — CLI entry point, runs the full pipeline
- `scripts/core/` — categorize, normalize, deduplicate, detect_transfers, schema
- `scripts/ingest/` — bank-specific CSV parsers (scotiabank, bmo)
- `scripts/output/` — CSV export and Google Sheets writer
- `rules/merchant_rules.example.csv` — public synthetic categorization rules
- `config/accounts.example.yaml` — public synthetic account definitions

## Key conventions

- Amount is always positive, stored as Decimal string. Direction (`debit`/`credit`) indicates flow.
- `transaction_id` is SHA-256 of `account + date + amount + direction + description`. Never include `source_file`.
- Rules engine runs first (exact → contains → regex). LLM fallback only for unmatched transactions.
- Target month = `max(all_transaction_dates)[:7]`. Filter runs after normalize, before dedup.
- Python 3.9 compatible. Use `Optional[X]` not `X | None`.

## Testing

```bash
pytest tests/ -v
```

## Running the pipeline

```bash
python3 run.py
```

## Never do

- Edit `outputs/transactions_clean.csv` directly. Use `review_needed.csv` corrections workflow.
- Store API keys or secrets in the repo. Use environment variables or a secret manager.
- Add real transaction, account, or merchant data to tracked example files.
- Use `float` for money. Always `Decimal`.
