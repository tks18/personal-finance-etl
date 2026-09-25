# Security Policy

Personal Finance ETL processes sensitive personal-finance data locally. Security reports should protect both the software and the financial information used with it.

## Supported versions

Security fixes are expected to target the latest published release. Older releases may not receive backported fixes unless explicitly stated.

Check [GitHub Releases](https://github.com/tks18/personal-finance-etl/releases) or [PyPI](https://pypi.org/project/personal-finance-etl/) for the current published version.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Use GitHub's private vulnerability-reporting/security-advisory workflow for this repository when available. If private vulnerability reporting is unavailable, contact the maintainer through a private channel listed on the maintainer's GitHub profile.

Include only the minimum information needed to reproduce and assess the issue:

```text
affected version
Python version
operating system
affected component
synthetic reproduction
expected / observed behaviour
security impact
sanitized logs
```

## Never submit real financial data

Do not attach or paste bank/broker statements, portfolio exports, tax documents, database files, raw Control Plane payloads, account numbers, tax identifiers, credentials, API keys, access tokens, addresses, or unsanitized execution logs into public issues, pull requests, discussions, or security reports.

Use synthetic examples or thoroughly sanitized reproductions.

## Security-relevant areas

Examples include:

- unintended disclosure of raw financial payloads,
- secrets written to logs,
- unsafe local database/file handling,
- path traversal or arbitrary file access,
- unsafe deserialization or command execution,
- permission bypass,
- sensitive information leaking through CLI/GUI output,
- dependency or packaging behaviour that creates a practical exploit path.

Ordinary financial-calculation bugs are generally correctness issues unless they create a security impact.

## Local-first does not mean risk-free

Users remain responsible for protecting source files, the SQLite Control Plane, DuckDB warehouse, backups/snapshots, local credentials, and the host operating system.

Do not assume a local database is encrypted merely because it is local.

## Disclosure

Please allow reasonable time to investigate and remediate a vulnerability before public disclosure.
