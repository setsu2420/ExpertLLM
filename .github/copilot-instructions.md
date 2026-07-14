# Copilot Instructions for ExpertLLM-V3

These instructions make AI coding agents productive quickly in this project. Follow the service boundaries and conventions below to avoid breaking flows.

# Copilot Instructions — ExpertLLM

These notes help AI coding agents become productive quickly in this repository. Focus on the files and patterns listed below — they encode the project's architecture, runtime expectations, and conventions.

## Quick summary
- Framework: Flask + Flask-SocketIO. HTTP + realtime (rooms per user major).
- Persistence: MySQL via SQLAlchemy (`models/`). Use `db_service.py` as the single DB API.
- Cache/pubsub: Redis via `utils/redis_client.py` (used for public chat list + pub/sub forwarder).
- Metrics: Prometheus endpoint at `/metrics`, helpers in `services/metrics.py`.

## Key files to read first
- [app.py](app.py): app bootstrap, Socket.IO connect flow, startup tasks (DB→Redis sync, pub/sub forwarder).
- [db_service.py](db_service.py): canonical DB access — sessions, turns, threads, public messages. All DB logic should go here.
- services/ (e.g. `chat_service.py`, `llm_service.py`, `runtime_service.py`): business logic, LLM integration, background tasks.
- routes/ (e.g. `public_routes.py`, `user_routes.py`, `auth_routes.py`, `llm_chat_routes.py`): endpoint-level orchestration — should call services/db_service rather than raw DB access.
- [utils/redis_client.py](utils/redis_client.py): get_redis(), JSON helpers, session token helpers.

## Important architecture & data flows (concrete)
- Chat flow: client POST → route in `llm_chat_routes` → session lock (`chat_service`) → `db_service.upsert_chat_turn()` + `db_service.append_thread_message()` → call model via `llm_service` → `chat_service.save_assistant_message()` / `db_service.set_record_turn_response()` to persist.
- Public chat: `routes/public_routes.py` uses Redis list+hash for today's messages. Fallback to `db_service.list_public_messages()` when cache misses. On create/vote it updates DB, updates Redis hash, and publishes to Redis channel for forwarder.
- History: `db_service.load_history_summaries()` and `load_history_detail()` produce the payload consumed by `/user/history`. `load_history_detail()` has logic to reorder `selected_models` using `Turn.model_order` — keep this when changing response shape.

## Project-specific conventions
- Central DB API: prefer `db_service.py` for any DB change. Avoid direct `db.session` in routes or services unless extending `db_service` intentionally.
- Multi-model support: messages and turns are model-agnostic; new model providers only need a unique `model_key` and integration in `services/llm_service.py`.
- Locks: `chat_service` exposes session-level locks used around turn creation and model calls. Respect these to avoid race conditions.
- Time/ISO: many functions return both human strings and `*_iso` UTC strings that end with `Z`. When adding timestamps follow this pattern.
- Redis keys: public list & hash prefixes are configured in `config.py`. `public_routes.py` shows the exact LRU/trim + TTL logic — mimic it if you change caching behavior.

## Developer workflows & commands
- Run locally (dev):
  - python app.py
  - Uses Flask threading mode for Socket.IO (dev). The app disables reloader on startup tasks.
- Docker / production: `docker-compose.yml` is provided. The recommended production command for the container is:
  - `gunicorn -k eventlet -w 1 -b 0.0.0.0:7100 app:app`
- Prometheus / Grafana: Prometheus config is in `prometheus.yml`; dashboard in `docs/grafana-dashboard.json`.

## Logging & observability notes
- `utils/logging_config.py` configures JSON logging to stdout; note it forces a minimum level to WARNING for root logger — access logs are emitted via the returned access logger.
- Metrics are recorded via `services/metrics.py`. Use provided helpers (e.g., `metrics.record_db_query()`) when adding DB calls.

## How to add a new LLM provider (example)
1. Implement call logic in `services/llm_service.py` (add `call_llm` or `call_llm_stream`).
2. Use a consistent `model_key` string (e.g., "my_provider").
3. Persist assistant output via `db_service.add_turn_message()` or `db_service.set_record_turn_response()` and keep `selected_models`/`model_order` updated via `upsert_chat_turn()` / `set_turn_order()`.

## Where to make changes safely
- For DB schema changes: modify `models/` and ensure `init_app(app)` and migrations (not present here) are considered.
- For request/response shape: update corresponding route and the `db_service` serializer used by front-end (`user.js` and templates expect certain fields like `created_at_iso`).

## Quick checklist for AI edits
- Prefer changing code in `services/` or `db_service.py` over `routes/` when altering business logic.
- Update metrics when adding DB/LLM operations.
- Preserve Redis cache semantics (list/hashes/trim/TTL) when editing public chat code.

---
If anything here is unclear or you want me to expand a section (e.g., show a concrete example of adding a new model provider), tell me which part and I'll iterate.

## Recent Project Notes (Feb 2026)

- Database / Docker:
  - The `docker-compose.yml` uses the official `mysql` image and will automatically create the database and user when the MySQL data volume is empty (via `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`).
  - The application (`app` service) runs `db.create_all()` on startup by default (see `app.py`), which creates SQLAlchemy model tables unless `DISABLE_APP_BOOTSTRAP=1` is set in the environment.
  - If you need custom SQL initialization, place SQL files into `/docker-entrypoint-initdb.d/` by mounting them into the MySQL container (only executed on first init).

- Registration / Users:
  - The `users` model was updated: `user_id` (phone number) is used as the identifier. Code and templates now reference `user_id` instead of `phone`.
  - Registration UI is a multi-step form at `templates/registration.html` (new behaviors: job→school/company branching, phone=`user_id`, optional student-card upload).
  - Frontend enhancements: `static/enhanced_style.css` contains the new UI styles (prefixed with `enh-` to avoid collisions), and `templates/registration.html` uses an `inert` polyfill for accessible step hiding.
  - The registration frontend now submits via AJAX and displays a confirmation modal (`showConfirmModal`) on success/failure; short messages use `showTopMessage(msg, kind)`.
  - The job list source is `static/assets/job.json` and is loaded on the registration page — ensure this file exists when testing.

- Accessibility & JS changes:
  - Steps are hidden using `aria-hidden` + `inert` and `safeFocusMove()` is used to avoid hiding an element that currently has focus.
  - Button click handlers were hardened (use `closest('button')`) and icons set to `pointer-events:none` so clicks on children register on the button.

These notes are intentionally short — if you want them converted into a longer developer onboarding section (with examples and commands), tell me which areas to expand.
