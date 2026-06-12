# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Report privately via [GitHub Security Advisories](https://github.com/calabamatex/CreativeForgeAI/security/advisories/new)
("Report a vulnerability"). Include:

- A description of the issue and its impact
- Steps to reproduce (a curl transcript or failing test is ideal)
- Affected endpoints/files if known

You can expect an acknowledgement within 5 business days. Please allow a
reasonable remediation window before any public disclosure.

## Scope

- The FastAPI backend (`src/`), background worker (`src/jobs/`), and React
  frontend (`frontend/`)
- Authentication, authorization (tenant scoping), rate limiting, file
  storage/path handling

Out of scope: vulnerabilities exclusively in third-party dependencies
(report upstream, though a heads-up is appreciated), and issues requiring
physical access or a compromised host.

## Trust model (summary)

Every campaign and brand guideline is owned by its creator (`created_by`).
Assets, jobs, compliance reports, and metrics inherit ownership from their
parent campaign. Non-admin users may only access objects they own; cross-tenant
access must return 404. Admin access to others' objects is deliberate and
logged. The model is enforced centrally in `src/api/authz.py` and encoded in
`tests/integration/test_api_authz.py` — any change weakening either is a
security regression.

## Security controls in CI

Every PR runs: CodeQL (Python + JS/TS), `bandit`, `pip-audit`, `npm audit`
(high+ on production deps), `gitleaks` secret scanning, and the cross-tenant
authorization regression suite with a coverage gate.
