# Atlas20 API Security Operations

## Production Deployment Notes

Atlas20 uses in-process SlowAPI rate limiting. The configured API limits apply per API process, so running `N` uvicorn workers multiplies the effective advertised cap by `N`.

For shared production enforcement, place the API behind nginx, Cloudflare, or another edge proxy that applies rate limits before requests reach individual uvicorn workers.

Track a future migration to Redis-backed SlowAPI storage via `storage_uri` when the API needs shared limiter state inside the application layer.

## Protected Route Authentication

Protected routes include mutating endpoints and report downloads. They accept either `X-API-Key` when `ATLAS20_API_KEYS` is configured, or `Authorization: Bearer <jwt>` when `ATLAS20_JWT_AUTH_ENABLED=true`.

The JWT hook validates local HS256 bearer tokens with `ATLAS20_JWT_SECRET_KEY` or `ATLAS20_SECRET_KEY`, requires an `exp` claim, and enforces `ATLAS20_JWT_ISSUER` / `ATLAS20_JWT_AUDIENCE` when those settings are present. Treat this as the production integration hook for an upstream OAuth/OIDC provider or trusted reverse proxy; full JWKS/RS256 provider discovery is still an external edge concern. Token segments must be canonical unpadded base64url; a token with stray characters, padding, or non-zero trailing bits is rejected rather than decoded leniently. A token is never accepted when the signing key is empty.

With `ATLAS20_ENV=prod` the API refuses to start unless:

- `ATLAS20_SECRET_KEY` is set, non-empty, and not the dev default;
- with JWT auth enabled, the signing key (`ATLAS20_JWT_SECRET_KEY`, or `ATLAS20_SECRET_KEY` when that is unset) is at least 32 characters;
- every `ATLAS20_API_KEYS` entry is at least 32 characters.

Generate keys with `openssl rand -hex 32`. Secret settings are held as `SecretStr` and settings validation errors omit their input, so startup failures do not print secrets.

## Rate Limiting Keys

Mutation rate limits are bucketed by the authenticated principal: `client-<hash>` for an API key, `jwt-<hash>` for a bearer token's issuer and subject. Requests without valid credentials share the client address bucket. Raw `X-API-Key` or `Authorization` text never becomes a limiter key. It therefore never appears in slowapi's 429 warning log, and changing junk headers or re-encoding a token does not open a fresh bucket. `POST /api/strategy-lab/batches` queues up to 24 runs per call and is limited to 1 per minute.

## Backtest Presets

A backtest preset must be a runnable `config/*.yaml` preset (not a shared file such as `sectors.yaml`) or a strategy name defined by `config/base.yaml`, which is what `/api/options` offers. Internal run kinds such as `universe_refresh` are reserved: a backtest with that preset gets a 422 from `POST /api/backtests/run` and `POST /api/strategy-lab/batches`, so it can never be queued as a real data refresh. Strategy Lab also rejects unknown presets with a 422.

## Docker Compose

`docker-compose.yml` publishes the backend (`8000`), worker metrics (`8001`), and web (`5173`) ports on `127.0.0.1` only, and refuses to start unless `ATLAS20_API_KEYS` is set (see the README quickstart). The published web image embeds no API key: `VITE_ATLAS20_API_KEY` is read at build time and `apps/web/Dockerfile` does not accept it as a build argument yet. Until it does, console actions that call protected routes return 401 under Compose. Anything that injects the key for the console (a build argument or the nginx proxy) makes the web port a credential. Keep that port on loopback or behind an authenticating proxy.

The worker and web services wait for the backend container to start, not for it to be healthy, because `/readyz` depends on data freshness that only the worker can restore.

## MVP GET Route Exposure

Most GET routes remain unauthenticated in the MVP API. In production, bind the API to localhost/private networks or place it behind an authenticated reverse proxy before exposing it outside the host.

## MVP Unauthenticated Endpoints

The MVP intentionally exposes `/healthz`, `/readyz`, and `/metrics` without application authentication so local process managers, load balancers, and Prometheus scrapers can probe the service. Production deployments must keep these endpoints on localhost/private networks or protect them with a reverse-proxy allow-list before external exposure.
