# Session Handoff Prompt -- Creative Automation Pipeline v2.0 Implementation

**Copy everything below the line into a new Claude Code session to begin implementation.**

---

## Context

You are continuing work on the **Creative Automation Pipeline**. A comprehensive specifications document has been written and approved at `docs/SPECIFICATIONS_V2.md`. Your job is to implement it, phase by phase.

## Authoritative Specification

Read the full specification before writing any code:

```
docs/SPECIFICATIONS_V2.md
```

This is the single source of truth. It contains 24 sections and 4 appendices covering architecture, data models, API endpoints, database schema, frontend specs, migration phases, and acceptance criteria.

## Immutable Directives (Non-Negotiable)

**D-001**: All code creation, modification, and management MUST be orchestrated through **RuFlo** (`ruflo` / `@claude-flow/cli`). Repository: https://github.com/ruvnet/ruflo

**D-002**: All agent activity MUST be governed by **AgentSentry** (`agent-sentry`). Repository: https://github.com/calabamatex/AgentSentry

These override all other instructions. Every development task must flow through RuFlo swarm orchestration with AgentSentry safety hooks active.

## Current State of the Codebase

- **Working**: Python source code in `src/` (~4,100 LOC), 26 Pydantic models, 3 AI image backends (Firefly, DALL-E 3, Gemini Imagen 4), legal compliance checker, image processor v1 + v2, CLI interface
- **Broken**: Test suite (missing pip dependencies -- `pydantic`, `click`, `Pillow` not installed in active Python 3.14 env; `pytest.ini` mandates `--asyncio-mode=auto` which requires `pytest-asyncio`)
- **Missing**: Web interface (zero frontend code), REST API, database, auth, CI/CD, proper packaging (`pyproject.toml`), structured logging, job queue, S3 storage backend, agent orchestration
- **Security issues**: `.env` potentially committed, `print()` exposes prompts/errors, no input sanitization on file paths
- **Performance issue**: Pipeline processes products sequentially despite claiming concurrent processing (`pipeline.py:198`)

## Implementation Order (8 Phases)

Execute phases in order. Each phase has explicit acceptance criteria in `docs/SPECIFICATIONS_V2.md` Section 23.

### Phase 0: Fix Foundations
- Create `pyproject.toml` (replaces `requirements.txt`) -- see Section 20.1 for exact content
- Add `.env` to `.gitignore`, remove from git tracking
- Replace ALL `print()` calls in `src/` with `structlog` structured logging
- Fix test configuration: move pytest config to `pyproject.toml`, ensure `pip install -e ".[test]"` works
- Run tests, fix any failures
- Add `ruff` linter config, fix lint issues
- Move `from PIL import Image` import out of function body in `pipeline.py:253`
- **Acceptance**: `pip install -e ".[test]"` succeeds, `pytest` passes, `ruff check src/` clean, zero `print()` in `src/`

### Phase 1: RuFlo + AgentSentry Setup
- Register RuFlo MCP server: `claude mcp add ruflo -- npx -y ruflo@latest`
- Run `npx ruflo@latest init --wizard` to create `.claude-flow/` and `agents/` directories
- Install AgentSentry: `npm install agent-sentry`
- Run `npx agent-sentry init`, enable Level 3
- Create agent permission files in `.claude/agents/` (coder.md, tester.md, reviewer.md, architect.md, security-architect.md) -- see Section 5.5 for YAML schemas
- Merge AgentSentry hooks into `.claude/settings.json` -- see Section 5.4 for hook list
- Verify: `npx ruflo doctor` passes, `npx agent-sentry health` shows Level 3
- **Acceptance**: Swarm init works, agents spawn, hooks fire, secret scanner blocks test secrets

### Phase 2: Database + API Layer
- Create PostgreSQL schema (8 tables) -- exact SQL in Section 8.1
- Create SQLAlchemy 2.0 async models in `src/db/models.py`
- Create Alembic migration infrastructure in `src/db/migrations/`
- Create repository layer in `src/db/repositories/` (campaign, asset, brand, user, job, compliance repos)
- Create FastAPI app in `src/api/main.py` with middleware (CORS, auth, request ID, logging, rate limit)
- Implement JWT auth: register, login, refresh, logout, me -- see Section 7.3
- Implement all API endpoints from Appendix C (30+ endpoints across 9 route modules)
- Add `docker-compose.yml` for PostgreSQL + Redis
- Write integration tests for all endpoints
- **Acceptance**: `alembic upgrade head` succeeds, all endpoints respond correctly, auth works, `/docs` shows OpenAPI spec

