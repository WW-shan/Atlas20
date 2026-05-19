# Batch 7 Persistence Execution Plan

1. Add persistence dependencies, settings, `_time.utc_now()`, SQLModel models, and Alembic baseline migration.
2. Add repository modules for runs, reports, idempotency keys, and key-value settings.
3. Convert run-related services and routes to use `Session` plus repository injection.
4. Add seed and backup CLIs with module entry points and operations backup documentation.
5. Add `db_session` test fixture, update existing API service/route tests, and add eight `test_db_*.py` files.
6. Run staged backend validation after models, repositories, services, and CLIs; then run final backend and frontend acceptance.
