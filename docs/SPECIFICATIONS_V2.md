# Creative Automation Pipeline -- Specifications v2.0

**Document Status**: AUTHORITATIVE
**Version**: 2.0.0
**Date**: 2026-03-25
**Classification**: Internal -- Engineering Reference
**Supersedes**: All prior specification documents

> **Note (post-cleanup):** This spec describes a `BusinessMetrics` data model with `manual_baseline_hours`, `manual_baseline_cost`, `roi_multiplier`, and similar tautology fields derived from hard-coded constants. That model has been **removed** from the implementation because the calculations were not measurements. The spec sections that describe it (Section 11.3 / business-metrics field definitions) are kept here for design-discussion reference but no longer correspond to running code. See the README "Status and scope" section for what is actually measured.

---

## Table of Contents

1. [Immutable Directives](#1-immutable-directives)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Agent Orchestration (RuFlo)](#4-agent-orchestration-ruflo)
5. [Agent Safety & Governance (AgentSentry)](#5-agent-safety--governance-agentsentry)
6. [Web Interface](#6-web-interface)
7. [API Layer](#7-api-layer)
8. [Database Layer](#8-database-layer)
9. [Image Generation Services](#9-image-generation-services)
10. [Pipeline Engine](#10-pipeline-engine)
11. [Legal Compliance Engine](#11-legal-compliance-engine)
12. [Localization System](#12-localization-system)
13. [Brand Guidelines System](#13-brand-guidelines-system)
14. [Image Processing System](#14-image-processing-system)
15. [Storage & Asset Management](#15-storage--asset-management)
16. [Metrics & Reporting](#16-metrics--reporting)
17. [Security](#17-security)
18. [Testing Strategy](#18-testing-strategy)
19. [CI/CD Pipeline](#19-cicd-pipeline)
20. [Configuration Management](#20-configuration-management)
21. [Error Handling & Logging](#21-error-handling--logging)
22. [Deployment](#22-deployment)
23. [Migration Plan](#23-migration-plan)
24. [Acceptance Criteria](#24-acceptance-criteria)
25. [Appendix A: File Tree](#appendix-a-target-file-tree)
26. [Appendix B: Data Models](#appendix-b-data-models)
27. [Appendix C: API Endpoints](#appendix-c-api-endpoints)
28. [Appendix D: Gap Register](#appendix-d-gap-register)

---

## 1. Immutable Directives

These directives are fixed constraints. They override any conflicting specification in this document.

| ID | Directive | Authority |
|----|-----------|-----------|
| **D-001** | All code creation, modification, and management MUST be orchestrated through **RuFlo** (`ruflo` / `@claude-flow/cli`). Source: [github.com/ruvnet/ruflo](https://github.com/ruvnet/ruflo). No agent-driven code change may bypass RuFlo orchestration. | Project Owner |
| **D-002** | All agent activity MUST be governed by **AgentSentry** (`agent-sentry`). Source: [github.com/calabamatex/AgentSentry](https://github.com/calabamatex/AgentSentry). Every agent session must have AgentSentry hooks active, every write operation must pass secret scanning, and every session must produce a hash-chained audit trail. | Project Owner |

### 1.1 Directive Implications

**D-001 (RuFlo)**: Every development task -- feature implementation, bug fix, refactoring, test writing, documentation update -- is decomposed into a RuFlo swarm with typed agents (coder, tester, reviewer, architect, etc.). Direct manual coding is permitted only when explicitly authorized outside the agent workflow.

**D-002 (AgentSentry)**: AgentSentry operates as the safety and governance layer that wraps all RuFlo agent activity. Specifically:
- AgentSentry's `secret-scanner.sh` hook fires on every Write/Edit/MultiEdit tool use
- AgentSentry's `permission-enforcer.sh` validates agent file/tool permissions before execution
- AgentSentry's `delegation-validator.sh` validates agent-to-agent task handoffs
- AgentSentry's hash-chained event store records all decisions, violations, and incidents
- AgentSentry's `context-estimator.sh` monitors token usage per agent session
- AgentSentry's `cost-tracker.sh` tracks API spend against budget limits

---

## 2. System Overview

### 2.1 Purpose

Automate the creation of localized, brand-compliant marketing assets at scale using generative AI, with a web-based interface for campaign management, asset preview, compliance review, and metrics dashboards.

### 2.2 Current State Summary

| Dimension | Current State | Target State |
|-----------|--------------|--------------|
| Interface | CLI only (`src/cli.py`, Click) | Web UI (React) + REST API (FastAPI) + CLI |
| Processing | Sequential product loop | Concurrent with `asyncio.gather` + semaphore |
| Storage | Flat JSON files on local filesystem | PostgreSQL + S3-compatible object storage |
| Testing | 12 test files, broken (missing deps) | Passing suite, 80%+ coverage, CI-gated |
| CI/CD | None | GitHub Actions: lint, test, build, deploy |
| Logging | `print()` with emoji prefixes | Structured JSON logging (`structlog`) |
| Auth | None | JWT-based auth with RBAC |
| Secrets | Plaintext `.env` (committed) | Secrets manager / `.env` in `.gitignore` |
| Monitoring | None | AgentSentry dashboard + application metrics |
| Agent Orchestration | None | RuFlo swarm with AgentSentry governance |
| Packaging | `requirements.txt` only | `pyproject.toml` with locked deps |

### 2.3 Technology Stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| Language | Python | 3.11+ | Existing codebase; Pydantic v2 compatibility |
| API Framework | FastAPI | 0.115+ | Async-native, OpenAPI auto-generation, WebSocket support |
| Frontend | React + TypeScript | React 18+, TS 5+ | Component reuse, strong typing, ecosystem |
| Frontend Build | Vite | 5+ | Fast dev server, optimized builds |
| UI Library | shadcn/ui + Tailwind CSS | Latest | Accessible components, utility-first styling |
| Database | PostgreSQL | 16+ | JSONB for flexible schemas, full-text search |
| ORM | SQLAlchemy 2.0 | 2.0+ | Async support, Alembic migrations |
| Object Storage | S3-compatible (MinIO local, S3 prod) | - | Asset delivery, CDN-ready |
| Task Queue | ARQ (async Redis queue) | 0.26+ | Python-native async job processing |
| Cache | Redis | 7+ | Session store, task queue backend, response cache |
| Image Processing | Pillow | 10.3+ | Existing; extended with post-processing |
| Validation | Pydantic v2 | 2.5+ | Existing; models already defined |
| Testing | pytest + pytest-asyncio | 7.4+ / 0.23+ | Existing test patterns |
| Logging | structlog | 24+ | Structured JSON logging |
| Agent Orchestration | RuFlo | 3.5+ | **D-001**: Immutable directive |
| Agent Governance | AgentSentry | 4.0+ | **D-002**: Immutable directive |

---

## 3. Architecture

### 3.1 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT PLANE                              │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │   RuFlo     │◄──►│ AgentSentry  │◄──►│  Developer / CI     │ │
│  │  Swarm      │    │  Governance  │    │  (Claude Code)      │ │
│  │  Orchestr.  │    │  Audit Trail │    │                     │ │
│  └──────┬──────┘    └──────┬───────┘    └─────────────────────┘ │
│         │                  │                                     │
│   MCP Tools (215+)    MCP Tools (10)                            │
│   12 Background       10 Hook Scripts                           │
│   Workers              Hash-Chain Log                           │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                   APPLICATION PLANE                               │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Frontend (React + TypeScript + Vite)                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │Campaign  │ │ Asset    │ │Compliance│ │  Metrics     │ │  │
│  │  │Builder   │ │ Gallery  │ │ Review   │ │  Dashboard   │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │  │
│  └───────────────────────┬────────────────────────────────────┘  │
│                          │ REST + WebSocket                      │
│  ┌───────────────────────▼────────────────────────────────────┐  │
│  │  API Layer (FastAPI)                                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │/api/     │ │/api/     │ │/api/     │ │/ws/          │ │  │
│  │  │campaigns │ │assets    │ │compliance│ │generation    │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │  │
│  │  │/api/     │ │/api/     │ │/api/auth │ │/api/metrics  │ │  │
│  │  │brands    │ │jobs      │ │          │ │              │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │  │
│  └───────────────────────┬────────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────▼────────────────────────────────────┐  │
│  │  Service Layer                                              │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐ │  │
│  │  │ Pipeline       │  │ Compliance   │  │ Localization   │ │  │
│  │  │ Orchestrator   │  │ Engine       │  │ Service        │ │  │
│  │  └────────┬───────┘  └──────────────┘  └────────────────┘ │  │
│  │  ┌────────┴───────┐  ┌──────────────┐  ┌────────────────┐ │  │
│  │  │ Image          │  │ Brand        │  │ Storage        │ │  │
│  │  │ Processor      │  │ Manager      │  │ Service        │ │  │
│  │  └────────────────┘  └──────────────┘  └────────────────┘ │  │
│  └───────────────────────┬────────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────▼────────────────────────────────────┐  │
│  │  Integration Layer                                          │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐│  │
│  │  │ Firefly    │  │ DALL-E 3     │  │ Gemini Imagen 4     ││  │
│  │  │ Client     │  │ Client       │  │ Client              ││  │
│  │  └────────────┘  └──────────────┘  └─────────────────────┘│  │
│  │  ┌────────────┐  ┌──────────────┐                         │  │
│  │  │ Claude     │  │ Redis / ARQ  │                         │  │
│  │  │ (Locale)   │  │ (Jobs)       │                         │  │
│  │  └────────────┘  └──────────────┘                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Data Layer                                                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │ PostgreSQL   │  │ Redis        │  │ S3 / MinIO       │ │  │
│  │  │ (metadata)   │  │ (cache/queue)│  │ (assets)         │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Separation of Concerns

| Layer | Responsibility | Forbidden Actions |
|-------|---------------|-------------------|
| Frontend | Rendering, user input, client-side validation | Direct DB access, API key handling, server-side logic |
| API | Request validation, auth, routing, serialization | Business logic, direct DB queries, image processing |
| Service | Business logic, orchestration, domain rules | HTTP concerns, rendering, direct SQL |
| Integration | External API calls, protocol translation | Business rules, state management |
| Data | Persistence, querying, migrations | Business logic, HTTP, rendering |

### 3.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async throughout | `async/await` in all service methods | Non-blocking API calls, concurrent processing |
| Repository pattern | SQLAlchemy repositories per aggregate | Testable, swappable persistence |
| Factory pattern | Retained from v1 for image services | Multi-backend support, clean instantiation |
| Event-driven jobs | ARQ for background processing | Campaign generation takes 30-120s, too long for HTTP |
| WebSocket for progress | `/ws/generation/{job_id}` | Real-time progress updates during generation |
| Monorepo | Single repository, separate `frontend/` and `src/` | Simplified CI/CD, shared types |

---

## 4. Agent Orchestration (RuFlo)

> **Governing Directive: D-001**

### 4.1 RuFlo Integration Architecture

RuFlo is registered as an MCP server and operates as the orchestration plane for all development activity.

**Registration:**
```bash
claude mcp add ruflo -- npx -y ruflo@latest
```

**Project initialization:**
```bash
npx ruflo@latest init --wizard
```

This creates:
```
.claude-flow/
  config.yaml          # RuFlo runtime configuration
  data/memory.db       # Agent shared memory (SQLite + HNSW vectors)
agents/
  architect.yaml       # Agent role definitions
  coder.yaml
  tester.yaml
  reviewer.yaml
  security-architect.yaml
```

### 4.2 Swarm Configuration

All development tasks use this anti-drift configuration:

```yaml
# .claude-flow/config.yaml
swarm:
  topology: hierarchical
  max_agents: 8
  strategy: specialized
  consensus: raft

memory:
  backend: hybrid
  path: .claude-flow/data/memory.db
  hnsw_enabled: true

neural:
  enabled: true

performance:
  mcp_response_target_ms: 100
  cli_startup_target_ms: 500
```

### 4.3 Task-to-Swarm Routing

Every development task is classified and routed to the appropriate swarm composition:

| Task Type | Code | Agents | Topology |
|-----------|------|--------|----------|
| Bug Fix | 1 | coordinator, researcher, coder, tester | hierarchical |
| New Feature | 3 | coordinator, architect, coder, tester, reviewer | hierarchical |
| Refactor | 5 | coordinator, architect, coder, reviewer | hierarchical |
| Performance | 7 | coordinator, perf-engineer, coder | hierarchical |
| Security | 9 | coordinator, security-architect, auditor | hierarchical |
| Documentation | 11 | researcher, api-docs | mesh |
| Web UI Component | 3 | coordinator, architect, coder (frontend), tester, reviewer | hierarchical |
| API Endpoint | 3 | coordinator, architect, coder (backend), tester, reviewer | hierarchical |
| Database Migration | 5 | coordinator, architect, coder, tester | hierarchical |

### 4.4 Swarm Execution Protocol

For every development task, the following protocol applies:

**Step 1: Memory Check**
```bash
npx ruflo memory search --query "[task keywords]" --namespace patterns
npx ruflo memory search --query "[task type]" --namespace tasks
npx ruflo hooks route --task "[task description]"
```

**Step 2: Swarm Initialization**
```bash
npx ruflo swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

**Step 3: Agent Spawning** (all agents in one operation)
```bash
npx ruflo agent spawn --type researcher --name "research-[task]" --task "[research prompt]"
npx ruflo agent spawn --type architect --name "arch-[task]" --task "[design prompt]"
npx ruflo agent spawn --type coder --name "code-[task]" --task "[implementation prompt]"
npx ruflo agent spawn --type tester --name "test-[task]" --task "[testing prompt]"
npx ruflo agent spawn --type reviewer --name "review-[task]" --task "[review prompt]"
```

**Step 4: Post-Completion Learning**
```bash
npx ruflo memory store --namespace patterns --key "[pattern-name]" --value "[what worked]"
npx ruflo hooks post-task --task-id "[id]" --success true --store-results true
```

### 4.5 RuFlo Background Workers

These workers are dispatched automatically based on development activity:

| Trigger Condition | Worker | Action |
|-------------------|--------|--------|
| After major refactor | `optimize` | Performance optimization analysis |
| After adding features | `testgaps` | Identify missing test coverage |
| After security changes | `audit` | Security vulnerability analysis |
| After API changes | `document` | Auto-update API documentation |
| Every 5+ file changes | `map` | Update codebase dependency map |
| Complex debugging session | `deepdive` | Deep code analysis |

### 4.6 RuFlo Memory Namespaces

| Namespace | Purpose | Example Key | Example Value |
|-----------|---------|-------------|---------------|
| `patterns` | Successful implementation patterns | `fastapi-websocket-pattern` | `Use connection manager class with broadcast method` |
| `tasks` | Completed task records | `task-campaign-api-endpoint` | `Created /api/campaigns with CRUD, pagination, filtering` |
| `solutions` | Bug fix solutions | `fix-sequential-processing` | `Replace for-loop with asyncio.gather + Semaphore(5)` |
| `architecture` | Architecture decisions | `db-choice-postgresql` | `PostgreSQL for JSONB, full-text search, async drivers` |
| `security` | Security patterns | `api-key-rotation` | `Use secrets manager, rotate every 90 days` |

---

## 5. Agent Safety & Governance (AgentSentry)

> **Governing Directive: D-002**

### 5.1 AgentSentry Integration Architecture

AgentSentry wraps all RuFlo agent activity with safety checks, permission enforcement, and audit logging.

**Registration:**
```bash
claude mcp add agent-sentry -- npx -y agent-sentry
```

**Initialization:**
```bash
npx agent-sentry init
npx agent-sentry enable 3   # Level 3: House Rules (recommended default)
```

### 5.2 Enablement Level

This project uses **Level 3 (House Rules)** as the baseline:

| Skill | Status | Configuration |
|-------|--------|---------------|
| Save Points | FULL | Auto-commit every 30 min; branch on risk score >= 8 |
| Context Health | FULL | Warn at 60% context, critical at 80% |
| Standing Orders | BASIC | Lint CLAUDE.md, enforce required sections |
| Small Bets | OFF | (Enable at Level 4 if needed) |
| Safety Checks | OFF | (Enable at Level 5 if needed) |

### 5.3 Configuration

```json
// agent-sentry.config.json
{
  "enablement": {
    "level": 3
  },
  "memory": {
    "provider": "sqlite",
    "embedding_provider": "auto",
    "database_path": "agent-sentry/data/ops.db"
  },
  "save_points": {
    "max_uncommitted_files_warning": 5,
    "auto_commit_after_minutes": 30,
    "auto_branch_on_risk_score": 8
  },
  "context_health": {
    "context_percent_warning": 60,
    "context_percent_critical": 80,
    "message_count_warning": 20,
    "message_count_critical": 30
  },
  "rules_file": {
    "claude_md_max_lines": 300,
    "required_sections": ["security", "error handling"]
  },
  "security": {
    "block_on_secret_detection": true
  },
  "budget": {
    "session_budget": "$25",
    "monthly_budget": "$1000",
    "warn_threshold": 0.80
  }
}
```

### 5.4 Hook Integration

The following hooks fire automatically via `.claude/settings.json`:

| Hook | Trigger | Action | Blocking |
|------|---------|--------|----------|
| `secret-scanner.sh` | PreToolUse (Write/Edit) | Scan for API keys, JWTs, PEM keys, connection strings | YES (exit 2 = block) |
| `permission-enforcer.sh` | PreToolUse | Enforce per-agent file/tool permissions | YES |
| `delegation-validator.sh` | PreToolUse | Validate agent-to-agent handoff tokens | YES |
| `git-hygiene-check.sh` | PreToolUse (Write/Edit) | Validate git state, enforce checkpoints | YES |
| `post-write-checks.sh` | PostToolUse | Error handling audit, PII detection, blast radius | NO (advisory) |
| `task-sizer.sh` | UserPromptSubmit | Risk scoring (0-20 scale), flag oversized changes | NO |
| `context-estimator.sh` | UserPromptSubmit | Token usage estimation | NO |
| `session-start-checks.sh` | SessionStart | Validate rules files, git state | NO |
| `session-checkpoint.sh` | Stop | Auto-commit, log session event | NO |
| `cost-tracker.sh` | PostToolUse | Per-call cost tracking against budget | NO |

### 5.5 Agent Permission Model

Each RuFlo agent has a permission file in `.claude/agents/`:

```yaml
# .claude/agents/coder.md
---
agent_id: coder
permissions:
  files:
    read: ["src/**", "tests/**", "docs/**", "examples/**"]
    write: ["src/**", "tests/**"]
    deny: [".env", ".env.*", "secrets/**", "*.key", "*.pem"]
  tools:
    allow: ["Read", "Edit", "Write", "Grep", "Glob", "Bash"]
    deny: []
  bash:
    allow: ["python3 -m pytest *", "pip install *", "npm *"]
    deny: ["rm -rf *", "curl * | bash", "chmod 777 *"]
---
```

```yaml
# .claude/agents/reviewer.md
---
agent_id: reviewer
permissions:
  files:
    read: ["src/**", "tests/**", "docs/**"]
    write: ["docs/**"]
    deny: [".env", ".env.*", "secrets/**"]
  tools:
    allow: ["Read", "Grep", "Glob"]
    deny: ["Bash", "Write", "Edit"]
---
```

### 5.6 Audit Trail Requirements

Every agent session MUST produce:
1. **Hash-chained event log** in `agent-sentry/data/ops.db` with SHA-256 chain integrity
2. **NDJSON session log** in `agent-sentry/dashboard/data/session-log.json`
3. **Cost log** in `agent-sentry/dashboard/data/cost-log.json`

Event types captured:
- `decision` -- Agent chose a particular approach
- `violation` -- Agent attempted a blocked action
- `incident` -- Error or unexpected condition

### 5.7 RuFlo + AgentSentry Interaction Flow

```
Developer submits task
        │
        ▼
┌─────────────────────┐
│ AgentSentry          │ ◄── session-start-checks.sh fires
│ SessionStart hook    │ ◄── context-estimator.sh fires
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ RuFlo Swarm Init    │ ◄── ruflo swarm init
│ Agent Spawning      │ ◄── ruflo agent spawn (per agent type)
└─────────┬───────────┘
          │
          ▼ (for each agent action)
┌─────────────────────┐
│ AgentSentry          │ ◄── permission-enforcer.sh validates file/tool access
│ PreToolUse hooks     │ ◄── secret-scanner.sh scans for secrets
│                      │ ◄── git-hygiene-check.sh validates git state
└─────────┬───────────┘
          │ (allowed)
          ▼
┌─────────────────────┐
│ Agent Executes       │ ◄── Read/Write/Edit/Bash tool call
│ (RuFlo coder/tester) │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ AgentSentry          │ ◄── post-write-checks.sh audits output
│ PostToolUse hooks    │ ◄── cost-tracker.sh logs spend
│                      │ ◄── capture_event (hash-chained)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Task Complete        │ ◄── ruflo hooks post-task --success true
│ Session End          │ ◄── session-checkpoint.sh auto-commits
│                      │ ◄── ruflo memory store (learned patterns)
└─────────────────────┘
```

---

## 6. Web Interface

### 6.1 Overview

The web interface provides visual campaign management, asset preview, compliance review, and metrics dashboards. It replaces the CLI as the primary interaction surface for non-developer users.

### 6.2 Pages and Components

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Overview: active campaigns, recent assets, key metrics |
| Campaign Builder | `/campaigns/new` | Create campaign briefs via form wizard |
| Campaign Detail | `/campaigns/:id` | View/edit campaign, see generated assets |
| Campaign List | `/campaigns` | List all campaigns with search, filter, sort |
| Asset Gallery | `/campaigns/:id/assets` | Browse generated assets with preview, download |
| Compliance Review | `/campaigns/:id/compliance` | View compliance violations, approve/reject |
| Brand Guidelines | `/brands` | Upload/manage brand guideline documents |
| Brand Detail | `/brands/:id` | View extracted guidelines, edit overrides |
| Metrics Dashboard | `/metrics` | Technical and business metrics, charts |
| Job Monitor | `/jobs` | Active/completed job status, progress bars |
| Settings | `/settings` | Backend selection, API key status, feature flags |
| Login | `/login` | Authentication |
| Registration | `/register` | User registration |

### 6.3 Campaign Builder Wizard

Multi-step form with validation at each step:

**Step 1: Campaign Details**
- Campaign name (required, 3-100 chars)
- Brand name (required)
- Target market (dropdown)
- Target audience (text)
- Image generation backend (dropdown: Firefly / DALL-E 3 / Gemini Imagen 4)

**Step 2: Products**
- Add 1+ products (repeating fieldset)
- Per product: name, description, category, features (tag input), generation prompt (textarea), existing hero image (file upload)
- Drag-and-drop reordering

**Step 3: Messaging**
- Default locale (dropdown)
- Headline (required, 1-80 chars)
- Subheadline (required, 1-120 chars)
- CTA (required, 1-40 chars)
- Enable localization toggle
- Target locales (multi-select, shown if localization enabled)

**Step 4: Aspect Ratios & Output**
- Checkboxes: 1:1, 9:16, 16:9, 4:5
- Output format: PNG, JPG (multi-select)

**Step 5: Guidelines (optional)**
- Upload brand guidelines (PDF, DOCX, TXT, JSON)
- Upload localization guidelines (YAML, JSON)
- Upload legal compliance guidelines (YAML, JSON)

**Step 6: Review & Submit**
- Summary of all inputs
- Estimated asset count: `products * locales * aspect_ratios`
- Submit button -> creates background job

### 6.4 Real-Time Generation Progress

WebSocket connection at `/ws/generation/{job_id}` sends events:

```json
{
  "type": "progress",
  "job_id": "uuid",
  "stage": "generating_hero",
  "product_id": "PROD-001",
  "locale": "en-US",
  "aspect_ratio": "1:1",
  "progress_percent": 45,
  "message": "Generating hero image for Elite Wireless Earbuds Pro...",
  "timestamp": "2026-03-25T10:30:00Z"
}
```

Progress stages (in order):
1. `validating` -- Validating brief and configuration
2. `loading_guidelines` -- Parsing brand/localization/legal documents
3. `compliance_check` -- Running legal compliance checks
4. `generating_hero` -- Generating hero image via AI backend
5. `processing_locale` -- Processing locale-specific variations
6. `resizing` -- Resizing to aspect ratios
7. `applying_overlays` -- Text and logo overlays
8. `post_processing` -- Sharpening, color correction
9. `saving_assets` -- Writing to storage
10. `generating_report` -- Computing metrics, saving reports
11. `complete` -- Done
12. `error` -- Error occurred (includes error detail)

### 6.5 Asset Gallery

- Grid view with thumbnails (lazy-loaded)
- Filter by: product, locale, aspect ratio
- Click to expand: full-size preview with metadata overlay
- Download individual assets or batch download (ZIP)
- Side-by-side comparison mode (select 2 assets)
- Metadata panel: generation method, timestamp, file size, dimensions

### 6.6 Metrics Dashboard

Two tabs: **Technical** and **Business**

**Technical tab:**
- API response time chart (line graph, min/avg/max per campaign)
- Cache hit rate (donut chart)
- Processing time breakdown (stacked bar: API calls, image processing, localization, compliance)
- Error rate trend (line graph)
- Peak memory usage (gauge)

**Business tab:**
- Time saved vs. manual (bar chart, hours)
- Cost savings (bar chart, dollars)
- ROI multiplier (single number, large)
- Assets per hour throughput (line graph)
- Compliance pass rate (donut chart)

### 6.7 Frontend Technical Requirements

| Requirement | Specification |
|-------------|---------------|
| Build tool | Vite 5+ |
| Language | TypeScript (strict mode) |
| Framework | React 18+ |
| Routing | React Router v6+ |
| State management | TanStack Query (server state) + Zustand (client state) |
| UI components | shadcn/ui |
| Styling | Tailwind CSS 3+ |
| Forms | React Hook Form + Zod validation |
| Charts | Recharts |
| File upload | react-dropzone |
| WebSocket | Native WebSocket API with reconnect logic |
| HTTP client | fetch (native) with typed wrappers |
| Authentication | JWT stored in httpOnly cookie |
| Responsive | Mobile-first, breakpoints: sm(640), md(768), lg(1024), xl(1280) |
| Accessibility | WCAG 2.1 AA compliance |
| Bundle size | < 500KB gzipped (initial load) |

---

## 7. API Layer

### 7.1 Framework

FastAPI with:
- OpenAPI 3.1 auto-generation at `/docs`
- CORS middleware (configurable origins)
- JWT authentication middleware
- Request ID middleware (UUID per request)
- Structured logging middleware
- Rate limiting middleware

### 7.2 API Design Principles

1. RESTful resource naming (`/api/campaigns`, not `/api/getCampaigns`)
2. Consistent response envelope: `{ "data": ..., "meta": { "request_id": "..." } }`
3. Pagination: cursor-based for lists (`?cursor=xxx&limit=20`)
4. Filtering: query parameters (`?status=active&backend=firefly`)
5. Sorting: `?sort=created_at&order=desc`
6. Error responses: RFC 7807 Problem Details format
7. Versioned: `/api/v1/...`

### 7.3 Authentication & Authorization

| Aspect | Specification |
|--------|---------------|
| Method | JWT (RS256) |
| Token storage | httpOnly, Secure, SameSite=Strict cookie |
| Token expiry | Access: 15 min, Refresh: 7 days |
| Roles | `admin`, `editor`, `viewer` |
| Admin | Full CRUD on all resources, user management, settings |
| Editor | Create/edit campaigns, trigger generation, view metrics |
| Viewer | Read-only access to campaigns, assets, metrics |
| Password hashing | bcrypt, cost factor 12 |
| Rate limiting | 100 req/min per user (auth), 20 req/min per IP (unauth) |

### 7.4 Endpoint Summary

See [Appendix C](#appendix-c-api-endpoints) for the complete endpoint specification.

---

## 8. Database Layer

### 8.1 Schema Overview

```sql
-- Users and authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Brand guidelines
CREATE TABLE brand_guidelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    source_file_path VARCHAR(500),
    primary_colors JSONB DEFAULT '[]',
    secondary_colors JSONB DEFAULT '[]',
    primary_font VARCHAR(100) DEFAULT 'Arial',
    secondary_font VARCHAR(100),
    brand_voice TEXT,
    photography_style TEXT,
    prohibited_elements JSONB DEFAULT '[]',
    logo_config JSONB DEFAULT '{}',
    text_customization JSONB,
    post_processing JSONB,
    raw_extracted_data JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Campaigns
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id VARCHAR(100) UNIQUE NOT NULL,
    campaign_name VARCHAR(255) NOT NULL,
    brand_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- status: draft, queued, processing, completed, failed, cancelled
    brief JSONB NOT NULL,
    image_backend VARCHAR(50) NOT NULL DEFAULT 'firefly',
    target_locales JSONB NOT NULL DEFAULT '["en-US"]',
    aspect_ratios JSONB NOT NULL DEFAULT '["1:1","9:16","16:9"]',
    brand_guidelines_id UUID REFERENCES brand_guidelines(id),
    localization_guidelines JSONB,
    legal_guidelines JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Products within campaigns
CREATE TABLE campaign_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    product_id VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    key_features JSONB DEFAULT '[]',
    generation_prompt TEXT,
    hero_image_path VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(campaign_id, product_id)
);

-- Generated assets
CREATE TABLE generated_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    product_id VARCHAR(100) NOT NULL,
    locale VARCHAR(10) NOT NULL,
    aspect_ratio VARCHAR(10) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    width INT,
    height INT,
    generation_method VARCHAR(50) NOT NULL,
    generation_time_ms FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(campaign_id, product_id, locale, aspect_ratio)
);

-- Background jobs
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    -- status: queued, running, completed, failed, cancelled
    progress_percent INT NOT NULL DEFAULT 0,
    current_stage VARCHAR(50),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    error_trace TEXT,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Compliance reports
CREATE TABLE compliance_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    is_compliant BOOLEAN NOT NULL,
    violations JSONB NOT NULL DEFAULT '[]',
    summary JSONB NOT NULL DEFAULT '{}',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Campaign metrics
CREATE TABLE campaign_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    technical_metrics JSONB NOT NULL DEFAULT '{}',
    business_metrics JSONB NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_created_by ON campaigns(created_by);
CREATE INDEX idx_generated_assets_campaign ON generated_assets(campaign_id);
CREATE INDEX idx_jobs_campaign ON jobs(campaign_id);
CREATE INDEX idx_jobs_status ON jobs(status);
```

### 8.2 Migration Strategy

- Tool: **Alembic** (SQLAlchemy migration framework)
- Location: `src/db/migrations/`
- Naming: `YYYYMMDD_HHMMSS_description.py`
- All migrations must be reversible (implement `upgrade()` and `downgrade()`)
- Migrations run automatically on application startup in development
- Migrations require explicit invocation in production

---

## 9. Image Generation Services

### 9.1 Service Interface (Unchanged)

```python
class ImageGenerationService(ABC):
    async def generate_image(
        self, prompt: str, size: str, brand_guidelines: Optional[ComprehensiveBrandGuidelines]
    ) -> bytes

    def get_backend_name(self) -> str
    def validate_config(self) -> tuple[bool, list[str]]
```

### 9.2 Backend Specifications

| Backend | Model | Max Size | Rate Limit | Timeout |
|---------|-------|----------|------------|---------|
| Adobe Firefly | Firefly v3 | 2048x2048 | Per Adobe plan | 60s |
| OpenAI DALL-E 3 | dall-e-3 | 1024x1792 max | 5 img/min (tier 1) | 60s |
| Google Gemini | imagen-4.0-generate-001 | Varies | Per Google plan | 60s |

### 9.3 Required Changes to Existing Services

| File | Change | Rationale |
|------|--------|-----------|
| `src/genai/base.py` | Add `structlog` logger; remove `print()` | Structured logging |
| `src/genai/firefly.py` | Replace `print()` with logger; add retry metrics emission | Observability |
| `src/genai/openai_service.py` | Replace `print()` with logger; add retry metrics emission | Observability |
| `src/genai/gemini_service.py` | Replace `print()` with logger; add retry metrics emission | Observability |
| All services | Add `asyncio.Semaphore` parameter, honor `MAX_CONCURRENT_REQUESTS` | True concurrency |
| All services | Emit structured events for AgentSentry capture | D-002 compliance |

### 9.4 New: HTTP Session Reuse

Current code creates a new `aiohttp.ClientSession` per API call. Change to session-per-service:

```python
class ImageGenerationService(ABC):
    def __init__(self, api_key: str, max_retries: int = 3):
        self.api_key = api_key
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
```

---

## 10. Pipeline Engine

### 10.1 Current Issues

1. **Sequential processing** (`pipeline.py:198`): `for product in brief.products:` -- must be concurrent
2. **Code duplication**: Lines 286-330 and 331-381 contain identical image processing logic
3. **Hardcoded metrics**: Lines 455-457 use fabricated baseline costs
4. **`print()` logging**: 40+ print statements throughout

### 10.2 Refactored Pipeline Architecture

```
CreativeAutomationPipeline
├── validate_brief()
├── load_guidelines()          # brand, localization, legal
├── run_compliance_check()     # returns violations or passes
├── process_campaign()         # main entry point
│   ├── _process_product()     # per-product (concurrent via asyncio.gather)
│   │   ├── _get_or_generate_hero()
│   │   └── _process_locale()  # per-locale
│   │       └── _process_ratio()   # per-ratio
│   │           ├── resize
│   │           ├── text_overlay
│   │           ├── logo_overlay
│   │           └── post_processing
│   ├── _calculate_metrics()
│   └── _save_reports()
└── close()                    # cleanup sessions
```

### 10.3 Concurrency Model

```python
semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

async def _process_product(self, product, ...):
    async with semaphore:
        hero_bytes = await self._get_or_generate_hero(product, ...)
        # ... process all locales/ratios for this product

# In process_campaign:
tasks = [self._process_product(p, ...) for p in brief.products]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 10.4 Job Integration

The pipeline is invoked by the background job system (ARQ), not directly by HTTP handlers:

```python
async def process_campaign_job(ctx, campaign_id: str):
    """ARQ worker function."""
    pipeline = CreativeAutomationPipeline(...)
    try:
        # Load campaign from DB
        campaign = await campaign_repo.get(campaign_id)
        brief = CampaignBrief(**campaign.brief)

        # Send progress updates via Redis pub/sub
        await ctx["redis"].publish(f"job:{campaign_id}", json.dumps({
            "type": "progress", "stage": "validating", "progress_percent": 0
        }))

        output = await pipeline.process_campaign(brief, progress_callback=...)
        # Save results to DB
        await campaign_repo.update_status(campaign_id, "completed", output)
    except Exception as e:
        await campaign_repo.update_status(campaign_id, "failed", str(e))
    finally:
        await pipeline.close()
```

---

## 11. Legal Compliance Engine

### 11.1 Current State

`src/legal_checker.py` (267 lines) is well-implemented with:
- Word boundary matching via regex
- Severity levels (error, warning, info)
- Locale-specific restrictions
- Required disclaimers
- Superlative detection
- Report generation

### 11.2 Required Changes

| Change | Rationale |
|--------|-----------|
| Store compliance results in PostgreSQL (`compliance_reports` table) | Queryable history |
| Add compliance endpoint: `GET /api/v1/campaigns/:id/compliance` | Web UI access |
| Replace `print()` with structured logging | Observability |
| Add `compliance_approved_by` and `compliance_approved_at` fields | Audit trail for manual overrides |
| Emit AgentSentry events for compliance violations | D-002 compliance |

### 11.3 Compliance Workflow (Web UI)

1. User creates campaign via builder
2. System runs compliance check automatically before generation
3. If violations exist with severity=error: campaign is blocked, user sees violation details
4. User can fix content and re-check
5. If only warnings/info: user can approve and proceed (with audit trail)

---

## 12. Localization System

### 12.1 Current State

Claude 3.5 Sonnet-based localization via `src/genai/claude.py`. Supports 20+ locales with cultural adaptation.

### 12.2 Required Changes

| Change | Rationale |
|--------|-----------|
| Add localization cache in Redis | Avoid duplicate API calls for same text+locale |
| Add `structlog` logging | Replace `print()` |
| Track localization time per locale in metrics | Performance visibility |
| Add fallback for Claude unavailability | Graceful degradation |

### 12.3 Localization Cache Key Format

```
locale:{locale}:sha256({source_text})
```

TTL: 7 days (configurable via `LOCALIZATION_CACHE_TTL_SECONDS`)

---

## 13. Brand Guidelines System

### 13.1 Current State

`src/parsers/brand_parser.py` extracts guidelines from PDF/DOCX/TXT/JSON with Claude fallback to regex.

### 13.2 Required Changes

| Change | Rationale |
|--------|-----------|
| Store extracted guidelines in PostgreSQL (`brand_guidelines` table) | Reusable across campaigns |
| Add file upload endpoint: `POST /api/v1/brands` | Web UI upload |
| Add manual override endpoint: `PATCH /api/v1/brands/:id` | Fine-tune extracted values |
| Store original uploaded file in S3/MinIO | Reference and re-extraction |
| Add `structlog` logging | Replace `print()` |

---

## 14. Image Processing System

### 14.1 Current State

`src/image_processor_v2.py` (374 lines) handles:
- Aspect ratio resizing (smart crop)
- Per-element text overlay (headline, subheadline, CTA)
- Logo overlay (4-corner positioning)
- Post-processing (sharpening, contrast, saturation)

### 14.2 Required Changes

| Change | Rationale |
|--------|-----------|
| Accept `PIL.Image` objects instead of raw bytes where possible | Avoid redundant encode/decode |
| Add `structlog` logging | Replace `print()` |
| Add processing time per operation to return value | Granular metrics |
| Keep v1 processor for backward compatibility | Existing campaigns may reference it |

---

## 15. Storage & Asset Management

### 15.1 Current State

`src/storage.py` (184 lines) saves assets to local filesystem in `output/` directory.

### 15.2 Target Architecture

Dual storage backend:

| Backend | Purpose | When |
|---------|---------|------|
| Local filesystem | Development, testing | `STORAGE_BACKEND=local` |
| S3-compatible (MinIO local, AWS S3 prod) | Production | `STORAGE_BACKEND=s3` |

### 15.3 Storage Interface

```python
class StorageBackend(ABC):
    async def save(self, key: str, data: bytes, content_type: str) -> str
    async def get(self, key: str) -> bytes
    async def delete(self, key: str) -> None
    async def get_url(self, key: str, expires_in: int = 3600) -> str
    async def list_keys(self, prefix: str) -> List[str]
```

### 15.4 Asset Key Format

```
campaigns/{campaign_id}/products/{product_id}/hero/{product_id}_hero.png
campaigns/{campaign_id}/products/{product_id}/{locale}/{aspect_ratio}/asset.{format}
```

---

## 16. Metrics & Reporting

### 16.1 Technical Metrics (17 fields -- unchanged)

All existing `TechnicalMetrics` fields are retained. Stored in `campaign_metrics.technical_metrics` JSONB column.

### 16.2 Business Metrics (13 fields -- modified)

**Current problem**: Hardcoded baselines (`$2,700`, `96 hours`, `$50/hr`) produce fabricated ROI figures.

**Solution**: Make baselines configurable per organization:

```python
class BusinessMetricsConfig(BaseModel):
    manual_baseline_hours: float = Field(default=96.0, description="Manual hours for baseline campaign")
    manual_baseline_cost: float = Field(default=2700.0, description="Manual cost for baseline campaign")
    manual_baseline_assets: int = Field(default=36, description="Assets in baseline campaign")
    hourly_rate: float = Field(default=50.0, description="Hourly rate for labor savings")
```

Store in `settings` table or application config. Display prominently that these are estimates based on configured baselines.

---

## 17. Security

### 17.1 Secrets Management

| Item | Current | Target |
|------|---------|--------|
| `.env` file | Committed (or trackable) | Added to `.gitignore`; use env vars in CI |
| API keys | Plaintext in `os.getenv()` | Environment variables, validated at startup |
| Prompt logging | `print(f"Final prompt: {prompt}")` | Remove from production; debug-level only |
| Error details | `print(f"API error: {status} - {error_text}")` | Log at warning level; sanitize before client response |

### 17.2 Input Validation

| Surface | Validation |
|---------|-----------|
| Campaign brief JSON | Pydantic v2 models (existing) |
| File uploads | Extension whitelist (pdf, docx, txt, json, yaml, yml); max size 10MB |
| API path parameters | UUID format validation |
| Query parameters | Type coercion via FastAPI |
| Prompts to AI backends | Max length 4000 chars; strip control characters |
| File paths in brief | Resolve and validate within allowed directories; reject path traversal |

### 17.3 AgentSentry Security Features

Per D-002, AgentSentry provides:
- **Secret scanning**: Detects API keys, JWTs, PEM keys, connection strings on every write operation
- **Permission enforcement**: Per-agent file and tool access control
- **Cost tracking**: Budget limits prevent runaway API spend
- **Audit trail**: Hash-chained, tamper-evident event log

---

## 18. Testing Strategy

### 18.1 Test Pyramid

| Level | Target Coverage | Framework | Location |
|-------|----------------|-----------|----------|
| Unit | 80%+ line coverage | pytest | `tests/unit/` |
| Integration | API endpoints, DB operations | pytest + httpx | `tests/integration/` |
| E2E | Critical user flows | Playwright | `tests/e2e/` |

### 18.2 Test Directory Structure

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_legal_checker.py
│   ├── test_image_processor.py
│   ├── test_storage.py
│   ├── test_parsers.py
│   └── test_pipeline.py
├── integration/
│   ├── test_api_campaigns.py
│   ├── test_api_assets.py
│   ├── test_api_auth.py
│   ├── test_api_compliance.py
│   ├── test_api_brands.py
│   ├── test_api_jobs.py
│   ├── test_db_repositories.py
│   └── test_job_processing.py
├── e2e/
│   ├── test_campaign_flow.py
│   └── test_asset_gallery.py
├── fixtures/
│   ├── sample_brief.json
│   ├── sample_guidelines.yaml
│   └── sample_image.png
└── conftest.py
```

### 18.3 Test Requirements

1. All tests pass before merge (CI-gated)
2. No test may depend on external API calls (mock all AI backends)
3. Integration tests use a test PostgreSQL database (created/destroyed per session)
4. Coverage report generated on every CI run
5. Coverage floor: 80% overall, 90% for `src/legal_checker.py` and `src/models.py`
6. Async tests use `pytest-asyncio` with `asyncio_mode = auto`

### 18.4 Fixing Current Test Suite

| Issue | Fix |
|-------|-----|
| `pytest.ini` mandates `--asyncio-mode=auto` in `addopts` | Move to `pyproject.toml` `[tool.pytest.ini_options]` |
| `pytest-cov` and `pytest-asyncio` not installed | Add to `[project.optional-dependencies]` test group |
| Tests import `click`, `PIL`, `pydantic` not installed | Add `pyproject.toml` with proper dependency groups |
| `conftest.py` has 200+ lines of fixtures | Keep; refactor into fixture modules if needed |

---

## 19. CI/CD Pipeline

### 19.1 GitHub Actions Workflows

**`.github/workflows/ci.yml`** -- Runs on every push and PR:

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install ruff
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_DB: test, POSTGRES_PASSWORD: test }
        ports: ['5432:5432']
      redis:
        image: redis:7
        ports: ['6379:6379']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e ".[test]"
      - run: pytest tests/ --cov=src --cov-report=xml --cov-fail-under=80
      - uses: codecov/codecov-action@v4

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run: { working-directory: frontend }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm run build
```

---

## 20. Configuration Management

### 20.1 `pyproject.toml` (New -- replaces `requirements.txt`)

```toml
[project]
name = "adobe-genai-platform"
version = "2.0.0"
description = "AI-powered creative automation platform"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.5.0",
    "python-dotenv>=1.0.0",
    "aiohttp>=3.9.1",
    "Pillow>=10.3.0",
    "psutil>=5.9.0",
    "PyMuPDF>=1.23.8",
    "python-docx>=1.1.0",
    "PyYAML>=6.0.1",
    "click>=8.1.7",
    "structlog>=24.0.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "arq>=0.26.0",
    "redis>=5.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.7",
    "boto3>=1.34.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
test = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.27.0",
    "factory-boy>=3.3.0",
]
dev = [
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pre-commit>=3.7.0",
]
```

### 20.2 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | Yes | `redis://localhost:6379` | Redis connection string |
| `SECRET_KEY` | Yes | - | JWT signing key (min 32 chars) |
| `FIREFLY_API_KEY` | No* | - | Adobe Firefly API key |
| `FIREFLY_CLIENT_ID` | No* | - | Adobe Firefly client ID |
| `OPENAI_API_KEY` | No* | - | OpenAI API key |
| `GEMINI_API_KEY` | No* | - | Google Gemini API key |
| `CLAUDE_API_KEY` | No | - | Anthropic Claude API key |
| `DEFAULT_IMAGE_BACKEND` | No | `firefly` | Default AI backend |
| `STORAGE_BACKEND` | No | `local` | `local` or `s3` |
| `S3_BUCKET` | If s3 | - | S3 bucket name |
| `S3_ENDPOINT_URL` | If s3 | - | S3/MinIO endpoint URL |
| `S3_ACCESS_KEY_ID` | If s3 | - | S3 access key |
| `S3_SECRET_ACCESS_KEY` | If s3 | - | S3 secret key |
| `MAX_CONCURRENT_REQUESTS` | No | `5` | Max concurrent AI API calls |
| `API_TIMEOUT` | No | `60` | API timeout in seconds |
| `MAX_RETRIES` | No | `3` | Max retry attempts |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated CORS origins |

*At least one image backend must be configured.

---

## 21. Error Handling & Logging

### 21.1 Logging Standard

All modules use `structlog` with JSON output:

```python
import structlog
logger = structlog.get_logger(__name__)

# Usage:
logger.info("campaign.processing.started", campaign_id=campaign_id, products=len(products))
logger.warning("api.rate_limited", backend="firefly", retry_attempt=2)
logger.error("pipeline.product_failed", product_id=product_id, error=str(e), exc_info=True)
```

### 21.2 Error Response Format (RFC 7807)

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "Campaign brief is missing required field: campaign_name",
  "instance": "/api/v1/campaigns",
  "errors": [
    {"field": "campaign_name", "message": "Field is required"}
  ]
}
```

### 21.3 Exception Hierarchy

```python
class AppError(Exception): ...
class NotFoundError(AppError): ...
class ValidationError(AppError): ...
class AuthenticationError(AppError): ...
class AuthorizationError(AppError): ...
class BackendUnavailableError(AppError): ...
class ComplianceError(AppError): ...
class StorageError(AppError): ...
class JobError(AppError): ...
```

---

## 22. Deployment

### 22.1 Development

```bash
# Backend
pip install -e ".[dev,test]"
uvicorn src.api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Services
docker compose up -d postgres redis minio
```

### 22.2 Production

Docker Compose or Kubernetes with:
- `api` service (FastAPI + Uvicorn, 2+ workers)
- `worker` service (ARQ worker, 1+ instances)
- `frontend` service (Nginx serving built React app)
- `postgres` service (PostgreSQL 16)
- `redis` service (Redis 7)
- `minio` service (MinIO for S3-compatible storage, or use AWS S3)

---

## 23. Migration Plan

### 23.1 Phase Sequence

| Phase | Scope | Deps |
|-------|-------|------|
| **Phase 0** | Fix foundations: `pyproject.toml`, `.gitignore`, logging, fix tests | None |
| **Phase 1** | RuFlo + AgentSentry setup: install, configure, agent permissions | Phase 0 |
| **Phase 2** | Database + API layer: PostgreSQL schema, FastAPI endpoints, auth | Phase 0 |
| **Phase 3** | Pipeline refactor: concurrency, session reuse, job queue | Phase 2 |
| **Phase 4** | Frontend: React app, campaign builder, asset gallery | Phase 2 |
| **Phase 5** | Storage: S3 backend, asset serving | Phase 3 |
| **Phase 6** | Metrics dashboard, reporting UI | Phase 4 |
| **Phase 7** | CI/CD: GitHub Actions, automated tests | Phase 0 |
| **Phase 8** | Hardening: security audit, performance tuning, load testing | All |

### 23.2 Phase 0: Fix Foundations

| Task | Files | Acceptance Criteria |
|------|-------|-------------------|
| Create `pyproject.toml` | `pyproject.toml` | `pip install -e ".[test]"` succeeds |
| Add `.env` to `.gitignore` | `.gitignore` | `git status` shows `.env` as untracked |
| Remove `.env` from git tracking | `.gitignore`, git history | `.env` not in committed files |
| Replace all `print()` with `structlog` | All `src/*.py` | Zero `print()` calls in `src/` |
| Fix `pytest.ini` / move to `pyproject.toml` | `pyproject.toml` | `pytest` runs without collection errors |
| Install test dependencies | `pyproject.toml` | All 12 test files collect and pass |
| Move imports to top of file | `src/pipeline.py:253` | No `import` inside function bodies |
| Add `ruff` configuration | `pyproject.toml` | `ruff check src/` passes |

### 23.3 Phase 1: RuFlo + AgentSentry Setup

| Task | Files | Acceptance Criteria |
|------|-------|-------------------|
| Install RuFlo MCP server | `.claude/settings.json` | `ruflo doctor` passes |
| Run `ruflo init --wizard` | `.claude-flow/`, `agents/` | Config files created |
| Install AgentSentry | `package.json` or npm | `npx agent-sentry health` passes |
| Run `npx agent-sentry init` | `agent-sentry.config.json`, `.claude/` | Level 3 enablement active |
| Create agent permission files | `.claude/agents/*.md` | coder, tester, reviewer, architect defined |
| Verify hook integration | `.claude/settings.json` | All 10 hooks registered |
| Test swarm init + agent spawn | Manual test | Swarm initializes, agents spawn, hooks fire |

### 23.4 Phase 2: Database + API Layer

| Task | Files | Acceptance Criteria |
|------|-------|-------------------|
| Add PostgreSQL schema | `src/db/models.py`, migrations | `alembic upgrade head` succeeds |
| Create SQLAlchemy models | `src/db/models.py` | Models match schema in Section 8 |
| Create repository layer | `src/db/repositories/` | CRUD for all tables |
| Create FastAPI app | `src/api/main.py` | Server starts, `/docs` shows OpenAPI |
| Implement auth endpoints | `src/api/routes/auth.py` | Register, login, refresh work |
| Implement campaign CRUD | `src/api/routes/campaigns.py` | All endpoints from Appendix C |
| Implement asset endpoints | `src/api/routes/assets.py` | List, get, download work |
| Implement brand endpoints | `src/api/routes/brands.py` | Upload, list, get work |
| Add integration tests | `tests/integration/` | 80%+ coverage on API layer |

### 23.5 Phase 3: Pipeline Refactor

| Task | Files | Acceptance Criteria |
|------|-------|-------------------|
| Refactor to concurrent processing | `src/pipeline.py` | `asyncio.gather` with semaphore |
| Extract `_process_product()` | `src/pipeline.py` | Eliminate code duplication |
| Add HTTP session reuse | `src/genai/base.py`, all services | Single session per service instance |
| Integrate ARQ job queue | `src/jobs/worker.py` | Campaign processing runs in background |
| Add WebSocket progress | `src/api/routes/ws.py` | Real-time updates during generation |
| Add Redis-based localization cache | `src/services/localization.py` | Cache hits for duplicate text+locale |

### 23.6 Phase 4: Frontend

| Task | Files | Acceptance Criteria |
|------|-------|-------------------|
| Scaffold React + Vite + TypeScript | `frontend/` | `npm run dev` serves app |
| Install shadcn/ui + Tailwind | `frontend/` | Components render correctly |
| Build campaign builder wizard | `frontend/src/pages/CampaignBuilder/` | All 6 steps functional |
| Build campaign list page | `frontend/src/pages/Campaigns/` | List, search, filter, sort |
| Build asset gallery | `frontend/src/pages/AssetGallery/` | Grid view, preview, download |
| Build compliance review page | `frontend/src/pages/Compliance/` | Violations displayed, approve flow |
| Build metrics dashboard | `frontend/src/pages/Metrics/` | Charts render with real data |
| Build job monitor | `frontend/src/pages/Jobs/` | WebSocket progress bars |
| Build auth pages | `frontend/src/pages/Auth/` | Login, registration |
| Build brand management | `frontend/src/pages/Brands/` | Upload, list, edit |
| Build settings page | `frontend/src/pages/Settings/` | Backend selection, feature flags |

---

## 24. Acceptance Criteria

### 24.1 Global Acceptance Criteria

Every deliverable must satisfy ALL of the following:

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-01 | All code changes orchestrated through RuFlo swarm | AgentSentry audit trail shows RuFlo agent IDs |
| AC-02 | AgentSentry Level 3 active during all agent sessions | `npx agent-sentry health` shows Level 3 |
| AC-03 | No secrets in committed code | `secret-scanner.sh` passes on all files |
| AC-04 | All tests pass | `pytest` exit code 0 in CI |
| AC-05 | Coverage >= 80% | `pytest --cov-fail-under=80` passes |
| AC-06 | No `print()` in `src/` | `grep -r "print(" src/` returns zero matches |
| AC-07 | All API endpoints documented | `/docs` shows complete OpenAPI spec |
| AC-08 | Frontend builds without errors | `npm run build` exit code 0 |
| AC-09 | WCAG 2.1 AA compliance | axe-core audit passes |
| AC-10 | Files under 500 lines | No source file exceeds 500 LOC |

### 24.2 Feature-Specific Acceptance Criteria

| Feature | Criteria |
|---------|---------|
| Campaign Builder | 6-step wizard completes; submission creates background job; progress shown via WebSocket |
| Asset Gallery | Assets load with thumbnails; filter by product/locale/ratio works; download works |
| Compliance Review | Violations displayed with severity; approve/reject flow works; audit trail created |
| Metrics Dashboard | Technical and business charts render; data matches DB records |
| Concurrent Processing | 3-product campaign processes in < 1.5x single-product time (given API limits) |
| Authentication | Register, login, logout, refresh token work; role-based access enforced |

---

## Appendix A: Target File Tree

```
CreativeForgeAI/
├── .claude/
│   ├── settings.json                    # AgentSentry hooks + RuFlo MCP
│   ├── agents/
│   │   ├── coder.md                     # Coder agent permissions
│   │   ├── tester.md                    # Tester agent permissions
│   │   ├── reviewer.md                  # Reviewer agent permissions
│   │   ├── architect.md                 # Architect agent permissions
│   │   └── security-architect.md        # Security agent permissions
│   └── commands/
│       └── agent-sentry/                # AgentSentry slash commands
├── .claude-flow/
│   ├── config.yaml                      # RuFlo configuration
│   └── data/
│       └── memory.db                    # RuFlo shared memory
├── agents/
│   ├── architect.yaml                   # RuFlo agent definitions
│   ├── coder.yaml
│   ├── reviewer.yaml
│   ├── security-architect.yaml
│   └── tester.yaml
├── agent-sentry/
│   ├── data/
│   │   └── ops.db                       # AgentSentry event store
│   └── dashboard/
│       └── data/                        # NDJSON logs
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── api/                             # NEW: FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI app factory
│   │   ├── dependencies.py              # Dependency injection
│   │   ├── middleware.py                # Auth, logging, CORS, rate limit
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py                  # POST /register, /login, /refresh
│   │       ├── campaigns.py             # CRUD /campaigns
│   │       ├── assets.py               # GET /assets, /assets/:id/download
│   │       ├── brands.py               # CRUD /brands
│   │       ├── compliance.py           # GET/POST /compliance
│   │       ├── jobs.py                 # GET /jobs
│   │       ├── metrics.py             # GET /metrics
│   │       └── ws.py                   # WebSocket /ws/generation/:job_id
│   ├── db/                              # NEW: Database layer
│   │   ├── __init__.py
│   │   ├── base.py                      # SQLAlchemy base, engine, session
│   │   ├── models.py                    # SQLAlchemy ORM models
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── campaign_repo.py
│   │   │   ├── asset_repo.py
│   │   │   ├── brand_repo.py
│   │   │   ├── user_repo.py
│   │   │   ├── job_repo.py
│   │   │   └── compliance_repo.py
│   │   └── migrations/                  # Alembic migrations
│   │       ├── env.py
│   │       └── versions/
│   ├── services/                        # NEW: Service layer
│   │   ├── __init__.py
│   │   ├── campaign_service.py
│   │   ├── asset_service.py
│   │   ├── brand_service.py
│   │   ├── compliance_service.py
│   │   ├── localization_service.py
│   │   └── auth_service.py
│   ├── jobs/                            # NEW: Background jobs
│   │   ├── __init__.py
│   │   ├── worker.py                    # ARQ worker
│   │   └── tasks.py                     # Job task definitions
│   ├── storage/                         # NEW: Pluggable storage
│   │   ├── __init__.py
│   │   ├── base.py                      # StorageBackend ABC
│   │   ├── local.py                     # Local filesystem
│   │   └── s3.py                        # S3-compatible storage
│   ├── genai/                           # EXISTING: AI services (modified)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── firefly.py
│   │   ├── openai_service.py
│   │   ├── gemini_service.py
│   │   ├── claude.py
│   │   └── claude_service_image.py
│   ├── parsers/                         # EXISTING: Document parsers (modified)
│   │   ├── __init__.py
│   │   ├── brand_parser.py
│   │   ├── localization_parser.py
│   │   └── legal_parser.py
│   ├── config.py                        # EXISTING: Config (modified)
│   ├── models.py                        # EXISTING: Pydantic models (extended)
│   ├── pipeline.py                      # EXISTING: Pipeline (refactored)
│   ├── cli.py                           # EXISTING: CLI (maintained)
│   ├── legal_checker.py                 # EXISTING: Compliance (modified)
│   ├── image_processor.py              # EXISTING: V1 processor (kept)
│   ├── image_processor_v2.py           # EXISTING: V2 processor (modified)
│   ├── campaign_generator.py           # EXISTING: Brief generator (kept)
│   └── storage.py                       # EXISTING: Legacy storage (deprecated)
├── frontend/                            # NEW: React application
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                         # API client layer
│       │   ├── client.ts
│       │   ├── campaigns.ts
│       │   ├── assets.ts
│       │   ├── auth.ts
│       │   ├── brands.ts
│       │   └── types.ts
│       ├── components/                  # Reusable components
│       │   ├── ui/                      # shadcn/ui components
│       │   ├── layout/
│       │   │   ├── AppLayout.tsx
│       │   │   ├── Sidebar.tsx
│       │   │   └── Header.tsx
│       │   ├── campaign/
│       │   │   ├── CampaignCard.tsx
│       │   │   ├── CampaignWizard.tsx
│       │   │   └── ProductForm.tsx
│       │   ├── assets/
│       │   │   ├── AssetGrid.tsx
│       │   │   ├── AssetPreview.tsx
│       │   │   └── AssetFilters.tsx
│       │   ├── compliance/
│       │   │   ├── ViolationList.tsx
│       │   │   └── ComplianceStatus.tsx
│       │   ├── metrics/
│       │   │   ├── TechnicalMetrics.tsx
│       │   │   └── BusinessMetrics.tsx
│       │   └── jobs/
│       │       ├── JobProgress.tsx
│       │       └── JobList.tsx
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── CampaignList.tsx
│       │   ├── CampaignDetail.tsx
│       │   ├── CampaignBuilder.tsx
│       │   ├── AssetGallery.tsx
│       │   ├── ComplianceReview.tsx
│       │   ├── BrandList.tsx
│       │   ├── BrandDetail.tsx
│       │   ├── MetricsDashboard.tsx
│       │   ├── JobMonitor.tsx
│       │   ├── Settings.tsx
│       │   ├── Login.tsx
│       │   └── Register.tsx
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   ├── useAuth.ts
│       │   └── useCampaigns.ts
│       ├── store/
│       │   └── authStore.ts
│       └── lib/
│           └── utils.ts
├── tests/                               # RESTRUCTURED
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── fixtures/
│   └── conftest.py
├── docker-compose.yml                   # NEW
├── Dockerfile                           # NEW
├── pyproject.toml                       # NEW (replaces requirements.txt)
├── alembic.ini                          # NEW
├── agent-sentry.config.json             # NEW (D-002)
├── .env.example                         # UPDATED
├── .gitignore                           # UPDATED (add .env)
├── CLAUDE.md                            # UPDATED
└── README.md                            # EXISTING
```

---

## Appendix B: Data Models

### B.1 Existing Pydantic Models (Retained)

All 26 existing Pydantic models in `src/models.py` are retained without breaking changes:

- `AspectRatio`, `Market`
- `Product`, `CampaignMessage`, `CampaignBrief`
- `TextShadow`, `TextOutline`, `TextBackgroundBox`, `TextElementStyle`, `TextCustomization`
- `PostProcessingConfig`
- `ComprehensiveBrandGuidelines`, `LegalComplianceGuidelines`, `LocalizationGuidelines`
- `GeneratedAsset`, `TechnicalMetrics`, `BusinessMetrics`, `CampaignOutput`

### B.2 New Pydantic Models

```python
# Auth
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=2, max_length=100)

class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# Campaigns
class CampaignCreate(BaseModel):
    brief: CampaignBrief
    brand_guidelines_id: Optional[UUID] = None

class CampaignResponse(BaseModel):
    id: UUID
    campaign_id: str
    campaign_name: str
    status: str
    brief: dict
    created_at: datetime
    asset_count: int
    job: Optional[dict]

# Jobs
class JobResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    status: str
    progress_percent: int
    current_stage: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

# Brands
class BrandGuidelinesResponse(BaseModel):
    id: UUID
    name: str
    primary_colors: list[str]
    primary_font: str
    brand_voice: Optional[str]
    photography_style: Optional[str]
    created_at: datetime

# Pagination
class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta

class PaginationMeta(BaseModel):
    total: int
    limit: int
    cursor: Optional[str]
    has_more: bool

# Business metrics config
class BusinessMetricsConfig(BaseModel):
    manual_baseline_hours: float = 96.0
    manual_baseline_cost: float = 2700.0
    manual_baseline_assets: int = 36
    hourly_rate: float = 50.0
```

---

## Appendix C: API Endpoints

### C.1 Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | No | Create user account |
| POST | `/api/v1/auth/login` | No | Authenticate, get JWT |
| POST | `/api/v1/auth/refresh` | Yes | Refresh access token |
| POST | `/api/v1/auth/logout` | Yes | Invalidate refresh token |
| GET | `/api/v1/auth/me` | Yes | Get current user |

### C.2 Campaigns

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/campaigns` | Yes | Any | List campaigns (paginated, filterable) |
| POST | `/api/v1/campaigns` | Yes | Editor+ | Create campaign + queue job |
| GET | `/api/v1/campaigns/:id` | Yes | Any | Get campaign detail |
| PATCH | `/api/v1/campaigns/:id` | Yes | Editor+ | Update campaign (draft only) |
| DELETE | `/api/v1/campaigns/:id` | Yes | Admin | Delete campaign |
| POST | `/api/v1/campaigns/:id/reprocess` | Yes | Editor+ | Re-run campaign generation |

### C.3 Assets

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/campaigns/:id/assets` | Yes | Any | List assets for campaign |
| GET | `/api/v1/assets/:id` | Yes | Any | Get asset metadata |
| GET | `/api/v1/assets/:id/download` | Yes | Any | Download asset file |
| POST | `/api/v1/campaigns/:id/assets/download-all` | Yes | Any | Download all as ZIP |

### C.4 Brands

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/brands` | Yes | Any | List brand guidelines |
| POST | `/api/v1/brands` | Yes | Editor+ | Upload + extract brand guidelines |
| GET | `/api/v1/brands/:id` | Yes | Any | Get brand detail |
| PATCH | `/api/v1/brands/:id` | Yes | Editor+ | Update brand overrides |
| DELETE | `/api/v1/brands/:id` | Yes | Admin | Delete brand |

### C.5 Compliance

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/campaigns/:id/compliance` | Yes | Any | Get compliance report |
| POST | `/api/v1/campaigns/:id/compliance/check` | Yes | Editor+ | Run compliance check |
| POST | `/api/v1/campaigns/:id/compliance/approve` | Yes | Editor+ | Approve with warnings |

### C.6 Jobs

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/jobs` | Yes | Any | List jobs (paginated) |
| GET | `/api/v1/jobs/:id` | Yes | Any | Get job status |
| POST | `/api/v1/jobs/:id/cancel` | Yes | Editor+ | Cancel running job |

### C.7 Metrics

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/campaigns/:id/metrics` | Yes | Any | Get metrics for campaign |
| GET | `/api/v1/metrics/aggregate` | Yes | Any | Aggregate metrics across campaigns |

### C.8 Settings

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/settings` | Yes | Admin | Get application settings |
| PATCH | `/api/v1/settings` | Yes | Admin | Update settings |
| GET | `/api/v1/settings/backends` | Yes | Any | List available backends |

### C.9 WebSocket

| Path | Auth | Description |
|------|------|-------------|
| `/ws/generation/{job_id}` | Token param | Real-time generation progress |

---

## Appendix D: Gap Register

Cross-reference of all identified gaps from the initial analysis, with their resolution in this specification:

| Gap ID | Description | Section | Resolution |
|--------|-------------|---------|------------|
| GAP-1 | No web interface | Section 6 | Full React frontend with 12 pages |
| GAP-2 | Tests cannot run | Sections 18, 23.2 | `pyproject.toml` with test deps, CI pipeline |
| GAP-3 | No `pyproject.toml` | Section 20.1 | Full `pyproject.toml` with dependency groups |
| GAP-4 | Sequential processing | Section 10.3 | `asyncio.gather` + `Semaphore` |
| GAP-5 | API keys in `.env` committed | Section 17.1 | `.env` in `.gitignore`, secrets management |
| GAP-6 | No CI/CD | Section 19 | GitHub Actions: lint, test, build |
| GAP-7 | No REST API | Section 7 | FastAPI with 30+ endpoints |
| GAP-8 | No database | Section 8 | PostgreSQL with 8 tables |
| GAP-9 | No auth | Section 7.3 | JWT-based auth with RBAC |
| GAP-10 | No job queue | Section 10.4 | ARQ (async Redis queue) |
| GAP-11 | No asset CDN | Section 15 | S3-compatible storage backend |
| GAP-12 | `print()` logging | Section 21 | `structlog` structured JSON logging |
| GAP-13 | Hardcoded business metrics | Section 16.2 | Configurable `BusinessMetricsConfig` |
| GAP-14 | Code duplication in pipeline | Section 10.2 | Extracted `_process_product()` method |
| GAP-15 | HTTP session per request | Section 9.4 | Session-per-service with cleanup |
| GAP-16 | No agent orchestration | Section 4 | RuFlo integration (D-001) |
| GAP-17 | No agent governance | Section 5 | AgentSentry integration (D-002) |
| GAP-18 | Singleton config anti-pattern | Section 20 | FastAPI dependency injection |
| GAP-19 | Import inside function body | Section 23.2 | Move to top-level imports |
| GAP-20 | No file upload validation | Section 17.2 | Extension whitelist, max size 10MB |

---

*End of Specification*