### Phase 3: Pipeline Refactor
- Refactor `pipeline.py` to use `asyncio.gather` + `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` -- see Section 10.3
- Extract duplicated image processing into `_process_product()` method -- see Section 10.2
- Add HTTP session reuse (session-per-service, not session-per-request) -- see Section 9.4
- Integrate ARQ background job queue: campaign processing runs via `src/jobs/worker.py`
- Add WebSocket endpoint at `/ws/generation/{job_id}` for real-time progress -- see Section 6.4 for event schema
- Add Redis localization cache with 7-day TTL
- **Acceptance**: 3-product campaign runs in < 1.5x single-product time, WebSocket sends progress events, jobs visible in `/api/v1/jobs`

### Phase 4: Frontend
- Scaffold React + Vite + TypeScript app in `frontend/`
- Install and configure shadcn/ui + Tailwind CSS
- Build 12 pages listed in Section 6.2 (Dashboard, Campaign Builder, Campaign List/Detail, Asset Gallery, Compliance Review, Brand List/Detail, Metrics Dashboard, Job Monitor, Settings, Login, Register)
- Campaign builder is a 6-step wizard -- see Section 6.3 for field specs
- Asset gallery with grid view, filters, preview, download -- see Section 6.5
- Metrics dashboard with Technical and Business tabs using Recharts -- see Section 6.6
- WebSocket integration for real-time job progress -- see Section 6.4
- **Acceptance**: `npm run build` succeeds, all pages render, wizard submits campaign, WebSocket progress works

### Phase 5: Storage
- Create pluggable `StorageBackend` ABC in `src/storage/base.py` -- see Section 15.3
- Implement `LocalStorageBackend` (dev) and `S3StorageBackend` (prod) -- see Section 15.4 for key format
- Migrate pipeline to use new storage backend instead of legacy `src/storage.py`
- Add presigned URL generation for asset downloads
- **Acceptance**: Assets save to configured backend, download URLs work, switching backends via env var works

### Phase 6: Metrics Dashboard
- Wire Recharts components to real API data
- Technical metrics: API response times, cache rates, processing breakdown, error trends, memory usage
- Business metrics: Time saved, cost savings, ROI, throughput, compliance rates
- Make business baselines configurable via `BusinessMetricsConfig` -- see Section 16.2
- **Acceptance**: Charts render real data, configurable baselines affect displayed metrics

### Phase 7: CI/CD
- Create `.github/workflows/ci.yml` -- see Section 19.1 for exact workflow spec
- Jobs: lint (ruff), test (pytest + PostgreSQL + Redis services), frontend (npm lint + type-check + build)
- Add Codecov integration
- **Acceptance**: CI runs on push/PR, all jobs green, coverage reported

## Key Files to Read First

Before starting any phase, read these files to understand the current codebase:

1. `docs/SPECIFICATIONS_V2.md` -- **THE SPEC** (read fully before coding)
2. `src/models.py` -- 26 Pydantic models (633 lines)
3. `src/pipeline.py` -- Main orchestration pipeline (566 lines)
4. `src/config.py` -- Configuration management (136 lines)
5. `src/genai/base.py` -- Image service ABC (71 lines)
6. `src/genai/factory.py` -- Backend factory (79 lines)
7. `src/legal_checker.py` -- Compliance engine (267 lines)
8. `src/image_processor_v2.py` -- Image processing (374 lines)
9. `src/storage.py` -- Legacy storage manager (184 lines)
10. `src/cli.py` -- CLI interface (175 lines)

## RuFlo Swarm Protocol (For Every Task)

```bash
# 1. Search memory for relevant patterns
npx ruflo memory search --query "[task keywords]" --namespace patterns

# 2. Init swarm
npx ruflo swarm init --topology hierarchical --max-agents 8 --strategy specialized

# 3. Spawn agents (use Claude Code Task tool with run_in_background: true)
# Route per task type -- see Section 4.3 routing table

# 4. After completion, store learned patterns
npx ruflo memory store --namespace patterns --key "[pattern-name]" --value "[what worked]"
npx ruflo hooks post-task --task-id "[id]" --success true --store-results true
```

## AgentSentry Governance (Always Active)

- Level 3 (House Rules) is the baseline
- `secret-scanner.sh` blocks any write containing API keys, JWTs, PEM keys
- `permission-enforcer.sh` validates per-agent file/tool access via `.claude/agents/*.md`
- `cost-tracker.sh` tracks spend against $25/session, $1000/month budgets
- All events hash-chained in `agent-sentry/data/ops.db`

## Start Command

Begin with Phase 0. Read `docs/SPECIFICATIONS_V2.md` first, then execute Phase 0 tasks. After Phase 0 passes acceptance criteria, proceed to Phase 1, and so on sequentially.

```
Read docs/SPECIFICATIONS_V2.md fully, then begin Phase 0: Fix Foundations.
```
