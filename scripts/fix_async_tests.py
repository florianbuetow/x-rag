#!/usr/bin/env python3
"""Fix async test functions."""

from pathlib import Path


def fix_async_tests(content: str) -> str:
    """Fix test functions that should be async."""
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # If this is @pytest.mark.asyncio
        if "@pytest.mark.asyncio" in line:
            new_lines.append(line)
            i += 1
            # Next line should be async def
            if i < len(lines):
                next_line = lines[i]
                # If it's def but not async def, make it async
                if next_line.strip().startswith("def test_") or next_line.strip().startswith("def setup_"):
                    next_line = next_line.replace("def ", "async def ", 1)
                new_lines.append(next_line)
                i += 1
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines)


def process_file(file_path: Path) -> bool:
    """Process a single file."""
    try:
        content = file_path.read_text()
        original = content

        content = fix_async_tests(content)

        if content != original:
            file_path.write_text(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main() -> None:
    """Main entry point."""
    test_dir = Path("/Users/flo/Developer/github/test/x-rag/florian-hackathon-evals/tests")

    test_files = list(test_dir.rglob("test_*.py"))

    print(f"Processing {len(test_files)} test files...")

    modified_count = 0
    for test_file in test_files:
        if process_file(test_file):
            modified_count += 1
            print(f"✓ {test_file.relative_to(test_dir.parent)}")

    print(f"\nFixed {modified_count} files")


if __name__ == "__main__":
    main()
