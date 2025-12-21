## Logging levels: best-practices for code-writing agents

When adding logs, treat **ERROR** as a scarce, high-signal operator alert. A program that’s functioning correctly as designed/configured should **not** emit ERROR-level logs.

### Meanings (sysadmin view)

* **ERROR**: The *program/system is not working right* and **someone must fix something locally** (and can fix it). Use for **program-level failures**: misconfiguration, required resource missing/unreadable, internal invariants broken, critical dependency unavailable *in a way that prevents correct operation*, startup failure, corruption, etc.
* **WARN**: Something went wrong for an operation or an unusual condition occurred, but the program **continues to function** (maybe degraded). Often **operation-level failures** or intermittent issues.
* **INFO**: Expected, routine state changes and significant milestones (startup/shutdown, reconfiguration applied, periodic summaries), without implying trouble.
* **DEBUG**: Verbose diagnostic detail meant for troubleshooting; should be easy to disable and should not pollute system logs by default.

### Decision rule

1. **Can the operator fix it locally?** If no, it’s rarely ERROR (otherwise people will ignore your logs or abandon the program).
2. **Is the program’s correct operation impaired?** If it prevents the program from working right overall → ERROR. If it only affects a specific operation/request → WARN/INFO.
3. **Is it routine/expected in normal environments?** If yes → INFO (or DEBUG), not ERROR.

### Concrete do/don’t

* **DO log ERROR** for: invalid/failed-to-parse configuration; required file/database schema unreadable; failure to allocate essential resources; unexpected internal failure reading required data; “can’t start” conditions.
* **DON’T log ERROR** for: failures “somewhere else” that are expected in distributed systems (e.g., remote host unreachable, connection refused, timeouts) unless your program cannot function without that remote dependency and you’re escalating accordingly.

  * Example: an SMTP sender failing to reach a *remote* port 25 is typically **not** local ERROR; log **WARN** (or INFO if expected/retried).
* **DO distinguish**: *operation error* (this attempt failed) vs *program error* (the service is unhealthy).
* **DO provide controls**: make DEBUG/trace output opt-in; allow reducing log verbosity; avoid forcing noisy logs into system logs.

### Implementation checklist (for each log statement)

* What is failing: **operation** or **program**?
* Does it require **human action**?
* Is the action **local and feasible**?
* Is this **expected** sometimes (network, remote services, user input)?
* If ERROR: ensure it’s actionable (include what failed, where, and what to check next).
