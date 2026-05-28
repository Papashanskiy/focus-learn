# Development Log

## 2026-05-28

### TUI progressive disclosure advanced menu

- Первый open roadmap item `Progressive disclosure` был слишком крупным для одной итерации, поэтому он разбит в `## Next` на advanced menu foundation, start-screen cleanup и queue controls grouping.
- Закрыт первый safe leaf: стартовое mode menu получило пункт `Advanced`, который открывает focused advanced screen с пунктами Content jobs, Materials, Question audit, Curation audit, History и Command palette.
- Slash-command fallbacks сохранены: `/content`, `/materials`, `/questions-review`, `/curation-audit`, `/history` и `/commands` продолжают открывать прежние экраны напрямую.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_main_menu_supports_keyboard_and_mouse_selection tests.test_tui.TUITests.test_tui_advanced_menu_exposes_diagnostics_without_breaking_slash_fallbacks tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m unittest tests.test_tui.TUITests.test_tui_minimal_start_screen_hides_debug_panes_and_hints tests.test_tui.TUITests.test_tui_today_action_bar_shows_only_primary_action -v`, `python -m compileall interview_prep`.

### TUI minimal mode layout

- Закрыт parent roadmap leaf `Minimal mode layout`: проверенный default minimal start screen уже показывает Today task, один primary action, compact readiness/progress context и mode menu, а service/debug panes скрыты с первого экрана.
- Поведенческих изменений не понадобилось: parent закрыт после ранее выполненных start-screen shell и start action simplification leaves.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_minimal_start_screen_hides_debug_panes_and_hints tests.test_tui.TUITests.test_tui_today_action_bar_shows_only_primary_action tests.test_tui.TUITests.test_tui_primary_action_starts_low_rubric_practice tests.test_tui.TUITests.test_tui_main_menu_supports_keyboard_and_mouse_selection tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill -v`.

### TUI start action simplification

- Закрыт roadmap leaf `Start action simplification`: в minimal start screen Today action bar теперь показывает только один primary action button, а secondary переходы остаются в mode menu и slash-command fallback.
- Primary button получает context-aware label для mock interview, baseline, repeat baseline и curriculum setup, но использует прежний `activate_today_start_drill_action()` flow.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_today_action_bar_shows_only_primary_action tests.test_tui.TUITests.test_tui_primary_action_starts_low_rubric_practice tests.test_tui.TUITests.test_tui_main_menu_supports_keyboard_and_mouse_selection tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill -v`, `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows tests.test_tui.TUITests.test_tui_smoke_switches_today_practice_learn_system_design_readiness_practice tests.test_tui.TUITests.test_tui_notebook_action_opens_current_topic_entries -v`, `python -m compileall interview_prep`.

### TUI minimal start shell

- Первый open leaf `Minimal mode layout` был слишком крупным для одной итерации, поэтому он разбит в `## Next` на start-screen shell и start action simplification.
- Закрыт первый safe leaf: TUI получил default `minimal` visual mode; стартовый экран скрывает generic right/debug pane с notes/history и больше не рекламирует `/content`, `/materials`, `/questions-review` в first-screen hints.
- Ручной выбор topic и Today primary action сохранены: левая колонка с темами остается доступной, а advanced/debug commands остаются через `/commands`.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_minimal_start_screen_hides_debug_panes_and_hints tests.test_tui.TUITests.test_tui_main_menu_supports_keyboard_and_mouse_selection tests.test_tui.TUITests.test_tui_clicking_practice_topic_starts_topic_session tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill -v`.

### TUI main menu foundation

- Закрыт roadmap leaf из 0C: стартовый экран TUI получил selectable main menu с режимами Today, Practice, Learn, Mock Interview, System Design, Readiness и Settings.
- Menu построено на `OptionList`, поэтому поддерживает keyboard selection через arrows/Enter при фокусе и mouse selection; пункты переиспользуют существующие action handlers, а Settings открыт как read-only runtime/config screen без изменения storage.
- Добавлен `/settings` как power-user fallback и пункт command palette.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_main_menu_supports_keyboard_and_mouse_selection tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`. Дополнительно запускался `python -m unittest tests.test_tui -v`: текущий полный TUI suite по-прежнему падает только в двух ранее известных regression-тестах `test_tui_practice_question_shows_linked_tags`/`test_tui_practice_question_shows_linked_competencies`, где canonical-priority selection выбирает canonical question вместо manually tagged fixture question.

### TUI UX inventory

- Закрыт первый leaf из 0C: добавлен `TUI_UX_INVENTORY.md` с перечислением текущих first-screen actions, panes, slash-command groups и secondary surfaces.
- Зафиксирован минимальный split для следующих UX-шагов: default flow должен оставить Today recommendation, primary action, mode choice и компактный progress/readiness signal, а queue/materials/review/audit/raw history controls уйти в advanced/debug.
- Runtime behavior не менялся.
- Проверки: `python -m compileall interview_prep`, `rg -n "TUI UX inventory|TUI_UX_INVENTORY|advanced/debug|Minimal Flow" TUI_UX_INVENTORY.md DEVELOPMENT_LOG.md ROADMAP.md`.

### 0B docs sync

- Закрыт roadmap docs leaf после reliability/migration follow-ups: README описывает automatic retry/backoff и empty legacy CLI session outcome, CLAUDE фиксирует TUI/content-worker contract, а ROADMAP отражает закрытый 0B queue.
- Схема зафиксирована отдельным migration guard entry: `CURRENT_SCHEMA_VERSION` должен совпадать с последним explicit migration step.
- Проверки: `python -m compileall interview_prep`, `rg -n "automatic retry|scheduled retry|abandoned|CURRENT_SCHEMA_VERSION|0B docs sync" README.md CLAUDE.md DEVELOPMENT_LOG.md ROADMAP.md`.

### CLI empty session status

- Закрыт roadmap leaf про legacy CLI `session`: выход через `/quit` до первого сохраненного ответа теперь вызывает `finish_session(..., abandon_if_empty=True)` и помечает session как `abandoned`, а не `completed`.
- Добавлен regression-тест через реальный CLI-процесс: пустая session не попадает в `session_count`, `answered_count`, completed history и сохраняется в stats recent history как `abandoned`; readiness остается в baseline empty-state.
- README синхронизирован с новым CLI session outcome behavior.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_session_quit_without_answers_abandons_legacy_cli_session tests.test_cli_flow.CLIFlowTests.test_session_no_feedback_saves_answer_after_single_line_input -v`, `python -m compileall interview_prep`.

### Content generation automatic retry contract

- Закрыт roadmap leaf про content generation retry: transient worker failures теперь остаются в automatic retry flow — job возвращается в `queued`, получает `retry.attempt`, `next_attempt_at`, exponential backoff и повторяется до `max_attempts`.
- Non-retryable/final failures остаются `failed` для ручного `content-retry` или TUI `/retry-job`; CLI/TUI worker теперь явно показывают scheduled retry и больше не подписывают requeued transient failure как hard failure.
- Документация синхронизирована в `README.md`, `CLAUDE.md` и `ROADMAP.md`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_content_generation_transient_failure_requeues_with_retry_backoff_metadata tests.test_services.ServiceTests.test_content_generation_transient_failure_fails_after_max_attempts tests.test_services.ServiceTests.test_content_generation_worker_skips_jobs_until_backoff_expires tests.test_services.ServiceTests.test_content_generation_retry_moves_failed_job_to_queue tests.test_services.ServiceTests.test_content_generation_retry_respects_active_job_limit -v`, `python -m unittest tests.test_tui.ContentWorkerControllerTests.test_finish_run_normalizes_results_and_updates_status tests.test_tui.TUIHelperTests.test_tui_records_retry_scheduled_content_result_without_failed_status tests.test_tui.TUITests.test_tui_content_screen_retries_failed_job tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs -v`, `python -m compileall interview_prep`.

### Migration schema-version guard

- Закрыт roadmap leaf про migration hygiene: `CURRENT_SCHEMA_VERSION` проверен против последнего explicit migration step (`020_question_auto_curation_audit_tables`) и уже равен `20`.
- Добавлен regression-тест, который валидирует числовые prefixes `MIGRATION_STEPS` как непрерывную последовательность и падает, если `CURRENT_SCHEMA_VERSION` расходится с последним migration step.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_current_schema_version_matches_latest_migration_step tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema -v`, `python -m compileall interview_prep`.

### Source curation docs sync

- Закрыт roadmap docs leaf после source refresh, auto-curation, canonical pack и quality gate: README теперь описывает source-backed refresh/candidates flow, automated approval policy, audit/undo surfaces и приоритет `canonical-2026` questions.
- `ROADMAP.md` обновлен: docs leaf закрыт, Done получил короткий итог, known limitations больше не говорят, что 0A quality/canonical/curation observability остаются открытыми.
- Проверки: `python -m compileall interview_prep`, `rg -n "Source curation docs sync|Качество и источники вопросов|Docs: после source refresh|quality gate|canonical-2026" README.md DEVELOPMENT_LOG.md ROADMAP.md`.

### Questions-review happy path copy

- Закрыт roadmap leaf: CLI/TUI `questions-review` теперь подписан как audit queue для pending exceptions, где automated curation является happy path, а `accept`/`archive` явно названы manual audit overrides.
- Поведение accept/archive не менялось: команды по-прежнему только переводят pending-review question в `accepted` или `archived` без удаления строки.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_review_lists_pending_generated_questions tests.test_cli_flow.CLIFlowTests.test_questions_review_accepts_and_archives_pending_questions tests.test_tui.TUITests.test_tui_questions_review_lists_and_updates_pending_generated_questions tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### Questions-review audit context

- Закрыт roadmap leaf: CLI/TUI `questions-review` теперь для pending questions с сохраненным auto-curation audit row показывает latest decision, curator rationale, source evidence и safe undo hint через `questions-source undo --question <id>`.
- Без изменения accept/archive behavior: audit context только помогает понять, почему вопрос попал в audit/review path и какой безопасный undo доступен через существующий CLI flow.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_review_lists_pending_generated_questions tests.test_tui.TUITests.test_tui_questions_review_lists_and_updates_pending_generated_questions -v`, `python -m compileall interview_prep`.

### TUI questions-review observability

- Закрыт TUI display leaf: `/questions-review` теперь показывает pending generated questions с source URL/retrieved metadata, category hints, frequency hint и deterministic quality flags без изменения accept/archive behavior.
- Regression-тест TUI review flow проверяет metadata/flags в focused screen и прежнее обновление очереди после accept/archive.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_questions_review_lists_and_updates_pending_generated_questions -v`, `python -m compileall interview_prep`.

### Questions review CLI observability

- Первый open roadmap item про curation observability был слишком крупным для одной итерации, поэтому он разбит в `## Next` на CLI display, TUI display, audit context и happy-path copy leaves.
- Закрыт CLI display leaf: `questions-review` теперь показывает pending questions с source URL/retrieved metadata, category hints, frequency hint и deterministic quality flags без изменения accept/archive behavior.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_review_lists_pending_generated_questions tests.test_cli_flow.CLIFlowTests.test_questions_review_accepts_and_archives_pending_questions -v`, `python -m compileall interview_prep`.

### Curriculum fallback specificity

- Закрыт roadmap leaf про `fallback_questions()`: fallback curriculum больше не строит generic prompts с подстановкой названия темы, а возвращает concrete canonical-style scenarios для Python runtime, async backend, system design и parser fallback.
- Добавлен regression-тест, который проверяет fallback prompts через общий generic wording detector и concrete scenario markers.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_parse_curriculum_falls_back_on_invalid_json tests.test_services.ServiceTests.test_curriculum_fallback_questions_are_specific_scenarios tests.test_services.ServiceTests.test_curriculum_service_archives_generic_llm_seed_questions tests.test_services.ServiceTests.test_curriculum_service_generates_and_saves_llm_seed_questions -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v` (138 tests, 1 optional Ollama skip; existing ResourceWarning про in-memory sqlite connections).

### Content quality generation gate

- Закрыт roadmap leaf про quality gate для generated prompts: общие phrases вроде `ключевой production-риск`, `backend-flow` и `какие tradeoffs` вынесены в общий rule helper, а background/curriculum generated questions с такими prompt сразу сохраняются как `archived`.
- Нормальные generated questions по-прежнему попадают в `pending_review`; для background job artifact добавлены `quality_flags`, чтобы UI/diagnostics могли показать причину gate.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_content_generation_archives_generic_background_question tests.test_services.ServiceTests.test_content_generation_queue_creates_background_question tests.test_services.ServiceTests.test_curriculum_service_archives_generic_llm_seed_questions tests.test_services.ServiceTests.test_curriculum_service_generates_and_saves_llm_seed_questions -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_audit_lists_generic_duplicate_and_too_long_questions -v`, `python -m unittest tests.test_services -v` (137 tests, 1 optional Ollama skip; existing ResourceWarning про in-memory sqlite connections), `python -m compileall interview_prep`.
- Дополнительно запускался `python -m unittest discover -s tests -v`: текущий full discover падает в двух TUI regression-тестах `test_tui_practice_question_shows_linked_tags`/`test_tui_practice_question_shows_linked_competencies`, потому что существующий canonical-priority selection выбирает canonical question вместо вручную размеченного fixture question.

### Practice selection canonical priority

- Закрыт roadmap leaf про practice selection: добавлен общий service-level rank для accepted canonical `must-know` questions и подключен к topic/mixed practice ordering, baseline plan и mock senior interview plan.
- Приоритет canonical ставится после weak-repeat в обычной practice и после answer-count в baseline/mock selection, поэтому due weak question и unanswered calibration candidate не теряются, но first exposure выбирает curated `canonical-2026` pack перед generated/bootstrap rows.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_practice_selection_prefers_canonical_must_know_over_generated_candidates tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_calibration_baseline_plan_prefers_unanswered_questions tests.test_services.ServiceTests.test_mock_senior_interview_plan_mixes_interview_sections tests.test_services.ServiceTests.test_mixed_session_next_question_prioritizes_weak_topic tests.test_services.ServiceTests.test_mixed_session_prefers_canonical_question_within_weak_topic tests.test_services.ServiceTests.test_topic_session_repeats_weak_question_after_interval -v`, `python -m unittest tests.test_services -v` (135 tests, 1 optional Ollama skip; existing ResourceWarning про in-memory sqlite connections), `python -m compileall interview_prep`.

### Canonical metadata tags

- Закрыт roadmap leaf про canonical metadata: `seed_defaults()` теперь идемпотентно создает metadata tags для `canonical-2026` и привязывает accepted canonical questions к `must-know`, `frequency-high` и top-level type tags (`python-core`, `coding`, `api`, `db`, `async`, `system-design`, `testing`, `ops`) через существующие `tags`/`question_tags`.
- Новая схема не понадобилась: frequency/type metadata идет через tags, а competency metadata остается через существующие `question_competencies`; повторный seed восстанавливает canonical tag links и не заменяет пользовательские/manual tags.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_links_canonical_2026_metadata_tags tests.test_services.ServiceTests.test_repository_persists_reusable_question_tags -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_and_canonical_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_python_core_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_coding_api_sql_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_async_system_testing_ops_batch tests.test_services.ServiceTests.test_seed_defaults_adds_canonical_2026_count_and_category_coverage tests.test_services.ServiceTests.test_seed_defaults_links_canonical_2026_metadata_tags tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies tests.test_services.ServiceTests.test_repository_persists_reusable_question_tags tests.test_services.ServiceTests.test_repository_replaces_question_tags_without_duplicates tests.test_services.ServiceTests.test_repository_filters_questions_by_tag_slug -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_filters_by_tag_slug -v`, `python -m unittest tests.test_services -v` (133 tests, 1 optional Ollama skip; есть существующие ResourceWarning про незакрытые in-memory sqlite connections, без failures).

## 2026-05-27

### Canonical coverage completion

- Закрыт roadmap leaf про completion `canonical-2026`: `seed_defaults()` теперь идемпотентно добавляет 40 accepted must-know вопросов, по 5 вопросов на каждую coverage category: Python core, coding screen, API/web, SQL/Postgres, async/queues, system design, testing и ops/reliability.
- Добавлено 21 конкретное non-LLM seed question с `source_category_hints`, `source_frequency_hint="high"` и competency links; regression-тест фиксирует общий count, 5-per-category coverage, accepted status, must-know metadata и primary competency link для каждого canonical вопроса.
- Backlog regression больше не зависит от малого числа seed-вопросов в `async-backend`: тест создает отдельную low-content topic, поэтому full canonical pack не ломает проверку duplicate active jobs.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_and_canonical_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_python_core_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_coding_api_sql_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_async_system_testing_ops_batch tests.test_services.ServiceTests.test_seed_defaults_adds_canonical_2026_count_and_category_coverage tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies -v`, `python -m unittest tests.test_services.ServiceTests.test_content_generation_ensure_question_backlog_avoids_duplicate_active_jobs tests.test_services.ServiceTests.test_seed_defaults_adds_canonical_2026_count_and_category_coverage -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_shows_linked_question_competencies tests.test_cli_flow.CLIFlowTests.test_questions_command_filters_by_tag_slug -v`, `python -m unittest tests.test_tui.TUITests.test_tui_today_review_weak_answer_click_starts_low_rubric_practice -v`, `python -m unittest discover -s tests -v` (307 tests, 1 optional Ollama skip).

### Canonical async/system-design/testing/ops batch

- Закрыт roadmap leaf про следующую `canonical-2026` batch: `seed_defaults()` теперь идемпотентно добавляет еще 8 accepted must-know вопросов для async/queues, system design, testing/migrations и ops/reliability.
- Batch покрывает cancellation/fan-out, backpressure/retry budget, notification service, caching/stampede, authz regression tests, zero-downtime migration testing, SLO/error budget и incident response; все вопросы сохраняют `source_category_hints`, `source_frequency_hint="high"` и competency links через существующую связь `question_competencies`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_and_canonical_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_python_core_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_coding_api_sql_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_async_system_testing_ops_batch tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies -v`, `python -m unittest tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_content_generation_regenerates_reference_answers_for_topic_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_async_system_testing_ops_batch -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Canonical coding/API/SQL batch

- Закрыт roadmap leaf про следующую `canonical-2026` batch: `seed_defaults()` теперь идемпотентно добавляет еще 6 accepted must-know вопросов для coding screen, API/web и SQL/Postgres.
- Batch покрывает hash map / graph topological sort coding prompts, API versioning/authz scenarios и Postgres index/idempotency scenarios; все вопросы сохраняют `source_category_hints`, `source_frequency_hint="high"` и competency links через существующую связь `question_competencies`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_and_canonical_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_python_core_batch tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_coding_api_sql_batch tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Canonical questions Python core batch

- Первый open roadmap item про полный `canonical-2026` pack на 40 вопросов был слишком крупным для одной итерации, поэтому он разбит в `## Next` на smaller batch leaves; закрыт только Python core/runtime batch.
- `seed_defaults()` теперь идемпотентно добавляет первую accepted batch `canonical-2026` из 5 must-know вопросов по Python runtime/core: mutable defaults/shared state, descriptors/ORM attributes, GIL для CPU-bound работы, import cycles/startup и streaming generators.
- Seed questions получили source metadata (`source_category_hints`, `source_frequency_hint`) и сохраняют competency links через существующий `question_competencies` foundation; broader coding/API/SQL/async/system-design/testing/ops coverage остается открытым.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_and_canonical_questions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_canonical_2026_python_core_batch tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies -v`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_shows_linked_question_competencies tests.test_cli_flow.CLIFlowTests.test_questions_command_filters_by_tag_slug tests.test_cli_flow.CLIFlowTests.test_questions_audit_lists_generic_duplicate_and_too_long_questions -v`, `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_enter_starts_baseline_session_from_empty_state -v`, `python -m compileall interview_prep`.

### Auto-curation audit undo

- Закрыт roadmap leaf про audit undo: добавлен service-level `QuestionAutoCurationService.undo_latest_decision()` и CLI `questions-source undo [--question <id>]`, который восстанавливает previous status последнего matching auto-curation decision без удаления audit row.
- Безопасность undo: команда отказывается перезаписывать статус, если текущий status вопроса уже не совпадает с audited resulting status; TUI `/curation-audit` и command palette показывают CLI-подсказку для отката.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_undo_latest_decision_restores_previous_status_safely tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curation_undo_restores_previous_status -v`, `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine tests.test_services.ServiceTests.test_question_auto_curation_undo_latest_decision_restores_previous_status_safely tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_applies_deterministic_status_changes tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curation_audit_lists_saved_decisions tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curation_undo_restores_previous_status -v`, `python -m unittest tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### Auto-curation audit TUI display

- Закрыт roadmap leaf про TUI audit display: добавлен focused read-only экран `/curation-audit` с alias `/questions-source audit`, который показывает saved auto-curation decisions и поддерживает фильтры `question <id>`, `topic <id>`, `status accepted|archived|pending_auto_review`.
- Экран показывает previous/resulting/current status, source URL/retrieved metadata, category/frequency hints, quality flags, source evidence, curator model/version/score и rationale; undo остается следующим отдельным leaf.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_auto_curation_audit_lists_saved_decisions_with_filters -v`, `python -m unittest tests.test_tui.TUITests.test_tui_questions_review_lists_and_updates_pending_generated_questions tests.test_tui.TUITests.test_tui_auto_curation_audit_lists_saved_decisions_with_filters tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### Auto-curation audit CLI display

- Первый open leaf `Audit display` был слишком крупным для одной итерации, поэтому он разбит в `## Next` на CLI display и TUI display leaves; закрыт только CLI display.
- Добавлен read-only CLI `questions-source audit` с фильтрами `--question`, `--topic`, `--status`, `--limit`; вывод показывает saved auto-curation decisions с previous/resulting/current status, source metadata/evidence, quality flags, curator model/version, score и rationale без изменения SQLite.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curation_audit_lists_saved_decisions tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_applies_deterministic_status_changes -v`, `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine -v`, `python -m compileall interview_prep`.

### Auto-curation audit storage foundation

- Первый open roadmap item про auto-curation audit был слишком крупным для одной итерации, поэтому он разбит в `## Next` на storage, display и undo leaves.
- Закрыт storage leaf: добавлены domain-модель `QuestionAutoCurationAudit`, SQLite-таблица `question_auto_curation_audits` и repository методы save/list/get; `questions-source auto-curate` в non-dry-run теперь сохраняет audit row для `auto_accepted`, `auto_archived` и `quarantined` decisions с previous/resulting status, confidence, rationale, quality flags, curator score/evidence, model/version и source metadata.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine tests.test_services.ServiceTests.test_question_auto_curation_llm_curator_accepts_ambiguous_candidate_before_apply -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_dry_run_classifies_without_status_changes tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_applies_deterministic_status_changes -v`, `python -m compileall interview_prep`.

### Auto-curation LLM curator rubric

- Закрыт roadmap leaf про LLM curator rubric: `QuestionAutoCurationService` теперь умеет перед применением статусов прогонять quarantined source-backed candidates через strict JSON prompt с решениями `auto_accepted`/`auto_archived`/`quarantined`.
- Безопасный fallback оставляет candidate в quarantine при недоступной LLM, невалидном JSON, low-confidence acceptance/archive или неполных source metadata; CLI подключает flow явно через `questions-source auto-curate --llm-curator`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_preview_classifies_source_backed_candidates_without_mutation tests.test_services.ServiceTests.test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine tests.test_services.ServiceTests.test_question_auto_curation_llm_curator_accepts_ambiguous_candidate_before_apply tests.test_services.ServiceTests.test_question_auto_curation_llm_curator_parse_fallback_keeps_quarantine -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_dry_run_classifies_without_status_changes tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_applies_deterministic_status_changes -v`, `python -m compileall interview_prep`.

