#!/usr/bin/env python3
"""Add type annotations to test functions based on fixture types."""

import re
import sys
from pathlib import Path
from re import Match

# Common fixture type mappings
FIXTURE_TYPES = {
    "monkeypatch": "MonkeyPatch",
    "tmp_path": "Path",
    "caplog": "LogCaptureFixture",
    "capsys": "CaptureFixture[str]",
    "request": "FixtureRequest",
    # Add more as needed
}


def add_type_annotations(file_path: Path) -> bool:
    """Add type annotations to test functions in a file."""
    content = file_path.read_text()
    original = content

    # Pattern to match test function definitions
    pattern = r"def (test_\w+)\((.*?)\):"

    def add_types(match: Match[str]) -> str:
        func_name = match.group(1)
        params = match.group(2).strip()

        if not params or ":" in params:  # Already has types
            return match.group(0)

        # Split parameters
        param_list = [p.strip() for p in params.split(",")]
        typed_params = []

        for param in param_list:
            if "=" in param:  # Has default value
                name, default = param.split("=", 1)
                name = name.strip()
            else:
                name = param
                default = None

            # Get type from fixture mapping
            param_type = FIXTURE_TYPES.get(name, "Any")

            if default:
                typed_params.append(f"{name}: {param_type} = {default}")
            else:
                typed_params.append(f"{name}: {param_type}")

        return f"def {func_name}({', '.join(typed_params)}) -> None:"

    content = re.sub(pattern, add_types, content)

    if content != original:
        file_path.write_text(content)
        return True
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_test_types.py <test_file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if add_type_annotations(file_path):
        print(f"✓ Added type annotations to {file_path}")
    else:
        print(f"✗ No changes needed for {file_path}")
