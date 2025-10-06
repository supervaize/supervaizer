# RFC-001: Cloud Deployment CLI

**Status:** Revised Draft (v1 – Fully Automated)

## Abstract

This RFC specifies a new `supervaizer deploy` CLI that **fully automates** deployment of Supervaizer agents to **GCP Cloud Run**, **AWS App Runner**, and **DigitalOcean App Platform**. The command builds and pushes a Docker image, provisions/updates the service, creates or updates secrets, sets `SUPERVAIZER_PUBLIC_URL`, verifies health, and prints final endpoints.

## Motivation

Manual deployment requires juggling Docker, registries, provider CLIs, secrets, and health checks. This is slow and error‑prone. A single automated command reduces time‑to‑value, standardizes best practices (health checks, secrets, idempotent updates, rollbacks), and ensures the server’s own assumptions (`/.well-known/health`, `X-API-Key`, `SUPERVAIZER_PUBLIC_URL`) are satisfied out of the box.

## Goals (v1)

- One command to **plan → apply → verify** for Cloud Run, App Runner, and DO App Platform.
- Idempotent **create/update** with safe defaults and optional rollback.
- Standardized environment/secret contract for the Server.
- Minimal assumptions: users authenticate with cloud CLIs; we orchestrate with those CLIs.

## Non‑Goals (v1)

- Kubernetes/Helm, Azure, custom VPC/LB/DNS/TLS provisioning, CI/CD pipelines.

---

## CLI Design

### Commands

```
supervaizer deploy plan   [OPTIONS]
supervaizer deploy up     [OPTIONS]
supervaizer deploy down   [OPTIONS]
supervaizer deploy status [OPTIONS]
```

### Common Options

```
--platform [cloud-run|aws-app-runner|do-app-platform]  (required)
--name TEXT                     # service base name; default from folder
--env [dev|staging|prod]        # default: dev
--project-id TEXT               # GCP project / AWS account / DO project (if used)
--region TEXT                   # provider region (e.g., europe-west1, eu-west-1, fra)
--image TEXT                    # registry/repo:tag; if omitted, computed from git SHA
--port INTEGER                  # default: 8000
--generate-api-key              # create secure API key if missing
--rsa-key-path PATH             # optional PEM to persist
--generate-rsa                  # generate RSA private key secret if none given
--yes                           # non-interactive
--no-rollback                   # keep failed revision
--timeout INTEGER               # seconds for deploy+verify; sensible default
--verbose                       # show underlying CLI output (secrets masked)
```

### Behavior

- **plan** – Resolve names, detect existing resources, show **CREATE/UPDATE/NOOP** actions.
- **up** – Build → Push → Secrets upsert → Service create/update → Set `SUPERVAIZER_PUBLIC_URL` → Verify health → Output.
- **down** – Destroy service and **tool-owned** secrets; keep images by default.
- **status** – Print URL, health state, image digest, revision, and key env vars.

### Idempotency

- Service name is deterministic: `${name}-${env}`.
- If service exists, perform **rolling update** only when image digest or env/secrets changed.
- On verify failure: **automatic rollback** to last healthy revision (unless `--no-rollback`).

---

## Environment & Secrets Contract (standardized)

Set for all platforms:

- `SUPERVAIZER_ENVIRONMENT` = `--env`
- `SUPERVAIZER_HOST=0.0.0.0`
- `SUPERVAIZER_PORT` = `--port`
- `SV_LOG_LEVEL=INFO` (default)
- `SUPERVAIZER_API_KEY` – stored in provider secret store (generated if `--generate-api-key`)
- **RSA** (choose one):
  - `SV_RSA_PRIVATE_KEY` (secret value), or
  - `SV_RSA_PRIVATE_KEY_PATH` (if platform supports volumes)

After provisioning, the CLI **reads the assigned URL** and sets:

- `SUPERVAIZER_PUBLIC_URL` = provider service URL (applied via a zero‑downtime update).

**Health check:** `/.well-known/health` (used for both liveness/readiness in v1).

