# gen_model_docs.py

"""
Model Documentation Generator

This script automatically generates model reference documentation for the supervaizer package.
It scans through all modules in the package and identifies Pydantic BaseModel classes and
dataclasses, then generates markdown files with their field definitions, types, defaults,
and descriptions.

Features:
- Discovers all Pydantic models and dataclasses in the package
- Extracts field information including types, defaults, and descriptions
- Generates markdown tables for easy reading
- Handles both Pydantic v1 and v2 field structures
- Supports dataclass metadata for field descriptions
- Groups models by reference_group configuration

Usage:
    python tools/gen_model_docs.py

Output:
    Creates docs/model_reference/ directory with multiple markdown files:
    - model_extra.md: for models with no reference_group or "extra" value
    - _{reference_group}.md: for models with specific reference_group values
    And also, copies the entire output directory to the external documentation directory
"""

from __future__ import annotations
import importlib
import inspect
import pkgutil
import dataclasses
import shutil
import json
from datetime import datetime
from types import ModuleType
from pathlib import Path
from typing import Any, Iterator, Union, Dict, List
from pydantic import BaseModel

PACKAGE = "supervaizer"
OUTPUT = Path("docs/model_reference")
EXTERNAL_DOC_PATH = Path(
    "../doc/supervaize-doc/docs/supervaizer-controller/model_reference"
)


def format_json_in_doc(doc: str) -> str:
    """Format JSON content in documentation with proper JSON code blocks."""
    lines = doc.split("\n")
    result = []
    in_json_block = False
    json_lines_raw: list[str] = []
    brace_count = 0
    bracket_count = 0

    for line in lines:
        stripped = line.strip()

        # Detect start of potential JSON block
        if not in_json_block:
            if stripped.startswith("{") or stripped.startswith("["):
                in_json_block = True
                json_lines_raw = [line]
                brace_count = line.count("{") - line.count("}")
                bracket_count = line.count("[") - line.count("]")
            else:
                result.append(line)
        else:
            json_lines_raw.append(line)
            brace_count += line.count("{") - line.count("}")
            bracket_count += line.count("[") - line.count("]")

            # End of block when counts balance
            if brace_count == 0 and bracket_count == 0:
                in_json_block = False
                json_content_raw = "\n".join(json_lines_raw)
                json_content_stripped = "\n".join(l.strip() for l in json_lines_raw)

                # Try parsing as JSON (raw first, then with common fixes)
                def fence(raw: str) -> str:
                    return f"\n```json\n{raw}\n```\n"

                try:
                    parsed = json.loads(json_content_raw)
                    formatted = json.dumps(parsed, indent=2)
                    result.append(fence(formatted))
                except json.JSONDecodeError:
                    try:
                        parsed = json.loads(json_content_stripped)
                        formatted = json.dumps(parsed, indent=2)
                        result.append(fence(formatted))
                    except json.JSONDecodeError:
                        # Common Python->JSON fixes
                        fixed = (
                            json_content_stripped.replace(" True", " true")
                            .replace(": True", ": true")
                            .replace(" False", " false")
                            .replace(": False", ": false")
                            .replace(" None", " null")
                            .replace(": None", ": null")
                        )
                        try:
                            parsed = json.loads(fixed)
                            formatted = json.dumps(parsed, indent=2)
                            result.append(fence(formatted))
                        except json.JSONDecodeError:
                            # Give up parsing; still wrap the original block in fences
                            result.append(fence(json_content_raw))

    # If doc ends while still in a block, close by fencing what we have
    if in_json_block and json_lines_raw:
        result.append("\n```json\n" + "\n".join(json_lines_raw) + "\n```\n")

    return "\n".join(result)


def iter_modules(package: str) -> Iterator[ModuleType]:
    mod = importlib.import_module(package)
    mod_file = getattr(mod, "__file__", None)
    if mod_file is None:
        return
    base = Path(mod_file).parent
    for m in pkgutil.walk_packages([str(base)], prefix=mod.__name__ + "."):
        try:
            yield importlib.import_module(m.name)
        except Exception:
            pass