### Auto-curation deterministic apply

- Закрыт roadmap leaf про apply deterministic decisions: `QuestionAutoCurationService.apply_pending_source_backed_candidates()` применяет `auto_accepted` как `accepted`, `auto_archived` как `archived`, а `quarantined` оставляет в `pending_auto_review`, чтобы такие вопросы не попадали в practice до audit/undo surface.
- CLI `questions-source auto-curate` теперь применяет deterministic decisions; `--dry-run` остался read-only preview. README обновлен, чтобы больше не описывать non-dry-run как ошибку.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_preview_classifies_source_backed_candidates_without_mutation tests.test_services.ServiceTests.test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_dry_run_classifies_without_status_changes tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_applies_deterministic_status_changes -v`, `python -m compileall interview_prep`.

### Auto-curation deterministic dry-run

- Первый open roadmap item про auto-curation contract оказался слишком крупным для одной итерации, поэтому он разбит в `## Next` на deterministic dry-run, apply decisions и LLM curator rubric leaves.
- Закрыт deterministic dry-run leaf: добавлен `QuestionAutoCurationService`, который классифицирует pending `source-backed` candidates как `auto_accepted`, `auto_archived` или `quarantined` по source metadata, generic/duplicate/length gates и не меняет SQLite.
- CLI `questions-source auto-curate --dry-run [--topic <id>]` показывает decision, confidence, quality flags, rationale и source evidence; без `--dry-run` команда пока явно отказывается менять статусы.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_question_auto_curation_preview_classifies_source_backed_candidates_without_mutation tests.test_cli_flow.CLIFlowTests.test_questions_source_auto_curate_dry_run_classifies_without_status_changes -v`, `python -m compileall interview_prep`.

### Source-backed candidates

- Закрыт roadmap leaf про source-backed candidates: добавлен статус `pending_auto_review`, source metadata columns для questions (`source_url`, `source_retrieved_at`, category hints, frequency hint) и deterministic candidate templates поверх saved source snapshots.
- CLI `questions-source candidates` создает 16 собственных source-backed candidate questions без копирования external lists; candidates остаются вне practice loop, потому что selection берет только `accepted` questions.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_question_source_refresh_persists_metadata_without_creating_questions tests.test_services.ServiceTests.test_question_source_candidates_create_pending_auto_review_questions_with_metadata -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_source_refresh_dry_run_lists_whitelist_without_creating_rows tests.test_cli_flow.CLIFlowTests.test_questions_source_candidates_saves_pending_auto_review_questions -v`, `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_repository_tracks_question_source_quality_status tests.test_services.ServiceTests.test_practice_selection_skips_archived_questions -v`, `python -m compileall interview_prep`, `python -m interview_prep --db /tmp/interview_prep_source_candidates_check.db questions-source refresh`, `python -m interview_prep --db /tmp/interview_prep_source_candidates_check.db questions-source candidates`.

### Source refresh foundation

- Закрыт roadmap leaf про source refresh foundation: добавлен metadata-only CLI `questions-source refresh --dry-run`, который показывает whitelisted source snapshots с `url`, `retrieved_at`, `title`, checksum и category hints без записи в SQLite.
- Non-dry-run `questions-source refresh` сохраняет только rows в `question_source_snapshots` через repository/service слой; questions/practice candidates не создаются, чтобы следующий source-backed candidates шаг остался отдельным.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_questions_source_refresh_dry_run_lists_whitelist_without_creating_rows tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_question_source_refresh_persists_metadata_without_creating_questions -v`, `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema -v`, `python -m compileall interview_prep`, `python -m interview_prep --db /tmp/interview_prep_source_refresh_check.db questions-source refresh --dry-run`.

### Question source research note

- Закрыт roadmap leaf про source research: добавлена `QUESTION_SOURCE_RESEARCH.md` с source inventory для Python core/async, coding screens, API/security, Postgres, system design, testing и ops/reliability.
- Список будущих candidate themes написан своими словами и зафиксирован как research input для `questions-source refresh`, source-backed candidates и `canonical-2026`; внешние списки вопросов не копировались.
- Проверки: `python -m compileall interview_prep`, `rg -n "Question source research|QUESTION_SOURCE_RESEARCH|\\[ \\] Question source research" ROADMAP.md DEVELOPMENT_LOG.md QUESTION_SOURCE_RESEARCH.md`.

### Content quality cleanup

- Закрыт roadmap leaf про cleanup accepted generic generated questions: добавлен явный CLI `questions-cleanup accepted-generic`, который архивирует только accepted generic generated questions из `background-llm`/`llm-seed` без удаления строк SQLite.
- Practice selection теперь берет только `accepted` questions, поэтому `archived` и `pending_review` rows не попадают в обычный practice loop.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_questions_audit_lists_generic_duplicate_and_too_long_questions tests.test_cli_flow.CLIFlowTests.test_questions_cleanup_archives_accepted_generic_generated_questions tests.test_services.ServiceTests.test_practice_selection_skips_archived_questions -v`, `python -m unittest tests.test_services.ServiceTests.test_mixed_session_next_question_prioritizes_weak_topic tests.test_services.ServiceTests.test_topic_session_repeats_weak_question_after_interval -v`, `python -m compileall interview_prep`.

### Content quality audit CLI

- Закрыт roadmap leaf про repeatable audit вопросов: добавлен read-only CLI `questions-audit`, который находит generic prompts по известным шаблонным формулировкам, same-topic duplicate prompts через существующую similarity logic и too-long prompts по настраиваемому `--max-prompt-chars`.
- Вывод audit включает `id`, `topic`, `source`, `source_quality`, `status`, finding kind, detail и prompt; команда не меняет SQLite и оставляет cleanup/curation отдельным следующим шагом.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_questions_audit_lists_generic_duplicate_and_too_long_questions -v`, `python -m compileall interview_prep`.

## 2026-05-26

### Calibration manual override readiness regression

- Закрыт roadmap leaf про regression-тест manual override readiness: добавлен service-level test, который сначала фиксирует low rubric readiness gap, затем применяет manual overrides как effective scores и проверяет рост readiness signal без потери original AI scores для аудита.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_manual_override_keeps_original_score_metadata tests.test_services.ServiceTests.test_readiness_uses_manual_override_scores_while_preserving_original_audit tests.test_services.ServiceTests.test_readiness_service_aggregates_competency_practice_signals -v`, `python -m compileall interview_prep`.

### Calibration rubric manual override readiness

- Закрыт roadmap leaf про manual override readiness: readiness aggregates теперь считают `avg_rubric_score` через `COALESCE(manual_override_score, score)`, а session outcome summary/strengths/gaps/readiness delta используют `AnswerEvaluationScore.effective_score`.
- `interview-report` теперь строит rubric gaps по effective score и помечает manual override рядом с original AI score в evidence section; CLI override сразу пересобирает completed session outcome, а устаревшие low-score drills не попадают в outcome, если dimension исправлена override до сильного score.
- Родительский manual override item закрыт, потому что foundation и effective-score surfaces завершены; отдельный regression-test leaf остается следующим в `## Next`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_manual_override_keeps_original_score_metadata tests.test_services.ServiceTests.test_readiness_service_aggregates_competency_practice_signals tests.test_services.ServiceTests.test_readiness_service_scores_competencies_with_gap_reasons tests.test_services.ServiceTests.test_finish_session_generates_session_outcome_from_scores_and_evaluations -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_evaluations_command_shows_saved_rubric_evaluation_for_answer tests.test_cli_flow.CLIFlowTests.test_evaluation_override_command_updates_one_dimension_with_audit_text tests.test_cli_flow.CLIFlowTests.test_interview_report_command_exports_markdown -v`, `python -m compileall interview_prep`.

### Calibration rubric manual override foundation

- Первый open roadmap item про manual override rubric score был слишком крупным для одной итерации, поэтому он разбит в `## Next` на foundation и readiness leaves.
- Закрыт foundation leaf: `answer_evaluation_scores` получил audit-поля manual override, `EvaluationService.override_score()` и CLI `evaluation-override` позволяют исправить одну rubric dimension, а `evaluations --answer` показывает effective score рядом с original AI score и reason.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_creates_rubric_evaluation_storage tests.test_services.ServiceTests.test_evaluation_service_manual_override_keeps_original_score_metadata -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_evaluations_command_shows_saved_rubric_evaluation_for_answer tests.test_cli_flow.CLIFlowTests.test_evaluation_override_command_updates_one_dimension_with_audit_text -v`, `python -m compileall interview_prep`.

### Calibration interview report export

- Закрыт roadmap leaf про Markdown export `interview-report`: добавлен read-only `InterviewReportService`, который собирает latest или выбранную completed practice session, readiness snapshot, session outcome, evidence answers и next plan.
- CLI-команда `python -m interview_prep interview-report [--session <id>]` печатает Markdown в stdout без изменения SQLite; README получил короткий пример команды.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_interview_report_command_exports_markdown -v`, `python -m compileall interview_prep`.

### Calibration repeat baseline delta comparison

- Закрыт roadmap leaf про baseline delta comparison: повторная baseline session теперь сохраняет в `SessionOutcome.summary` сравнение текущего `readiness_delta` с предыдущей completed baseline session.
- TUI finish-session screen уже показывает это сравнение через общий renderer session outcome; negative change дополнительно попадает в gaps baseline outcome.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_calibration_marks_baseline_session_outcome tests.test_services.ServiceTests.test_calibration_repeat_outcome_compares_delta_to_previous_baseline tests.test_services.ServiceTests.test_calibration_baseline_repeat_status_uses_seven_day_interval -v`, `python -m unittest tests.test_tui.TUITests.test_tui_repeat_baseline_finish_shows_delta_comparison tests.test_tui.TUITests.test_tui_baseline_finish_marks_session_outcome tests.test_tui.TUITests.test_tui_today_shows_due_repeat_baseline_action tests.test_tui.TUITests.test_tui_enter_starts_due_repeat_baseline_session -v`, `python -m compileall interview_prep`. Project `.venv/bin/python` отсутствовал в текущем checkout, поэтому проверки выполнены через доступный `python`.

## 2026-05-25

### Calibration repeat TUI action

- Закрыт roadmap leaf про repeat baseline action: Today panel теперь, когда completed calibration baseline старше 7 дней, показывает повторную baseline practice session как primary action и Enter запускает новый baseline session.
- `/readiness` показывает due repeat baseline в отдельном Calibration-блоке с последней session/date/readiness delta и action `/baseline-repeat`; команда запускает baseline только когда repeat действительно due.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.TUITests.test_tui_today_shows_due_repeat_baseline_action tests.test_tui.TUITests.test_tui_enter_starts_due_repeat_baseline_session tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_enter_starts_baseline_session_from_empty_state tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions -v`, `.venv/bin/python -m unittest tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration repeat baseline status

- Первый unchecked roadmap item про повторную baseline через 7 дней оказался слишком крупным для одной итерации, поэтому он разбит в `## Next` на service status, TUI action и delta comparison leaves.
- Закрыт первый leaf: `CalibrationService.baseline_repeat_status()` возвращает последнюю completed calibration baseline, следующий due time через 7 дней, последний `readiness_delta` и флаг доступности repeat baseline.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_calibration_baseline_repeat_status_uses_seven_day_interval tests.test_services.ServiceTests.test_calibration_starts_mixed_baseline_session_from_plan -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration must-fix readiness drills

- Закрыт roadmap leaf про "must fix before interview": `ReadinessGap` теперь содержит конкретный `must_fix_drill` для top gaps, а serialized readiness snapshot отдает его рядом с `next_action`.
- CLI `stats` и TUI `/readiness` показывают отдельный список `Must fix before interview` по top readiness gaps, чтобы перед интервью был короткий список конкретных drills.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_readiness_service_builds_overall_summary_without_absolute_claim tests.test_services.ServiceTests.test_readiness_recommends_low_rubric_topic_as_first_drill tests.test_cli_flow.CLIFlowTests.test_stats_command_shows_senior_readiness_top_gaps tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions -v`, `.venv/bin/python -m unittest tests.test_cli_flow.CLIFlowTests.test_stats_command_shows_senior_readiness_top_gaps -v`, `.venv/bin/python -m compileall interview_prep`. Первая попытка targeted suite использовала неверный class name `CliFlowTests` и завершилась loader error для этого target; исправленный `CLIFlowTests` прошел.

### Mock senior interview progress UI

- Закрыт roadmap leaf про mock interview progress: TUI хранит ordered sections из `MockSeniorInterviewSessionPlan` и показывает текущую section plus remaining sections в центральном practice review flow и правой practice-панели.
- Родительский roadmap item про mock senior interview mode закрыт, потому что planning/session/TUI action/progress leaves завершены.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.TUITests.test_tui_mock_interview_review_shows_section_progress tests.test_tui.TUITests.test_tui_mock_interview_command_starts_from_readiness_without_topic tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_baseline_review_shows_progress_and_remaining_questions -v`, `.venv/bin/python -m compileall interview_prep`.

### Mock senior interview TUI action

- Закрыт roadmap leaf про Today/readiness action: primary Today drill при system-design readiness gap и кнопка `Mock Senior Interview` запускают topicless mixed practice session из `CalibrationService.start_mock_senior_interview_session()`.
- Добавлена slash-команда `/mock-interview`, доступная из `/readiness`, чтобы начать mixed mock senior interview без ручного выбора topic; section progress остается следующим открытым leaf.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions tests.test_tui.TUITests.test_tui_mock_interview_command_starts_from_readiness_without_topic -v`, `.venv/bin/python -m compileall interview_prep`.

### Mock senior interview session

- Закрыт roadmap leaf про запуск mock senior interview session: `CalibrationService.start_mock_senior_interview_session()` создает topicless mixed practice session из deterministic mock interview plan и возвращает ordered sections/question ids.
- TUI action и progress UI остаются следующими открытыми leaves; текущий шаг только добавляет service-level session start contract.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_mock_senior_interview_plan_mixes_interview_sections tests.test_services.ServiceTests.test_calibration_starts_mixed_mock_senior_interview_session_from_plan tests.test_services.ServiceTests.test_calibration_starts_mixed_baseline_session_from_plan -v`, `.venv/bin/python -m compileall interview_prep`.

### Mock senior interview plan

- Первый unchecked roadmap item про mock senior interview mode оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller mock-interview leaves.
- Закрыт первый leaf: `CalibrationService.mock_senior_interview_plan()` строит deterministic plan из accepted questions для sections coding/theory/system design/debugging без ручного выбора topic.
- Текущий шаг не запускает TUI/session flow; следующие leaves должны подключить plan к mixed practice session, Today/readiness action и progress UI.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_mock_senior_interview_plan_mixes_interview_sections tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_calibration_starts_mixed_baseline_session_from_plan -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration baseline outcome marker

- Закрыт roadmap leaf про baseline outcome marker: `session_outcomes` получил `outcome_type` с default `practice`, а baseline completion маркирует outcome как `calibration_baseline` и добавляет summary marker с planned question count.
- Readiness weekly trend теперь сохраняет `baseline_session_count`, чтобы primary baseline sessions отличались от обычных practice outcomes в readiness payload.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_init_db_creates_session_outcome_storage tests.test_services.ServiceTests.test_repository_upserts_and_reads_session_outcome tests.test_services.ServiceTests.test_finish_session_generates_session_outcome_from_scores_and_evaluations tests.test_services.ServiceTests.test_calibration_marks_baseline_session_outcome tests.test_services.ServiceTests.test_readiness_service_builds_weekly_trend_from_completed_session_outcomes tests.test_tui.TUITests.test_tui_baseline_finish_marks_session_outcome -v`, `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_calibration_baseline_plan_prefers_unanswered_questions tests.test_services.ServiceTests.test_calibration_starts_mixed_baseline_session_from_plan tests.test_tui.TUITests.test_tui_enter_starts_baseline_session_from_empty_state tests.test_tui.TUITests.test_tui_baseline_review_shows_progress_and_remaining_questions tests.test_tui.TUITests.test_tui_baseline_finish_marks_session_outcome -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration baseline progress UI

- Закрыт roadmap leaf про baseline progress в TUI review flow: активная baseline session теперь показывает счетчик вида `Baseline progress: 1/5 answered, 4 remaining.` в центральном practice экране и правой practice-панели.
- Regression-тест проходит первый baseline question до scoring/review и проверяет, что progress/remaining видны на обоих шагах.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.TUITests.test_tui_enter_starts_baseline_session_from_empty_state tests.test_tui.TUITests.test_tui_baseline_review_shows_progress_and_remaining_questions -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration baseline session launch

- Закрыт roadmap leaf про запуск baseline practice session: `CalibrationService.start_baseline_session()` создает mixed practice session без topic и возвращает выбранный service-level план вопросов.
- Today empty-state `первая baseline practice session` теперь по Enter/Start Drill запускает baseline session и TUI берет следующие вопросы из сохраненного planned question id list, а не из обычной weak-topic сортировки.
- Progress/remaining UI и outcome marker остаются следующими открытыми baseline leaves.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_calibration_baseline_plan_prefers_unanswered_questions tests.test_services.ServiceTests.test_calibration_starts_mixed_baseline_session_from_plan -v`, `.venv/bin/python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_baseline_empty_state_when_curriculum_exists tests.test_tui.TUITests.test_tui_enter_starts_baseline_session_from_empty_state -v`, `.venv/bin/python -m compileall interview_prep`.

### Calibration baseline selection

- Первый unchecked roadmap item про baseline session flow оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller baseline leaves.
- Закрыт первый leaf: `CalibrationService.baseline_question_plan()` выбирает до 5 accepted questions по разным competencies, предпочитая primary competency links и unanswered questions.
- TUI/session execution для baseline остается открытым следующим leaf; текущий шаг только фиксирует service-level deterministic question plan.
- Проверки: `.venv/bin/python -m unittest tests.test_services.ServiceTests.test_calibration_baseline_plan_picks_five_distinct_competencies tests.test_services.ServiceTests.test_calibration_baseline_plan_prefers_unanswered_questions -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API adapter boundaries

- Закрыт roadmap leaf про adapter boundaries: README и CLAUDE теперь фиксируют, что будущий web UI должен идти через `ReadOnlyApplicationFacade` или явные service/use-case methods, а не напрямую в `SQLiteRepository`.
- Контракт WSGI adapter оставлен тонким: HTTP path/query validation, вызов facade method и JSON/HTML diagnostics serialization; write-сценарии должны сначала появляться в service layer с тестами.
- Проверки: `.venv/bin/python -m compileall interview_prep`, `rg -n "Web adapter boundary|Web adapter boundaries|\\[ \\] Web API: документировать adapter boundaries" README.md CLAUDE.md ROADMAP.md`.

### Web API HTML smoke page

- Закрыт roadmap leaf про simple HTML smoke page: read-only WSGI adapter теперь отдает `/` и `/smoke` как минимальную diagnostics-страницу с counters и ссылками на JSON endpoints.
- Страница явно подписана как diagnostics для будущего web adapter и не меняет основной продуктовый контракт: TUI остается primary interface, а endpoint не выполняет write-операций.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API query param validation tests

- Закрыт roadmap leaf про query param validation для новых endpoints: добавлен regression-тест `/api/notebook`, который проверяет `400 Bad Request` для нечислового `topic`, `limit` вне диапазона и сохранение read-only counters.
- WSGI adapter теперь валидирует numeric query params `/api/notebook` строго: `topic=...` должен быть числом, а `limit` должен быть в диапазоне 1..100; валидный запрос продолжает отдавать notebook payload.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API notebook endpoint

- Закрыт roadmap leaf про read-only `/api/notebook`: WSGI adapter теперь отдает notebook payload из `ReadOnlyApplicationFacade.notebook()` с `entries`, `manual_notes`, counts и примененными filters.
- Endpoint поддерживает filters `topic`, `competency`, `session`; competency фильтрует через linked question topics, session фильтрует AI entries по `dialog_session_id` и manual notes по numeric `session_id`, а internal TUI draft notes скрываются.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API session detail endpoint

- Закрыт roadmap leaf про read-only `/api/sessions/<id>`: WSGI adapter теперь отдает completed practice session detail из `ReadOnlyApplicationFacade.completed_session_detail()` вместе с сохраненным `outcome`.
- Endpoint возвращает `404 session_not_found` для отсутствующей или не completed practice session и `400 invalid_session_id` для нечислового id; payload остается read-only и не меняет counters.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API competencies endpoint

- Закрыт roadmap leaf про read-only `/api/competencies`: WSGI adapter теперь отдает competency readiness metadata из `ReadOnlyApplicationFacade.competency_readiness()` поверх существующих `ReadinessService` aggregates.
- Payload включает counts, `generated_at` и per-competency score/coverage metadata: linked/answered questions, answer coverage, rubric/self-score averages, readiness score и reasons.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### Web API readiness endpoint

- Закрыт roadmap leaf про read-only `/api/readiness`: WSGI adapter теперь отдает JSON-safe readiness snapshot напрямую из `ReadOnlyApplicationFacade.readiness()`, поверх существующего `ReadinessService`.
- Добавлен regression-тест web adapter, который проверяет структуру readiness payload и что endpoint не меняет session/answer counters.
- Проверки: `.venv/bin/python -m unittest tests.test_web -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI refactor contract documentation

- Закрыт roadmap leaf про обновление `ROADMAP.md` и `DEVELOPMENT_LOG.md` после выделения TUI-модулей: текущий статус roadmap теперь фиксирует, что pure render helpers, practice/learning/system-design controllers и content worker orchestration уже выделены из `ui/tui.py`.
- Поведенческий контракт для следующих TUI-изменений: новые state transitions должны оставаться в соответствующих controller/orchestration модулях, а `InterviewPrepTUI` должен удерживать UI/storage side effects и Textual wiring.
- Проверки: `.venv/bin/python -m compileall interview_prep`, `rg -n "\\[ \\].*TUI refactor: обновить|TUI refactor: roadmap/log|TUI refactor contract documentation" ROADMAP.md DEVELOPMENT_LOG.md`. Первая попытка через `python -m compileall interview_prep` не запускалась, потому что в shell нет команды `python`.

## 2026-05-22

### TUI mode chain smoke regression

- Закрыт roadmap leaf про smoke test переключения `Today -> Practice -> Learn -> System Design -> Readiness -> Practice`: добавлен TUI regression-тест, который стартует baseline practice из Today, проходит через learning/system design/readiness и возвращается в исходную practice session.
- Тест фиксирует поддержанный mixed navigation contract: mode action buttons для Practice/Learn/System Design, slash-command `/readiness` из focused mode и возврат в practice через Practice action.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.TUITests.test_tui_smoke_switches_today_practice_learn_system_design_readiness_practice tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows tests.test_tui.TUITests.test_tui_clicking_mode_actions_before_topic_does_not_stick_in_learning -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI content worker unmount stability

- Закрыт roadmap leaf про regression-тест TUI unmount: `ContentWorkerOrchestrator.mark_unmounted()` теперь сбрасывает stale running state, если приложение закрывается до завершения background callback.
- `InterviewPrepTUI.on_unmount()` вызывает этот teardown hook перед сохранением notes/session close, чтобы следующий render/status snapshot не оставался в `generating...`.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.ContentWorkerControllerTests tests.test_tui.TUITests.test_tui_unmount_clears_running_content_worker_state tests.test_tui.TUITests.test_tui_unmount_persists_notes_draft_across_database_reopen -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI worker thread callback stability

- Закрыт roadmap leaf про RuntimeWarning `call_from_thread`: background content worker и system design async flows теперь возвращают результат в Textual через queued `call_later`, не блокируя worker thread на app loop.
- Это сохраняет прежний finish/render contract, но избегает unawaited coroutine warning, когда TUI test teardown пересекается с завершением background thread.
- Проверки: `.venv/bin/python -W error::RuntimeWarning -m unittest tests.test_tui.ContentWorkerControllerTests tests.test_tui.SystemDesignControllerTests tests.test_tui.TUITests.test_tui_auto_queues_system_design_scenario_when_entering_mode tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer tests.test_tui.TUITests.test_tui_generate_curriculum_command_queues_job_and_starts_worker tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs tests.test_tui.TUITests.test_tui_content_screen_retries_failed_job -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI content worker finish transition

