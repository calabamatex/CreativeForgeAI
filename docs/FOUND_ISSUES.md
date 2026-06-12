# Found Issues

Out-of-scope or incidental issues discovered while executing the Phase 0 plan.
Keep entries short: title + 1-2 lines + file reference.

## P0-T5

### Compose postgres healthcheck used invalid `CMD-EXEC` form — FIXED
The `postgres` healthcheck was `["CMD-EXEC", ...]`, which is not a valid Compose
healthcheck form (`docker compose config` errored: must start with `CMD`,
`CMD-SHELL` or `NONE`). Fixed to `CMD-SHELL` here as part of standing up the dev
env. `docker-compose.yml:23`.

### Host :5432 / :6379 / :9000-9001 collision with another project — RESOLVED via port remap
A separate, unrelated stack (`affiliatemarketingplatform`, at
`/Users/ethanallen/Documents/Affiliate Marketing Platform`) was already running
and bound to host :5432 (postgres), :6379 (redis), and :9000-9001 (minio). This
is why a prior run saw `asyncpg InvalidPasswordError for user "postgres"` — it
was hitting the *other* project's Postgres. Those containers belong to an active
project, so they were left running. Instead this project's Compose host ports
were remapped: postgres 5432→5434, redis 6379→6380, minio 9000→9002 / 9001→9003.
`.env.example`, `src/db/base.py`, and `docker-compose.yml` updated to match.

### MinIO/S3 backend requires `AWS_*` credentials, not the documented `S3_*` ones — NOTED
`src/storage_s3.py` reads `S3_BUCKET` / `S3_REGION` / `S3_ENDPOINT_URL` directly
but authenticates via the standard boto3 credential chain, so it actually needs
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — the `S3_ACCESS_KEY_ID` /
`S3_SECRET_ACCESS_KEY` vars in `.env.example` are not consumed by the code.
Worked around in `.env.example` by setting both the `S3_*` (documentation) and
`AWS_*` (actually used) variables. A future cleanup could make the backend read
the `S3_*` names explicitly. `src/storage_s3.py:35-57`.

## P1 (discovered during Phase 1)

### `test_cli.py::test_validate_config_command` fails in the FULL suite, passes in isolation — FIXED in P6-T1
**FIXED (P6-T1):** Root cause was process-global config state leaking across
tests — `validate-config` reads the module-level `Config` singleton
(`src/config.py`), and other tests mutate `os.environ` / reset `config._config`,
so it failed out of order. Fixed with an autouse fixture
`_isolate_env_and_config` in `tests/conftest.py` that, around EVERY test:
(1) snapshots `os.environ`, (2) applies a deterministic baseline of fake test API
keys + backend so config-dependent tests are order-independent (they previously
relied on leaked keys), (3) resets the `src.config` singleton to rebuild fresh,
and (4) at teardown restores the exact original env and drops the singleton.
`test_validate_config_command` now PASSES in the full suite repeatedly (full suite
2x: 523 passed / 1 skipped / 0 failed each). `tests/conftest.py`,
`tests/test_cli.py::TestCLI::test_validate_config_command`.

Originally: Confirmed pre-existing (failed identically on `phase-0-baseline`,
before any Phase 1 change). The test passed alone but exited 1 in a full `pytest`
run — a test-isolation/ordering bug. Not a Phase 1 regression; deferred to the P6
test-taxonomy/conftest work.

### Residual `Adobe` branding + unsubstantiated "patent-pending" claim in README — NOTED
After the P1-T4 honesty pass, `README.md` still carries legacy `Adobe` /
`adobe-genai-project` branding, a "patent-pending" claim near the footer, and a
back-to-top anchor pointing at an old `#adobe-genai...` slug. Out of scope for the
P1-T4 feature-claim reconciliation; flag for a later branding/legal pass.

## P3 (discovered during Phase 3)

