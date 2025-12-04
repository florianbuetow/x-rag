````markdown
# Adding Hypothesis to `x-rag`

This document describes how to integrate **Hypothesis** (property-based testing) into the `x-rag` codebase:

- How to add it as a dev dependency
- How to wire it into your existing `pytest` setup
- A **sensible base configuration** (profiles for local vs CI)
- How to add more configuration over time (without turning it into ceremony)
- Example tests tailored to RAG / indexing logic

Hypothesis is **purely local**: it requires no external services and runs entirely within your test process. 


---

## 1. Installation and pyproject changes

You already have a `[project.optional-dependencies].dev` section. Just add Hypothesis there.

### 1.1. Add Hypothesis to `pyproject.toml`

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-grpc>=0.8.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "mypy-protobuf>=3.5.0",
    "bandit[toml]>=1.7.8",
    "deptry>=0.20.0",
    "pygount>=1.6.4",
    "codespell>=2.3.0",
    # Type stubs
    "types-protobuf>=5.27.0",
    "types-grpcio",
    "types-grpcio-reflection",

    # Property-based testing
    "hypothesis>=6.100.0",
]
````

Any recent 6.x release is fine; pin the lower bound to something reasonably new.

### 1.2. Install dev dependencies

Assuming you’re using `uv` and a `make init` (or equivalent):

```bash
uv sync --group dev
```

or, if you prefer to be explicit:

```bash
uv sync --group dev --all-extras
```

You don’t need any extra pytest plugin: Hypothesis integrates with pytest out of the box.

---

## 2. Directory structure and naming

You already use:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

A simple pattern that works well:

```text
tests/
    unit/
        test_xxx.py
    integration/
        test_yyy.py
    property/
        test_chunking_properties.py
        test_indexing_properties.py
```

Property-based tests are just pytest test functions decorated with `@given(...)`, so they fit your current pattern with no extra configuration.

---

## 3. Minimal “Hello World” Hypothesis test

### 3.1. Example: testing basic invariants

Create `tests/property/test_example_properties.py`:

```python
from hypothesis import given
from hypothesis import strategies as st


def reverse_twice(s: str) -> str:
    return s[::-1][::-1]


@given(st.text())
def test_reverse_twice_is_identity(s: str) -> None:
    # Property: reversing twice yields the original string
    assert reverse_twice(s) == s
```

Run:

```bash
pytest tests/property/test_example_properties.py -q
```

If this passes, Hypothesis is wired correctly.

---

## 4. Sensible base configuration: settings and profiles

Hypothesis is primarily configured via **settings**, most often using:

* the `@settings(...)` decorator, and/or
* **profiles** (named configurations you can switch via an environment variable).

For your project, I’d recommend:

* One **“dev” profile**: faster feedback, fewer examples.
* One **“ci” profile**: more exhaustive, looser time limits.
* Default profile selected by an environment variable `HYPOTHESIS_PROFILE`, falling back to `"dev"`.

### 4.1. Create a central Hypothesis config module

Create `tests/hypothesis_config.py`:

```python
import os

from hypothesis import HealthCheck, settings


# Base defaults, applied to all profiles unless overridden
BASE_MAX_EXAMPLES = 100        # dev: fast but decent coverage
BASE_DEADLINE_MS = 200         # ms per example; adjust if code is slow


settings.register_profile(
    "dev",
    max_examples=BASE_MAX_EXAMPLES,
    deadline=BASE_DEADLINE_MS,
    suppress_health_check=[HealthCheck.too_slow],
)

# CI: more exhaustive, slightly higher deadline, more examples
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=500,
    suppress_health_check=[HealthCheck.too_slow],
)

# Debug: minimal shrinking, very verbose, handy for nasty failures
settings.register_profile(
    "debug",
    max_examples=20,
    deadline=None,  # disable per-example deadline
    suppress_health_check=[HealthCheck.too_slow],
    print_blob=True,
)


def _load_default_profile() -> None:
    profile = os.getenv("HYPOTHESIS_PROFILE", "dev")
    settings.load_profile(profile)


_load_default_profile()
```

This does two things:

1. Registers three profiles (`dev`, `ci`, `debug`).
2. Automatically loads a default profile when this module is imported.

### 4.2. Ensure the config is imported for all tests

There are two clean ways to ensure `hypothesis_config` is imported:

#### Option A — Use `conftest.py` in `tests/`

In `tests/conftest.py`:

```python
# Ensure our Hypothesis profiles are registered and loaded before any tests run
from tests import hypothesis_config  # noqa: F401
```

This is usually the simplest. Pytest auto-imports `conftest.py`.

#### Option B — Import in each property test module

In each property test file:

```python
from tests import hypothesis_config  # noqa: F401
from hypothesis import given, strategies as st
```

Option A is better; it centralizes the initialization.

---

## 5. Selecting profiles for different environments

