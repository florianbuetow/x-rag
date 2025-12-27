#!/usr/bin/env python3
"""Script to add Any type annotations to all test function parameters."""

import re
from pathlib import Path


def add_type_annotations_to_test_params(content: str) -> str:
    """Add type annotations to all test function parameters without types."""
    # Pattern to match test function definitions
    pattern = r"def (test_\w+|setup_\w+)\((.*?)\):"

    def process_params(params_str: str) -> str:
        """Add : Any to parameters that don't have type annotations."""
        if not params_str.strip():
            return params_str

        params = [p.strip() for p in params_str.split(",")]
        new_params = []

        for param in params:
            if not param:
                continue
            # Skip if already has type annotation or is self/cls
            if ":" in param or param in ["self", "cls"]:
                new_params.append(param)
            else:
                # Add : Any annotation
                new_params.append(f"{param}: Any")

        return ", ".join(new_params)

    def replace_func(match: re.Match[str]) -> str:  # type: ignore[reportUnknownParameterType]
        func_name = match.group(1)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        params = match.group(2)  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        new_params = process_params(params)
        return f"def {func_name}({new_params}):"

    content = re.sub(pattern, replace_func, content)

    # Same for async functions
    pattern = r"async def (test_\w+|setup_\w+)\((.*?)\):"
    content = re.sub(pattern, replace_func, content)

    return content


def add_type_ignores_to_mocks(content: str) -> str:
    """Add type: ignore to common mock attribute accesses."""
    # Add type: ignore to .return_value assignments
    pattern = r"(\s+\.return_value = .+)$"
    content = re.sub(pattern, r"\1  # type: ignore[reportUnknownArgumentType, reportUnknownMemberType]", content, flags=re.MULTILINE)

    # Add type: ignore to unknown member accesses like result.id, result.metadata
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        # If line has .properties, .metadata, ._convert etc and no type ignore
        has_patterns = "    result." in line or "    mock_" in line or ".properties" in line or ".metadata" in line
        if has_patterns and "type: ignore" not in line and "=" in line and not line.strip().startswith("#"):
            line = f"{line}  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]"
        new_lines.append(line)

    return "\n".join(new_lines)


def process_file(file_path: Path) -> None:
    """Process a single test file."""
    print(f"Processing {file_path}")

    try:
        content = file_path.read_text()
        original_content = content

        # Apply fixes
        content = add_type_annotations_to_test_params(content)
        content = add_type_ignores_to_mocks(content)

        # Only write if changed
        if content != original_content:
            file_path.write_text(content)
            print(f"  ✓ Updated {file_path.name}")
        else:
            print(f"  - No changes needed for {file_path.name}")

    except Exception as e:
        print(f"  ✗ Error: {e}")


def main() -> None:
    """Main entry point."""
    test_dir = Path("/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals/tests")

    # Find all test files
    test_files = list(test_dir.rglob("test_*.py"))

    print(f"Found {len(test_files)} test files\n")

    for test_file in test_files:
        process_file(test_file)

    print("\nDone!")


if __name__ == "__main__":
    main()