def sanitize_default_for_mdx(default_repr: str) -> str:
    """Sanitize default value representation to avoid MDX parsing issues."""
    # Replace enum representations that contain colons with a safer format
    if "<" in default_repr and ":" in default_repr and ">" in default_repr:
        # This looks like an enum representation like <Enum.VALUE: 'string'>
        # Extract the enum name and value
        try:
            # Find the colon and extract the value part
            colon_pos = default_repr.find(":")
            if colon_pos != -1:
                # Get the part after the colon, before the closing >
                value_start = colon_pos + 1
                value_end = default_repr.rfind(">")
                if value_end != -1:
                    value_part = default_repr[value_start:value_end].strip()
                    # Remove quotes if present
                    if value_part.startswith("'") and value_part.endswith("'"):
                        value_part = value_part[1:-1]
                    elif value_part.startswith('"') and value_part.endswith('"'):
                        value_part = value_part[1:-1]
                    return f"`{value_part}`"
        except Exception:
            pass
        # Fallback: just escape the angle brackets
        return default_repr.replace("<", "&lt;").replace(">", "&gt;")

    return default_repr


def get_model_fields(model: type[BaseModel]) -> list[tuple[str, str, str, str]]:
    fields = getattr(model, "model_fields", {})
    result: list[tuple[str, str, str, str]] = []
    for name, field in fields.items():
        # Try to get type/annotation consistently across pydantic versions
        type_obj = getattr(field, "annotation", None) or getattr(field, "type_", None)

        # Format type string properly
        if (
            type_obj is not None
            and hasattr(type_obj, "__origin__")
            and getattr(type_obj, "__origin__", None) is Union
        ) or (
            type_obj is not None
            and hasattr(type_obj, "__args__")
            and type(type_obj).__name__ == "UnionType"
        ):
            # Handle Union types (e.g., str | None)
            type_args = getattr(type_obj, "__args__", [])
            type_parts = []
            non_none_types = []
            for arg in type_args:
                if arg is type(None):
                    # Skip None types, we'll handle them via default value
                    continue
                else:
                    # Handle complex types like list[str]
                    arg_str = str(arg)
                    if "[" in arg_str and "]" in arg_str:
                        # Complex type like list[str], dict[str, int], etc.
                        non_none_types.append(f"`{arg_str}`")
                    else:
                        non_none_types.append(
                            f"`{str(arg.__name__ if hasattr(arg, '__name__') else arg)}`"
                        )

            # If we have non-None types, use them; otherwise fall back to original logic
            if non_none_types:
                type_str = " \\| ".join(non_none_types)
            else:
                # Fallback to original logic if no non-None types found
                for arg in type_args:
                    if arg is type(None):
                        type_parts.append("`None`")
                    else:
                        # Handle complex types like list[str]
                        arg_str = str(arg)
                        if "[" in arg_str and "]" in arg_str:
                            # Complex type like list[str], dict[str, int], etc.
                            type_parts.append(f"`{arg_str}`")
                        else:
                            type_parts.append(
                                f"`{str(arg.__name__ if hasattr(arg, '__name__') else arg)}`"
                            )
                type_str = " \\| ".join(type_parts)
        elif type_obj is not None and str(type_obj).startswith("typing.Union"):
            # Handle older Union syntax
            type_str = (
                str(type_obj)
                .replace("typing.Union[", "")
                .replace("]", "")
                .replace(", ", " | ")
            )
            # Add backticks around each type
            type_parts = type_str.split(" | ")
            type_parts = [f"`{part.strip()}`" for part in type_parts]
            type_str = " \\| ".join(type_parts)
        elif type_obj is not None and str(type_obj).startswith("typing.Optional"):
            # Handle Optional types (which are Union[T, None])
            inner_type = str(type_obj).replace("typing.Optional[", "").replace("]", "")
            type_str = f"`{inner_type}` | `None`"
        else:
            type_str = f"`{getattr(type_obj, '__name__', str(type_obj))}`"

        # Required detection compatible with pydantic v1/v2
        required: bool
        is_required_attr = getattr(field, "is_required", None)
        if isinstance(is_required_attr, bool):
            required = is_required_attr
        elif callable(is_required_attr):
            try:
                required = bool(is_required_attr())
            except Exception:
                required = False
        else:
            required = bool(getattr(field, "required", False))

        # Description
        desc = getattr(field, "description", "") or ""

        # Default handling
        default_repr: str
        if required:
            default_repr = "**required**"
        else:
            if hasattr(field, "default"):
                default_val = getattr(field, "default")
                # Hide Pydantic undefined sentinels
                if default_val is None:
                    default_repr = "`None`"
                else:
                    s = repr(default_val)
                    if "Undefined" in s or "PydanticUndefined" in s:
                        default_repr = "—"
                    else:
                        default_repr = sanitize_default_for_mdx(s)
            else:
                default_repr = "—"

        result.append((name, type_str, default_repr, desc))
    return result


