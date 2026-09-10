# 10 — Maintenance & Roadmap (Post-v1.0)

Goal: keep the deployed app healthy, dependencies current, and the backlog moving without letting the repo rot.

## 10.1 Recurring Cadence

| Cadence | Task |
|---------|------|
| Every merge | CI green on `main`; Pages redeployed automatically |
| Weekly (15 min) | Triage open issues; delete merged branches; review Dependabot PRs; skim Pages URL still works |
| Monthly (30 min) | Update vendored headers if security-relevant (httplib/json/doctest) with `chore(deps)` commits; re-run benchmarks; refresh README screenshots |
| Per quarter | Review roadmap below; cut a minor release if enough `feat`s accumulated |

## 10.2 Versioning & Releases After v1.0

- PATCH (`v1.0.1`): fixes only → tag + release within a day of merging the fix.
- MINOR (`v1.1.0`): new backward-compatible features (anything from backlog marked Should/Could).
- MAJOR: reserved for contract breaks (API shape changes) — unlikely; avoid.
- Maintain `CHANGELOG.md` ("Keep a Changelog" format) generated from release notes; the conventional-commit log makes this near-automatic.

## 10.3 Issue Templates

`.github/ISSUE_TEMPLATE/bug_report.md`: expected vs actual, browser/OS, dataset date affected, console/network screenshot.
`feature_request.md`: problem statement, proposed behavior, willing-to-implement checkbox.
Label scheme: `bug`, `enhancement`, `good first issue`, `area:core|server|wasm|frontend|ci`, `blocked`.

## 10.4 Backlog (prioritized)

| Priority | Item | Notes |
|----------|------|-------|
| High | Multi-pair comparison chart | 2–3 pairs vs base on one axes (PRD Could-have) |
| High | PWA offline mode | manifest + service worker caching wasm/csv; big UX win for a static app |
| Medium | Cryptocurrency columns | Extend schema + normalizer; rate engine unchanged |
| Medium | Inflation adjustment | CPI CSV second dataset; stats engine gains `realRate()` |
| Medium | i18n | Extract UI strings; `Intl` already handles numbers/dates |
| Low | Custom domain | doc 09 §9.5 |
| Low | Server-side rate refresh action | Optional scheduled job regenerating CSV — only if a license-safe source is found |

Each backlog item starts life as an issue → branch → PR using the standard flow (doc 08).

## 10.5 Health Monitoring (zero-cost)

- README badges: CI workflow status, latest release version, live-site link.
- GitHub Insights → Traffic (views/clones over 14 days) — enough signal for a portfolio project.
- UptimeRobot (free) pinging the Pages URL weekly if you want downtime alerts.
- Watch for silent breakage class specific to this stack: **dataset staleness** (data ends at last Kaggle update — surface `dateMax` prominently in the header badge so users always see coverage; consider a tiny "data as of" footer note).

## 10.6 Dependency Update Procedure (vendored C++)

```bash
# example: bump httplib
curl -L -o server/third_party/httplib.h https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.16.0/httplib.h
ctest … && scripts/smoke_api.sh …        # prove nothing broke
git commit -m "chore(deps): bump cpp-httplib 0.15.3 -> 0.16.0"
```

Update the pins table in [doc 01](01-setup-and-prerequisites.md) §1.5 in the same commit — docs and code move together.

## 10.7 Definition of "Healthy Repo" (audit quarterly)

- [ ] `main` green; Pages live; release notes current
- [ ] No stale branches (> 30 days)
- [ ] All issues labeled; none older than 6 months unanswered
- [ ] Docs match reality (pins, endpoints, structure)
- [ ] Benchmarks recorded and within 20% of previous release
- [ ] LICENSE + CREDITS still accurate

## ✅ You Are Done When…

The public URL works for a stranger on their phone, `main` is green, `v1.0.0` is released, and this checklist passes. Then pick the first backlog item and repeat the whole loop — branch → PR → deploy.
