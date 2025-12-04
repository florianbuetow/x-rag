# Adding Semgrep to `x-rag`

This guide explains how to add **Semgrep** to `x-rag` as a **local, offline static analysis tool**:

* How to install it and wire it into your existing stack
* How to structure rule files
* A **sensible base configuration** that is *not* redundant with ruff/mypy/bandit
* How to extend the configuration incrementally over time

We will only use **Semgrep Community Edition** via the CLI, with **local YAML rules**, no SaaS platform and no external services. Semgrep is an open-source static analyzer that uses patterns written in YAML to search code structurally, not just with regex.

---

## 1. Install Semgrep as a dev dependency

You already have a `dev` optional dependency group. Add Semgrep there.

### 1.1. `pyproject.toml` changes

Add **one line** to your existing `[project.optional-dependencies].dev` list:

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

    # Static semantic analysis (pattern-based)
    "semgrep>=1.144.0",
]
```

`1.144.0` is currently the latest Semgrep version on PyPI; using `>=1.144.0` keeps you close to current releases while allowing upgrades.

### 1.2. Install dev dependencies

Assuming `uv`:

```bash
uv sync --group dev
```

This installs Semgrep CLI alongside your existing dev tooling.

---

## 2. Repository layout for Semgrep

Introduce a dedicated folder for rules and keep them versioned with the repo:

```text
x-rag/
  semgrep/
    python-base.yml
    rag-architecture.yml
  .semgrepignore
  pyproject.toml
  src/
  tests/
  ...
```

This layout is consistent with Semgrep’s recommended practice of putting custom rules in YAML files within a project folder and running them with `semgrep --config ./semgrep`.

We will:

* Put all rule files under `semgrep/`.
* Use `semgrep --config semgrep/ ...` as the primary invocation.
* Use `.semgrepignore` to control scope and noise.

No registry rule packs are required; everything can work fully offline once the package is installed.

---

## 3. Base rule file: `python-base.yml`

Start with a small, **generic but useful** rule set that:

* Catches patterns *not* already covered well by ruff/mypy/bandit.
* Demonstrates how to write rules so you can extend later.

Create `semgrep/python-base.yml`:

```yaml
rules:
  # 1) Discourage 'is' for value comparison (classic Python bug)
  # Example pattern taken from Semgrep docs, adapted to your context.
  # https://semgrep.dev/docs/running-rules/
  - id: python.lang.correctness.is-vs-eq
    languages: [python]
    message: >
      The operator 'is' is for reference equality, not value equality.
      Use '==' instead unless you really want identity comparison.
    severity: WARNING
    pattern: |
      $X is $Y
    # Narrow to typical value comparison contexts (not 'is None')
    pattern-not: |
      $X is None

  # 2) Forbid direct 'eval' usage
  - id: python.security.forbid-eval
    languages: [python]
    message: >
      Avoid eval(). Use safer parsing or explicit dispatch.
    severity: ERROR
    patterns:
      - pattern: eval($EXPR)

  # 3) Enforce using your own OpenAI client wrapper, not direct openai.Client()
  - id: xrag.openai.use-internal-wrapper
    languages: [python]
    message: >
      Use the internal X-RAG OpenAI client wrapper instead of direct openai.Client().
    severity: ERROR
    patterns:
      - pattern: openai.Client($ARGS)
    # Allow exceptions, e.g. in test or experimental modules, if you prefer:
    # paths:
    #   exclude:
    #     - "tests/**"
```

This file illustrates:

* **Single-pattern rule** (`is-vs-eq`).
* **Simple security rule** (forbid `eval`).
* **Architecture rule** enforcing your own wrapper (Semgrep’s strength).

You can evolve this into many rules; for now it’s a minimal, non-redundant baseline.

---

## 4. Architecture rules: `rag-architecture.yml`

You can use Semgrep to encode architectural guardrails (where ruff/mypy are blind). For example:

* “No direct Kafka producers in FastAPI handlers.”
* “No direct Redis calls in API layer; must go through infra module.”

Example `semgrep/rag-architecture.yml`:

```yaml
rules:
  # Disallow direct aiokafka usage in API handlers; enforce a messaging adapter.
  - id: xrag.arch.no-direct-aiokafka-in-api
    languages: [python]
    message: >
      API layer must not use aiokafka directly. Use the messaging adapter instead.
    severity: ERROR
    patterns:
      - pattern: aiokafka.$FUNC(...)
    paths:
      include:
        - "src/xrag/api/**"

  # Example: no direct redis import in domain layer
  - id: xrag.arch.no-direct-redis-in-domain
    languages: [python]
    message: >
      Domain logic must not depend directly on redis. Inject a repository instead.
    severity: WARNING
    patterns:
      - pattern: from redis import $X
    paths:
      include:
        - "src/xrag/domain/**"
```

The `paths` key constrains where rules apply. This is extremely useful to reduce noise and keep rules aligned with your architecture.

---

## 5. Base `.semgrepignore` to control scope

Semgrep respects `.gitignore` and a default ignore list, and also supports a project-level `.semgrepignore` file for customizing which files/folders are scanned.

Create `.semgrepignore` at repo root:

```gitignore
# Start from Semgrep defaults but customize for x-rag.