def get_parent_model(
    model: type[BaseModel], models_by_group: Dict[str, List[type[BaseModel]]]
) -> type[BaseModel] | None:
    """Find the parent model that is also documented in the same group."""
    if not issubclass(model, BaseModel):
        return None

    # Get all bases that are Pydantic models
    bases = [
        base
        for base in model.__bases__
        if issubclass(base, BaseModel) and base != BaseModel
    ]

    # Find the parent that is also in our documented models
    for base in bases:
        for group_models in models_by_group.values():
            if base in group_models:
                return base

    return None


def get_model_group(
    model: type[BaseModel], models_by_group: Dict[str, List[type[BaseModel]]]
) -> str:
    """Find which group a model belongs to."""
    for group_name, group_models in models_by_group.items():
        if model in group_models:
            return group_name
    return "extra"  # fallback


def get_dataclass_fields(model: Any) -> list[tuple[str, str, str, str]]:
    fields = getattr(model, "__dataclass_fields__", {})
    result = []
    for name, field in fields.items():
        type_ = getattr(field, "type", str)

        # Format type string properly
        if (
            type_ is not None
            and hasattr(type_, "__origin__")
            and getattr(type_, "__origin__", None) is Union
        ) or (
            type_ is not None
            and hasattr(type_, "__args__")
            and type(type_).__name__ == "UnionType"
        ):
            # Handle Union types (e.g., str | None)
            type_args = getattr(type_, "__args__", [])
            type_parts = []
            non_none_types = []
            for arg in type_args:
                if arg is type(None):
                    # Skip None types, we'll handle them via default value
                    continue
                else:
                    # Handle complex types like list[str]
                    arg_str = str(arg)
                    if "[" in arg_str and "]" in arg_str:
                        # Complex type like list[str], dict[str, int], etc.
                        non_none_types.append(f"`{arg_str}`")
                    else:
                        non_none_types.append(
                            f"`{str(arg.__name__ if hasattr(arg, '__name__') else arg)}`"
                        )

            # If we have non-None types, use them; otherwise fall back to original logic
            if non_none_types:
                type_str = " \\| ".join(non_none_types)
            else:
                # Fallback to original logic if no non-None types found
                for arg in type_args:
                    if arg is type(None):
                        type_parts.append("`None`")
                    else:
                        # Handle complex types like list[str]
                        arg_str = str(arg)
                        if "[" in arg_str and "]" in arg_str:
                            # Complex type like list[str], dict[str, int], etc.
                            type_parts.append(f"`{arg_str}`")
                        else:
                            type_parts.append(
                                f"`{str(arg.__name__ if hasattr(arg, '__name__') else arg)}`"
                            )
                type_str = " \\| ".join(type_parts)
        elif type_ is not None and str(type_).startswith("typing.Union"):
            # Handle older Union syntax
            type_str = (
                str(type_)
                .replace("typing.Union[", "")
                .replace("]", "")
                .replace(", ", " | ")
            )
            # Add backticks around each type
            type_parts = type_str.split(" | ")
            type_parts = [f"`{part.strip()}`" for part in type_parts]
            type_str = " \\| ".join(type_parts)
        elif type_ is not None and str(type_).startswith("typing.Optional"):
            # Handle Optional types (which are Union[T, None])
            inner_type = str(type_).replace("typing.Optional[", "").replace("]", "")
            type_str = f"`{inner_type}` | `None`"
        else:
            type_str = f"`{getattr(type_, '__name__', str(type_))}`"

        required = (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        )
        default = (
            "**required**"
            if required
            else "`None`"
            if field.default is None
            else sanitize_default_for_mdx(repr(field.default))
            if field.default is not dataclasses.MISSING
            else "factory"
        )
        desc = field.metadata.get("description", "")
        result.append((name, type_str, default, desc))
    return result


