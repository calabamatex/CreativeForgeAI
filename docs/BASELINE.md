# Baseline (P0-T1)

This document records, with captured command output, which entry points of the
GenAI Creative Automation Platform actually work today on this machine and which
fail — and the exact failure modes. It is the verified floor the remediation plan
builds on. **No source logic was changed to produce this baseline.**

Environment captured:

- Python in venv: **3.14.2** (the README/QUICKSTART claim "Python 3.11+"; the docs
  also reference Docker base `python:3.12-slim`).
- venv path: `/Users/ethanallen/CreativeForgeAI/venv` (activate before every command).
- No `.env` file present. No API keys set.

---

## a. Install dependencies — PARTIAL / DOCS WRONG

**Working install path:** `pip install -e ".[test]"` (from `pyproject.toml`) — this
is what populated the venv and is the only path that installs the full API/DB/worker
stack. Verified the stack is importable:

```
$ python --version
Python 3.14.2

$ python -c "import fastapi, sqlalchemy, asyncpg, redis, jose, arq; \
  print('fastapi', fastapi.__version__); print('sqlalchemy', sqlalchemy.__version__); print('jose OK')"
fastapi 0.136.3
sqlalchemy 2.0.50
jose OK
```

**The README/QUICKSTART instruction `pip install -r requirements.txt` does NOT install
the API/DB/worker stack.** `requirements.txt` contains only the CLI/runtime libs
(pydantic, click, Pillow, aiohttp, PyMuPDF, structlog, etc.). It has zero of the
server dependencies that `pyproject.toml` lists (fastapi, uvicorn, sqlalchemy,
asyncpg, alembic, arq, redis, python-jose, passlib, boto3, aioboto3, httpx, ...):

```
$ grep -ic fastapi requirements.txt
0
```

**Result:** Following the documented `pip install -r requirements.txt` would let the
CLI run but leave the API completely uninstallable. Correct path is the editable
`pyproject.toml` install.

---

## b. `python -m src.cli validate-config` — FAIL (expected, no keys)

The command runs and exits cleanly with a clear validation error (no traceback). It
correctly reports that no image backend is configured.

```
$ python -m src.cli validate-config

🔍 Validating configuration...
[warning] config.validation_warning  warning='CLAUDE_API_KEY not set - guideline extraction and localization will use fallback methods'
❌ Configuration errors:
  - At least one image generation backend must be configured: Firefly (FIREFLY_API_KEY + FIREFLY_CLIENT_ID), OpenAI (OPENAI_API_KEY), or Gemini (GEMINI_API_KEY)
Aborted!
EXIT=1
```

**Failure mode:** No API keys / no `.env`, so validation fails by design. The CLI
entry point itself imports and runs correctly.

---

## c. Example CLI campaign — `process` — PASS (dry-run) / FAIL (real, no keys)

`process --help` works and documents a `--dry-run` flag.

**Dry-run (validation only) — PASS:**

```
$ python -m src.cli process --brief examples/campaign_brief.json --dry-run

📄 Loading campaign brief from examples/campaign_brief.json...

✓ Dry run complete - brief is valid
DRYRUN_EXIT=0
```

**Real run (no API keys) — FAIL, fails fast before any paid API call.** The brief
validates, then construction of `CreativeAutomationPipeline` raises in
`ClaudeService.__init__` because `CLAUDE_API_KEY` is unset. No image/LLM network
call is ever attempted.

```
$ python -m src.cli process --brief examples/campaign_brief.json --verbose

📄 Loading campaign brief from examples/campaign_brief.json...
✓ Brief validated successfully
  Campaign: Summer Tech Collection 2026
  Products: 2
  Locales: en-US, es-MX, fr-CA
❌ Error: CLAUDE_API_KEY is required. Set it in environment variables or pass to constructor.
Traceback (most recent call last):
  File ".../src/cli.py", line 53, in process
    pipeline = CreativeAutomationPipeline(image_backend=backend)
  File ".../src/pipeline.py", line 63, in __init__
    self.claude_service = ClaudeService()
  File ".../src/genai/claude.py", line 22, in __init__
    raise ValueError(
        "CLAUDE_API_KEY is required. Set it in environment variables or pass to constructor."
    )
ValueError: CLAUDE_API_KEY is required. ...
Aborted!
```

**Failure mode:** Missing `CLAUDE_API_KEY`. Pipeline construction hard-requires Claude
even for backends that don't need it; it fails fast (no cost incurred). No keys were
set to force this through.

---

## d. Start the API — `uvicorn src.api.main:app` — FAIL

**d1. Import with NO `SECRET_KEY` — FAIL at import time.** `import src.api.main`
raises `RuntimeError` from `src/api/dependencies.py:34` (imported transitively via the
auth router):

```
$ python -c "import src.api.main"
  File ".../src/api/main.py", line 115, in create_app
    from src.api.routes.auth import router as auth_router
  File ".../src/api/routes/auth.py", line 13, in <module>
    from src.api.dependencies import (...)
  File ".../src/api/dependencies.py", line 34, in <module>
    raise RuntimeError(...)
RuntimeError: SECRET_KEY environment variable must be set and at least 32 characters. Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**d2. Import WITH a throwaway `SECRET_KEY` — import succeeds, startup FAILS on DB.**
Setting `SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(64))")`
lets the module import cleanly:

```
$ SECRET_KEY=<64-char-token> python -c "import src.api.main; print('IMPORT OK - app object:', type(src.api.main.app).__name__)"
IMPORT OK - app object: FastAPI
```

