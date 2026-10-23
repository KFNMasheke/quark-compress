# Engineering reliability: resources and concurrency

**Applies to every new feature, refactor and production fix.** Stack: Python/native compression.

## Project-specific review
bounded input memory, parallel codec contexts, exclusive output creation, worker cancellation and native buffer release. Inspect code before introducing locks, pooling or threading. A static/documentation-only project must not add an unnecessary connection pool; the corresponding checks apply when it gains runtime components.

## Required design rules
1. **Memory and ownership:** Identify which component owns each timer, listener, stream, buffer, file, subprocess, browser, cache and worker. Set a measurable bound on retained objects and large payloads. Release resources in a `finally` block, disposable lifecycle or shutdown hook even after exceptions and cancellation.
2. **Connections:** Use the framework's intended connection lifecycle. Bound any real pool's maximum size, idle lifetime and queue wait. Set connect, statement and request timeouts. Close or return connections reliably; transactions must commit atomically or roll back completely. For Python SQLite, `with sqlite3.connect(...)` does **not** close the connection; explicitly close it.
3. **Races:** Mark shared mutable state and read-modify-write paths. Specify invariants for duplicate submissions, simultaneous saves, retries and background jobs. Use database constraints/transactions, explicit locks or idempotency keys when warranted. Never assume an in-process mutex protects multiple processes or deployments.
4. **Backpressure and cancellation:** Set maximum active jobs and input sizes. Propagate cancellation through network calls and workers. Abort abandoned requests. Avoid unbounded Promise/task queues.
5. **Privacy and failure isolation:** Do not log credentials, personal statements, documents or request bodies in stress-test output; use synthetic fixtures. Fail safely on timeouts, pool exhaustion and partial writes.

## Mandatory concurrent test cases (where applicable)
- Start **at least 8 competing operations** with a barrier, Promise.all with independently scheduled work, worker threads or separate processes. Verify invariants after *all* tasks settle; sequential loops are insufficient.
- Run concurrent writes/updates on the same and on distinct records; verify no unexpected overwrites or duplicates. Test rollback after one worker fails.
- Execute concurrent reads during writes and after cancellation. Assert data remains valid and previous committed records survive.
- Force failure, timeout and retry paths and verify cleanup: no orphaned temp files, stuck locks, leaked DB handles, timers or browser sessions.
- Test bounded memory and queued work under repeated operations where relevant. Compare against a baseline and document acceptable thresholds to avoid flaky assertions.
- Run the normal unit suite **and** the concurrency suite in CI; exercise the real persistence/worker layer with isolated test fixtures. Do not imply a test passed until it actually ran.

## Definition of done
The PR records: (a) resources and who closes them, (b) actual pool/timeouts or “not applicable,” (c) shared-state invariants, (d) a reproducible concurrency regression test, and (e) observed local/CI results. A policy file alone does not count as implementing the required runtime fix or tests.
