# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities through GitHub's private vulnerability reporting:
<https://github.com/supervaize/supervaizer/security/advisories/new>

Do not report security issues in public issues, discussions, or pull requests.

We will acknowledge receipt within 72 hours and provide an initial assessment within 7 days.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.19.x  | ✅        |
| < 0.19  | ❌        |

## Supply-chain posture

This repository implements the following controls:

- Branch protection via GitHub rulesets on `main` (enforced on admins)
- Required CI status checks before merge
- Secret scanning with push protection
- Dependabot security updates with a cooldown window on new releases
- `uv sync --frozen` enforced in CI (lockfile cannot silently change)
- Trusted Publishing (OIDC) for PyPI releases — no long-lived publish tokens
- Required reviewer approval on the `pypi` environment before publish secrets are exposed
- Third-party GitHub Actions pinned to commit SHAs
- OSV-Scanner in CI (daily + on every PR targeting `main` or `develop`) against the OSV.dev malicious package index

If you observe a deviation from this posture, please report it via the private channel above.
