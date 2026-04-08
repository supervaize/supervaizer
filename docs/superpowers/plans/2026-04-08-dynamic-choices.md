# Dynamic Choices for AgentMethodField — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow AgentMethodField to declare dynamic choices that are resolved at runtime via a callback on the Agent, exposed through a new API endpoint that Supervaize Studio calls when rendering job-start forms.

**Architecture:** A new `dynamic_choices: str | None` attribute on `AgentMethodField` acts as a key. The `Agent` class gets a `get_dynamic_choices` callable that maps method names to `{key: [(value, label), ...]}`. A new GET endpoint `/agents/{slug}/start/dynamic_choices` invokes this callback and returns the choices. Static `choices` and `dynamic_choices` are mutually exclusive on a field.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI

---

### Task 1: Add `dynamic_choices` attribute to `AgentMethodField`

**Files:**
- Modify: `src/supervaizer/agent.py:55-128` (AgentMethodField class)
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test for the new attribute**

In `tests/test_agent.py`, add:

```python
def test_agent_method_field_dynamic_choices():
    """Test that AgentMethodField accepts dynamic_choices attribute."""
    field = AgentMethodField(
        name="List of projects",
        type=str,
        field_type="ChoiceField",
        dynamic_choices="projects",
        required=True,
    )
    assert field.dynamic_choices == "projects"
    assert field.choices is None


def test_agent_method_field_dynamic_choices_default_none():
    """Test that dynamic_choices defaults to None."""
    field = AgentMethodField(
        name="color",
        type=str,
        field_type="ChoiceField",
        choices=[("R", "Red"), ("B", "Blue")],
        required=True,
    )
    assert field.dynamic_choices is None


def test_agent_method_field_dynamic_choices_mutual_exclusion():
    """Test that choices and dynamic_choices cannot both be set."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="mutually exclusive"):
        AgentMethodField(
            name="List of projects",
            type=str,
            field_type="ChoiceField",
            choices=[("A", "Option A")],
            dynamic_choices="projects",
            required=True,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_agent.py::test_agent_method_field_dynamic_choices tests/test_agent.py::test_agent_method_field_dynamic_choices_default_none tests/test_agent.py::test_agent_method_field_dynamic_choices_mutual_exclusion -v`

Expected: FAIL — `dynamic_choices` not recognized as a field

- [ ] **Step 3: Add `dynamic_choices` field and validator to `AgentMethodField`**

In `src/supervaizer/agent.py`, inside the `AgentMethodField` class (after the `required` field, before `model_config`):

```python
    dynamic_choices: str | None = Field(
        default=None,
        description="Key name for dynamic choices resolved at runtime via Agent.get_dynamic_choices callback. Mutually exclusive with 'choices'.",
    )

    @model_validator(mode="after")
    def validate_choices_mutual_exclusion(self) -> "AgentMethodField":
        if self.choices is not None and self.dynamic_choices is not None:
            raise ValueError(
                "'choices' and 'dynamic_choices' are mutually exclusive. "
                "Use 'choices' for static options or 'dynamic_choices' for runtime-resolved options."
            )
        return self
```

Add `model_validator` to the pydantic imports at the top of the file if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_agent.py::test_agent_method_field_dynamic_choices tests/test_agent.py::test_agent_method_field_dynamic_choices_default_none tests/test_agent.py::test_agent_method_field_dynamic_choices_mutual_exclusion -v`

Expected: All 3 PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/supervaizer/agent.py tests/test_agent.py
git commit -m "feat: add dynamic_choices attribute to AgentMethodField"
```

---

### Task 2: Add `dynamic_choices` to `fields_definitions` serialization

**Files:**
- Modify: `src/supervaizer/agent.py:229-250` (AgentMethod.fields_definitions property)
- Test: `tests/test_agent.py`

The `fields_definitions` property currently uses `field.__dict__` which will automatically include `dynamic_choices`. We need to verify this works and that `registration_info` propagates it correctly.

- [ ] **Step 1: Write the failing test**

In `tests/test_agent.py`, add:

```python
def test_agent_method_fields_definitions_includes_dynamic_choices():
    """Test that fields_definitions includes dynamic_choices in the output."""
    method = AgentMethod(
        name="start",
        method="my_module.start",
        fields=[
            AgentMethodField(
                name="Project",
                type=str,
                field_type="ChoiceField",
                dynamic_choices="projects",
                required=True,
            ),
        ],
        description="Start",
    )
    definitions = method.fields_definitions
    assert len(definitions) == 1
    assert definitions[0]["dynamic_choices"] == "projects"
    assert definitions[0]["choices"] is None


def test_agent_method_registration_info_includes_dynamic_choices():
    """Test that registration_info propagates dynamic_choices through fields."""
    method = AgentMethod(
        name="start",
        method="my_module.start",
        fields=[
            AgentMethodField(
                name="Project",
                type=str,
                field_type="ChoiceField",
                dynamic_choices="projects",
                required=True,
            ),
        ],
        description="Start",
    )
    info = method.registration_info
    assert info["fields"][0]["dynamic_choices"] == "projects"
```

- [ ] **Step 2: Run tests to verify they pass (they should already work via `__dict__`)**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_agent.py::test_agent_method_fields_definitions_includes_dynamic_choices tests/test_agent.py::test_agent_method_registration_info_includes_dynamic_choices -v`

Expected: PASS — `fields_definitions` uses `field.__dict__` which already includes `dynamic_choices`

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent.py
git commit -m "test: verify dynamic_choices serialization in fields_definitions"
```

---

### Task 3: Add `get_dynamic_choices` callback to `Agent`

**Files:**
- Modify: `src/supervaizer/agent.py:558-618` (AgentAbstract) and `src/supervaizer/agent.py:621-695` (Agent.__init__)
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_agent.py`, add:

```python
def test_agent_with_dynamic_choices_callback(agent_method_fixture: AgentMethod):
    """Test that Agent accepts a get_dynamic_choices callable."""

    def my_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        return {"projects": [("P1", "Project 1"), ("P2", "Project 2")]}

    agent = Agent(
        name="dynamicAgent",
        author="test",
        version="1.0",
        description="test agent",
        methods=AgentMethods(job_start=agent_method_fixture),
        get_dynamic_choices=my_dynamic_choices,
    )
    assert agent.get_dynamic_choices is not None
    result = agent.get_dynamic_choices("start")
    assert result == {"projects": [("P1", "Project 1"), ("P2", "Project 2")]}


def test_agent_without_dynamic_choices_callback(agent_method_fixture: AgentMethod):
    """Test that get_dynamic_choices defaults to None."""
    agent = Agent(
        name="staticAgent",
        author="test",
        version="1.0",
        description="test agent",
        methods=AgentMethods(job_start=agent_method_fixture),
    )
    assert agent.get_dynamic_choices is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_agent.py::test_agent_with_dynamic_choices_callback tests/test_agent.py::test_agent_without_dynamic_choices_callback -v`

Expected: FAIL — `get_dynamic_choices` not a recognized attribute

- [ ] **Step 3: Add `get_dynamic_choices` to `AgentAbstract` and `Agent.__init__`**

In `src/supervaizer/agent.py`, in `AgentAbstract` class, add after the `custom_routes` field (line ~614):

```python
    get_dynamic_choices: Any | None = Field(
        default=None,
        description="Callable that returns dynamic choices for method fields. Signature: (method_name: str) -> dict[str, list[tuple[str, str]]]",
        exclude=True,
    )
```

In `Agent.__init__` (line ~622), add the parameter to the signature after `custom_routes`:

```python
        get_dynamic_choices: Any | None = None,
```

And pass it through to `super().__init__()`:

```python
            get_dynamic_choices=get_dynamic_choices,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_agent.py::test_agent_with_dynamic_choices_callback tests/test_agent.py::test_agent_without_dynamic_choices_callback -v`

Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/supervaizer/agent.py tests/test_agent.py
git commit -m "feat: add get_dynamic_choices callback to Agent"
```

---

### Task 4: Add the `/start/dynamic_choices` endpoint

