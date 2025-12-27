#!/usr/bin/env python3
"""Script to automatically add type annotations to pytest test files."""

import re
from pathlib import Path


def add_pytest_imports(content: str) -> str:
    """Add pytest type imports if not present."""
    if "from pytest import" in content or "import pytest" not in content:
        return content

    # Add imports after the pytest import
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "import pytest":
            lines.insert(i + 1, "from pytest import FixtureRequest, MonkeyPatch")
            break

    # Add typing imports if not present
    has_any = "from typing import Any" in content or "from typing import (" in content
    if not has_any:
        # Find first import line
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i, "from typing import Any")
                break

    return "\n".join(lines)


def fix_monkeypatch_params(content: str) -> str:
    """Add type annotations to monkeypatch parameters."""
    # Fix function definitions with monkeypatch parameter
    pattern = r"def (test_\w+|setup_\w+)\(([^)]*monkeypatch[^)]*)\):"

    def replace_monkeypatch(match: re.Match[str]) -> str:  # type: ignore[reportUnknownParameterType]
        func_name = match.group(1)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        params = match.group(2)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]

        # Add type annotation if not present
        if "monkeypatch:" not in params:
            params = params.replace("monkeypatch", "monkeypatch: MonkeyPatch")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]

        return f"def {func_name}({params}):"

    content = re.sub(pattern, replace_monkeypatch, content)

    # Fix async functions
    pattern = r"async def (test_\w+|setup_\w+)\(([^)]*monkeypatch[^)]*)\):"
    content = re.sub(pattern, replace_monkeypatch, content)

    return content


def fix_request_params(content: str) -> str:
    """Add type annotations to request parameters."""
    # Fix function definitions with request parameter
    pattern = r"def (test_\w+|setup_\w+)\(([^)]*\brequest\b[^)]*)\):"

    def replace_request(match: re.Match[str]) -> str:  # type: ignore[reportUnknownParameterType]
        func_name = match.group(1)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        params = match.group(2)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]

        # Add type annotation if not present
        if "request:" not in params:
            params = params.replace("request", "request: FixtureRequest")  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]

        return f"def {func_name}({params}):"

    content = re.sub(pattern, replace_request, content)

    return content


def add_dict_type_annotations(content: str) -> str:
    """Add type arguments to dict types."""
    # Fix function return types
    pattern = r"-> dict:"
    content = content.replace(pattern, "-> dict[str, Any]:")

    # Fix parameter types
    pattern = r": dict\b"
    content = re.sub(pattern, ": dict[str, Any]", content)

    return content


def add_setenv_type_ignore(content: str) -> str:
    """Add type ignore to monkeypatch.setenv calls."""
    pattern = r"(\s+monkeypatch\.setenv\([^)]+\))$"
    content = re.sub(pattern, r"\1  # type: ignore[reportUnknownMemberType]", content, flags=re.MULTILINE)

    return content


def process_file(file_path: Path) -> None:
    """Process a single test file."""
    print(f"Processing {file_path}")

    content = file_path.read_text()

    # Apply all fixes
    content = add_pytest_imports(content)
    content = fix_monkeypatch_params(content)
    content = fix_request_params(content)
    content = add_dict_type_annotations(content)
    content = add_setenv_type_ignore(content)

    # Write back
    file_path.write_text(content)


def main() -> None:
    """Main entry point."""
    test_dir = Path("/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals/tests")

    # Find all test files
    test_files = list(test_dir.rglob("test_*.py"))

    print(f"Found {len(test_files)} test files")

    for test_file in test_files:
        try:
            process_file(test_file)
        except Exception as e:
            print(f"Error processing {test_file}: {e}")
            continue

    print("Done!")


if __name__ == "__main__":
    main()
