# Privacy model

This portfolio project processes financial data, so its safe default is local-only and cloud AI is disabled.

## What stays local by default

- Uploaded CSV files
- SQLite databases and generated reports
- Custom account configuration and categorization rules
- Google service-account credentials

The corresponding runtime paths are gitignored. The repository contains only synthetic examples.

## What leaves the machine when cloud AI is enabled

Setting `ENABLE_CLOUD_LLM=true` and configuring `ANTHROPIC_API_KEY` enables Anthropic calls. Depending on the action, the request can include:

- Chat messages
- Transaction descriptions and normalized merchant names
- Amounts, currencies, directions, dates, account types, and categories returned by tools
- Unmatched transaction fields sent for categorization

Do not enable this mode unless that data flow is acceptable. Never use employer, client, or other third-party confidential data in this project.

## Other optional external services

The Google Sheets exporter sends selected processed data to the workbook configured by the user. It is not enabled during the normal local run.

## Public-repository checklist

Before committing, confirm that `git status` does not include `.env`, bank exports, databases, output files, runtime account configs, runtime rules, or service-account JSON files.
