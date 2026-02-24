# Branching and versions

We use **numbered branches** for versions:

- **`main`** — Development. Latest code and in-progress work.
- **`v1`** — First major version (1.x). Stable release branch for version 1.
- **`v1.1`, `v1.2`, …** — Minor upgrades under v1. Create from `v1` (or merge `main` into a new branch) when releasing 1.1, 1.2, etc.
- **`v2`** — Next major version. Create from `main` when starting the 2.x line.
- **`v2.1`, `v2.2`, …** — Minor upgrades under v2.

## Summary

| Branch   | Meaning                    |
|----------|----------------------------|
| `main`   | Development (current)      |
| `v1`     | Release branch for 1.x     |
| `v1.1`   | Minor release 1.1          |
| `v1.2`   | Minor release 1.2          |
| `v2`     | Next major (2.x)           |
| `v2.1`   | Minor release 2.1          |

## Tags

We can tag specific commits for releases, e.g.:

- `v1.0.0` — First release of 1.x (on branch `v1`)
- `v1.1.0` — Release 1.1 (on branch `v1.1` or `v1`)
- `v2.0.0` — First release of 2.x (on branch `v2`)

## Workflow

1. **Day-to-day:** Work on `main`; merge PRs into `main`.
2. **Minor release (e.g. 1.1):** From `v1`, create branch `v1.1`, cherry-pick or merge the changes you want, tag `v1.1.0`, push.
3. **Major release (e.g. 2.0):** When starting 2.x, create branch `v2` from `main`, tag `v2.0.0` when ready, push.
