# Supervaizer Changelog

All notable changes to this project will be documented in this file.

> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
>
> | Emoji Legend |                        |               |                |
> | ------------ | ---------------------- | ------------- | -------------- |
> | 🌅 Template  | 🏹 Service             | 👔 Model      | 👓 Views       |
> | 🐛 Bug       | 🛣️ Infrastructure/CICD | 🔌 API        | ⏱️ Celery Task |
> | 💼 Admin     | 📖 Documentation       | 📰 Events     | 🥇 Performance |
> | 🧪 Tests     | 🧑‍🎨 UI/Style            | 🎼 Controller |                |

## [Unreleased]

### Added

- Data persistence with tinyDB
- Admin UI with fastAdmin
- Dynamic content on:
  - Server page
  - Agent
  - Jobs
  - Cases
- Improved test coverage : accounts, admin/routes,
- Add persisted data to job status check.
- Paramater.to_dict : override to avoid storing secrets.

### Changed

- Removed Case Nodes

  | Status        | Count |
  | ------------- | ----- |
  | 🤔 Skipped    | 6     |
  | ☑️ Deselected | 0     |
  | ⚠️ Failed     | 0     |
  | ✅ Passed     | 281   |

Test Coverage : 81%