**Note**: The current implementation provides both A2A (`/.well-known/health`) and ACP (`/agents/health`) health endpoints. The deployment CLI will use `/.well-known/health` as the primary health check endpoint for consistency with A2A protocol standards.

---

## Provider Workflows (Automated)

### GCP: Cloud Run

1. **Build & Push**: Local Docker build → Artifact Registry push (or `--use-cloud-build`).
2. **Secrets**: Create/Update Secret Manager entries for `SUPERVAIZER_API_KEY` and optional `SV_RSA_PRIVATE_KEY`.
3. **Deploy/Update**: `gcloud run deploy` with `--port`, env vars, `--set-secrets`, min instances=1, safe concurrency.
4. **Set Public URL**: Fetch service URL → update `SUPERVAIZER_PUBLIC_URL` via config update.
5. **Verify**: Poll `GET {url}/.well-known/health` until 200 or timeout.
6. **Output**: URL, `/docs` and `/redoc` links, revision, masked secret notes.

### AWS: App Runner (primary)

1. **ECR**: Ensure repo, login, build & push image.
2. **Secrets Manager**: Upsert `SUPERVAIZER_API_KEY` and optional `SV_RSA_PRIVATE_KEY`.
3. **Create/Update Service**: Port=8000, health path, env + secret refs.
4. **Set Public URL**: Read service URL → update env `SUPERVAIZER_PUBLIC_URL`.
5. **Verify** and **Output** as above.

### DigitalOcean: App Platform

1. **Registry**: Push image to DOCR (or external).
2. **App Spec**: Create or update `do-app-spec.yaml` programmatically with image, http_port=8000, health path, env & secret items.
3. **Apply**: `doctl apps create` (first run) or `doctl apps update` (subsequent).
4. **Set Public URL**: Read assigned URL → update env `SUPERVAIZER_PUBLIC_URL` and redeploy.
5. **Verify** and **Output**.

---

## Preflight Checks (fail-fast)

- Docker available and running.
- Provider CLIs authenticated & authorized:
  - **GCP**: `gcloud` with active project; Artifact Registry & Cloud Run APIs enabled.
  - **AWS**: `aws` with default profile/region; ECR & App Runner permissions.
  - **DO**: `doctl` authenticated with access to registry & App Platform.
- Confirms app port and health path; warns if server code deviates from defaults.
- Ensures no plaintext secrets will be written to the repo.
- Validates `supervaizer_control.py` exists and is properly configured.
- Checks for required environment variables and provides setup guidance.
- Verifies Dockerfile generation requirements (Python version, dependencies).
- Ensures `.deployment/` directory is properly gitignored.

---

## Generated/Updated Files

All deployment artifacts are stored under `.deployment/` directory (added to `.gitignore`):

- `.deployment/Dockerfile` (Python slim, EXPOSE 8000, `CMD ["python","-m","supervaizer.__main__"]`)
- `.deployment/.dockerignore` (excludes dev files, tests, docs)
- `.deployment/docker-compose.yml` (local dev/test; uses health check path)
- `.deployment/do-app-spec.yaml` (DigitalOcean App Platform)
- `.deployment/cloudbuild.yaml` (optional when `--use-cloud-build`)
- `.deployment/DEPLOY_AUTOMATION.md` (how to use the CLI, recover, rollback)
- `.deployment/state.json` (machine‑generated state: service IDs, URL, image digest, revision)
- `.deployment/config.yaml` (optional user configuration overrides)
- `.deployment/logs/` (deployment logs and debug information)

**Note**: The entire `.deployment/` directory is added to `.gitignore` to prevent accidental commits of deployment artifacts, secrets, and generated files.

---

## Acceptance Criteria

1. **Plan**: First run shows CREATE; subsequent runs show UPDATE/NOOP with correct diffs.
2. **Up**: Returns public URL; health passes within timeout; `SUPERVAIZER_PUBLIC_URL` is set and reflected in `/docs` links.
3. **Update**: Changing image/env results in a rolling update with no downtime.
4. **Rollback**: On failed verify, last healthy revision is restored (unless `--no-rollback`).
5. **Down**: Destroys service and tool‑owned secrets without orphaning provider resources.
6. **Health Check**: Service responds to `/.well-known/health` endpoint with 200 status.
7. **API Key**: Generated API key works for admin interface access.
8. **Environment**: All required environment variables are properly set.
9. **Idempotency**: Multiple runs of same command produce identical results.
10. **Error Handling**: Clear error messages with actionable recovery steps.

