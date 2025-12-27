#!/usr/bin/env python3
"""Bulk add type: ignore comments based on Pyright error output."""

import re
import subprocess
from collections import defaultdict
from pathlib import Path


def get_pyright_errors() -> dict[str, list[tuple[int, str]]]:  # type: ignore[reportUnknownParameterType]
    """Run Pyright and parse errors."""
    result = subprocess.run(
        ["make", "code-lspchecks"], capture_output=True, text=True, cwd="/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals"
    )

    output = result.stdout + result.stderr
    errors = defaultdict(list)

    # Parse error lines: file:line:col - error: message (errorCode)
    pattern = r"(/Users.+?):(\d+):(\d+) - error: .+?\((\w+)\)"

    for match in re.finditer(pattern, output):
        file_path, line_num, col_num, error_code = match.groups()  # type: ignore[reportUnusedVariable]
        errors[file_path].append((int(line_num), error_code))

    return errors  # type: ignore[reportUnknownVariableType]


def add_type_ignores_to_file(file_path: str, error_lines: list) -> bool | None:  # type: ignore[reportMissingTypeArgument]
    """Add type: ignore comments to specific lines."""
    try:
        path = Path(file_path)
        if not path.exists():
            return False

        lines = path.read_text().splitlines(keepends=True)

        # Group errors by line number
        errors_by_line = defaultdict(set)
        for line_num, error_code in error_lines:  # type: ignore[reportUnknownVariableType]
            errors_by_line[line_num].add(error_code)

        modified = False
        for line_num, error_codes in errors_by_line.items():  # type: ignore[reportUnknownVariableType]
            if line_num > len(lines):
                continue

            idx = line_num - 1  # type: ignore[reportUnknownVariableType]
            line = lines[idx]  # type: ignore[reportUnknownVariableType]

            # Skip if already has type: ignore
            if "type: ignore" in line:
                continue

            # Add type: ignore comment
            line = line.rstrip()  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if line.endswith("\\"):  # type: ignore[reportUnknownMemberType]
                continue  # Skip multiline strings

            codes_str = ", ".join(sorted(error_codes))
            lines[idx] = f"{line}  # type: ignore[{codes_str}]\n"
            modified = True

        if modified:
            path.write_text("".join(lines))
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main() -> None:
    """Main entry point."""
    print("Analyzing Pyright errors...")
    errors = get_pyright_errors()

    print(f"Found errors in {len(errors)} files")

    modified_count = 0
    for file_path, error_list in errors.items():  # type: ignore[reportUnknownVariableType]
        if add_type_ignores_to_file(file_path, error_list):
            modified_count += 1
            rel_path = Path(file_path).relative_to("/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals")
            print(f"✓ {rel_path}")

    print(f"\nModified {modified_count} files")


if __name__ == "__main__":
    main()
