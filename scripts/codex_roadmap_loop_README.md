# Codex Roadmap Loop

`codex_roadmap_loop.sh` runs Codex in a bounded development loop from the repository root. Each iteration asks Codex to read the project planning/state files, choose exactly one small safe roadmap step from `ROADMAP.md`, run relevant checks, and update the project progress files.

The loop is designed to move through the `## Next` queue in `ROADMAP.md`, not just append new notes to `## Done`.

## Run

From anywhere inside the repository:

```bash
scripts/codex_roadmap_loop.sh
```

The default loop length is 5 iterations.

To run a different number of iterations:

```bash
scripts/codex_roadmap_loop.sh 1
scripts/codex_roadmap_loop.sh 10
```

The script rejects non-positive values and caps runs at `MAX_ITERATIONS=50`.

By default the script does not print the full Codex transcript. It prints a compact clipped final summary for each iteration. To suppress even that:

```bash
CODEX_LOOP_OUTPUT=quiet scripts/codex_roadmap_loop.sh 3
```

To debug with the full raw Codex output:

```bash
CODEX_LOOP_OUTPUT=full scripts/codex_roadmap_loop.sh 1
```

## How Iterations Work

On each iteration the script asks Codex to:

- read the planning/state files;
- treat `ROADMAP.md` `## Next` as the execution queue;
- choose the first unchecked leaf checkbox from `## Next`, top-to-bottom;
- split an oversized item into smaller leaf checkboxes before implementing;
- complete one small safe task;
- run relevant tests/checks;
- mark the selected checkbox from `[ ]` to `[x]` when it is actually complete;
- update `DEVELOPMENT_LOG.md`;
- report one explicit status line.

The required final status line is one of:

```text
ROADMAP_LOOP_STATUS: continue
ROADMAP_LOOP_STATUS: complete
ROADMAP_LOOP_STATUS: blocked
```

If Codex does not return a valid status line, the script stops instead of silently continuing.

## Configuration

Edit the variables near the top of `scripts/codex_roadmap_loop.sh`:

```bash
DEFAULT_ITERATIONS=5
MAX_ITERATIONS=50
CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_LOOP_OUTPUT="${CODEX_LOOP_OUTPUT:-summary}"
CODEX_LOOP_SUMMARY_MAX_LINES="${CODEX_LOOP_SUMMARY_MAX_LINES:-20}"
CODEX_LOOP_SUMMARY_MAX_CHARS="${CODEX_LOOP_SUMMARY_MAX_CHARS:-2400}"
CODEX_LOOP_ERROR_TAIL_LINES="${CODEX_LOOP_ERROR_TAIL_LINES:-80}"
CODEX_FLAGS=(exec --sandbox workspace-write --skip-git-repo-check)
```

`CODEX_FLAGS` is the main place to change Codex behavior. The default command shape is:

```bash
codex exec --sandbox workspace-write --skip-git-repo-check -C "$REPO_ROOT" --output-last-message "$tmp_file" "<prompt>"
```

`--skip-git-repo-check` is included because this project directory may not be inside a Git repository. Remove it if you want Codex to require a Git repository before running.

You can also override the binary without editing the script:

```bash
CODEX_BIN=/path/to/codex scripts/codex_roadmap_loop.sh 3
```

`CODEX_LOOP_OUTPUT` controls terminal verbosity:

- `summary` — default; prints only the clipped final Codex summary and loop status.
- `quiet` — prints only loop status lines.
- `full` — prints the raw Codex output for debugging.

Summary mode can be tuned without editing the script:

```bash
CODEX_LOOP_SUMMARY_MAX_LINES=8 CODEX_LOOP_SUMMARY_MAX_CHARS=1200 scripts/codex_roadmap_loop.sh 3
```

On Codex failures, non-`full` modes print only the last `CODEX_LOOP_ERROR_TAIL_LINES` raw output lines.

## Detected Planning Files

The script validates and references these project-specific planning/state files:

- `ROADMAP.md` — main roadmap and checklist.
- `DEVELOPMENT_LOG.md` — progress/state log updated after each step.
- `CLAUDE.md` — project memory, architecture rules, and check commands.
- `README.md` — product behavior, commands, and architecture overview.
- `task.md` — original requirements and process notes.

The main roadmap is `ROADMAP.md`.

The primary progress/state file is `DEVELOPMENT_LOG.md`.

## Safety Limits

The script is intentionally bounded and conservative:

- It requires `set -euo pipefail`.
- It resolves the repository root through Git when available.
- It validates that `codex` exists in `PATH`.
- It validates that the detected planning/state files exist before running.
- It runs at most the requested iteration count and refuses counts above `MAX_ITERATIONS`.
- It asks Codex to do one small roadmap leaf checkbox per iteration.
- It asks Codex to close the exact completed `## Next` checkbox, not only add a `## Done` entry.
- It asks Codex not to auto-commit, delete files, run destructive commands, or make broad unrelated refactors.
- It keeps the terminal readable by default by suppressing the raw Codex transcript and printing only a compact final summary.
- It stops early when Codex reports `ROADMAP_LOOP_STATUS: complete` or `ROADMAP_LOOP_STATUS: blocked`.
- It stops if Codex omits the required `ROADMAP_LOOP_STATUS` line.

The script does not guarantee that Codex will make perfect choices. Review changes after each run before keeping or building on them.