- Закрыт roadmap leaf про finish/result status transition: `ContentWorkerOrchestrator.finish_run()` теперь нормализует result payload, сбрасывает running state и выбирает итоговый status для empty/done/failed/paused outcomes.
- `InterviewPrepTUI.finish_background_content_worker()` оставляет artifact-specific side effects в `apply_background_content_result()`, но финальный worker status берет из controller snapshot.
- Родительский roadmap item про content worker orchestration закрыт, потому что все выделенные controller leaf завершены.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.ContentWorkerControllerTests tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs tests.test_tui.TUITests.test_tui_content_screen_pauses_and_resumes_worker_without_deleting_jobs tests.test_tui.TUITests.test_tui_content_screen_retries_failed_job -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI content worker loop orchestration

- Закрыт roadmap leaf про worker loop/process-next-job orchestration: `ContentWorkerOrchestrator.process_available_jobs()` теперь владеет batch loop до трех ready jobs, empty-queue stop и exception-to-last-error handling.
- `InterviewPrepTUI.start_background_content_worker()` оставляет за собой AppServices lifecycle, thread handoff через `call_from_thread` и result application; finish/result status transition пока остается следующим unchecked leaf.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.ContentWorkerControllerTests tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs tests.test_tui.TUITests.test_tui_content_screen_pauses_and_resumes_worker_without_deleting_jobs tests.test_tui.TUITests.test_tui_content_screen_retries_failed_job -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI content worker orchestration state

- Первый unchecked roadmap item про content worker orchestration оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller controller leaves.
- Закрыт первый leaf: `interview_prep.ui.content_worker_controller.ContentWorkerOrchestrator` теперь владеет TUI-local `status`/`running`/`paused` state и pause/resume/start guard decisions.
- `InterviewPrepTUI` делегирует эти флаги через свойства, сохраняя прежние thread side effects, worker loop и result application внутри TUI для следующих leaf.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.ContentWorkerControllerTests tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs tests.test_tui.TUITests.test_tui_content_screen_pauses_and_resumes_worker_without_deleting_jobs tests.test_tui.TUITests.test_tui_content_screen_retries_failed_job -v`, `.venv/bin/python -m compileall interview_prep`. Первая попытка targeted TUI tests использовала устаревшие имена двух тестов и завершилась loader errors без выполнения этих тестов.

### TUI system design auxiliary transitions controller

- Закрыт roadmap leaf про checkpoint/pressure/final-feedback transitions: loading и finish state для `/sd-checkpoint`, `/sd-pressure` и `/sd-feedback` теперь проходят через pure helpers в `interview_prep.ui.system_design_controller`.
- `InterviewPrepTUI` применяет snapshots вокруг прежних side effects: сохранение checkpoint/pressure transcript messages и final feedback artifact/evaluation осталось в TUI/service path.
- Родительский roadmap item про system-design state transitions закрыт, потому что все выделенные controller leaf завершены.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.SystemDesignControllerTests tests.test_tui.TUITests.test_tui_system_design_checkpoint_saves_interviewer_message_without_final_feedback tests.test_tui.TUITests.test_tui_system_design_pressure_saves_interviewer_follow_up_without_final_feedback tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI system design finish-turn controller

- Закрыт roadmap leaf про finish-turn transition: ответ interviewer в system design mock теперь проходит через pure `interview_prep.ui.system_design_controller.build_system_design_finish_turn_snapshot()` для transcript entries, pending state, Ollama/fallback status, history message и возврата в `system_design`.
- `InterviewPrepTUI.finish_system_design_turn()` применяет snapshot вокруг прежних side effects: сохранение transcript и автоперенос artifact-команд из candidate message остались в TUI/service path.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.SystemDesignControllerTests tests.test_tui.TUITests.test_tui_composer_submits_multiline_code_block_to_system_design tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer tests.test_tui.TUITests.test_tui_autosaves_explicit_artifact_commands_from_system_design_transcript -v`, `.venv/bin/python -m compileall interview_prep`.

### TUI system design request controller

- Закрыт roadmap leaf про request/loading transition для кандидатского turn: отправка сообщения в system design mock теперь использует pure `interview_prep.ui.system_design_controller.build_system_design_request_snapshot()` для pending message, loading mode, Ollama status и history message.
- `InterviewPrepTUI.request_system_design_turn()` применяет snapshot перед прежними side effects: async interviewer call, transcript/artifact persistence и finish-render flow остались в TUI.
- Проверки: `.venv/bin/python -m unittest tests.test_tui.SystemDesignControllerTests tests.test_tui.TUITests.test_tui_composer_submits_multiline_code_block_to_system_design tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `.venv/bin/python -m compileall interview_prep`. Системный `python3` не смог импортировать TUI tests из-за отсутствующего `textual`, поэтому итоговые проверки выполнены через project `.venv`.

### TUI system design entry controller

- Первый unchecked roadmap item про system-design state transitions оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller controller leaves.
- Закрыт первый leaf: вход в `/system-design` теперь использует pure `interview_prep.ui.system_design_controller.build_system_design_entry_snapshot()` для return mode, сохраненного practice context, scenario/transcript reset contract и focused-mode feedback.
- `InterviewPrepTUI.enter_system_design()` применяет snapshot перед прежними side effects: запуск/выбор session topic, background content/scenario orchestration, artifact restore и render flow остались в TUI.
- Проверки: `python -m unittest tests.test_tui.SystemDesignControllerTests tests.test_tui.TUITests.test_tui_auto_queues_system_design_scenario_when_entering_mode tests.test_tui.TUITests.test_tui_reuses_saved_system_design_scenario_without_queueing_job tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows tests.test_tui.TUITests.test_tui_composer_submits_multiline_code_block_to_system_design -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer tests.test_tui.TUITests.test_tui_persists_and_restores_system_design_artifacts_for_scenario -v`, `python -m compileall interview_prep`.

### TUI learning finish controller

- Закрыт roadmap leaf про finish-learning transition: ответ learning LLM теперь проходит через pure `interview_prep.ui.learning_controller.build_learning_finish_snapshot()` для fallback/ok статуса, history message, transcript entries, pending state, dialog offset и финального `last_feedback`.
- `InterviewPrepTUI.finish_learning()` применяет snapshot вокруг прежних side effects: сохранение learning transcript/notebook осталось в TUI/service path, а learning-mode controller leaves теперь закрыты полностью.
- Проверки: `python -m unittest tests.test_tui.LearningControllerTests tests.test_tui.TUITests.test_tui_learning_mode_persists_dialog_through_service tests.test_tui.TUITests.test_tui_composer_submits_multiline_code_block_to_learning tests.test_tui.TUIHelperTests.test_learning_text_uses_chat_renderer_for_dialog_and_pending_message -v`, `python -m compileall interview_prep`.

### TUI learning request controller

- Закрыт roadmap leaf про request/loading transition: отправка учебного вопроса теперь использует pure `interview_prep.ui.learning_controller.build_learning_request_snapshot()` для dialog session id, pending message, loading mode, Ollama status и history message.
- `InterviewPrepTUI.request_learning()` применяет snapshot перед прежними side effects: lookup topic/question context, async LLM call, save transcript/notebook и render flow остались в TUI.
- Проверки: `python -m unittest tests.test_tui.LearningControllerTests tests.test_tui.TUITests.test_tui_learning_mode_persists_dialog_through_service tests.test_tui.TUITests.test_tui_composer_submits_multiline_code_block_to_learning tests.test_tui.TUITests.test_tui_learning_before_topic_selection_does_not_load_saved_topic_dialog -v`, `python -m compileall interview_prep`.

### TUI learning entry controller

- Первый unchecked roadmap item про learning-mode state transitions оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller controller leaves.
- Закрыт первый leaf: вход в `/learn` теперь использует pure `interview_prep.ui.learning_controller.build_learning_entry_snapshot()` для return mode, dialog session id, topic context и решений по generated learning material.
- `InterviewPrepTUI` применяет snapshot перед прежними UI/storage side effects: history, загрузка transcript, проверка material backlog и render flow остались в TUI.
- Проверки: `python -m unittest tests.test_tui.LearningControllerTests tests.test_tui.TUITests.test_tui_auto_queues_learning_material_when_entering_learning_mode tests.test_tui.TUITests.test_tui_reuses_saved_learning_material_without_queueing_job tests.test_tui.TUITests.test_tui_learning_before_topic_selection_does_not_load_saved_topic_dialog -v`, `python -m compileall interview_prep`.

### TUI practice answer transition controller

- Закрыт roadmap leaf про answer -> scoring -> answered contract: `interview_prep.ui.practice_controller` теперь содержит pure snapshots для сохраненного ответа, завершенной самооценки и перехода к следующему вопросу, а также parsing optional self-score.
- `InterviewPrepTUI` применяет эти snapshots вокруг существующих service/storage side effects: сохранение answer, обновление self-score, rubric evaluation и render/history flow остались в TUI.
- Родительский roadmap item про practice-mode state transitions закрыт, потому что все три выделенных controller leaf завершены.
- Проверки: `python -m unittest tests.test_tui.PracticeControllerTests tests.test_tui.TUITests.test_tui_can_answer_one_question_and_save_score tests.test_tui.TUITests.test_tui_composer_submits_multiline_practice_answer tests.test_tui.TUITests.test_tui_slash_commands_update_visible_state -v`, `python -m compileall interview_prep`.

### TUI practice session snapshots

- Закрыт roadmap leaf про reset/start-session state snapshot: `interview_prep.ui.practice_controller` теперь возвращает pure `PracticeSessionStartSnapshot` и `PracticeSessionResetSnapshot` без Textual harness.
- `InterviewPrepTUI` применяет эти snapshots перед прежними UI/storage side effects: history, notes persistence, background content check, `load_next_question()` и render flow оставлены в TUI.
- Проверки: `python -m unittest tests.test_tui.PracticeControllerTests tests.test_tui.TUITests.test_tui_can_answer_one_question_and_save_score tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_composer_keeps_fast_command_and_topic_submit_flow -v`, `python -m compileall interview_prep`.

### TUI practice submit controller

- Первый unchecked roadmap item про practice-mode state transitions оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на smaller controller leaves.
- Закрыт первый leaf: submit-routing для practice modes `select_topic`/`answering`/`scoring`/`answered` вынесен в `interview_prep.ui.practice_controller.decide_practice_submit()` как pure helper без Textual harness.
- `InterviewPrepTUI` теперь только применяет `PracticeSubmitDecision`, оставляя UI/storage side effects в TUI; answer-flow regression-тест стартует practice через явный topic id, чтобы не конфликтовать с Today empty-state Enter -> `/generate-curriculum`.
- Проверки: `python -m unittest tests.test_tui.PracticeControllerTests tests.test_tui.TUITests.test_tui_can_answer_one_question_and_save_score tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_composer_keeps_fast_command_and_topic_submit_flow -v`, `python -m compileall interview_prep`.

### TUI render helper extraction

- Закрыт roadmap leaf про вынос pure render helpers: stateless форматтеры, markdown/chat rendering, content job label/parsing helpers, feedback gap extraction и command palette перенесены из `interview_prep/ui/tui.py` в `interview_prep/ui/tui_render.py`.
- `interview_prep.ui.tui` импортирует эти имена обратно, чтобы существующий TUI-код и тесты с прежним import surface не меняли поведение.
- Проверки: `python -m unittest tests.test_tui.TUIHelperTests -v`, `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_daily_practice_shows_ai_feedback_in_center_panel tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `python -m compileall interview_prep`.

### TUI Today command palette grouping

- Закрыт roadmap leaf про группировку command palette: `/commands` теперь показывает команды по workflow-секциям Today, Practice, Learning, Notebook, Content, Materials, System Design, History и Utility вместо одного длинного списка.
- Regression-тест command palette теперь проверяет наличие workflow-заголовков, порядок секций относительно ключевых команд и прежнее покрытие core commands.
- Проверки: `python -m unittest tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands tests.test_tui.TUITests.test_tui_slash_commands_update_visible_state tests.test_tui.TUITests.test_tui_composer_keeps_fast_command_and_topic_submit_flow -v`, `python -m compileall interview_prep`.

### TUI Today Review Weak Answer regression

- Закрыт roadmap leaf про regression-тест клика по `Review Weak Answer`: тест теперь создает слабый evaluated answer с низкой rubric оценкой, кликает кнопку Today и проверяет переход в practice по linked competency topic.
- Product decision: для low-rubric readiness drill кнопка `Review Weak Answer` стартует practice по теме, связанной с competency drill; если такого drill нет, остается fallback в `/readiness`.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_today_review_weak_answer_click_starts_low_rubric_practice tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill -v`, `python -m compileall interview_prep`.

### TUI Today Enter recommended drill regression

- Закрыт roadmap leaf про regression-тест keyboard flow Enter -> recommended drill: стартовый Today screen теперь покрыт тестом, который нажимает Enter в пустом composer и проверяет переход в recommended system design drill.
- Runtime-поведение не менялось; тест фиксирует уже реализованный contract Enter как эквивалент primary `Start Drill`.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_today_enter_starts_recommended_drill tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill -v`, `python -m compileall interview_prep`.

### TUI Today empty-state

- Закрыт roadmap leaf про empty-state при недостатке readiness data: если нет сохраненных ответов/rubric evidence, Today теперь предлагает сначала `/generate-curriculum`, когда generated curriculum отсутствует, или первую baseline practice session, когда curriculum уже есть.
- `Start Drill` на пустом readiness state следует этому же контракту: ставит curriculum job для bootstrap-only базы или запускает baseline practice, а обычные readiness-driven drills остаются без изменений после появления evidence.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_empty_state_without_evidence tests.test_tui.TUITests.test_tui_start_screen_shows_baseline_empty_state_when_curriculum_exists tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_start_screen_warns_when_generated_curriculum_is_missing -v`, `python -m compileall interview_prep`.

### TUI Today readiness drill reason

- Закрыт roadmap leaf про "why this drill" из `ReadinessService`: `ReadinessGap` теперь сам отдает `why_this_drill`, поле входит в serialized readiness snapshot, а Today panel рендерит именно service-level explanation.
- TUI fallback для старых/подмененных drill-like объектов оставлен без изменения поведения.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_service_builds_overall_summary_without_absolute_claim tests.test_services.ServiceTests.test_readiness_recommends_low_rubric_topic_as_first_drill -v`, `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill -v`, `python -m compileall interview_prep`.

### TUI Today Enter primary drill

- Закрыт roadmap leaf про Enter на стартовом экране: пустой Enter теперь запускает тот же primary recommended drill, что и кнопка `Start Drill`, включая system design mock или curriculum generation по readiness reasons.
- Ручной practice topic flow оставлен вторичным: ввод ID темы и `/accept-topic` продолжают запускать выбранную/recommended practice-тему, а Today copy и placeholder обновлены под новый keyboard contract.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_shows_curriculum_recommended_topic_on_practice_start tests.test_tui.TUITests.test_tui_accept_topic_command_starts_curriculum_recommended_topic -v`, `python -m compileall interview_prep`, ad hoc `InterviewPrepTUI.run_test()` smoke для Enter -> `system_design`.

### TUI Today action buttons

- Закрыт roadmap leaf про Today action buttons: на стартовом экране добавлена отдельная строка кнопок `Start Drill`, `Review Weak Answer`, `System Design Mock`, `Open Readiness`, `Notebook`.
- `Start Drill` запускает primary readiness action: system design mock для system-design gap, curriculum generation для gap без связанных вопросов, иначе recommended practice; остальные кнопки переиспользуют существующие safe TUI workflows.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_today_action_buttons_are_visible_and_start_primary_drill tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows -v`, `python -m compileall interview_prep`.

## 2026-05-21

### TUI Today compact panel

- Закрыт roadmap leaf про компактный Today panel: стартовый экран выбора темы больше не открывается длинной инструкцией, а показывает recommended drill, why now, expected time и primary action из readiness-driven next action.
- Secondary navigation оставлена компактной строкой с topic list/topic ID и ключевыми slash commands, чтобы не менять Enter/buttons behavior из следующих roadmap leaf.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_start_screen_warns_when_generated_curriculum_is_missing tests.test_tui.TUITests.test_tui_shows_curriculum_recommended_topic_on_practice_start -v`, `python -m unittest tests.test_tui.TUITests.test_tui_notebook_action_opens_current_topic_entries tests.test_tui.TUITests.test_tui_generate_curriculum_command_queues_job_and_starts_worker -v`, `python -m compileall interview_prep`.

### TUI notes unmount persistence regression

- Закрыт roadmap leaf про сохранение notes при TUI unmount и повторном открытии базы: добавлен regression-тест, который записывает global notes draft, закрывает TUI и проверяет восстановление после запуска нового app instance с тем же SQLite-файлом.
- Исправлен unmount path: TUI кеширует widget notes editor и его текст, чтобы `persist_notes_draft()` мог сохранить последний draft даже когда Textual уже не отдает widget через `query_one()`.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_unmount_persists_notes_draft_across_database_reopen tests.test_tui.TUITests.test_tui_saves_notes_editor_draft_on_mode_switch_and_exit tests.test_tui.TUITests.test_tui_restores_notes_editor_draft_when_context_returns -v`, `python -m compileall interview_prep`.

### Notebook note from answer

- Закрыт roadmap leaf про `/note-from-answer`: TUI теперь сохраняет gap из последнего AI feedback как `notebook_entries` source `answer-feedback` с привязкой к текущей теме и answer id через `dialog_session_id`.
- Команда берет явный раздел gap из feedback, добавляет rubric gaps/next drills при наличии structured evaluation и показывает сохраненную запись в `/notebook`; README/CLAUDE/command palette обновлены.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_note_from_answer_saves_feedback_gap_to_notebook tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m unittest tests.test_tui.TUITests.test_tui_daily_practice_shows_ai_feedback_in_center_panel tests.test_tui.TUITests.test_tui_note_from_answer_saves_feedback_gap_to_notebook tests.test_tui.TUITests.test_tui_recheck_feedback_replaces_last_feedback_with_strict_prompt -v`, `python -m compileall interview_prep`.

### Notebook competency filter

- Закрыт roadmap leaf про `/notebook competency <slug>`: TUI notebook теперь фильтрует AI explanations и named manual notes по темам, у которых есть вопросы с linked senior competency.
- Фильтр работает без изменения SQLite-схемы через `question_competencies`; command palette, README и CLAUDE обновлены новой командой.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_notebook_screen_filters_entries_by_competency tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic tests.test_tui.TUITests.test_tui_notebook_screen_shows_manual_notes_with_ai_entries tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### Notebook manual notes

- Закрыт roadmap leaf про показ manual notes в `/notebook`: экран конспекта теперь показывает named manual notes рядом с AI explanations с тем же topic/all фильтром.
- Internal draft rows notes editor (`tui-notes-draft` / `TUI notes draft`) скрыты из notebook, чтобы не смешивать автосохраненные черновики с ручными заметками.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_notebook_screen_shows_manual_notes_with_ai_entries tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic -v`, `python -m compileall interview_prep`.

### TUI save-note command

- Закрыт roadmap leaf про `/save-note <title>`: TUI теперь сохраняет multiline composer text как named `manual_notes` entry с текущим session/topic/global context.
- Команда ожидает первую строку `/save-note <title>`, а тело заметки — следующими строками composer через Shift+Enter; command palette и README обновлены.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_save_note_command_persists_multiline_composer_text -v`, `python -m unittest tests.test_tui.TUITests.test_tui_has_scrollable_panels_and_notes_editor tests.test_tui.TUITests.test_tui_save_note_command_persists_multiline_composer_text tests.test_tui.TUITests.test_tui_saves_notes_editor_draft_on_mode_switch_and_exit tests.test_tui.TUITests.test_tui_restores_notes_editor_draft_when_context_returns tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### TUI notes draft restore

- Закрыт roadmap leaf про восстановление notes editor при возврате в session/topic context: TUI теперь отслеживает активный notes draft context, сохраняет предыдущий draft перед сменой context и загружает сохраненный `tui-notes-draft` обратно в editor.
- Restore работает для session/topic/global contexts поверх существующих `manual_notes` rows без изменения SQLite-схемы.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_saves_notes_editor_draft_on_mode_switch_and_exit tests.test_tui.TUITests.test_tui_restores_notes_editor_draft_when_context_returns -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### TUI notes draft persistence

- Закрыт roadmap leaf про сохранение TUI notes editor при смене режима и выходе: notes editor теперь сохраняет текущий draft в `manual_notes` с context `tui-notes-draft` для session/topic/global.
- `SQLiteRepository` получил `upsert_manual_note_by_context()`, чтобы повторные mode switch/quit обновляли один draft-row вместо создания дублей.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_repository_persists_manual_notes_with_context_links -v`, `python -m unittest tests.test_tui.TUITests.test_tui_saves_notes_editor_draft_on_mode_switch_and_exit -v`, `python -m unittest tests.test_tui.TUITests.test_tui_has_scrollable_panels_and_notes_editor tests.test_tui.TUITests.test_tui_saves_notes_editor_draft_on_mode_switch_and_exit -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Manual notes SQLite storage

