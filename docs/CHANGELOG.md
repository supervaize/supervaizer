# Supervaizer Changelog

All notable changes to this project will be documented in this file.

> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Parameter Validation System**: Added comprehensive parameter validation for job creation with clean error messages
  - New `validate_parameters()` method in `ParametersSetup` class for type checking and validation
  - New `/validate-parameters` endpoint for pre-job parameter validation
  - Enhanced job start endpoints with parameter validation before execution
  - Support for validating both job fields and encrypted agent parameters
  - Clean error messages with specific details about invalid parameter types and missing required parameters

### Fixed

- Execution of `supervaizer start` was not maintaining the _main_ namespace so the fastapi server was never starting. Replaced execution by sub-process.
- Type of agent.choice. #TODO: test and decide which to keep (list[str] or list [tuple[str,str]])
- When supervisor_account is provided, A2A endpoints are automatically activated, because Supervaize needs to be able to trigger the healthchecks. -`export_openapi.py` tool to generate openapi.json (for docusaurus documentation) - automation in docusaurus to do.

### Changed

- **Job Start Endpoints**: Enhanced with parameter validation to prevent jobs from starting with incorrect parameters
  - `/jobs` endpoint now validates parameters before starting jobs
  - Custom method endpoints now include parameter validation
  - Returns HTTP 400 with detailed validation errors instead of failing during execution
  - Improved error handling for encrypted parameter decryption failures

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 284   |
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
