# Agent Harness Rules (Project Template)

## Control and scope

- The primary agent owns the user's objective, target identity, authorization, plan, risk decisions, and final acceptance.
- Work only from an explicit task packet. Keep reads and writes within its named resources; do not infer permission from tool availability.
- Assign one writer to each mutable file, account, service, or browser session. The primary handles steps that require its own account, approval, or interface.
- Do not delegate again from an executor. Do not add providers, credentials, accounts, plugins, Skills, MCP servers, or permissions unless the task explicitly authorizes that change.

## Capability use

- Use only interfaces actually exposed and permitted for the task. A configured or visible Skill/MCP is not proof that it is callable, authenticated, inherited by an executor, or appropriate for the target.
- State which route was used and what it could observe. Do not silently switch a named provider, account, path, or executor.
- Never send secrets, private logs, browser profiles, or unrelated user data to another executor. Stop on authentication, permission, sandbox, or protected-data boundaries.
- Do not replay a write after timeout until the original target's state is read back.

## Evidence and status

- Distinguish executor-reported `completed`, `partial`, `failed`, and `blocked` from primary-agent `accepted`, `rejected`, and `pending`.
- Treat model claims, exit codes, HTTP status, process existence, and configuration presence as evidence only for the specific fact they show.
- The primary independently checks the requested downstream state and records each acceptance check with evidence. Missing evidence remains pending; do not invent verification.
- Preserve failures and uncertainty. A successful fallback does not rewrite an earlier failed route as successful.

## Stop and recovery

- Stop the affected action when target identity, authorization, scope, or side effects are unclear. Continue only independent work that remains within scope.
- Use bounded, evidence-based retries. Keep the original operation identity when work is pending; do not start a replacement writer while its result is unknown.
- Return changed files/resources, commands and results, evidence, limitations, and unresolved items. Do not claim completion until primary acceptance is recorded.
