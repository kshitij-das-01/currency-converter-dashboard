# 09 — Deployment: Public Link on GitHub Pages (+ Optional Server Path)

Goal: produce the shareable URL **`https://<user>.github.io/currency-converter-dashboard/`** where anyone can use the app, deployed automatically on every merge to `main`.

**Architecture recap:** GitHub Pages serves static files only, so production uses the **C++→WebAssembly** target (doc 05). The native REST server (doc 04) remains the local-dev/API path and has an optional cloud deployment (§9.4).

## 9.1 One-Time Pages Enablement

Repo → **Settings → Pages → Build and deployment → Source: "GitHub Actions"**. That's all — the workflow below does the rest.

> Free personal accounts require the repo to be **public** for Pages. Verify dataset licensing allows this (or ship sample data + self-download instructions).

## 9.2 Deploy Workflow (`.github/workflows/deploy-pages.yml`)

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write          # required for OIDC Pages deploy

concurrency:
  group: pages
  cancel-in-progress: true

env:
  EM_VERSION: 3.1.61       # must match doc 01 pin

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      # --- Native side: build server, boot it, run smoke + parity gates ---
      - name: Build native server
        run: |
          cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
          cmake --build build -j

      - name: Start server & run smoke suite
        run: |
          ./build/server/currency_server --port 8080 --data data/sample_rates.csv &
          sleep 1
          ./scripts/smoke_api.sh http://localhost:8080

      # --- WASM side ---
      - name: Cache emsdk
        uses: actions/cache@v4
        with:
          path: ~/emsdk
          key: emsdk-${{ env.EM_VERSION }}

      - name: Setup Emscripten
        uses: mymindstorm/setup-emsdk@v14
        with:
          version: ${{ env.EM_VERSION }}
          actions-cache-folder: emsdk-cache

      - name: Build WASM module
        run: |
          emcmake cmake -S . -B build-wasm -DCMAKE_BUILD_TYPE=Release \
                 -DBUILD_SERVER=OFF -DBUILD_TESTS=OFF
          cmake --build build-wasm -j

      - name: Run WASM↔REST parity gate
        run: node scripts/parity_test.mjs   # seeds point at localhost:8080 (still up)

      # --- Assemble static site ---
      - name: Assemble site
        run: |
          mkdir -p dist
          cp -r frontend/* dist/
          mkdir -p dist/wasm dist/data
          cp build-wasm/wasm/currency_core.js build-wasm/wasm/currency_core.wasm dist/wasm/
          cp data/exchange_rates.csv dist/data/ || cp data/sample_rates.csv dist/data/

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with: { path: dist }

      - name: Deploy
        id: deployment
        uses: actions/deploy-pages@v4
```

CI workflow (`.github/workflows/ci.yml`) is the same minus assembly/deploy: native build → ctest → smoke suite, plus macos matrix leg. Keep them consistent.

**Mode flag:** the deploy step ensures `frontend/js/config.js` has `MODE:'wasm'` (it's the committed default; add a sed guard if you ever flip it for dev).

## 9.3 Post-Deploy Verification

1. Open the Pages URL in a private window (cold cache).
2. Header badge shows real dataset range → WASM loaded + CSV fetched successfully.
3. Convert USD→EUR = expected value; run one trend range; export CSV.
4. DevTools console clean; Network tab shows `currency_core.wasm` served as `application/wasm`.
5. Share the link. 🎉

Common first-deploy failures:

| Symptom | Cause / fix |
|---------|-------------|
| 404 on `.wasm` | Artifacts not copied into `dist/wasm/` — check assemble step |
| `CurrencyCore is not defined` | Script tag missing/order wrong in wasm mode |
| Blank page, MIME error for js/wasm | Serving via `file://` — always verify over HTTP(S) |
| Parity job fails in CI only | Server still parsing sample CSV while seeds expect full dataset — align seed fixture |
| Pages didn't trigger | Settings→Pages source not set to "GitHub Actions", or workflow lacks `permissions` block |

## 9.4 Optional Path B — Hosted Native Server (Render.com)

For demonstrating the REST API publicly. Not required for the product (Pages path already serves users), and free tiers have cold starts (~30–60 s first hit).

`Dockerfile` (repo root):

```dockerfile
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y build-essential cmake && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY core/ core/  && COPY server/ server/ && COPY CMakeLists.txt .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF \
 && cmake --build build -j

FROM ubuntu:24.04
COPY --from=build /src/build/server/currency_server /usr/local/bin/currency_server
COPY frontend/ /app/frontend/
COPY data/ /app/data/
WORKDIR /app
ENV PORT=8080
EXPOSE 8080
CMD ["currency_server", "--port", "8080", "--data", "/app/data/exchange_rates.csv", "--static", "/app/frontend"]
```

`render.yaml`:

```yaml
services:
  - type: web
    name: currency-dashboard-api
    runtime: docker
    plan: free
```

If you use Path B for the UI too, point `config.js` `API_BASE` at the Render URL and enable the CORS headers block in `api_routes.cpp` (httplib `set_default_headers`). Otherwise leave Path B as an API demo only.

## 9.5 Custom Domain (optional, later)

Settings → Pages → Custom domain → add `dashboard.yourdomain.dev`, DNS `CNAME` → `<user>.github.io`, enforce HTTPS. Add a `CNAME` file to `dist/` in the assemble step if used.

## ✅ Exit Checklist

- [ ] Merge to `main` produced a green deploy run and live URL
- [ ] Cold-cache private-window walkthrough passes (§9.3)
- [ ] Badges in README: CI status + live link
- [ ] Tagged `v1.0.0` + GitHub Release published (doc 08 §8.4)
- [ ] (Optional) Path B service deployed and documented in README as API demo