---

## Security & Logging

- Secrets never printed; values masked in logs.
- IAM scope guidance documented per provider.
- CLI logs actionable errors and underlying CLI output with `--verbose` (still masked).

---

## Implementation Notes

- Driver modules: `drivers/cloud_run.py`, `drivers/aws_app_runner.py`, `drivers/do_app_platform.py` implementing `plan()`, `up()`, `down()`, `status()`.
- Shared utilities: docker build/push, secret upsert, health verifier, state manager, name & tag resolver.
- Default image tag: git SHA; fallback `:latest`.

---

## Implementation Plan

### Phase 1: Core Infrastructure

**Goal**: Establish basic CLI structure and Docker support

**Tasks**:

1. **CLI Structure Setup**

   - Add `deploy` subcommand to existing CLI (`src/supervaizer/cli.py`)
   - Create `src/supervaizer/deploy/` module structure
   - Add Docker-related dependencies to `pyproject.toml`

2. **Docker Support**

   - Create `Dockerfile` generator (`src/supervaizer/deploy/docker.py`)
   - Create `.dockerignore` generator
   - Add `docker-compose.yml` generator for local testing
   - Implement image building and tagging logic
   - Generate all files under `.deployment/` directory

3. **State Management**

   - Create deployment state manager (`src/supervaizer/deploy/state.py`)
   - Implement `.deployment/state.json` persistence
   - Add state validation and migration logic
   - Create `.deployment/` directory structure and `.gitignore` entry

4. **Initial Testing**
   - Unit tests for CLI structure and Docker operations
   - Test Dockerfile generation and validation
   - Test state management and persistence
   - Integration tests with mock Docker API

**Dependencies**: None (builds on existing CLI)

### Phase 2: Provider Drivers

**Goal**: Implement core provider drivers

**Tasks**:

1. **GCP Cloud Run Driver** (`src/supervaizer/deploy/drivers/cloud_run.py`)

   - Artifact Registry integration
   - Secret Manager integration
   - Cloud Run service management
   - Health check verification

2. **AWS App Runner Driver** (`src/supervaizer/deploy/drivers/aws_app_runner.py`)

   - ECR integration
   - Secrets Manager integration
   - App Runner service management
   - Health check verification

3. **DigitalOcean App Platform Driver** (`src/supervaizer/deploy/drivers/do_app_platform.py`)

   - DOCR integration
   - App Platform service management
   - Health check verification

4. **Driver Testing**
   - Unit tests for each driver with mocked APIs
   - Test authentication and permission handling
   - Test resource creation, update, and deletion
   - Test error handling and edge cases
   - Integration tests with real provider APIs (dev accounts)

**Dependencies**: Phase 1 completion

### Phase 3: CLI Commands

**Goal**: Implement all CLI commands

**Tasks**:

1. **Plan Command** (`src/supervaizer/deploy/commands/plan.py`)

   - Resource detection and diff generation
   - Cost estimation (optional)
   - Dry-run validation

2. **Up Command** (`src/supervaizer/deploy/commands/up.py`)

   - Orchestrate build → push → deploy → verify workflow
   - Handle rollback on failure
   - Progress reporting with rich console

3. **Down Command** (`src/supervaizer/deploy/commands/down.py`)

   - Safe resource cleanup
   - Confirmation prompts
   - Resource dependency handling

4. **Status Command** (`src/supervaizer/deploy/commands/status.py`)

   - Service health reporting
   - Resource utilization metrics
   - Configuration validation

5. **Command Testing**
   - Unit tests for each command with mocked dependencies
   - Test command-line argument parsing and validation
   - Test workflow orchestration and error handling
   - Test progress reporting and user feedback
   - Integration tests with real deployments (dev environments)

