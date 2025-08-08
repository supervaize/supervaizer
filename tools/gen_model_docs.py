# gen_model_docs.py

"""
Model Documentation Generator

This script automatically generates model reference documentation for the supervaizer package.
It scans through all modules in the package and identifies Pydantic BaseModel classes and
dataclasses, then generates a markdown file with their field definitions, types, defaults,
and descriptions.

Features:
- Discovers all Pydantic models and dataclasses in the package
- Extracts field information including types, defaults, and descriptions
- Generates markdown tables for easy reading
- Handles both Pydantic v1 and v2 field structures
- Supports dataclass metadata for field descriptions

Usage:
    python tools/gen_model_docs.py

Output:
    Creates docs/model_reference.md with comprehensive model documentation
    And also, copies the file to the external documentation directory
"""

from __future__ import annotations
import importlib
import inspect
import pkgutil
import dataclasses
import shutil
import json
from types import ModuleType
from pathlib import Path
from typing import Any, Iterator
from pydantic import BaseModel

PACKAGE = "supervaizer"
OUTPUT = Path("docs/model_reference.md")
EXTERNAL_DOC_PATH = Path(
    "../doc/supervaize-doc/docs/Supervaizer Controller/model_reference.md"
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


def get_model_fields(model: type[BaseModel]) -> list[tuple[str, str, str, str]]:
    fields = getattr(model, "model_fields", {}) or getattr(model, "__fields__", {})
    result: list[tuple[str, str, str, str]] = []
    for name, field in fields.items():
        # Try to get type/annotation consistently across pydantic versions
        type_obj = getattr(field, "annotation", None) or getattr(field, "type_", None)
        type_str = getattr(type_obj, "__name__", str(type_obj))

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
                    default_repr = "—"
                else:
                    s = repr(default_val)
                    if "Undefined" in s or "PydanticUndefined" in s:
                        default_repr = "—"
                    else:
                        default_repr = s
            else:
                default_repr = "—"

        result.append((name, type_str, default_repr, desc))
    return result


def get_dataclass_fields(model: Any) -> list[tuple[str, str, str, str]]:
    fields = getattr(model, "__dataclass_fields__", {})
    result = []
    for name, field in fields.items():
        type_ = getattr(field, "type", str)
        type_str = getattr(type_, "__name__", str(type_))
        required = (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        )
        default = (
            "**required**"
            if required
            else repr(field.default)
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

    out = ["# Model Reference", ""]
    out.append(f"**Version:** {version}\n")
    seen = set()
    for mod in iter_modules(PACKAGE):
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if obj in seen or obj.__module__.startswith("pydantic"):
                continue
            if issubclass(obj, BaseModel):
                # Remove "supervaizer." prefix from module name
                module_name = obj.__module__.replace("supervaizer.", "")
                out.append(f"## `{module_name}.{obj.__name__}`\n")
                doc = inspect.getdoc(obj)
                if doc:
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
                rows = get_model_fields(obj)
            elif dataclasses.is_dataclass(obj):
                # Remove "supervaizer." prefix from module name
                module_name = obj.__module__.replace("supervaizer.", "")
                out.append(f"## `{module_name}.{obj.__name__}`\n")
                doc = inspect.getdoc(obj)
                if doc:
                    # Format JSON content in documentation
                    formatted_doc = format_json_in_doc(doc)
                    out.append(formatted_doc + "\n")
                rows = get_dataclass_fields(obj)
            else:
                continue
            seen.add(obj)

            if not rows:
                out.append("_No fields found._\n")
                continue

            out.append("| Field | Type | Default | Description |")
            out.append("|---|---|---|---|")
            for f, t, d, desc in rows:
                out.append(f"| `{f}` | `{t}` | {d} | {desc} |")
            out.append("")

    OUTPUT.write_text("\n".join(out))
    print(f"✅ Wrote model reference to {OUTPUT}")

    # Copy to external documentation directory
    try:
        # Ensure the target directory exists
        EXTERNAL_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUTPUT, EXTERNAL_DOC_PATH)
        print(f"✅ Copied model reference to {EXTERNAL_DOC_PATH}")
    except Exception as e:
        print(f"⚠️  Failed to copy to external directory: {e}")


if __name__ == "__main__":
    generate_model_docs()
