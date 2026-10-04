# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities through GitHub's private vulnerability reporting:
<https://github.com/supervaize/supervaizer/security/advisories/new>

Do not report security issues in public issues, discussions, or pull requests.

We will acknowledge receipt within 72 hours and provide an initial assessment within 7 days.

## Supported versions

Only the latest 1.x release receives security fixes.

| Version | Supported |
|---------|-----------|
| 1.x (latest) | ✅   |
| < 1.0   | ❌        |

## Supply-chain posture

This repository implements the following controls:

- Branch rulesets on the default branch (`develop`) block deletion and force-pushes; `main` receives only release PRs created by `just ship`
- CI (lint, type check, tests, OSV-Scanner) runs on pull requests
- Secret scanning with push protection
- Dependabot security updates, with a cooldown window on new releases for version updates
- `uv sync --frozen` in the test and lint jobs (lockfile cannot silently change)
- Trusted Publishing (OIDC) for PyPI releases — no long-lived publish tokens
- Required reviewer approval on the `pypi` GitHub environment before the publish job runs
- Third-party GitHub Actions pinned to commit SHAs
- OSV-Scanner in CI (daily, plus every push and PR on `main` and `develop`) against the OSV.dev vulnerability database
- Tag protection ruleset on `v*` release tags

If you observe a deviation from this posture, please report it via the private channel above.
