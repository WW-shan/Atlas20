# Atlas20 API Security Operations

## Production Deployment Notes

Atlas20 uses in-process SlowAPI rate limiting. The configured API limits apply per API process, so running `N` uvicorn workers multiplies the effective advertised cap by `N`.

For shared production enforcement, place the API behind nginx, Cloudflare, or another edge proxy that applies rate limits before requests reach individual uvicorn workers.

Track a future migration to Redis-backed SlowAPI storage via `storage_uri` when the API needs shared limiter state inside the application layer.

## MVP GET Route Exposure

GET routes are not auth-protected in the MVP API. In production, bind the API to localhost only, or put it behind an authenticated reverse proxy such as nginx with basic auth before exposing it outside the host.
