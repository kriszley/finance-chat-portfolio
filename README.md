# Finance Chat — Portfolio Edition

An in-progress, local-first personal-finance assistant that turns Canadian bank CSV exports into normalized transactions, monthly analysis, natural-language answers, and inline charts.

This repository is a sanitized portfolio snapshot. It contains synthetic examples only; personal configurations, categorization rules, bank exports, databases, generated reports, and secrets are gitignored.

> Local development project, not financial advice and not production-ready. See [PROJECT_STATUS.md](PROJECT_STATUS.md), [PRIVACY.md](PRIVACY.md), and [SECURITY.md](SECURITY.md).

## What it demonstrates

- A Next.js 15 / React 19 chat and visualization interface
- A FastAPI tool-execution API with SQLite and WAL mode
- A deterministic Python pipeline for parsing, normalization, deduplication, transfer detection, categorization, and reporting
- Rules-first classification with an explicitly opt-in cloud-LLM fallback
- Privacy boundaries for sensitive local data and security-focused upload handling
- Python unit/integration tests, a frontend production build, dependency lockfiles, and GitHub Actions CI

## Architecture

```text
Next.js chat UI
  ├─ upload proxy ────────────────┐
  └─ optional Anthropic chat      │
         │ tool calls             │
         v                        v
FastAPI tool API ──> Python transaction pipeline ──> SQLite
                          │
                          └─ optional Anthropic categorization
```

Next.js owns conversational model calls. FastAPI owns tool execution and SQLite access. The Python pipeline remains independently runnable and testable.

## Safe quick start

```bash
git clone https://github.com/kriszley/finance-chat-portfolio.git
cd finance-chat-portfolio
cp .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. Both services bind to `127.0.0.1`, and cloud AI is disabled by default.

To exercise the deterministic pipeline without sending data to a model:

```bash
mkdir -p finance-automation/inputs
cp examples/scotiabank-demo.csv finance-automation/inputs/
cd finance-automation
python3 -m pip install --require-hashes -r requirements.lock
python3 run.py
```

The checked-in configuration and transaction fixture are synthetic. Copy the `*.example.*` configuration or rule files to their runtime names only when privately customizing the project.

## Optional cloud AI

Read [PRIVACY.md](PRIVACY.md) first. Enabling cloud AI can send chat messages, queried transaction results, and unmatched transaction fields to Anthropic.

```dotenv
ENABLE_CLOUD_LLM=true
ANTHROPIC_API_KEY=your-key-from-your-secret-manager
```

Never use employer, client, or other third-party confidential data.

## Supported inputs

| Institution | Parser status |
|---|---|
| Scotiabank | Implemented |
| BMO | Implemented |
| RBC, EQ Bank, Tangerine, Questrade | Planned |

Questrade portfolio analysis is intentionally a separate project; this repository only has a planned parser entry and does not contain the Questrade research/risk system.

## Development

```bash
# Backend
python3 -m pip install --require-hashes -r backend/requirements.lock
pytest -q backend/tests

# Transaction pipeline
python3 -m pip install --require-hashes -r finance-automation/requirements.lock
pytest -q finance-automation/tests

# Frontend
cd frontend
npm ci
npm run build
```

## Repository layout

```text
frontend/             Next.js UI and server routes
backend/              FastAPI API, tool handlers, and SQLite access
finance-automation/   Deterministic transaction-processing pipeline
examples/             Synthetic data only
.github/workflows/    CI for Python tests and frontend build
```