- Закрыт roadmap leaf про SQLite-хранилище manual notes: добавлена domain-модель `ManualNote`, таблица `manual_notes` и schema version поднята до 12.
- `SQLiteRepository` получил `add_manual_note()`, `get_manual_note()` и `list_manual_notes()` с фильтрами `topic_id`, `session_id`, `context_type` и `context_id`; TUI notes editor пока не подключался.
- Проверки: `python -m unittest tests.test_domain_models.DomainModelTests.test_manual_note_model_describes_user_authored_note tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_creates_manual_notes_storage tests.test_services.ServiceTests.test_repository_persists_manual_notes_with_context_links -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### System design artifact score regression

- Закрыт roadmap leaf про artifact-команды и итоговый completeness score: добавлен TUI regression-тест, который сначала сохраняет baseline `/sd-feedback`, затем добавляет `/req`, `/api`, `/data`, `/decision`, `/risk` и проверяет рост среднего system design rubric score.
- Тест использует реальный `SystemDesignService.save_final_feedback()` и heuristic evaluation path, подменяя только LLM-facing `next_turn`/`final_feedback`, чтобы не зависеть от Ollama.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_system_design_artifact_commands_improve_final_rubric_score -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_artifact_commands_improve_final_rubric_score tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `python -m compileall interview_prep`.

### System design history CLI

- Закрыт roadmap leaf про CLI `system-design-history`: команда показывает список saved system design feedback/scenarios, а detail view через `--feedback <id>` или `--scenario <id>` выводит scenario, transcript, artifacts, final feedback и stored rubric scores.
- Команда читает существующие repository tables без изменения SQLite-схемы и поддерживает default/custom scenario rows через `scenario_id IS NULL`.
- README и CLAUDE обновлены CLI workflow для system design history.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_system_design_history_command_shows_feedback_detail -v`, `python -m compileall interview_prep`.

### System design history feedback scores

- Закрыт roadmap leaf про показ system design final feedback в TUI history: добавлен `/history system-design` со списком saved feedback artifacts и `/history system-design <feedback-id>` с read-only просмотром итогового feedback и stored rubric scores.
- TUI history side panel и command palette теперь подсказывают system design history path; README/CLAUDE обновлены новым workflow.
- Добавлен repository read helper `get_system_design_feedback_artifact()` без изменения схемы.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_shows_system_design_feedback_and_rubric_scores tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m unittest tests.test_services.ServiceTests.test_system_design_service_saves_final_feedback_artifact_with_metadata tests.test_services.ServiceTests.test_repository_persists_system_design_evaluation_scores tests.test_services.ServiceTests.test_system_design_service_stores_rubric_evaluation_after_final_feedback -v`, `python -m compileall interview_prep`.

### System design pressure follow-up command

- Закрыт roadmap leaf про pressure follow-up questions: TUI system design mode получил `/sd-pressure`, который запрашивает один targeted interviewer follow-up по capacity, hot keys, retries, idempotency, migrations или abuse protection.
- Добавлен отдельный service prompt для pressure follow-up: он явно запрещает final score/level/verdict, использует transcript и saved artifacts, а результат сохраняется только как interviewer transcript message.
- README, command palette, ROADMAP и CLAUDE обновлены новой командой.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_system_design_pressure_prompt_targets_senior_failure_modes_without_final_score tests.test_services.ServiceTests.test_system_design_checkpoint_prompt_is_not_final_evaluation -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_pressure_saves_interviewer_follow_up_without_final_feedback tests.test_tui.TUITests.test_tui_system_design_checkpoint_saves_interviewer_message_without_final_feedback tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands tests.test_tui.TUIHelperTests.test_system_design_text_shows_missing_sections_before_feedback -v`, `python -m compileall interview_prep`.

### System design checkpoint command

- Закрыт roadmap leaf про `/sd-checkpoint`: TUI system design mode получил промежуточный interviewer checkpoint без финального artifact/evaluation.
- Добавлен отдельный service prompt для checkpoint: он явно запрещает level/score/final verdict, использует transcript и saved artifacts, а результат сохраняется только как interviewer transcript message.
- README и command palette обновлены новой командой.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_system_design_checkpoint_prompt_is_not_final_evaluation tests.test_services.ServiceTests.test_system_design_prompts_use_interviewer_flow_and_senior_criteria -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_checkpoint_saves_interviewer_message_without_final_feedback tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### System design missing sections preflight

- Закрыт roadmap leaf про missing sections before feedback: system design screen теперь показывает блок `Missing sections before /sd-feedback`, если requirements/API/data/risks еще пустые.
- `/sd-feedback` остается не блокирующим, но при запуске добавляет history-событие с пустыми секциями, чтобы пользователь видел слабые места до итогового feedback.
- Проверки: `python -m unittest tests.test_tui.TUIHelperTests.test_system_design_text_shows_missing_sections_before_feedback tests.test_tui.TUIHelperTests.test_system_design_text_uses_chat_renderer_for_transcript_pending_and_feedback -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### System design rubric evaluation storage

- Закрыт roadmap leaf про оценку transcript/artifacts после `/sd-feedback`: финальный feedback artifact теперь получает связанную `SystemDesignEvaluation` со scores по seeded system design rubric dimensions.
- SQLite-схема поднята до версии 11 и получила таблицы `system_design_evaluations`/`system_design_evaluation_scores`; repository умеет add/get/list evaluation по feedback/topic/scenario/session.
- Service-level heuristic оценивает только кандидатские transcript messages и saved artifacts, чтобы interviewer questions не засчитывались как candidate evidence; UI/history display оставлены следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_domain_models.DomainModelTests.test_system_design_evaluation_model_describes_rubric_scores -v`, `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_creates_system_design_evaluation_storage tests.test_services.ServiceTests.test_repository_persists_system_design_evaluation_scores tests.test_services.ServiceTests.test_system_design_service_stores_rubric_evaluation_after_final_feedback tests.test_services.ServiceTests.test_system_design_service_saves_final_feedback_artifact_with_metadata -v`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `python -m compileall interview_prep`.

### System design rubric dimensions

- Закрыт roadmap leaf про system design rubric dimensions: добавлен отдельный seeded contract для requirements, API, data model, scaling, consistency, reliability, observability и tradeoffs.
- SQLite-схема поднята до версии 10 и получила таблицу `system_design_rubric_dimensions`, чтобы будущая оценка `/sd-feedback` не расширяла practice answer rubric и не меняла текущий evaluation flow.
- `SQLiteRepository` получил методы upsert/get/find/list для system design rubric dimensions; seed idempotent и покрыт regression-тестами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_rubric_dimensions tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_system_design_rubric_dimensions tests.test_services.ServiceTests.test_repository_lists_gets_and_upserts_rubric_dimensions tests.test_services.ServiceTests.test_repository_lists_gets_and_upserts_system_design_rubric_dimensions -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### System design final feedback artifact

- Закрыт roadmap leaf про сохранение итогового `/sd-feedback`: добавлена domain-модель `SystemDesignFeedbackArtifact`, SQLite-таблица `system_design_feedback_artifacts` и repository/service methods для записи feedback с topic/scenario/session metadata.
- TUI после `/sd-feedback` сохраняет итоговый feedback как отдельный artifact с `scenario_id`, текущим `session_id` и source `llm`/`fallback`, не создавая обычный interview answer.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_system_design_service_saves_final_feedback_artifact_with_metadata tests.test_services.ServiceTests.test_system_design_service_saves_and_lists_artifacts -v`, `python -m unittest tests.test_tui.TUITests.test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer -v`, `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_system_design_service_saves_final_feedback_artifact_with_metadata -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Duplicate generated question count regression

- Закрыт roadmap leaf про duplicate background question count: existing content-generation regression теперь явно фиксирует, что при похожем generated prompt не растет ни topic-level, ни общий question count.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_content_generation_skips_similar_question_in_same_topic -v`, `python -m compileall interview_prep`.

### Generated artifact archive reasons

- Закрыт roadmap leaf про reason при архивировании generated materials/scenarios: SQLite-схема поднята до версии 8, а `learning_materials` и `system_design_scenarios` получили nullable `archive_reason` с backward-compatible migration guard.
- TUI-команды `/archive-material <id> confirm [reason]` и `/archive-scenario <id> confirm [reason]` сохраняют текст после `confirm`, показывают его в history и продолжают скрывать archived rows из `/materials` без удаления.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_adds_learning_material_archive_column_to_existing_database tests.test_services.ServiceTests.test_init_db_adds_system_design_scenario_archive_column_to_existing_database tests.test_services.ServiceTests.test_repository_archives_learning_materials_without_deleting_rows tests.test_services.ServiceTests.test_repository_archives_system_design_scenarios_without_deleting_rows -v`, `python -m unittest tests.test_tui.TUITests.test_tui_materials_screen_lists_and_opens_saved_artifacts tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Generated question tag/competency metadata

- Закрыт roadmap leaf про prompt для generated question tags/competencies: background question prompt теперь требует `tag_slugs` и `competency_slugs`, перечисляя допустимые seeded competency slugs.
- `ContentGenerationService` сохраняет LLM tags как `background-llm` tags, привязывает их к новому вопросу и связывает только существующие competencies; неизвестные competency slugs игнорируются без падения job.
- Result artifact для question job теперь включает `tag_slugs` и `competency_slugs`, чтобы `/content`/diagnostics могли видеть примененную metadata.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_background_question_prompt_requests_tags_and_known_competencies tests.test_services.ServiceTests.test_content_generation_queue_creates_background_question tests.test_services.ServiceTests.test_content_generation_links_llm_tags_and_competencies_to_generated_question tests.test_services.ServiceTests.test_content_generation_skips_similar_question_in_same_topic -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### TUI generated questions review

- Закрыт roadmap leaf про TUI `/questions-review`: добавлен focused read-only экран pending generated questions с topic, difficulty, source/status, prompt, hint, reference preview и командами accept/archive.
- Команды `/questions-review accept <id>` и `/questions-review archive <id>` переиспользуют `QuestionService`, работают только с pending-review вопросами и обновляют список без выхода в CLI.
- README обновлен TUI-командами review flow.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_questions_review_lists_and_updates_pending_generated_questions tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### CLI generated questions review

- Закрыт roadmap leaf про CLI `questions-review`: команда показывает generated questions со статусом `pending_review`, включая topic, difficulty, source, prompt, hint и reference answer.
- Добавлены безопасные actions `questions-review accept <id>` и `questions-review archive <id>`: они работают только с pending-review вопросами и переводят их в `accepted` или `archived` без удаления строк из SQLite.
- README обновлен примерами review-команд.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_questions_review_lists_pending_generated_questions tests.test_cli_flow.CLIFlowTests.test_questions_review_accepts_and_archives_pending_questions -v`, `python -m unittest tests.test_cli_flow -v`, `python -m compileall interview_prep`.

## 2026-05-20

### Generated question source quality status

- Закрыт roadmap leaf про source_quality/status для generated questions: `Question` теперь хранит `source_quality_status` со статусами `pending_review`, `accepted`, `archived`.
- SQLite-схема поднята до версии 7; новый столбец `questions.source_quality_status` добавляется backward-compatible к legacy базам, bootstrap/manual вопросы остаются `accepted`.
- Background `question` jobs и `llm-seed` curriculum questions теперь сохраняются как `pending_review`; repository умеет фильтровать вопросы по статусу и переводить вопрос в другой статус для будущих `questions-review`/archive flows.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_seed_defaults_adds_minimal_bootstrap_topics_and_questions tests.test_services.ServiceTests.test_repository_tracks_question_source_quality_status tests.test_services.ServiceTests.test_content_generation_queue_creates_background_question tests.test_services.ServiceTests.test_curriculum_service_generates_and_saves_llm_seed_questions -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`.

### Content quality question similarity gate

- Закрыт roadmap leaf про similarity check для generated questions: background `question` job теперь перед сохранением сравнивает prompt с уже существующими вопросами той же темы.
- Product decision: gate консервативный и локальный для topic; он использует нормализованные tokens и sequence similarity, а при очевидном дубле завершает job как `done`, возвращая существующий question без новой строки в `questions`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_content_generation_skips_similar_question_in_same_topic tests.test_services.ServiceTests.test_content_generation_queue_creates_background_question -v`, `python -m compileall interview_prep`.

### TUI generate curriculum command

- Закрыт roadmap leaf про TUI `/generate-curriculum`: команда ставит глобальную `curriculum` job через `ContentGenerationService.enqueue_curriculum()` и запускает существующий embedded content worker.
- Стартовый экран, curriculum warning, `/content` screen, side panel и command palette теперь подсказывают `/generate-curriculum`, чтобы bootstrap-only база могла перейти к generated curriculum без выхода в CLI.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_generate_curriculum_command_queues_job_and_starts_worker tests.test_tui.TUITests.test_tui_content_screen_lists_service_jobs tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### Curriculum background job type

- Первый unchecked roadmap item про `/generate-curriculum` оказался слишком крупным для одного безопасного шага, поэтому он разбит в `## Next` на service prerequisite и отдельный TUI slash-command.
- Закрыт prerequisite leaf: `ContentGenerationService` теперь поддерживает job kind `curriculum`, ставит глобальную queued job без topic dependency и обрабатывает ее через существующий idempotent `CurriculumService.generate_and_save()` path.
- Result payload фиксирует counts saved topics/curriculum topics/subtopics/objectives/questions и topic slugs; TUI `/content`/topbar formatter получил человекочитаемый label для completed curriculum jobs.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_content_generation_worker_processes_curriculum_job tests.test_services.ServiceTests.test_content_generation_limits_active_jobs_by_topic_and_kind tests.test_services.ServiceTests.test_curriculum_service_status_reports_counts_and_empty_zones -v`, `python -m unittest tests.test_tui.TUIHelperTests.test_content_artifact_label_formats_curriculum_jobs -v`, `python -m compileall interview_prep`.

### TUI generated curriculum warning

- Закрыт roadmap item про warning при bootstrap-only curriculum: стартовый экран выбора темы теперь показывает заметный `Curriculum warning`, если `CurriculumService.status()` не находит generated curriculum и база работает только на bootstrap/fallback.
- Warning предлагает безопасные существующие команды `python -m interview_prep generate-seed` и `python -m interview_prep curriculum-status`; новых background jobs или TUI-команд в этом шаге не добавлялось.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_warns_when_generated_curriculum_is_missing tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_shows_curriculum_recommended_topic_on_practice_start -v`, `python -m compileall interview_prep`.

### Curriculum status CLI

- Закрыт roadmap item про `curriculum-status`: `CurriculumService.status()` теперь собирает read-only сводку по generated curriculum source с counts app topics, curriculum topics, subtopics, objectives и generated questions.
- CLI-команда `python -m interview_prep curriculum-status` показывает эти counts, per-topic покрытие и пустые зоны: отсутствие generated curriculum, subtopics/objectives/questions или сломанную связь с app topic.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_curriculum_service_status_reports_counts_and_empty_zones tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered tests.test_cli_flow.CLIFlowTests.test_curriculum_status_command_shows_counts_and_empty_zones -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_cli_flow -v`.

### Readiness weekly session trend

- Закрыт roadmap item про недельную динамику readiness по сессиям: `ReadinessService.snapshot()` теперь включает `weekly_trend`, построенный из `session_outcomes.readiness_delta` completed sessions, сгруппированных по неделе `sessions.ended_at`.
- Product decision: trend показывается только при наличии outcome-данных минимум за две разные недели; abandoned sessions не учитываются, schema не менялась.
- TUI `/readiness` и CLI `stats` показывают weekly readiness trend с количеством sessions, average delta и total delta по неделям.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_service_builds_weekly_trend_from_completed_session_outcomes tests.test_services.ServiceTests.test_readiness_service_builds_overall_summary_without_absolute_claim -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_stats_command_shows_weekly_readiness_trend_when_enough_session_outcomes tests.test_cli_flow.CLIFlowTests.test_stats_command_shows_senior_readiness_top_gaps -v`, `python -m unittest tests.test_tui.TUITests.test_tui_readiness_screen_shows_weekly_trend_when_enough_session_outcomes tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions -v`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_web -v`, `python -m compileall interview_prep`.

### Readiness low-rubric recommended drill regression

- Закрыт roadmap item про regression-тест weak topic с низкой rubric оценкой: `ReadinessService` теперь приоритизирует competencies с observed low rubric evidence в `recommended_drill` перед purely missing-evidence gaps.
- Добавлен тест, что свежий слабый ответ по теме databases с низкой rubric evaluation становится первым recommended drill и дает action на перерешивание слабого ответа; TUI fallback action text синхронизирован с service priority.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_recommends_low_rubric_topic_as_first_drill tests.test_services.ServiceTests.test_readiness_service_builds_overall_summary_without_absolute_claim -v`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions -v`, `python -m compileall interview_prep`.

### Read facade readiness dashboard data

- Закрыт roadmap item про readiness data в `/api/dashboard`: read-only facade теперь включает `ReadinessService.snapshot().to_dict()` в dashboard payload под ключом `readiness`.
- `AppServices` передает существующий `ReadinessService` в facade; web adapter продолжает отдавать тот же `/api/dashboard`, но JSON теперь содержит overall summary, recommended drill и per-competency readiness aggregates.
- Проверки: `python -m unittest tests.test_web -v`, `python -m unittest tests.test_services.ServiceTests.test_read_only_facade_exposes_serializable_snapshot_without_writes -v`, `python -m compileall interview_prep`.

### TUI readiness focused screen

- Закрыт roadmap item про `/readiness`: TUI получил focused read-only dashboard по `ReadinessService.snapshot()` со списком competencies, readiness score, evidence count, rubric/self-score aggregates, reasons и next action.
- `/readiness` добавлен в slash-command routing, command palette, стартовую подсказку и mode-aware side panel; `/practice` возвращает в предыдущий workflow.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_readiness_screen_lists_competency_scores_and_actions tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### TUI Today readiness block

- Закрыт roadmap item про стартовый TUI-блок `Today`: экран выбора темы теперь показывает один recommended drill из `ReadinessService.snapshot().overall_summary.recommended_drill`.
- Блок показывает next action, competency, readiness score и причины выбора, чтобы пользователь видел первый evidence-based drill до ручного выбора темы.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_start_screen_shows_today_recommended_readiness_drill -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### CLI senior readiness stats

- Закрыт roadmap item про `stats` CLI readiness block: команда теперь показывает отдельный блок `Senior readiness` с signal, label, summary, caveat и top gaps из `ReadinessService.snapshot()`.
- Top gaps выводятся с competency slug, readiness score, причинами gap и next action, чтобы CLI-статистика сразу давала следующий drill без открытия TUI.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_stats_command_shows_senior_readiness_top_gaps -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_cli_flow -v`.

### Readiness overall summary

- Закрыт roadmap item про overall senior readiness summary: `ReadinessService.snapshot()` теперь включает `overall_summary` с усредненным evidence signal, label, summary, caveat, top gaps и recommended drill.
- Product decision: общий signal считается только как агрегат сохраненных answers/rubric evaluations/recency по competencies и явно помечен caveat "не абсолютная оценка кандидата"; TUI/read facade exposure остается следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_service_aggregates_competency_practice_signals tests.test_services.ServiceTests.test_readiness_service_scores_competencies_with_gap_reasons tests.test_services.ServiceTests.test_readiness_service_builds_overall_summary_without_absolute_claim -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`.

### Readiness competency scoring

- Закрыт roadmap item про readiness score per competency: `ReadinessService` теперь добавляет к каждому competency aggregate `readiness_score` 0-100 и `readiness_reasons`.
- Reasons покрывают мало ответов, низкую rubric оценку, давность практики, отсутствие rubric evaluation, отсутствие linked questions и отдельный gap "нет system design практики" для `system-design`.
- `SQLiteRepository.system_design_practice_metrics()` добавлен как небольшой read-only aggregate по transcript turns, чтобы readiness service не считал system design mock практику через обычные вопросы.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_service_aggregates_competency_practice_signals tests.test_services.ServiceTests.test_readiness_service_scores_competencies_with_gap_reasons -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Readiness service aggregate foundation

- Закрыт roadmap item про foundation `ReadinessService`: добавлен service-layer snapshot по senior competencies с linked/primary questions, answer coverage, answer count, latest rubric score aggregates, self-score average и recency.
- `SQLiteRepository.competency_practice_metrics()` агрегирует только non-abandoned sessions и берет latest rubric evaluation per answer, чтобы будущий readiness score не дублировал re-evaluations.
- `AppServices` получил `services.readiness`; CLI/TUI/read facade пока не менялись, потому что score/recommendation UX вынесены в следующие roadmap items.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_readiness_service_aggregates_competency_practice_signals -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Stats abandoned session filtering

- Закрыт roadmap item про abandoned sessions в stats: `repository.stats()`, topic practice metrics и question practice metrics больше не учитывают abandoned sessions и их answers в основных counters/avg/weak-topic signals.
- Recent session history в stats оставлен полным и теперь включает `status`, чтобы abandoned sessions были видимы как history/audit, но не влияли на readiness counters.
- CLI `stats` показывает статус каждой recent session.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_stats_excludes_abandoned_sessions_but_keeps_recent_history -v`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_cli_flow -v`, `python -m unittest tests.test_web -v`, `python -m compileall interview_prep`.

### CLI session outcome summary

- Закрыт roadmap item про CLI `session-summary <id>`: команда читает сохраненный `SessionOutcome` по session id и показывает summary, strengths, gaps, next drills и `readiness_delta`.
- `SessionService` получил read-only метод `get_session_outcome()`, чтобы CLI не обращался к repository напрямую для нового сценария.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_session_summary_command_shows_saved_session_outcome tests.test_cli_flow.CLIFlowTests.test_content_generation_commands_are_registered -v`, `python -m unittest tests.test_cli_flow -v`, `python -m compileall interview_prep`.

### TUI history session outcome

- Закрыт roadmap item про outcome в `/history <session-id>`: detail view завершенной practice session теперь показывает сохраненный `SessionOutcome` перед блоком answer details.
- Если у legacy/completed session нет outcome row, history остается без ложного итогового блока и продолжает показывать ответы как раньше.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_finish_session_shows_outcome_without_exiting -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`.

### TUI finish-session command

- Закрыт roadmap item про `/finish-session`: команда явно завершает текущую practice session, генерирует/читает `SessionOutcome` и показывает summary/outcome без выхода из TUI.
- Добавлен отдельный TUI state `session_finished`: slash-навигация остается доступной, `/history <session-id>` можно открыть сразу после завершения, `/practice` возвращает на выбор новой practice session, а `/quit` по-прежнему отвечает только за выход.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_finish_session_shows_outcome_without_exiting tests.test_tui.TUITests.test_tui_quit_after_answer_shows_session_outcome tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m unittest tests.test_tui.TUITests.test_tui_slash_commands_update_visible_state -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### TUI session outcome end screen

- Закрыт roadmap item про показ session outcome в TUI: после `/quit` answered practice session завершает session, поднимает сохраненный `SessionOutcome` и показывает summary, strengths, gaps, next drills и `readiness_delta` на ended screen.
- TUI теперь также завершает session по достижении `target_minutes` через topbar timer и показывает тот же outcome; topbar remaining time использует `session.target_minutes`, а не только default 60 минут.
- Empty abandoned sessions по-прежнему не создают outcome и показывают явный empty-state вместо ложной readiness сводки.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_quit_after_answer_shows_session_outcome tests.test_tui.TUITests.test_tui_target_time_completion_shows_session_outcome tests.test_tui.TUITests.test_tui_quit_without_answers_marks_session_abandoned tests.test_tui.TUITests.test_tui_slash_commands_update_visible_state -v`, `python -m unittest tests.test_tui -v`, `python -m compileall interview_prep`.

### Session outcome generation

