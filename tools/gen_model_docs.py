# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# gen_model_docs.py

"""
Model Documentation Generator

** DISCLAIMER **
This script has been almost completely written by Cursor and has not really been reviewed.
It does the job (more or less). It probably deserves a good review...
Most importantly, it should not be used as a reference for code quality / style of the supervaizer library.
***

# TODO: full review / optimization / testing

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
import re
import importlib
import inspect
import os
import pkgutil
import dataclasses
import shutil
import json
from datetime import datetime
import sys
from types import ModuleType
from pathlib import Path
from typing import Any, Iterator, Union, Dict, List, Set
from pydantic import BaseModel
from rich import print

PACKAGE = "supervaizer"
LOCAL_DOCS = Path("./docs")
LOCAL_MODEL_DOCS = LOCAL_DOCS / "model_reference"
EXTERNAL_DOCS = Path(os.environ.get("EXTERNAL_DOCS", "../"))
EXTERNAL_DOC_PATH = EXTERNAL_DOCS / "supervaizer-controller/model_reference"
EXTERNAL_REF_PATH = EXTERNAL_DOCS / "supervaizer-controller/ref"


if not LOCAL_MODEL_DOCS.exists():
    print(f"⚠️  LOCAL_MODEL_DOCS directory {LOCAL_MODEL_DOCS} does not exist")
    sys.exit(1)
if not EXTERNAL_DOC_PATH.exists():
    print(f"⚠️  EXTERNAL_DOC_PATH directory {EXTERNAL_DOC_PATH} does not exist")
    sys.exit(1)
if not EXTERNAL_REF_PATH.exists():
    print(f"⚠️  EXTERNAL_REF_PATH directory {EXTERNAL_REF_PATH} does not exist")
    sys.exit(1)

print(f"LOCAL_MODEL_DOCS: {LOCAL_MODEL_DOCS}")
print(f"EXTERNAL_DOCS: {EXTERNAL_DOCS}")
print(f"EXTERNAL_DOC_PATH: {EXTERNAL_DOC_PATH}")
print(f"EXTERNAL_REF_PATH: {EXTERNAL_REF_PATH}")


def generate_slug(text: str) -> str:
    """Generate a URL-friendly slug from heading text."""
    # Convert to lowercase and replace spaces/hyphens with hyphens
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


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
                json_content_stripped = "\n".join(
                    line.strip() for line in json_lines_raw
                )

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


def clean_type_string(type_str: str) -> str:
    """Clean up type strings to make them more readable."""
    # Remove typing. prefix from common types
    type_str = type_str.replace("typing.", "")

    # Clean up module paths for common types
    type_str = type_str.replace("supervaizer.", "")

    # Handle <class 'type'> format
    if type_str.startswith("<class '") and type_str.endswith("'>"):
        inner_type = type_str[8:-2]  # Remove "<class '" and "'>"
        # Extract just the type name, not the full module path
        if "." in inner_type:
            inner_type = inner_type.split(".")[-1]
        return inner_type

    # Handle specific cases for better readability
    type_str = type_str.replace("Dict", "Dict")
    type_str = type_str.replace("List", "List")
    type_str = type_str.replace("Optional", "Optional")
    type_str = type_str.replace("Union", "Union")

    return type_str


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
            cleaned_inner_type = clean_type_string(inner_type)
            type_str = f"`{cleaned_inner_type}` | `None`"
        else:
            # Handle generic types and other types
            type_str_raw = str(type_obj)
            if "[" in type_str_raw and "]" in type_str_raw:
                # Complex type like list[str], dict[str, int], etc.
                cleaned_type = clean_type_string(type_str_raw)
                type_str = f"`{cleaned_type}`"
            else:
                cleaned_type = clean_type_string(type_str_raw)
                type_str = f"`{cleaned_type}`"

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
    model: type[BaseModel],
    models_by_group: Dict[str, List[Union[type[BaseModel], type]]],
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
    model: type[BaseModel],
    models_by_group: Dict[str, List[Union[type[BaseModel], type]]],
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
            cleaned_inner_type = clean_type_string(inner_type)
            type_str = f"`{cleaned_inner_type}` | `None`"
        else:
            # Handle generic types and other types
            type_str_raw = str(type_)
            if "[" in type_str_raw and "]" in type_str_raw:
                # Complex type like list[str], dict[str, int], etc.
                cleaned_type = clean_type_string(type_str_raw)
                type_str = f"`{cleaned_type}`"
            else:
                cleaned_type = clean_type_string(type_str_raw)
                type_str = f"`{cleaned_type}`"

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


def add_header(page_name: str) -> list[str]:
    """Add header content to the documentation."""
    out = [page_name, ""]
    return out


def add_footer() -> list[str]:
    """Add footer content with timestamp to the documentation."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = []
    out.append("")
    out.append(f"*Uploaded on {timestamp}*")
    return out


