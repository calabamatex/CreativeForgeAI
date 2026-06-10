# Architecture Notes

## Asset storage: the pluggable `StorageBackend` (P3-T3)

### Dual-storage resolution — Option (a)

There were historically two storage systems doing overlapping asset work:

* the legacy **`StorageManager`** (`src/storage.py`), which wrote asset PNGs to
  local disk; and
* the pluggable **`StorageBackend`** abstraction (`src/storage_factory.py`,
  `storage_local.py`, `storage_s3.py`, `storage_backend.py` with
  `build_asset_key`).

This produced a redundant double-write: the pipeline wrote each asset to disk via
`StorageManager`, then the worker read those bytes back from `file_path` and
re-saved them through the backend.

**Decision: Option (a).** The `StorageBackend` owns ALL final asset bytes.
`StorageManager` is reduced to **report/brief JSON only** (plus the intermediate
hero-image cache). The boundary is documented in the `StorageManager` module
docstring (`src/storage.py`).

| Concern | Owner |
| --- | --- |
| Final per-variant campaign **asset** bytes (PNG/JPG) | `StorageBackend` (local or S3), written once by the worker |
| Per-product campaign **report** JSON | `StorageManager` (local disk) |
| Campaign **brief** backup / update | `StorageManager` (local disk) |
| Intermediate **hero** images (reused within a run) | `StorageManager` (local disk) |

Hero images are an intermediate cache, not a deliverable asset; they stay on
local disk so a re-run can reuse them. They are never served via
`/assets/{id}/download`.

### Exactly one asset-bytes write path

The redundant disk-write → reread is gone:

1. `CreativeAutomationPipeline._generate_asset_for_ratio`
   (`src/pipeline.py`) produces each final asset as **in-memory bytes** and does
   NOT write it to disk. It computes the canonical key with `build_asset_key(...)`
   and carries the bytes + key on `GeneratedAsset.metadata`
   (`image_bytes`, `storage_key`, `fmt`). `file_path` mirrors the canonical key
   for display/logging.
2. The worker `_persist_assets` (`src/jobs/tasks.py`) performs the **single**
   `backend.save(key, data, content_type)` call per asset (in-memory bytes; a
   disk read is only a fallback for callers that materialise the asset first,
   e.g. the generation-only integration fake or a reused on-disk asset). The key
   passed to `backend.save` is the key written to `GeneratedAsset.storage_key`,
   so **the DB key always equals the key the backend stored under**.

The single save lives in the **worker** (not the pipeline) because the worker
already owns the DB session and the `storage_key → DB` consistency, and runs the
pipeline in-process so the in-memory byte handoff is free.

### Downloads resolve through the backend

`GET /assets/{id}/download` (`src/api/routes/assets.py`) uses
`asset.storage_key` as the single source of truth and branches on the configured
backend:

* **`STORAGE_BACKEND=local`** → resolve the key through
  `LocalStorageBackend._resolve_path` (honoring P1-T3 `is_relative_to`
  containment) and stream the file via `FileResponse` (HTTP 200).
* **`STORAGE_BACKEND=s3`** (MinIO acceptable) → generate a presigned URL via
  `S3StorageBackend.get_url` and return an HTTP **307** redirect to it. Fetching
  that URL returns the same bytes.

### Verification

`tests/integration/test_api_assets.py::TestBackendDownload` covers both real
backends end-to-end (worker saves once → download → bytes match):

* `test_local_backend_streams_file_response` — real `LocalStorageBackend` over a
  tmp dir; download returns 200 with the exact PNG bytes.
* `test_s3_backend_redirects_to_working_presigned_url` — real `S3StorageBackend`
  against the Compose MinIO (`genai-assets`); download returns 307 and the
  presigned URL, when fetched, returns the same bytes (`integration` tier, no
  paid spend).