- Закрыт roadmap item про генерацию session outcome после завершения practice session: `SessionService.finish_session()` теперь для completed sessions с ответами детерминированно upsert-ит `SessionOutcome`.
- Outcome строится без нового LLM-вызова на shutdown path: summary использует количество ответов, среднюю самооценку и средний rubric score; strengths/gaps берутся из self-score и latest rubric evaluations; next drills агрегируются из сохраненных evaluations.
- Product decision: `readiness_delta` пока является небольшим directional signal на основе среднего self-score/rubric относительно нейтральных 3/5; полноценный readiness scoring остается за будущим `ReadinessService`.
- Empty abandoned sessions не получают outcome, чтобы не засорять history/readiness будущими пустыми результатами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_finish_session_generates_session_outcome_from_scores_and_evaluations tests.test_services.ServiceTests.test_finish_abandoned_empty_session_does_not_generate_session_outcome tests.test_services.ServiceTests.test_repository_upserts_and_reads_session_outcome tests.test_services.ServiceTests.test_session_status_tracks_in_progress_completed_and_abandoned_rows -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`.

## 2026-05-19

### Session outcome SQLite storage

- Закрыт roadmap item про SQLite-хранилище session outcomes: схема поднята до версии 6 и добавлена таблица `session_outcomes` с одной записью на session, summary, strengths/gaps/next_drills JSON, `readiness_delta` и `created_at`.
- `SQLiteRepository` получил `upsert_session_outcome()`, `get_session_outcome()` и `get_session_outcome_for_session()` для round-trip domain-модели `SessionOutcome`; FK на `sessions` сохраняет cascade cleanup.
- Генерация outcome после practice session, показ в TUI/history и CLI-просмотр остаются следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_creates_session_outcome_storage tests.test_services.ServiceTests.test_repository_upserts_and_reads_session_outcome -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`.

### Session outcome domain model

- Закрыт roadmap item про domain foundation session outcomes: добавлен immutable `SessionOutcome` с привязкой к session, summary, strengths, gaps, next_drills, readiness_delta и created_at.
- Модель экспортируется из `interview_prep.domain`; storage, генерация outcome и UI/CLI просмотр остаются следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_domain_models -v`, `python -m compileall interview_prep`.

### TUI abandoned empty sessions

- Закрыт roadmap item про выход из TUI без ответов: `finish_session_if_needed()` теперь завершает practice session как `abandoned`, если в SQLite нет сохраненных ответов для этой session.
- `SessionService.finish_session(..., abandon_if_empty=True)` выбирает между `completed` и `abandoned`, а repository получил явный `abandon_session()` и безопасный подсчет ответов по session.
- Сессии с хотя бы одним сохраненным answer по-прежнему завершаются как `completed`; abandoned rows не попадают в completed history.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_session_status_tracks_in_progress_completed_and_abandoned_rows -v`, `python -m unittest tests.test_tui.TUITests.test_tui_quit_without_answers_marks_session_abandoned tests.test_tui.TUITests.test_tui_slash_commands_update_visible_state -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`.

### Session status foundation

- Закрыт roadmap item про базовый статус сессии: domain-модель `Session` теперь хранит `in_progress`, `completed` или `abandoned`, новые sessions создаются как `in_progress`, а `finish_session()` переводит их в `completed`.
- SQLite-схема поднята до версии 5: `sessions.status` добавляется с CHECK/default, legacy rows backfill-ятся из `ended_at`, так что старые завершенные sessions остаются видимыми в history.
- `list_completed_practice_sessions()` теперь опирается на `status='completed'`, поэтому будущие `abandoned` rows можно будет скрыть из completed history без удаления.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_session_status_tracks_in_progress_completed_and_abandoned_rows -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`.

### AI feedback README guidance

- Закрыт roadmap item про README-раздел для AI feedback quality gates: README теперь явно разделяет свободный AI feedback как учебную подсказку и structured rubric evaluation как основной evidence-based сигнал прогресса/readiness.
- Раздел описывает, где видеть rubric scores в TUI/CLI, и напоминает про warning для fallback/suspicious feedback и `/recheck-feedback`.
- Проверки: docs-only change; `python -m compileall interview_prep`.

### Feedback short unknown regression

- Закрыт roadmap item про regression-тест для короткого ответа "не знаю": service-level тест теперь проверяет, что heuristic rubric evaluation оставляет все dimensions на низком score и не использует эталон как evidence.
- Тот же тест фиксирует quality gate для AI feedback: если раздел `Хорошо` хвалит reference-only пункты вроде idempotency/backoff/DLQ/observability при ответе "не знаю", feedback помечается `praise_without_candidate_evidence`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_short_unknown_answer_stays_low_and_reference_only_praise_is_suspicious -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### TUI recheck feedback command

- Закрыт roadmap item про `/recheck-feedback`: TUI теперь повторно запрашивает AI feedback для текущего последнего ответа через более строгий recheck prompt и заменяет сохраненный `answers.ai_feedback`.
- Recheck prompt получает предыдущий feedback как проверяемые claims, требует подтверждать похвалу только evidence из `<candidate_answer>` и явно писать, что подтвержденных сильных сторон нет для коротких/пустых ответов.
- Command palette, подсказки practice review и README обновлены новым slash-command; feedback quality metadata перезаписывается тем же путем, что и обычный `/feedback`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_recheck_feedback_prompt_is_stricter_and_includes_previous_feedback tests.test_services.ServiceTests.test_recheck_feedback_with_quality_uses_strict_prompt -v`, `python -m unittest tests.test_tui.TUITests.test_tui_recheck_feedback_replaces_last_feedback_with_strict_prompt -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`.

### TUI feedback quality warning

- Закрыт roadmap item про предупреждение в TUI для fallback/suspicious AI feedback: practice review теперь читает `feedback_quality` из payload последней structured evaluation и показывает короткий warning перед текстом AI feedback.
- Старый `answers.ai_feedback` не меняется; предупреждение строится только из сохраненной metadata (`fallback`, `suspicious`, flags и optional fallback error).
- Добавлены regression-тесты на форматирование warning для fallback/suspicious payload и на видимое предупреждение при suspicious feedback в daily practice flow.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_feedback_quality_warning_formats_fallback_and_suspicious_payload tests.test_tui.TUITests.test_tui_daily_practice_warns_about_suspicious_feedback tests.test_tui.TUITests.test_tui_daily_practice_shows_ai_feedback_in_center_panel -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### Feedback quality evaluation payload

- Закрыт roadmap item про сохранение `feedback_quality_flags`: при генерации AI feedback приложение теперь записывает flags/evidence/fallback metadata в `raw_payload_json` последней structured `answer_evaluations` для ответа.
- Старый текстовый feedback не меняется: `answers.ai_feedback` остается plain text, а metadata живет отдельно в evaluation payload для будущего TUI warning.
- TUI `/feedback` теперь использует `feedback_with_quality()`, чтобы сохранять quality metadata тем же путем, что и сервисный `add_feedback_to_answer()`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_feedback_quality_flags_are_saved_in_latest_evaluation_payload -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui.TUITests.test_tui_daily_practice_shows_ai_feedback_in_center_panel -v`, `python -m unittest tests.test_tui -v`.

### Feedback quality suspicious guard

- Закрыт roadmap item про service-level guard для AI feedback: `SessionService.feedback_with_quality()` теперь возвращает raw feedback вместе с `FeedbackQuality`.
- Guard парсит раздел `Хорошо` и ставит flag `praise_without_candidate_evidence`, если в нем нет наблюдаемого token/stem evidence из candidate answer; старый `feedback()` и сохраненный `answers.ai_feedback` остаются строкой без изменения.
- Это foundation для следующих шагов: flags пока не сохраняются в evaluation payload и не показываются в TUI.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_feedback_service_marks_good_section_without_candidate_evidence_as_suspicious -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Feedback prompt evidence-only guard

- Закрыт roadmap item про unit-тест `build_feedback_prompt`: prompt теперь явно требует, чтобы похвала и положительные утверждения опирались на evidence из `<candidate_answer>`, а не на `<reference_answer>`.
- Regression-тест фиксирует наличие evidence-only правила и отдельные candidate/reference блоки, чтобы эталон оставался только чеклистом gaps.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_feedback_prompt_requires_evidence_only_rules_and_answer_tags -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Feedback weak answer eval cases

- Закрыт roadmap item про тестовый набор слабых ответов для AI feedback quality gates: добавлены cases для GIL, database indexes и retry/idempotency, где reference-only claims не должны попадать в похвалу кандидату.
- Regression-тест проверяет, что каждый weak answer остается строго внутри `<candidate_answer>`, эталон отдельно в `<reference_answer>`, а reference-only claims отсутствуют в candidate text.
- Это только foundation для следующих шагов quality gate; prompt guard, suspicious flags и TUI warnings пока не менялись.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_feedback_eval_weak_answer_cases_cover_reference_only_claims -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### CLI rubric evaluation viewer

- Закрыт roadmap item про CLI `evaluations --answer <id>`: команда показывает сохраненные structured rubric evaluations для ответа без изменения practice/TUI flow.
- Вывод включает evaluation id, session/question links, source, created_at, summary, средний rubric score, per-dimension scores с evidence/gaps/next drill и общий список next drills.
- `EvaluationService` получил read-only method для списка evaluations по answer id; README обновлен примером команды.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_evaluations_command_shows_saved_rubric_evaluation_for_answer -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_cli_flow -v`, `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_persists_answer_evaluation_without_overwriting_textual_feedback -v`.

### TUI rubric scores review block

- Закрыт roadmap item про отображение rubric scores в TUI review: после ввода self-score active practice screen показывает сохраненную structured evaluation из `answer_evaluations`.
- Новый блок расположен после самооценки и до эталона/свободного AI feedback; он показывает source, summary, средний score, scores по dimensions и первые next drills.
- Regression-тест practice flow теперь проверяет наличие блока и порядок `Твой ответ -> Самооценка -> Rubric scores -> Эталонный ответ`.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_can_answer_one_question_and_save_score -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### Rubric evaluation practice persistence

- Закрыт roadmap item про сохранение structured rubric evaluation в practice flow: после ввода self-score в TUI создается `answer_evaluations` row с per-dimension scores для текущего ответа.
- `SQLiteRepository` получил методы сохранения/чтения answer evaluations и scores; `EvaluationService.evaluate_and_store_answer()` конвертирует structured scoring в persisted `AnswerEvaluation`.
- Старый textual AI feedback остается в `answers.ai_feedback` и не перезаписывается rubric persistence; TUI пока сохраняет deterministic heuristic evaluation, а отображение scores остается следующим roadmap-шагом.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_persists_answer_evaluation_without_overwriting_textual_feedback tests.test_services.ServiceTests.test_evaluation_service_falls_back_when_llm_is_unavailable -v`, `python -m unittest tests.test_tui.TUITests.test_tui_can_answer_one_question_and_save_score -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`, `python -m unittest discover -s tests -v`.

### Rubric evaluation fallback

- Закрыт roadmap item про fallback evaluation: `EvaluationService.evaluate_answer_with_llm()` теперь возвращает deterministic `fallback-heuristic` evaluation, если LLM недоступна или strict JSON не проходит parsing/validation.
- Успешный LLM JSON path не изменился (`source="llm-json"` и raw payload сохраняется для будущего persistence step); обычный heuristic `evaluate_answer()` остался `source="heuristic"`.
- Добавлены regression-тесты для невалидного JSON-ответа и `LLMUnavailable`, чтобы structured rubric scores оставались доступны без Ollama.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_parses_valid_llm_json_rubric_response tests.test_services.ServiceTests.test_evaluation_service_falls_back_when_llm_json_is_invalid tests.test_services.ServiceTests.test_evaluation_service_falls_back_when_llm_is_unavailable tests.test_services.ServiceTests.test_evaluation_service_returns_structured_scores_for_all_rubric_dimensions tests.test_services.ServiceTests.test_evaluation_service_keeps_short_unknown_answer_low_and_evidence_bound -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Rubric LLM JSON prompt

- Закрыт roadmap item про LLM prompt evaluation: добавлен `build_rubric_evaluation_prompt()`, который требует от модели strict JSON без markdown fences, score 1-5 по каждому rubric dimension, evidence только из ответа кандидата, gaps и next drills.
- `EvaluationService` получил `evaluate_answer_with_llm()` и parser валидного JSON-ответа в `StructuredEvaluation` с `source="llm-json"` и сохранением raw payload для будущего persistence step; heuristic `evaluate_answer()` не менялся.
- `AppServices` теперь передает resilient LLM client в `EvaluationService`, но practice/TUI flow, fallback при invalid JSON и сохранение evaluation остаются следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_rubric_evaluation_prompt_requires_json_scores_and_evidence tests.test_services.ServiceTests.test_evaluation_service_parses_valid_llm_json_rubric_response tests.test_services.ServiceTests.test_evaluation_service_returns_structured_scores_for_all_rubric_dimensions tests.test_services.ServiceTests.test_evaluation_service_keeps_short_unknown_answer_low_and_evidence_bound -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Rubric EvaluationService structured scoring

- Закрыт roadmap item про service boundary для rubric evaluation: добавлен `EvaluationService`, который принимает `Question`, `user_answer` и `reference_answer`, читает seeded rubric dimensions и возвращает `StructuredEvaluation` со structured `AnswerEvaluationScore` по каждому измерению.
- Первый scoring backend намеренно deterministic/heuristic и evidence-bound: он не сохраняет данные, не вызывает LLM и не меняет practice/TUI flow; LLM JSON prompt, fallback при invalid JSON и persistence остаются следующими roadmap-шагами.
- `AppServices` получил `services.evaluations`, чтобы последующие шаги могли подключать evaluation без прямого обращения UI к repository.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_evaluation_service_returns_structured_scores_for_all_rubric_dimensions tests.test_services.ServiceTests.test_evaluation_service_keeps_short_unknown_answer_low_and_evidence_bound -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Rubric dimension seed and repository API

- Закрыт roadmap item про idempotent seed базовых rubric dimensions: семь измерений `correctness`, `depth`, `tradeoffs`, `production-realism`, `failure-modes`, `communication`, `evidence` теперь заданы в `infra/seed.py` и upsert-ятся через `SQLiteRepository.seed_defaults()`.
- `SQLiteRepository` получил методы `upsert_rubric_dimension()`, `get_rubric_dimension()`, `find_rubric_dimension_by_slug()` и `list_rubric_dimensions()` с сортировкой по `order_index`, затем `id`.
- Добавлены repository/regression-тесты на идемпотентный seed и чтение/обновление rubric dimensions; evaluation service и LLM JSON scoring остаются следующими roadmap-шагами.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_rubric_dimensions tests.test_services.ServiceTests.test_repository_lists_gets_and_upserts_rubric_dimensions -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Rubric evaluation SQLite storage

- Закрыт roadmap item про storage foundation для rubric evaluations: `CURRENT_SCHEMA_VERSION` поднят до `4`, добавлены таблицы `rubric_dimensions`, `answer_evaluations` и `answer_evaluation_scores`.
- `answer_evaluations` явно хранит связи с `answer_id`, `session_id` и `question_id`, summary/source/raw payload и JSON next drills; per-dimension scores хранят score 1-5, evidence, gaps и optional next drill.
- Repository API и seed базовых rubric dimensions намеренно оставлены следующему roadmap-шагу.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_rubric_evaluation_storage tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Rubric domain models

- Закрыт roadmap item про domain foundation rubric evaluations: добавлены immutable `RubricDimension`, `AnswerEvaluationScore` и `AnswerEvaluation` без подключения storage/UI.
- Модель evaluation уже хранит связи с answer/session/question, набор per-dimension scores, summary, next drills, source, created_at и optional raw JSON payload для будущего repository/LLM шага.
- Проверки: `python -m unittest tests.test_domain_models -v`, `python -m compileall interview_prep`.

### Senior answer rubric dimensions

- Закрыт roadmap item про foundation rubric dimensions: зафиксирован стабильный набор измерений для будущих `RubricDimension`, `AnswerEvaluation` и readiness scoring; схема/UI в этой итерации не менялись.
- Implementation contract: `slug` остается stable identifier, порядок идет с шагом 10, итоговая оценка каждого dimension должна быть 1-5, а положительные утверждения в evaluation должны ссылаться на evidence из ответа кандидата, не из эталона.

| order_index | slug | title | senior evidence focus |
| --- | --- | --- | --- |
| 10 | `correctness` | Correctness | техническая верность ответа, прямое попадание в вопрос и отсутствие критичных ошибок |
| 20 | `depth` | Depth | объяснение причин, механизмов, ограничений и senior-level деталей, а не только поверхностных фактов |
| 30 | `tradeoffs` | Tradeoffs | явные альтернативы, стоимость решений, компромиссы и условия выбора |
| 40 | `production-realism` | Production Realism | применимость в реальном сервисе: эксплуатация, performance, безопасность, данные, миграции и поддержка |
| 50 | `failure-modes` | Failure Modes | edge cases, деградация, retries, идемпотентность, consistency risks и границы отказов |
| 60 | `communication` | Communication | структура ответа, ясные допущения, уточняющие вопросы, приоритизация и понятное объяснение риска |
| 70 | `evidence` | Evidence | оценка основана на наблюдаемом тексте кандидата; нельзя засчитывать пункты, которые есть только в reference answer |

- Проверки: `python -m compileall interview_prep`; код не менялся, поэтому unit-тесты не запускались.

### Read facade competencies snapshot

- Закрыт roadmap item про read-only facade: `dashboard()` теперь включает JSON-safe список senior competencies, а `questions()` по умолчанию добавляет `competencies` с primary/weight metadata для каждого вопроса рядом с уже существующими tags.
- Web adapter не менялся; существующий `/api/dashboard` продолжает идти через тот же read-only facade.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_read_only_facade_exposes_serializable_snapshot_without_writes -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_web -v`.

### TUI question competency display

- Закрыт roadmap item про отображение competencies в TUI practice header: текущий вопрос теперь показывает строку `Компетенции:` до текста вопроса, рядом с уже существующей строкой tags.
- Формат совпадает с CLI: `Title (slug)`, primary competency помечается `[основная]`, а Rich markup в названиях экранируется.
- Добавлен regression-тест TUI flow с primary и secondary competency links.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_practice_question_shows_linked_competencies -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### CLI question competency display

- Закрыт roadmap item про отображение competencies в CLI: `questions` теперь показывает строку `Компетенции:` для каждого вопроса с привязанными senior competencies рядом с tags.
- `QuestionService` получил read method для `question_competencies`, а CLI форматирует primary competency с пометкой `[основная]`.
- Добавлен regression-тест реального CLI flow с явными competency links.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_shows_linked_question_competencies -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_cli_flow -v`.

### Bootstrap question competency seed links

- Закрыт roadmap item про базовые competency links для стартовых вопросов: `SeedQuestion` получил `competency_links`, а все 5 bootstrap/fallback вопросов теперь связаны с primary и secondary senior competencies.
- `SQLiteRepository.seed_defaults()` backfill-ит links для bootstrap-вопросов при первом seed и при повторном запуске на базе с уже существующими вопросами, но не перезаписывает вопросы, у которых links уже есть.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_seed_defaults_links_bootstrap_questions_to_senior_competencies tests.test_services.ServiceTests.test_init_db_creates_question_competency_link_storage tests.test_services.ServiceTests.test_repository_add_question_competency_updates_existing_primary_link -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Question competency repository API

- Закрыт roadmap item про repository API для привязки вопросов к senior competencies: добавлен immutable read model `QuestionCompetencyLink` с `competency`, `is_primary` и `weight`.
- `SQLiteRepository` получил методы `add_question_competency()`, `set_question_competencies()` и `list_question_competencies()`; overwrite-flow дедуплицирует links, сохраняет primary/weight metadata и валидирует единственный primary competency и положительный weight.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_repository_replaces_question_competencies_with_primary_and_weights tests.test_services.ServiceTests.test_repository_add_question_competency_updates_existing_primary_link tests.test_services.ServiceTests.test_repository_rejects_invalid_question_competency_links -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_domain_models -v`, `python -m unittest discover -s tests -v`.

### Question competency link schema

- Закрыт roadmap item про первую связь вопросов с senior competencies: добавлена SQLite-таблица `question_competencies` с FK на `questions`/`competencies`, каскадным удалением и защитой от дублей по `(question_id, competency_id)`.
- Product/schema decision: связь хранит `is_primary` для одного главного competency на вопрос и положительный `weight` для будущего readiness scoring; repository API, seed-привязки и UI оставлены следующими roadmap-шагами.
- `CURRENT_SCHEMA_VERSION` поднят до `3`; migration/index tests проверяют новую таблицу, legacy upgrade и constraint на единственный primary competency вопроса.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_init_db_creates_question_competency_link_storage -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Competency repository API

- Закрыт roadmap item про repository API для senior competencies: добавлены `upsert_competency()`, `get_competency()`, `find_competency_by_slug()` и `list_competencies()`.
- API сохраняет idempotency по `slug`, возвращает domain-модель `Competency` и сортирует список по `order_index`, затем `id`, чтобы будущие readiness/read facade шаги могли опираться на стабильный порядок.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_repository_lists_gets_and_upserts_competencies -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`.

### Competency SQLite seed foundation

- Закрыт roadmap item про storage foundation для senior competencies: добавлена таблица `competencies` с уникальным `slug`, category/level/order и индексом для будущих readiness queries.
- `CURRENT_SCHEMA_VERSION` поднят до `2`; `seed_defaults()` идемпотентно upsert-ит 9 базовых senior competencies из зафиксированной taxonomy без подключения UI.
- Repository list/upsert/get API для competencies намеренно оставлен следующему roadmap-шагу.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema tests.test_services.ServiceTests.test_seed_defaults_adds_idempotent_senior_competencies -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Competency domain model

- Закрыт roadmap item про foundation domain-модели senior competencies: добавлен immutable `Competency` с `slug`, `title`, `description`, `category`, `level` и `order_index`.
- Модель экспортируется из `interview_prep.domain`; storage, seed, repository и UI намеренно оставлены следующим roadmap-шагам.
- Проверки: `python -m unittest tests.test_domain_models -v`, `python -m compileall interview_prep`.

### Senior competency taxonomy

- Закрыт roadmap item про первую senior competency taxonomy: зафиксирован стабильный набор competencies для будущих `Competency` rows, question links, rubric evidence и readiness dashboard; схема/UI в этой итерации не менялись.
- Implementation contract: `slug` остается stable identifier, `category` группирует readiness, `level` для всех стартовых rows = `senior`, `order_index` идет с шагом 10 для будущих вставок.

| order_index | slug | title | category | senior evidence focus |
| --- | --- | --- | --- | --- |
| 10 | `python-runtime` | Python Runtime | `language-runtime` | object model, memory, GIL, GC, imports, packaging, performance tradeoffs |
| 20 | `async-concurrency` | Async and Concurrency | `concurrency` | asyncio lifecycle, cancellation, backpressure, threads/processes, race conditions |
| 30 | `databases` | Databases | `data` | data modeling, indexes, transactions/isolation, migrations, query tuning |
| 40 | `distributed-systems` | Distributed Systems | `architecture` | consistency, messaging, idempotency, retries, partitions, failure boundaries |
| 50 | `system-design` | System Design | `architecture` | requirements, API, data model, scaling, reliability, explicit tradeoffs |
| 60 | `observability` | Observability | `operations` | logs, metrics, traces, SLOs, alerting, production diagnostics |
| 70 | `testing-quality` | Testing and Quality | `quality` | test strategy, CI, code review, maintainability, refactoring discipline |
| 80 | `debugging-incidents` | Debugging and Incidents | `operations` | triage, mitigation, root cause, postmortems, follow-up prevention |
| 90 | `communication-tradeoffs` | Communication and Tradeoffs | `communication` | clarifying constraints, explaining options, communicating risk and scope |

- Проверки: `python -m compileall interview_prep`; код не менялся, поэтому unit-тесты не запускались.

### Ollama default runtime gemma4

- Закрыт roadmap item про миграцию основного локального runtime: `DEFAULT_OLLAMA_MODEL` теперь `gemma4:e4b`, а прямой `OllamaClient()` берет model/base_url/timeout из тех же config-констант.
- Обновлены `config.example.toml`, generated default config text, README и CLAUDE current state; env overrides через `INTERVIEW_PREP_OLLAMA_MODEL` сохранены.
- Добавлен focused regression-тест на default runtime и совпадение `OllamaClient` с config default; fallback behavior проверен через существующий resilient LLM test и `llm-check` на недоступном локальном endpoint.
- Проверки: `python -m unittest tests.test_config tests.test_cli_flow.LLMFallbackTests -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`, `INTERVIEW_PREP_OLLAMA_BASE_URL=http://127.0.0.1:9 INTERVIEW_PREP_OLLAMA_TIMEOUT=0.2 python -m interview_prep --db /tmp/interview_prep_llm_check.db llm-check` (ожидаемый fallback exit 1 при недоступной Ollama).

