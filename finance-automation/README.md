# Finance automation pipeline

The local transaction-processing core used by Finance Chat Portfolio Edition.

```text
CSV -> parse -> normalize -> latest-month filter -> deduplicate
    -> detect transfers -> rules-first categorize -> export/report
```

Cloud categorization is disabled by default. Unknown transactions remain in the manual review queue unless both `ENABLE_CLOUD_LLM=true` and `ANTHROPIC_API_KEY` are configured. See the repository-level `PRIVACY.md` before enabling it.

## Supported parsers

| Institution | Status |
|---|---|
| Scotiabank | Implemented |
| BMO | Implemented |
| RBC, EQ Bank, Tangerine, Questrade | Planned |

## Run with synthetic data

```bash
python3 -m pip install --require-hashes -r requirements.lock
mkdir -p inputs
cp ../examples/scotiabank-demo.csv inputs/
python3 run.py
```

The pipeline automatically uses tracked `*.example.*` files when private runtime configs are absent. To customize it locally, create:

- `config/accounts.yaml`
- `config/sheets_config.yaml`
- `rules/merchant_rules.csv`
- `rules/transfer_rules.csv`

Those runtime files are gitignored. Manual category corrections create a private `merchant_rules.csv` from the public example before appending.

## Tests

```bash
pytest -q tests
```

Amounts remain positive Decimal strings; `direction` represents debit or credit. Transaction IDs are stable SHA-256 hashes of account, date, amount, direction, and description, excluding the source filename.
