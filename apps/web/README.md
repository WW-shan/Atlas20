# Atlas20 Web Console

Desktop-first React/Vite console for the Atlas20 research framework.

## Development

Start the Python API in one terminal:

```bash
python scripts/run_api.py
```

Start the web app in another terminal:

```bash
npm --prefix apps/web install
npm --prefix apps/web run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Verification

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
```