### Read-only web adapter skeleton

- Закрыт roadmap item про минимальный web smoke/adapter skeleton: добавлен `interview_prep.ui.web.ReadOnlyWebApp`, WSGI-адаптер поверх `ReadOnlyApplicationFacade`.
- Adapter не добавляет новых зависимостей и не заменяет TUI; поддерживает read-only `GET /api/smoke`, `GET /api/dashboard?limit=...`, `/health`/`/api/health`, а unknown/method errors возвращает JSON.
- Добавлен focused regression-тест на smoke/dashboard JSON, read-only отсутствие записей и 404/405 responses.
- Проверки: `python -m unittest tests.test_web -v`, `python -m compileall interview_prep`, `python -m unittest discover -s tests -v`.

### Read-only application facade

- Закрыт roadmap item про foundation для будущего web UI: добавлен `ReadOnlyApplicationFacade` в service layer, который отдает JSON-safe read-модели поверх существующих services.
- Facade подключен к `AppServices` как `services.read` и покрывает dashboard snapshot, topics/questions with tags, completed practice sessions/detail, learning dialogs, notebook entries, generated artifacts и content jobs без write-операций.
- Добавлен regression-тест, который проверяет JSON-сериализацию snapshot/detail/artifacts и отсутствие побочных записей при read-вызовах.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_read_only_facade_exposes_serializable_snapshot_without_writes -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Legacy SQLite upgrade regression

- Закрыт roadmap item про тест обновления старой SQLite-базы: добавлен regression-тест для legacy practice-only схемы без `schema_version` и новых feature-таблиц.
- Тест создает старые `topics`/`questions`/`sessions`/`answers` с существующими данными, дважды запускает `init_db()` и проверяет, что текущие таблицы/версия схемы добавлены без потери истории practice.
- Дополнительно проверено, что после upgrade repository может читать старые completed sessions и использовать новую tag-связь для legacy question.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_upgrades_legacy_practice_database_to_current_schema -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Explicit migration steps

- Закрыт roadmap item про явные idempotent migration steps: `init_db()` теперь применяет именованный список `MIGRATION_STEPS` вместо одного монолитного schema script.
- Создание таблиц сгруппировано по feature-слоям: базовый practice storage, curriculum, question tags, content generation, generated artifacts, learning/notebook и system design; существующий `SCHEMA` оставлен совместимым объединением этих шагов.
- Добавлен focused regression-тест, который проверяет уникальность/идемпотентность migration steps и полный набор таблиц после повторного `init_db()`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version tests.test_services.ServiceTests.test_init_db_runs_explicit_idempotent_migration_steps tests.test_services.ServiceTests.test_init_db_adds_learning_material_archive_column_to_existing_database tests.test_services.ServiceTests.test_init_db_adds_learning_dialog_metadata_columns_to_existing_database tests.test_services.ServiceTests.test_init_db_creates_notebook_entries_storage tests.test_services.ServiceTests.test_init_db_adds_system_design_scenario_archive_column_to_existing_database -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### Schema version foundation

- Закрыт roadmap item про начальную миграционную метаинформацию: `init_db()` теперь создает таблицу `schema_version` и записывает текущую версию схемы `CURRENT_SCHEMA_VERSION = 1`.
- Запись версии хранится как single-row metadata (`id = 1`) и повторный `init_db()` не создает дублей; будущая версия не будет случайно понижена текущим кодом.
- Добавлен focused regression-тест на создание таблицы, текущую версию и идемпотентный повторный запуск `init_db()`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_schema_version_table_with_current_version -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest discover -s tests -v`.

### CLI question tag filter

- Закрыт roadmap item про фильтр вопросов по тегу: `questions --tag <slug>` теперь выводит только вопросы с указанным тегом и может сочетаться с `--topic`.
- `SQLiteRepository.list_questions()` и `QuestionService.list_questions()` получили optional `tag_slug` filter поверх существующей связи `question_tags`.
- Добавлены regression-тесты repository и реального CLI flow; README обновлен примером `python -m interview_prep questions --tag concurrency`.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_repository_filters_questions_by_tag_slug -v`, `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_filters_by_tag_slug -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_cli_flow -v`, `python -m unittest discover -s tests -v`.

### TUI question tag display

- Закрыт TUI-slice roadmap item про отображение тегов вопроса: practice screen теперь показывает привязанные теги текущего вопроса сразу под заголовком вопроса.
- Добавлен helper форматирования тегов для TUI с экранированием Rich markup, чтобы user-defined titles/slugs не ломали разметку.
- Добавлен regression-тест TUI flow: тест привязывает два тега к bootstrap-вопросу, стартует practice по теме и проверяет строку `Теги: Title (slug)` перед текстом вопроса.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_practice_question_shows_linked_tags -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### CLI question tag display

- Roadmap item про CLI/TUI отображение тегов разбит на маленькие leaf-шаги; в этой итерации закрыт только CLI slice.
- `QuestionService` получил read method для тегов вопроса, а команда `questions` теперь показывает привязанные теги рядом с вопросом в формате `Title (slug)`.
- Добавлен regression-тест реального CLI flow: тест готовит `tags`/`question_tags` в SQLite, запускает `python -m interview_prep questions` и проверяет отображение тегов.
- Проверки: `python -m unittest tests.test_cli_flow.CLIFlowTests.test_questions_command_shows_linked_question_tags -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_cli_flow -v`.

### Notebook regression coverage

- Добавлен TUI regression-тест, который проходит реальный learning flow, сохраняет AI explanation в `notebook_entries`, затем открывает `/notebook topic <id>` и проверяет topic-фильтрацию.
- Тест дополнительно фиксирует, что записи другой темы не попадают в topic-filtered notebook view.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_learning_explanation_is_visible_in_topic_notebook -v`, `python -m unittest tests.test_tui.TUITests.test_tui_learning_mode_persists_dialog_through_service tests.test_tui.TUITests.test_tui_learning_explanation_is_visible_in_topic_notebook tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic tests.test_services.ServiceTests.test_learning_service_saves_user_and_assistant_messages tests.test_services.ServiceTests.test_repository_persists_notebook_entries_with_context_links -v`, `python -m compileall interview_prep`.

### TUI notebook naming

- `/notebook` теперь в TUI явно подписан как `Конспект обучения`: action-кнопка, focused notebook screen, правая панель, history links и command palette используют этот user-facing label.
- Экран notebook дополнительно показывает заголовки `Разбивка по темам` и `Разбивка по subtopics`, чтобы было понятно, где искать сохраненные AI explanations по topic/subtopic.
- Regression-тесты обновлены для проверки нового label в кнопке, notebook screen, правой панели, history learning detail и command palette.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_notebook_action_opens_current_topic_entries tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions tests.test_tui.TUIHelperTests.test_command_palette_text_lists_core_commands -v`, `python -m compileall interview_prep`.

### TUI notebook discovery from materials

- `/materials` теперь явно показывает переходы в конспект обучения: для текущей темы в заголовке/правой панели и для темы каждого listed material/scenario в строке artifact.
- Переход использует существующую команду `/notebook topic <id>`, поэтому из `/materials all` можно открыть notebook entries темы выбранного artifact без ручного поиска topic id.
- Добавлен regression-тест для flow `/materials` -> `/materials all` -> `/notebook topic <id>` с проверкой фильтрации notebook entries по теме artifact.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_materials_screen_links_to_notebook_topic_entries -v`, `python -m unittest tests.test_tui.TUITests.test_tui_materials_screen_lists_and_opens_saved_artifacts -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions tests.test_tui.TUITests.test_tui_notebook_action_opens_current_topic_entries -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### TUI notebook discovery from history

- History learning list/detail теперь явно показывает переход `Notebook: /notebook topic <id>` для темы сохраненного learning dialog.
- Правая панель history добавляет `/notebook topic <id>` в список команд, чтобы переход в конспект обучения был виден без знания глобальной команды.
- Regression-тест history browser теперь проверяет путь из read-only learning dialog в `/notebook topic <id>` и фильтрацию notebook entries по этой теме.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

## 2026-05-14

### TUI notebook discovery from topic screen

- Roadmap item про notebook discovery разбит на маленькие leaf-шаги для стартового/topic экрана, history и materials; в этой итерации закрыт только стартовый/topic slice.
- В верхнюю TUI-панель действий добавлена кнопка `Notebook`; если practice topic уже выбран, она открывает `/notebook topic <id>`, иначе показывает все notebook entries.
- Стартовый экран выбора темы теперь явно подсказывает, что конспект обучения доступен через кнопку `Notebook` или `/notebook`.
- Добавлен regression-тест клика по `Notebook`: после выбора topic открываются только notebook entries текущей темы.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_notebook_action_opens_current_topic_entries tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_tui -v`.

### TUI pre-topic learning regression coverage

- Добавлен regression-тест, что `/learn` до выбора topic открывает topicless learning-сессию и не загружает сохраненный topic-bound диалог из прошлой сессии.
- Тест также фиксирует, что для topicless learning не подхватывается saved learning material и не ставится topic-bound generation job.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_learning_before_topic_selection_does_not_load_saved_topic_dialog tests.test_tui.TUITests.test_tui_learning_mode_loads_saved_dialog_on_enter -v`.

### TUI free learning before topic selection

- `/learn` до выбора practice topic теперь открывает новую topicless learning-сессию: экран не поднимает сохраненные topic-bound реплики и не показывает stale learning material прошлой темы.
- Учебный вопрос в таком режиме отправляется в `LearningService.explain()` без topic/question context и ведется только в текущем in-memory transcript; сохранение в `learning_dialog_messages`/`notebook_entries` остается topic-bound до явного выбора темы.
- Для topic-bound learning сохранено прежнее восстановление последних сохраненных реплик и автоподхват/очередь learning material.
- Проверки: focused inline TUI check для pre-topic free learning, `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows tests.test_tui.TUITests.test_tui_clicking_mode_actions_before_topic_does_not_stick_in_learning tests.test_tui.TUITests.test_tui_slash_mode_actions_before_topic_do_not_stack_focused_modes tests.test_tui.TUITests.test_tui_learning_mode_loads_saved_dialog_on_enter tests.test_tui.TUITests.test_tui_learning_mode_does_not_save_interview_answer -v`, `python -m unittest tests.test_tui.TUITests.test_tui_auto_queues_learning_material_when_entering_learning_mode tests.test_tui.TUITests.test_tui_reuses_saved_learning_material_without_queueing_job -v`, `python -m compileall interview_prep`.

### TUI mode switching fix

- Исправлено переключение основных TUI-режимов `learn`/`system-design`/`practice`: перед входом в другой focused mode приложение разворачивает текущий focused mode до practice-context, поэтому `Learn -> System Design -> Practice` больше не возвращает пользователя обратно в learning.
- Та же логика подключена к slash-командам `/learn`, `/system-design`, `/sd` и `/practice`; во время `loading_*` смена режима блокируется тем же сообщением ожидания ИИ.
- Expected-failure regression по pre-topic кликам переведен в обычный passing test, добавлен отдельный regression-тест для slash-команд.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_before_topic_does_not_stick_in_learning -v`, `python -m unittest tests.test_tui.TUITests.test_tui_slash_mode_actions_before_topic_do_not_stack_focused_modes -v`, `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows -v`, `python -m unittest tests.test_tui -v`, `python -m compileall interview_prep`.

### TUI pre-topic mode action regression

- Добавлен expected-failure regression-тест для pre-topic кликов `Learn -> System Design -> Practice`.
- Тест фиксирует текущий sticky focused-mode путь: после возврата из system design приложение остается в `learning`, вместо выхода из focused mode к practice/select-topic flow.
- Исправление самого переключения оставлено следующим roadmap-шагом.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_before_topic_does_not_stick_in_learning -v`, `python -m unittest tests.test_tui.TUITests.test_tui_clicking_mode_actions_switches_main_workflows -v`.

## 2026-05-13

### Notebook TUI screen

- Добавлен focused read-only TUI-экран `/notebook` для просмотра сохраненных AI explanations из `notebook_entries`.
- Экран поддерживает навигацию и фильтры `/notebook all`, `/notebook topic <id>`, `/notebook subtopic <id>` и открытие полной записи через `/notebook entry <id>`.
- Правая панель notebook показывает следующий шаг, счетчики entries/topics/subtopics, текущий фильтр, команды и последние события; command palette и README обновлены новыми командами.
- `SQLiteRepository` получил lookup `get_curriculum_subtopic()` для user-visible labels без прямого SQL в UI.
- Проверки: `python -m unittest tests.test_tui.TUITests.test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic -v`, `python -m unittest tests.test_services.ServiceTests.test_repository_persists_notebook_entries_with_context_links -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`.

### Notebook autosave from learning mode

- `LearningService` получил helper для сохранения AI learning replies в `notebook_entries` с source `learning-ai`, заголовком из вопроса пользователя и привязкой к `dialog_session_id`/source learning message.
- TUI learning flow теперь после сохранения assistant-реплики автоматически создает notebook entry без ручного копирования и без записи learning-сообщений как interview answers.
- Regression-покрытие проверяет service-level `explain_and_save` и реальный TUI learning flow: assistant reply сохраняется в dialog и linked notebook entry.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_learning_service_saves_user_and_assistant_messages -v`, `python -m unittest tests.test_tui.TUITests.test_tui_learning_mode_persists_dialog_through_service -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`.

### Notebook storage foundation

- Добавлена immutable domain-модель `NotebookEntry` для AI explanation notes с привязками к `topic_id`, optional `curriculum_subtopic_id`, `dialog_session_id` и source learning dialog message.
- SQLite-схема получила таблицу `notebook_entries` и индексы для чтения тетради по topic/subtopic/session/source message без физического удаления или изменения learning dialog flow.
- `SQLiteRepository` теперь умеет сохранять notebook entries и читать их с фильтрами по topic, subtopic, dialog session и source message.
- Проверки: `python -m unittest tests.test_domain_models -v`, `python -m unittest tests.test_services.ServiceTests.test_init_db_creates_notebook_entries_storage tests.test_services.ServiceTests.test_repository_persists_notebook_entries_with_context_links -v`, `python -m unittest tests.test_services -v`, `python -m compileall interview_prep`.

### Learning dialog session/context metadata

- `learning_dialog_messages` получили metadata `dialog_session_id`, `context_type` и `context_id`; `init_db()` добавляет эти колонки к существующим SQLite-базам без пересоздания таблицы.
- TUI создает отдельный `learn-...` id при входе в `/learn`, сохраняет новые учебные реплики с привязкой к текущей practice session и показывает history summaries по dialog session, чтобы несколько учебных сессий одной темы в один день не сливались.
- Старый history path `/history learning <topic-id> <YYYY-MM-DD>` оставлен как legacy-группировка по дате; новый path `/history learning <session-id>` открывает конкретный learning dialog.
- Проверки: `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`, `python -m compileall interview_prep`.

### Learning dialog history detail view

- `/history learning <topic-id> <YYYY-MM-DD>` теперь открывает выбранную группу сохраненного learning dialog в read-only режиме и показывает сохраненные реплики пользователя/ИИ через общий chat renderer.
- Добавлен service/repository read path для сообщений learning dialog по `(topic_id, date(created_at))` без изменения SQLite-схемы; список `/history learning` теперь показывает команду открытия для каждой группы.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_learning_service_lists_dialog_messages_for_selected_date -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`.

### Learning dialog history list

- Первый шаг history browser для learning dialogs: `/history learning` показывает read-only список сохраненных учебных диалогов, сгруппированных по topic/date на основе существующих `learning_dialog_messages.created_at`.
- Добавлен read model `LearningDialogSummary` и service/repository методы без изменения SQLite-схемы; session/context metadata оставлена следующим roadmap-шагом.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_learning_service_lists_dialog_summaries_by_topic_and_date -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`.

### Practice history browser detail view

- `/history <session-id>` теперь открывает завершенную practice session в read-only режиме и показывает вопрос, ответ пользователя, self-score, эталонный ответ и AI feedback.
- Detail view построен через service/repository read model `PracticeSessionDetail` без изменения SQLite-схемы и без подключения к active practice state.
- Экран `/history` по-прежнему показывает список sessions; повторная команда `/history` возвращает из деталей к списку, `/practice` возвращает в practice flow.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_session_service_returns_completed_practice_session_detail -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`.

### Practice history browser list

- Добавлен read-only TUI-экран `/history` со списком завершенных practice sessions: session id, topic, started/ended date, количество ответов и средняя self-score.
- Список построен через service/repository read model `PracticeSessionSummary`; незавершенные sessions не попадают в history browser.
- Детальный просмотр конкретной session оставлен следующим roadmap-шагом.
- Проверки: `python -m unittest tests.test_services.ServiceTests.test_session_service_lists_completed_practice_sessions -v`, `python -m unittest tests.test_tui.TUITests.test_tui_history_browser_lists_completed_practice_sessions -v`, `python -m compileall interview_prep`, `python -m unittest tests.test_services -v`, `python -m unittest tests.test_tui -v`, `python -m unittest discover -s tests -v`.

### TUI clickable mode actions regression

- Добавлен regression-тест кликабельных TUI-действий `Practice`, `Learn` и `System Design`.
- Проверка фиксирует переходы через UI-кнопки: вход в learning, возврат к выбору practice, старт practice по клику, вход в system design и возврат к исходной practice-сессии.
- Проверки: `python -m unittest tests.test_tui -v`.

### TUI clickable mode actions

- Добавлена постоянная TUI-панель действий с кнопками `Practice`, `Learn` и `System Design`, чтобы основные режимы можно было открыть кликом без ввода slash commands.
- Кнопки используют существующие mode flows: learning и system design открывают прежние режимы, а practice возвращает из special modes или стартует рекомендованную practice-сессию со стартового экрана.
- Slash commands сохранены как быстрый keyboard fallback без изменения текущего composer flow.
- Проверки: `python -m unittest tests.test_tui -v`, `python -m compileall interview_prep`.

### TUI clickable practice topic regression

- Добавлен focused regression-тест, который кликает первую доступную строку topic в левой `OptionList` на стартовом экране practice.
- Проверка фиксирует полный user-visible flow: mouse click запускает topic session, переводит TUI в `answering`, выставляет `app.topic` и связывает session с выбранной темой.
- В тесте отключена фоновая генерация через quiet fake, чтобы покрытие проверяло только navigation behavior.

### TUI clickable practice topic selection

- Левая панель тем в TUI переведена с пассивной Rich-таблицы на Textual `OptionList`, где строки topic доступны для mouse/keyboard selection на стартовом экране practice.
- Выбор topic кликом идет через существующий `start_session_from_input()` flow, поэтому сохраняет текущий запуск сессии, recommendation fallback и автогенерацию question backlog.
- На экране выбора темы текст подсказки обновлен: topic можно выбрать кликом, а ручной ввод ID и `/accept-topic` остаются keyboard fallback.

### Question tag repository foundation

- Добавлена immutable domain-модель `Tag` для reusable меток вопросов.
- SQLite-схема получила таблицы `tags` и `question_tags` с many-to-many связью вопроса и тега без изменения существующего UI.
- `SQLiteRepository` теперь умеет upsert/list tags, привязывать тег к вопросу, заменять набор тегов вопроса и читать теги конкретного вопроса.
- Добавлены focused regression-тесты на immutable tag model, idempotent attach и замену тегов без дублей.

### TUI composer multiline regression coverage

- Расширены TUI regression-тесты многострочного composer: существующее practice-покрытие дополнено learning и system design flows.
- Новые проверки фиксируют, что Shift+Enter вставляет newline, обычный Enter отправляет весь draft, а code block не обрезается при передаче в learning prompt/system design transcript.
- Для focused тестов добавлен quiet content-generation fake с no-op `ensure_learning_material`, `ensure_system_design_scenario` и `list_jobs`, чтобы проверки не зависели от фоновой очереди.

### TUI composer fast command/topic flow

- Добавлена focused TUI-регрессионная проверка, что многострочный `Composer` сохраняет быстрый keyboard flow для slash commands и выбора темы.
- Проверка фиксирует поведение Enter: `/commands` с пробелами по краям выполняется как команда, composer очищается без вставки newline и остается compact, затем topic id с пробелами по краям стартует practice из того же input flow.

### TUI composer long draft visibility

- `Composer` теперь динамически растет по числу строк draft от compact height до ограниченного максимума, чтобы перед отправкой были видны многострочные ответы и code snippets.
- Очень длинные draft остаются в capped `TextArea`, где сохраняется встроенный scroll/edit flow без изменения Enter submit и Shift+Enter newline.
- Добавлена focused TUI-регрессионная проверка на расширение composer, max-height cap и возврат к compact height после очистки draft.

### TUI composer Shift+Enter newline

- `Composer` теперь различает `Enter` и `Shift+Enter`: обычный Enter отправляет текущий draft через прежний submit-flow, а Shift+Enter вставляет `\n` внутри TextArea без отправки.
- Многострочные ответы сохраняют перенос строки и отправляются следующим обычным Enter.
- Добавлена focused TUI-регрессионная проверка на Shift+Enter/newline перед отправкой practice answer.

### TUI multiline composer foundation

- Нижний однострочный `Input` заменен на `Composer` поверх Textual `TextArea`, чтобы practice, learning и system design режимы могли держать многострочный draft.
- Composer сохраняет прежний быстрый submit-flow: Enter отправляет текущий текст через тот же обработчик, очищает draft и не ломает slash commands/выбор темы.
- Все TUI-тесты переведены на `#input_bar` TextArea composer; добавлена regression-проверка, что многострочный practice answer с code fence сохраняется полностью.
- Отдельная scrollable/resizable область длинного draft оставлена следующим roadmap-шагом.

### TUI markdown chat regression tests

