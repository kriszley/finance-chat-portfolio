# Security

## Intended use

Finance Chat Portfolio Edition is a single-user, local development application. Docker Compose binds the frontend and backend to `127.0.0.1`. It does not implement user authentication and must not be exposed directly to the internet or used as a multi-user service.

## Safe defaults

- Cloud AI is disabled until `ENABLE_CLOUD_LLM=true` is set explicitly.
- Uploaded files are limited to CSV and 10 MiB.
- Uploads receive server-generated opaque tokens; tool calls cannot select arbitrary local paths.
- Real inputs, outputs, databases, secrets, account configs, and customized rules are gitignored.
- Dependency resolutions are committed as lockfiles.

## Reporting

Please open a private GitHub security advisory rather than a public issue for a suspected vulnerability. Do not include real financial records, API keys, or credentials in a report.
