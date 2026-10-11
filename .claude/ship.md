# Ship profile: supervaizer

- Branches: `develop` → `main`. Feature and fix PRs target `develop` and are squash-merged.
- Command: `just ship <patch|minor|major>`. It runs `just precommit`, creates `release/<part>-<timestamp>` from `origin/main`, merges `origin/develop` with `--no-ff`, pushes, and opens the PR to `main`. CI bumps the version after the merge, not the ship PR.
- Merge rule: merge commit. The subject must carry the bump token, or CI publishes without a bump:
  `gh pr merge <N> --merge --subject "[MINOR] chore: merge develop to main (#<N>)"`
- Release notes: `docs/CHANGELOG.md` `Unreleased`. `bump-my-version` in CI rotates it to `## [X.Y.Z] - <UTC date>`. `just ship-reconcile` copies that section into the GitHub release.
- Deploys to: PyPI through `.github/workflows/publish-pypi.yml`, on every push to `main`. The `publish` job waits for the GitHub Environment `pypi` (reviewer `alain-sv`, environment id `8053067545`).
- Live check:
  - `https://pypi.org/pypi/supervaizer/X.Y.Z/json` lists the wheel and the sdist.
  - Tag `vX.Y.Z` is on the `main` head, and `gh api repos/supervaize/supervaizer/releases/latest` returns it.
  - Clean install: `uv run --no-project --refresh --with 'supervaizer==X.Y.Z' python -c "import supervaizer.__version__ as v; print(v.VERSION)"`.
- Back-merge: `just ship-reconcile`. It waits for PyPI, merges `origin/main` into a new `chore/sync-main-vX.Y.Z` branch cut from `origin/develop`, opens a PR to `develop`, and rewrites the release notes. Merge that PR with a merge commit, not a squash: `gh pr merge <N> --merge`. Never push `develop` directly: `develop` requires PRs, and AGENTS.md forbids a ruleset or protection bypass, even for an admin.

## Rules

- Run `just ship` and `just ship-reconcile` only in a detached worktree, never in the GitButler checkout. Both recipes switch branches.
  1. `git worktree add --detach <scratchpad>/ship origin/develop`
  2. `cd <scratchpad>/ship && uv sync --frozen --extra dev`
  3. After the back-merge PR merges: `git worktree remove --force <scratchpad>/ship`, `git branch -D release/<part>-<timestamp> chore/sync-main-vX.Y.Z`, then `but pull` in the main checkout.
- Before the ship: the `develop` head is green on `Python package` and on `Security scan`. The security scan is a separate workflow, and publish does not wait for it.
- Before the PyPI approval: `gh api repos/supervaize/supervaizer/actions/runs/<id> --jq .head_commit.message` contains the bump token, and the `ci` job is green. Approve only when Alain allowed it for this release.
- Never re-run `publish-pypi` after the `chore(release): vX.Y.Z` commit is on `main`. Any other push to `main` also starts a publish.

## Known failures

| Symptom | Fix |
| --- | --- |
| `pre-commit` fails with hundreds of Ruff findings after a Ruff bump | The Ruff default rule set changed. Fix it in a PR to `develop` before the ship (1.7.0: #123, then #133). |
| `Security scan` red on `develop` (OSV on `uv.lock`) | `uv lock --upgrade-package <pkg>`, PR to `develop` (1.8.0: #135). |
| `ccd_pr get_status` shows pending or zero checks | The app cache lags. Read `gh pr checks <N>` once. |
| Clean install says the version does not exist right after the publish | PyPI simple-index lag. Retry after about 2 minutes. |
| Changelog date is one day before the local date | CI uses the UTC date. No action. |
| Push output says `Bypassed rule violations for refs/heads/develop` | A direct push used an admin bypass, which AGENTS.md forbids. Use the back-merge PR (1.7.0 and 1.8.0 were pushed this way before PR #137). |
