# Model Reference

**Version:** 0.9.4

## Models in Group: `Core`

### `parameter.Parameter`

Base model for agent parameters that defines configuration and metadata.

Parameters can be environment variables, secrets, or regular configuration values
that are used by agents during execution. The Supervaize platform uses this
model to manage parameter definitions and values.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the parameter, as used in the agent code |
| `description` | `str` | `None` | — | The description of the parameter, used in the Supervaize UI |
| `is_environment` | `bool` | False | Whether the parameter is set as an environment variable |
| `value` | `str` | `None` | — | The value of the parameter - provided by the Supervaize platform |
| `is_secret` | `bool` | False | Whether the parameter is a secret - hidden from the user in the Supervaize UI |
| `is_required` | `bool` | False | Whether the parameter is required, used in the Supervaize UI |

### `parameter.ParameterModel`

Base model for agent parameters that defines configuration and metadata.

Parameters can be environment variables, secrets, or regular configuration values
that are used by agents during execution. The Supervaize platform uses this
model to manage parameter definitions and values.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the parameter, as used in the agent code |
| `description` | `str` | `None` | — | The description of the parameter, used in the Supervaize UI |
| `is_environment` | `bool` | False | Whether the parameter is set as an environment variable |
| `value` | `str` | `None` | — | The value of the parameter - provided by the Supervaize platform |
| `is_secret` | `bool` | False | Whether the parameter is a secret - hidden from the user in the Supervaize UI |
| `is_required` | `bool` | False | Whether the parameter is required, used in the Supervaize UI |
