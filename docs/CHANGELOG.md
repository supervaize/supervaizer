# Supervaizer Changelog

All notable changes to this project will be documented in this file.

> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [0.9.9] - 2025-01-17

### Added

- **🚀 Cloud Deployment CLI** - Complete automated deployment system for Supervaizer agents
  - Full implementation of [RFC-001: Cloud Deployment CLI](docs/rfc/001-cloud-deployment-cli.md)
  - Support for three major cloud platforms:
    - **Google Cloud Run** with Artifact Registry and Secret Manager
    - **AWS App Runner** with ECR and Secrets Manager
    - **DigitalOcean App Platform**
  - New deployment commands:
    - `supervaizer deploy plan` - Preview deployment actions before applying
    - `supervaizer deploy up` - Deploy to cloud platform with automated build, push, and verification
    - `supervaizer deploy down` - Tear down deployment and clean up resources
    - `supervaizer deploy status` - Check deployment status and health
    - `supervaizer deploy local` - Local Docker testing with docker-compose
    - `supervaizer deploy clean` - Clean up deployment artifacts and state
  - **Automated Docker Workflow**: Build → Push → Deploy → Verify
  - **Secret Management**: Secure handling of API keys and RSA keys via cloud provider secret stores
  - **Health Verification**: Automatic health checks at `/.well-known/health` endpoint
  - **Idempotent Deployments**: Safe create/update operations with rollback on failure
  - **Local Testing**: Full Docker Compose environment for pre-deployment testing
  - See [Local Testing Documentation](docs/LOCAL_TESTING.md) for details

- **Agent Instructions Template** - New HTML page served by FastAPI for Supervaize integration instructions
  - Accessible at `/admin/supervaize-instructions`
  - Provides step-by-step setup guide for agents

- **Version Check Utility** - Automatic check for latest Supervaizer version
  - Helps users stay up-to-date with latest features and fixes
  - Located in `supervaizer.utils.version_check`

- **Enhanced Admin Interface**
  - New agents listing page with grid view
  - Improved agent detail views
  - Better navigation and UI consistency

### Changed

- **📦 Dependency Optimization** - Cloud SDKs moved to optional dependencies
  - Base package size significantly reduced
  - Cloud deployment dependencies now optional: `pip install supervaizer[deploy]`
  - Optional `deploy` group includes: boto3, docker, google-cloud-artifact-registry, google-cloud-run, google-cloud-secret-manager, psutil
  - Removed unused `pymongo` dependency
  - Updated dependency versions for better compatibility

- **Improved Error Handling** - Enhanced API error responses with better context

- **Documentation Updates**
  - Added comprehensive deployment documentation
  - Updated model reference documentation
  - Improved README with deployment examples

### Fixed

- API documentation errors corrected
- Improved type hints for `agent_parameters` and `case_ids` in job.py
- Health logging optimized in A2A and ACP routes

### Unit Tests Results

| Status     | Count  |
| ---------- | ------ |
| ✅ Passed  | 420    |
| 🤔 Skipped | 6      |
| 🔴 Failed  | 0      |
| ⏱️ in      | 82.63s |

### Migration Notes

- If you need deployment features, install with: `pip install supervaizer[deploy]`
- For development, install with: `pip install supervaizer[dev,deploy]`
- No breaking changes to existing APIs or functionality

## [0.9.8]

### Added

- **Parameter Validation System**: Added comprehensive parameter validation for job creation with clean error messages
  - New `validate_parameters()` method in `ParametersSetup` class for agent parameter validation
  - New `validate_method_fields()` method in `AgentMethod` class for job field validation
  - Two separate validation endpoints for different validation needs:
    - `/validate-agent-parameters` - Validate agent configuration parameters (secrets, API keys, etc.)
    - `/validate-method-fields` - Validate job input fields against method definitions
  - Support for validating both job fields and encrypted agent parameters
  - Clean error messages with specific details about invalid parameter types and missing required parameters

### Fixed

- Execution of `supervaizer start` was not maintaining the _main_ namespace so the fastapi server was never starting. Replaced execution by sub-process.
- Type of agent.choice. #TODO: test and decide which to keep (list[str] or list [tuple[str,str]])
- When supervisor_account is provided, A2A endpoints are automatically activated, because Supervaize needs to be able to trigger the healthchecks. -`export_openapi.py` tool to generate openapi.json (for docusaurus documentation) - automation in docusaurus to do.

### Changed

- **Parameter Validation System**: Refactored to provide separate validation endpoints for different concerns

  - **Agent Parameters**: Now validated separately through `/validate-agent-parameters` endpoint
  - **Method Fields**: Now validated separately through `/validate-method-fields` endpoint
  - **Clean Architecture**: Removed legacy endpoint for cleaner, more focused API design
  - **Code Deduplication**: Eliminated redundant validation code in job start endpoints
  - **Clearer Separation**: Agent configuration validation vs. job input validation are now distinct operations

- pytest does not run with coverage by default (change in pyproject.toml)

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 308   |
| 🤔 Skipped | 6     |

## [0.9.6]

- Public release to Pypi
- Fixed the gihut workflows
- Improve README.md

## [0.9.5]

### Fixed

- Setup : missing `py.typed` in pyproject
- clarified public_url (replaced registration_host by public_url)
- changed "supervaizer install" to "supervaizer scaffold"

### Added

- `gen_model_docs.py`: tool for documentation generation - see disclaimer

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 277   |
| 🤔 Skipped | 6     |

## [0.9.4]

### Added

- CICD : release, deploy
- `gen_model_docs.py` : to generate the documentation of the models.

### Changed

- Moved "example" to `src/supervaizer`
- Improved and Moved some documentation to `docs`
- Added `python-package.yml` github action, triggered on push / PR of "develop" branch

## [0.9.3]

### Added

- Data persistence with tinyDB
- Admin UI with fastAdmin
- Dynamic content on:
  - Server page
  - Agent
  - Jobs
  - Cases
- Add persisted data to job status check.

### Changed

- Paramater.to_dict : override to avoid storing secrets.
- Removed Case Nodes
- Improved test coverage : accounts, admin/routes,

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| 🤔 Skipped | 6     |
| ⚠️ Failed  | 0     |
| ✅ Passed  | 281   |

Test Coverage : [![Test Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

> | Emoji Legend |                        |               |
> | ------------ | ---------------------- | ------------- |
> | 🌅 Template  | 🏹 Service             | 👔 Models     |
> | 🐛 Bug       | 🛣️ Infrastructure/CICD | 🔌 API        |
> | 💼 Admin     | 📖 Documentation       | 📰 Events     |
> | 🧪 Tests     | 🧑‍🎨 UI/Style            | 🎼 Controller |