- Добавлены regression-тесты на AI-authored markdown в `render_chat_message()` для ролей `ИИ`, `Интервьюер`, `Эталонный ответ` и `AI feedback`.
- Тесты проверяют, что headings, bullet lists и fenced code blocks проходят через Rich Markdown renderer до embedding в chat window и не остаются сырым markdown (`#`, `-`, code fence markers).
- Усилен helper-тест `render_llm_markdown()` проверкой, что bullet syntax не печатается как raw markdown.

### TUI LLM markdown rendering

- Добавлен helper `render_llm_markdown()` поверх Rich `Markdown`, который преобразует LLM-authored markdown в отображаемый текст и затем безопасно встраивается в текущие TUI markup-строки.
- `render_chat_message()` теперь рендерит markdown для AI-authored ролей: `ИИ`, `Интервьюер`, `Эталонный ответ` и `AI feedback`, сохраняя escaping пользовательских сообщений.
- Markdown rendering подключен к подготовленным learning materials, system design scenario text и preview bodies для learning materials/system design scenarios.
- Добавлена focused helper-проверка, что headings/lists/code fences проходят через Rich Markdown output и code fences не остаются сырым markdown.

### Daily practice chat renderer rollout

- `question_text()` теперь использует единый `render_chat_message()` для блоков `Твой ответ`, `Эталонный ответ` и `AI feedback` в daily practice review/scoring экранах.
- Пользовательский ответ, эталон и feedback получают одинаковый visual separator/role header и escaping Rich markup, поэтому текст вроде `[bold]...[/bold]` больше не интерпретируется как оформление в review-блоках.
- Добавлен focused regression-тест на порядок блоков и escaping Rich markup для ответа, эталона и AI feedback.

### System design chat renderer rollout

- `system_design_text()` теперь использует единый `render_chat_message()` для transcript mock interview, pending-сообщения кандидата и блока `Feedback / следующий вопрос`.
- Итоговый `/sd-feedback` показывается как AI chat-блок с role header/separator и escaping Rich markup, а pending system design ответ больше не дублируется сырым `last_feedback`.
- Добавлен focused regression-тест на system design transcript, pending message и final feedback с Rich markup-like текстом.

### Learning mode chat renderer rollout

- `learning_text()` теперь использует единый `render_chat_message()` для загруженных сохраненных реплик, pending-сообщения пользователя и новых ответов ИИ, которые добавляются в learning transcript после генерации.
- Пользовательский и AI-текст в learning dialog теперь получает одинаковые role headers, separator и escaping Rich markup вместо ручных `[bold]Ты[/bold]`/`[bold]ИИ[/bold]` блоков.
- Добавлен focused regression-тест на learning-mode rendering saved dialog, pending message и assistant reply с Rich markup-like текстом.

### Codex roadmap loop output

- `scripts/codex_roadmap_loop.sh` больше не печатает весь raw transcript Codex в терминал в обычном режиме.
- Добавлен `CODEX_LOOP_OUTPUT=summary|quiet|full`: default `summary` показывает только обрезанную финальную сводку, `quiet` оставляет только статусы итераций, `full` возвращает прежний подробный вывод для debugging.
- Добавлены лимиты `CODEX_LOOP_SUMMARY_MAX_LINES`, `CODEX_LOOP_SUMMARY_MAX_CHARS` и `CODEX_LOOP_ERROR_TAIL_LINES`; при ошибке скрипт печатает только хвост raw output, если не включен `full`.
- README для loop-скрипта обновлен новыми режимами вывода.

### TUI chat message renderer

- Добавлен единый helper `render_chat_message()` для chat-реплик с явным role header, вертикальным spacing и визуальным separator.
- Renderer экранирует Rich markup в тексте сообщения, чтобы пользовательский ввод вроде `[bold]...[/bold]` не интерпретировался как оформление.
- Mode-specific подключение renderer к learning/system design/daily practice оставлено следующими отдельными roadmap-шагами, чтобы rollout был пошаговым и проверяемым.
- Добавлен focused regression-тест на escaping пользовательского Rich markup и сохранение code fence как обычного текста.

### Practice weak-question spaced repetition

- `SessionService.candidate_questions()` теперь учитывает question-level practice metrics и поднимает слабые вопросы после repeat-интервала.
- Выбранное правило: вопрос считается due для повторения, если последний `self_score <= 3` и с последнего ответа прошло не меньше 7 дней; недавние слабые ответы не вытесняют обычный порядок.
- Для mixed sessions сохранен приоритет weak topics, а внутри topic rank due weak questions идут первыми.
- Добавлен regression-тест, что topic session сначала выдает старый слабый вопрос, но не поднимает недавний слабый вопрос до истечения интервала.

### Practice weak-topic question selection

- `SessionService.candidate_questions()` добавляет общий service-level порядок вопросов для practice.
- Для сессий без выбранной темы вопросы теперь сортируются по ranking из `StatsService.weak_topics()`, поэтому слабые темы получают приоритет перед обычным fallback-порядком `topic/difficulty/id`.
- TUI `next_available_question()` использует тот же service-level порядок и поверх него применяет локальные answered/skipped фильтры.
- Добавлен regression-тест, что mixed session сначала выдает вопрос из темы с низкой самооценкой.

### Stats weak topics service method

- `StatsService.weak_topics()` добавляет reusable service-level ranking слабых тем без изменения SQLite-схемы.
- Выбранное правило ранжирования учитывает низкую среднюю самооценку, недостаточное количество ответов относительно минимального порога и давность последнего ответа; результат содержит score и причины для будущего practice selection.
- `dashboard()` теперь использует тот же enriched weak topics список для `suggested_topic`, сохраняя совместимые поля `title`, `answers` и `avg_score`.
- Добавлен regression-тест, что self-score, давность и малое количество ответов влияют на порядок слабых тем.

### TUI accept recommended topic command

- Добавлена slash-команда `/accept-topic` на стартовом экране выбора темы: она принимает текущую recommendation из curriculum/statistics flow и сразу начинает practice без ручного ввода ID.
- Команда безопасно сообщает, если вызвана вне выбора темы или если recommendation недоступна.
- Command palette, стартовый экран и README обновлены новой командой; добавлена TUI-регрессионная проверка запуска рекомендованной темы через `/accept-topic`.

### TUI curriculum next topic recommendation

- Стартовый экран practice теперь показывает предложенную следующую тему из `CurriculumService.suggest_next_topic()` вместе с причиной, количеством ответов и доступными метриками self-score/last answered.
- Enter на выборе темы и `*`-маркер в левой панели теперь используют ту же curriculum recommendation, с fallback на прежнюю stats-рекомендацию при недоступности curriculum service.
- Добавлена TUI-регрессионная проверка, что старт practice показывает curriculum recommendation и Enter начинает именно рекомендованную тему.

### Curriculum next topic recommendation service

- `CurriculumService.suggest_next_topic()` теперь выбирает следующую тему для practice из generated curriculum order.
- Выбранное правило: сначала предлагается первая еще не отвеченная тема по curriculum order, затем слабая тема с `self_score <= 3`, затем самая давно отвеченная тема.
- `SQLiteRepository.topic_practice_metrics()` добавляет service-level данные по topic: количество ответов, средний self-score и последний `answered_at`.
- Добавлены regression-тесты на выбор первой новой темы, слабой темы перед старой сильной и самой давно отвеченной темы при сильных score.

### Curriculum generated structure idempotency

- Generated curriculum topics теперь переиспользуются по паре `slug`/`source`: повторный `generate-seed` обновляет metadata existing row вместо вставки дубля.
- Generated subtopics переиспользуются внутри persisted curriculum topic по `slug`/`source`, а objectives — по scope/text/source, чтобы повторный импорт не раздувал дерево curriculum.
- `CurriculumService.generate_and_save()` теперь считает `curriculum_topics_saved`, `subtopics_saved` и `objectives_saved` только для новых строк, сохраняя прежний upsert topics/questions flow.
- Добавлен regression-тест, что повторный `generate-seed` оставляет один curriculum topic, одну subtopic и четыре objectives для одного generated seed.

### Curriculum generate-seed structure persistence

- `generate-seed` теперь просит LLM возвращать `subtopics` с objectives и парсит их в generated curriculum model.
- `CurriculumService.generate_and_save()` сохраняет generated curriculum topics, topic-level objectives, subtopics и subtopic-level objectives через существующие repository-методы вместе с прежним upsert topics/questions.
- CLI output `generate-seed` показывает счетчики сохраненных curriculum topics/subtopics/objectives и печатает subtopics в preview.
- Добавлен service-level regression-тест на сохранение generated curriculum structure из seed.

### Curriculum repository persistence

- Добавлены SQLite-таблицы `curriculum_topics`, `curriculum_subtopics` и `curriculum_objectives` для сохранения generated curriculum structure поверх существующих `topics`.
- `SQLiteRepository` получил методы добавления и ordered-чтения curriculum topics, subtopics и objectives с фильтрацией curriculum topics по `source`/`topic_id`.
- Добавлен repository-level regression-тест на сохранение topic-level и subtopic-level learning objectives без подключения `generate-seed`.

### Curriculum domain models

- Добавлены immutable domain-модели `CurriculumTopic`, `CurriculumSubtopic` и `CurriculumObjective` как foundation для полноценной curriculum structure поверх существующих topics/questions.
- Модели описывают связь generated curriculum topic с существующей темой, порядок элементов, source и objectives на уровне topic/subtopic без изменения SQLite-схемы и UI.
- Добавлен domain-level regression-тест на структуру и immutability моделей.

### Content generation reference answer regeneration

- Добавлен новый background job kind `reference-answer`: он проходит по существующим вопросам выбранной темы и регенерирует только `reference_answer`, не меняя prompt, hint, difficulty и source.
- CLI `content-enqueue --kind reference-answer --topic <id>` теперь ставит такую задачу в общую SQLite-очередь с теми же active job limits, retry/backoff metadata и worker flow.
- TUI `/content` показывает новый kind как обычную job, topbar умеет показать последний результат `answers:<count>`, а текущий вопрос в TUI обновляет эталонный ответ после завершения job.
- Добавлены regression-тесты на service-level обновление эталонных ответов и CLI enqueue нового kind.

### TUI content worker pause/resume

- `/content` получил TUI-local команды `/pause-content` и `/resume-content` для управления embedded background worker без удаления queued jobs из SQLite.
- Когда worker на паузе, автоматические ensure/retry flow могут оставлять jobs в `queued`, но TUI не запускает обработку до resume.
- Экран `/content`, правая панель, placeholder, topbar status и command palette показывают состояние worker и новые команды.
- Добавлена TUI-регрессионная проверка, что pause не переводит queued job в running/done и resume снимает флаг.

### TUI content job retry

- `/content` получил TUI-команду `/retry-job <id>` для безопасного retry failed background job без выхода в CLI.
- Команда работает только с failed jobs, возвращает задачу в `queued`, показывает результат в history/queue snapshot и запускает background worker.
- Manual retry теперь очищает stale `retry.next_attempt_at` и `retry.last_error` в payload, чтобы повторная попытка не зависала за старым backoff.
- README/CLAUDE/ROADMAP обновлены новым workflow, добавлены service-level и TUI regression-тесты.

### TUI content jobs screen

- Добавлен read-only TUI service screen `/content` для диагностики очереди фоновой генерации.
- Центральная область показывает отдельные списки `queued`, `running` и `failed` jobs с id, kind, status, темой, created/updated timestamps, note, retry/backoff metadata и error.
- Правая mode-specific панель для `/content` показывает следующее действие, счетчики очереди, topbar snapshot и последние события.
- Retry failed job, pause/resume worker и новые job types были оставлены следующими отдельными roadmap-шагами.
- Добавлена TUI-регрессионная проверка списка jobs и command palette.

### TUI content generation compact status

- Верхняя строка TUI теперь показывает не только локальное состояние worker, но и компактный snapshot очереди: queued/running/failed counts.
- TUI также показывает последний `done` или `failed` generation job с id, kind и id созданного artifact/question, если он есть в `result_json`.
- Статус строится через существующий `ContentGenerationService.list_jobs()` без изменения SQLite-схемы и без новых CLI-команд.
- README/CLAUDE обновлены описанием нового status surface.
- Добавлена TUI-регрессионная проверка для queue counts и последнего generation result.

### Content generation worker backoff selection

- `process_next_job()` теперь выбирает первый queued job, у которого отсутствует `retry.next_attempt_at` или backoff уже истек.
- Если самый старый queued job еще находится в backoff, worker не блокирует очередь и берет следующий готовый queued job.
- Добавлен repository-метод чтения queued jobs в FIFO-порядке без изменения SQLite-схемы.
- Добавлен regression-тест на сценарий: старый delayed job остается queued, новый ready job выполняется, delayed job выполняется после истечения backoff.

### Content generation retry/backoff metadata

- Новые `content_generation_jobs` теперь получают retry-блок внутри `payload_json`, без изменения SQLite-схемы: `attempt`, `max_attempts`, `backoff_seconds`, `next_attempt_at`, `last_error`.
- При failed processing сервис увеличивает `attempt`, записывает последний error и рассчитывает следующий backoff timestamp в payload.
- `retry_job()` backfill-ит retry metadata для старых payload, если ее еще нет, и сохраняет существующую проверку active job limit.
- Добавлены service-level regression-тесты на payload новых jobs, failed metadata и совместимость retry flow.

### Content generation active job limits

- `ContentGenerationService` теперь ограничивает количество active jobs (`queued`/`running`) по паре topic/kind: по умолчанию не больше одной активной задачи.
- Ограничение применяется на общем `enqueue()` пути, поэтому его используют CLI, TUI ручная регенерация и автоматические TUI ensure-сценарии.
- `retry_job()` также проверяет лимит перед возвратом failed job в `queued`, чтобы retry не создавал второй active job для той же topic/kind.
- Добавлены service-level regression-тесты на queued/running лимит, разрешение других kind/topic и блокировку retry при существующей active job.

## 2026-05-12

### TUI materials system design scenario archive

- `system_design_scenarios` получил soft-archive поле `archived_at`; `init_db()` добавляет колонку в уже существующую SQLite-базу без destructive migration.
- Repository скрывает archived system design scenarios из `list/latest/get` по умолчанию, но оставляет чтение строки через `include_archived=True`.
- `/materials` получил команду `/archive-scenario <id> confirm`: без явного `confirm` команда показывает безопасный usage, а после архивации scenario исчезает из списков и latest.
- Обновлены README/CLAUDE и добавлены regression-тесты на repository archive и TUI protected archive flow.

### TUI materials learning material archive

- Первый пункт про archive/delete generated artifacts разбит на безопасные leaf-задачи: отдельно learning materials и system design scenarios.
- `learning_materials` получил soft-archive поле `archived_at`; `init_db()` добавляет колонку в уже существующую SQLite-базу без отдельного destructive migration.
- Repository скрывает archived learning materials из `list/latest/get` по умолчанию, но оставляет возможность прочитать строку через `include_archived=True`.
- `/materials` получил команду `/archive-material <id> confirm`: без явного `confirm` команда только показывает безопасный usage, а после архивации материал исчезает из списков и latest.
- Обновлены README/CLAUDE и добавлены regression-тесты на repository archive и TUI protected archive flow.

### TUI materials artifact versions

- `/materials` теперь показывает версии learning materials и system design scenarios внутри темы как `vN/total`, а последнюю версию помечает `latest`.
- Команды `/material latest` и `/scenario latest` явно открывают последнюю версию для текущего learning/system design контекста.
- Команды `/preview-material latest` и `/preview-scenario latest` показывают preview последней версии без входа в другой режим.
- Выбор конкретной версии остался через стабильный artifact id: `/material <id>`, `/scenario <id>`, `/preview-material <id>`, `/preview-scenario <id>`.
- Обновлены README/CLAUDE и TUI-регрессионная проверка latest/specific version flow.

### TUI materials artifact preview

- `/materials` получил preview полного learning material через `/preview-material <id>` без входа в `/learn`.
- `/materials` получил preview полного system design scenario через `/preview-scenario <id>` без входа в mock interview.
- Preview показывается в центральной materials-области вместе с metadata artifact: id, title, topic, source и временем создания.
- Существующие команды `/material <id>` и `/scenario <id>` остались действиями открытия artifact в соответствующем режиме.
- Обновлены README/CLAUDE и TUI-регрессионная проверка preview flow.

### TUI materials system design scenario filter

- `/materials` получил отдельный фильтр system design scenarios: текущий system design контекст по умолчанию или все темы через `/materials scenarios all`.
- Команда `/materials scenarios current` возвращает список scenarios к текущему system design контексту, не меняя фильтр learning materials.
- Центральная materials-область и правая mode-specific панель показывают активный фильтр system design scenarios и количество найденных scenarios.
- В all topics режиме у system design scenario показывается название темы, чтобы можно было выбрать artifact без потери контекста.
- Расширена TUI-регрессионная проверка current/all фильтра scenarios и открытия выбранного scenario.

### TUI materials learning material filter

- `/materials` получил фильтр learning materials: текущая тема по умолчанию или все темы через `/materials all`.
- Команда `/materials current` возвращает список learning materials к текущей теме без влияния на список system design scenarios.
- Центральная materials-область и правая mode-specific панель показывают активный фильтр и количество найденных learning materials.
- В all topics режиме у каждого learning material показывается название темы, чтобы можно было выбрать artifact без потери контекста.
- Расширена TUI-регрессионная проверка current/all фильтра и открытия выбранного material/scenario после переключения.

### TUI materials mode-specific side panel

- `/materials` теперь остается focused экраном без левой панели, но показывает правую mode-specific панель.
- Правая панель materials показывает:
  - следующее действие пользователя;
  - текущий контекст learning materials;
  - количество показанных learning materials и system design scenarios;
  - команды выбора и регенерации artifacts;
  - последние события flow.
- Центральная `/materials`-область больше не дублирует последние события, чтобы оставаться сфокусированной на списке generated artifacts.
- Добавлена TUI-регрессионная проверка, что materials side panel видна, mode-specific и не дублирует preview учебного материала.

### TUI system design mode-specific side panel

- В system design/loading system design focused modes левая панель тем остается скрытой, но правая панель теперь видима и mode-specific.
- Правая панель system design показывает:
  - следующее действие пользователя;
  - текущую тему;
  - статус scenario;
  - количество focus areas, design artifacts и transcript-реплик;
  - команды фиксации artifacts;
  - последние события flow.
- Центральная system design-область больше не дублирует последние события, чтобы оставаться сфокусированной на scenario, artifacts, transcript и feedback.
- Добавлена TUI-регрессионная проверка, что system design side panel видна, mode-specific и не дублирует transcript/interviewer content.

### TUI learning mode-specific side panel

- Первый крупный пункт про mode-specific side panels был разбит на отдельные leaf-задачи для learning, system design и `/materials`.
- В learning/loading learning mode левая панель тем остается скрытой, но правая панель теперь видима и показывает:
  - следующее действие пользователя;
  - текущую тему;
  - статус подготовленного материала;
  - количество реплик учебного диалога;
  - компактную навигацию по длинному диалогу;
  - последние события flow.
- Центральная learning-область больше не дублирует последние события и служебную panel-информацию, чтобы оставаться сфокусированной на материале и учебном диалоге.
- Добавлена TUI-регрессионная проверка, что learning side panel видна, mode-specific и не дублирует текст учебного ответа.

### System design artifact auto-transfer from transcript

- TUI system design flow теперь распознает явные artifact-команды внутри обычной реплики кандидата: `/req`, `/requirement`, `/api`, `/data`, `/decision`, `/risk`.
- После сохранения transcript turn такие строки автоматически сохраняются в persisted design sections через существующий путь сохранения artifact.
- Автоперенос сделан line-based и срабатывает только на явные команды в начале строки, чтобы не извлекать неструктурированный текст кандидата.
- Добавлены regression-тесты на parser и TUI-сохранение artifact-команд из transcript.

### System design artifact sections persistence

- `SystemDesignService` получил service-level методы `add_artifact()` и `list_artifacts()` для секций `requirements`, `api`, `data_model`, `decisions`, `risks`.
- TUI-команды `/req`, `/api`, `/data`, `/decision`, `/risk` теперь сохраняют design artifacts в SQLite с привязкой к текущему topic и optional saved scenario.
- При открытии сохраненного system design scenario TUI восстанавливает persisted sections в focused layout.
- Добавлены регрессионные проверки service-level сохранения artifacts и TUI-восстановления sections после повторного открытия scenario.

### System design transcript service persistence

- `SystemDesignService` теперь получает `SQLiteRepository` и сохраняет transcript-реплики mock interview через сервисный слой.
- Добавлены service-методы:
  - `save_transcript_turn()` для сохранения пары candidate/interviewer;
  - `add_transcript_message()` для валидированной записи отдельной реплики;
  - `list_transcript_messages()` для чтения transcript по topic и optional saved scenario.
- TUI system design flow сохраняет пару реплик после ответа интервьюера на основном Textual thread, не используя SQLite connection из background thread.
- Для выбранных/автоматически загруженных saved scenarios TUI запоминает `scenario_id`, чтобы transcript сохранялся с привязкой к scenario.
- Добавлены регрессионные проверки service-level сохранения transcript и TUI-сохранения без записи interview answer.

### System design repository persistence foundation

- Добавлены domain-модели `SystemDesignTranscriptMessage` и `SystemDesignArtifact`.
- Добавлены SQLite-таблицы:
  - `system_design_transcript_messages`;
  - `system_design_artifacts`.
- `SQLiteRepository` получил методы сохранения и чтения transcript-реплик и design artifacts по topic и optional saved scenario.
- Чтение transcript и artifacts возвращает последние записи в порядке чтения, чтобы следующий service/TUI шаг мог восстановить состояние без дополнительной сортировки.
- Добавлены repository-тесты на изоляцию transcript по scenario и фильтрацию artifacts по section.

### Learning dialog compact navigation

- Focused learning layout теперь загружает до 50 последних учебных реплик по теме, но показывает компактное окно из 10 реплик.
- Добавлены команды `/learn-older` и `/learn-newer` для навигации по длинному учебному диалогу без выхода из `/learn`.
- При новом учебном вопросе или повторном входе в `/learn` окно автоматически возвращается к самым свежим репликам.
- Добавлена TUI-регрессионная проверка навигации по длинному сохраненному диалогу.

### Learning dialog restore in TUI

- `LearningService` получил read-метод `list_dialog_messages()` для загрузки последних учебных реплик через сервисный слой.
- При входе в `/learn` TUI загружает последние сохраненные реплики по текущей теме и показывает их в focused learning layout.
- Если сервисный read недоступен в тестовом double, TUI использует существующий repository fallback, чтобы не ломать легковесные TUI-тесты.
- Добавлены регрессионные тесты на service-level чтение последних реплик и восстановление диалога при входе в `/learn`.

### Learning dialog service persistence

- `LearningService` теперь получает `SQLiteRepository` и сохраняет учебные реплики через сервисный слой.
- Добавлены сервисные методы:
  - `explain_and_save()` для сценариев, где генерация и сохранение выполняются в одном потоке;
  - `add_dialog_message()` для безопасного сохранения отдельных реплик `user`/`assistant`.
- TUI learning mode сохраняет пару реплик пользователя и ИИ после завершения генерации через `LearningService`, а не напрямую через repository.
- SQLite-запись в TUI оставлена на основном Textual thread: background thread только вызывает LLM, чтобы не использовать main SQLite connection из другого потока.
- Добавлены тесты на service-level persistence и TUI-сохранение learning dialog без записи interview answer.

