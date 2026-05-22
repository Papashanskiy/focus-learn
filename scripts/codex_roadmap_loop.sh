#!/usr/bin/env bash
set -euo pipefail

# Default number of Codex iterations when no argument is passed.
DEFAULT_ITERATIONS=5

# Hard safety cap to prevent accidental long-running loops.
MAX_ITERATIONS=50

# Codex executable. Override with CODEX_BIN=/path/to/codex if needed.
CODEX_BIN="${CODEX_BIN:-codex}"

# Terminal output mode:
# - summary: print a compact clipped final response from Codex.
# - quiet: print only iteration status lines.
# - full: print the raw Codex output for debugging.
CODEX_LOOP_OUTPUT="${CODEX_LOOP_OUTPUT:-summary}"

# Limits for summary mode.
CODEX_LOOP_SUMMARY_MAX_LINES="${CODEX_LOOP_SUMMARY_MAX_LINES:-20}"
CODEX_LOOP_SUMMARY_MAX_CHARS="${CODEX_LOOP_SUMMARY_MAX_CHARS:-2400}"
CODEX_LOOP_ERROR_TAIL_LINES="${CODEX_LOOP_ERROR_TAIL_LINES:-80}"

# Edit this array to change Codex flags.
# --sandbox workspace-write lets Codex edit the repository without using the
# deprecated --full-auto flag. --skip-git-repo-check is needed because this
# project directory may be used without a .git repository.
# Example: CODEX_FLAGS=(exec --sandbox workspace-write --skip-git-repo-check --model gpt-5.4)
CODEX_FLAGS=(exec --sandbox workspace-write --skip-git-repo-check)

# Planning/state files detected in this repository.
MAIN_ROADMAP_FILE="ROADMAP.md"
PROGRESS_FILE="DEVELOPMENT_LOG.md"
PLANNING_FILES=(
  "ROADMAP.md"
  "DEVELOPMENT_LOG.md"
  "CLAUDE.md"
  "README.md"
  "task.md"
)

usage() {
  printf 'Usage: %s [iterations]\n' "$(basename "$0")"
  printf 'Runs Codex in a bounded roadmap loop. Default iterations: %s\n' "$DEFAULT_ITERATIONS"
  printf '\n'
  printf 'Environment:\n'
  printf '  CODEX_LOOP_OUTPUT=summary|quiet|full  Terminal output mode. Default: summary\n'
  printf '  CODEX_LOOP_SUMMARY_MAX_LINES=N       Max final-summary lines in summary mode. Default: %s\n' "$CODEX_LOOP_SUMMARY_MAX_LINES"
  printf '  CODEX_LOOP_SUMMARY_MAX_CHARS=N       Max final-summary chars in summary mode. Default: %s\n' "$CODEX_LOOP_SUMMARY_MAX_CHARS"
}

is_positive_integer() {
  [[ "${1:-}" =~ ^[1-9][0-9]*$ ]]
}