With the `hypothesis_config` above, you can switch behavior via env vars, without changing code:

### 5.1. Local development (default)

No env var set:

```bash
pytest
```

→ uses `"dev"`:

* `max_examples=100`
* `deadline=200ms`

### 5.2. Continuous Integration

In your CI configuration (or Makefile):

```bash
export HYPOTHESIS_PROFILE=ci
pytest
```

or in a Makefile:

```make
test:
	HYPOTHESIS_PROFILE=ci pytest
```

### 5.3. Debugging tricky failures

When Hypothesis finds a nasty counterexample, you may want to relax deadlines, turn up verbosity:

```bash
HYPOTHESIS_PROFILE=debug pytest tests/property/test_chunking_properties.py -k "some_property"
```

This uses `max_examples=20`, `deadline=None`, and keeps the failing “data blob” for easier reproduction.

---

## 6. Writing meaningful property-based tests for `x-rag`

The value of Hypothesis depends on **which properties** you encode. Some canonical places in a RAG/search system:

1. **Chunking / splitting**
2. **Indexing idempotency & stability**
3. **Search invariants**
4. **Serialization / deserialization**
5. **Scoring and ranking invariants**

### 6.1. Example: chunking invariants

Suppose you have `chunk_text(text: str) -> list[str]`.

Properties you might want:

* Each chunk is non-empty.
* Each chunk length is ≤ `MAX_CHUNK_SIZE`.
* Concatenating chunks (with the appropriate join) reconstructs the original text, modulo allowed normalization.
* No unexpected exceptions for arbitrary Unicode.

```python
from hypothesis import given, strategies as st

from tests import hypothesis_config  # noqa: F401
from x_rag.chunking import chunk_text, MAX_CHUNK_SIZE


@given(st.text())
def test_chunk_text_basic_invariants(text: str) -> None:
    chunks = chunk_text(text)

    # Invariant 1: no empty chunks
    for c in chunks:
        assert c, "Chunk must not be empty"

    # Invariant 2: size bound
    for c in chunks:
        assert len(c) <= MAX_CHUNK_SIZE

    # Invariant 3: reconstruction (adjust if you normalize whitespace)
    reconstructed = "".join(chunks)
    assert reconstructed == text
```

If your chunker normalizes whitespace or applies other transforms, adapt the reconstruction check accordingly.

### 6.2. Example: idempotent indexing

Suppose `index_document(doc)` stores a document in Weaviate / MinIO, and `get_document(id)` retrieves it.

Property:

> Indexing the same logical document twice should not create conflicting state or change its content unexpectedly.

You can model this with a fake or in-memory index (for unit tests) and generate many variations of documents.

---

## 7. Per-test configuration (`@settings`)

Sometimes you need to override the global profile for a specific test:

* It’s very fast → increase `max_examples`.
* It’s inherently slow → raise `deadline` or disable it.
* You want more exploration in a specific area.

You can stack `@settings(...)` on top of `@given(...)`:

```python
from hypothesis import given, settings
from hypothesis import strategies as st


@given(st.text())
@settings(max_examples=300)
def test_chunk_text_extra_coverage(text: str) -> None:
    ...
```

This overrides only for this test; everything else still uses the profile.

---

## 8. Extending configuration over time

You can evolve the config in a controlled way by following a few rules:

1. **Never hardcode settings in many places.**
   Keep defaults in `tests/hypothesis_config.py` and adjust them there.

2. **Use profiles for environment-level differences.**

   * `dev`: fast feedback, strict deadlines
   * `ci`: more examples, slightly relaxed deadlines
   * `debug`: unlimited time, fewer examples, maximal introspection

3. **Make changes in small increments.**

   * If CI becomes flaky, first inspect failures; then adjust `deadline` / `max_examples` slightly.
   * Avoid “max_examples=10000” unless a test is very cheap.

4. **Introduce new profiles only when needed.**
   e.g. `stress` for occasional long-running stress checks.

Example extension:

```python
settings.register_profile(
    "stress",
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
```

Then occasionally:

```bash
HYPOTHESIS_PROFILE=stress pytest tests/property/ -k "indexing"
```

Run this locally or in a nightly CI job, not in normal pipelines.

---

## 9. Summary

* **Install** `hypothesis` as a `dev` dependency in `pyproject.toml`.
* **Centralize config** in `tests/hypothesis_config.py` using **profiles**.
* **Load profiles** via `HYPOTHESIS_PROFILE` env var (`dev` / `ci` / `debug`).
* **Integrate with pytest** via `tests/conftest.py` importing the config.
* **Start small** with a few high-value properties (chunking, indexing, search invariants).
* **Evolve** the settings slowly, keeping most configuration centralized and profile-based.

This setup gives you **non-redundant, high-leverage bug detection** with minimal operational overhead and no external services.

```markdown
(End of guide)
```