**Dependencies**: Phase 2 completion

### Phase 4: Advanced Features

**Goal**: Add advanced deployment features

**Tasks**:

1. **Secret Management**

   - Secure secret generation and storage
   - Secret rotation support
   - Cross-environment secret sharing

2. **Health Verification**

   - Enhanced health check endpoints
   - Retry logic with exponential backoff
   - Detailed health reporting

3. **Rollback Support**
   - Automatic rollback on health check failure
   - Manual rollback to previous revisions
   - Rollback validation and testing

**Dependencies**: Phase 3 completion

### Phase 5: Testing & Documentation

**Goal**: Comprehensive testing and documentation

**Tasks**:

1. **Testing**

   - **Unit Testing**

     - Test all driver classes (`src/supervaizer/deploy/drivers/`)
     - Test all command implementations (`src/supervaizer/deploy/commands/`)
     - Test state management (`src/supervaizer/deploy/state.py`)
     - Test Docker operations (`src/supervaizer/deploy/docker.py`)
     - Test secret management (`src/supervaizer/deploy/secrets.py`)
     - Test health check utilities (`src/supervaizer/deploy/health.py`)
     - Achieve 90%+ code coverage

   - **Integration Testing**

     - Mock cloud provider APIs for all three platforms
     - Test complete deployment workflows (plan → up → status → down)
     - Test error handling and rollback scenarios
     - Test secret management across providers
     - Test state persistence and recovery

   - **End-to-End Testing**
     - Real deployments to dev environments for each provider
     - Test with actual `supervaizer_control.py` files
     - Validate health checks and API key functionality
     - Test rollback mechanisms with real failures
     - Performance testing (deployment time, resource usage)

2. **Documentation**
   - Update CLI documentation
   - Create deployment guides for each provider
   - Add troubleshooting guides
   - Update API documentation

**Dependencies**: Phase 4 completion

### Phase 6: Production Readiness

**Goal**: Production-ready release

**Tasks**:

1. **Security Audit**

   - Secret handling validation
   - Permission scope review
   - Security best practices implementation

2. **Performance Optimization**

   - Parallel deployment operations
   - Caching improvements
   - Resource cleanup optimization

3. **Release Preparation**

   - Version bumping and changelog
   - Release notes and migration guides
   - Community feedback integration

4. **Final Testing**
   - Full regression testing across all providers
   - Security testing and penetration testing
   - Load testing and performance validation
   - User acceptance testing with beta users
   - Documentation review and validation

**Dependencies**: Phase 5 completion

### Implementation Dependencies

**New Dependencies Required**:

```toml
# Add to pyproject.toml
dependencies = [
    # ... existing dependencies ...
    "docker>=7.0.0",           # Docker SDK for Python
    "boto3>=1.34.0",          # AWS SDK
    "google-cloud-run>=0.10.0", # GCP Cloud Run
    "google-cloud-secret-manager>=2.18.0", # GCP Secret Manager
    "google-cloud-artifact-registry>=1.8.0", # GCP Artifact Registry
    "digitalocean>=0.0.1",     # DigitalOcean API
]
```

**File Structure**:

```
src/supervaizer/deploy/
├── __init__.py
├── cli.py                 # Deploy CLI commands
├── state.py               # State management
├── docker.py              # Docker operations
├── health.py              # Health check utilities
├── secrets.py             # Secret management
├── drivers/
│   ├── __init__.py
│   ├── base.py            # Base driver interface
│   ├── cloud_run.py       # GCP Cloud Run
│   ├── aws_app_runner.py  # AWS App Runner
│   └── do_app_platform.py # DigitalOcean App Platform
└── commands/
    ├── __init__.py
    ├── plan.py
    ├── up.py
    ├── down.py
    └── status.py
```

## Future Enhancements

- ECS Fargate driver; Azure Container Apps/Instances.
- Separate `/ready` endpoint and richer probes.
- Canary/blue‑green and traffic splitting where supported.
- CI/CD templates (GitHub Actions) wiring `plan` on PRs and `up` on release tags.
