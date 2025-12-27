#!/usr/bin/env python3
"""Add type annotations to all test function parameters."""

import re
from pathlib import Path


def add_any_import(content: str) -> str:
    """Add 'from typing import Any' if not present."""
    if "from typing import Any" in content:
        return content

    # Check if there's an existing typing import we can extend
    if "from typing import" in content:
        # Add Any to existing import
        content = re.sub(
            r"from typing import ([^\n]+)",
            lambda m: f"from typing import Any, {m.group(1)}" if "Any" not in m.group(1) else m.group(0),
            content,
            count=1,
        )
        return content

    # No typing import, add one at the top after docstring
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            lines.insert(i, "from typing import Any\n")
            return "\n".join(lines)

    return content


def add_types_to_test_params(content: str) -> str:
    """Add : Any to test function parameters missing types."""
    # Match test/setup functions - handle multi-line signatures
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a test/setup function definition
        if re.match(r"\s*(async\s+)?def\s+(test_|setup_)\w+\s*\(", line):
            # Collect the full function signature
            func_lines = [line]
            j = i + 1

            # Keep collecting lines until we find the closing paren and colon
            while j < len(lines):
                func_lines.append(lines[j])
                if re.search(r"\)\s*(?:->.*?)?:\s*$", lines[j]):
                    break
                j += 1

            # Process the collected signature
            full_sig = "\n".join(func_lines)
            processed_sig = process_function_signature(full_sig)

            # Add processed lines
            new_lines.extend(processed_sig.split("\n"))
            i = j + 1
        else:
            new_lines.append(line)
            i += 1

    return "\n".join(new_lines)


def split_params(params_str: str) -> list[str]:
    """Split parameters by comma, accounting for nested structures."""
    params = []
    current_param = ""
    paren_depth = 0
    bracket_depth = 0

    for char in params_str:
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "," and paren_depth == 0 and bracket_depth == 0:
            params.append(current_param.strip())
            current_param = ""
            continue

        current_param += char

    if current_param.strip():
        params.append(current_param.strip())

    return params


def add_type_annotation(param: str) -> str:
    """Add type annotation to a parameter if missing."""
    param = param.strip()
    if not param or param in ["self", "cls"] or ":" in param:
        return param
    return f"{param}: Any"


def format_signature(prefix: str, params: list[str], suffix: str) -> str:
    """Format signature as single or multi-line."""
    if len(params) <= 1 or all(len(p) < 30 for p in params):
        return f"{prefix}{', '.join(params)}{suffix}"
    else:
        formatted_params = ",\n        ".join(params)
        return f"{prefix}\n        {formatted_params},\n    {suffix}"


def process_function_signature(signature: str) -> str:
    """Process a function signature to add type annotations."""
    match = re.match(r"(.*?\()(.*?)(\)\s*(?:->.*?)?:\s*)$", signature, re.DOTALL)
    if not match:
        return signature

    prefix = match.group(1)
    params_str = match.group(2)
    suffix = match.group(3)

    params = split_params(params_str)
    new_params = [add_type_annotation(p) for p in params]

    return format_signature(prefix, new_params, suffix)


def process_file(file_path: Path) -> bool:
    """Process a single test file.

    Returns:
        True if file was modified
    """
    content = file_path.read_text()
    original = content

    # Add Any import
    content = add_any_import(content)

    # Add type annotations
    content = add_types_to_test_params(content)

    if content != original:
        file_path.write_text(content)
        return True
    return False


def main() -> None:
    """Process all test files."""
    test_dir = Path("tests")
    test_files = list(test_dir.rglob("test_*.py"))

    print(f"Found {len(test_files)} test files\n")

    modified = 0
    for test_file in sorted(test_files):
        if process_file(test_file):
            print(f"✓ Modified {test_file}")
            modified += 1

    print(f"\n✓ Modified {modified}/{len(test_files)} files")


if __name__ == "__main__":
    main()
