# 08 — Git Workflow & Repository Maintenance

Goal: professional, low-friction Git habits that keep `main` releasable at all times and make history readable for reviewers.

## 8.1 Branching Model (trunk-based)

- `main` is always shippable and protected (doc 02 §2.5).
- All work happens on short-lived branches, merged via PR (no direct pushes):

| Prefix | Use | Example |
|--------|-----|---------|
| `feat/` | new functionality | `feat/wasm-parity-harness` |
| `fix/` | bug fixes | `fix/moving-average-off-by-one` |
| `docs/` | documentation only | `docs/prd-updates` |
| `chore/` | tooling, CI, deps | `chore/pin-emsdk-ci` |
| `test/` | test-only changes | `test/parser-fuzz-cases` |

Lifecycle:

```bash
git switch main && git pull origin main
git switch -c feat/converter-flow
# …work, commit…
git fetch origin && git rebase origin/main     # keep linear history
git push -u origin feat/converter-flow
gh pr create --fill                            # or via web UI
# merge with "Squash and merge"; delete branch
```

Keep branches ≤ ~2 days old / small diffs. Long-running ideas go into GitHub Issues instead of stale branches.

## 8.2 Conventional Commits (enforced by habit + review)

Format: `type(scope): imperative summary` — lowercase, ≤ 72 chars, optional body explaining *why*.

| Type | When |
|------|------|
| `feat` | user-visible feature (triggers minor bump) |
| `fix` | bug fix (patch bump) |
| `docs` | markdown/docs only |
| `test` | tests only |
| `chore` | build, CI, deps, housekeeping |
| `refactor` | no behavior change |
| `perf` | performance improvement |

Examples:

```
feat(core): add moving average engine with running-sum window
fix(server): map EmptyRange to HTTP 404 not 500
docs(implementation): document render blueprint env vars
chore(ci): cache emsdk 3.1.61 between runs
```

A commit should compile and pass tests. If it doesn't, finish the work before committing (or use `WIP:` prefix and rebase-clean before opening the PR).

## 8.3 Pull Request Discipline

PR template (save as `.github/PULL_REQUEST_TEMPLATE.md`):

```markdown
## What & why
<!-- 2–4 sentences -->

## How tested
- [ ] ctest green locally
- [ ] smoke_api.sh green (if API touched)
- [ ] parity_test.mjs green (if serializer/core touched)
- [ ] Manual UI walkthrough (if frontend touched)

## Screenshots
<!-- UI changes only -->

## Benchmarks (release PRs only)
<parse ms / p95 ms / lighthouse>
```

Self-review before requesting merge: read your own diff once end-to-end. Squash-merge keeps `main` linear; the squash title becomes the conventional commit.

## 8.4 Tags & Releases (SemVer)

```
v0.x.y  pre-release development
v1.0.0  first public Pages deployment
vMAJOR.MINOR.PATCH  thereafter
```

Cutting a release:

```bash
git switch main && git pull
git tag -a v1.0.0 -m "First public release"
git push origin v1.0.0
gh release create v1.0.0 --generate-notes
```

Optionally attach native binaries (`currency_server-macos.tar.gz`, `-linux`) built from `cmake --install`. Release notes auto-generate from conventional commits — which is why commit discipline matters.

## 8.5 Dependabot (`.github/dependabot.yml`)

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

(Vendored C++ headers are updated manually + deliberately, with a `chore(deps)` commit noting the new pinned version.)

## 8.6 Hygiene Rules

- **Never** commit: secrets (none exist in this project — keep it that way), build outputs, `frontend/wasm/` artifacts, raw Kaggle zips.
- Dataset size discipline: `data/exchange_rates.csv` ≤ 10 MB; if a future dataset exceeds 50 MB use Git LFS (`git lfs track "*.csv"`), but prefer trimming.
- Resolve every CI failure before merging; red `main` is an incident, fix-forward immediately.
- Rebase feature branches onto `main` rather than merging `main` into them.
- Weekly (doc 10 cadence): review open issues, close stale branches, check Dependabot PRs.

## ✅ Exit Checklist

- [ ] Every change so far went through branch → PR → squash-merge
- [ ] Commit log reads like a changelog (conventional, scoped)
- [ ] Branch protection + auto-delete active; zero stale branches
- [ ] Dependabot enabled; first weekly triage done
- [ ] First annotated tag exists (`v0.1.0` at M1 completion is fine)
