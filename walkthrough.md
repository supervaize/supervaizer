# Supervaizer Codebase Walkthrough

*2026-03-14T22:52:48Z by Showboat 0.6.1*
<!-- showboat-id: cff7c9b5-74ea-45ac-a1fd-c85a605f0f77 -->

## What is Supervaizer?

Supervaizer is a Python toolkit (v0.10.25, Python 3.12+) for building **controller servers** that manage AI agents. It bridges custom AI agent code with the Supervaize SaaS platform, providing:

- A FastAPI HTTP server that exposes standardized job/case APIs
- A state machine for tracking job and case lifecycles
- Agent-to-Agent (A2A) protocol discovery endpoints
- TinyDB-backed persistence (optional)
- RSA encryption for passing secrets to agents
- Cloud deployment automation (GCP, AWS, DigitalOcean)
- A web-based admin dashboard

The mental model: you write an agent function, Supervaizer wraps it in a server so the Supervaize platform (or any HTTP client) can start jobs, monitor progress, and receive results in a uniform way.

## Repository Layout

The entire library lives under `src/supervaizer/`. Here is the top-level shape:

```bash
find src/supervaizer -maxdepth 2 -name '*.py' | sort | grep -v __pycache__ | sed 's|src/supervaizer/||'
```

```output
__init__.py
__version__.py
account.py
account_service.py
admin/routes.py
agent.py
case.py
cli.py
common.py
deploy/__init__.py
deploy/cli.py
deploy/docker.py
deploy/driver_factory.py
deploy/health.py
deploy/state.py
deploy/utils.py
event.py
examples/controller_template.py
instructions.py
job.py
job_service.py
lifecycle.py
parameter.py
protocol/__init__.py
routes.py
server.py
server_utils.py
storage.py
telemetry.py
utils/__init__.py
utils/version_check.py
```

The files fall into these logical groups:

| Group | Files |
|---|---|
| **Core models** | `agent.py`, `job.py`, `case.py`, `parameter.py`, `common.py` |
| **Server/HTTP** | `server.py`, `routes.py`, `server_utils.py` |
| **Lifecycle** | `lifecycle.py`, `event.py`, `job_service.py` |
| **Persistence** | `storage.py` |
| **Platform integration** | `account.py`, `account_service.py` |
| **A2A protocol** | `protocol/a2a/model.py`, `protocol/a2a/routes.py` |
| **Admin UI** | `admin/routes.py`, `admin/templates/`, `admin/static/` |
| **CLI** | `cli.py`, `deploy/cli.py` |
| **Deployment** | `deploy/` (drivers for GCP, AWS, DO) |
| **Telemetry** | `telemetry.py` |

## Public API (`__init__.py`)

Before diving in, it helps to see what the library exports — these are the only names users touch directly.

```bash
grep -E '^from|^import' src/supervaizer/__init__.py | head -60
```

```output
from supervaizer import protocol
from supervaizer.account import Account
from supervaizer.agent import (
from supervaizer.case import (
from supervaizer.common import ApiError, ApiResult, ApiSuccess
from supervaizer.event import (
from supervaizer.job import Job, JobContext, JobInstructions, JobResponse, Jobs
from supervaizer.lifecycle import EntityEvents, EntityLifecycle, EntityStatus
from supervaizer.parameter import Parameter, ParametersSetup
from supervaizer.server import Server
from supervaizer.server_utils import ErrorResponse, ErrorType, create_error_response
from supervaizer.telemetry import (
```

---

## 1. Entry Point: The CLI (`cli.py`)

