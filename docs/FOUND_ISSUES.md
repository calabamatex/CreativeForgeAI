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