def generate_model_docs() -> None:
    # Get the supervaizer version
    try:
        from supervaizer.__version__ import VERSION

        version = VERSION
    except (ImportError, AttributeError):
        version = "N/A"

    # Ensure the output directory exists
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Get all models and their reference_group
    models_by_group: Dict[str, List[type[BaseModel]]] = {}
    seen = set()

    for mod in iter_modules(PACKAGE):
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if obj in seen or obj.__module__.startswith("pydantic"):
                continue
            if issubclass(obj, BaseModel):
                # Get the reference_group from model_config
                # Try different ways to access model_config
                model_config = getattr(obj, "model_config", {})
                if not model_config:
                    # Try accessing it as a class attribute
                    model_config = getattr(obj, "__dict__", {}).get("model_config", {})
                if not model_config:
                    # Try accessing it from the class itself
                    model_config = getattr(type(obj), "model_config", {})
                # Check for both reference_group and documentation fields
                reference_group = model_config.get(
                    "reference_group", model_config.get("documentation", "extra")
                )
                if reference_group not in models_by_group:
                    models_by_group[reference_group] = []
                models_by_group[reference_group].append(obj)
                seen.add(obj)
            elif dataclasses.is_dataclass(obj):
                # Dataclasses go to "extra" group
                if "extra" not in models_by_group:
                    models_by_group["extra"] = []
                models_by_group["extra"].append(obj)
                seen.add(obj)

    # Generate documentation for each group
    for group_name, models in models_by_group.items():
        out = [f"# Model Reference {group_name}", ""]
        out.append(f"**Version:** {version}\n")

        for model in models:
            # Remove "supervaizer." prefix from module name
            module_name = model.__module__.replace("supervaizer.", "")
            out.append(f"### `{module_name}.{model.__name__}`\n")

            # Check if this model inherits from another documented model
            parent_model = get_parent_model(model, models_by_group)
            if parent_model:
                parent_module = parent_model.__module__.replace("supervaizer.", "")
                parent_group = get_model_group(parent_model, models_by_group)

                # Generate appropriate link based on whether parent is in same file
                if parent_group == group_name:
                    link = f"#{parent_module}-{parent_model.__name__.lower()}"
                else:
                    # Cross-file link
                    if parent_group == "extra":
                        link = f"../model_extra.md#{parent_module}-{parent_model.__name__.lower()}"
                    else:
                        link = f"../model_{parent_group.lower()}.md#{parent_module}-{parent_model.__name__.lower()}"

                out.append(
                    f"**Inherits from:** [`{parent_module}.{parent_model.__name__}`]({link})\n"
                )

            # Show class description, but hide if it's the same as parent's
            doc = inspect.getdoc(model)
            if doc:
                # Check if parent has the same description
                parent_has_same_doc = False
                if parent_model:
                    parent_doc = inspect.getdoc(parent_model)
                    if parent_doc == doc:
                        parent_has_same_doc = True

                # Only show description if it's different from parent or if there's no parent
                if not parent_has_same_doc:
                    # Filter out verbose Pydantic base class documentation
                    if (
                        "!!! abstract" in doc
                        or "A base class for creating Pydantic models" in doc
                    ):
                        # Only show the essential base class description
                        if "A base class for creating Pydantic models" in doc:
                            out.append("A base class for creating Pydantic models.\n")
                    else:
                        # Format JSON content in documentation
                        formatted_doc = format_json_in_doc(doc)
                        out.append(formatted_doc + "\n")

            if issubclass(model, BaseModel):
                rows = get_model_fields(model)
            elif dataclasses.is_dataclass(model):
                rows = get_dataclass_fields(model)
            else:
                continue

            if not rows:
                out.append("_No fields found._\n")
                continue

            # If this model inherits from another documented model, show only new fields
            if parent_model:
                parent_fields = (
                    get_model_fields(parent_model)
                    if issubclass(parent_model, BaseModel)
                    else get_dataclass_fields(parent_model)
                )
                parent_field_names = {field[0] for field in parent_fields}
                new_fields = [
                    field for field in rows if field[0] not in parent_field_names
                ]

                if new_fields:
                    out.append("#### Model Fields\n")
                    out.append("| Field | Type | Default | Description |")
                    out.append("|---|---|---|---|")
                    for f, t, d, desc in new_fields:
                        out.append(f"| `{f}` | {t} | {d} | {desc} |")
                    out.append("")
                else:
                    out.append("_No additional fields beyond parent class._\n")
            else:
                # Show all fields for models without inheritance
                out.append("| Field | Type | Default | Description |")
                out.append("|---|---|---|---|")
                for f, t, d, desc in rows:
                    out.append(f"| `{f}` | {t} | {d} | {desc} |")
                out.append("")

            # Add examples if available in model_config
            if issubclass(model, BaseModel):
                model_config = getattr(model, "model_config", {})
                if not model_config:
                    model_config = getattr(model, "__dict__", {}).get(
                        "model_config", {}
                    )
                if not model_config:
                    model_config = getattr(type(model), "model_config", {})

                # Custom JSON encoder to handle type objects
                class TypeEncoder(json.JSONEncoder):
                    def default(self, obj: Any) -> Any:
                        if isinstance(obj, type):
                            return obj.__name__
                        return super().default(obj)

                # Check for example_dict
                example_dict = model_config.get("example_dict")
                if example_dict:
                    # Check if parent also has the same example to avoid duplication
                    parent_has_same_example = False
                    if parent_model:
                        parent_model_config = getattr(parent_model, "model_config", {})
                        if not parent_model_config:
                            parent_model_config = getattr(
                                parent_model, "__dict__", {}
                            ).get("model_config", {})
                        if not parent_model_config:
                            parent_model_config = getattr(
                                type(parent_model), "model_config", {}
                            )

                        parent_example = parent_model_config.get("example_dict")
                        if parent_example == example_dict:
                            parent_has_same_example = True

                    if not parent_has_same_example:
                        out.append("#### Example\n")
                        out.append("```json\n")
                        out.append(json.dumps(example_dict, indent=2, cls=TypeEncoder))
                        out.append("\n```\n")

                # Check for json_schema_extra["examples"]
                json_schema_extra = model_config.get("json_schema_extra", {})
                examples = json_schema_extra.get("examples", [])
                if examples:
                    # Check if parent also has the same examples to avoid duplication
                    parent_has_same_examples = False
                    if parent_model:
                        parent_model_config = getattr(parent_model, "model_config", {})
                        if not parent_model_config:
                            parent_model_config = getattr(
                                parent_model, "__dict__", {}
                            ).get("model_config", {})
                        if not parent_model_config:
                            parent_model_config = getattr(
                                type(parent_model), "model_config", {}
                            )

                        parent_json_schema_extra = parent_model_config.get(
                            "json_schema_extra", {}
                        )
                        parent_examples = parent_json_schema_extra.get("examples", [])
                        if parent_examples == examples:
                            parent_has_same_examples = True

                    if not parent_has_same_examples:
                        if len(examples) == 1:
                            out.append("#### Example\n")
                            out.append("```json\n")
                            out.append(
                                json.dumps(examples[0], indent=2, cls=TypeEncoder)
                            )
                            out.append("\n```\n")
                        else:
                            out.append("#### Examples\n")
                            for i, example in enumerate(examples, 1):
                                out.append(f"**Example {i}:**\n")
                                out.append("```json\n")
                                out.append(
                                    json.dumps(example, indent=2, cls=TypeEncoder)
                                )
                                out.append("\n```\n")

        # Determine output filename based on group name
        if group_name == "extra":
            filename = "model_extra.md".lower()
        else:
            filename = f"model_{group_name}.md".lower()

        output_file = OUTPUT / filename

        # Add timestamp at the bottom
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out.append("")
        out.append(f"*Updated on {timestamp}*")

        output_file.write_text("\n".join(out))
        print(f"✅ Wrote model reference for group '{group_name}' to {output_file}")

    # Copy to external documentation directory
    try:
        # Ensure the target directory exists
        EXTERNAL_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing directory if it exists
        if EXTERNAL_DOC_PATH.exists():
            shutil.rmtree(EXTERNAL_DOC_PATH)

        shutil.copytree(OUTPUT, EXTERNAL_DOC_PATH)
        print(f"✅ Copied model reference directory to {EXTERNAL_DOC_PATH}")
    except Exception as e:
        print(f"⚠️  Failed to copy to external directory: {e}")


if __name__ == "__main__":
    generate_model_docs()