Users interact with Supervaizer through its CLI. The tool is built with [Typer](https://typer.tiangolo.com/). Let's read its structure:

```bash
grep -n 'def \|app\.' src/supervaizer/cli.py | head -40
```

```output
31:def _check_version() -> tuple[bool, str | None]:
43:def _display_version_info() -> None:
57:def _display_update_warning() -> None:
74:@app.callback(invoke_without_command=True)
75:def main_callback(
97:app.add_typer(
105:app.add_typer(scaffold_app, name="scaffold", invoke_without_command=True)
108:@app.command()
109:def start(
175:    def signal_handler(signum: int, frame: Any) -> None:
189:def _create_instructions_file(
225:@scaffold_app.callback(invoke_without_command=True)
226:def scaffold(
288:@scaffold_app.command(name="instructions")
289:def scaffold_instructions(
335:@scaffold_app.command(name="refresh-instructions")
336:def refresh_instructions(
```

Two Typer apps are created — `app` (root) and `scaffold_app` (subgroup). The `main_callback` runs on every invocation to display version warnings. The key commands are:

```bash
sed -n '108,180p' src/supervaizer/cli.py
```

```output
@app.command()
def start(
    public_url: Optional[str] = typer.Option(
        os.environ.get("SUPERVAIZER_PUBLIC_URL") or None,
        help="Public URL to use for inbound connections",
    ),
    host: str = typer.Option(
        os.environ.get("SUPERVAIZER_HOST", "0.0.0.0"), help="Host to bind the server to"
    ),
    port: int = typer.Option(
        int(os.environ.get("SUPERVAIZER_PORT") or "8000"),
        help="Port to bind the server to",
    ),
    log_level: str = typer.Option(
        os.environ.get("SUPERVAIZER_LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    ),
    debug: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_DEBUG") or "False").lower() == "true",
        help="Enable debug mode",
    ),
    reload: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_RELOAD") or "False").lower() == "true",
        help="Enable auto-reload",
    ),
    environment: str = typer.Option(
        os.environ.get("SUPERVAIZER_ENVIRONMENT", "dev"), help="Environment name"
    ),
    persist: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_PERSISTENCE") or "false").lower()
        in ("true", "1", "yes"),
        "--persist/--no-persist",
        help="Persist data to file (default: off; set for self-hosted, off for Vercel/serverless)",
    ),
    script_path: Optional[str] = typer.Argument(
        None,
        help="Path to the supervaizer_control.py script",
    ),
) -> None:
    """Start the Supervaizer Controller server."""
    if script_path is None:
        # Try to get from environment variable first, then default
        script_path = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    if not os.path.exists(script_path):
        console.print(f"[bold red]Error:[/] {script_path} not found")
        console.print("Run [bold]supervaizer scaffold[/] to create a default script")
        sys.exit(1)

    # Set environment variables for the server configuration
    os.environ["SUPERVAIZER_HOST"] = host
    os.environ["SUPERVAIZER_PORT"] = str(port)
    os.environ["SUPERVAIZER_ENVIRONMENT"] = environment
    os.environ["SUPERVAIZER_PERSISTENCE"] = str(persist).lower()
    os.environ["SUPERVAIZER_LOG_LEVEL"] = log_level
    os.environ["SUPERVAIZER_DEBUG"] = str(debug)
    os.environ["SUPERVAIZER_RELOAD"] = str(reload)
    if public_url is not None:
        os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url

    console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/]")
    console.print(f"Loading configuration from [bold]{script_path}[/]")

    # Execute the script in a new Python process with proper signal handling

    def signal_handler(signum: int, frame: Any) -> None:
        # Send the signal to the subprocess
        if "process" in globals():
            globals()["process"].terminate()
        sys.exit(0)

```

The `start` command stamps all settings into environment variables then spawns a subprocess running the user's `supervaizer_control.py` script. Every CLI option has a corresponding `SUPERVAIZER_*` environment variable, so Docker/cloud environments can configure the server without re-running the CLI.

The `scaffold` subcommand generates starter files:

```bash
sed -n '225,290p' src/supervaizer/cli.py
```

```output
@scaffold_app.callback(invoke_without_command=True)
def scaffold(
    ctx: typer.Context,
    output_path: str = typer.Option(
        os.environ.get("SUPERVAIZER_OUTPUT_PATH", "supervaizer_control.py"),
        help="Path to save the script",
    ),
    force: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_FORCE_INSTALL") or "False").lower() == "true",
        help="Overwrite existing file",
    ),
) -> None:
    """Create a draft supervaizer_control.py script and supervaize_instructions.html."""
    # Only run if no subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return
    # Check if file already exists
    if os.path.exists(output_path) and not force:
        console.print(f"[bold red]Error:[/] {output_path} already exists")
        console.print("Use [bold]--force[/] to overwrite it")
        sys.exit(1)

    # Get the path to the examples directory
    examples_dir = Path(__file__).parent / "examples"
    example_file = examples_dir / "controller_template.py"

    if not example_file.exists():
        console.print("[bold red]Error:[/] Example file not found")
        sys.exit(1)

    # Copy the example file to the output path
    shutil.copy(example_file, output_path)
    console.print(
        f"[bold green]Success:[/] Created an example file at [bold blue]{output_path}[/]"
    )

    # Create instructions file in the same directory (silently if it already exists)
    output_dir = Path(output_path).parent
    instructions_path = output_dir / "supervaize_instructions.html"
    instructions_existed = instructions_path.exists()
    _create_instructions_file(output_dir, force=force, silent=True)
    # Only show success message if we actually created the file (didn't exist before or force was used)
    if not instructions_existed or force:
        console.print(
            f"[bold green]Success:[/] Created instructions template at [bold blue]{instructions_path}[/]"
        )

    console.print(
        "1. Copy this file to [bold]supervaizer_control.py[/] and edit it to configure your agent(s)"
    )
    console.print(
        "2. Customize [bold]supervaize_instructions.html[/] to match your agent's documentation"
    )
    console.print(
        "3. (Optional) Get your API from [bold]supervaizer.com and setup your environment variables"
    )
    console.print(
        "4. Run [bold]supervaizer start[/] to start the supervaizer controller"
    )
    console.print("5. Open [bold]http://localhost:8000/docs[/] to explore the API")
    sys.exit(0)


@scaffold_app.command(name="instructions")
def scaffold_instructions(
    control_file: Optional[str] = typer.Option(
```

Scaffold simply copies `examples/controller_template.py` to `supervaizer_control.py` in the current directory — no magic, just a starter file.

---

## 2. The Controller Template (`examples/controller_template.py`)

This is what a user writes. It defines agents and launches the server:

```bash
cat src/supervaizer/examples/controller_template.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# This is an example file.
# It must be copied / renamed to supervaizer_control.py
# and edited to configure your agent(s)

import os
import shortuuid
from rich.console import Console

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    Parameter,
    ParametersSetup,
    Server,
)
from supervaizer.account import Account

# Create a console with default style set to yellow
console = Console(style="yellow")

# Public url of your hosted agent  (including port if needed)
# Use loca.lt or ngrok to get a public url during development.
# This can be setup from environment variables.
# SUPERVAIZER_HOST and SUPERVAIZER_PORT
DEV_PUBLIC_URL = "https://myagent-dev.loca.lt"
# Public url of your hosted agent
PROD_PUBLIC_URL = "https://myagent.cloud-hosting.net:8001"

# Define the parameters and secrets expected by the agent
agent_parameters: ParametersSetup | None = ParametersSetup.from_list([
    Parameter(
        name="OPEN_API_KEY",
        description="OpenAPI Key",
        is_environment=True,
        is_secret=True,
    ),
    Parameter(
        name="SERPER_API",
        description="Server API key updated",
        is_environment=True,
        is_secret=True,
    ),
    Parameter(
        name="COMPETITOR_SUMMARY_URL",
        description="Competitor Summary URL",
        is_environment=True,
        is_secret=False,
    ),
])

# Define the method used to start a job
job_start_method: AgentMethod = AgentMethod(
    name="start",  # This is required
    method="example_agent.example_synchronous_job_start",  # Path to the main function in dotted notation.
    is_async=False,  # Only use sync methods for the moment
    params={"action": "start"},  # If default parameters must be passed to the function.
    fields=[
        {
            "name": "Company to research",  # Field name - displayed in the UI
            "type": str,  # Python type of the field for pydantic validation - note , ChoiceField and MultipleChoiceField are a list[str]
            "field_type": "CharField",  # Field type for persistence.
            "description": "Company to research",  # Optional -  Description of the field - displayed in the UI
            "default": "Google",  # Optional - Default value for the field
            "required": True,  # Whether the field is required
        },
        {
            "name": "Max number of results",
            "type": int,
            "field_type": "IntegerField",
            "required": True,
        },
        {
            "name": "Subscribe to updates",
            "type": bool,
            "field_type": "BooleanField",
            "required": False,
        },
        {
            "name": "Type of research",
            "type": str,
            "field_type": "ChoiceField",
            "choices": [["A", "Advanced"], ["R", "Restricted"]],
            "widget": "RadioSelect",
            "required": True,
        },
        {
            "name": "Details of research",
            "type": str,
            "field_type": "CharField",
            "widget": "Textarea",
            "required": False,
        },
        {
            "name": "List of countries",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [
                ["PA", "Panama"],
                ["PG", "Papua New Guinea"],
                ["PY", "Paraguay"],
                ["PE", "Peru"],
                ["PH", "Philippines"],
                ["PN", "Pitcairn"],
                ["PL", "Poland"],
            ],
            "required": True,
        },
        {
            "name": "languages",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [["en", "English"], ["fr", "French"], ["es", "Spanish"]],
            "required": False,
        },
    ],
    description="Start the collection of new competitor summary",
)

job_stop_method: AgentMethod = AgentMethod(
    name="stop",
    method="control.stop",
    params={"action": "stop"},
    description="Stop the agent",
)
job_status_method: AgentMethod = AgentMethod(
    name="status",
    method="hello.mystatus",
    params={"status": "statusvalue"},
    description="Get the status of the agent",
)
custom_method: AgentMethod = AgentMethod(
    name="custom",
    method="control.custom",
    params={"action": "custom"},
    description="Custom method",
)

custom_method2: AgentMethod = AgentMethod(
    name="custom2",
    method="control.custom2",
    params={"action": "custom2"},
    description="Custom method",
)


agent_name = "competitor_summary"

# Define the Agent
agent: Agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(f"{agent_name}"),
    author="John Doe",  # Author of the agent
    developer="Developer",  # Developer of the controller integration
    maintainer="Ive Maintained",  # Maintainer of the integration
    editor="DevAiExperts",  # Editor (usually a company)
    version="1.3",  # Version string
    description="This is a test agent",
    tags=["testtag", "testtag2"],
    methods=AgentMethods(
        job_start=job_start_method,
        job_stop=job_stop_method,
        job_status=job_status_method,
        chat=None,
        custom={"custom1": custom_method, "custom2": custom_method2},
    ),
    parameters_setup=agent_parameters,
    instructions_path="supervaize_instructions.html",  # Path where instructions page is served
)

# For export purposes, use dummy values if environment variables are not set
account: Account = Account(
    workspace_id=os.getenv("SUPERVAIZE_WORKSPACE_ID") or "dummy_workspace_id",
    api_key=os.getenv("SUPERVAIZE_API_KEY") or "dummy_api_key",
    api_url=os.getenv("SUPERVAIZE_API_URL") or "https://app.supervaize.com",
)

# Define the supervaizer server capabilities
sv_server: Server = Server(
    agents=[agent],
    a2a_endpoints=True,  # Enable A2A endpoints
    supervisor_account=account,  # Account of the supervisor from Supervaize
)


if __name__ == "__main__":
    # Start the supervaize server
    sv_server.launch(log_level="DEBUG")
```

This is the entire user-facing configuration. Three steps:

1. **Parameters** — declare environment variables / secrets the agent needs (e.g. API keys).
2. **Methods** — declare callable functions using dotted-path strings (`module.function`).
3. **Server** — wire agents into a `Server` instance and call `server.launch()`.

---

## 3. Common Foundations (`common.py`)

Before examining the models, let's read the base classes everything inherits from:

```bash
sed -n '1,100p' src/supervaizer/common.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import base64
import json
import os
import traceback
from typing import Any, Callable, Dict, Optional, TypeVar

import demjson3
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger
from pydantic import BaseModel

log = logger.bind(module="supervaize")

T = TypeVar("T")


class SvBaseModel(BaseModel):
    """
    Base model for all Supervaize models.
    """

    @staticmethod
    def serialize_value(value: Any) -> Any:
        """Recursively serialize values, converting type objects and datetimes to strings."""
        from datetime import datetime

        if isinstance(value, type):
            # Convert type objects to their string name
            return value.__name__
        elif isinstance(value, datetime):
            # Convert datetime to ISO format string
            return value.isoformat()
        elif isinstance(value, dict):
            # Recursively process dictionaries
            return {k: SvBaseModel.serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            # Recursively process lists and tuples
            return [SvBaseModel.serialize_value(item) for item in value]
        else:
            # Return value as-is for other types
            return value

    @property
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.

        Note: Handles datetime serialization and type objects by converting them
        to their string representation.
        Tested in tests/test_common.test_sv_base_model_json_conversion
        """
        # Use mode="python" to avoid Pydantic's JSON serialization errors with type objects
        # Then post-process to handle type objects and datetimes
        data = self.model_dump(mode="python")
        return self.serialize_value(data)

    @property
    def to_json(self) -> str:
        return json.dumps(self.to_dict)


class ApiResult:
    def __init__(self, message: str, detail: Optional[Dict[str, Any]], code: str):
        self.message = message
        self.code = str(code)
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.json_return}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.message})"

    @property
    def dict(self) -> Dict[str, Any]:
        return {key: value for key, value in self.__dict__.items()}

    @property
    def json_return(self) -> str:
        return json.dumps(self.dict)


class ApiSuccess(ApiResult):
    """
    ApiSuccess is a class that extends ApiResult.
    It is used to return a success response from the API.

    If the detail is a string, it is decoded as a JSON object: Expects a JSON object with a
    key "object" and a value of the JSON object to return.
    If the detail is a dictionary, it is used as is.

```

```bash
sed -n '100,200p' src/supervaizer/common.py
```

```output


    Tested in tests/test_common.py
    """

    def __init__(
        self, message: str, detail: Optional[Dict[str, Any] | str], code: int = 200
    ):
        log_message = "✅ "
        if isinstance(detail, str):
            result = demjson3.decode(detail, return_errors=True)
            detail = {"object": result.object}
            id = result.object.get("id") or None
            if id is not None:
                log_message += f"{message} : {id}"
            else:
                log_message += f"{message}"
        else:
            id = None
            detail = detail
            log_message += f"{message}"

        super().__init__(
            message=message,
            detail=detail,
            code=str(code),
        )
        self.id: Optional[str] = id
        self.log_message = log_message
        log.debug(f"[API Success] {self.log_message}")


class ApiError(ApiResult):
    """
    ApiError is a class that extends ApiResult.
    It can be used to return an error response from the API.
    Note : not really useful for the moment, as API errors raise exception.

    Tested in tests/test_common.py
    """

    def __init__(
        self,
        message: str,
        code: str = "",
        detail: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        url: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, detail, code)
        self.exception = exception
        self.url = url
        self.payload = payload
        self.log_message = f"❌ {message} : {self.exception}"

    @property
    def dict(self) -> Dict[str, Any]:
        if self.exception:
            exception_dict: Dict[str, Any] = {
                "type": type(self.exception).__name__,
                "message": str(self.exception),
                "traceback": traceback.format_exc(),
                "attributes": {},
            }
            if (
                response := hasattr(self.exception, "response")
                and self.exception.response
            ):
                self.code = str(response.status_code) or ""

                try:
                    response_text = self.exception.response.text
                    exception_dict["response"] = json.loads(response_text)
                except json.JSONDecodeError:
                    pass
            for attr in dir(self.exception):
                try:
                    if (
                        not attr.startswith("__")
                        and not callable(attribute := getattr(self.exception, attr))
                        and getattr(self.exception, attr)
                    ):
                        try:
                            exception_dict["attributes"][attr] = json.loads(
                                str(attribute)
                            )
                        except json.JSONDecodeError:
                            pass
                except Exception:
                    pass

        result: Dict[str, Any] = {
            "message": self.message,
            "code": self.code,
            "url": self.url,
            "payload": self.payload,
            "detail": self.detail,
        }
        if self.exception:
            result["exception"] = exception_dict
```

Three building blocks from `common.py`:

- **`SvBaseModel`** — Pydantic `BaseModel` with a custom `serialize_value` that converts Python `type` objects and `datetime` instances to strings, enabling JSON-safe `to_dict`/`to_json` properties.
- **`ApiSuccess`** — wraps a success result; if `detail` is a JSON string it auto-decodes it and extracts the object id for logging.
- **`ApiError`** — wraps an exception with full traceback and HTTP response info for clean error reporting.
- **`encrypt_value` / `decrypt_value`** — RSA+AES hybrid encryption used to pass agent secrets securely (public key sent to platform, private key stays on server).

---

## 4. Parameter Management (`parameter.py`)

Parameters declare what environment variables/secrets an agent requires. Let's see the model:

```bash
grep -n 'class \|def \|is_environment\|is_secret\|set_value' src/supervaizer/parameter.py | head -40
```

```output
15:class ParameterAbstract(SvBaseModel):
31:    is_environment: bool = Field(
39:    is_secret: bool = Field(
53:            "is_environment": True,
54:            "is_secret": True,
60:class Parameter(ParameterAbstract):
62:    def to_dict(self) -> Dict[str, Any]:
67:        if self.is_secret:
72:    def registration_info(self) -> Dict[str, Any]:
76:            "is_environment": self.is_environment,
77:            "is_secret": self.is_secret,
81:    def set_value(self, value: str) -> None:
84:        Note that environment is updated ONLY if set_value is called explicitly.
88:        if self.is_environment:
92:class ParametersSetup(SvBaseModel):
118:    def from_list(
137:    def value(self, name: str) -> str | None:
145:    def registration_info(self) -> List[Dict[str, Any]]:
148:    def update_values_from_server(
167:                def_parameter.set_value(parameter["value"])
175:    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
203:        for param_name, param_def in self.definitions.items():
217:            param_def = self.definitions[param_name]
```

```bash
sed -n '60,100p' src/supervaizer/parameter.py
```

```output
class Parameter(ParameterAbstract):
    @property
    def to_dict(self) -> Dict[str, Any]:
        """
        Override the to_dict method to handle the value field.
        """
        data = super().to_dict
        if self.is_secret:
            data["value"] = "********"
        return data

    @property
    def registration_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "is_environment": self.is_environment,
            "is_secret": self.is_secret,
            "is_required": self.is_required,
        }

    def set_value(self, value: str) -> None:
        """
        Set the value of a parameter and update the environment variable if needed.
        Note that environment is updated ONLY if set_value is called explicitly.
        Tested in tests/test_parameter.py
        """
        self.value = value
        if self.is_environment:
            os.environ[self.name] = value


class ParametersSetup(SvBaseModel):
    """
    ParametersSetup model for the Supervaize Control API.

    This represents a collection of parameters that can be used by an agent.
    It contains a dictionary of parameters, where the key is the parameter name
    and the value is the parameter object.

    Example:
```

Key design: `Parameter.set_value()` stores the value AND pushes it to `os.environ` if `is_environment=True`. This means encrypted secrets arrive over HTTP, get decrypted by the server, and are silently injected as environment variables so agent code can use `os.getenv('OPENAI_API_KEY')` without any Supervaizer-specific code.

Secrets are redacted (`"value": "********"`) in any serialized output.

---

## 5. The Agent Model (`agent.py`)

The `Agent` class is the central registry entry. Here is its shape:

```bash
grep -n 'class \|def ' src/supervaizer/agent.py | head -50
```

```output
42:class FieldTypeEnum(str, Enum):
54:class AgentMethodField(BaseModel):
126:class AgentJobContextBase(BaseModel):
135:class AgentMethodAbstract(BaseModel):
221:class AgentMethod(AgentMethodAbstract):
223:    def fields_definitions(self) -> list[Dict[str, Any]]:
245:    def fields_annotations(self) -> type[BaseModel]:
247:        Creates and returns a dynamic Pydantic model class based on the field definitions.
298:    def validate_method_fields(self, job_fields: Dict[str, Any]) -> Dict[str, Any]:
339:            field_def = next((f for f in self.fields if f.name == field_name), None)
400:    def job_model(self) -> type[AgentJobContextBase]:
402:        Creates and returns a dynamic Pydantic model class combining job context and job fields.
419:    def registration_info(self) -> Dict[str, Any]:
433:class AgentMethodParams(BaseModel):
445:class AgentCustomMethodParams(AgentMethodParams):
449:class AgentMethodsAbstract(BaseModel):
459:    def validate_custom_method_keys(
483:class AgentMethods(AgentMethodsAbstract):
485:    def registration_info(self) -> Dict[str, Any]:
503:class AgentAbstract(SvBaseModel):
606:class Agent(AgentAbstract):
607:    def __init__(
680:    def __str__(self) -> str:
684:    def slug(self) -> str:
688:    def path(self) -> str:
692:    def registration_info(self) -> Dict[str, Any]:
718:    def update_agent_from_server(self, server: "Server") -> Optional["Agent"]:
777:    def update_parameters_from_server(
787:    def _execute(self, action: str, params: Dict[str, Any] = {}) -> JobResponse:
803:    def job_start(
913:    def job_stop(self, params: Dict[str, Any] = {}) -> Any:
919:    def job_status(self, params: Dict[str, Any] = {}) -> Any:
925:    def chat(self, context: str, message: str) -> Any:
933:    def custom_methods_names(self) -> list[str] | None:
939:class AgentResponse(BaseModel):
```

```bash
sed -n '221,310p' src/supervaizer/agent.py
```

```output
class AgentMethod(AgentMethodAbstract):
    @property
    def fields_definitions(self) -> list[Dict[str, Any]]:
        """
        Returns a list of the fields with the type key as a string
        Used for the API response.
        """
        if self.fields:
            result = []
            for field in self.fields:
                d = {k: v for k, v in field.__dict__.items() if k != "type"}
                # type as string
                type_val = field.type
                if hasattr(type_val, "__name__"):
                    d["type"] = type_val.__name__
                elif hasattr(type_val, "_name") and type_val._name:
                    d["type"] = type_val._name
                else:
                    d["type"] = str(type_val)
                result.append(d)
            return result
        return []

    @property
    def fields_annotations(self) -> type[BaseModel]:
        """
        Creates and returns a dynamic Pydantic model class based on the field definitions.
        """
        if not self.fields:
            return type("EmptyFieldsModel", (BaseModel,), {"to_dict": lambda self: {}})

        field_annotations = {}
        for field in self.fields:
            field_name = field.name
            field_type = field.type

            # Convert Python types to proper typing annotations
            if field_type is str:
                annotation_type: type = str
            elif field_type is int:
                annotation_type = int
            elif field_type is bool:
                annotation_type = bool
            elif field_type is list:
                annotation_type = list
            elif field_type is dict:
                annotation_type = dict
            elif field_type is float:
                annotation_type = float
            elif hasattr(field_type, "__origin__") and field_type.__origin__ is list:
                # Handle generic list types like list[str]
                annotation_type = list
            elif hasattr(field_type, "__origin__") and field_type.__origin__ is dict:
                # Handle generic dict types like dict[str, Any]
                annotation_type = dict
            else:
                # Default to Any for unknown types
                annotation_type = Any

            # Make field optional if not required
            field_annotations[field_name] = (
                annotation_type if field.required else Optional[annotation_type]
            )

        # Create the dynamic model with proper module information
        model_dict = {
            "__module__": "supervaizer.agent",
            "__annotations__": field_annotations,
            "to_dict": lambda self: {
                k: getattr(self, k)
                for k in field_annotations.keys()
                if hasattr(self, k)
            },
        }

        return type("DynamicFieldsModel", (BaseModel,), model_dict)

    def validate_method_fields(self, job_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Validate job fields against the method's field definitions.

        Args:
            job_fields: Dictionary of field names and values to validate

        Returns:
            Dictionary with validation results:
            - "valid": bool - whether all fields are valid
            - "errors": List[str] - list of validation error messages
            - "invalid_fields": Dict[str, str] - field name to error message mapping
        """
        if self.fields is None:
```

`AgentMethod` has two clever dynamic-class features:

- **`fields_annotations`** builds a Pydantic `BaseModel` at runtime from the field list. This lets FastAPI validate incoming job payloads without knowing field names at import time.
- **`fields_definitions`** converts `type` objects (e.g. `str`, `int`) to their string names for JSON serialisation.

Now the `Agent._execute` method — the bridge between Supervaizer and user code:

```bash
sed -n '787,870p' src/supervaizer/agent.py
```

```output
    def _execute(self, action: str, params: Dict[str, Any] = {}) -> JobResponse:
        """
        Execute an agent method and return a JobResponse
        """

        module_name, func_name = action.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        log.debug(f"[Agent method] {method.__name__} with params {params}")
        result = method(**params)
        if not isinstance(result, JobResponse):
            raise TypeError(
                f"Method {func_name} must return a JobResponse object, got {type(result).__name__}"
            )
        return result

    def job_start(
        self,
        job: Job,
        job_fields: Dict[str, Any],
        context: JobContext,
        server: "Server",
        method_name: str = "job_start",
    ) -> Job:
        """Execute the agent's start method in the background

        Args:
            job (Job): The job instance to execute
            job_fields (dict): The job-specific parameters
            context (SupervaizeContextModel): The context of the job
        Returns:
            Job: The updated job instance
        """
        if not self.methods:
            raise ValueError("Agent methods not defined")
        log.debug(
            f"[Agent job_start] Run <{self.methods.job_start.method}> - Job <{job.id}>"
        )
        event = JobStartConfirmationEvent(
            job=job,
            account=server.supervisor_account,
        )
        if server.supervisor_account is not None:
            server.supervisor_account.send_event(sender=job, event=event)
        else:
            log.warning(
                f"[Agent job_start] No supervisor account defined for server, skipping event send for job {job.id}"
            )

        # Mark job as in progress when execution starts
        job.add_response(
            JobResponse(
                job_id=job.id,
                status=EntityStatus.IN_PROGRESS,
                message="Starting job execution",
                payload=None,
            )
        )

        # Execute the method
        if method_name == "job_start":
            action = self.methods.job_start
        else:
            if not self.methods.custom:
                raise ValueError(f"Custom method {method_name} not found")
            action = self.methods.custom[method_name]

        action_method = action.method
        method_params = action.params or {}
        params = (
            method_params
            | {"fields": job_fields}
            | {"context": context}
            | {"agent_parameters": job.agent_parameters}
        )
        log.debug(
            f"[Agent job_start] action_method : {action_method} - params : {params}"
        )
        try:
            if self.methods.job_start.is_async:
                # TODO: Implement async job execution & test
                raise NotImplementedError(
                    "[Agent job_start] Async job execution is not implemented"
                )
```

`_execute` is the dynamic dispatch core: it splits the dotted-path string (`module.function`), imports the module at runtime with `__import__`, calls the function, and enforces that the return value is a `JobResponse`.

`job_start` wraps execution in three steps:
1. Fire a `JobStartConfirmationEvent` to the platform (non-blocking).
2. Mark the job `IN_PROGRESS`.
3. Call `_execute` with merged params: `method_params | {fields, context, agent_parameters}`.

---

## 6. The Lifecycle State Machine (`lifecycle.py`)

Every Job and Case flows through a strict state machine:

```bash
cat src/supervaizer/lifecycle.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Protocol, TypeVar

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class EntityStatus(str, Enum):
    """Base status enum for workflow entities."""

    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    CANCELLING = "cancelling"
    AWAITING = "awaiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @staticmethod
    def status_stopped() -> list["EntityStatus"]:
        return [
            EntityStatus.STOPPED,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
            EntityStatus.COMPLETED,
        ]

    @property
    def is_stopped(self) -> bool:
        return self in EntityStatus.status_stopped()

    @staticmethod
    def status_running() -> list["EntityStatus"]:
        return [
            EntityStatus.IN_PROGRESS,
            EntityStatus.CANCELLING,
            EntityStatus.AWAITING,
        ]

    @property
    def is_running(self) -> bool:
        return self in EntityStatus.status_running()

    @staticmethod
    def status_anomaly() -> list["EntityStatus"]:
        return [
            EntityStatus.CANCELLING,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
        ]

    @property
    def is_anomaly(self) -> bool:
        return self in EntityStatus.status_anomaly()

    @property
    def label(self) -> str:
        """Get the display label for the enum value."""
        return self.name.replace("_", " ").title()


class EntityEvents(str, Enum):
    """Events that trigger transitions between entity states."""

    START_WORK = "start_work"
    SUCCESSFULLY_DONE = "successfully_done"
    AWAITING_ON_INPUT = "awaiting_on_input"
    CANCEL_REQUESTED = "cancel_requested"
    ERROR_ENCOUNTERED = "error_encountered"
    TIMEOUT_OR_ERROR = "timeout_or_error"
    INPUT_RECEIVED = "input_received"
    CANCEL_WHILE_WAITING = "cancel_while_waiting"
    CANCEL_CONFIRMED = "cancel_confirmed"

    @property
    def label(self) -> str:
        """Get the display label for the enum value."""
        return self.name.replace("_", " ").title()


class Lifecycle:
    """
    Defines valid state transitions for workflow entities.

    From: https://agentcommunicationprotocol.dev/core-concepts/agent-lifecycle
    ```mermaid
        stateDiagram-v2
            [*] --> created
            created --> in_progress : Start work
            in_progress --> completed : Successfully done
            in_progress --> awaiting : Awaiting on input
            in_progress --> cancelling : Cancel requested
            awaiting --> failed : Timeout or error
            in_progress --> failed : Error encountered
            awaiting --> in_progress : Input received
            awaiting --> cancelling : Cancel while waiting
            cancelling --> cancelled : Cancel confirmed
            cancelled --> [*]
            completed --> [*]
            failed --> [*]
    ```
    """

    # Event to transition mapping
    EVENT_TRANSITIONS = {
        EntityEvents.START_WORK: (EntityStatus.STOPPED, EntityStatus.IN_PROGRESS),
        EntityEvents.SUCCESSFULLY_DONE: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.COMPLETED,
        ),
        EntityEvents.AWAITING_ON_INPUT: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.AWAITING,
        ),
        EntityEvents.CANCEL_REQUESTED: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.CANCELLING,
        ),
        EntityEvents.ERROR_ENCOUNTERED: (EntityStatus.IN_PROGRESS, EntityStatus.FAILED),
        EntityEvents.TIMEOUT_OR_ERROR: (EntityStatus.AWAITING, EntityStatus.FAILED),
        EntityEvents.INPUT_RECEIVED: (EntityStatus.AWAITING, EntityStatus.IN_PROGRESS),
        EntityEvents.CANCEL_WHILE_WAITING: (
            EntityStatus.AWAITING,
            EntityStatus.CANCELLING,
        ),
        EntityEvents.CANCEL_CONFIRMED: (
            EntityStatus.CANCELLING,
            EntityStatus.CANCELLED,
        ),
    }

    @classmethod
    def get_terminal_states(cls) -> List[EntityStatus]:
        """
        Identify terminal states in the state machine.

        A terminal state is a state that has no outgoing transitions.

        Returns:
            list: List of EntityStatus enum values representing terminal states
        """
        # Get all states that appear as 'from_status' in transitions
        states_with_outgoing = set(
            from_status for _, (from_status, _) in cls.EVENT_TRANSITIONS.items()
        )

        # Terminal states are those that have no outgoing transitions
        terminal_states = [
            status for status in EntityStatus if status not in states_with_outgoing
        ]

        return terminal_states

    @classmethod
    def get_start_states(cls) -> List[EntityStatus]:
        """
        Identify start states in the state machine.

        A start state is a state that can be entered directly at the beginning of
        the workflow. In our case, this is determined by convention and by examining
        which states don't appear as target states in any transition except their own.

        Returns:
            list: List of EntityStatus enum values representing start states
        """
        # Get all states that appear as 'to_status' in transitions
        target_states = set(
            to_status for _, (_, to_status) in cls.EVENT_TRANSITIONS.items()
        )

        # Get all states that appear as 'from_status' in transitions
        source_states = set(
            from_status for _, (from_status, _) in cls.EVENT_TRANSITIONS.items()
        )

        # Find states that are source states but never target states
        # (except for cycles where they might transition to themselves)
        start_candidates = source_states.difference(target_states)

        # If no clear start states are found based on the above logic,
        # use STOPPED as the conventional start state
        if not start_candidates:
            return [EntityStatus.STOPPED]

        return list(start_candidates)

    @classmethod
    def get_valid_transitions(
        cls, current_status: EntityStatus
    ) -> Dict[EntityStatus, EntityEvents]:
        """Get valid transitions from the current status."""
        result = {}
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            if from_status == current_status:
                result[to_status] = event
        return result

    @classmethod
    def can_transition(cls, from_status: EntityStatus, to_status: EntityStatus) -> bool:
        """Check if transition from current status to target status is valid."""
        for event, (event_from, event_to) in cls.EVENT_TRANSITIONS.items():
            if event_from == from_status and event_to == to_status:
                return True
        return False

    @classmethod
    def get_transition_reason(
        cls, from_status: EntityStatus, to_status: EntityStatus
    ) -> str:
        """Get the reason/description for a transition."""
        for event, (event_from, event_to) in cls.EVENT_TRANSITIONS.items():
            if event_from == from_status and event_to == to_status:
                return event.value
        return "Invalid transition"

    @classmethod
    def get_status_from_event(
        cls, current_status: EntityStatus, event: EntityEvents
    ) -> EntityStatus | None:
        """Get the target status for a given event from the current status."""
        if event not in cls.EVENT_TRANSITIONS:
            return None

        from_status, to_status = cls.EVENT_TRANSITIONS[event]
        if current_status == from_status:
            return to_status

        return None

    @classmethod
    def generate_valid_transitions_dict(
        cls,
    ) -> Dict[EntityStatus, Dict[EntityStatus, EntityEvents]]:
        """
        Generate a complete dictionary of all valid transitions in the format:
        {
            StatusA: {StatusB: EventAB, StatusC: EventAC},
            StatusB: {StatusD: EventBD},
            ...
            TerminalStatusX: {},
        }
        """
        # Initialize the result dictionary with all statuses
        result: Dict[EntityStatus, Dict[EntityStatus, EntityEvents]] = {
            status: {} for status in EntityStatus
        }

        # Populate with transitions from EVENT_TRANSITIONS
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            result[from_status][to_status] = event

        return result

    @classmethod
    def generate_mermaid_diagram(cls, steps_list: list[str]) -> str:
        """
        Generate a Mermaid stateDiagram-v2 representation of the state machine.

        Args:
            steps_list: List of steps to include in the diagram (get it from cls.mermaid_diagram_all_steps())

        Returns:
            str: Mermaid markdown for the state diagram
        """
        # Start with diagram header
        mermaid = "```mermaid\nstateDiagram-v2\n"
        # Start state
        mermaid += "\n    ".join(steps_list)

        # Close the diagram
        mermaid += "\n```"

        return mermaid

    @classmethod
    def mermaid_diagram_all_steps(cls) -> list[str]:
        """Get all steps for the Mermaid diagram."""
        steps = cls.mermaid_start_state()
        steps.extend(cls.mermaid_diagram_steps())
        steps.extend(cls.mermaid_terminal_states())
        return steps

    @classmethod
    def mermaid_diagram_steps(cls) -> list[str]:
        """
        Generate a list of steps for the Mermaid diagram.
        """
        steps = []
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            # Get the event display name for the transition label
            event_display = str(event.label)
            from_state = from_status.value
            to_state = to_status.value

            steps.append(f"{from_state} --> {to_state} : {event_display}")

        return steps

    @classmethod
    def mermaid_start_state(cls) -> list[str]:
        """Get the start state for the Mermaid diagram."""
        return [f"[*] --> {state.value}" for state in cls.get_start_states()]

    @classmethod
    def mermaid_terminal_states(cls) -> list[str]:
        """Get the terminal states for the Mermaid diagram."""
        return [f"{state.value} --> [*]" for state in cls.get_terminal_states()]


# Type aliases for backward compatibility
JobTransitions = Lifecycle


class WorkflowEntity(Protocol):
    """Protocol that defines the interface required for an entity to work with lifecycle transitions."""

    status: EntityStatus
    finished_at: Any
    id: Any
    name: str


T = TypeVar("T", bound=WorkflowEntity)


class EntityLifecycle:
    """
    Generic lifecycle manager for workflow entities like Job and Case.
    Handles state transitions according to defined business rules.
    """

    @staticmethod
    def transition(entity: T, to_status: EntityStatus) -> tuple[bool, str]:
        """
        Transition an entity to a new status if the transition is valid.

        Args:
            entity: The entity object to transition (Job, Case, etc.)
            to_status: The target EntityStatus to transition to

        Returns:
            tuple[bool, str]: (True, "") if transition was successful,
                             (False, "error explanation") otherwise

        Side effects:
            - Updates the entity status
            - Records the finished time if the entity is in a terminal state

        Tested in apps.sv_entities.tests.test_lifecycle
        """
        current_status = entity.status

        # Check if transition is valid
        if not Lifecycle.can_transition(current_status, to_status):
            error_msg = (
                f"Invalid transition: {current_status} → {to_status} "
                f"for {entity.__class__.__name__} {entity.id} ({entity.name})"
            )
            log.warning(error_msg)
            return False, error_msg

        # Log the transition
        reason = Lifecycle.get_transition_reason(current_status, to_status)
        log.info(
            f"{entity.__class__.__name__} {entity.id} ({entity.name}) "
            f"transitioning: {current_status} → {to_status}. Reason: {reason}"
        )

        # Update the entity status
        entity.status = to_status

        # If transitioning to a terminal state, record the finished time
        if to_status in [
            EntityStatus.COMPLETED,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
        ]:
            if not entity.finished_at:
                entity.finished_at = datetime.now()

        return True, ""

    @staticmethod
    def handle_event(entity: T, event: EntityEvents) -> tuple[bool, str]:
        """
        Handle an event by transitioning the entity to the appropriate status.

        Args:
            entity: The entity object to transition
            event: The event that occurred

        Returns:
            tuple[bool, str]: (True, "") if handling was successful,
                             (False, "error explanation") otherwise
        """
        current_status = entity.status
        to_status = Lifecycle.get_status_from_event(current_status, event)

        if not to_status:
            error_msg = (
                f"Invalid event {event} for current status {current_status} "
                f"in {entity.__class__.__name__} {entity.id} ({entity.name})"
            )
            log.warning(error_msg)
            return False, error_msg

        return EntityLifecycle.transition(entity, to_status)
```

The state machine is table-driven: `EVENT_TRANSITIONS` maps each event to a `(from_status, to_status)` pair. `EntityLifecycle.transition()` checks `Lifecycle.can_transition()` before updating the entity — invalid transitions log a warning and return `(False, error_msg)` rather than raising.

The `Lifecycle` class also self-documents via `generate_mermaid_diagram()` — it can emit a Mermaid state diagram from its own transition table.

State groups for convenience:
- `is_stopped` — STOPPED, CANCELLED, FAILED, COMPLETED (terminal)
- `is_running` — IN_PROGRESS, CANCELLING, AWAITING
- `is_anomaly` — CANCELLING, CANCELLED, FAILED

---

## 7. Jobs (`job.py`)

A `Job` is created when a client requests work and lives until the agent finishes.

```bash
grep -n 'class \|def ' src/supervaizer/job.py | head -50
```

```output
27:class Jobs:
30:    def __init__(self) -> None:
34:    def reset(self) -> None:
37:    def add_job(self, job: "Job") -> None:
58:    def get_job(
91:    def get_agent_jobs(self, agent_name: str) -> dict[str, "Job"]:
102:    def __contains__(self, job_id: str) -> bool:
107:class JobInstructions(SvBaseModel):
116:    def check(self, cases: int, cost: float) -> tuple[bool, str]:
142:    def registration_info(self) -> Dict[str, Any]:
153:class JobContext(SvBaseModel):
164:    def registration_info(self) -> Dict[str, Any]:
180:class JobResponse(SvBaseModel):
188:    def __init__(
220:    def registration_info(self) -> Dict[str, Any]:
232:class AbstractJob(SvBaseModel):
249:class Job(AbstractJob):
266:    def __init__(self, **kwargs: Any) -> None:
276:    def add_response(self, response: JobResponse) -> None:
301:    def add_case_id(self, case_id: str) -> None:
313:    def remove_case_id(self, case_id: str) -> None:
326:    def registration_info(self) -> Dict[str, Any]:
343:    def new(
```

```bash
sed -n '27,100p' src/supervaizer/job.py
```

```output
class Jobs:
    """Global registry for all jobs, organized by agent."""

    def __init__(self) -> None:
        # Structure: {agent_name: {job_id: Job}}
        self.jobs_by_agent: dict[str, dict[str, "Job"]] = {}

    def reset(self) -> None:
        self.jobs_by_agent.clear()

    def add_job(self, job: "Job") -> None:
        """Add a job to the registry under its agent

        Args:
            job (Job): The job to add

        Raises:
            ValueError: If job with same ID already exists for this agent
        """
        agent_name = job.agent_name

        # Initialize agent's job dict if not exists
        if agent_name not in self.jobs_by_agent:
            self.jobs_by_agent[agent_name] = {}

        # Check if job already exists for this agent
        if job.id in self.jobs_by_agent[agent_name]:
            log.warning(f"Job ID '{job.id}' already exists for agent {agent_name}.")

        self.jobs_by_agent[agent_name][job.id] = job

    def get_job(
        self,
        job_id: str,
        agent_name: str | None = None,
        include_persisted: bool = False,
    ) -> "Job | None":
        """Get a job by its ID and optionally agent name

        Args:
            job_id (str): The ID of the job to get
            agent_name (str | None): The name of the agent. If None, searches all agents.
            include_persisted (bool): Whether to include persisted jobs. Defaults to False.

        Returns:
            Job | None: The job if found, None otherwise
        """
        found_job = None

        if agent_name:
            # Search in specific agent's jobs
            found_job = self.jobs_by_agent.get(agent_name, {}).get(job_id)

        # Search across all agents
        for agent_jobs in self.jobs_by_agent.values():
            if job_id in agent_jobs:
                found_job = agent_jobs[job_id]

        if include_persisted:
            job_from_storage = storage_manager.get_object_by_id("Job", job_id)
            if job_from_storage:
                found_job = Job(**job_from_storage)
        return found_job

    def get_agent_jobs(self, agent_name: str) -> dict[str, "Job"]:
        """Get all jobs for a specific agent

        Args:
            agent_name (str): The name of the agent

        Returns:
            dict[str, Job]: Dictionary of jobs for this agent, empty if agent not found
        """
        return self.jobs_by_agent.get(agent_name, {})
```

```bash
sed -n '249,380p' src/supervaizer/job.py
```

```output
class Job(AbstractJob):
    """
    Jobs are typically created by the platform and are not created by the agent.

    Args:
        id (str): Unique identifier for the job - provided by the platform
        agent_name (str): Name (slug) of the agent running the job
        status (EntityStatus): Current status of the job
        job_context (JobContext): Context information for the job
        payload (Any, optional): Job payload data. Defaults to None
        result (Any, optional): Job result data. Defaults to None
        error (str, optional): Error message if job failed. Defaults to None
        responses (list[JobResponse], optional): List of job responses. Defaults to empty list
        finished_at (datetime, optional): When job completed. Defaults to None
        created_at (datetime, optional): When job was created. Defaults to None
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.created_at = datetime.now()
        Jobs().add_job(
            job=self,
        )
        # Persist job to storage

        storage_manager.save_object("Job", self.to_dict)

    def add_response(self, response: JobResponse) -> None:
        """Add a response to the job and update status based on the event lifecycle.

        Args:
            response: The response to add
        """
        if response.status in Lifecycle.get_terminal_states():
            self.finished_at = datetime.now()

        # Update payload
        self.payload = response.payload
        self.status = response.status
        # Additional handling for completed or failed jobs
        if response.status == EntityStatus.COMPLETED:
            self.result = response.payload

        if response.status == EntityStatus.FAILED:
            self.error = response.message

        self.responses.append(response)

        # Persist updated job to storage

        storage_manager.save_object("Job", self.to_dict)

    def add_case_id(self, case_id: str) -> None:
        """Add a case ID to this job's case list.

        Args:
            case_id: The case ID to add
        """
        if case_id not in self.case_ids:
            self.case_ids.append(case_id)
            log.debug(f"[Job add_response] Added case {case_id} to job {self.id}")
            # Persist updated job to storage
            storage_manager.save_object("Job", self.to_dict)

    def remove_case_id(self, case_id: str) -> None:
        """Remove a case ID from this job's case list.

        Args:
            case_id: The case ID to remove
        """
        if case_id in self.case_ids:
            self.case_ids.remove(case_id)
            log.debug(f"Removed case {case_id} from job {self.id}")
            # Persist updated job to storage
            storage_manager.save_object("Job", self.to_dict)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the job"""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "job_context": self.job_context.registration_info,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "responses": [response.registration_info for response in self.responses],
            "finished_at": self.finished_at.isoformat() if self.finished_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "case_ids": self.case_ids,
        }

    @classmethod
    def new(
        cls,
        job_context: "JobContext",
        agent_name: str,
        agent_parameters: Optional[list[dict[str, Any]]] = None,
        name: Optional[str] = None,
    ) -> "Job":
        """Create a new job

        Args:
            job_context (JobContext): The context of the job
            agent_name (str): The name of the agent
            agent_parameters (list[dict[str, Any]] | None): Optional parameters for the job
            name (str | None): Optional name for the job, defaults to mission name if not provided

        Returns:
            Job: The new job
        """
        job_id = job_context.job_id or str(uuid.uuid4())
        # Use provided name or fallback to mission name from context
        job_name = name or job_context.mission_name

        # Ensure agent_parameters is a list of dicts, not nested incorrectly
        if agent_parameters is not None:
            # If it's a list but the first element is also a list, unwrap it
            if isinstance(agent_parameters, list) and len(agent_parameters) > 0:
                if isinstance(agent_parameters[0], list):
                    # Unwrap nested list: [[{...}, {...}]] -> [{...}, {...}]
                    agent_parameters = agent_parameters[0]
            # Ensure all elements are dicts
            if not all(isinstance(p, dict) for p in agent_parameters):
                raise ValueError(
                    f"agent_parameters must be a list of dictionaries, got: {type(agent_parameters)}"
                )

        job = cls(
            id=job_id,
            name=job_name,
```

Three important patterns in `Job`:

1. **Self-registration**: `Job.__init__` immediately calls `Jobs().add_job(self)` — every Job instance joins the global in-memory registry and is persisted to storage atomically on creation.
2. **Persistence on every mutation**: `add_response`, `add_case_id`, `remove_case_id` all call `storage_manager.save_object` after modifying state, so the file on disk is always current.
3. **`add_response`** drives the status machine: setting a terminal status stamps `finished_at`; `COMPLETED` copies the payload to `result`; `FAILED` copies the message to `error`.

---

## 8. Cases (`case.py`)

Cases are the step-by-step execution log *within* a job. Each Case has a series of Nodes, each Node records one unit of work.

```bash
grep -n 'class \|def ' src/supervaizer/case.py | head -60
```

```output
24:class CaseNodeUpdate(SvBaseModel):
26:    CaseNodeUpdate is a class that represents an update to a case node.
41:    def __init__(
101:    def registration_info(self) -> Dict[str, Any]:
117:class CaseNodeType(Enum):
136:class CaseNode(SvBaseModel):
147:    def __call__(self, *args: Any, **kwargs: Any) -> CaseNodeUpdate:
152:    def registration_info(self) -> Dict[str, Any]:
162:class CaseNodes(SvBaseModel):
165:    def get(self, name: str) -> CaseNode | None:
169:    def registration_info(self) -> Dict[str, Any]:
176:class CaseAbstractModel(SvBaseModel):
190:class Case(CaseAbstractModel):
191:    def __init__(self, **kwargs: Any) -> None:
202:    def uri(self) -> str:
206:    def case_ref(self) -> str:
210:    def calculated_cost(self) -> float:
213:    def update(self, updateCaseNode: CaseNodeUpdate, **kwargs: Any) -> None:
229:    def request_human_input(
247:    def receive_human_input(
257:    def close(
295:    def registration_info(self) -> Dict[str, Any]:
310:    def start(
368:class Cases:
371:    def __init__(self) -> None:
375:    def reset(self) -> None:
378:    def add_case(self, case: "Case") -> None:
399:    def get_case(self, case_id: str, job_id: str | None = None) -> "Case | None":
419:    def get_job_cases(self, job_id: str) -> dict[str, "Case"]:
430:    def __contains__(self, case_id: str) -> bool:
```

```bash
sed -n '24,115p' src/supervaizer/case.py
```

```output
class CaseNodeUpdate(SvBaseModel):
    """
    CaseNodeUpdate is a class that represents an update to a case node.


    Returns:
        CaseNodeUpdate: CaseNodeUpdate object
    """

    index: int | None = None  # added in Case.update
    cost: float | None = None
    name: str | None = None
    # Todo: test with non-serializable objects. Make sure it works.
    payload: Optional[Dict[str, Any]] = None
    is_final: bool = False
    error: Optional[str] = None

    def __init__(
        self,
        cost: float | None = None,
        name: str | None = None,
        payload: Dict[str, Any] | None = None,
        is_final: bool = False,
        index: int | None = None,
        error: Optional[str] = None,
    ) -> None:
        """Initialize a CaseNodeUpdate.

        Args:
            cost (float): Cost of the update
            name (str): Name of the update
            payload (Dict[str, Any]): Additional data for the update - when a question is requested to the user, the payload is the question
            is_final (bool): Whether this is the final update. Default to False
            index (int): Index of the node to update. This is set by Case.update()
            error (Optional[str]): Error message if any. Default to None

        When payload contains a question (supervaizer_form):
            payload = {
                "supervaizer_form": {
                    "question": str,  # The question to ask
                    "answer": {
                        "fields": [
                            {
                                "name": str,        # Field name
                                "description": str, # Field description
                                "type": type,      # Field type (e.g. bool)
                                "field_type": str, # Field type name (e.g. "BooleanField")
                                "required": bool   # Whether field is required
                            },
                            # ... additional fields
                        ]
                    }
                }
            }

        Returns:
            CaseNodeUpdate: CaseNodeUpdate object
        """
        # Use model_construct rather than passing arguments to __init__
        values = {
            "cost": cost,
            "name": name,
            "payload": payload,
            "is_final": is_final,
            "index": index,
            "error": error,
        }
        object.__setattr__(self, "__dict__", {})
        object.__setattr__(self, "__pydantic_fields_set__", set())
        object.__setattr__(self, "__pydantic_extra__", None)
        object.__setattr__(self, "__pydantic_private__", None)

        # Update the model fields without calling the SvBaseModel.__init__
        for key, value in values.items():
            setattr(self, key, value)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node update"""
        # Serialize payload to convert type objects to strings for JSON serialization
        serialized_payload = (
            self.serialize_value(self.payload) if self.payload else None
        )
        return {
            "index": self.index,
            "name": self.name,
            "error": self.error,
            "cost": self.cost,
            "payload": serialized_payload,
            "is_final": self.is_final,
        }

```

```bash
sed -n '190,300p' src/supervaizer/case.py
```

```output
class Case(CaseAbstractModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Register the case in the global registry
        Cases().add_case(self)
        # Persist case to storage
        from supervaizer.storage import StorageManager

        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    @property
    def uri(self) -> str:
        return f"case:{self.id}"

    @property
    def case_ref(self) -> str:
        return f"{self.job_id}-{self.id}"

    @property
    def calculated_cost(self) -> float:
        return sum(update.cost or 0.0 for update in self.updates)

    def update(self, updateCaseNode: CaseNodeUpdate, **kwargs: Any) -> None:
        updateCaseNode.index = len(self.updates) + 1
        if updateCaseNode.error:
            success, error = PersistentEntityLifecycle.handle_event(
                self, EntityEvents.ERROR_ENCOUNTERED
            )
            log.warning(
                f"[Case update] CaseRef {self.case_ref} has error {updateCaseNode.error}"
            )
            assert self.status == EntityStatus.FAILED  # Just to be sure
        self.account.send_update_case(self, updateCaseNode)
        self.updates.append(updateCaseNode)

        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    def request_human_input(
        self, updateCaseNode: CaseNodeUpdate, message: str, **kwargs: Any
    ) -> None:
        updateCaseNode.index = len(self.updates) + 1
        log.info(
            f"[Update case human_input] CaseRef {self.case_ref} with update {updateCaseNode}"
        )
        self.account.send_update_case(self, updateCaseNode)
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.AWAITING_ON_INPUT)
        self.updates.append(updateCaseNode)

        # Persist updated case to storage (for the updates list change)

        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    def receive_human_input(
        self, updateCaseNode: CaseNodeUpdate, **kwargs: Any
    ) -> None:
        # Add the update to the case (this handles index, send_update_case, and persistence)
        self.update(updateCaseNode)
        # Transition from AWAITING to IN_PROGRESS
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.INPUT_RECEIVED)

    def close(
        self,
        case_result: Dict[str, Any],
        final_cost: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Close the case and send the final update to the account.
        """
        if final_cost:
            self.total_cost = final_cost
        else:
            self.total_cost = self.calculated_cost
        log.info(
            f"[Close case] CaseRef {self.case_ref} with result {case_result} - Case cost is {self.total_cost}"
        )
        # Transition from IN_PROGRESS to COMPLETED
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.SUCCESSFULLY_DONE)

        update = CaseNodeUpdate(
            payload=case_result,
            is_final=True,
        )
        update.index = len(self.updates) + 1

        self.final_delivery = case_result
        self.finished_at = datetime.now()
        self.account.send_update_case(self, update)

        # Persist updated case to storage
        from supervaizer.storage import StorageManager

        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case"""
        return {
            "case_id": self.id,
            "job_id": self.job_id,
            "case_ref": self.case_ref,
```

```bash
sed -n '310,370p' src/supervaizer/case.py
```

```output
    def start(
        cls,
        job_id: str,
        name: str,
        account: "Account",
        description: str,
        case_id: Optional[str] = None,
    ) -> "Case":
        """
        Start a new case

        Args:
            case_id (str): The id of the case - should be unique for the job. If not provided, a shortuuid will be generated.
            job_id (str): The id of the job
            name (str): The name of the case
            account (Account): The account
            description (str): The description of the case

        Returns:
            Case: The case
        """

        case = cls(
            id=case_id or shortuuid.uuid(),
            job_id=job_id,
            account=account,
            name=name,
            description=description,
            status=EntityStatus.STOPPED,
        )
        log.info(f"[Case created] {case.id}")

        # Add case to job's case_ids for foreign key relationship
        from supervaizer.job import Jobs

        job = Jobs().get_job(job_id)
        if job:
            job.add_case_id(case.id)

        # Transition from STOPPED to IN_PROGRESS

        PersistentEntityLifecycle.handle_event(case, EntityEvents.START_WORK)

        # Send case start event to Supervaize SaaS.
        result = account.send_start_case(case=case)
        if result:
            log.debug(
                f"[Case start] Case {case.id} send to Supervaize with result {result}"
            )
        else:
            log.error(
                f"[Case start] §SCCS01 Case {case.id} failed to send to Supervaize"
            )

        return case


@singleton
class Cases:
    """Global registry for all cases, organized by job."""

```

The Case lifecycle in three phases:

1. **`Case.start()`** — factory classmethod: creates the case, registers it, fires `START_WORK` transition (`STOPPED→IN_PROGRESS`), then calls `account.send_start_case` to notify the platform.
2. **`Case.update()`** — appends a `CaseNodeUpdate` (auto-indexes it), sends it to the platform, persists to storage. If the update contains an `error`, the state transitions to `FAILED`.
3. **`Case.close()`** — fires `SUCCESSFULLY_DONE` transition, sends final delivery payload, stamps `finished_at`.

Human-in-the-loop:
- `request_human_input` → `AWAITING_ON_INPUT` transition → pauses execution.
- `receive_human_input` → `INPUT_RECEIVED` transition → resumes.

---

## 9. Storage (`storage.py`)

TinyDB-backed persistence with an in-memory fallback for serverless environments.

```bash
grep -n 'class \|def ' src/supervaizer/storage.py | head -40
```

```output
25:class _MemoryStorage(MemoryStorage):
28:    def __init__(self, *args: Any, **kwargs: Any) -> None:
52:class StorageManager:
62:    def __init__(self, db_path: Optional[str] = None):
93:    def save_object(self, type: str, obj: Dict[str, Any]) -> None:
98:            type: The object type (class name)
116:    def get_objects(self, type: str) -> List[Dict[str, Any]]:
121:            type: The object type (class name)
131:    def get_object_by_id(self, type: str, obj_id: str) -> Optional[Dict[str, Any]]:
136:            type: The object type (class name)
148:    def delete_object(self, type: str, obj_id: str) -> bool:
153:            type: The object type (class name)
169:    def reset_storage(self) -> None:
180:    def get_cases_for_job(self, job_id: str) -> List[Dict[str, Any]]:
196:    def close(self) -> None:
212:class EntityRepository(Generic[T]):
219:    def __init__(
226:            entity_class: The entity class this repository manages
229:        self.entity_class = entity_class
233:    def get_by_id(self, entity_id: str) -> Optional[T]:
248:    def save(self, entity: T) -> None:
258:    def get_all(self) -> List[T]:
268:    def delete(self, entity_id: str) -> bool:
280:    def _to_dict(self, entity: T) -> Dict[str, Any]:
292:    def _from_dict(self, data: Dict[str, Any]) -> T:
307:class PersistentEntityLifecycle:
311:    This class wraps the original EntityLifecycle methods to add persistence.
315:    def transition(
347:    def handle_event(
379:def create_job_repository() -> "EntityRepository[Job]":
386:def create_case_repository() -> "EntityRepository[Case]":
393:def load_running_entities_on_startup() -> None:
```

```bash
sed -n '52,200p' src/supervaizer/storage.py
```

```output
class StorageManager:
    """
    Thread-safe TinyDB-based persistence manager for WorkflowEntity instances.

    Stores entities in separate tables by type, with foreign key relationships
    represented as ID references (Job.case_ids, Case.job_id).

    When SUPERVAIZER_PERSISTENCE is false (default), uses in-memory storage only.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the storage manager.

        Args:
            db_path: Path to the TinyDB JSON file, or None to use env-based
                     persistence (file if SUPERVAIZER_PERSISTENCE=true, else memory).
        """
        self._lock = threading.Lock()
        # Explicit file path (e.g. tests) uses file; else file only if persistence enabled
        use_file = (db_path is not None and db_path != ":memory:") or (
            db_path is None and PERSISTENCE_ENABLED
        )
        if use_file:
            path = (
                db_path
                if (db_path and db_path != ":memory:")
                else f"{DATA_STORAGE_PATH}/entities.json"
            )
            self.db_path = Path(path)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = TinyDB(path, sort_keys=True, indent=2)
        else:
            # In-memory only (default for Vercel/serverless)
            self.db_path = Path(":memory:")
            self._db = TinyDB(storage=_MemoryStorage, sort_keys=True, indent=2)

        # log.debug(
        #    f"[StorageManager] 🗃️ Local DB initialized at {self.db_path.absolute()}"
        # )

    def save_object(self, type: str, obj: Dict[str, Any]) -> None:
        """
        Save an object to the appropriate table.

        Args:
            type: The object type (class name)
            obj: Dictionary representation of the object
        """
        with self._lock:
            table = self._db.table(type)
            obj_id = obj.get("id")

            if not obj_id:
                raise ValueError(
                    f"[StorageManager] §SSSS01 Object must have an 'id' field: {obj}"
                )

            # Use upsert to handle both new and existing objects
            query = Query()
            table.upsert(obj, query.id == obj_id)

            # log.debug(f"Saved object with ID: {type} {obj_id} - {obj}")

    def get_objects(self, type: str) -> List[Dict[str, Any]]:
        """
        Get all objects of a specific type.

        Args:
            type: The object type (class name)

        Returns:
            List of object dictionaries
        """
        with self._lock:
            table = self._db.table(type)
            documents = table.all()
            return [dict(doc) for doc in documents]

    def get_object_by_id(self, type: str, obj_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific object by its ID.

        Args:
            type: The object type (class name)
            obj_id: The object ID

        Returns:
            Object dictionary if found, None otherwise
        """
        with self._lock:
            table = self._db.table(type)
            query = Query()
            result = table.search(query.id == obj_id)
            return result[0] if result else None

    def delete_object(self, type: str, obj_id: str) -> bool:
        """
        Delete an object by its ID.

        Args:
            type: The object type (class name)
            obj_id: The object ID

        Returns:
            True if object was deleted, False if not found
        """
        with self._lock:
            table = self._db.table(type)
            query = Query()
            deleted_count = len(table.remove(query.id == obj_id))

            if deleted_count > 0:
                log.debug(f"Deleted {type} object with ID: {obj_id}")
                return True
            return False

    def reset_storage(self) -> None:
        """
        Reset storage by clearing all tables but preserving the database file.
        """
        with self._lock:
            # Clear all tables
            for table_name in self._db.tables():
                self._db.drop_table(table_name)

            log.info("Storage reset - all tables cleared")

    def get_cases_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Helper method to get all cases for a specific job.

        Args:
            job_id: The job ID

        Returns:
            List of case dictionaries
        """
        with self._lock:
            table = self._db.table("Case")
            query = Query()
            documents = table.search(query.job_id == job_id)
            return [dict(doc) for doc in documents]

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if hasattr(self, "_db") and self._db is not None:
                try:
```

`StorageManager` uses a `threading.Lock` to make all reads and writes thread-safe. Every `save_object` call does a TinyDB **upsert** (insert or replace) keyed on `id`, so callers never need to check existence first.

The `SUPERVAIZER_PERSISTENCE` env var switches between:
- **File mode** — `./data/entities.json` (self-hosted servers that survive restarts)
- **In-memory mode** (default) — ephemeral, for serverless/Vercel deployments

`PersistentEntityLifecycle` wraps `EntityLifecycle.transition` and `handle_event` to auto-save after every state change — the two methods call `storage_manager.save_object` immediately after transitioning.

`load_running_entities_on_startup()` is called during server startup to restore any jobs/cases that were `IN_PROGRESS` when the process last exited (only useful in file-persistence mode).

---

## 10. The Event System (`event.py`)

Events are fire-and-forget notifications sent to the Supervaize SaaS platform after significant state changes.

```bash
grep -n 'class \|EventType\.' src/supervaizer/event.py | head -50
```

```output
21:class EventType(str, Enum):
39:class AbstractEvent(SvBaseModel):
48:class Event(AbstractEvent):
49:    """Base class for all events in the Supervaize Control system.
81:class AgentRegisterEvent(Event):
94:            type=EventType.AGENT_REGISTER,
102:class ServerRegisterEvent(Event):
109:            type=EventType.SERVER_REGISTER,
117:class JobStartConfirmationEvent(Event):
124:            type=EventType.JOB_START_CONFIRMATION,
132:class JobFinishedEvent(Event):
141:            EventType.JOB_END
143:            else EventType.JOB_ERROR
155:class CaseStartEvent(Event):
160:            type=EventType.CASE_START,
168:class CaseUpdateEvent(Event):
176:            type=EventType.CASE_UPDATE,
```

```bash
sed -n '21,185p' src/supervaizer/event.py
```

```output
class EventType(str, Enum):
    AGENT_REGISTER = "agent.register"
    SERVER_REGISTER = "server.register"
    AGENT_WAKEUP = "agent.wakeup"
    AGENT_SEND_ANOMALY = "agent.anomaly"
    INTERMEDIARY = "agent.intermediary"
    JOB_START_CONFIRMATION = "agent.job.start.confirmation"
    JOB_END = "agent.job.end"
    JOB_STATUS = "agent.job.status"
    JOB_RESULT = "agent.job.result"
    JOB_ERROR = "agent.job.error"
    CASE_START = "agent.case.start"
    CASE_END = "agent.case.end"
    CASE_STATUS = "agent.case.status"
    CASE_RESULT = "agent.case.result"
    CASE_UPDATE = "agent.case.update"


class AbstractEvent(SvBaseModel):
    supervaizer_VERSION: ClassVar[str] = VERSION
    source: Dict[str, Any]
    account: Any  # Use Any to avoid Pydantic type resolution issues
    type: EventType
    object_type: str
    details: Dict[str, Any]


class Event(AbstractEvent):
    """Base class for all events in the Supervaize Control system.

    Events represent messages sent from agents to the control system to communicate
    status, anomalies, deliverables and other information.

    Inherits from AbstractEvent which defines the core event attributes:
        - source: The source/origin of the event (e.g. agent/server URI)
        - type: The EventType enum indicating the event category
        - account: The account that the event belongs to
        - details: A dictionary containing event-specific details

    Tests in tests/test_event.py
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def payload(self) -> Dict[str, Any]:
        """
        Returns the payload for the event.
        This must be a dictionary that can be serialized to JSON to be sent in the request body.
        """
        return {
            "source": self.source,
            "workspace": f"{self.account.workspace_id}",
            "event_type": f"{self.type.value}",
            "object_type": self.object_type,
            "details": self.details,
        }


class AgentRegisterEvent(Event):
    """Event sent when an agent registers with the control system.

    Test in tests/test_agent_register_event.py
    """

    def __init__(
        self,
        agent: "Agent",
        account: Any,  # Use Any to avoid type resolution issues
        polling: bool = True,
    ) -> None:
        super().__init__(
            type=EventType.AGENT_REGISTER,
            account=account,
            source={"agent": agent.slug},
            object_type="agent",
            details=agent.registration_info | {"polling": polling},
        )


class ServerRegisterEvent(Event):
    def __init__(
        self,
        account: Any,  # Use Any to avoid type resolution issues
        server: "Server",
    ) -> None:
        super().__init__(
            type=EventType.SERVER_REGISTER,
            source={"server": server.uri},
            account=account,
            object_type="server",
            details=server.registration_info,
        )


class JobStartConfirmationEvent(Event):
    def __init__(
        self,
        job: "Job",
        account: Any,  # Use Any to avoid type resolution issues
    ) -> None:
        super().__init__(
            type=EventType.JOB_START_CONFIRMATION,
            account=account,
            source={"job": job.id},
            object_type="job",
            details=job.registration_info,
        )


class JobFinishedEvent(Event):
    def __init__(self, job: "Job", account: Any) -> None:
        # Check if job has responses, otherwise use the job's current status
        if job.responses:
            details = job.responses[-1].status
        else:
            details = job.status

        event_type = (
            EventType.JOB_END
            if details == EntityStatus.COMPLETED
            else EventType.JOB_ERROR
        )

        super().__init__(
            type=event_type,
            account=account,
            source={"job": job.id},
            object_type="job",
            details=job.registration_info,
        )


class CaseStartEvent(Event):
    def __init__(
        self, case: "Case", account: Any
    ) -> None:  # Use Any to avoid type resolution issues
        super().__init__(
            type=EventType.CASE_START,
            account=account,
            source={"job": case.job_id, "case": case.id},
            object_type="case",
            details=case.registration_info,
        )


class CaseUpdateEvent(Event):
    def __init__(
        self,
        case: "Case",
        account: Any,
        update: "CaseNodeUpdate",
    ) -> None:
        super().__init__(
            type=EventType.CASE_UPDATE,
            account=account,
            source={"job": case.job_id, "case": case.id},
            object_type="case",
            details=update.registration_info,
        )
```

Each event subclass is just a constructor that composes the right fields from its input objects. No network code here — events are dispatched by `account.send_event()` (in `account.py`).

`JobFinishedEvent` has one interesting branch: it checks the last response status to decide between `JOB_END` (success) or `JOB_ERROR` (failure).

---

## 11. Account & Platform Integration (`account.py`, `account_service.py`)

The `Account` class is the HTTP client that talks to the Supervaize SaaS.

```bash
grep -n 'class \|def \|endpoint\|api_url' src/supervaizer/account.py | head -50
```

```output
26:class AccountAbstract(SvBaseModel):
46:        api_url (str): The URL of the Supervaize SaaS API provided by Supervaize.com
54:    api_url: str = Field(
58:    @field_validator("workspace_id", "api_key", "api_url", mode="before")
60:    def strip_whitespace(cls, v: Any) -> Any:
73:                    "api_url": "https://app.supervaize.com",
80:class Account(AccountAbstract):
83:        "team": "{api_url}/w/{workspace_id}",
84:        "event": "{api_url}/w/{workspace_id}/api/v1/ctrl-events/",
85:        "agent_by_id": "{api_url}/w/{workspace_id}/api/v1/agents/{agent_id}",
86:        "agent_by_slug": "{api_url}/w/{workspace_id}/api/v1/agents/by-slug/{agent_slug}",
87:        "telemetry": "{api_url}/{telemetry_version}/telemetry",
90:    def __init__(self, **kwargs: Any) -> None:
105:    def api_url_w_v1(self) -> str:
109:        return f"{self.api_url}/w/{self.workspace_id}/api/v1"
112:    def api_headers(self) -> Dict[str, str]:
123:    def api_url_team(self) -> str:
128:    def url_event(self) -> str:
132:        return f"{self.api_url_w_v1}/ctrl-events/".strip()
134:    def get_url(self, pattern_name: str, **kwargs: Any) -> str:
154:            "api_url": self.api_url,
164:    def send_event(
185:    def register_server(self, server: "Server") -> ApiResult:
210:    def _create_api_result(
222:    def get_agent_by(
237:            url = f"{self.api_url_w_v1}/agents/{agent_id}"
239:            url = f"{self.api_url_w_v1}/agents/by-slug/{agent_slug}"
260:    def register_agent(self, agent: "Agent", polling: bool = True) -> ApiResult:
277:    def send_start_case(self, case: "Case") -> ApiResult:
284:    def send_update_case(self, case: "Case", update: "CaseNodeUpdate") -> ApiResult:
294:    def send_telemetry(self, telemetry: Telemetry) -> ApiResult:
```

```bash
sed -n '164,210p' src/supervaizer/account.py
```

```output
    def send_event(
        self,
        sender: Union["Agent", "Job", "Server", "Case", "CaseNodeUpdate"],
        event: "Event",
    ) -> ApiResult:
        """Send an event to the Supervaize SaaS API.

        Args:
            sender (Union[Agent, Server, Case, CaseNodeUpdate]): The sender of the event
            event (Event): The event to be sent

        Returns:
            ApiResult: ApiSuccess with response details if successful,
        Raises:
            Request exception if the request fails.
        """
        # Import here to avoid circular imports
        from supervaizer.account_service import send_event as service_send_event

        return service_send_event(self, sender, event)

    def register_server(self, server: "Server") -> ApiResult:
        """Register a server with the Supervaize Control API.

        Args:
            server (Server): The server to register.

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails

        Side effects:
            - Sends a ServerRegisterEvent to the Supervaize Control API
        """
        # Import here to avoid circular imports
        from supervaizer.event import ServerRegisterEvent

        event = ServerRegisterEvent(server=server, account=self)
        result = self.send_event(sender=server, event=event)
        if isinstance(result, ApiSuccess):
            log.success(result.message)
            # TODO: Update server with the server ID from the response. store this ID in env variable.
        else:
            log.error(result.message)
        return result

    def _create_api_result(
```

```bash
cat src/supervaizer/account_service.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import logging
import os
from typing import TYPE_CHECKING, Union

import httpx

from supervaizer.common import ApiError, ApiResult, ApiSuccess, log

logger = logging.getLogger("httpx")
# Enable httpx debug logging (optional - uncomment for transport-level debugging)
logger.setLevel(logging.DEBUG)

_httpx_transport = httpx.HTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2))
)
_httpx_client = httpx.Client(transport=_httpx_transport)

if TYPE_CHECKING:
    from supervaizer.account import Account
    from supervaizer.agent import Agent
    from supervaizer.case import Case, CaseNodeUpdate
    from supervaizer.event import Event
    from supervaizer.job import Job
    from supervaizer.server import Server


def send_event(
    account: "Account",
    sender: Union["Agent", "Server", "Job", "Case", "CaseNodeUpdate"],
    event: "Event",
) -> ApiResult:
    """Send an event to the Supervaize SaaS API.

    Args:
        account (Account): The account used to authenticate the request
        sender (Union[Agent, Server, Case, CaseNodeUpdate]): The sender of the event
        event (Event): The event to be sent

    Returns:
        ApiResult: ApiSuccess with response details if successful,
    Raises:
        Request exception if the request fails.

    Side effects:
        - Sends an event to the Supervaize Control API

        Tested in tests/test_account_service.py
    """

    headers = account.api_headers
    payload = event.payload
    url_event = (
        account.url_event.strip()
    )  # defensive: env vars often have trailing newline

    # Generate curl equivalent for debugging

    curl_headers = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
    curl_cmd = f"curl -X 'GET' '{url_event}'  {curl_headers}"

    try:
        response = _httpx_client.post(url_event, headers=headers, json=payload)

        # Log response details before raising for status

        response.raise_for_status()
        result = ApiSuccess(
            message=f"POST Event {event.type.name} sent", detail=response.text
        )

        log.success(result.log_message)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        log.error(
            f"Supervaize controller is not available at {url_event}. "
            "Connection refused or timed out. Is the controller server running?"
        )
        log.error(f"❌ Error sending event {event.type.name}: {e!s}")
        raise e
    except httpx.HTTPError as e:
        # Enhanced error logging
        log.error("[Send event] HTTP Error occurred")
        log.warning(f"⚠️ Try to connect via curl:\n{curl_cmd}")

        error_result = ApiError(
            message=f"Error sending event {event.type.name}",
            url=url_event,
            payload=event.payload,
            exception=e,
        )
        log.error(f"[Send event] Error details: {error_result.dict}")
        log.error(error_result.log_message)
        raise e
    return result
```

All HTTP traffic to the Supervaize SaaS goes through a single global `httpx.Client` with a configurable retry transport (`SUPERVAIZE_HTTP_MAX_RETRIES`, default 2).

`account.send_event` → `account_service.send_event` → `POST {api_url}/w/{workspace_id}/api/v1/ctrl-events/`.

The function logs a `curl` equivalent command for easy debugging when errors occur. Network failures raise the `httpx` exception up to the caller; `ConnectError` gets a more helpful message.

---

## 12. The Server (`server.py`)

This is the piece that wires everything together.

```bash
grep -n 'class \|def ' src/supervaizer/server.py | head -50
```

```output
58:def _get_or_create_server_id() -> str:
68:def _get_or_create_private_key() -> RSAPrivateKey:
98:class ServerInfo(BaseModel):
112:def save_server_info_to_storage(server_instance: "Server") -> None:
154:def get_server_info_from_storage() -> Optional[ServerInfo]:
164:def get_server_info_from_live(server_instance: "Server") -> ServerInfo:
190:class ServerAbstract(SvBaseModel):
285:    def scheme_validator(cls, v: str) -> str:
291:    def host_validator(cls, v: str) -> str:
296:    def get_agent_by_name(self, agent_name: str) -> Optional[Agent]:
303:class Server(ServerAbstract):
304:    def __init__(
401:        async def validation_exception_handler(
465:        async def home_page(request: Request) -> HTMLResponse:
490:        async def get_current_server() -> "Server":
511:    async def verify_api_key(
539:    def url(self) -> str:
544:    def uri(self) -> str:
549:    def registration_info(self) -> Dict[str, Any]:
573:    def launch(self, log_level: Optional[str] = "INFO") -> None:
586:                def log_queue_handler(message: Any) -> None:
642:    def instructions(self) -> None:
648:    def decrypt(self, encrypted_parameters: str) -> str:
655:    def encrypt(self, parameters: str) -> str:
```

```bash
sed -n '303,470p' src/supervaizer/server.py
```

```output
class Server(ServerAbstract):
    def __init__(
        self,
        agents: List[Agent],
        supervisor_account: Optional[Account] = None,
        a2a_endpoints: bool = True,
        admin_interface: bool = True,
        scheme: str = "http",
        environment: str = os.getenv("SUPERVAIZER_ENVIRONMENT", "dev"),
        host: str = os.getenv("SUPERVAIZER_HOST", "0.0.0.0"),
        port: int = int(os.getenv("SUPERVAIZER_PORT", 8000)),
        debug: bool = False,
        reload: bool = False,
        mac_addr: str = "",
        private_key: Optional[RSAPrivateKey] = None,
        public_url: Optional[str] = os.getenv("SUPERVAIZER_PUBLIC_URL", None),
        api_key: Optional[str] = os.getenv(
            "SUPERVAIZER_API_KEY", secrets.token_urlsafe(32)
        ),
        **kwargs: Any,
    ) -> None:
        """Initialize the server with the given configuration.

        Args:
            agents: List of agents to register with the server
            supervisor_account: Account of the supervisor
            a2a_endpoints: Whether to enable A2A endpoints
            admin_interface: Whether to enable admin interface
            scheme: URL scheme (http or https)
            environment: Environment name (e.g., dev, staging, prod)
            host: Host to bind the server to (e.g., 0.0.0.0 for all interfaces)
            port: Port to bind the server to
            debug: Whether to enable debug mode
            reload: Whether to enable auto-reload
            mac_addr: MAC address to use for server identification
            private_key: RSA private key for encryption

            api_key: API key for securing endpoints

        """
        if not mac_addr:
            node_id = uuid.getnode()
            mac_addr = "-".join(
                format(node_id, "012X")[i : i + 2] for i in range(0, 12, 2)
            )

        if private_key is None:
            private_key = _get_or_create_private_key()

        public_key = private_key.public_key()
        log.info(f"[Server launch] Public key: {public_key}")
        log.info(
            f"[Server launch] Public key - decode:  {
                str(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    ).decode('utf-8')
                )
            },"
        )
        # Create root app to handle version prefix
        docs_url = "/docs"  # Swagger UI
        redoc_url = "/redoc"  # ReDoc
        openapi_url = "/openapi.json"

        app = FastAPI(
            debug=debug,
            title="Supervaizer API",
            description=(
                f"API version: {API_VERSION}  Controller version: {VERSION}\n\n"
                "API for controlling and managing Supervaize agents. \n\nMore information at "
                "[https://doc.supervaize.com](https://doc.supervaize.com)\n\n"
                "## Authentication\n\n"
                "Some endpoints require API key authentication. Protected endpoints expect "
                "the API key in the X-API-Key header.\n\n"
                f"[Swagger]({docs_url})\n"
                f"[Redoc]({redoc_url})\n"
                f"[OpenAPI]({openapi_url})\n"
            ),
            version=API_VERSION,
            terms_of_service="https://supervaize.com/terms/",
            contact={
                "name": "Support Team",
                "url": "https://supervaize.com/dev_contact/",
                "email": "integration_support@supervaize.com",
            },
            license_info={
                "name": "Mozilla Public License 2.0",
                "url": "https://mozilla.org/MPL/2.0/",
            },
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
        )

        # Add exception handler for 422 validation errors
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(
            request: Request, exc: RequestValidationError
        ) -> JSONResponse:
            log.error(f"[422 Error] {exc.errors()}")
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors(), "body": exc.body},
            )

        # Create API key header security
        API_KEY_NAME = "X-API-Key"
        api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

        super().__init__(
            scheme=scheme,
            host=host,
            port=port,
            environment=environment,
            mac_addr=mac_addr,
            debug=debug,
            agents=agents,
            app=app,
            reload=reload,
            supervisor_account=supervisor_account,
            a2a_endpoints=a2a_endpoints,
            private_key=private_key,
            public_key=public_key,
            public_url=public_url,
            api_key=api_key,
            api_key_header=api_key_header,
            **kwargs,
        )

        log.info(f"[Server launch] Server ID: {self.server_id}")

        # Create routes
        if self.supervisor_account:
            log.info(
                "[Server launch] 🚀 Deploy Supervaizer routes - also activates A2A routes"
            )
            self.app.include_router(create_default_routes(self))
            self.app.include_router(create_utils_routes(self))
            self.app.include_router(create_agents_routes(self))
            self.a2a_endpoints = True  # Needed by supervaize.
        if self.a2a_endpoints:
            log.info("[Server launch] 📢 Deploy A2A routes  ")
            self.app.include_router(create_a2a_routes(self))

        # Deploy admin routes if API key is available
        if self.api_key and admin_interface:
            log.info(
                f"[Server launch] 💼 Deploy Admin interface @ {self.public_url}/admin"
            )
            self.app.include_router(create_admin_routes(), prefix="/admin")

            # Save server info to storage for admin interface
            save_server_info_to_storage(self)

        # Home page (template in admin/templates)
        _home_templates = Jinja2Templates(
            directory=str(Path(__file__).parent / "admin" / "templates")
        )

        @self.app.get("/", response_class=HTMLResponse)
        async def home_page(request: Request) -> HTMLResponse:
            root_index = Path.cwd() / "index.html"
            if root_index.is_file():
                return HTMLResponse(content=root_index.read_text(encoding="utf-8"))
            base = self.public_url or f"{self.scheme}://{self.host}:{self.port}"
            return _home_templates.TemplateResponse(
```

`Server.__init__` does the full wiring in order:

1. Generate MAC address → stable server fingerprint.
2. Load or generate RSA key pair (from `SUPERVAIZER_PRIVATE_KEY` env or fresh generation).
3. Create a `FastAPI` app with OpenAPI docs.
4. Add a `RequestValidationError` handler for 422 responses.
5. Create `APIKeyHeader` security scheme.
6. **Route registration** (conditional):
   - If `supervisor_account` is set: add supervision routes + agent routes + force A2A on.
   - If `a2a_endpoints`: add A2A discovery routes.
   - If `api_key` and `admin_interface`: add admin routes.
7. Register a home page that serves `index.html` from CWD if present, otherwise a bundled template.

Let's look at `launch()`:

```bash
sed -n '573,645p' src/supervaizer/server.py
```

```output
    def launch(self, log_level: Optional[str] = "INFO") -> None:
        if log_level:
            log.remove()
            log.add(
                sys.stderr,
                colorize=True,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>|<level> {level}</level> | <level>{message}</level>",
                level=log_level,
            )

            # Add log handler for admin streaming if API key is enabled
            if self.api_key:

                def log_queue_handler(message: Any) -> None:
                    record = message.record
                    try:
                        # Import here to avoid circular imports and ensure module is loaded
                        import supervaizer.admin.routes as admin_routes

                        admin_routes.add_log_to_queue(
                            timestamp=record["time"].isoformat(),
                            level=record["level"].name,
                            message=record["message"],
                        )
                    except ImportError:
                        # Silently ignore import errors to avoid breaking logging
                        pass
                    except Exception:
                        # Silently ignore other errors to avoid breaking logging
                        pass

                # Add the handler with a specific format to avoid recursion
                log.add(log_queue_handler, level=log_level, format="{message}")

            log_level = (
                log_level.lower()
            )  # needs to be lower case of uvicorn and uppercase of loguru

        log.info(
            f"[Server launch] Starting Supervaize Controller API v{VERSION} - Log : {log_level} "
        )

        # self.instructions()
        if self.supervisor_account:
            # Register the server with the supervisor account
            server_registration_result: ApiResult = (
                self.supervisor_account.register_server(server=self)
            )
            # log.debug(f"[Server launch] Server registration result: {server_registration_result}")
            # inspect(server_registration_result)
            assert isinstance(
                server_registration_result, ApiSuccess
            )  # If ApiError, exception should have been raised before
            # Get the agent details from the server
            for agent in self.agents:
                updated_agent = agent.update_agent_from_server(self)
                if updated_agent:
                    log.info(f"[Server launch] Updated agent {updated_agent.name}")

        import uvicorn

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            reload=self.reload,
            log_level=log_level,
        )

    def instructions(self) -> None:
        server_url = f"http://{self.host}:{self.port}"
        display_instructions(
            server_url, f"Starting server on {server_url} \n Waiting for instructions.."
```

`launch()` configures Loguru with a coloured stderr sink plus an additional in-memory queue sink that feeds the admin's Server-Sent Events log stream. Then:

1. If a `supervisor_account` is configured, it calls `account.register_server` → `account.register_agent` for each agent (sending `ServerRegisterEvent` and `AgentRegisterEvent` to the SaaS).
2. Starts `uvicorn.run` with the FastAPI app.

---

## 13. Routes (`routes.py`)

FastAPI route factories return `APIRouter` instances that are `include_router`'d into the app.

```bash
grep -n 'def create_\|@router\.' src/supervaizer/routes.py | head -40
```

```output
126:def create_default_routes(server: "Server") -> APIRouter:
130:    @router.get(
151:    @router.get(
203:    @router.post(
282:    @router.get("/agents", response_model=List[AgentResponse])
298:    @router.get("/agent/{agent_id}", response_model=AgentResponse)
318:def create_utils_routes(server: "Server") -> APIRouter:
322:    @router.get(
336:    @router.post(
350:def create_agents_routes(server: "Server") -> APIRouter:
361:def create_agent_route(server: "Server", agent: Agent) -> APIRouter:
373:    @router.get(
389:    @router.get(
437:    @router.post(
546:    @router.post(
632:    @router.post(
680:    @router.get(
724:    @router.get(
755:    @router.post(
784:    @router.post(
808:    @router.post(
839:def create_agent_custom_routes(server: "Server", agent: Agent) -> APIRouter:
863:        @router.post(
```

```bash
sed -n '1,130p' src/supervaizer/routes.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import traceback
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

from cryptography.hazmat.primitives import serialization
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status as http_status,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from supervaizer.agent import (
    Agent,
    AgentMethodParams,
    AgentResponse,
)
from supervaizer.case import CaseNodeUpdate, Cases
from supervaizer.common import SvBaseModel, log
from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.job_service import service_job_custom, service_job_start
from supervaizer.lifecycle import EntityStatus
from supervaizer.server_utils import ErrorResponse, ErrorType, create_error_response

if TYPE_CHECKING:
    from enum import Enum

    from supervaizer.server import Server

T = TypeVar("T")


class CaseUpdateRequest(SvBaseModel):
    """Request model for updating a case with answer to a question."""

    answer: Dict[str, Any]
    message: Optional[str] = None


def handle_route_errors(
    job_conflict_check: bool = False,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Awaitable[Union[T, JSONResponse]]]
]:
    """
    Decorator to handle common route error patterns.

    Args:
        job_conflict_check: If True, checks for "already exists" in ValueError messages
                          and returns a conflict error response
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[Union[T, JSONResponse]]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Union[T, JSONResponse]:
            # log.debug(f"------[DEBUG]----------\n args :{args} \n kwargs :{kwargs}")
            try:
                result: T = await func(*args, **kwargs)
                return result

            except HTTPException as e:
                return create_error_response(
                    error_type=ErrorType.INVALID_REQUEST,
                    detail=e.detail if hasattr(e, "detail") else str(e),
                    status_code=e.status_code,
                )
            except ValueError as e:
                if job_conflict_check and "already exists" in str(e):
                    return create_error_response(
                        ErrorType.JOB_ALREADY_EXISTS,
                        str(e),
                        http_status.HTTP_409_CONFLICT,
                    )
                return create_error_response(
                    error_type=ErrorType.INVALID_REQUEST,
                    detail=str(e),
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    traceback=f"Error at line {traceback.extract_tb(e.__traceback__)[-1].lineno}:\n"
                    f"{traceback.format_exc()}",
                )
            except Exception as e:
                return create_error_response(
                    error_type=ErrorType.INTERNAL_ERROR,
                    detail=str(e),
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    traceback=f"Error at line {traceback.extract_tb(e.__traceback__)[-1].lineno}:\n"
                    f"{traceback.format_exc()}",
                )

        return wrapper

    return decorator


async def get_server() -> "Server":
    """Get the current server instance."""
    raise NotImplementedError("This function should be overridden by the server")


def create_default_routes(server: "Server") -> APIRouter:
    """Create default routes for the server."""
    router = APIRouter(prefix="/supervaizer", tags=["Supervision"])

    @router.get(
```

The `@handle_route_errors` decorator is the key cross-cutting concern in routes. It wraps every async route handler to:
- Catch `HTTPException` → forward with original status code.
- Catch `ValueError` → 400 Bad Request (or 409 Conflict if it contains "already exists" and `job_conflict_check=True`).
- Catch everything else → 500 Internal Server Error.
- Include a full traceback in the error detail for debugging.

Routes are split into four factories:
- `create_default_routes` — platform supervision endpoints at `/supervaizer/`
- `create_utils_routes` — utilities (registration info, public key)
- `create_agents_routes` — iterates agents and calls `create_agent_route` for each
- `create_agent_custom_routes` — custom method endpoints for each agent

Let's look at the job-start route (the most important one):

```bash
sed -n '437,550p' src/supervaizer/routes.py
```

```output
    @router.post(
        "/validate-agent-parameters",
        summary=f"Validate agent parameters for agent: {agent.name}",
        description="Validate agent configuration parameters (secrets, API keys, etc.) before starting a job",
        response_model=Dict[str, Any],
        responses={
            http_status.HTTP_200_OK: {"model": Dict[str, Any]},
            http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def validate_agent_parameters(
        body_params: Any = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> Dict[str, Any]:
        """Validate agent parameters for this agent"""
        log.info(
            f"📥 POST /validate-agent-parameters [Validate agent parameters] {agent.name}"
        )

        if not agent.parameters_setup:
            result = {
                "valid": True,
                "message": "Agent has no parameter setup defined",
                "errors": [],
                "invalid_parameters": {},
            }
            log.info(f"📤 Agent {agent.name}: No parameter setup defined → {result}")
            return result

        if body_params is None:
            body_params = {}

        encrypted_agent_parameters = body_params.get("encrypted_agent_parameters")

        agent_parameters: Dict[str, Any] = {}
        if encrypted_agent_parameters:
            # Basic debug trace
            log.info(
                f"📥 Received encrypted_agent_parameters, length: {len(encrypted_agent_parameters)}"
            )

            try:
                import json

                from supervaizer.common import decrypt_value

                agent_parameters_str = decrypt_value(
                    encrypted_agent_parameters, server.private_key
                )
                agent_parameters = (
                    json.loads(agent_parameters_str) if agent_parameters_str else {}
                )

                # Debug: Log the parsed data type and structure
                log.info(f"🔍 Parsed agent_parameters type: {type(agent_parameters)}")
                if isinstance(agent_parameters, list):
                    log.info(
                        f"🔍 Converting list to dict with {len(agent_parameters)} items"
                    )
                    # Convert list to dict if needed (common when frontend sends array)
                    agent_parameters = {
                        f"param_{i}": param for i, param in enumerate(agent_parameters)
                    }
                elif isinstance(agent_parameters, dict):
                    log.info(
                        f"🔍 Agent parameters keys: {list(agent_parameters.keys())}"
                    )
                else:
                    log.warning(
                        f"🔍 Unexpected type: {type(agent_parameters)}, converting to empty dict"
                    )
                    agent_parameters = {}

            except Exception as e:
                log.error(f"❌ Decryption failed: {type(e).__name__}: {str(e)}")
                result = {
                    "valid": False,
                    "message": f"Failed to decrypt agent parameters: {str(e)}",
                    "errors": [f"Decryption failed: {str(e)}"],
                    "invalid_parameters": {
                        "encrypted_agent_parameters": f"Decryption failed: {str(e)}"
                    },
                }
                log.info(f"📤 Agent {agent.name}: Decryption failed → {result}")
                return result

        # Log the incoming request details
        log.info(
            f"🔍 Agent {agent.name}: Incoming request - encrypted_params: {bool(encrypted_agent_parameters)}, parsed_params: {agent_parameters}"
        )

        # Validate agent parameters
        validation_result = agent.parameters_setup.validate_parameters(agent_parameters)

        result = {
            "valid": validation_result["valid"],
            "message": "Agent parameters validated successfully"
            if validation_result["valid"]
            else "Agent parameter validation failed",
            "errors": validation_result["errors"],
            "invalid_parameters": validation_result["invalid_parameters"],
        }

        log.info(f"📤 Agent {agent.name}: Validation result → {result}")
        return result

    @router.post(
        "/validate-method-fields",
        summary=f"Validate method fields for agent: {agent.name}",
        description="Validate job input fields against the method's field definitions before starting a job",
        response_model=Dict[str, Any],
```

```bash
sed -n '632,730p' src/supervaizer/routes.py
```

```output
    @router.post(
        "/jobs",
        summary=f"Start a job with agent: {agent.name}",
        description=f"{agent.methods.job_start.description}",
        responses={
            http_status.HTTP_202_ACCEPTED: {"model": Job},
            http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
            http_status.HTTP_409_CONFLICT: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        response_model=Job,
        status_code=http_status.HTTP_202_ACCEPTED,
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors(job_conflict_check=True)
    async def start_job(
        background_tasks: BackgroundTasks,
        body_params: Any = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> Union[Job, JSONResponse]:
        """Start a new job for this agent"""
        log.info(f"📥 POST /jobs [Start job] {agent.name} with params {body_params}")

        if body_params is None:
            body_params = {}

        job_context_data = body_params.get("job_context")
        if job_context_data is None:
            raise ValueError("job_context is required")

        sv_context: JobContext = JobContext(**job_context_data)
        job_fields = body_params.get("job_fields", {})

        # Get job encrypted parameters if available
        encrypted_agent_parameters = body_params.get("encrypted_agent_parameters")

        # Delegate job creation and scheduling to the service
        new_job = await service_job_start(
            server,
            background_tasks,
            agent,
            sv_context,
            job_fields,
            encrypted_agent_parameters,
        )

        return new_job

    @router.get(
        "/jobs",
        summary=f"Get all jobs for agent: {agent.name}",
        description="Get all jobs for this agent with pagination and optional status filtering",
        response_model=List[JobResponse],
        responses={
            http_status.HTTP_200_OK: {"model": List[JobResponse]},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_agent_jobs(
        agent: Agent = Depends(get_agent),
        skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
        limit: int = Query(
            default=100, ge=1, le=1000, description="Number of jobs to return"
        ),
        status: EntityStatus | None = Query(
            default=None, description="Filter jobs by status"
        ),
    ) -> List[JobResponse] | JSONResponse:
        """Get all jobs for this agent"""
        log.info(f"📥  GET /jobs [Get agent jobs] {agent.name}")
        jobs = list(Jobs().get_agent_jobs(agent.name).values())

        # Apply status filter if specified
        if status:
            jobs = [job for job in jobs if job.status == status]

        # Apply pagination
        jobs = jobs[skip : skip + limit]

        # Convert Job objects to JobResponse objects
        return [
            JobResponse(
                job_id=job.id,
                status=job.status,
                message=f"Job {job.id} status: {job.status.value}",
                payload=job.payload,
            )
            for job in jobs
        ]

    @router.get(
        "/jobs/{job_id}",
        summary=f"Get job status for agent: {agent.name}",
        description="Get the status and details of a specific job",
        response_model=JobResponse,
        responses={
            http_status.HTTP_200_OK: {"model": Job},
```

The `POST /jobs` route (202 Accepted) follows a clean pattern:
1. Parse `job_context` and `job_fields` from the JSON body.
2. Optionally extract `encrypted_agent_parameters`.
3. Hand off to `service_job_start` — the route stays thin, all logic lives in the service.
4. Return the `Job` object immediately (202 means "accepted, processing asynchronously").

The actual agent work runs in a `BackgroundTasks` worker so the HTTP response returns before the job completes.

---

## 14. Job Service (`job_service.py`)

The service layer decouples route handlers from domain logic.

```bash
cat src/supervaizer/job_service.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
from typing import TYPE_CHECKING, Any, Dict, Optional


from supervaizer.common import decrypt_value, log
from supervaizer.event import JobFinishedEvent
from supervaizer.job import Job, Jobs
from supervaizer.lifecycle import EntityStatus

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

    from supervaizer.agent import Agent
    from supervaizer.job import JobContext
    from supervaizer.server import Server


async def service_job_start(
    server: "Server",
    background_tasks: "BackgroundTasks",
    agent: "Agent",
    sv_context: "JobContext",
    job_fields: Dict[str, Any],
    encrypted_agent_parameters: Optional[str] = None,
) -> "Job":
    """
    Create a new job and schedule its execution.

    Args:
        server: The server instance
        background_tasks: FastAPI background tasks
        agent: The agent to run the job
        sv_context: The supervaize context
        job_fields: Fields for the job
        encrypted_agent_parameters: Optional encrypted parameters

    Returns:
        The created job
    """
    agent_parameters = None
    # If agent has parameters_setup defined, validate parameters
    if getattr(agent, "parameters_setup") and encrypted_agent_parameters:
        agent_parameters_str = decrypt_value(
            encrypted_agent_parameters, server.private_key
        )
        agent_parameters = (
            json.loads(agent_parameters_str) if agent_parameters_str else None
        )

        # inspect(agent)
        # log.debug(
        #    f"[service_job_start Decrypted parameters] : parameters = {agent_parameters}"
        # )

    # Create and prepare the job
    new_saas_job = Job.new(
        job_context=sv_context,
        agent_name=agent.name,
        agent_parameters=agent_parameters,
        name=sv_context.job_id,
    )

    # Start the background execution
    background_tasks.add_task(
        agent.job_start, new_saas_job, job_fields, sv_context, server
    )
    return new_saas_job


def service_job_finished(job: Job, server: "Server") -> None:
    """
    Service to handle the completion of a job.

    Args:
        job: The job that has finished
        server: The server instance

    Tested in tests/test_job_service.py
    """
    assert server.supervisor_account is not None, "No account defined"
    account = server.supervisor_account
    event = JobFinishedEvent(
        job=job,
        account=account,
    )
    account.send_event(sender=job, event=event)


async def service_job_custom(
    method_name: str,
    server: "Server",
    background_tasks: "BackgroundTasks",
    agent: "Agent",
    sv_context: "JobContext",
    job_fields: Dict[str, Any],
    encrypted_agent_parameters: Optional[str] = None,
) -> "Job":
    """
    Create a new job and schedule its execution for a custom method.

    Args:
        server: The server instance
        background_tasks: FastAPI background tasks
        agent: The agent to run the job
        sv_context: The supervaize context
        job_fields: Fields for the job
        encrypted_agent_parameters: Optional encrypted parameters

    Returns:
        The created job
    """
    log.info(
        f"[service_job_custom] /custom/{method_name} [custom job] {agent.name} with params {job_fields}"
    )
    _agent_parameters: dict[str, Any] | None = None
    # If agent has parameters_setup defined, validate parameters
    if getattr(agent, "parameters_setup") and encrypted_agent_parameters:
        agent_parameters_str = decrypt_value(
            encrypted_agent_parameters, server.private_key
        )
        _agent_parameters = (
            json.loads(agent_parameters_str) if agent_parameters_str else None
        )
        log.debug("[Decrypted parameters] : parameters decrypted")

    # Create and prepare the job
    job_id = sv_context.job_id

    if not job_id:
        raise ValueError(
            "[service_job_custom] Job ID is required to start a custom job"
        )

    job = Jobs().get_job(job_id) or Job(
        id=job_id,
        job_context=sv_context,
        agent_name=agent.name,
        name=sv_context.mission_name,
        status=EntityStatus.STOPPED,
    )  # TODO clean the name
    # Start the background execution
    background_tasks.add_task(
        agent.job_start,
        job,
        job_fields,
        sv_context,
        server,
        method_name,
    )
    return job
```

`service_job_start` in three lines conceptually:
1. Decrypt parameters if present.
2. `Job.new()` creates and registers the job.
3. `background_tasks.add_task(agent.job_start, ...))` enqueues the actual agent execution.

`service_job_finished` is called after the background task completes — it fires a `JobFinishedEvent` to the platform.

`service_job_custom` is the same pattern but looks up or creates the job by ID (custom methods can attach to an existing job), then dispatches to a named method instead of the default `job_start`.

---

## 15. A2A Protocol (`protocol/a2a/`)

The Agent-to-Agent protocol exposes discovery endpoints so other agents can find and call this one.

```bash
find src/supervaizer/protocol -name '*.py' | sort | xargs grep -n 'class \|def \|@router' | head -40
```

```output
src/supervaizer/protocol/a2a/model.py:14:def create_agent_card(agent: Agent, base_url: str) -> Dict[str, Any]:
src/supervaizer/protocol/a2a/model.py:131:def create_agents_list(agents: List[Agent], base_url: str) -> Dict[str, Any]:
src/supervaizer/protocol/a2a/model.py:157:def create_health_data(agents: List[Agent]) -> Dict[str, Any]:
src/supervaizer/protocol/a2a/routes.py:24:def create_routes(server: "Server") -> APIRouter:
src/supervaizer/protocol/a2a/routes.py:29:    @router.get(
src/supervaizer/protocol/a2a/routes.py:36:    async def get_a2a_agents() -> Dict[str, Any]:
src/supervaizer/protocol/a2a/routes.py:42:    @router.get(
src/supervaizer/protocol/a2a/routes.py:49:    async def get_health() -> Dict[str, Any]:
src/supervaizer/protocol/a2a/routes.py:57:        def create_agent_route_versioned(current_agent: "Agent") -> None:
src/supervaizer/protocol/a2a/routes.py:62:            @router.get(
src/supervaizer/protocol/a2a/routes.py:69:            async def get_agent_card() -> Dict[str, Any]:
src/supervaizer/protocol/a2a/routes.py:78:        def create_agent_route_legacy(current_agent: "Agent") -> None:
src/supervaizer/protocol/a2a/routes.py:81:            @router.get(
src/supervaizer/protocol/a2a/routes.py:88:            async def get_agent_card_legacy() -> Dict[str, Any]:
```

```bash
cat src/supervaizer/protocol/a2a/model.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from datetime import datetime
from typing import Any, Dict, List

from supervaizer.agent import Agent
from supervaizer.job import EntityStatus, Jobs


def create_agent_card(agent: Agent, base_url: str) -> Dict[str, Any]:
    """
    Create an A2A agent card for the given agent.

    This follows the A2A protocol as defined in:
    https://github.com/google/A2A/blob/main/specification/json/a2a.json

    Args:
        agent: The Agent instance
        base_url: The base URL of the server

    Returns:
        A dictionary representing the agent card in A2A format
    """
    # Construct the agent URL
    agent_url = f"{base_url}{agent.path}"

    # Build API endpoints object with OpenAPI integration
    api_endpoints = [
        {
            "type": "json",
            "url": agent_url,
            "name": "Supervaize API - A2A protocol support",
            "description": f"RESTful API for {agent.name} agent",
            "openapi_url": f"{base_url}/openapi.json",
            "docs_url": f"{base_url}/docs",
            "examples": [
                {
                    "name": "Get agent info",
                    "description": "Retrieve information about the agent",
                    "request": {"method": "GET", "url": agent_url},
                },
                {
                    "name": "Start a job",
                    "description": "Start a new job with this agent",
                    "request": {"method": "POST", "url": f"{agent_url}/jobs"},
                },
            ],
        }
    ]

    # Build the tools object based on agent methods
    tools = []

    # Add basic job tools
    tools.append({
        "name": "job_start",
        "description": (agent.methods.job_start.description if agent.methods else None)
        or f"Start a job with {agent.name}",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_fields": {"type": "object"},
                "job_context": {"type": "object"},
            },
        },
    })

    tools.append({
        "name": "job_status",
        "description": "Check the status of a job",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
        },
    })

    # Add custom tools if available
    if agent.methods and agent.methods.custom:
        for name, method in agent.methods.custom.items():
            tools.append({
                "name": name,
                "description": method.description or f"Execute {name} custom method",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "method_name": {"type": "string", "const": name},
                        "params": {"type": "object"},
                    },
                },
            })

    # Build authentication object
    authentication = {
        "type": "none",
        "description": "Authentication is handled at the Supervaize server level",
    }

    # Version information
    version_info = {
        "current": agent.version,
        "latest": agent.version,
        "changelog_url": f"{base_url}/changelog/{agent.slug}",
    }

    # Create the main agent card
    agent_card = {
        "name": agent.name,
        "description": agent.description,
        "developer": {
            "name": agent.developer or agent.author or "Supervaize",
            "url": "https://supervaize.com/",
            "email": "info@supervaize.com",
        },
        "version": agent.version,
        "version_info": version_info,
        "logo_url": f"{base_url}/static/agents/{agent.slug}_logo.png",
        "human_url": f"{base_url}/agents/{agent.slug}",
        "contact_information": {"general": {"email": "support@supervaize.com"}},
        "api_endpoints": api_endpoints,
        "tools": tools,
        "authentication": authentication,
    }

    return agent_card


def create_agents_list(agents: List[Agent], base_url: str) -> Dict[str, Any]:
    """
    Create an A2A agents list for all available agents.

    Args:
        agents: List of Agent instances
        base_url: The base URL of the server

    Returns:
        A dictionary representing the list of agent cards in A2A format
    """
    return {
        "schema_version": "a2a_2023_v1",
        "agents": [
            {
                "name": agent.name,
                "description": agent.description,
                "developer": agent.developer or agent.author or "Supervaize",
                "version": agent.version,
                "agent_card_url": f"{base_url}/.well-known/agents/v{agent.version}/{agent.slug}_agent.json",
            }
            for agent in agents
        ],
    }


def create_health_data(agents: List[Agent]) -> Dict[str, Any]:
    """
    Create health data for all agents according to A2A protocol.

    Args:
        agents: List of Agent instances

    Returns:
        A dictionary with health information for all agents
    """
    jobs_registry = Jobs()

    agents_health = {}
    for agent in agents:
        # Get agent jobs
        agent_jobs = jobs_registry.get_agent_jobs(agent.name)

        # Calculate job statistics
        total_jobs = len(agent_jobs)
        completed_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.COMPLETED
        )
        failed_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.FAILED
        )
        in_progress_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.IN_PROGRESS
        )

        # Set agent status based on health indicators
        if total_jobs == 0:
            status = "available"
        elif failed_jobs > total_jobs / 2:  # If more than half are failing
            status = "degraded"
        elif in_progress_jobs > 0:
            status = "busy"
        else:
            status = "available"

        agents_health[agent.id] = {
            "agent_id": agent.id,
            "agent_server_id": agent.server_agent_id,
            "name": agent.name,
            "status": status,
            "version": agent.version,
            "statistics": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "in_progress_jobs": in_progress_jobs,
                "success_rate": (completed_jobs / total_jobs * 100)
                if total_jobs > 0
                else 100,
            },
        }

    return {
        "schema_version": "a2a_2023_v1",
        "status": "operational",
        "timestamp": str(datetime.now()),
        "agents": agents_health,
    }
```

The A2A model creates three kinds of documents from in-memory data:

- **Agent Card** — a self-describing JSON document per agent, listing endpoints, tools (job_start, job_status, custom methods), and auth info.
- **Agents List** — a directory of all agents on the server with URLs to their cards.
- **Health Data** — live statistics computed from the `Jobs` registry: total/completed/failed/in-progress counts, success rate, and a simple `status` label (`available`, `busy`, `degraded`).

These serve `GET /.well-known/agents.json` and `GET /.well-known/health` — standard A2A discovery URLs that allow agent orchestrators to discover capabilities dynamically.

---

## 16. Telemetry (`telemetry.py`)

A structured observability model for emitting typed monitoring data.

```bash
grep -n 'class \|Enum' src/supervaizer/telemetry.py | head -30
```

```output
8:from enum import Enum
18:class TelemetryType(str, Enum):
28:class TelemetryCategory(str, Enum):
39:class TelemetrySeverity(str, Enum):
47:class TelemetryModel(BaseModel):
56:class Telemetry(TelemetryModel):
57:    """Base class for all telemetry data in the Supervaize Control system.
```

```bash
cat src/supervaizer/telemetry.py
```

```output
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from enum import Enum
from typing import Any, ClassVar, Dict

from pydantic import BaseModel

from supervaizer.__version__ import VERSION

# TODO: Uuse OpenTelemetry  / OpenInference standard  - Consider connecting to Arize Phoenix observability backend for storage and visualization.


class TelemetryType(str, Enum):
    LOGS = "logs"
    METRICS = "metrics"
    EVENTS = "events"
    TRACES = "traces"
    EXCEPTIONS = "exceptions"
    DIAGNOSTICS = "diagnostics"
    CUSTOM = "custom"


class TelemetryCategory(str, Enum):
    SYSTEM = "system"
    APPLICATION = "application"
    USER_INTERACTION = "user_interaction"
    SECURITY = "security"
    BUSINESS = "business"
    ENVIRONMENT = "environment"
    NETWORKING = "networking"
    CUSTOM = "custom"


class TelemetrySeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TelemetryModel(BaseModel):
    supervaizer_VERSION: ClassVar[str] = VERSION
    agentId: str
    type: TelemetryType
    category: TelemetryCategory
    severity: TelemetrySeverity
    details: Dict[str, Any]


class Telemetry(TelemetryModel):
    """Base class for all telemetry data in the Supervaize Control system.

    Telemetry represents monitoring and observability data sent from agents to the control system.
    This includes logs, metrics, events, traces, exceptions, diagnostics and custom telemetry.

    Inherits from TelemetryModel which defines the core telemetry attributes:
        - agentId: The ID of the agent sending the telemetry
        - type: The TelemetryType enum indicating the telemetry category (logs, metrics, etc)
        - category: The TelemetryCategory enum for the functional area (system, application, etc)
        - severity: The TelemetrySeverity enum indicating importance (debug, info, warning, etc)
        - details: A dictionary containing telemetry-specific details
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def payload(self) -> Dict[str, Any]:
        return {
            "agentId": self.agentId,
            "eventType": self.type.value,
            "severity": self.severity.value,
            "eventCategory": self.category.value,
            "details": self.details,
        }
```

Telemetry is a simple typed container — a `Pydantic BaseModel` with three classifying enums (`TelemetryType`, `TelemetryCategory`, `TelemetrySeverity`) and a free-form `details` dict. It serializes to a platform-friendly `payload` dict via the property.

The TODO comment mentions a future migration to **OpenTelemetry** / **OpenInference** standards with Arize Phoenix as the backend — the current design is kept minimal to make that migration straightforward.

---

## 17. Admin Interface (`admin/routes.py`)

A web-based dashboard served at `/admin/` for monitoring jobs, cases, and server logs.

```bash
grep -n '@router\.\|def \|async def ' src/supervaizer/admin/routes.py | head -40
```

```output
50:def set_server_start_time(start_time: float) -> None:
56:def add_log_to_queue(timestamp: str, level: str, message: str) -> None:
126:async def verify_admin_access(
157:def format_uptime(seconds: int) -> str:
171:def _get_server_info(request: Optional[Request]) -> Optional[Any]:
188:def get_server_status(request: Optional[Request] = None) -> ServerStatus:
234:def get_server_configuration(
256:def create_admin_routes() -> APIRouter:
265:    @router.get("/", response_class=HTMLResponse)
266:    async def admin_dashboard(request: Request) -> Response:
290:    @router.get("/jobs", response_class=HTMLResponse)
291:    async def admin_jobs_page(request: Request) -> Response:
303:    @router.get("/cases", response_class=HTMLResponse)
304:    async def admin_cases_page(request: Request) -> Response:
316:    @router.get("/server", response_class=HTMLResponse)
317:    async def admin_server_page(request: Request) -> Response:
339:    @router.get("/agents", response_class=HTMLResponse)
340:    async def admin_agents_page(request: Request) -> Response:
365:    @router.get("/job-start-test", response_class=HTMLResponse)
366:    async def admin_job_start_test_page(request: Request) -> Response:
378:    @router.get("/static/js/job-start-form.js")
379:    async def serve_job_start_form_js() -> Response:
389:    @router.get("/console", response_class=HTMLResponse)
390:    async def admin_console_page(request: Request) -> Response:
405:    @router.get("/api/stats")
406:    async def get_stats() -> AdminStats:
410:    @router.get("/api/server/status")
411:    async def get_server_status_api(request: Request) -> Response:
428:    @router.post("/api/server/register")
429:    async def register_server_with_supervisor(request: Request) -> JSONResponse:
479:    @router.get("/api/agents")
480:    async def get_agents_api(
551:    @router.get("/api/agents/{agent_slug}")
552:    async def get_agent_details(
589:    @router.get("/api/jobs")
590:    async def get_jobs_api(
676:    @router.get("/api/jobs/{job_id}")
677:    async def get_job_details(request: Request, job_id: str) -> Response:
703:    @router.get("/api/cases")
704:    async def get_cases_api(
```

```bash
sed -n '50,90p' src/supervaizer/admin/routes.py
```

```output
def set_server_start_time(start_time: float) -> None:
    """Set the server start time for uptime calculation."""
    global SERVER_START_TIME
    SERVER_START_TIME = start_time


def add_log_to_queue(timestamp: str, level: str, message: str) -> None:
    """Add a log message to the streaming queue."""
    try:
        log_data = {"timestamp": timestamp, "level": level, "message": message}
        # Non-blocking put - if queue is full, skip the message
        try:
            log_queue.put_nowait(log_data)
        except asyncio.QueueFull:
            pass  # Skip if queue is full
    except Exception:
        pass  # Silently ignore errors to avoid breaking logging


# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# API key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AdminStats(BaseModel):
    """Statistics for admin dashboard."""

    jobs: Dict[str, int]
    cases: Dict[str, int]
    collections: int


class ServerStatus(BaseModel):
    """Server status and metrics."""

    status: str
    uptime: str
    uptime_seconds: int
    memory_usage: str
```

```bash
grep -n 'logs\|SSE\|EventSource\|log_queue' src/supervaizer/admin/routes.py | head -20
```

```output
28:from sse_starlette.sse import EventSourceResponse
40:log_queue: asyncio.Queue[Dict[str, str]] = asyncio.Queue()
62:            log_queue.put_nowait(log_data)
974:    ) -> EventSourceResponse:
1029:                while not log_queue.empty():
1031:                        log_message = log_queue.get_nowait()
1053:                            log_queue.get(), timeout=30.0
1097:        return EventSourceResponse(generate_log_events())
1141:        queue_size = log_queue.qsize()
1152:            "queue_size_after": log_queue.qsize(),
```

```bash
sed -n '974,1060p' src/supervaizer/admin/routes.py
```

```output
    ) -> EventSourceResponse:
        """Stream log messages via Server-Sent Events."""

        # Support both console token and API key authentication
        auth_valid = False
        auth_method = None

        if token:
            auth_valid = validate_console_token(token)
            auth_method = "console_token"
            # If token validation fails, fall back to admin console mode
            if not auth_valid:
                auth_valid = True
                auth_method = "admin_console_fallback"
        elif key:
            # Use API key validation
            try:
                from supervaizer.server import get_server_info_from_storage

                server_info = get_server_info_from_storage()
                if (
                    server_info
                    and hasattr(server_info, "api_key")
                    and key == server_info.api_key
                ):
                    auth_valid = True
                    auth_method = "api_key"
            except Exception:
                # Fallback: just check if key is provided for now
                if key:
                    auth_valid = True
                    auth_method = "api_key_fallback"
        else:
            # Allow access without authentication for admin interface live console
            # In a production environment, you might want to add additional security
            auth_valid = True
            auth_method = "admin_console"

        if not auth_valid:
            raise HTTPException(
                status_code=403,
                detail=f"Invalid or expired authentication token (method: {auth_method or 'none'})",
            )

        async def generate_log_events() -> AsyncGenerator[str, None]:
            try:
                # Send connection message immediately
                test_message = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": f"Log stream connected using {auth_method}",
                }
                yield f"data: {json.dumps(test_message, ensure_ascii=False)}\n\n"

                # Send any existing messages in the queue
                while not log_queue.empty():
                    try:
                        log_message = log_queue.get_nowait()
                        if isinstance(log_message, dict):
                            event_data = json.dumps(log_message, ensure_ascii=False)
                            yield f"data: {event_data}\n\n"
                        else:
                            fallback_message = {
                                "timestamp": datetime.now().isoformat(),
                                "level": "INFO",
                                "message": str(log_message),
                            }
                            event_data = json.dumps(
                                fallback_message, ensure_ascii=False
                            )
                            yield f"data: {event_data}\n\n"
                    except Exception:  # QueueEmpty or any other exception
                        break

                # Keep alive and wait for new messages
                while True:
                    try:
                        # Wait for a log message with timeout to send keep-alive
                        log_message = await asyncio.wait_for(
                            log_queue.get(), timeout=30.0
                        )

                        if isinstance(log_message, dict):
                            event_data = json.dumps(log_message, ensure_ascii=False)
                            yield f"data: {event_data}\n\n"
                        else:
                            fallback_message = {
```

The real-time log console uses **Server-Sent Events (SSE)**:

1. During `Server.launch()`, a Loguru sink is registered that calls `admin_routes.add_log_to_queue()` for every log message — this puts a `{timestamp, level, message}` dict into a global `asyncio.Queue`.
2. The SSE endpoint (`/admin/api/logs`) drains the queue in an async generator using `asyncio.wait_for(..., timeout=30)` — a 30-second heartbeat keeps the connection alive.
3. The browser JavaScript subscribes with `EventSource` and appends entries to the console UI.

The queue is capped — when full, new messages are silently dropped (`put_nowait` + `asyncio.QueueFull`) to avoid blocking the logger.

---

## 18. Deployment (`deploy/`)

The `deploy` subpackage automates Docker build → push → cloud deploy.

```bash
find src/supervaizer/deploy -name '*.py' | sort | grep -v __pycache__
```

```output
src/supervaizer/deploy/__init__.py
src/supervaizer/deploy/cli.py
src/supervaizer/deploy/commands/__init__.py
src/supervaizer/deploy/commands/clean.py
src/supervaizer/deploy/commands/down.py
src/supervaizer/deploy/commands/local.py
src/supervaizer/deploy/commands/plan.py
src/supervaizer/deploy/commands/status.py
src/supervaizer/deploy/commands/up.py
src/supervaizer/deploy/docker.py
src/supervaizer/deploy/driver_factory.py
src/supervaizer/deploy/drivers/__init__.py
src/supervaizer/deploy/drivers/aws_app_runner.py
src/supervaizer/deploy/drivers/base.py
src/supervaizer/deploy/drivers/cloud_run.py
src/supervaizer/deploy/drivers/do_app_platform.py
src/supervaizer/deploy/health.py
src/supervaizer/deploy/state.py
src/supervaizer/deploy/templates/debug_env.py
src/supervaizer/deploy/utils.py
```

```bash
grep -n 'class \|def ' src/supervaizer/deploy/drivers/base.py
```

```output
21:class ActionType(str, Enum):
30:class ResourceType(str, Enum):
40:class ResourceAction:
51:class DeploymentPlan(BaseModel):
77:class DeploymentResult(BaseModel):
98:class BaseDriver(ABC):
101:    def __init__(self, region: str, project_id: Optional[str] = None):
107:    def plan_deployment(
120:    def deploy_service(
134:    def destroy_service(
144:    def get_service_status(
153:    def verify_health(self, service_url: str, timeout: int = 60) -> bool:
157:    def verify_health_enhanced(
181:    def check_prerequisites(self) -> List[str]:
185:    def get_service_key(self, service_name: str, environment: str) -> str:
189:    def validate_configuration(self, **kwargs: Any) -> List[str]:
```

```bash
sed -n '98,200p' src/supervaizer/deploy/drivers/base.py
```

```output
class BaseDriver(ABC):
    """Base interface for deployment drivers."""

    def __init__(self, region: str, project_id: Optional[str] = None):
        """Initialize the driver."""
        self.region = region
        self.project_id = project_id

    @abstractmethod
    def plan_deployment(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None,
    ) -> DeploymentPlan:
        """Plan deployment changes without applying them."""
        pass

    @abstractmethod
    def deploy_service(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> DeploymentResult:
        """Deploy or update the service."""
        pass

    @abstractmethod
    def destroy_service(
        self,
        service_name: str,
        environment: str,
        keep_secrets: bool = False,
    ) -> DeploymentResult:
        """Destroy the service and cleanup resources."""
        pass

    @abstractmethod
    def get_service_status(
        self,
        service_name: str,
        environment: str,
    ) -> DeploymentResult:
        """Get current service status and health."""
        pass

    @abstractmethod
    def verify_health(self, service_url: str, timeout: int = 60) -> bool:
        """Verify service health by checking the health endpoint."""
        pass

    def verify_health_enhanced(
        self,
        service_url: str,
        api_key: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 5,
    ) -> bool:
        """
        Enhanced health verification with retry logic and exponential backoff.

        Args:
            service_url: Base URL of the service
            api_key: Optional API key for authenticated endpoints
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts

        Returns:
            True if service is healthy, False otherwise
        """
        from supervaizer.deploy.health import verify_service_health

        return verify_service_health(service_url, api_key, timeout, max_retries)

    @abstractmethod
    def check_prerequisites(self) -> List[str]:
        """Check prerequisites and return list of missing requirements."""
        pass

    def get_service_key(self, service_name: str, environment: str) -> str:
        """Generate a unique key for the service."""
        return f"{service_name}-{environment}"

    def validate_configuration(self, **kwargs: Any) -> List[str]:
        """Validate driver configuration and return list of errors."""
        errors = []

        if not self.region:
            errors.append("Region is required")

        return errors
```

```bash
grep -n 'class \|def ' src/supervaizer/deploy/commands/up.py | head -20
```

```output
31:def deploy_up(
194:def _get_default_region(platform: str) -> str:
204:def _generate_image_tag(service_name: str, environment: str) -> str:
210:def _generate_secrets(
227:def _generate_api_key() -> str:
233:def _generate_rsa_key() -> str:
252:def _get_default_env_vars(environment: str) -> dict[str, str]:
262:def _display_deployment_result(result: DeploymentResult) -> None:
```

```bash
sed -n '31,100p' src/supervaizer/deploy/commands/up.py
```

```output
def deploy_up(
    platform: str,
    name: Optional[str] = None,
    env: str = "dev",
    region: Optional[str] = None,
    project_id: Optional[str] = None,
    image: Optional[str] = None,
    port: int = 8000,
    generate_api_key: bool = False,
    generate_rsa: bool = False,
    yes: bool = False,
    no_rollback: bool = False,
    timeout: int = 300,
    verbose: bool = False,
    source_dir: Optional[Path] = None,
) -> None:
    """Deploy or update the service."""
    # Validate platform
    if platform not in get_supported_platforms():
        console.print(f"[bold red]Error:[/] Unsupported platform: {platform}")
        console.print(f"Supported platforms: {', '.join(get_supported_platforms())}")
        return

    # Set defaults
    if not name:
        name = (source_dir or Path.cwd()).name
    if not region:
        region = _get_default_region(platform)

    console.print(f"[bold green]Deploying to {platform}[/bold green]")
    console.print(f"Service name: {name}")
    console.print(f"Environment: {env}")
    console.print(f"Region: {region}")
    console.print(f"Port: {port}")
    if project_id:
        console.print(f"Project ID: {project_id}")
    if image:
        console.print(f"Image: {image}")

    try:
        # Check Docker
        if not ensure_docker_running():
            console.print("[bold red]Error:[/] Docker is not running")
            return

        # Create deployment directory
        deployment_dir = create_deployment_directory(source_dir or Path.cwd())
        state_manager = StateManager(deployment_dir)

        # Create driver
        driver = create_driver(platform, region, project_id)

        # Check prerequisites
        prerequisites = driver.check_prerequisites()
        if prerequisites:
            console.print("[bold red]Prerequisites not met:[/]")
            for prereq in prerequisites:
                console.print(f"  • {prereq}")
            return

        # Generate image tag
        if not image:
            image = _generate_image_tag(name, env)

        # Generate secrets
        secrets_dict = _generate_secrets(name, env, generate_api_key, generate_rsa)

        # Build and push Docker image
        with Progress(
            SpinnerColumn(),
```

```bash
sed -n '100,145p' src/supervaizer/deploy/commands/up.py
```

```output
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building Docker image...", total=None)

            docker_manager = DockerManager()

            # Generate Docker files
            dockerfile_path = deployment_dir / "Dockerfile"
            dockerignore_path = deployment_dir / ".dockerignore"
            compose_path = deployment_dir / "docker-compose.yml"

            docker_manager.generate_dockerfile(
                output_path=dockerfile_path,
                app_port=port,
            )
            docker_manager.generate_dockerignore(dockerignore_path)
            docker_manager.generate_docker_compose(
                compose_path,
                port=port,
                service_name=name,
                environment=env,
                api_key=secrets_dict.get("api_key", "test-api-key"),
                rsa_key=secrets_dict.get("rsa_private_key", "test-rsa-key"),
            )

            # Build image
            progress.update(task, description="Building Docker image...")

            # Get build arguments for environment variables
            from supervaizer.deploy.docker import get_docker_build_args

            build_args = get_docker_build_args(port)

            docker_manager.build_image(
                image, source_dir or Path.cwd(), dockerfile_path, build_args=build_args
            )

            # Push image (this would be platform-specific)
            progress.update(task, description="Pushing Docker image...")
            # Note: Actual push would depend on the platform's registry

        # Deploy service
        with Progress(
            SpinnerColumn(),
```

```python3
/tmp/flow_summary.py
```

```output
  File "<string>", line 1
    /tmp/flow_summary.py
    ^
SyntaxError: invalid syntax
```

```bash
python3 -c "
lines = [
    '# End-to-end job flow (pseudocode summary)',
    '',
    '# 1. Startup',
    'cli.start()',
    '  -> sets SUPERVAIZER_* env vars',
    '  -> subprocess runs supervaizer_control.py',
    '    -> Server.__init__(agents, account)   # build FastAPI app, register routes',
    '    -> Server.launch()                    # register with platform, start uvicorn',
    '',
    '# 2. Inbound job request',
    'POST /agents/{name}/jobs  {job_context, job_fields, encrypted_agent_parameters}',
    '  -> routes.start_job()',
    '    -> service_job_start()',
    '      -> decrypt_value(encrypted_agent_parameters, server.private_key)',
    '      -> Job.new()  # creates Job, registers in Jobs(), persists',
    '      -> background_tasks.add_task(agent.job_start, ...)',
    '  <- HTTP 202 Accepted {job}',
    '',
    '# 3. Background execution',
    'agent.job_start(job, job_fields, context, server)',
    '  -> account.send_event(JobStartConfirmationEvent)',
    '  -> job.add_response(IN_PROGRESS)  # update status + persist',
    '  -> Agent._execute(dotted_path, params)',
    '    -> __import__(module).function(**params)  # user code runs',
    '    -> returns JobResponse',
    '  -> Case.start(job_id)  # create case, fire CaseStartEvent',
    '  -> case.update(CaseNodeUpdate())  # send live updates',
    '  -> case.close(result)  # COMPLETED, send final delivery',
    '  -> job.add_response(COMPLETED)',
    '  -> service_job_finished(job, server)',
    '    -> account.send_event(JobFinishedEvent)',
    '',
    '# 4. Polling',
    'GET /agents/{name}/jobs/{job_id}',
    '  -> Jobs().get_job(job_id)',
    '  <- JobResponse {status, payload}',
]
print('\n'.join(lines))
"
```

```output
# End-to-end job flow (pseudocode summary)

# 1. Startup
cli.start()
  -> sets SUPERVAIZER_* env vars
  -> subprocess runs supervaizer_control.py
    -> Server.__init__(agents, account)   # build FastAPI app, register routes
    -> Server.launch()                    # register with platform, start uvicorn

# 2. Inbound job request
POST /agents/{name}/jobs  {job_context, job_fields, encrypted_agent_parameters}
  -> routes.start_job()
    -> service_job_start()
      -> decrypt_value(encrypted_agent_parameters, server.private_key)
      -> Job.new()  # creates Job, registers in Jobs(), persists
      -> background_tasks.add_task(agent.job_start, ...)
  <- HTTP 202 Accepted {job}

# 3. Background execution
agent.job_start(job, job_fields, context, server)
  -> account.send_event(JobStartConfirmationEvent)
  -> job.add_response(IN_PROGRESS)  # update status + persist
  -> Agent._execute(dotted_path, params)
    -> __import__(module).function(**params)  # user code runs
    -> returns JobResponse
  -> Case.start(job_id)  # create case, fire CaseStartEvent
  -> case.update(CaseNodeUpdate())  # send live updates
  -> case.close(result)  # COMPLETED, send final delivery
  -> job.add_response(COMPLETED)
  -> service_job_finished(job, server)
    -> account.send_event(JobFinishedEvent)

# 4. Polling
GET /agents/{name}/jobs/{job_id}
  -> Jobs().get_job(job_id)
  <- JobResponse {status, payload}
```

This is the complete request journey through the system.

---

## 20. Key Design Patterns

Let's collect the recurring patterns across the codebase:

```bash
grep -rn '@singleton\|class Jobs\|class Cases\|class StorageManager' src/supervaizer/ | grep -v __pycache__ | head -15
```

```output
src/supervaizer/storage.py:51:@singleton
src/supervaizer/storage.py:52:class StorageManager:
src/supervaizer/case.py:367:@singleton
src/supervaizer/case.py:368:class Cases:
src/supervaizer/job.py:26:@singleton
src/supervaizer/job.py:27:class Jobs:
```

```bash
grep -n 'from_list\|from_dict\|\.new(' src/supervaizer/*.py | grep -v __pycache__ | head -20
```

```output
src/supervaizer/agent.py:531:        parameters_setup=ParametersSetup.from_list([
src/supervaizer/job_service.py:62:    new_saas_job = Job.new(
src/supervaizer/parameter.py:102:    ParametersSetup.from_list([
src/supervaizer/parameter.py:118:    def from_list(
src/supervaizer/storage.py:245:            return self._from_dict(data)
src/supervaizer/storage.py:266:        return [self._from_dict(data) for data in data_list]
src/supervaizer/storage.py:292:    def _from_dict(self, data: Dict[str, Any]) -> T:
```

```bash
grep -rn 'registration_info' src/supervaizer/agent.py | head -10
```

```output
419:    def registration_info(self) -> Dict[str, Any]:
429:            "nodes": self.nodes.registration_info if self.nodes else None,
485:    def registration_info(self) -> Dict[str, Any]:
487:            "job_start": self.job_start.registration_info,
488:            "job_stop": self.job_stop.registration_info if self.job_stop else None,
489:            "job_status": self.job_status.registration_info
492:            "human_answer": self.human_answer.registration_info
495:            "chat": self.chat.registration_info if self.chat else None,
497:                name: method.registration_info
692:    def registration_info(self) -> Dict[str, Any]:
```

**Patterns used throughout Supervaizer:**

**1. Singleton** (via `@singleton` decorator)
`Jobs`, `Cases`, and `StorageManager` are all singletons. Any code anywhere can call `Jobs()` and get the same in-memory registry. This avoids passing context through every call chain.

**2. Factory methods**
- `Job.new()` — builds and registers a Job with sensible defaults.
- `Case.start()` — builds, registers, and fires the lifecycle event.
- `ParametersSetup.from_list()` — converts a list of dicts to a typed `ParametersSetup`.
- `create_default_routes(server)`, `create_agents_routes(server)` — route factories accept a server instance for closure access.

**3. `registration_info` property**
Every model has a `registration_info` property returning a plain dict for platform API payloads. This isolates serialisation logic from the model fields and keeps API contracts explicit.

**4. Environment-first configuration**
All configuration reads environment variables with sensible defaults. The CLI stamps env vars before spawning the subprocess, so both code paths (CLI and direct `server.launch()`) read from the same source of truth.

**5. `@handle_route_errors` decorator**
A single decorator handles all route error types uniformly. Routes stay thin — just parse, validate, delegate.

**6. Deferred imports for circular dependency avoidance**
Many files have `from supervaizer.X import Y` inside function bodies rather than at module level. This is a deliberate pattern to break circular import chains between interdependent modules (`agent`, `job`, `case`, `server`, `account`).

---

## 21. Configuration Reference

All environment variables that affect runtime behaviour:

```bash
grep -rn 'os\.getenv\|os\.environ\.get' src/supervaizer/server.py src/supervaizer/cli.py src/supervaizer/storage.py | grep -v __pycache__ | grep -oP 'SUPERVAIZER[A-Z_]+|DATA_STORAGE_PATH|SUPERVAIZE_[A-Z_]+' | sort -u
```

```output
DATA_STORAGE_PATH
SUPERVAIZER_API_KEY
SUPERVAIZER_DEBUG
SUPERVAIZER_ENVIRONMENT
SUPERVAIZER_FORCE_INSTALL
SUPERVAIZER_HOST
SUPERVAIZER_LOG_LEVEL
SUPERVAIZER_OUTPUT_PATH
SUPERVAIZER_PERSISTENCE
SUPERVAIZER_PORT
SUPERVAIZER_PRIVATE_KEY
SUPERVAIZER_PUBLIC_URL
SUPERVAIZER_RELOAD
SUPERVAIZER_SCRIPT_PATH
SUPERVAIZER_SERVER_ID
```

```bash
grep -rn 'SUPERVAIZE_' src/supervaizer/account.py src/supervaizer/account_service.py | grep 'getenv\|environ' | grep -oP 'SUPERVAIZE[A-Z_]+' | sort -u
```

```output
SUPERVAIZE_HTTP_MAX_RETRIES
```

| Variable | Default | Purpose |
|---|---|---|
| `SUPERVAIZER_HOST` | `0.0.0.0` | Bind host |
| `SUPERVAIZER_PORT` | `8000` | Bind port |
| `SUPERVAIZER_ENVIRONMENT` | `dev` | Environment label |
| `SUPERVAIZER_PERSISTENCE` | `false` | File-based storage |
| `DATA_STORAGE_PATH` | `./data` | TinyDB file directory |
| `SUPERVAIZER_PUBLIC_URL` | none | URL registered with platform |
| `SUPERVAIZER_API_KEY` | auto-generated | X-API-Key for protected routes |
| `SUPERVAIZER_PRIVATE_KEY` | auto-generated | RSA PEM key for parameter encryption |
| `SUPERVAIZER_SERVER_ID` | auto-generated | Stable server UUID |
| `SUPERVAIZER_DEBUG` | `false` | FastAPI debug mode |
| `SUPERVAIZER_RELOAD` | `false` | Uvicorn auto-reload |
| `SUPERVAIZER_LOG_LEVEL` | `INFO` | Loguru/Uvicorn log level |
| `SUPERVAIZER_SCRIPT_PATH` | `supervaizer_control.py` | Control script path |
| `SUPERVAIZE_WORKSPACE_ID` | — | Supervaize SaaS workspace |
| `SUPERVAIZE_API_KEY` | — | Supervaize SaaS API key |
| `SUPERVAIZE_API_URL` | `https://app.supervaize.com` | Supervaize SaaS API URL |
| `SUPERVAIZE_HTTP_MAX_RETRIES` | `2` | HTTP client retry count |

---

*Walkthrough generated with [showboat](https://github.com/anthropics/showboat)*
