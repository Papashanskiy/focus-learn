# TUI UX Inventory

Date: 2026-05-28

Source files checked: `interview_prep/ui/tui.py`, `interview_prep/ui/tui_render.py`, `tests/test_tui.py`.

## Current First Screen

- Topbar: current topic, question id/state, elapsed/remaining timer, Ollama status, and compact content queue status.
- Mode action bar: `Practice`, `Learn`, `System Design`, and `Конспект обучения`/learning notebook.
- Today action bar: `Start Drill`, `Review Weak Answer`, `Mock Senior Interview`, `Open Readiness`, and `Notebook`.
- Left panel: topic list with answer counts, suggested-topic marker, and a long disabled slash-command hint row.
- Center panel: Today recommendation, why-now reason, expected time, primary action, optional curriculum warning, topic recommendation, and secondary command hints.
- Right panel on the start screen: generic history/feedback/palette area plus the persistent notes editor.
- Composer: accepts Enter for the primary Today drill, topic ids, and slash commands.
- Footer: Textual key bindings such as quit, stats, hint, answer, commands, notes, and input focus.

## Current Command Groups

- Today workflow: `/accept-topic`, `/readiness`, `/baseline-repeat`, `/mock-interview`, `/generate-curriculum`, `/system-design`.
- Practice workflow: `/hint`, `/answer`, `/feedback`, `/recheck-feedback`, `/finish-session`, `/skip`, `/next`, `/practice`.
- Learning workflow: `/learn`, `/learn-older`, `/learn-newer`.
- Notebook workflow: `/notebook`, `/notebook topic <id>`, `/notebook subtopic <id>`, `/notebook competency <slug>`, `/notebook entry <id>`, `/note-from-answer`, `/notes`, `/save-note <title>`.
- Content workflow: `/content`, `/pause-content`, `/resume-content`, `/retry-job <id>`, `/questions-review`, `/questions-review accept <id>`, `/questions-review archive <id>`, `/curation-audit`, `/curation-audit topic <id>`, `/curation-audit status <status>`.
- Materials workflow: `/materials`, `/materials current/all`, `/materials scenarios current/all`, `/preview-material <id|latest>`, `/preview-scenario <id|latest>`, `/material <id|latest>`, `/scenario <id|latest>`, `/archive-material <id> confirm [reason]`, `/archive-scenario <id> confirm [reason]`, `/regen-material`, `/regen-scenario`.
- System design workflow: `/sd <scenario>`, `/sd-checkpoint`, `/sd-pressure`, `/sd-feedback`, `/req`, `/api`, `/data`, `/decision`, `/risk`.
- History workflow: `/history`, `/history <id>`, `/history learning`, `/history learning <session-id>`, `/history learning <topic-id> <date>`, `/history system-design`, `/history system-design <feedback-id>`.
- Utility: `/stats`, `/quit`, command palette via `/commands` or `Ctrl+P`.

## Minimal Flow Candidates

- Keep visible by default: one Today recommendation, one primary action, compact progress/readiness signal, mode choice, current topic or drill context, composer, and a small path to notebook/readiness.
- Keep as secondary but reachable from the menu: manual topic selection, Learn, Practice, Mock Interview, System Design, Readiness, Notebook, and Settings once it exists.
- Move to advanced/debug by default: content queue controls, generated artifact management, question review, auto-curation audit, raw history details, command palette dump, pause/resume/retry worker controls, and source-curation undo hints.
- Hide from the first screen unless contextually relevant: persistent notes editor, long slash-command lists, queue counters beyond the topbar summary, materials version management, and raw transcript/artifact debug commands.

## Next UX Decisions

- The next roadmap leaves can add the menu without changing service behavior.
- Minimal mode should not remove power-user slash commands; it should stop advertising debug surfaces as the default path.
- Advanced/debug screens should remain reachable for diagnostics, but should not compete with the main study action on app start.
