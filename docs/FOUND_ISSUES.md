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

### `test_cli.py::test_validate_config_command` fails in the FULL suite, passes in isolation — PRE-EXISTING, deferred to P6
Confirmed pre-existing (fails identically on `phase-0-baseline`, before any Phase 1
change). The test passes when run alone but exits 1 in a full `pytest` run — a
test-isolation/ordering bug: `validate-config` reads a module-level `Config`
singleton (`src/config.py`) and another test pollutes `os.environ` / the singleton,
so the image-backend check fails out of order. Not a Phase 1 regression. Belongs to
the P6 test-taxonomy/conftest work (isolate config state per test).
`tests/test_cli.py::TestCLI::test_validate_config_command`.

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

### passlib 1.7.4 + bcrypt 5.0.0 incompatible — auth register/login broken — DEFERRED to P4
`passlib[bcrypt]>=1.7.4` resolved passlib 1.7.4 with bcrypt 5.0.0, which removed the
`__about__` attribute passlib reads and trips passlib's backend 72-byte self-test
(`ValueError: password cannot be longer than 72 bytes`). Result: `hash_password` /
`/auth/register` / `/auth/login` raise 500 in this environment. Pre-existing
dependency-compat bug (not P3 scope). The P3-T0 e2e test works around it by seeding
the user row + minting a JWT via `create_access_token`. Real fix (pin a compatible
bcrypt, or switch to the bcrypt lib directly) belongs to P4-T1 (auth hardening).
`src/api/dependencies.py` (`hash_password`), `pyproject.toml`.

### e2e tripwire XPASSes after P3-T1 alone (not at "step 5") — marker removal owed to P3-T3
`tests/integration/test_e2e_campaign.py::test_e2e_campaign_enqueue_persist_retrieve`
is a `@pytest.mark.xfail(strict=True)` tripwire. The P3-T1 brief expected it to
"advance past step 3 (enqueue) but still XFAIL at step 5 (no assets persisted —
P3-T2)". In practice the test does NOT depend on P3-T2 production code: it injects
its OWN persisting `process_campaign` (`_make_persisting_process_campaign`) into
`fake_arq_pool.drive(...)`, so once enqueue is wired (T1) the whole create ->
enqueue -> drive -> persist -> retrieve -> reprocess-dedupe chain passes. With
`strict=True`, that XPASS becomes a FAILURE — the tripwire firing exactly as its
docstring describes ("XPASSes -> strict failure -> marker removed in P3-T3").
Proof the underlying behaviour moved: under `--runxfail`, pre-T1 it fails at step 3
(`live ids []`, create route never enqueues); post-T1 it passes fully. Per the T1
brief, the marker is NOT removed here — removing it is P3-T3's job. Until then
`pytest tests/integration` reports this one expected strict-XPASS failure
(113 passed, 1 "failed" = the tripwire). `tests/integration/test_e2e_campaign.py`
(xfail marker, line ~204).