But starting uvicorn fails during the lifespan startup (`init_db`). The app tries the
hardcoded default DB URL
`postgresql+asyncpg://postgres:postgres@localhost:5432/adobe_genai`
(from `src/db/base.py:20`). Notably, Postgres on `:5432` IS reachable — startup fails
on **password authentication**, not connection refused:

```
$ SECRET_KEY=<token> uvicorn src.api.main:app --port 8000
INFO:     Started server process
INFO:     Waiting for application startup.
[info] api.startup
[info] db.init  url=postgresql+asyncpg://postgres:postgres@localhost:5432/adobe_genai
ERROR:    Traceback (most recent call last):
  ...
  File ".../asyncpg/connect_utils.py", line 1102, in __connect_addr
    await connected
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"

ERROR:    Application startup failed. Exiting.
```

**Failure modes (two, sequential):**
1. Missing `SECRET_KEY` → import-time `RuntimeError`.
2. With `SECRET_KEY` set → startup fails connecting to Postgres. There is no `.env`,
   so the hardcoded default URL `postgres:postgres@.../adobe_genai` is used; a Postgres
   is listening on `:5432` but rejects those credentials (`InvalidPasswordError`). Note
   this differs from the plan's assumption of "no Postgres configured" — a Postgres is
   present, just with non-matching creds.

---

## e. Hit `/health` — FAIL (API never came up)

Because startup aborted in (d), the server never bound a listener:

```
$ curl -s -m 5 localhost:8000/health
CURL_EXIT=7
```

**Failure mode:** `curl` exit 7 = "Failed to connect" — uvicorn exited during
application startup, so `/health` was never reachable. (The `/health` route itself is
defined in `src/api/main.py` and is trivial; it is unreachable only because lifespan
startup fails first.)

---

## Infra baseline (observed, NOT fixed)

- **Docker daemon: UP.** `docker info` reports server version `29.1.3`.
- **`docker compose config`: FAILS** — pre-existing bug in `docker-compose.yml`:

  ```
  $ docker compose config
  healthcheck.test must start either by "CMD", "CMD-SHELL" or "NONE"
  ```

  Root cause: the `postgres` service healthcheck uses `["CMD-EXEC", ...]`
  (`docker-compose.yml:23`) — `CMD-EXEC` is not a valid form; it should be
  `CMD-SHELL`. Because compose config fails, `docker compose up` cannot bring up the
  Postgres/Redis/MinIO stack. (Left unfixed; a later task handles it.)
- **No `.env` file** exists in the repo root (`ls .env` → No such file or directory).

---

## Summary table

| Check | Result | One-line failure mode |
|-------|--------|------------------------|
| a. Install deps | PARTIAL | `pip install -r requirements.txt` omits the entire API/DB/worker stack; only `pip install -e ".[test]"` works. |
| b. `validate-config` | FAIL (expected) | No image backend / no keys configured. |
| c. CLI `process` | PASS (dry-run) / FAIL (real) | Real run fails fast: `CLAUDE_API_KEY` required at pipeline init; no paid call made. |
| d. Start API | FAIL | No `SECRET_KEY` → import `RuntimeError`; with it → Postgres `InvalidPasswordError` on startup. |
| e. `/health` | FAIL | curl exit 7 (connect failed) — API never started. |

**Infra:** Docker daemon UP; `docker compose config` FAILS (`CMD-EXEC` typo in postgres
healthcheck); no `.env`.

---

## Dev environment (P0-T5)

The local Docker Compose stack (Postgres + Redis + MinIO) was brought up healthy
and verified reachable from the app. Changes made to get here:

- Fixed the invalid postgres healthcheck `CMD-EXEC` → `CMD-SHELL` so
  `docker compose config` passes (`docker-compose.yml:23`). Redis/MinIO
  healthchecks were already valid.
- Host ports remapped to avoid a collision with another local stack already
  bound to :5432/:6379/:9000-9001 (the `affiliatemarketingplatform` project —
  see `docs/FOUND_ISSUES.md`): **postgres 5432→5434, redis 6379→6380,
  minio 9000→9002 / 9001→9003**. Containers still listen on their default
  ports internally.
- Added a one-shot `minio-init` service that creates the `genai-assets` bucket.
- Reconciled the hardcoded `DATABASE_URL` default in `src/db/base.py` and the
  `.env.example` infra creds to the real Compose values (remapped ports).

### `docker compose ps`

```
NAME             IMAGE                COMMAND                  SERVICE    STATUS                    PORTS
genai-minio      minio/minio:latest   "/usr/bin/docker-ent…"   minio      Up (healthy)   0.0.0.0:9002->9000/tcp, 0.0.0.0:9003->9001/tcp
genai-postgres   postgres:16          "docker-entrypoint.s…"   postgres   Up (healthy)   0.0.0.0:5434->5432/tcp
genai-redis      redis:7-alpine       "docker-entrypoint.s…"   redis      Up (healthy)   0.0.0.0:6380->6379/tcp
```

(`genai-minio-init` runs once to create the bucket, then exits 0.)

### Connectivity checks (with the documented `.env` loaded)

**Postgres** — `alembic upgrade head`:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 53a16420a6ea, baseline schema
exit=0
```

**Redis** — `r.from_url(REDIS_URL).ping()`:

```
redis ok
```

**MinIO / S3** — repo storage backend (`STORAGE_BACKEND=s3`,
`get_default_storage_backend()`), save + list round-trip against bucket
`genai-assets`:

```
storage.s3.init  bucket=genai-assets endpoint_url=http://localhost:9002 region=us-east-1
storage.s3.saved bucket=genai-assets key=campaigns/_p0t5_healthcheck.txt size=2
list_keys(campaigns/) -> ['campaigns/_p0t5_healthcheck.txt']
minio/s3 ok
```

The stack is left **UP** as the dev environment for later phases.
