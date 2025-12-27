#!/usr/bin/env python3
"""Remove unused type: ignore comments reported by mypy."""

import re
import subprocess
from collections import defaultdict
from pathlib import Path


def get_unused_ignores() -> dict[str, set[int]]:
    """Run mypy and parse unused-ignore errors."""
    result = subprocess.run(
        ["uv", "run", "mypy", "src", "tests", "--config-file", "pyproject.toml"],
        capture_output=True,
        text=True,
        cwd="/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals",
    )

    output = result.stdout + result.stderr
    errors = defaultdict(set)

    # Parse error lines - handle both single and multiline formats
    # Pattern: file.py:123: error: Unused
    pattern = r"^(.+?):(\d+): error: Unused"

    for line in output.split("\n"):
        match = re.match(pattern, line)
        if match:
            file_path, line_num = match.groups()
            errors[file_path].add(int(line_num))

    return dict(errors)


def remove_type_ignores_from_file(file_path: str, line_numbers: set[int]) -> bool:
    """Remove type: ignore comments from specific lines."""
    try:
        path = Path(file_path)
        if not path.exists():
            return False

        lines = path.read_text().splitlines(keepends=True)
        modified = False

        for line_num in sorted(line_numbers):
            if line_num > len(lines):
                continue

            idx = line_num - 1
            line = lines[idx]

            # Remove type: ignore comments (both specific and general)
            # Pattern matches:  # type: ignore[...] or  # type: ignore
            new_line = re.sub(r"\s*# type: ignore(\[[\w\s,]+\])?", "", line)

            if new_line != line:
                lines[idx] = new_line
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
    base_dir = Path("/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals")
    print("Analyzing unused type: ignore comments...")
    errors = get_unused_ignores()

    print(f"Found unused ignores in {len(errors)} files")

    modified_count = 0
    for file_path, line_nums in errors.items():
        # Convert to absolute path if relative
        abs_path = file_path if Path(file_path).is_absolute() else str(base_dir / file_path)
        if remove_type_ignores_from_file(abs_path, line_nums):
            modified_count += 1
            print(f"✓ {file_path} ({len(line_nums)} lines)")

    print(f"\nModified {modified_count} files")


if __name__ == "__main__":
    main()