**Files:**
- Modify: `src/supervaizer/routes.py` (inside `create_agent_route` function, after validate-method-fields endpoint ~line 619)
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_routes.py`, add:

```python
from supervaizer.agent import AgentMethodField
from supervaizer.routes import create_agents_routes


def test_dynamic_choices_endpoint(server_fixture: Server, mocker: Any) -> None:
    """Test GET /supervaizer/agents/{slug}/start/dynamic_choices returns choices."""

    def mock_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        if method_name == "start":
            return {"projects": [("P1", "Project 1"), ("P2", "Project 2")]}
        return {}

    # Set the callback on the agent
    agent = server_fixture.agents[0]
    agent.get_dynamic_choices = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.get(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"]["projects"] == [["P1", "Project 1"], ["P2", "Project 2"]]


def test_dynamic_choices_endpoint_no_callback(
    server_fixture: Server, mocker: Any
) -> None:
    """Test that endpoint returns 404 when no callback is registered."""
    agent = server_fixture.agents[0]
    agent.get_dynamic_choices = None

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.get(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices", headers=headers
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_routes.py::test_dynamic_choices_endpoint tests/test_routes.py::test_dynamic_choices_endpoint_no_callback -v`

Expected: FAIL — endpoint does not exist (404 for both, but for wrong reason on the first)

- [ ] **Step 3: Add the endpoint to `create_agent_route`**

In `src/supervaizer/routes.py`, inside `create_agent_route()`, add after the `validate_method_fields` endpoint (after ~line 619, before the job model creation):

```python
    @router.get(
        "/start/dynamic_choices",
        summary=f"Get dynamic choices for agent: {agent.name} start method",
        description="Returns dynamic choice values for fields that use dynamic_choices",
        response_model=Dict[str, Any],
        responses={
            http_status.HTTP_200_OK: {"model": Dict[str, Any]},
            http_status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_dynamic_choices(
        agent: Agent = Depends(get_agent),
    ) -> Dict[str, Any] | JSONResponse:
        """Get dynamic choices for the start method fields."""
        log.info(
            f"📥 GET /start/dynamic_choices [Dynamic choices] {agent.name}"
        )

        if not agent.get_dynamic_choices:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent.name} does not have dynamic choices configured",
            )

        choices = agent.get_dynamic_choices("start")

        log.info(
            f"📤 Agent {agent.name}: Dynamic choices keys: {list(choices.keys())}"
        )
        return {"choices": choices}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_routes.py::test_dynamic_choices_endpoint tests/test_routes.py::test_dynamic_choices_endpoint_no_callback -v`

Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/supervaizer/routes.py tests/test_routes.py
git commit -m "feat: add /start/dynamic_choices endpoint"
```

---

### Task 5: Update the example template

**Files:**
- Modify: `src/supervaizer/examples/controller_template.py`

- [ ] **Step 1: Wire the existing `get_dynamic_choices` function to the Agent**

In `src/supervaizer/examples/controller_template.py`, the function `get_dynamic_choices` already exists at line 39. Update the `Agent` constructor (line ~176) to pass it:

```python
agent: Agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(f"{agent_name}"),
    author="John Doe",
    developer="Developer",
    maintainer="Ive Maintained",
    editor="DevAiExperts",
    version="1.3",
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
    instructions_path="supervaize_instructions.html",
    get_dynamic_choices=get_dynamic_choices,
)
```

- [ ] **Step 2: Run full test suite to verify no regressions**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/supervaizer/examples/controller_template.py
git commit -m "feat: wire get_dynamic_choices in example controller template"
```

---

### Task 6: Comprehensive unit tests

**Files:**
- Modify: `tests/test_agent.py`
- Modify: `tests/test_routes.py`

This task adds additional edge-case and integration tests beyond the basic ones written in Tasks 1-4.

- [ ] **Step 1: Add edge-case tests for `AgentMethodField`**

In `tests/test_agent.py`, add:

```python
def test_agent_method_field_dynamic_choices_in_model_dump():
    """Test that dynamic_choices appears in model_dump output."""
    field = AgentMethodField(
        name="Project",
        type=str,
        field_type="ChoiceField",
        dynamic_choices="projects",
        required=True,
    )
    dumped = field.model_dump()
    assert dumped["dynamic_choices"] == "projects"
    assert dumped["choices"] is None


def test_agent_method_field_static_choices_no_dynamic():
    """Test that static choices field has dynamic_choices=None in model_dump."""
    field = AgentMethodField(
        name="Color",
        type=str,
        field_type="ChoiceField",
        choices=[("R", "Red"), ("B", "Blue")],
        required=True,
    )
    dumped = field.model_dump()
    assert dumped["dynamic_choices"] is None
    assert dumped["choices"] == [("R", "Red"), ("B", "Blue")]


def test_agent_method_field_non_choice_field_with_dynamic_choices():
    """Test that dynamic_choices can be set on a ChoiceField type."""
    field = AgentMethodField(
        name="Items",
        type=str,
        field_type="ChoiceField",
        dynamic_choices="items",
        required=False,
    )
    assert field.dynamic_choices == "items"
    assert field.field_type == "ChoiceField"


def test_agent_method_mixed_static_and_dynamic_fields():
    """Test a method with both static and dynamic choice fields."""
    method = AgentMethod(
        name="start",
        method="my_module.start",
        fields=[
            AgentMethodField(
                name="Type",
                type=str,
                field_type="ChoiceField",
                choices=[("A", "Alpha"), ("B", "Beta")],
                required=True,
            ),
            AgentMethodField(
                name="Project",
                type=str,
                field_type="ChoiceField",
                dynamic_choices="projects",
                required=True,
            ),
            AgentMethodField(
                name="Name",
                type=str,
                field_type="CharField",
                required=True,
            ),
        ],
        description="Start",
    )
    defs = method.fields_definitions
    assert defs[0]["choices"] == [("A", "Alpha"), ("B", "Beta")]
    assert defs[0]["dynamic_choices"] is None
    assert defs[1]["choices"] is None
    assert defs[1]["dynamic_choices"] == "projects"
    assert defs[2]["dynamic_choices"] is None
```

- [ ] **Step 2: Add callback edge-case tests for `Agent`**

In `tests/test_agent.py`, add:

```python
def test_agent_dynamic_choices_callback_returns_empty(agent_method_fixture: AgentMethod):
    """Test callback that returns empty dict for unknown method."""

    def my_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        if method_name == "start":
            return {"projects": [("P1", "Project 1")]}
        return {}

    agent = Agent(
        name="emptyCallbackAgent",
        author="test",
        version="1.0",
        description="test",
        methods=AgentMethods(job_start=agent_method_fixture),
        get_dynamic_choices=my_dynamic_choices,
    )
    assert agent.get_dynamic_choices("start") == {"projects": [("P1", "Project 1")]}
    assert agent.get_dynamic_choices("unknown") == {}


def test_agent_dynamic_choices_callback_multiple_keys(agent_method_fixture: AgentMethod):
    """Test callback returning multiple choice keys."""

    def my_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        return {
            "projects": [("P1", "Project 1"), ("P2", "Project 2")],
            "teams": [("T1", "Team Alpha"), ("T2", "Team Beta")],
        }

    agent = Agent(
        name="multiKeyAgent",
        author="test",
        version="1.0",
        description="test",
        methods=AgentMethods(job_start=agent_method_fixture),
        get_dynamic_choices=my_dynamic_choices,
    )
    result = agent.get_dynamic_choices("start")
    assert "projects" in result
    assert "teams" in result
    assert len(result["projects"]) == 2
    assert len(result["teams"]) == 2
```

- [ ] **Step 3: Add route endpoint edge-case tests**

In `tests/test_routes.py`, add:

```python
def test_dynamic_choices_endpoint_multiple_keys(
    server_fixture: Server, mocker: Any
) -> None:
    """Test endpoint returns multiple choice keys."""

    def mock_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        return {
            "projects": [("P1", "Project 1")],
            "teams": [("T1", "Team Alpha")],
        }

    agent = server_fixture.agents[0]
    agent.get_dynamic_choices = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.get(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data["choices"]
    assert "teams" in data["choices"]


def test_dynamic_choices_endpoint_empty_result(
    server_fixture: Server, mocker: Any
) -> None:
    """Test endpoint returns empty choices when callback returns empty dict."""

    def mock_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        return {}

    agent = server_fixture.agents[0]
    agent.get_dynamic_choices = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.get(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"] == {}


def test_dynamic_choices_endpoint_requires_api_key(
    server_fixture: Server, mocker: Any
) -> None:
    """Test that the dynamic choices endpoint requires API key authentication."""

    def mock_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
        return {"projects": [("P1", "Project 1")]}

    agent = server_fixture.agents[0]
    agent.get_dynamic_choices = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)

    # No API key header
    resp = client.get(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices"
    )
    assert resp.status_code == 403
```

- [ ] **Step 4: Run all tests**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent.py tests/test_routes.py
git commit -m "test: add comprehensive unit tests for dynamic choices"
```

---

### Task 7: Clean code review — Pass 1 (agent.py)

**Files:**
- Review & modify: `src/supervaizer/agent.py`

- [ ] **Step 1: Run the clean-code skill on agent.py**

Use the `/simplify` skill (or `clean-code-clean-general` skill) focused on the changes made in Tasks 1-3 within `src/supervaizer/agent.py`. Review for:
- Naming clarity of `dynamic_choices` field and `get_dynamic_choices` callback
- Validator readability
- Consistency with existing code patterns in the file
- Any unnecessary complexity introduced

- [ ] **Step 2: Apply fixes if needed and run tests**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 3: Commit if changes were made**

```bash
git add src/supervaizer/agent.py
git commit -m "refactor: clean code pass on agent.py dynamic choices"
```

---

### Task 8: Clean code review — Pass 2 (routes.py)

**Files:**
- Review & modify: `src/supervaizer/routes.py`

- [ ] **Step 1: Run the clean-code skill on routes.py**

Use the `/simplify` skill focused on the new `get_dynamic_choices` endpoint added in Task 4. Review for:
- Consistency with other endpoint patterns in the same file (logging style, error handling, response format)
- Unnecessary code or over-engineering
- Proper use of FastAPI patterns (dependencies, response models)

- [ ] **Step 2: Apply fixes if needed and run tests**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 3: Commit if changes were made**

```bash
git add src/supervaizer/routes.py
git commit -m "refactor: clean code pass on routes.py dynamic choices endpoint"
```

---

### Task 9: Clean code review — Pass 3 (tests)

**Files:**
- Review & modify: `tests/test_agent.py`
- Review & modify: `tests/test_routes.py`

- [ ] **Step 1: Run the clean-code skill on the test files**

Use the `/simplify` skill focused on all new tests added in Tasks 1-4 and Task 6. Review for:
- Test naming consistency
- Unnecessary duplication between tests
- Missing assertions or redundant assertions
- Fixture reuse opportunities
- Compliance with existing test patterns in the files

- [ ] **Step 2: Apply fixes if needed and run tests**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 3: Commit if changes were made**

```bash
git add tests/test_agent.py tests/test_routes.py
git commit -m "refactor: clean code pass on dynamic choices tests"
```

---

### Task 10: Update supervaize-doc — model reference

**Files:**
- Modify: `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/docs/supervaizer-controller/model_reference/model_core.md:213-288` (AgentMethodField section)

- [ ] **Step 1: Add `dynamic_choices` to the AgentMethodField field table**

In the field table at line ~234, add a new row after the `choices` row:

```markdown
| `dynamic_choices` | `str` | `None` | Key name for runtime-resolved choices via `Agent.get_dynamic_choices` callback. Mutually exclusive with `choices`. |
```

- [ ] **Step 2: Add a dynamic choices example after the existing examples**

After "Example 2" (line ~287), add:

```markdown
**Example 3: Dynamic choices field**

```json
{
  "name": "List of projects",
  "type": "str",
  "field_type": "ChoiceField",
  "dynamic_choices": "projects",
  "choices": null,
  "required": true
}
```

> When `dynamic_choices` is set, choices are not embedded in the field definition. Instead, Supervaize Studio fetches them at runtime from the `GET /agents/{slug}/start/dynamic_choices` endpoint. See [Dynamic Choices](/docs/supervaizer-controller/dynamic-choices) for setup instructions.
```

- [ ] **Step 3: Add `get_dynamic_choices` to the Agent class documentation**

Find the `agent.AgentAbstract` section in model_core.md and add to its field table:

```markdown
| `get_dynamic_choices` | `Callable` | `None` | Callback that returns dynamic choices for method fields. Signature: `(method_name: str) -> dict[str, list[tuple[str, str]]]`. Excluded from serialization. |
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc
git add docs/supervaizer-controller/model_reference/model_core.md
git commit -m "docs: add dynamic_choices to model reference"
```

---

### Task 11: Update supervaize-doc — controller setup guide

**Files:**
- Modify: `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/docs/supervaizer-controller/controller-setup.mdx:145-175` (section 3: fields)

- [ ] **Step 1: Add a dynamic choices subsection after the existing field setup**

After the closing `</details>` tag of section 3 (line ~174), and before section 4 "Declare the agent", add:

```markdown
### Dynamic choices

For fields whose options are determined at runtime (e.g., a list of projects fetched from a database), use `dynamic_choices` instead of static `choices`:

```python
AgentMethodField(
    name="List of projects",
    type=str,
    field_type="ChoiceField",
    dynamic_choices="projects",  # key name — resolved at runtime
    required=True,
)
```

Then define a callback function and pass it to your Agent:

```python
def get_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
    if method_name == "start":
        # Fetch from database, API, or any source
        return {
            "projects": [("P1", "Project 1"), ("P2", "Project 2"), ("P3", "Project 3")],
        }
    return {}

agent = Agent(
    name="my_agent",
    # ... other fields ...
    get_dynamic_choices=get_dynamic_choices,
)
```

:::info
`choices` and `dynamic_choices` are mutually exclusive on a field. Use `choices` for fixed options known at definition time, and `dynamic_choices` for options that change at runtime.
:::

See the full [Dynamic Choices guide](/docs/supervaizer-controller/dynamic-choices) for details.
```

- [ ] **Step 2: In section 4 "Declare the agent", mention the optional callback**

After the existing Agent example prompt (line ~205), add a note:

```markdown
:::tip
If your agent uses dynamic choice fields, pass the `get_dynamic_choices` callback to the Agent constructor. See [Dynamic Choices](/docs/supervaizer-controller/dynamic-choices).
:::
```

- [ ] **Step 3: Commit**

```bash
cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc
git add docs/supervaizer-controller/controller-setup.mdx
git commit -m "docs: add dynamic choices section to controller setup guide"
```

---

### Task 12: Update supervaize-doc — new dynamic choices guide page

**Files:**
- Create: `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/docs/supervaizer-controller/dynamic-choices.mdx`
- Modify: `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/sidebars.ts`

- [ ] **Step 1: Create the new doc page**

Create `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/docs/supervaizer-controller/dynamic-choices.mdx`:

```mdx
---
id: dynamic-choices
title: Dynamic Choices
displayed_sidebar: supervaizerControllerSidebar
slug: dynamic-choices
---

# Dynamic Choices

Dynamic choices allow your agent's form fields to display options that are resolved at runtime rather than being hardcoded in the field definition. This is useful when the available options depend on external data sources like databases, APIs, or configuration files.

## When to use

Use dynamic choices when:
- The list of options changes over time (e.g., active projects, team members, available models)
- The options come from an external source (database, API)
- The options are environment-specific (dev vs. prod)

Use static `choices` when the options are fixed and known at definition time (e.g., country codes, status values).

## Setup

### 1. Define the field with `dynamic_choices`

Instead of providing a `choices` list, set `dynamic_choices` to a key name:

```python
from supervaizer import AgentMethodField

field = AgentMethodField(
    name="List of projects",
    type=str,
    field_type="ChoiceField",
    dynamic_choices="projects",  # key name
    required=True,
)
```

:::warning
`choices` and `dynamic_choices` are mutually exclusive. Setting both will raise a validation error.
:::

### 2. Define the callback function

Create a function that takes a method name and returns a dictionary mapping choice keys to their value/label pairs:

```python
def get_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
    """Return dynamic choices for the given method.

    Args:
        method_name: The method requesting choices (e.g., "start")

    Returns:
        Dict mapping choice key names to lists of (value, label) tuples
    """
    if method_name == "start":
        # Fetch from your data source
        projects = fetch_projects_from_db()
        return {
            "projects": [(p.id, p.name) for p in projects],
        }
    return {}
```

The return format is `dict[str, list[tuple[str, str]]]`:
- **Keys** match the `dynamic_choices` values on your fields
- **Values** are lists of `(value, label)` tuples — same format as static `choices`

You can return multiple keys if multiple fields use dynamic choices:

```python
def get_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
    return {
        "projects": [("P1", "Project 1"), ("P2", "Project 2")],
        "teams": [("T1", "Team Alpha"), ("T2", "Team Beta")],
    }
```

### 3. Pass the callback to the Agent

```python
from supervaizer import Agent

agent = Agent(
    name="my_agent",
    author="Your Name",
    version="1.0",
    description="My agent with dynamic choices",
    methods=AgentMethods(job_start=job_start_method),
    get_dynamic_choices=get_dynamic_choices,
)
```

## How it works

When Supervaize Studio renders the job start form:

1. Studio checks if any field has `dynamic_choices` set
2. If so, it calls `GET /supervaizer/agents/{agent_slug}/start/dynamic_choices`
3. The endpoint invokes your `get_dynamic_choices("start")` callback
4. The returned choices are used to populate the form dropdowns

```
┌──────────────┐     GET /start/dynamic_choices     ┌───────────────┐
│   Supervaize │ ──────────────────────────────────► │  Supervaizer  │
│    Studio    │                                     │   Controller  │
│              │ ◄────────────────────────────────── │               │
│  (renders    │     {"choices": {"projects": ...}}  │  (calls your  │
│   the form)  │                                     │   callback)   │
└──────────────┘                                     └───────────────┘
```

## API Reference

### Endpoint

```
GET /supervaizer/agents/{agent_slug}/start/dynamic_choices
```

**Headers:** `X-API-Key: {your_api_key}`

### Response

```json
{
    "choices": {
        "projects": [
            ["P1", "Project 1"],
            ["P2", "Project 2"],
            ["P3", "Project 3"]
        ]
    }
}
```

### Error responses

| Status | Meaning |
|--------|---------|
| 200 | Choices returned successfully |
| 404 | Agent has no `get_dynamic_choices` callback |
| 500 | Callback raised an error |

## Complete example

```python
from supervaizer import Agent, AgentMethod, AgentMethodField, AgentMethods, Server


def get_dynamic_choices(method_name: str) -> dict[str, list[tuple[str, str]]]:
    if method_name == "start":
        return {
            "projects": [("P1", "Project 1"), ("P2", "Project 2"), ("P3", "Project 3")],
        }
    return {}


job_start = AgentMethod(
    name="start",
    method="my_agent.start_job",
    fields=[
        AgentMethodField(
            name="Company name",
            type=str,
            field_type="CharField",
            required=True,
        ),
        AgentMethodField(
            name="Project",
            type=str,
            field_type="ChoiceField",
            dynamic_choices="projects",
            required=True,
        ),
    ],
    description="Start a new research job",
)

agent = Agent(
    name="research_agent",
    author="Your Name",
    version="1.0",
    description="Research agent with dynamic project selection",
    methods=AgentMethods(job_start=job_start),
    get_dynamic_choices=get_dynamic_choices,
)

server = Server(agents=[agent])
```
```

- [ ] **Step 2: Add to sidebar**

In `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc/sidebars.ts`, add a new entry after the "Controller Setup Guide" item (line ~31):

```typescript
        {
          type: "doc",
          id: "supervaizer-controller/dynamic-choices",
          label: "Dynamic Choices",
        },
```

The items array should look like:

```typescript
items: [
    { type: "doc", id: "supervaizer-controller/quickstart", label: "Quick Start" },
    { type: "doc", id: "supervaizer-controller/core-concepts", label: "Core Concepts" },
    { type: "doc", id: "supervaizer-controller/controller-setup", label: "Controller Setup Guide" },
    { type: "doc", id: "supervaizer-controller/dynamic-choices", label: "Dynamic Choices" },  // <-- NEW
    { type: "doc", id: "supervaizer-controller/application-flow-control", label: "Application Flow Control" },
    // ... rest
```

- [ ] **Step 3: Verify the doc builds**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc && just build`

Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc
git add docs/supervaizer-controller/dynamic-choices.mdx sidebars.ts
git commit -m "docs: add dynamic choices guide page"
```

---

### Task 13: Update changelog

**Files:**
- Modify: `/Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer/docs/CHANGELOG.md`

- [ ] **Step 1: Add entry under Unreleased**

In `docs/CHANGELOG.md`, add to the `## Unreleased` → `### Added` section (after the existing ADMIN_ALLOWED_IPS entry):

```markdown
- **Dynamic choices for `AgentMethodField`** — Fields can now use `dynamic_choices` instead of static `choices` to resolve options at runtime via a callback. Add a `get_dynamic_choices` callable to the `Agent` constructor and a `dynamic_choices` key to your `AgentMethodField`. Supervaize Studio fetches choices from the new `GET /agents/{slug}/start/dynamic_choices` endpoint when rendering the job start form. Static `choices` and `dynamic_choices` are mutually exclusive on a field.
```

- [ ] **Step 2: Update the test count table**

Run the test suite and update the test count table in the Unreleased section to reflect the new test count:

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Update the table with the new counts.

- [ ] **Step 3: Commit**

```bash
cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer
git add docs/CHANGELOG.md
git commit -m "docs: update changelog with dynamic choices feature"
```

---

### Task 14: Final verification

- [ ] **Step 1: Run the full supervaizer test suite**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`

Expected: All tests PASS

- [ ] **Step 2: Run pre-commit hooks**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && just precommit`

Expected: All hooks PASS

- [ ] **Step 3: Verify supervaize-doc builds**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaize-doc && just build`

Expected: Build succeeds

---

## Supervaize Studio Integration Instructions

For the Studio team to integrate dynamic choices into the job-start form:

### Detection

When rendering a job-start form, check if any field in the method's `fields` array has a non-null `dynamic_choices` key. This key is included in `registration_info` → `methods` → `job_start` → `fields`.

```python
# In the registration_info response, a dynamic field looks like:
{
    "name": "List of projects",
    "type": "str",
    "field_type": "ChoiceField",
    "dynamic_choices": "projects",  # <-- this is the indicator
    "choices": null,                # <-- always null when dynamic_choices is set
    "required": true,
    ...
}
```

### API Call

When the form is opened (before rendering), if any field has `dynamic_choices` set, call:

```
GET {supervaizer_url}/supervaizer/agents/{agent_slug}/start/dynamic_choices
Headers: X-API-Key: {api_key}
```

### Response Format

```json
{
    "choices": {
        "projects": [["P1", "Project 1"], ["P2", "Project 2"], ["P3", "Project 3"]]
    }
}
```

Each key in `choices` maps to a `dynamic_choices` value on a field. The value is a list of `[value, label]` pairs — same format as static `choices`.

### Form Rendering

1. Fetch dynamic choices once when the form opens
2. For each field where `dynamic_choices` is set, look up the matching key in the response
3. Populate the field's choices with those values
4. Render as a standard `ChoiceField` dropdown

### Error Handling

- **404**: Agent has no `get_dynamic_choices` callback — render the field as disabled with "Options not available"
- **500**: Callback raised an error — render the field as disabled with "Could not load options"
- **Network error**: Retry once, then show error state

### Caching

Do NOT cache dynamic choices — they should be fetched fresh each time the form is opened. The whole point is that they change (e.g., project lists, user lists, etc.).

### Future: Conditional Fields

A future iteration may add `POST /start/dynamic_choices` accepting `{"field_values": {...}}` for fields that depend on other field values. The GET endpoint will remain for non-conditional dynamic choices.