def generate_model_docs() -> None:
    # Get the supervaizer version
    try:
        from supervaizer.__version__ import VERSION

        version = VERSION
    except (ImportError, AttributeError):
        version = "N/A"

    # Ensure the output directory exists
    LOCAL_MODEL_DOCS.mkdir(parents=True, exist_ok=True)

    # Get all models and their reference_group
    models_by_group: Dict[str, List[Union[type[BaseModel], type]]] = {}
    seen = set()

    # Track all generated slugs across all files for link validation
    all_slugs: Dict[str, Set[str]] = {}

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

    # First pass: build all slugs for link validation
    for group_name, models in models_by_group.items():
        if group_name not in all_slugs:
            all_slugs[group_name] = set()
        for model in models:
            module_name = model.__module__.replace("supervaizer.", "")
            heading_text = f"{module_name}.{model.__name__}"
            slug = generate_slug(heading_text)
            all_slugs[group_name].add(slug)

    # Second pass: generate documentation for each group
    for group_name, models in models_by_group.items():
        out = add_header(f"# Model Reference {group_name}")
        out.append(f"**Version:** {version}\n")

        for model in models:
            # Remove "supervaizer." prefix from module name
            module_name = model.__module__.replace("supervaizer.", "")
            heading_text = f"{module_name}.{model.__name__}"
            slug = generate_slug(heading_text)
            out.append(f"### `{heading_text}`\n")

            # Check if this model inherits from another documented model
            parent_model = get_parent_model(model, models_by_group)
            if parent_model:
                parent_module = parent_model.__module__.replace("supervaizer.", "")
                parent_group = get_model_group(parent_model, models_by_group)

                # Generate the expected slug for the parent
                parent_heading = f"{parent_module}.{parent_model.__name__}"
                parent_slug = generate_slug(parent_heading)

                # Check if the parent slug exists in the target group
                parent_slug_exists = (
                    parent_group in all_slugs and parent_slug in all_slugs[parent_group]
                )

                # Generate appropriate link based on whether parent is in same file
                if parent_group == group_name:
                    if parent_slug_exists:
                        link = f"#{parent_slug}"
                        out.append(
                            f"**Inherits from:** [`{parent_module}.{parent_model.__name__}`]({link})\n"
                        )
                    else:
                        out.append(
                            f"**Inherits from:** `{parent_module}.{parent_model.__name__}`\n"
                        )
                else:
                    # Cross-file link - check if parent slug exists in the target group
                    target_group_slugs = all_slugs.get(parent_group, set())
                    parent_slug_exists_in_target = parent_slug in target_group_slugs

                    if parent_slug_exists_in_target:
                        if parent_group == "extra":
                            link = f"model_extra.md#{parent_slug}"
                        else:
                            link = f"model_{parent_group.lower()}.md#{parent_slug}"
                        out.append(
                            f"**Inherits from:** [`{parent_module}.{parent_model.__name__}`]({link})\n"
                        )
                    else:
                        out.append(
                            f"**Inherits from:** `{parent_module}.{parent_model.__name__}`\n"
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

        output_file = LOCAL_MODEL_DOCS / filename

        # Add timestamp at the bottom
        out.extend(add_footer())

        output_file.write_text("\n".join(out))
        print(f"✅ Wrote model reference for group '{group_name}' to {output_file}")

    # Copy to external documentation directory
    try:
        # Ensure the target directory exists
        EXTERNAL_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing directory if it exists
        if EXTERNAL_DOC_PATH.exists():
            shutil.rmtree(EXTERNAL_DOC_PATH)

        shutil.copytree(LOCAL_MODEL_DOCS, EXTERNAL_DOC_PATH)
        print(f"✅ Copied model reference directory to {EXTERNAL_DOC_PATH}")
    except Exception as e:
        print(f"⚠️  Failed to copy to external directory: {e}")


def copy_to_docs_dir() -> None:
    """Copy all docs/*.md and some root files to the OUTPUT/ref folder."""

    # Get all .md files from docs directory
    docs_md_files = list(LOCAL_DOCS.glob("*.md"))
    print(f"docs_md_files: {docs_md_files}")

    # Add root directory markdown files
    root_md_files = [
        Path("./CODE_OF_CONDUCT.md"),
        Path("./CONTRIBUTING.md"),
        Path("./LICENSE.md"),
        Path("./README.md"),
    ]

    # Combine all markdown files
    md_files = docs_md_files + [f for f in root_md_files if f.exists()]

    for md_file in md_files:
        try:
            # Read the content of the markdown file
            content = md_file.read_text()

            # Replace "docs/" links with empty strings
            content = content.replace("(docs/", "(")

            # Add footer to the content
            footer_lines = add_footer()
            content_with_footer = content + "\n" + "\n".join(footer_lines)

            # Write the content with footer to the output directory
            output_path = EXTERNAL_REF_PATH / md_file.name
            output_path.write_text(content_with_footer)

            print(f"✅ Copied {md_file} to {output_path} (with footer)")
        except Exception as e:
            print(f"⚠️  Failed to copy {md_file}: {e}")

    if md_files:
        print(
            f"✅ Copied {len(md_files)} markdown files from docs/ and root to {EXTERNAL_REF_PATH}"
        )
    else:
        print("ℹ️  No .md files found in docs/ directory or root")


if __name__ == "__main__":
    generate_model_docs()
    copy_to_docs_dir()
