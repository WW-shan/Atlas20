# Atlas20 API Security Operations

## Production Deployment Notes

Atlas20 uses in-process SlowAPI rate limiting. The configured API limits apply per API process, so running `N` uvicorn workers multiplies the effective advertised cap by `N`.

For shared production enforcement, place the API behind nginx, Cloudflare, or another edge proxy that applies rate limits before requests reach individual uvicorn workers.

Track a future migration to Redis-backed SlowAPI storage via `storage_uri` when the API needs shared limiter state inside the application layer.

## Protected Route Authentication

Protected routes include mutating endpoints and report downloads. They accept either `X-API-Key` when `ATLAS20_API_KEYS` is configured, or `Authorization: Bearer <jwt>` when `ATLAS20_JWT_AUTH_ENABLED=true`.

The JWT hook validates local HS256 bearer tokens with `ATLAS20_JWT_SECRET_KEY` or `ATLAS20_SECRET_KEY`, requires an `exp` claim, and enforces `ATLAS20_JWT_ISSUER` / `ATLAS20_JWT_AUDIENCE` when those settings are present. Treat this as the production integration hook for an upstream OAuth/OIDC provider or trusted reverse proxy; full JWKS/RS256 provider discovery is still an external edge concern.

## MVP GET Route Exposure

Most GET routes remain unauthenticated in the MVP API. In production, bind the API to localhost/private networks or place it behind an authenticated reverse proxy before exposing it outside the host.

## MVP Unauthenticated Endpoints

The MVP intentionally exposes `/healthz`, `/readyz`, and `/metrics` without application authentication so local process managers, load balancers, and Prometheus scrapers can probe the service. Production deployments must keep these endpoints on localhost/private networks or protect them with a reverse-proxy allow-list before external exposure.
