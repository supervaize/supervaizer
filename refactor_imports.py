#!/usr/bin/env python3
"""
Script to refactor relative imports to absolute imports in the supervaizer package.
"""

import os
import re


def process_file(filepath):
    """
    Process a single Python file to convert relative imports to absolute imports.
    """
    with open(filepath, "r") as f:
        content = f.read()

    # Get the module path from the file path
    rel_path = os.path.relpath(
        filepath, start=os.path.dirname(os.path.dirname(filepath))
    )
    module_path = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
    package_parts = module_path.split(".")
    package_name = package_parts[0]  # Should be 'supervaizer'

    # Replace relative imports with absolute imports

    # Pattern 1: from . import module
    content = re.sub(
        r"from\s+\.\s+import\s+(.+)", rf"from {package_name} import \1", content
    )

    # Pattern 2: from .module import symbol
    content = re.sub(
        r"from\s+\.([a-zA-Z0-9_]+)\s+import\s+(.+)",
        rf"from {package_name}.\1 import \2",
        content,
    )

    # Pattern 3: from .. import module  (for deeper nesting)
    def replace_deeper_import(match):
        dots, module = match.groups()
        # Count the number of dots to determine how far up to go
        level = len(dots) + 1
        # Get the current module parts and remove 'level' number of parts from the end
        current_parts = module_path.split(".")
        base_path = ".".join(current_parts[:-level])
        return f"from {base_path} import {module}"

    content = re.sub(
        r"from\s+(\.+)([a-zA-Z0-9_]+)\s+import\s+(.+)",
        lambda m: f"from {package_name}{'.' + m.group(2) if m.group(2) else ''} import {m.group(3)}",
        content,
    )

    # Pattern 4: import .module
    content = re.sub(
        r"import\s+\.([a-zA-Z0-9_.]+)", rf"import {package_name}.\1", content
    )

    # Write the modified content back to the file
    with open(filepath, "w") as f:
        f.write(content)

    print(f"Processed {filepath}")


def main():
    """
    Main function to process all Python files in the supervaizer directory.
    """
    for root, _, files in os.walk("supervaizer"):
        for file in files:
            if file.endswith(".py") and "__pycache__" not in root:
                process_file(os.path.join(root, file))


if __name__ == "__main__":
    main()