### tz-aware datetimes written into `TIMESTAMP WITHOUT TIME ZONE` columns — FIXED in P3-T0b
The repos/worker write tz-aware datetimes (`datetime.now(timezone.utc)`) into
`jobs.started_at` / `jobs.completed_at` (and similar `created_at`/`updated_at`/
`checked_at`/`recorded_at` via `onupdate`), but `src/db/models.py` mapped them as
`TIMESTAMP WITHOUT TIME ZONE`, so real Postgres raised `DBAPIError` and
`process_campaign_job` could not reach a terminal state (mocks hid it). Fixed by
making all 13 datetime columns `DateTime(timezone=True)` + Alembic migration
`da96efc5089e`. `src/db/models.py`,
`src/db/migrations/versions/da96efc5089e_tz_aware_timestamp_columns.py`.

### passlib 1.7.4 + bcrypt 5.0.0 incompatible — auth register/login broken — FIXED in P4-T0
**FIXED (P4-T0):** Replaced passlib with the `bcrypt` library directly in `src/api/dependencies.py` (`hash_password`/`verify_password`, cost 12); passwords are SHA-256+base64 pre-hashed before bcrypt to sidestep the 72-byte limit without truncating; `verify_password` returns `False` on malformed hashes. Dropped `passlib[bcrypt]` from `pyproject.toml` (now `bcrypt>=4.1.0`) and uninstalled passlib from the venv. Stored hashes remain standard `$2b$`; auth tests + full integration suite green.


`passlib[bcrypt]>=1.7.4` resolved passlib 1.7.4 with bcrypt 5.0.0, which removed the
`__about__` attribute passlib reads and trips passlib's backend 72-byte self-test
(`ValueError: password cannot be longer than 72 bytes`). Result: `hash_password` /
`/auth/register` / `/auth/login` raise 500 in this environment. Pre-existing
dependency-compat bug (not P3 scope). The P3-T0 e2e test works around it by seeding
the user row + minting a JWT via `create_access_token`. Real fix (pin a compatible
bcrypt, or switch to the bcrypt lib directly) belongs to P4-T1 (auth hardening).
`src/api/dependencies.py` (`hash_password`), `pyproject.toml`.

### e2e tripwire XPASSes after P3-T1 alone (not at "step 5") — RESOLVED in P3-T2
`tests/integration/test_e2e_campaign.py::test_e2e_campaign_enqueue_persist_retrieve`
was a `@pytest.mark.xfail(strict=True)` tripwire. The P3-T1 brief expected it to
"advance past step 3 (enqueue) but still XFAIL at step 5 (no assets persisted —
P3-T2)". In practice the test did NOT depend on P3-T2 production code: it injected
its OWN persisting `process_campaign` (`_make_persisting_process_campaign`) into
`fake_arq_pool.drive(...)`, so once enqueue was wired (T1) the whole chain passed
and `strict=True` turned that XPASS into a FAILURE (the tripwire firing).

**Resolved in P3-T2.** The circular test-supplied persistence hook is gone. The
test now injects only a *generation-only* fake `process_campaign` (the seam the
harness already fakes: image-gen returns the mocked tiny PNG, written to a real
`file_path` on disk) and the REAL worker — `process_campaign_job` →
`_persist_assets` → `AssetRepository.upsert` (`ON CONFLICT uq_asset_variant DO
UPDATE`) — does the DB persistence + `storage_key` population. The test therefore
now guards PRODUCTION persistence code, so the `strict-xfail` marker has been
REMOVED. `pytest tests/integration -q` is fully green (115 passed, 0 failed, 0
xpass-failures). Files: `tests/integration/test_e2e_campaign.py` (marker removed;
`_make_generating_process_campaign`), `src/jobs/tasks.py` (`_persist_assets`),
`src/db/repositories/asset_repo.py` (`upsert`).

