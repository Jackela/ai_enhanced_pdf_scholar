# Project Context

## Purpose
AI Enhanced PDF Scholar provides an end-to-end research workspace that ingests PDF libraries, indexes them with LlamaIndex, and exposes conversational + retrieval workflows through a single `/api` FastAPI service and a React front end. The goal is to streamline academic reading: upload PDFs, search semantically, ask RAG questions, and track document insights with strong observability.

## Tech Stack
- **Backend:** Python 3.11+, FastAPI, Async SQL repository layer, LlamaIndex, Redis (optional) for caching
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, React Query, Jest/RTL for tests
- **Persistence:** SQLite for local/dev, PostgreSQL for production, Vector indexes stored on disk
- **AI/RAG:** Google Gemini via `google-generativeai`, multiple LlamaIndex modules, PyMuPDF for parsing
- **Ops/Tooling:** Docker, GitHub Actions, Prometheus metrics, OpenSpec for change proposals, Black/isort/Ruff/mypy, ESLint/Prettier

## Project Conventions

### Code Style
- Python formatted with Black (line length 88) and imports sorted via isort; Ruff enforces lint rules; mypy runs in strict-ish mode (no implicit Optional, disallow Any generics).
- TypeScript/React code follows ESLint + Prettier defaults with functional components and hooks; prefer explicit prop interfaces and React Testing Library patterns.
- Docstrings and inline comments explain non-obvious business logic; API/request/response models live under `backend/api` with pydantic v2 typing.

### Architecture Patterns
- Service-layered FastAPI app: `backend/api` handles transport, `backend/services` hosts business logic, and `src/repositories` encapsulate DB access using a lightweight repository pattern over `DatabaseConnection`.
- RAG pipeline split into ingestion (document import, hashing, metadata), vector indexing, and query execution (llama-index executors + Gemini LLMs).
- Caching uses a multi-layer strategy (in-memory, Redis, optional CDN) orchestrated by `IntegratedCacheManager`, with ML-assisted predictions when scikit-learn is available.
- Observability is first-class: Prometheus metrics, structured logging, metrics collector background jobs, and rate-limit/security middleware are always wired.

### Testing Strategy
- Backend: `pytest` with async support, coverage reporting, targeted contract suites (`pytest -q` for smoke, `pytest --maxfail=1` in CI). Fixtures spin up temporary SQLite DBs; long-running integration tests are opt-in.
- Frontend: `npm run test -- --run` executes Jest/React Testing Library suites (e.g., `LibraryViewPagination.test.tsx`). Prefer component-level tests over snapshot-only assertions.
- Wrapper scripts (`start_api_server.py`, `start_frontend_dev.py`) plus `verify_*` scripts are used for local validation; CI mirrors the documented commands.

### Git Workflow
- GitHub Flow: work happens on short-lived feature branches off `v2.0-refactor`/`main`, merged via PR after review.
- Conventional Commits drive history (`feat:`, `fix:`, `docs:` etc.) and changelog automation.
- Significant behavior changes must go through OpenSpec proposals (scaffold under `openspec/changes/<change-id>`), validated with `openspec validate --strict` before implementation.
- Every code change requires updating the relevant docs (`PROJECT_DOCS.md`, `API_ENDPOINTS.md`, etc.) per CLAUDE instructions.

## Domain Context
The product targets researchers and knowledge workers managing large PDF corpora. Key flows: uploading academic papers, extracting metadata/pages, deduplicating via hashes, running semantic/RAG queries, and monitoring system health (caching, metrics, rate limits). The UI must feel like a library browser + chat assistant combo, while backend focuses on correctness and traceability (logs, metrics, document tags, cache statistics).

## Important Constraints
- Documentation parity: any API, architecture, or workflow change must update the corresponding Markdown references and OpenSpec specs.
- No silent dependency failures—optional components (Redis, scikit-learn, file_type column) need graceful fallbacks with actionable logs.
- Security defaults: CORS whitelist, security headers, rate limiting, and request validation stay enabled even in dev; changes require explicit review.
- Tests must be deterministic (SQLite in-memory by default) and avoid calling external AI/LLM services during CI; use stubs/mocks.
- AI usage must route through approved providers (Gemini) with keys loaded from `.env`; never hardcode secrets.

## External Dependencies
- Google Gemini API (LLM + embeddings) accessed via `google-generativeai` and `llama-index-*` integrations.
- Redis (local or managed) for distributed caching/ratelimiting; optional but supported in config.
- Prometheus-compatible scraping via `prometheus_client`; dashboards consume `/metrics`.
- PyMuPDF for PDF parsing, numpy/scikit-learn for cache ML, psutil for system metrics, and Playwright for any future E2E testing (in `requirements-test`).