### Learning dialog repository persistence

- Добавлена domain-модель `LearningDialogMessage` для реплик учебного диалога по теме.
- Добавлена SQLite-таблица `learning_dialog_messages` с привязкой к `topics`, ролями `user`/`assistant` и временем создания.
- `SQLiteRepository` получил методы:
  - `add_learning_dialog_message()`;
  - `list_learning_dialog_messages()`.
- Загрузка последних реплик возвращает их в порядке чтения, чтобы следующий TUI/service шаг мог использовать историю без дополнительной сортировки.
- Добавлены repository-тесты на изоляцию по теме и limit последних реплик.

### TUI daily practice mode-specific side panel

- Правая панель в обычном practice flow больше не дублирует центральный контент с ответом, эталоном и AI feedback.
- Для шагов `answering`, `scoring`, `answered` и `loading_feedback` добавлен mode-specific текст:
  - следующее действие пользователя;
  - последние события flow.
- Статистика и command palette остаются доступными в правой панели, потому что они не дублируются в центральной области.
- Добавлены TUI-регрессионные проверки для scoring, answered и готового AI feedback состояний.

### Codex roadmap loop discipline

- `ROADMAP.md` переформатирован так, чтобы `## Next` был исполняемой очередью маленьких leaf-задач, а не набором крупных эпиков.
- Добавлены правила исполнения roadmap:
  - работать сверху вниз;
  - закрывать конкретный выбранный checkbox;
  - разбивать слишком крупные пункты перед реализацией;
  - предпочитать user-visible улучшения TUI и рабочего flow.
- `scripts/codex_roadmap_loop.sh` теперь просит Codex выбирать первый незакрытый leaf-checkbox из `## Next`.
- Скрипт требует менять завершенный пункт с `[ ]` на `[x]`, а не только добавлять запись в `## Done`.
- Скрипт парсит финальный ответ через `--output-last-message` и останавливается, если Codex не вернул валидный `ROADMAP_LOOP_STATUS`.
- README для loop обновлен описанием итераций, статусов и safety limits.

### TUI daily practice pending self-score block

- Daily practice center panel теперь показывает блок `Самооценка` уже на шаге ввода оценки.
- После сохранения ответа порядок review-блоков остается явным: ответ -> ожидаемая самооценка -> эталон.
- Добавлена TUI-регрессионная проверка порядка блоков на scoring-шаге.

### TUI daily practice self-score placement

- Daily practice center panel теперь показывает отдельный блок `Самооценка` между ответом пользователя и эталонным ответом.
- Это делает порядок review-блоков более явным: ответ -> самооценка -> эталон -> AI feedback.
- Добавлена TUI-регрессионная проверка порядка этих блоков после сохранения самооценки.

### TUI daily practice visual states

- Daily practice center panel теперь явно показывает состояние текущего ответа:
  - ожидает ответ;
  - ответ сохранен и ожидает самооценку;
  - ответ/самооценка сохранены и AI feedback генерируется;
  - AI feedback готов.
- Статус расположен рядом с вопросом, ответом, эталоном и feedback, чтобы пользователь не искал состояние flow в истории или правой панели.
- Добавлены TUI-регрессионные проверки для статусов после сохранения ответа, самооценки и готового AI feedback.

### TUI generated artifacts screen

- Добавлен focused TUI-экран `/materials`.
- Экран показывает:
  - последние `learning_materials` для текущей темы;
  - последние `system_design_scenarios` для system design темы;
  - команды выбора и регенерации.
- Добавлены slash commands:
  - `/material <id>` открывает сохраненный учебный материал в learning mode;
  - `/scenario <id>` открывает сохраненный system design scenario в mock interview;
  - `/regen-material` ставит новую `learning-material` job;
  - `/regen-scenario` ставит новую `system-design-scenario` job.
- `/materials` использует focused layout, чтобы не занимать экран боковыми панелями во время выбора artifact.
- Добавлены TUI-тесты на список и открытие сохраненных artifacts.

### Persistent generated artifacts

- Добавлены отдельные SQLite-таблицы:
  - `learning_materials`;
  - `system_design_scenarios`.
- Добавлены domain-модели `LearningMaterial` и `SystemDesignScenario`.
- Repository получил методы сохранения и загрузки последнего artifact по теме:
  - `add_learning_material()`;
  - `latest_learning_material()`;
  - `add_system_design_scenario()`;
  - `latest_system_design_scenario()`.
- `content-worker` теперь сохраняет `learning-material` и `system-design-scenario` не только в `content_generation_jobs.result_json`, но и в отдельные таблицы.
- `ensure_learning_material()` и `ensure_system_design_scenario()` больше не ставят новую job, если для темы уже есть сохраненный artifact.
- TUI при входе в `/learn` или `/system-design` сначала загружает сохраненный artifact и только при отсутствии ставит новую background job.
- Добавлены тесты на persistence artifacts и TUI reuse без повторной генерации.

### Automatic learning and system design content in TUI

- TUI теперь автоматически ставит background jobs не только для вопросов:
  - `/learn` ставит `learning-material` job для текущей темы;
  - `/system-design` ставит `system-design-scenario` job для system design темы.
- Background worker в TUI теперь за один запуск обрабатывает до трех queued jobs, чтобы задачи, поставленные во время активной генерации, не зависали до следующего ручного действия.
- Готовый `learning-material` отображается в центральной области focused learning mode.
- Готовый `system-design-scenario`, если transcript еще пустой и используется дефолтный сценарий, заменяет default scenario и показывает focus areas.
- Добавлены тесты:
  - TUI auto-queue для learning material;
  - TUI auto-queue для system design scenario;
  - сервисный ensure для artifact jobs без дублей.

### Background generation job types

- Расширена SQLite-очередь фоновой генерации без изменения схемы:
  - `question`;
  - `learning-material`;
  - `system-design-scenario`.
- `content-enqueue` получил параметр `--kind`.
- `content-worker` теперь умеет обрабатывать не только генерацию вопросов, но и generated artifacts:
  - учебный материал по теме;
  - system design mock interview scenario с focus areas.
- Для вопросов поведение прежнее: результат сохраняется как `Question(source='background-llm')`.
- Для learning/system design artifacts `result_json` остается audit/result snapshot у job; актуальные материалы дополнительно сохраняются в отдельных таблицах.
- Fallback LLM теперь возвращает русскоязычные learning material и system design scenario для этих job types.
- Добавлены тесты сервиса и CLI на новые типы фоновой генерации.

### Minimal bootstrap instead of hardcoded seed base

- Сокращен hardcoded seed до минимального bootstrap/fallback набора:
  - 5 стартовых тем;
  - 1 общий fallback-вопрос на тему вместо полноценной встроенной базы вопросов.
- Источник bootstrap-вопросов теперь сохраняется как `source='bootstrap'`.
- Дефолт `Question.source` и новая SQLite-схема выровнены на `bootstrap`.
- Старые существующие вопросы в пользовательской базе не удаляются и не перезаписываются.
- `AppServices` и `SQLiteRepository` теперь идемпотентно закрывают SQLite connection, включая временные репозитории в тестах.
- Обновлены тесты seed/bootstrap поведения и TUI `/skip`, чтобы тест не зависел от старого количества встроенных вопросов.

### Automatic question generation from TUI

- Реализован первый шаг автоматической генерации контента без ручного запуска CLI-команд.
- При старте TUI-сессии с выбранной темой приложение проверяет количество вопросов по теме.
- Если вопросов меньше порога, TUI:
  - ставит `question` job в SQLite-очередь;
  - защищается от дублей, если по теме уже есть queued/running job;
  - запускает background worker в отдельном thread;
  - использует отдельное подключение к SQLite внутри worker, чтобы не шарить connection между потоками;
  - показывает статус в topbar `Content: ...`;
  - добавляет событие в history после завершения генерации.
- CLI-команды `content-enqueue` и `content-worker` остаются как служебный интерфейс, но для обычного TUI-flow больше не обязательны для генерации новых вопросов.
- Добавлены тесты:
  - `ensure_question_backlog()` не создает дубли активных jobs;
  - TUI автоматически ставит job и запускает worker при выборе темы.

### TUI daily practice feedback

- Daily practice стал ближе к focused workflow:
  - вопрос;
  - ответ пользователя;
  - эталон;
  - AI feedback
  теперь отображаются в центральной области.
- `/feedback` по-прежнему сохраняет feedback в SQLite, но пользователь больше не обязан искать его в правой панели.
- Статистика и command palette не смешиваются с центральным AI feedback для вопроса.
- Добавлен TUI-тест на отображение AI feedback в center panel после ответа и самооценки.

### TUI system design artifacts

- System design mode получил отдельные focused-секции:
  - requirements;
  - API;
  - data model;
  - architecture decisions;
  - risks / failure modes.
- Добавлены slash commands:
  - `/req <текст>`;
  - `/requirement <текст>`;
  - `/api <текст>`;
  - `/data <текст>`;
  - `/decision <текст>`;
  - `/risk <текст>`.
- Артефакты отображаются в центральной области system design focused layout рядом со сценарием, transcript и feedback.
- При запуске нового `/sd <сценарий>` transcript и design artifacts сбрасываются.
- Добавлены TUI-тесты на artifact-команды и отображение секций.
- `refresh_topbar()` защищен от timer race при размонтировании Textual widgets в headless-тестах.

### TUI learning dialog history

- Learning mode больше не использует только последний `last_feedback` как основной UI.
- Добавлена отдельная in-memory история учебного диалога:
  - реплика пользователя;
  - ответ ИИ;
  - pending message во время генерации.
- Центральная область learning mode показывает несколько последних реплик учебного диалога, контекст текущего interview-вопроса и loading state.
- `/stats` и `/commands` остаются видимыми в focused layout через блок "Панель".
- Добавлены TUI-тесты на несколько учебных реплик и сохранение learning history без записи в `answers`.

### Focused TUI layout, first step

- Начата переработка TUI по roadmap в сторону mode-aware интерфейса.
- Для `learning`, `loading_learning`, `system_design`, `loading_system_design` и `loading_system_design_feedback` включается focused layout:
  - левая панель тем скрывается;
  - правая панель истории/feedback/notes скрывается;
  - центральная область занимает основное пространство.
- Learning mode теперь показывает учебный вопрос, контекст текущего interview-вопроса, loading state, AI-разбор и последние события в центральной области.
- System design mode теперь показывает transcript, pending message, feedback/следующий вопрос и последние события в центральной области.
- При возврате через `/practice` обычный трехпанельный practice layout восстанавливается.
- Добавлены TUI-тесты на скрытие/возврат боковых панелей и отображение учебного ответа в центральной области.

## 2026-05-11

### Background content generation

- Реализован roadmap-пункт фоновой генерации контента.
- Добавлена SQLite-таблица `content_generation_jobs`:
  - `kind`;
  - `status`;
  - `payload_json`;
  - `result_json`;
  - `error`;
  - timestamps.
- Добавлена domain-модель `ContentGenerationJob`.
- Добавлен `ContentGenerationService`:
  - `enqueue_question()`;
  - `list_jobs()`;
  - `process_next_job()`;
  - `retry_job()`.
- Первый поддержанный job type: `question`.
- Worker генерирует вопрос через существующий LLM/fallback, сохраняет его в `questions` с `source='background-llm'` и обновляет job status.
- Добавлены CLI-команды:
  - `content-enqueue`;
  - `content-jobs`;
  - `content-worker`;
  - `content-retry`.
- Добавлены тесты очереди, worker-flow, retry и регистрации CLI-команд.
- Выполнен smoke через временную SQLite-базу:
  - enqueue job;
  - worker `--once`;
  - просмотр job status;
  - проверка созданного вопроса.

### LLM-generated starter pack

- Реализован первый шаг к LLM-generated curriculum.
- Добавлен `CurriculumService`:
  - строит prompt для генерации учебного плана;
  - парсит JSON с темами, learning objectives, вопросами, эталонными ответами и mock scenarios;
  - имеет fallback curriculum при невалидном JSON или недоступной Ollama;
  - сохраняет темы и вопросы в SQLite.
- Добавлена CLI-команда:
  - `generate-seed --topics N --questions-per-topic M`;
  - `generate-seed --dry-run` для просмотра без записи в SQLite.
- Добавлены repository-методы:
  - `upsert_topic()`;
  - `add_question_once()`;
  - `question_exists()`.
- LLM-generated вопросы сохраняются с `source='llm-seed'` и не дублируются при повторном запуске.
- Fallback LLM теперь возвращает структурированный starter pack на русском для `generate-seed`.
- Добавлены тесты:
  - генерация и сохранение LLM seed-вопросов;
  - защита от дублей;
  - fallback parsing при невалидном JSON.
- Выполнены smoke-проверки CLI `generate-seed` в `--dry-run` и с записью во временную SQLite-базу.

### System Design Mock Interview

- Реализован roadmap-пункт System Design Mock Interview.
- Добавлен `SystemDesignService` поверх существующего LLM-интерфейса без изменений SQLite-схемы.
- Добавлены prompt-ы:
  - следующий ход интервьюера по system design;
  - итоговый structured feedback по senior-критериям.
- Добавлены TUI-команды:
  - `/system-design` — начать mock interview с дефолтным сценарием;
  - `/sd <сценарий>` — начать mock interview с собственным сценарием;
  - `/sd-feedback` — получить итоговый feedback;
  - `/practice` — вернуться из system design mode к обычным вопросам.
- System design mode показывает сценарий, transcript, loading state для Ollama и не сохраняет реплики как обычные interview answers.
- Fallback LLM теперь умеет отдавать русскоязычный system design interviewer response и итоговый feedback.
- Добавлены тесты service prompt-ов и TUI-flow system design mode.

### TUI workspace improvements

- Реализован roadmap-пункт улучшения TUI.
- Левая, центральная и правая панели переведены на scrollable containers.
- В правую панель добавлен отдельный notes editor на `TextArea`.
- Добавлены команды и hotkeys:
  - `/commands` и `Ctrl+P` — command palette;
  - `/notes` и `Ctrl+N` — фокус на notes editor;
  - `Esc` — вернуть фокус в input bar.
- Summary сессии теперь показывает количество непустых строк заметок.
- Добавлены тесты:
  - наличие scrollable panels;
  - работа notes editor;
  - command palette содержит основные команды;
  - helper подсчета строк заметок.

### Ollama timeout increase

- Увеличен дефолтный timeout Ollama с 45 до 180 секунд для слабой локальной машины и медленных ответов `qwen3-coder:30b`.
- Значение по-прежнему можно переопределить через `INTERVIEW_PREP_OLLAMA_TIMEOUT`.

### Config file support

- Реализован roadmap-пункт с config-файлом для Ollama.
- Добавлен `interview_prep/infra/config.py`:
  - `load_config()`;
  - `write_default_config()`;
  - настройки `model`, `base_url`, `timeout_seconds`.
- Добавлен пример `config.example.toml`.
- Локальный файл по умолчанию: `config/interview_prep.toml`.
- Добавлены CLI-команды:
  - `config-init`;
  - `config-show`.
- Добавлен глобальный параметр `--config`, который работает до и после подкоманды.
- Переменные окружения `INTERVIEW_PREP_OLLAMA_MODEL`, `INTERVIEW_PREP_OLLAMA_BASE_URL`, `INTERVIEW_PREP_OLLAMA_TIMEOUT` имеют приоритет над TOML config.
- Добавлены тесты config loader, env override, записи default config и `config-show`.

### TUI learning mode

- Реализован roadmap-пункт "режим обучения и разъяснения с ИИ".
- Добавлен `LearningService` без доступа к SQLite: он строит учебный prompt и вызывает существующий LLM client.
- Добавлены TUI-команды:
  - `/learn` — включить учебный режим;
  - `/learn <вопрос>` — сразу задать учебный вопрос по текущей теме;
  - `/practice` — вернуться к interview practice.
- В learning mode обычный текст отправляется в ИИ как учебный вопрос, а не сохраняется как interview answer.
- Учебный prompt требует:
  - объяснять пошагово на русском;
  - давать backend-примеры;
  - добавлять mini-drill;
  - не оценивать пользователя.
- Добавлен loading state `ИИ готовит учебное объяснение...`, чтобы TUI не выглядел зависшим на Ollama.
- Добавлены тесты:
  - learning prompt не является interview evaluation;
  - TUI learning mode не увеличивает `answered_count`;
  - `/practice` возвращает к прохождению вопросов.

### Textual TUI workspace

- Добавлены зависимости `textual` и `rich` в `pyproject.toml` и `requirements.txt`.
- Сохранены старые CLI-команды.
- Добавлены новые основные команды:
  - `python -m interview_prep tui`;
  - `python -m interview_prep app`.
- Реализован полноэкранный TUI workspace:
  - topbar с темой, номером вопроса, прошедшим/оставшимся временем и статусом Ollama;
  - левая панель тем и количества ответов по теме;
  - центральная панель текущего вопроса, подсказки, ответа пользователя и эталона;
  - правая панель истории, AI feedback, статистики и summary;
  - нижняя input bar для ответов и slash commands.
- Поддержаны команды TUI:
  - `/hint`;
  - `/answer`;
  - `/feedback`;
  - `/skip`;
  - `/stats`;
  - `/quit`;
  - дополнительно `/next` для ручного перехода.
- TUI сохраняет ответ сразу, затем просит самооценку `1-5` и дописывает ее в SQLite.
- Добавлен `update_answer_score()` в repository и `update_self_score()` в `SessionService`.
- AI feedback в TUI генерируется в background thread: UI показывает loading state и не зависает на Ollama.
- `/skip` теперь исключает вопрос из текущей TUI-сессии, чтобы он не возвращался сразу же.
- Добавлены headless Textual-тесты:
  - end-to-end прохождение одного вопроса с сохранением self-score;
  - slash commands `/hint`, `/answer`, `/stats`, `/skip`, `/quit`.
- Выполнен ручной smoke запуска `python -m interview_prep tui`.

### Russian flow and Ollama feedback fix

- Проверена локальная Ollama:
  - `ollama list` показывает `qwen3-coder:30b`;
  - прямой smoke с timeout 30 секунд успешно вернул русский ответ.
- Причина fallback в сессии: timeout 8 секунд был слишком коротким для `qwen3-coder:30b`, особенно при холодном старте или длинном prompt.
- Timeout Ollama увеличен до 45 секунд.
- Добавлены env-настройки:
  - `INTERVIEW_PREP_OLLAMA_MODEL`;
  - `INTERVIEW_PREP_OLLAMA_BASE_URL`;
  - `INTERVIEW_PREP_OLLAMA_TIMEOUT`.
- Добавлена CLI-команда `llm-check` для диагностики Ollama.
- CLI переведен на русский.
- Seed topics/questions/reference answers переведены на русский; существующие `source='seed'` вопросы обновляются при `init`.
- Fallback feedback переведен на русский.
- Prompt для AI feedback усилен требованием отвечать строго на русском.
- Самооценка убрана из интерактивной сессии; ответы сохраняются с `self_score = NULL`.
- Статистика CLI больше не показывает среднюю самооценку и слабые темы по самооценке.
- Проверены сценарии:
  - session с `--no-feedback`;
  - session с живым Ollama feedback;
  - `llm-check`;
  - обновление существующей базы через `init`.

### Feedback attribution fix

- Воспроизведена проблема на ответе `эта тузла для мета программирования`: модель приписывала кандидату детали из эталонного ответа.
- Причина: feedback prompt давал рядом `Reference answer` и `Candidate answer`, но не запрещал явно переносить пункты из эталона в раздел "Хорошо".
- Сборка prompt вынесена в `build_feedback_prompt()`.
- Новый prompt:
  - отделяет вопрос, ответ кандидата и эталон XML-like тегами;
  - просит оценивать только текст внутри `<candidate_answer>`;
  - запрещает писать, что кандидат упомянул то, чего нет в его ответе;
  - требует сначала пересказать, что реально было в ответе пользователя.
- Добавлен регрессионный тест на guardrails feedback prompt.
- Проверено через живую Ollama: детали из эталона теперь попадают в "Упущено", а не в "Хорошо".

### Interactive session flow fix

- Воспроизведен баг интерактивной сессии в TTY: после ввода одной строки ответа и Enter приложение продолжало ждать следующую строку многострочного ответа без явного prompt, что выглядело как зависание.
- Причина: `read_multiline_answer()` завершал ввод только строкой `.` или EOF.
- Исправлен flow ответа:
  - обычный ответ теперь однострочный и завершается Enter;
  - многострочный режим включается явно через `/multi`;
  - многострочный ответ завершается пустой строкой или `.`.
- Добавлены явные сообщения:
  - `Answer captured.`;
  - `Now rate your answer.`;
  - `Saving answer...`;
  - `Answer saved as #...`;
  - `Generating feedback with Ollama or fallback...`;
  - `Feedback saved.`.
- Ответ теперь сохраняется до запроса AI feedback, чтобы долгая или недоступная Ollama не блокировала сохранение.
- Timeout Ollama сначала был уменьшен до 8 секунд для быстрого fallback, затем поднят до 45 секунд после проверки реальной скорости `qwen3-coder:30b`.
- Добавлены тесты CLI-flow:
  - однострочный ответ завершается Enter;
  - многострочный режим имеет явный terminator;
  - session с `--no-feedback` сохраняет ответ после обычного однострочного ввода;
  - `ResilientLLMClient` использует fallback при недоступности primary LLM.

### MVP foundation

- Изучена текущая директория проекта: были только `task.md`, `promts.txt`, `utils.md` и локальные настройки.
- Зафиксированы допущения MVP:
  - Python 3.13.9 из текущего окружения.
  - SQLite-база по умолчанию: `data/interview_prep.db`.
  - Терминальный CLI для первой версии; Textual/Rich оставлены на следующий этап.
  - Ollama используется через локальный HTTP API, fallback обязателен.

### Domain and infrastructure

- Создан пакет `interview_prep`.
- Добавлены доменные модели: `Topic`, `Question`, `Session`, `Answer`.
- Добавлены правила валидации сложности и самооценки.
- Реализована SQLite-схема для тем, вопросов, сессий и ответов.
- Добавлен seed стартовых тем и 10 вопросов по Python backend/system design подготовке.

### Services

- Реализован `SessionService` для старта/завершения сессии, выбора следующего вопроса, сохранения ответа и запроса feedback.
- Реализован `QuestionService` для списка тем/вопросов и добавления вопроса из свободного текста.
- Реализован `StatsService` для статистики и предложения темы.
- Реализован `OllamaClient`, `FallbackLLMClient` и `ResilientLLMClient`.

### UI

- Добавлен CLI:
  - `init`
  - `topics`
  - `questions`
  - `session`
  - `add-question`
  - `stats`
- Параметр `--db` поддерживается до и после подкоманды.

### Tests and verification

- Добавлены unittest-тесты ключевых сервисных сценариев.
- Добавлен optional live Ollama test через `RUN_OLLAMA_TESTS=1`.
- Проверены:
  - компиляция пакета;
  - unit-тесты;
  - инициализация БД;
  - список вопросов;
  - интерактивная сессия через stdin;
  - статистика после сохраненного ответа;
  - добавление вопроса с fallback LLM.
