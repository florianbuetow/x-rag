# Pyright Configuration Guide

This document explains the strict type checking configuration for Pyright used in this project.

## Configuration Location

`pyrightconfig.json` in the project root.

## Type Checking Mode

**`typeCheckingMode: "strict"`**

Enables the most rigorous type checking. All type annotations are required and strictly validated.

## Environment Settings

- **`pythonVersion: "3.11"`** - Target Python 3.11 language features and stdlib stubs
- **`pythonPlatform: "Darwin"`** - Target macOS platform for platform-conditional stubs
- **`venvPath: "."`** - Virtual environment location (project root)
- **`venv: ".venv"`** - Virtual environment directory name
- **`stubPath: "stubs"`** - Custom type stub directory
- **`useLibraryCodeForTypes: true`** - Use library source code for type inference when stubs unavailable

## Included/Excluded Paths

**Included:**
- `src/` - Production code
- `tests/` - Test code
- `evals/` - Evaluation harness

**Excluded:**
- `**/__pycache__` - Python bytecode cache
- `**/.pytest_cache` - Pytest cache
- `**/node_modules` - Node.js dependencies (if any)
- `**/.venv` - Virtual environment
- `src/proto_gen` - Generated protobuf code

## Strict Type Inference

These settings prevent Pyright from falling back to `Any` types, forcing explicit type annotations.

### `strictListInference: true`

**Without:** `[1, "hello"]` → `list[Any]`
**With:** `[1, "hello"]` → `list[int | str]`

Forces you to be explicit about heterogeneous collections.

### `strictDictionaryInference: true`

**Without:** `{"a": 1, "b": "hello"}` → `dict[str, Any]`
**With:** `{"a": 1, "b": "hello"}` → `dict[str, int | str]`

Prevents `Any` in dictionary values.

### `strictSetInference: true`

**Without:** `{1, "hello"}` → `set[Any]`
**With:** `{1, "hello"}` → `set[int | str]`

Prevents `Any` in set types.

### `analyzeUnannotatedFunctions: true`

Analyzes and reports type errors in functions without type annotations.

**Without this:**
```python
def process(data):  # No annotations, no checking
    return data.invalid_method()  # Not caught
```

**With this:**
```python
def process(data):  # Error: Missing parameter type annotation
    return data.invalid_method()  # Error: Type of "data" is unknown
```

Forces all functions to have complete type annotations.

### `strictParameterNoneValue: true`

Requires `Optional[T]` when a parameter has a default value of `None`.

**Wrong:**
```python
def greet(name: str = None) -> str:  # Error: str not compatible with None
    pass
```

**Correct:**
```python
def greet(name: str | None = None) -> str:
    pass
```

### `deprecateTypingAliases: true`

Flags old `typing` module aliases as deprecated (Python 3.9+).

**Wrong (Python 3.11):**
```python
from typing import List, Dict, Tuple
def process(items: List[str]) -> Dict[str, int]:  # Error: Use built-in types
    pass
```

**Correct:**
```python
def process(items: list[str]) -> dict[str, int]:
    pass
```

Use built-in generic types: `list`, `dict`, `tuple`, `set`, etc.

### `enableReachabilityAnalysis: true`

Detects unreachable code after control flow statements.

```python
def example():
    return 42
    print("Never executed")  # Warning: Unreachable code
```

## Error-Level Diagnostics

These settings will **fail CI** if violations are found.

### `reportUnusedImport: "error"`

No unused imports allowed.

```python
import os  # Error if never used
from typing import List  # Error if never used
```

### `reportUnusedVariable: "error"`

No unused variables allowed.

```python
def process():
    result = expensive_computation()  # Error if result never used
```

### `reportUnusedClass: "error"`

No unused class definitions allowed.

```python
class UnusedHelper:  # Error if class never instantiated
    pass
```

### `reportUnusedFunction: "error"`

No unused function definitions allowed.

```python
def helper():  # Error if function never called
    pass
```

### `reportDuplicateImport: "error"`

No duplicate imports allowed.

```python
import os
from os import path
import os  # Error: Duplicate import
```

### `reportUnnecessaryTypeIgnoreComment: "error"`

No stale `# type: ignore` comments allowed.

```python
x: int = 42  # type: ignore  # Error: Comment has no effect
```

Ensures type ignore comments are removed when issues are fixed.

### `reportUnusedCoroutine: "error"`

Missing `await` on async functions (common bug).

```python
async def fetch_data():
    return "data"

def caller():
    fetch_data()  # Error: Coroutine never awaited
```

**Correct:**
```python
async def caller():
    await fetch_data()
```

### `reportMatchNotExhaustive: "error"`

`match` statements must cover all possible cases.

```python
from enum import Enum

class Status(Enum):
    PENDING = 1
    COMPLETE = 2
    FAILED = 3

def handle(status: Status):
    match status:
        case Status.PENDING:
            pass
        case Status.COMPLETE:
            pass
        # Error: Missing case for Status.FAILED
```

## Warning-Level Diagnostics

These settings will **not fail CI**, but will emit warnings.

### `reportImportCycles: "warning"`

Detects circular import dependencies.

```python
# a.py
from b import foo  # Warning if b.py imports from a.py
```

Circular imports work in Python but can cause import order issues.

### `reportUnusedCallResult: "warning"`

Warns when function return values are ignored.

```python
def get_user() -> User:
    return User()

get_user()  # Warning: Result ignored (possible mistake)
```

Useful for catching cases where you forgot to use the result.

## Basic Reporting (Already Strict Mode Defaults)

### `reportMissingImports: true`

Reports imports that cannot be resolved.

```python
import nonexistent_module  # Error: Cannot find module
```

### `reportMissingTypeStubs: true`

Reports when imported libraries have no type stubs.

```python
import some_library  # Warning: No type stubs available
```

## Running Type Checks

### Via Make (Recommended)

```bash
make code-typecheck  # Runs both mypy and pyright
```

### Directly

```bash
uv run pyright         # Check all included paths
uv run pyright src/    # Check specific directory
```

### In CI

Type checking is part of the CI pipeline:

```bash
make ci         # Runs all checks including code-typecheck
make ci-quiet   # Same but quieter output
```

## Why Both Mypy and Pyright?

This project runs **both** mypy and pyright for maximum type safety:

- **Mypy**: Python community standard, extensive plugin ecosystem (e.g., Pydantic)
- **Pyright**: Microsoft's type checker, faster, different inference rules

Running both catches more issues than either alone.

## Philosophy

**Strict type checking is non-negotiable in this project.**

- All production code (`src/`) must pass strict type checks
- No `# type: ignore` comments without documented justification
- No `Any` types unless genuinely needed for dynamic behavior
- Clean code: no unused imports, variables, or dead code

Type safety prevents runtime errors and makes refactoring safer.