# Include .gitignore rules as well (recommended).
:include .gitignore

# Explicit ignores
.venv/
venv/
build/
dist/
reports/
.data/
.cache/
src/proto_gen/

# If you want tests scanned by Semgrep, DO NOT ignore tests here.
# (Semgrep’s built-in template ignores tests/* by default; you can override
# that later if you want full coverage of tests too.)
```

You can add more patterns over time if Semgrep becomes noisy in specific folders (generated code, migrations, etc.).

---

## 6. Running Semgrep locally

Semgrep CLI supports running with a config file, a directory of YAML rules, or registry rule sets. We’ll stick to **local directory-based rules** to avoid external dependencies.

### 6.1. Basic command

From the repo root:

```bash
semgrep --config semgrep/ src tests
```

* `--config semgrep/` tells Semgrep to load all YAML rule files under `semgrep/`.
* `src tests` sets scan roots (you can omit `tests` if you initially only want to scan production code).

### 6.2. Tighten exit behavior for CI

Add `--error` to make Semgrep exit non-zero on findings:

```bash
semgrep --config semgrep/ --error src tests
```

This allows you to fail CI builds when new violations are introduced.

---

## 7. Makefile integration

Add a simple target to your existing Makefile:

```make
SEMgrep_CONFIG := semgrep/

.PHONY: semgrep
semgrep:
	semgrep --config $(SEMgrep_CONFIG) --error src tests
```

If you want a “soft” mode (warnings only), you can add another target:

```make
.PHONY: semgrep-soft
semgrep-soft:
	semgrep --config $(SEMgrep_CONFIG) src tests
```

You can call this in CI alongside ruff/mypy/bandit.

---

## 8. Extending configuration over time

The core idea: **do not bloat a single YAML file.** Instead:

* Keep **rule files small and thematic**.
* Add new files under `semgrep/`.
* Let `--config semgrep/` pick them all up.

Example structure after growing:

```text
semgrep/
  python-base.yml           # general Python bugs, safety
  rag-architecture.yml      # architecture invariants
  rag-security.yml          # security-sensitive rules (e.g. secrets, logging)
  grpc-usage.yml            # gRPC-specific patterns
```

Each file:

* `rules: [...]` at top-level.
* Each rule with:

  * `id`
  * `languages`
  * one or more `pattern` / `patterns` / `pattern-either`
  * `message`, `severity`, `metadata` as needed

### 8.1. Adding a new rule file

1. Create `semgrep/rag-security.yml`.

2. Put something like:

   ```yaml
   rules:
     - id: xrag.security.no-secrets-in-code
       languages: [python]
       message: "Potential secret in code. Store secrets in configuration, not in source."
       severity: ERROR
       patterns:
         - pattern: |
             $VAR = "$SECRET"
       metadata:
         category: security
         confidence: medium
   ```

3. Run:

   ```bash
   semgrep --config semgrep/ src
   ```

No change to CLI invocation is required; all `.yml` files under `semgrep/` are used.

---

## 9. Tuning noise and suppression

You will inevitably have a few false positives. Semgrep gives two primary mechanisms to deal with them:

1. **Ignore paths** in `.semgrepignore` (whole files/folders).
2. **Inline suppression** with `nosemgrep` comments for specific lines/rules.

### 9.1. Ignoring a file or folder

Add a pattern to `.semgrepignore`:

```gitignore
# Ignore auto-generated gRPC stubs
src/proto_gen/
```

Next run will skip these files.

### 9.2. Inline suppression with `nosemgrep`

For a one-off case where you *consciously* violate a rule:

```python
eval(user_supplied_expr)  # nosemgrep: python.security.forbid-eval
```

You can omit the rule id (`# nosemgrep`) to suppress *all* rules at that location, or specify a particular rule id to be precise.

---

## 10. Optional: using registry rule packs (with network)

If you later decide that you *do* want to use Semgrep’s public registry rules (e.g. OWASP Top 10, Python security packs), you can:

* Download the YAML files from the Semgrep rules repo and vendor them under `semgrep/`, or
* Temporarily allow network access in CI and use configs like `p/python` or `p/owasp-top-ten` with `--config`.

Example (network required):

```bash
semgrep --config p/python --config semgrep/ src
```

Here `p/python` is a registry ruleset, and `semgrep/` is your local rules.

For your “no external services” constraint, stick to **vendored local YAML** only and avoid registry entries; the rest of the guide already satisfies that constraint.

---

## 11. Summary

* **Install**: add `semgrep>=1.144.0` to `dev` extras and `uv sync --group dev`.
* **Layout**: create a `semgrep/` folder with small, thematic rule files (`python-base.yml`, `rag-architecture.yml`, etc.).
* **Ignore**: create `.semgrepignore` to exclude generated code, venvs, and noisy directories.
* **Run**: use `semgrep --config semgrep/ src tests` locally and in CI (optionally with `--error`).
* **Extend**: add new YAML rule files and rules over time, focusing on:

  * Architecture invariants (`paths:`).
  * RAG-specific misuse patterns (OpenAI, Redis, Kafka, MinIO).
  * Security patterns not already covered by bandit.

This gives you a **non-redundant, offline static analysis layer** that encodes your architectural decisions and catches bug patterns that ruff/mypy/bandit cannot express.