### dual-storage overlap (StorageManager vs StorageBackend) — RESOLVED in P3-T3
The redundant double-write is gone. Resolution: **option (a)** — `StorageBackend`
owns ALL final asset bytes; `StorageManager` is reduced to **report/brief JSON
only** (plus the intermediate hero-image cache). The boundary is documented in
the `StorageManager` module docstring (`src/storage.py`) and in
`docs/ARCHITECTURE.md`.

Single asset-bytes write path: `CreativeAutomationPipeline._generate_asset_for_ratio`
(`src/pipeline.py`) now produces each asset as in-memory bytes (no disk write) and
carries them + the canonical `build_asset_key` on `GeneratedAsset.metadata`; the
worker `_persist_assets` (`src/jobs/tasks.py`) performs the ONE
`backend.save(key, data, content_type)` per asset, and the key it saves under is
exactly the key written to `GeneratedAsset.storage_key` (consistency guaranteed).
The old disk-write → reread round trip is eliminated (a disk read remains only as
a fallback for callers that materialise the asset first, e.g. the generation-only
integration fake).

Downloads resolve through the backend (`src/api/routes/assets.py`): `local` →
`FileResponse` (200) via `LocalStorageBackend._resolve_path` honoring P1-T3
containment; `s3`/MinIO → 307 redirect to a presigned URL that fetches the same
bytes. Verified end-to-end against BOTH real backends in
`tests/integration/test_api_assets.py::TestBackendDownload`
(local 200 bytes-match + S3/MinIO 307 presigned bytes-match). `pytest
tests/integration -q` → 117 passed. Files: `src/pipeline.py`, `src/storage.py`,
`src/jobs/tasks.py`, `src/api/routes/assets.py`,
`tests/integration/test_api_assets.py`, `docs/ARCHITECTURE.md`.

Deferred (expected under option (a)): report & brief JSON are still written by
`StorageManager` to local disk — that is by design (reports/briefs, NOT assets),
and the intermediate hero-image cache likewise stays local.

### WebSocket `/ws/generation/{job_id}` has no authentication — FIXED in P4-T1
**FIXED (P4-T1):** `src/api/routes/ws.py` now authenticates the handshake. The
access token is accepted via the `?token=` query param (browsers can't set
`Authorization` on a WS) or the `access_token` httpOnly cookie, and validated with
the SAME decode + revocation-denylist + active-user checks as HTTP
(`resolve_access_token_user`). Unauthenticated/invalid/revoked tokens are closed
with **4401** before any progress is streamed. After auth, the connection is
authorized against ownership: a job's owner is its parent campaign's `created_by`;
a non-owner (and non-admin) is closed with **4403**. Admins may stream any job.
Covered by `tests/integration/test_api_ws.py` (missing/invalid/revoked token,
owner streams, non-owner 4403, admin override).

### P3-T4 WebSocket test is timing-flaky — FIXED in P6-T1
**FIXED (P6-T1):** Made
`tests/integration/test_api_ws.py::test_ws_streams_real_progress_then_closes_on_terminal`
deterministic. The old version mutated the job row on a fixed `asyncio.sleep(0.6)`
cadence in a background task, RACING the server's 0.5s poll loop, so a transition
occasionally landed between two polls and a frame was missed/merged. The endpoint
now reads its poll interval at connection time from `WS_POLL_INTERVAL_SECONDS`
(`src/api/routes/ws.py`, `_poll_interval_seconds()`); the test sets it to ~10ms and
drives each state transition IN LOCKSTEP with the received frames (read the next
CHANGED frame → apply the next transition → repeat). Because the endpoint emits
only on a changed `(progress, stage, status)` signature, advancing strictly after
observing the prior frame guarantees every distinct state is seen once, in order —
no wall-clock race. Asserts unchanged (real progress fields + monotonic + terminal
`completed` at 100 + socket close). Stable 10/10 in a repeat loop.
`tests/integration/test_api_ws.py`, `src/api/routes/ws.py`.
