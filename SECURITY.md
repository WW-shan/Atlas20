# Security Policy

Atlas20 is designed as a local research tool. The FastAPI service exposes
backtest execution endpoints without authentication and should not be placed on
the public internet as-is.

## Supported Versions

Security fixes target the current `main` branch.

## Reporting Issues

Open a private advisory or contact the repository maintainer if GitHub private
advisories are not available.

## Deployment Notes

- Run the API on localhost for development.
- Add authentication and rate limiting before exposing the API to a network.
- Review generated report paths before allowing multi-user write access.
- Never store provider API keys or private trading credentials in the repo.