print_compact_final_message() {
  local message="$1"
  local max_lines="$2"
  local max_chars="$3"

  awk -v max_lines="$max_lines" -v max_chars="$max_chars" '
    function is_status_line(line) {
      line = tolower(line)
      return line ~ /^[[:space:]]*roadmap_loop_status:[[:space:]]*(continue|complete|blocked)[[:space:]]*$/
    }

    BEGIN {
      lines = 0
      chars = 0
      omitted = 0
    }

    {
      if (is_status_line($0)) {
        next
      }
      if (lines == 0 && $0 ~ /^[[:space:]]*$/) {
        next
      }

      line_length = length($0) + 1
      if (lines >= max_lines || chars + line_length > max_chars) {
        omitted = 1
        next
      }

      print
      lines += 1
      chars += line_length
    }

    END {
      if (lines == 0) {
        print "(Codex returned only ROADMAP_LOOP_STATUS, no final summary.)"
      }
      if (omitted) {
        print "... (summary truncated; set CODEX_LOOP_OUTPUT=full to print raw Codex output)"
      }
    }
  ' <<<"$message"
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
fi

if (($# > 1)); then
  usage >&2
  exit 2
fi

ITERATIONS="${1:-$DEFAULT_ITERATIONS}"

if [[ "$ITERATIONS" == "-h" || "$ITERATIONS" == "--help" ]]; then
  usage
  exit 0
fi

if ! is_positive_integer "$ITERATIONS"; then
  printf 'Error: iterations must be a positive integer, got: %s\n' "$ITERATIONS" >&2
  exit 2
fi

case "$CODEX_LOOP_OUTPUT" in
  summary | quiet | full)
    ;;
  *)
    printf 'Error: CODEX_LOOP_OUTPUT must be summary, quiet, or full; got: %s\n' "$CODEX_LOOP_OUTPUT" >&2
    exit 2
    ;;
esac

if ! is_positive_integer "$CODEX_LOOP_SUMMARY_MAX_LINES"; then
  printf 'Error: CODEX_LOOP_SUMMARY_MAX_LINES must be a positive integer, got: %s\n' "$CODEX_LOOP_SUMMARY_MAX_LINES" >&2
  exit 2
fi

if ! is_positive_integer "$CODEX_LOOP_SUMMARY_MAX_CHARS"; then
  printf 'Error: CODEX_LOOP_SUMMARY_MAX_CHARS must be a positive integer, got: %s\n' "$CODEX_LOOP_SUMMARY_MAX_CHARS" >&2
  exit 2
fi

if ! is_positive_integer "$CODEX_LOOP_ERROR_TAIL_LINES"; then
  printf 'Error: CODEX_LOOP_ERROR_TAIL_LINES must be a positive integer, got: %s\n' "$CODEX_LOOP_ERROR_TAIL_LINES" >&2
  exit 2
fi

if ((ITERATIONS > MAX_ITERATIONS)); then
  printf 'Error: iterations=%s exceeds MAX_ITERATIONS=%s\n' "$ITERATIONS" "$MAX_ITERATIONS" >&2
  exit 2
fi

if ! command -v "$CODEX_BIN" >/dev/null 2>&1; then
  printf 'Error: %s was not found in PATH\n' "$CODEX_BIN" >&2
  exit 1
fi

missing_files=()
for file in "${PLANNING_FILES[@]}"; do
  if [[ ! -f "$REPO_ROOT/$file" ]]; then
    missing_files+=("$file")
  fi
done

if ((${#missing_files[@]} > 0)); then
  printf 'Error: required planning/state files are missing:\n' >&2
  printf '  - %s\n' "${missing_files[@]}" >&2
  exit 1
fi

printf 'Codex roadmap loop\n'
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Iterations: %s\n' "$ITERATIONS"
printf 'Main roadmap: %s\n' "$MAIN_ROADMAP_FILE"
printf 'Progress/state file: %s\n' "$PROGRESS_FILE"
printf 'Terminal output: %s\n' "$CODEX_LOOP_OUTPUT"
printf '\n'

printf -v PLANNING_FILES_TEXT '  - %s\n' "${PLANNING_FILES[@]}"

for ((iteration = 1; iteration <= ITERATIONS; iteration++)); do
  printf '============================================================\n'
  printf 'Iteration %s of %s\n' "$iteration" "$ITERATIONS"
  printf 'Started: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
  printf '============================================================\n'

  PROMPT="$(cat <<PROMPT_EOF
You are working inside this repository:

$REPO_ROOT

Use these actual project planning/state files:

$PLANNING_FILES_TEXT
Main roadmap file:
  - $MAIN_ROADMAP_FILE

Progress/state file:
  - $PROGRESS_FILE

Do exactly one small safe roadmap step for this iteration.

Rules:
- Read the planning/state files before choosing work.
- Treat the ## Next section in $MAIN_ROADMAP_FILE as the execution queue.
- Choose the first unchecked leaf checkbox in ## Next, top-to-bottom, unless it is blocked or clearly unsafe.
- A leaf checkbox is a concrete task with no smaller unchecked child checkbox underneath it.
- Prefer user-visible workflow improvements over invisible polish when both are available.
- If the first unchecked item is still too large for one iteration, split it into smaller unchecked leaf checkboxes in ## Next, then implement the first safe leaf checkbox.
- Keep the change narrowly scoped.
- Do not auto-commit changes.
- Do not delete files.
- Do not run destructive git or filesystem commands.
- Do not perform broad unrelated refactors.
- If the roadmap appears complete, do not modify files.
- If the next step is blocked or unsafe without human input, do not modify files.
- After making a change, run relevant tests/checks for the touched area.
- Prefer project check commands from CLAUDE.md when appropriate.
- Update $PROGRESS_FILE after the step.
- Update $MAIN_ROADMAP_FILE after the step.
- When a selected checkbox is completed, change that exact checkbox from [ ] to [x].
- Do not only append a new Done entry while leaving the completed ## Next checkbox open.
- Leave the selected checkbox open if the task is only partially complete, and write a short note under it explaining what remains.
- Keep your final response concise: at most 12 lines before the status line.
- In your final response, summarize the selected roadmap item, files changed, checks run, and result.

End your final response with exactly one machine-readable line using this prefix and one value:
ROADMAP_LOOP_STATUS: continue
ROADMAP_LOOP_STATUS: complete
ROADMAP_LOOP_STATUS: blocked
PROMPT_EOF
)"

  last_message_file="$(mktemp -t codex-roadmap-loop.XXXXXX)"
  output_file="$(mktemp -t codex-roadmap-loop-output.XXXXXX)"
  CODEX_CMD=("$CODEX_BIN" "${CODEX_FLAGS[@]}" -C "$REPO_ROOT" --output-last-message "$last_message_file")

  if "${CODEX_CMD[@]}" "$PROMPT" >"$output_file" 2>&1; then
    codex_status=0
  else
    codex_status=$?
  fi

  final_message="$(<"$output_file")"
  if [[ -s "$last_message_file" ]]; then
    final_message="$(<"$last_message_file")"
  fi
  rm -f "$last_message_file"

  if ((codex_status != 0)); then
    printf 'Codex exited with status %s; stopping loop.\n' "$codex_status" >&2
    if [[ "$CODEX_LOOP_OUTPUT" == "full" ]]; then
      cat "$output_file" >&2
    else
      printf 'Last %s lines of Codex output:\n' "$CODEX_LOOP_ERROR_TAIL_LINES" >&2
      tail -n "$CODEX_LOOP_ERROR_TAIL_LINES" "$output_file" >&2 || true
      printf 'Set CODEX_LOOP_OUTPUT=full to print raw Codex output.\n' >&2
    fi
    rm -f "$output_file"
    exit "$codex_status"
  fi
  case "$CODEX_LOOP_OUTPUT" in
    full)
      cat "$output_file"
      ;;
    summary)
      printf 'Codex summary:\n'
      print_compact_final_message "$final_message" "$CODEX_LOOP_SUMMARY_MAX_LINES" "$CODEX_LOOP_SUMMARY_MAX_CHARS"
      ;;
    quiet)
      ;;
  esac
  rm -f "$output_file"

  if grep -Eiq '^ROADMAP_LOOP_STATUS:[[:space:]]*complete[[:space:]]*$' <<<"$final_message"; then
    printf 'Codex reported roadmap complete; stopping loop.\n'
    break
  fi

  if grep -Eiq '^ROADMAP_LOOP_STATUS:[[:space:]]*blocked[[:space:]]*$' <<<"$final_message"; then
    printf 'Codex reported blocked; stopping loop.\n'
    break
  fi

  if ! grep -Eiq '^ROADMAP_LOOP_STATUS:[[:space:]]*continue[[:space:]]*$' <<<"$final_message"; then
    printf 'Codex did not report a valid ROADMAP_LOOP_STATUS; stopping loop.\n' >&2
    exit 1
  fi

  printf 'Iteration %s finished; continuing if iterations remain.\n\n' "$iteration"
done

printf 'Roadmap loop finished.\n'
