# Roadmap

## Текущий статус

Технический MVP готов и проверен локально, но продуктовый сценарий еще не соответствует целевому качеству.

Главные текущие проблемы:

- Полноценный curriculum lifecycle еще не заменил bootstrap полностью: `infra/seed.py` оставляет минимальный fallback-набор тем и по одному общему вопросу на тему.
- Фоновая генерация контента уже умеет генерировать вопросы, учебные материалы и system design scenarios; TUI автоматически ставит эти задачи, показывает компактный статус очереди/последний результат в верхней строке, имеет экран `/materials` для просмотра/выбора generated artifacts и экран `/content` для списка queued/running/failed jobs с безопасным retry failed job. Полноценное управление очередью из TUI еще не готово.
- TUI layout уже движется к focused/mode-aware интерфейсу; learning dialog сохраняется с session/context metadata, восстанавливается по теме с компактной навигацией длинного диалога и доступен в history как отдельные учебные сессии.
- Читаемость AI-диалогов в TUI уже улучшена единым renderer в learning, system design и daily practice review, но markdown из LLM пока часто отображается как сырой текст.
- TUI теперь прогоняет LLM-authored markdown через Rich Markdown renderer для AI feedback, learning answers, system design replies и preview generated artifacts; нужны более широкие regression-тесты на markdown в чат-окнах.
- TUI input bar заменен на многострочный composer на базе TextArea; Enter отправляет сообщение, Shift+Enter вставляет перенос строки, а composer расширяется для длинных draft до scrollable cap.
- TUI composer теперь покрыт regression-тестами для многострочных ответов, Shift+Enter/newline и code block submit в practice, learning и system design flows.
- Для вопросов добавлен foundation тегов: domain-модель `Tag`, SQLite-таблицы `tags`/`question_tags`, repository-методы для привязки тегов к вопросам, CLI `questions` показывает привязанные теги вопроса и фильтрует список через `--tag <slug>`, а TUI показывает теги текущего вопроса в practice workflow.
- Для накопительной тетради AI-объяснений добавлен storage foundation: domain-модель `NotebookEntry`, SQLite-таблица `notebook_entries` и repository-методы чтения по topic/subtopic/session/source message.
- Learning mode теперь автоматически сохраняет AI-объяснения в notebook entries с привязкой к topic/dialog session/source message. TUI получил read-only экран `/notebook` с фильтрами topic/subtopic/competency, named manual notes, feedback gaps из `/note-from-answer` и просмотром сохраненных explanations; переходы в notebook уже заметны из стартового/topic экрана, history learning dialogs и `/materials`.
- Для ручных заметок добавлен storage foundation: domain-модель `ManualNote`, SQLite-таблица `manual_notes` и repository-методы чтения по topic/session/context; TUI notes editor сохраняет и восстанавливает draft по session/topic/global context.
- Ручная UX-регрессия `learn` до выбора topic закрыта: вход запускает новую topicless learning-сессию без восстановления прошлых topic-bound реплик; вход в конспект обучения уже заметен на стартовом/topic экране через Notebook action и подсказку, из history learning dialogs и из `/materials` по текущей или выбранной теме.
- Переключение TUI между `learn`/`system-design`/`practice` через клики и slash-команды больше не наслаивает focused modes: текущий focused mode разворачивается до practice-context перед входом в другой основной режим.
- Для будущего web UI есть read-only WSGI adapter skeleton поверх `ReadOnlyApplicationFacade`: `/api/smoke`, `/api/dashboard`, `/api/readiness`, `/api/competencies`, `/api/sessions/<id>`, `/api/notebook`, health endpoints и simple HTML diagnostics smoke page без замены TUI.
- Основной Ollama runtime по умолчанию переключен на локальную модель `gemma4:e4b`; config/env overrides и fallback при недоступности модели сохранены.
- Продукт уже начал измерять подготовку через senior competencies и evidence: taxonomy зафиксирована, добавлена domain-модель, базовая SQLite-таблица/seed competencies, repository API, таблица связи `question_competencies`, repository-методы чтения/перезаписи привязок вопросов и seed links для bootstrap-вопросов, CLI `questions` и TUI practice header показывают competencies вопроса. Rubric dimensions для senior answers зафиксированы как contract; отдельные system design rubric dimensions сохранены и после `/sd-feedback` transcript/artifacts оцениваются deterministic rubric evaluation с сохранением scores; TUI system design screen заранее показывает пустые requirements/API/data/risks sections перед итоговым feedback, `/sd-checkpoint` дает короткую промежуточную interviewer-проверку без final feedback artifact/evaluation, `/sd-pressure` задает targeted pressure follow-up по senior failure modes, а `/history system-design` показывает сохраненный final feedback и rubric scores; structured evaluation service умеет strict LLM JSON и fallback heuristic при недоступной Ollama/невалидном JSON, practice flow сохраняет evaluation, TUI review показывает rubric scores после self-score, а `ReadinessService` считает per-competency readiness score и общий evidence-based readiness summary без абсолютной оценки кандидата; CLI `stats` показывает `Senior readiness` и top gaps, а TUI `/readiness` показывает focused dashboard по competencies, score, evidence count и next action.
- Read-only facade теперь отдает JSON-safe список competencies, competency links вопросов и web endpoints `/api/readiness`/`/api/competencies`/`/api/sessions/<id>`/`/api/notebook` для будущих dashboard/API слоев без замены TUI.
- CLI `evaluations --answer <id>` показывает сохраненную structured rubric evaluation по ответу: summary, source, average score, per-dimension evidence/gaps и next drills. Manual override rubric score сохраняет original AI score для аудита и используется как effective score в readiness, session outcome и interview report surfaces.
- AI feedback prompt уже ужесточен против приписывания кандидату лишних пунктов; есть weak-answer eval cases, unit prompt guard и service-level suspicious flag для praise без evidence из candidate answer. `feedback_quality_flags` сохраняются в payload последней structured evaluation, TUI review показывает предупреждение, если feedback помечен как fallback или suspicious, `/recheck-feedback` повторно запрашивает feedback для последнего ответа с более строгим prompt, а regression-тест фиксирует низкие rubric scores для ответа "не знаю" и suspicious-flag для reference-only praise.
- Сессии уже сохраняются и видны в history; базовый статус `in_progress`/`completed`/`abandoned` хранится в SQLite с legacy-backfill, а session outcome уже имеет domain-модель, SQLite/repository storage foundation, deterministic generation после answered practice session и показывается на TUI ended screen после `/quit` или истечения target time, через `/finish-session` без выхода из TUI, в `/history <session-id>` и через CLI `session-summary <id>`.
- Calibration baseline уже умеет выбирать до 5 accepted questions по разным competencies и запускать из Today empty-state mixed practice session, которая идет по выбранному service-level плану; outcome сохраняется с типом `calibration_baseline`, чтобы readiness/trend отличал первичную оценку от обычной practice. Repeat baseline через 7 дней показывается как Today/readiness action и после завершения сохраняет сравнение readiness delta с предыдущей baseline. Mock senior interview запускается без ручного выбора topic из Today/readiness, смешивает coding/theory/system design/debugging и показывает section progress в practice review flow.
- Readiness snapshot теперь включает `must_fix_drill` для top gaps, а CLI `stats` и TUI `/readiness` показывают список `Must fix before interview` с конкретными drills перед интервью.
- CLI `interview-report` экспортирует Markdown-отчет перед интервью по latest или выбранной completed practice session: readiness signal, strengths/gaps, evidence answers и next plan.
- CLI `curriculum-status` показывает read-only покрытие generated curriculum: counts curriculum topics/subtopics/objectives/questions и пустые зоны bootstrap/fallback.
- Generated content уже появляется в приложении; для generated questions добавлен первый quality gate против очевидных дублей внутри темы, storage foundation source_quality/status (`pending_review`/`accepted`/`archived`), CLI `questions-review` и TUI `/questions-review` для pending review/accept/archive. Background question generation уже просит LLM вернуть tag/competency slugs и безопасно привязывает tags/known competencies к новым вопросам; generated materials/scenarios можно архивировать с optional reason; еще нет оценки полезности generated artifacts.
- TUI refactor уже выделил pure render helpers, practice/learning/system-design controllers и content worker orchestration; дальнейшие TUI-фичи должны сохранять этот контракт и не возвращать state transitions обратно в монолитный `ui/tui.py`.

## Product principles

- Это не одноразовый MVP, а приложение с фичами, которые должны использоваться и развиваться дальше.
- Главная цель UX: снизить когнитивную нагрузку пользователя. Пользователь должен открыть приложение и сразу заниматься, а не думать, какую команду запустить, что сгенерировать или где искать следующий шаг.
- LLM должна незаметно помогать подготовке: предлагать темы, заранее готовить вопросы, объяснения и system design сценарии, а не требовать ручного запуска служебных команд.
- TUI должен фокусировать экран на текущем учебном действии. Если пользователь в режиме обучения, основное пространство должно быть занято объяснением и диалогом, а не простаивающими панелями.
- Senior readiness должен измеряться по наблюдаемым компетенциям и evidence, а не по общему ощущению прогресса. Любая рекомендация следующего шага должна объяснять, какой gap она закрывает.

## Roadmap execution rules

- `## Next` — это очередь исполнения, а не общий wishlist.
- Работать сверху вниз: брать первый незакрытый checkbox, который можно завершить, проверить и задокументировать за одну итерацию.
- Если пункт слишком крупный для одной итерации, сначала разбить его прямо в `## Next` на конкретные leaf-задачи и выполнить первую безопасную leaf-задачу.
- После завершения менять выбранный checkbox с `[ ]` на `[x]`. Не ограничиваться добавлением новой строки в `## Done`.
- В `## Done` добавлять только короткий итог завершенной работы; детальный отчет писать в `DEVELOPMENT_LOG.md`.
- Предпочитать user-visible улучшения TUI и рабочего flow. Чистые refactor/docs брать только когда они прямо разблокируют следующий пользовательский шаг.
- Если задача требует решения по схеме, UX или продуктовой логике, зафиксировать выбранное решение в `DEVELOPMENT_LOG.md` и продолжить маленькой безопасной реализацией.

## Done

- [x] Calibration: regression-тест подтверждает, что manual override влияет на readiness и сохраняет original AI score для аудита.
- [x] Calibration: manual override rubric score учитывается как effective score в readiness/session outcome/report surfaces.
- [x] Calibration: CLI `interview-report` экспортирует Markdown-отчет со strengths, gaps, evidence answers и next plan.
- [x] Calibration: repeat baseline outcome сравнивает текущий readiness delta с предыдущей completed baseline и показывает summary в session outcome.
- [x] Calibration: service-level repeat baseline status определяет последнюю completed baseline, 7-day due date и последний readiness delta.
- [x] Calibration: readiness показывает "must fix before interview" список из top gaps с конкретными drills.
- [x] Mock interview progress: TUI practice review показывает текущую section и remaining sections для mixed mock senior interview.
- [x] Mock interview TUI: Today/readiness action starts topicless mixed mock senior interview from the service-level plan.
- [x] Mock interview session: запуск mixed practice session из service-level mock interview plan без ручного выбора topic.
- [x] Calibration: service-level mock senior interview plan смешивает coding/theory/system design/debugging sections без ручного выбора topic.
- [x] Calibration: baseline outcome сохраняется с marker/type для readiness trend и summary первичной оценки.
- [x] Calibration: baseline practice session запускается из Today empty-state и использует service-level план вопросов по разным competencies.
- [x] Web API: adapter boundaries задокументированы для будущего web UI без прямого доступа adapter к repository.
- [x] Web API: simple HTML smoke page добавлена как diagnostics surface для read-only adapter, без замены TUI.
- [x] Web API: query param validation для новых endpoints покрыта regression-тестом `/api/notebook`, malformed numeric params возвращают `400`.
- [x] Web API: `/api/sessions/<id>` отдает completed session detail и сохраненный outcome.
- [x] Web API: `/api/notebook` отдает AI notebook entries и named manual notes с filters topic/competency/session.
- [x] Web API: `/api/competencies` отдает read-only competency readiness metadata со score/coverage.
- [x] Web API: `/api/readiness` отдает read-only readiness snapshot поверх `ReadinessService`.
- [x] TUI refactor: roadmap/log зафиксировали контракт уже выделенных render/controller/worker модулей после серии extraction steps.
- [x] TUI refactor: system-design entry state snapshot вынесен в pure controller helper с тестами без Textual harness.
- [x] TUI refactor: content worker finish/result status transition вынесен в `ContentWorkerOrchestrator` без изменения artifact side effects.
- [x] TUI refactor: content worker loop/process-next-job orchestration вынесен в `ContentWorkerOrchestrator` без изменения TUI thread handoff.
- [x] TUI refactor: content worker state/pause/resume/start guard вынесены в отдельный orchestration class без изменения worker thread/result side effects.
- [x] TUI refactor: system-design checkpoint/pressure/final-feedback transitions вынесены в pure controller helpers с тестами без Textual harness.
- [x] TUI refactor: system-design finish-turn transition snapshot вынесен в pure controller helper с тестами без Textual harness.
- [x] TUI refactor: learning finish transition snapshot вынесен в pure controller helper с тестами без Textual harness.
- [x] TUI refactor: learning request/loading transition snapshot вынесен в pure controller helper с тестами без Textual harness.
- [x] TUI refactor: learning entry state snapshot для входа в `/learn` вынесен в pure controller helper с тестами без Textual harness.
- [x] TUI refactor: practice start/reset session state snapshots вынесены в pure controller helpers без Textual harness.
- [x] TUI refactor: practice submit-routing для `select_topic`/`answering`/`scoring`/`answered` вынесен в pure helper с тестами без Textual harness.
- [x] TUI refactor: pure render helpers вынесены из `ui/tui.py` в отдельный модуль без изменения поведения.
- [x] TUI Today: command palette сгруппирована по workflow.
- [x] TUI Today: добавлен regression-тест клика по `Review Weak Answer`.
- [x] TUI Today: добавлен regression-тест keyboard flow Enter -> recommended drill.
- [x] TUI Today: empty-state без readiness evidence предлагает `/generate-curriculum` или первую baseline practice session.
- [x] TUI Today: "why this drill" теперь берется из `ReadinessService` recommended drill и попадает в serialized readiness snapshot.
- [x] Осмотр текущей директории.
- [x] План MVP и архитектурные допущения.
- [x] Слоистая структура проекта.
- [x] Domain-модели и бизнес-правила.
- [x] SQLite-схема и repository.
- [x] Минимальный bootstrap стартовых тем и fallback-вопросов.
- [x] Ollama client.
- [x] Fallback/mock LLM.
- [x] Сервис ежедневной сессии.
- [x] Сервис вопросов и добавления вопроса из свободного текста.
- [x] Сервис статистики.
- [x] CLI для основных операций.
- [x] Тесты ключевой логики.
- [x] Optional live Ollama test.
- [x] README, CLAUDE, DEVELOPMENT_LOG, ROADMAP.
- [x] Исправить интерактивный session flow после обычного Enter.
- [x] Сохранять ответ до запроса AI feedback.
- [x] Показывать понятные статусы сохранения и генерации feedback.
- [x] Покрыть CLI session flow регрессионными тестами.
- [x] Перевести CLI, seed-вопросы, эталонные ответы и fallback feedback на русский.
- [x] Убрать самооценку из интерактивной сессии.
- [x] Увеличить Ollama timeout для `qwen3-coder:30b` и добавить `llm-check`.
- [x] Ужесточить prompt AI feedback, чтобы модель не приписывала пользователю пункты из эталона.
- [x] Добавить Textual/Rich TUI workspace как основной интерфейс.
- [x] Поддержать TUI slash commands: `/hint`, `/answer`, `/feedback`, `/skip`, `/stats`, `/quit`.
- [x] Добавить TUI flow: выбор темы, ответ, самооценка, эталон, feedback, следующий вопрос, summary.
- [x] Добавить режим обучения и разъяснения с ИИ: `/learn` и `/practice` в TUI, без сохранения учебного диалога как interview answer.
- [x] Добавить настройки модели, URL Ollama и timeout через config-файл.
- [x] Улучшить TUI: scrollable панели, command palette, отдельный notes editor.
- [x] Добавить режим System Design Mock Interview: отдельный TUI-сценарий для проектирования полноценного сервиса end-to-end, где ИИ играет интервьюера, задает уточняющие вопросы, проверяет requirements, API, data model, storage, scaling, consistency, queues, caching, observability, failure modes и в конце дает structured feedback по senior-критериям.
- [x] Генерировать расширенный starter pack вопросов через live Ollama командой `generate-seed` как первый шаг к LLM-generated curriculum.
- [x] Добавить фоновую генерацию контента: SQLite-очередь задач и worker для генерации новых вопросов без блокировки TUI.
- [x] Добавить команды управления фоновой генерацией: `content-enqueue`, `content-jobs`, `content-worker`, `content-retry`.
- [x] Первый шаг focused TUI layout: learning и system design режимы используют центральную область как основное рабочее пространство, а боковые панели временно скрываются.
- [x] Улучшить learning mode в TUI: отдельная история учебного диалога в центральной области вместо затирания предыдущего ответа через `last_feedback`.
- [x] Улучшить system design mode в TUI: добавить focused-секции для requirements, API, data model, architecture decisions и risks/failure modes.
- [x] Улучшить daily practice в TUI: AI feedback по последнему ответу показывается в центральной области вместе с вопросом, ответом и эталоном.
- [x] Первый шаг автоматической генерации контента: TUI сам определяет нехватку вопросов по выбранной теме, ставит `question` job в SQLite-очередь и запускает background worker без ручного `content-enqueue`/`content-worker`.
- [x] Сократить hardcoded seed до минимального bootstrap/fallback: один общий вопрос на тему, а не основная база учебного контента.
- [x] Расширить фоновую генерацию контента: добавить job types для `learning-material` и `system-design-scenario` поверх существующей SQLite-очереди.
- [x] Подключить автоматическую генерацию learning materials и system design scenarios к TUI: `/learn` и `/system-design` сами ставят нужные jobs без ручного CLI.
- [x] Улучшить TUI background worker: за один запуск обрабатывается несколько queued jobs, а готовые artifacts сразу отображаются в focused learning/system design экранах.
- [x] Добавить отдельное SQLite-хранение generated artifacts: `learning_materials` и `system_design_scenarios`.
- [x] Научить TUI повторно использовать сохраненные learning materials и system design scenarios без новой генерации.
- [x] Добавить TUI-поверхность `/materials`: список сохраненных learning materials/system design scenarios, выбор через `/material <id>` и `/scenario <id>`.
- [x] Добавить ручную регенерацию generated artifacts из TUI: `/regen-material` и `/regen-scenario`.
- [x] Улучшить daily practice в TUI: добавить явные статусы ответа/самооценки/AI feedback в центральной области.
- [x] Улучшить daily practice в TUI: добавить отдельный блок самооценки между ответом пользователя, эталоном и AI feedback.
- [x] Улучшить daily practice в TUI: показывать pending-блок самооценки между сохраненным ответом и эталоном на scoring-шаге.
- [x] Переформатировать roadmap в исполняемую очередь маленьких leaf-задач для `scripts/codex_roadmap_loop.sh`.
- [x] Улучшить daily practice в TUI: правая панель на practice-шагах показывает следующее действие и последние события без дублирования центрального ответа/feedback.
- [x] Learning mode: добавлены SQLite-модель и repository-методы для сохранения учебных диалогов по теме без подключения TUI.
- [x] Learning mode: учебные реплики пользователя и ИИ сохраняются через сервисный слой.
- [x] Learning mode: при входе в `/learn` TUI поднимает последние сохраненные реплики по текущей теме.
- [x] Learning mode: добавлена компактная навигация `/learn-older` и `/learn-newer` по длинному учебному диалогу в focused layout.
- [x] System design mode: transcript mock interview сохраняется через сервисный слой.
- [x] System design mode: секции `/req`, `/api`, `/data`, `/decision`, `/risk` сохраняются и восстанавливаются по scenario.
- [x] System design mode: явные artifact-команды из transcript автоматически сохраняются в persisted sections.
- [x] Learning mode: правая панель стала mode-specific и показывает следующий шаг, статус материала/диалога и последние события.
- [x] System design mode: правая панель стала mode-specific и показывает следующий шаг, статус scenario/artifacts/transcript и последние события.
- [x] `/materials`: правая панель стала mode-specific и показывает следующий шаг, контекст artifacts, команды и последние события.
- [x] `/materials`: добавлен фильтр current topic / all topics для learning materials.
- [x] `/materials`: добавлен фильтр current topic / all topics для system design scenarios.
- [x] `/materials`: добавлен preview полного artifact без входа в learning/system design режим.
- [x] `/materials`: добавлены per-topic версии artifacts и явный выбор latest/конкретной версии.
- [x] `/materials`: learning materials можно архивировать командой `/archive-material <id> confirm [reason]`; archived rows скрываются из списков/latest без физического удаления.
- [x] `/materials`: system design scenarios можно архивировать командой `/archive-scenario <id> confirm [reason]`; archived rows скрываются из списков/latest без физического удаления.
- [x] `/materials`: generated artifacts можно безопасно архивировать без физического удаления строк.
- [x] Content generation: service-level limits не дают поставить больше одной queued/running job на topic/kind.
- [x] Content generation: job payload хранит retry/backoff metadata без изменения SQLite-схемы.
- [x] Content generation: worker пропускает queued jobs до истечения retry backoff и берет следующий готовый job.
- [x] Content generation: TUI показывает компактный статус queued/running/failed jobs и последний done/failed generation result без открытия CLI.
- [x] Content generation: TUI service screen `/content` показывает queued/running/failed jobs с id, типом, темой, заметкой, retry/backoff metadata и ошибкой.
- [x] Content generation: TUI-команда `/retry-job <id>` возвращает failed job из `/content` в queued и запускает worker.
- [x] Content generation: TUI-команды `/pause-content` и `/resume-content` управляют embedded worker без удаления queued jobs.
- [x] Content generation: добавлен job type `reference-answer` для регенерации эталонных ответов существующих вопросов темы.
- [x] Curriculum: описаны domain-модели для curriculum topics/subtopics/objectives без изменения UI.
- [x] Curriculum: добавлены SQLite-таблицы и repository-методы сохранения curriculum topics/subtopics/objectives.
- [x] Curriculum: `generate-seed` сохраняет generated curriculum topics, learning objectives и subtopics поверх прежних topics/questions.
- [x] Curriculum: generated curriculum structure сохраняется идемпотентно по slug/source без дублей при повторном `generate-seed`.
- [x] Curriculum: добавлен сервис выбора следующей темы на основе curriculum order, давности ответов и self-score.
- [x] TUI: показывает предложенную следующую тему при старте practice.
- [x] TUI: добавлена команда `/accept-topic` для принятия предложенной темы без ручного выбора из списка.
- [x] Stats: добавлен service method для weak topics с учетом self-score, количества ответов и давности.
- [x] Practice: смешанные session-потоки выбирают следующий вопрос с приоритетом слабых тем.
- [x] Practice: слабые вопросы повторяются после заданного интервала.
- [x] TUI chat rendering: добавлен reusable renderer для реплик с role header, spacing, visual separator и escaping пользовательского Rich markup.
- [x] Learning mode: единый renderer применен к сохраненному диалогу, pending-сообщению и новым ответам ИИ.
- [x] System design mode: единый renderer применен к transcript mock interview, pending-сообщению кандидата и итоговому `/sd-feedback`.
- [x] Daily practice: единый renderer применен к `Твой ответ`, эталону и AI feedback в review-экране.
- [x] TUI markdown rendering: LLM-authored markdown отображается через Rich renderer в AI feedback, learning answers, system design replies и artifact previews.
- [x] TUI markdown rendering: добавлены regression-тесты на списки, code fences и заголовки из AI markdown в chat renderer.
- [x] TUI composer: однострочный input bar заменен на многострочный TextArea composer для practice/learning/system design с сохранением текущего submit flow.
- [x] TUI composer: Enter отправляет сообщение, а Shift+Enter вставляет перенос строки внутри ответа.
- [x] TUI composer: длинный draft виден в динамически расширяемой scrollable области перед отправкой.
- [x] TUI composer: быстрый ввод slash commands и выбор темы сохранены без ухудшения keyboard flow.
- [x] TUI composer: добавлены regression-тесты на многострочный ответ, Shift+Enter/newline и отправку code block в practice/learning/system design.
- [x] Questions: добавлена domain-модель tag и repository-методы для тегов.
- [x] TUI navigation: topics в левой колонке стали кликабельными на стартовом выборе темы для practice.
- [x] TUI navigation: добавлен regression-тест выбора practice topic кликом по строке topic в левой колонке.
- [x] TUI navigation: команды learn/practice/system-design стали кликабельными mode actions в TUI.
- [x] History browser: завершенную practice session можно открыть из `/history` и посмотреть вопрос, ответ, self-score, эталон и AI feedback.
- [x] History browser: `/history learning` показывает read-only список saved learning dialogs по topic/date.
- [x] History browser: выбранную группу saved learning dialog можно открыть из `/history learning <topic-id> <date>` и посмотреть сохраненные реплики read-only.
- [x] Learning persistence: learning dialog entries связаны с session/context metadata и различаются в history по dialog session id.
- [x] Notebook: добавлены domain-модель и SQLite-хранилище для AI explanation notes, привязанных к topic/subtopic/session/source message.
- [x] Notebook: AI-объяснения из learning mode автоматически сохраняются как notebook entries без ручного копирования.
- [x] Notebook: добавлен focused TUI-экран `/notebook` с навигацией по topic/subtopic и просмотром сохраненных AI explanations.
- [x] TUI navigation: залипание pre-topic кликов `Learn -> System Design -> Practice` зафиксировано expected-failure regression-тестом.
- [x] TUI navigation: переключение `learn`/`system-design`/`practice` через клики и slash-команды разворачивает текущий focused mode и не оставляет пользователя в learning после возврата к practice.
- [x] Learning mode: при входе в `learn` до выбора topic запускается новая topicless learning-сессия без восстановления topic-bound диалога из прошлой сессии.
- [x] Learning mode: добавлен regression-тест на `learn` before topic selection, чтобы не поднимался чужой сохраненный диалог.
- [x] Notebook discovery: стартовый/topic экран получил Notebook action и подсказку `/notebook`; при выбранной теме action открывает notebook entries этой темы.
- [x] Notebook discovery: history learning list/detail получил явный переход `/notebook topic <id>` к конспекту обучения соответствующей темы.
- [x] Notebook discovery: `/materials` показывает `/notebook topic <id>` для текущей темы и для темы каждого listed artifact.
- [x] Notebook discovery: `/notebook` в TUI подписан как конспект обучения с разбивкой по темам/subtopics.
- [x] Notebook: добавлены regression-тесты сохранения AI explanations и просмотра notebook entries по topic.
- [x] Questions: CLI `questions` показывает привязанные теги вопроса.
- [x] Questions: TUI показывает привязанные теги текущего вопроса в practice workflow.
- [x] Questions: CLI `questions` фильтрует список вопросов по slug тега.
- [x] Migrations: добавлена таблица `schema_version` и запись текущей версии схемы.
- [x] Migrations: создание таблиц вынесено в явные idempotent migration steps.
- [x] Migrations: добавлен regression-тест обновления legacy practice-only SQLite-базы до текущей схемы без потери старых данных.
- [x] Web UI: выделен read-only application facade для будущих adapter/smoke endpoints поверх существующих services.
- [x] Web UI: добавлен минимальный read-only WSGI smoke/dashboard adapter skeleton без замены TUI.
- [x] Ollama: default runtime переключен на `gemma4:e4b` с обновлением config/example/README и проверкой fallback path.
- [x] Competencies: первая senior competency taxonomy зафиксирована в `DEVELOPMENT_LOG.md` как contract для будущих models/seeds/readiness.
- [x] Competencies: добавлена domain-модель `Competency` с slug/title/description/category/level/order_index без подключения UI.
- [x] Competencies: добавлена SQLite-таблица `competencies` и idempotent seed базовых senior competencies.
- [x] Competencies: добавлены repository-методы list/upsert/get/find для competencies и unit-тесты.
- [x] Competencies: добавлена SQLite-связь `question_competencies` между question и competency с primary flag и weight.
- [x] Competencies: добавлены repository-методы для привязки competencies к вопросам и regression-тесты на чтение/перезапись связей.
- [x] Competencies: bootstrap/fallback seed привязывает стартовые вопросы к базовым senior competencies.
- [x] Competencies: CLI `questions` показывает competencies вопроса рядом с tags.
- [x] Competencies: TUI practice header показывает competencies текущего вопроса до текста вопроса.
- [x] Read facade: JSON-safe dashboard/questions snapshot включает competencies и question competency links без изменения web adapter.
- [x] Rubrics: senior answer rubric dimensions зафиксированы как contract для будущих models/storage/evaluation.
- [x] Rubrics: добавлены SQLite-таблицы для rubric dimensions, answer evaluations и per-dimension scores.
- [x] Rubrics: базовые rubric dimensions seed-ятся идемпотентно и доступны через repository API.
- [x] Rubrics: LLM evaluation prompt теперь требует JSON со score 1-5, evidence из ответа кандидата, gaps и next drills.
- [x] Rubrics: EvaluationService возвращает fallback heuristic evaluation при недоступной Ollama или невалидном JSON.
- [x] Rubrics: practice flow сохраняет structured answer evaluation после самооценки, не изменяя старый textual AI feedback.
- [x] Rubrics: TUI review-экран показывает сохраненные rubric scores после self-score и перед свободным AI feedback.
- [x] Rubrics: CLI-команда `evaluations --answer <id>` показывает сохраненную rubric evaluation для ответа.
- [x] Feedback evals: добавлен тестовый набор слабых ответов с reference-only claims, которые нельзя приписывать кандидату.
- [x] Feedback evals: `build_feedback_prompt` покрыт unit-тестом на evidence-only правила и candidate/reference теги.
- [x] Feedback evals: service-level guard помечает feedback как suspicious, если раздел `Хорошо` не содержит evidence из candidate answer.
- [x] Feedback evals: `feedback_quality_flags` сохраняются в payload последней structured evaluation без изменения старого feedback text.
- [x] Feedback evals: TUI показывает предупреждение в review-экране, если AI feedback помечен как fallback или suspicious.
- [x] Feedback evals: TUI-команда `/recheck-feedback` повторно запрашивает feedback для последнего ответа с более строгим prompt.
- [x] Feedback evals: regression-тест фиксирует низкие rubric scores для ответа "не знаю" и suspicious-flag для похвалы за эталонные пункты.
- [x] Sessions: добавлен статус сессии `completed`, `abandoned`, `in_progress` без потери совместимости со старыми rows.
- [x] Sessions: TUI при выходе без сохраненных ответов помечает practice session как `abandoned`.
- [x] Sessions: добавлена domain-модель `SessionOutcome` с summary, strengths, gaps, next_drills и readiness_delta.
- [x] Sessions: добавлено SQLite-хранилище session outcomes и repository-тесты.
- [x] Sessions: session outcome генерируется после завершения answered practice session на основе answers, self-score и rubric evaluations.
- [x] Sessions: TUI показывает session outcome на ended screen после `/quit` или истечения target time.
- [x] Sessions: TUI-команда `/finish-session` явно завершает текущую practice session и показывает outcome без выхода из TUI.
- [x] Sessions: `/history <session-id>` показывает сохраненный session outcome рядом с деталями ответов.
- [x] Sessions: CLI-команда `session-summary <id>` показывает сохраненный session outcome.
- [x] Stats: abandoned sessions исключены из основных stats/readiness counters, но остаются видимыми в recent session history со статусом.
- [x] Readiness: добавлен service `ReadinessService`, который агрегирует competencies, rubric scores, recency и answer coverage.
- [x] Readiness: добавлен расчет readiness score per competency с gap reasons по coverage, rubric score, recency и system design practice.
- [x] Readiness: добавлен overall senior readiness summary как evidence-based signal без абсолютной оценки кандидата.
- [x] Readiness: CLI `stats` показывает блок `Senior readiness` и top gaps с next action.
- [x] Readiness: TUI стартовый экран показывает блок `Today` с одним recommended drill и причиной выбора.
- [x] Readiness: TUI `/readiness` показывает focused dashboard по competencies, score, evidence count и next action.
- [x] Readiness: `/api/dashboard` read-only facade payload включает readiness snapshot с overall summary, recommended drill и per-competency aggregates.
- [x] Readiness: TUI `/readiness` и CLI `stats` показывают недельную динамику readiness delta по completed session outcomes, когда есть данные минимум за две недели.
- [x] Curriculum: CLI `curriculum-status` показывает counts generated curriculum и пустые зоны.
- [x] Curriculum: стартовый TUI-экран предупреждает, если generated curriculum отсутствует и база работает только на bootstrap/fallback.
- [x] Content generation: добавлен job type `curriculum`, который worker обрабатывает через idempotent curriculum import path.
- [x] Curriculum: TUI `/generate-curriculum` ставит background curriculum job и запускает worker.
- [x] Content quality: background question generation пропускает очевидные same-topic дубли через similarity check.
- [x] Content quality: generated questions получили source_quality/status foundation: pending_review, accepted, archived.
- [x] Content quality: CLI `questions-review` показывает pending generated questions и поддерживает accept/archive без удаления строк.
- [x] Content quality: TUI `/questions-review` показывает pending generated questions и поддерживает accept/archive без выхода в CLI.
- [x] Content quality: background question generation просит LLM вернуть tags/competencies и привязывает их к новым вопросам.
- [x] Content quality: archive generated material/scenario сохраняет optional reason из текста после `confirm`.
- [x] Content quality: duplicate background question не увеличивает question count.
- [x] System design: итоговый `/sd-feedback` сохраняется как отдельный feedback artifact с scenario/session metadata.
- [x] System design: добавлены отдельные rubric dimensions для system design senior workflow.
- [x] System design: transcript и artifacts оцениваются по system design rubric после `/sd-feedback` и сохраняются как structured evaluation.
- [x] System design: TUI показывает missing sections before feedback, если requirements/API/data/risks пустые.
- [x] System design: `/sd-checkpoint` дает короткую промежуточную interviewer-проверку без финального artifact/evaluation.
- [x] System design: `/sd-pressure` задает targeted pressure follow-up по capacity, hot keys, retries, idempotency, migrations и abuse protection без финального artifact/evaluation.
- [x] System design: TUI history показывает сохраненный final feedback и rubric scores через `/history system-design`.
- [x] System design: CLI `system-design-history` показывает saved scenarios, transcript, artifacts, final feedback и stored rubric scores.
- [x] System design: TUI artifact commands покрыты regression-тестом, что `/req`, `/api`, `/data`, `/decision`, `/risk` повышают итоговый rubric completeness score.
- [x] Notes: добавлено SQLite-хранилище manual notes с topic/session/context links и repository API.
- [x] Notes: TUI notes editor сохраняет draft в manual notes при смене режима и выходе без дублей по context.
- [x] Notes: TUI notes editor восстанавливает draft при возврате в session/topic/global context.
- [x] Notes: TUI `/save-note <title>` сохраняет multiline composer text как named manual note в текущем session/topic/global context.
- [x] Notes: `/notebook` показывает named manual notes рядом с AI explanations и скрывает internal notes drafts.
- [x] Notebook: `/notebook competency <slug>` фильтрует AI explanations и named manual notes по topics с linked competency questions.
- [x] Notebook: `/note-from-answer` сохраняет gap из последнего AI feedback как notebook entry текущей темы.
- [x] Notebook: notes editor draft покрыт regression-тестом на сохранение при TUI unmount и восстановление после повторного открытия SQLite-базы.
- [x] TUI Today: стартовый экран выбора темы заменен компактным Today panel с recommended drill, why now, expected time и primary action.
- [x] TUI Today: добавлена строка action buttons `Start Drill`, `Review Weak Answer`, `System Design Mock`, `Open Readiness`, `Notebook`.
- [x] TUI Today: Enter на стартовом экране запускает primary recommended drill, а ручной topic practice остается через ID темы или `/accept-topic`.

## Next

Работать сверху вниз. Каждый незакрытый checkbox ниже должен быть достаточно маленьким для одной итерации Codex loop.

### 0. User feedback: TUI navigation and learning entry

- [x] TUI navigation: воспроизвести и зафиксировать regression-тестом лаг/залипание при кликах `learn`/`system-design`/`practice` до выбора topic.
- [x] TUI navigation: исправить переключение `learn`/`system-design`/`practice`, чтобы клики и slash-команды всегда выходили из текущего focused mode без перезапуска приложения.
- [x] Learning mode: при входе в `learn` до выбора topic запускать новую свободную learning-сессию без восстановления последнего topic-bound диалога из прошлой сессии.
- [x] Learning mode: добавить regression-тест на `learn` before topic selection, чтобы не поднимался чужой сохраненный диалог.
- [x] Notebook discovery: сделать конспект обучения заметным из стартового/topic экрана, history и materials: явная action-кнопка/подсказка `/notebook` и переход к entries выбранной темы.
  - [x] Стартовый/topic экран: добавить явную Notebook action-кнопку и подсказку `/notebook`; при выбранной теме открывать notebook entries этой темы.
  - [x] History: добавить явный переход из history/learning dialog к notebook entries соответствующей темы.
  - [x] Materials: добавить явный переход из `/materials` к notebook entries текущей или выбранной темы.
- [x] Notebook discovery: подписать `/notebook` в UI как "конспект обучения" или "learning notebook", чтобы было понятно, где искать разбивку по топикам/темам.

### 1. Mode-aware TUI workflow

- [x] Daily practice: показать AI feedback по последнему ответу в центральной области рядом с вопросом, ответом и эталоном.
- [x] Daily practice: добавить явные статусы ответа/самооценки/AI feedback в центральной области.
- [x] Daily practice: добавить отдельный блок самооценки между ответом пользователя, эталоном и AI feedback.
- [x] Daily practice: показывать pending-блок самооценки между сохраненным ответом и эталоном на scoring-шаге.
- [x] Daily practice: сделать правую панель mode-specific на шагах ответа/самооценки/review, чтобы она показывала следующее действие и последние события, а не дублировала центральный контент.
- [x] Learning mode: добавить SQLite-модели и repository-методы для сохранения учебных диалогов по теме без подключения TUI.
- [x] Learning mode: сохранять реплики пользователя и ответы ИИ через сервисный слой.
- [x] Learning mode: при входе в `/learn` поднимать последние сохраненные реплики по текущей теме.
- [x] Learning mode: добавить компактную навигацию по длинному учебному диалогу в focused layout.
- [x] System design mode: добавить SQLite-модели и repository-методы для transcript и design artifacts без подключения TUI.
- [x] System design mode: сохранять transcript mock interview через сервисный слой.
- [x] System design mode: сохранять секции `/req`, `/api`, `/data`, `/decision`, `/risk` и восстанавливать их при возврате к scenario.
- [x] System design mode: добавить первый безопасный автоперенос явных artifact-команд из transcript в persisted sections.
- [x] Side panels: сделать правую панель mode-specific для learning mode вместо скрытой универсальной истории.
- [x] Side panels: сделать правую панель mode-specific для system design mode вместо скрытой универсальной истории.
- [x] Side panels: сделать правую панель mode-specific для `/materials` вместо скрытой универсальной истории.
- [x] TUI navigation: сделать topics в левой колонке кликабельными на стартовом выборе темы для practice, чтобы не вводить topic id вручную.
- [x] TUI navigation: добавить regression-тест выбора practice topic кликом по строке/кнопке topic в левой колонке.
- [x] TUI navigation: сделать команды `learn`, `practice`, `system-design` кликабельными действиями в UI, сохранив slash commands как быстрый keyboard fallback.
- [x] TUI navigation: добавить regression-тест выбора `learn`, `practice`, `system-design` кликом по UI-действию.

### 1A. Past sessions and learning notebook

- [x] History browser: добавить read-only экран со списком уже пройденных practice sessions по topic/session/date.
- [x] History browser: открывать пройденную practice session и показывать вопрос, ответ пользователя, self-score, эталон и AI feedback в режиме просмотра.
- [x] History browser: добавить просмотр сохраненных learning dialogs по topic/session/date, а не только последний диалог текущей темы.
  - [x] History browser: показать read-only список saved learning dialogs по topic/date на основе существующих timestamps.
  - [x] History browser: открыть выбранный learning dialog group и показать сохраненные реплики в read-only режиме.
- [x] Learning persistence: связать learning dialog entries с session/context metadata, чтобы можно было отличать разные учебные сессии по одной теме.
- [x] Notebook: добавить domain-модель и SQLite-хранилище для AI explanation notes, привязанных к topic/subtopic/session/source message.
- [x] Notebook: при ответах ИИ в learning mode сохранять полезные объяснения как notebook entries без ручного копирования.
- [x] Notebook: добавить TUI-экран тетради с навигацией по topic/subtopic и просмотром сохраненных AI explanations.
- [x] Notebook: добавить переход из стартового/topic экрана, history и materials к соответствующим notebook entries.
- [x] Notebook: добавить regression-тесты сохранения AI explanations и просмотра notebook entries по topic.

### 2. Generated artifacts surface

- [x] `/materials`: добавить фильтр current topic / all topics для learning materials.
- [x] `/materials`: добавить фильтр current topic / all topics для system design scenarios.
- [x] `/materials`: добавить preview полного artifact без входа в learning/system design режим.
- [x] `/materials`: показать версии artifact по теме и явно выбирать последнюю/конкретную версию.
- [x] `/materials`: добавить archive/delete для неудачных generated artifacts через repository и TUI-команду с защитой от случайного удаления.
  - [x] Learning materials: архивировать через repository и `/archive-material <id> confirm [reason]`, скрывая archived rows из списков/latest без физического удаления.
  - [x] System design scenarios: архивировать через repository и `/archive-scenario <id> confirm [reason]`, скрывая archived rows из списков/latest без физического удаления.

### 3. Background content lifecycle

- [x] Content generation: добавить service-level limits для количества queued/running jobs по topic/kind.
- [x] Content generation: добавить backoff/retry metadata в job payload без изменения схемы.
- [x] Content generation: учитывать backoff при выборе следующей queued job в worker.
- [x] Content generation: показывать в TUI компактный статус очереди и последний результат generation без открытия CLI.
- [x] Content generation: добавить TUI service screen `/content` со списком queued/running/failed jobs.
- [x] Content generation: добавить TUI-команду retry failed job из `/content`.
- [x] Content generation: добавить pause/resume флаг для TUI worker без удаления jobs.
- [x] Content generation: добавить job type для регенерации эталонных ответов.

### 4. LLM-generated curriculum lifecycle

- [x] Curriculum: описать domain-модели для curriculum topics/subtopics/objectives без изменения UI.
- [x] Curriculum: добавить repository-методы сохранения curriculum structure поверх существующих topics/questions.
- [x] Curriculum: расширить `generate-seed`, чтобы он сохранял learning objectives и subtopics, а не только topics/questions.
- [x] Curriculum: добавить idempotency для generated curriculum structure по slug/source.
- [x] Curriculum: добавить сервис выбора следующей темы на основе curriculum order, давности ответов и self-score.
- [x] TUI: показывать предложенную следующую тему при старте practice.
- [x] TUI: добавить команду принятия предложенной темы без ручного выбора из списка.

### 5. Chat readability and markdown rendering

- [x] TUI chat rendering: добавить единый renderer для реплик `Ты`/`ИИ` с явным role header, spacing и визуальным разделителем, без интерпретации пользовательского текста как Rich markup.
- [x] Learning mode: применить единый renderer к сохраненному диалогу, pending-сообщению и новому ответу ИИ.
- [x] System design mode: применить единый renderer к transcript mock interview и итоговому `/sd-feedback`.
- [x] Daily practice: применить единый renderer к `Твой ответ`, эталону и AI feedback в review-экране.
- [x] TUI markdown rendering: отображать markdown из LLM через Rich/Textual markdown renderer для AI feedback, learning answers, system design replies и artifact previews.
- [x] TUI markdown rendering: добавить regression-тесты на списки, code fences и заголовки из AI markdown, чтобы они не печатались как сырой markdown в чат-окне.
- [x] TUI composer: заменить однострочный input bar на многострочный composer для practice/learning/system design режимов.
- [x] TUI composer: сделать Enter отправкой сообщения, а Shift+Enter переносом строки внутри ответа.
- [x] TUI composer: показывать длинный черновик целиком или в scrollable/resizable области, чтобы перед отправкой были видны многострочные ответы и code snippets.
- [x] TUI composer: сохранить быстрый ввод slash commands и выбор темы без ухудшения текущего keyboard flow.
- [x] TUI composer: добавить regression-тесты на многострочный ответ, Shift+Enter/newline и отправку code block в practice/learning/system design.

### 6. Practice quality and spaced repetition

- [x] Stats: добавить service method для weak topics с учетом self-score, количества ответов и давности.
- [x] Practice: добавить выбор вопроса с приоритетом слабых тем.
- [x] Practice: добавить повторение слабых вопросов после заданного интервала.
- [x] Questions: добавить domain-модель tag и repository-методы для тегов.
- [x] Questions: добавить CLI/TUI отображение тегов вопроса.
  - [x] CLI: показывать привязанные теги в выводе `questions`.
  - [x] TUI: показывать привязанные теги текущего вопроса в practice workflow.
- [x] Questions: добавить фильтр вопросов по тегу.

### 7. Schema and platform foundations

- [x] Migrations: добавить таблицу schema_version и текущую версию схемы.
- [x] Migrations: вынести создание новых таблиц в явные idempotent migration steps.
- [x] Migrations: добавить тест обновления старой SQLite-базы до текущей схемы.
- [x] Web UI: выделить read-only application facade для будущего web UI поверх services.
- [x] Web UI: добавить минимальный smoke endpoint или adapter skeleton без замены TUI.

### 8. LLM runtime and local model migration

- [x] Ollama: переехать на локальную модель `gemma4:e4b` как основной runtime: обновить default config/example/README, проверить `llm-check` и сохранить fallback-поведение при недоступной модели.

### 9. Senior competency matrix

- [x] Competencies: зафиксировать первую senior competency taxonomy в `DEVELOPMENT_LOG.md`: Python runtime, async/concurrency, databases, distributed systems, system design, observability, testing/quality, debugging/incidents, communication/tradeoffs.
- [x] Competencies: добавить domain-модель `Competency` с slug/title/description/category/level/order_index без подключения UI.
- [x] Competencies: добавить SQLite-таблицу `competencies` и idempotent seed базовых senior competencies.
- [x] Competencies: добавить repository-методы list/upsert/get для competencies и покрыть их unit-тестами.
- [x] Competencies: добавить связь `question_competencies` между question и competency с весом или primary flag.
- [x] Competencies: добавить repository-методы для привязки competencies к вопросам и regression-тесты на чтение/перезапись связей.
- [x] Competencies: расширить bootstrap/fallback seed, чтобы стартовые вопросы получали базовые competency links.
- [x] Competencies: показывать competencies текущего вопроса в CLI `questions` рядом с tags.
- [x] Competencies: показывать competencies текущего вопроса в TUI practice header до текста вопроса.
- [x] Read facade: добавить competencies и question competencies в read-only JSON facade без изменения web UI.

### 10. Rubric-based answer evaluation

- [x] Rubrics: зафиксировать rubric dimensions для senior answers: correctness, depth, tradeoffs, production realism, failure modes, communication, evidence.
- [x] Rubrics: добавить domain-модели `RubricDimension`, `AnswerEvaluation` и `AnswerEvaluationScore` без UI.
- [x] Rubrics: добавить SQLite-таблицы для rubric dimensions и answer evaluations с привязкой к answer/session/question.
- [x] Rubrics: добавить idempotent seed базовых rubric dimensions и repository-тесты.
- [x] Rubrics: реализовать сервис `EvaluationService`, который принимает question, user_answer, reference_answer и возвращает structured scores.
- [x] Rubrics: обновить LLM prompt evaluation так, чтобы модель возвращала JSON со score 1-5, evidence из ответа кандидата, gaps и next drills.
- [x] Rubrics: добавить fallback evaluation, если Ollama недоступна или JSON невалиден.
- [x] Rubrics: сохранять evaluation после ответа в practice flow без удаления старого textual AI feedback.
- [x] Rubrics: показывать rubric scores в TUI review-экране после self-score и перед свободным AI feedback.
- [x] Rubrics: добавить CLI-команду `evaluations --answer <id>` для просмотра сохраненной rubric evaluation.

### 11. AI feedback quality gates

- [x] Feedback evals: добавить тестовый набор слабых ответов, где модель не должна приписывать кандидату несуществующие детали.
- [x] Feedback evals: добавить unit-тест на `build_feedback_prompt`, проверяющий наличие evidence-only правил и candidate/reference тегов.
- [x] Feedback evals: добавить service-level guard, который помечает feedback как suspicious, если в разделе "Хорошо" нет evidence из candidate answer.
- [x] Feedback evals: добавить сохранение `feedback_quality_flags` в evaluation payload без изменения старого feedback text.
- [x] Feedback evals: показывать предупреждение в TUI, если feedback помечен как fallback или suspicious.
- [x] Feedback evals: добавить команду `/recheck-feedback`, которая повторно запрашивает feedback для последнего ответа с более строгим prompt.
- [x] Feedback evals: добавить regression-тест, что короткий ответ "не знаю" получает низкие rubric scores и не получает похвалу за эталонные пункты.
- [x] Feedback evals: добавить README-раздел о том, что AI feedback является подсказкой, а readiness считается по rubric/evidence.

### 12. Session outcomes and practice loop

- [x] Sessions: добавить статус сессии `completed`, `abandoned`, `in_progress` без потери совместимости со старыми rows.
- [x] Sessions: при выходе из TUI без ответов помечать сессию как abandoned или не учитывать ее в readiness metrics.
- [x] Sessions: добавить domain-модель `SessionOutcome` с summary, strengths, gaps, next_drills и readiness_delta.
- [x] Sessions: добавить SQLite-хранилище session outcomes и repository-тесты.
- [x] Sessions: генерировать session outcome после завершения practice session на основе answers, self-score и rubric evaluations.
- [x] Sessions: показывать session outcome в TUI после `/quit` или завершения target time.
- [x] Sessions: добавить `/finish-session`, который явно завершает текущую practice session и показывает outcome без выхода из TUI.
- [x] Sessions: показывать outcome в `/history <session-id>` рядом с answer details.
- [x] Sessions: добавить CLI `session-summary <id>` для просмотра session outcome.
- [x] Stats: исключить abandoned sessions из основных readiness counters, но оставить их видимыми в history.

### 13. Readiness dashboard

- [x] Readiness: добавить service `ReadinessService`, который агрегирует competencies, rubric scores, recency и answer coverage.
- [x] Readiness: добавить расчет readiness score per competency с причинами: мало ответов, низкий score, давно не повторялось, нет system design практики.
- [x] Readiness: добавить расчет overall senior readiness summary без претензии на абсолютную оценку кандидата.
- [x] Readiness: расширить `stats` CLI блоком "Senior readiness" и списком top gaps.
- [x] Readiness: расширить TUI стартовый экран блоком "Today" с одним recommended drill и причиной выбора.
- [x] Readiness: добавить `/readiness` focused screen в TUI со списком competencies, score, evidence count и next action.
- [x] Readiness: добавить read facade endpoint data для readiness в `/api/dashboard`.
- [x] Readiness: добавить тесты на слабую тему с низкой rubric оценкой, которая должна стать первым recommended drill.
- [x] Readiness: добавить недельную динамику readiness по сессиям, если в базе есть достаточно данных.

### 14. Curriculum lifecycle and content quality

- [x] Curriculum: добавить команду `curriculum-status`, которая показывает количество curriculum topics/subtopics/objectives/questions и пустые зоны.
- [x] Curriculum: при старте TUI показывать warning, если generated curriculum отсутствует и база работает только на bootstrap/fallback.
- [x] Curriculum: добавить TUI action `/generate-curriculum`, который ставит безопасную фоновую задачу генерации curriculum starter pack.
  - [x] Content generation: добавить job type `curriculum` в content generation service вместо ручной CLI-зависимости от `generate-seed`.
  - [x] TUI: добавить slash-command `/generate-curriculum`, который ставит `curriculum` job и запускает worker.
- [x] Content quality: добавить similarity check для новых generated questions внутри topic, чтобы не сохранять очевидные дубли.
- [x] Content quality: добавить source_quality/status для generated questions: pending_review, accepted, archived.
- [x] Content quality: добавить CLI `questions-review` со списком pending generated questions и командами accept/archive.
- [x] Content quality: добавить TUI `/questions-review` read-only список pending generated questions с командами accept/archive.
- [x] Content quality: добавить LLM prompt для генерации tags/competencies вместе с новым вопросом.
- [x] Content quality: при archive generated material/scenario сохранять reason, если пользователь передал текст после `confirm`.
- [x] Content quality: добавить тесты, что duplicate background question не увеличивает question count.

### 15. System design senior workflow

- [x] System design: сохранять итоговый `/sd-feedback` как отдельный artifact с scenario_id/session metadata.
- [x] System design: добавить rubric dimensions для system design: requirements, API, data model, scaling, consistency, reliability, observability, tradeoffs.
- [x] System design: оценивать transcript и artifacts по system design rubric после `/sd-feedback`.
- [x] System design: показывать missing sections before feedback, если requirements/API/data/risks пустые.
- [x] System design: добавить command `/sd-checkpoint`, который дает короткий interviewer checkpoint без финальной оценки.
- [x] System design: добавить follow-up pressure questions по capacity, hot keys, retries, idempotency, migrations и abuse protection.
- [x] System design: показывать сохраненный final feedback и rubric scores в `/history` для system design sessions.
- [x] System design: добавить CLI `system-design-history` для просмотра сценариев, transcript, artifacts и feedback.
- [x] System design: добавить тест, что artifact-команды `/req`, `/api`, `/data`, `/decision`, `/risk` влияют на итоговый completeness score.

### 16. Notebook and persistent notes

- [x] Notes: добавить SQLite-хранилище manual notes с topic_id/session_id/context_type/context_id.
- [x] Notes: сохранять TUI notes editor при смене режима и при выходе из приложения.
- [x] Notes: восстанавливать notes editor при возврате в session/topic context.
- [x] Notes: добавить `/save-note <title>` для сохранения текущего composer text как notebook/manual note.
- [x] Notes: показывать manual notes вместе с AI notebook entries в `/notebook`.
- [x] Notebook: добавить фильтр `/notebook competency <slug>` после появления competency links.
- [x] Notebook: добавить команду `/note-from-answer`, которая сохраняет gap из последнего feedback как notebook entry.
- [x] Notebook: добавить тесты на сохранение notes при TUI unmount и повторном открытии базы.

### 17. TUI product UX: Today-first workflow

- [x] TUI Today: заменить стартовый текст выбора темы на компактный Today panel: recommended drill, why now, expected time, primary action.
- [x] TUI Today: добавить action buttons для `Start Drill`, `Review Weak Answer`, `System Design Mock`, `Open Readiness`, `Notebook`.
- [x] TUI Today: сделать Enter на старте запуском primary recommended drill, а ручной выбор темы оставить вторичным.
- [x] TUI Today: показать "why this drill" из ReadinessService, а не только topic recommendation reason.
- [x] TUI Today: добавить empty-state, если нет достаточных данных: предложить generate curriculum или первую baseline session.
- [x] TUI Today: добавить regression-тест keyboard flow Enter -> recommended drill.
- [x] TUI Today: добавить regression-тест клика по `Review Weak Answer`.
- [x] TUI Today: обновить command palette так, чтобы команды группировались по workflow, а не одним длинным списком.

### 18. TUI maintainability and async stability

- [x] TUI refactor: вынести pure render helpers из `ui/tui.py` в отдельный модуль без изменения поведения.
- [x] TUI refactor: вынести practice-mode state transitions в отдельный controller/service с тестами без Textual harness.
  - [x] Practice controller: вынести submit-routing для `select_topic`/`answering`/`scoring`/`answered` в pure helper без Textual harness.
  - [x] Practice controller: вынести reset/start-session state snapshot для новой practice session без изменения UI side effects.
  - [x] Practice controller: вынести answer -> scoring -> answered transition contract с тестами на self-score/next-question flow.
- [x] TUI refactor: вынести learning-mode state transitions в отдельный controller/service с тестами без Textual harness.
  - [x] Learning controller: вынести entry state snapshot для входа в `/learn` без изменения UI/storage side effects.
  - [x] Learning controller: вынести request/loading transition snapshot для отправки учебного вопроса.
  - [x] Learning controller: вынести finish-learning transition contract для ответа ИИ, transcript и fallback status.
- [x] TUI refactor: вынести system-design state transitions в отдельный controller/service с тестами без Textual harness.
  - [x] System design controller: вынести entry state snapshot для входа в `/system-design` без изменения UI/storage side effects.
  - [x] System design controller: вынести request/loading transition для кандидатского turn.
  - [x] System design controller: вынести finish-turn transition contract для interviewer reply, transcript и fallback status.
  - [x] System design controller: вынести checkpoint/pressure/final-feedback loading и finish transitions.
- [x] TUI refactor: вынести content worker orchestration из `InterviewPrepTUI` в отдельный класс.
  - [x] Content worker controller: вынести status/running/paused state и pause/resume/start guard в отдельный orchestration class без изменения thread/result side effects.
  - [x] Content worker controller: вынести worker loop/process-next-job orchestration из `start_background_content_worker()`.
  - [x] Content worker controller: вынести finish/result status transition из `finish_background_content_worker()`.
- [x] TUI stability: исправить RuntimeWarning `call_from_thread` в тестах background worker/system design flow.
- [x] TUI stability: добавить regression-тест, что TUI unmount не оставляет running worker state.
- [x] TUI stability: добавить smoke test для переключения Today -> Practice -> Learn -> System Design -> Readiness -> Practice.
- [x] TUI refactor: обновить `ROADMAP.md` и `DEVELOPMENT_LOG.md` после каждого выделения модуля, чтобы не терять поведенческий контракт.

### 19. Web/API foundations for future UI

- [x] Web API: добавить read-only endpoint `/api/readiness` поверх `ReadinessService`.
- [x] Web API: добавить read-only endpoint `/api/competencies` со score/coverage metadata.
- [x] Web API: добавить read-only endpoint `/api/sessions/<id>` для completed session detail и outcome.
- [x] Web API: добавить read-only endpoint `/api/notebook` с filters topic/competency/session.
- [x] Web API: добавить tests на query param validation для новых endpoints.
- [x] Web API: добавить simple HTML smoke page только как diagnostics, без замены TUI.
- [x] Web API: документировать adapter boundaries, чтобы будущий web UI не обращался напрямую к repository.

### 20. Calibration and real interview readiness

- [x] Calibration: добавить baseline session flow из 5 вопросов по разным competencies для первичной оценки.
  - [x] Baseline selection: добавить service-level план из 5 accepted questions по разным competencies без подключения TUI/session flow.
  - [x] Baseline session: добавить запуск baseline practice session, который использует выбранный service-level план.
  - [x] Baseline session: показывать baseline progress/remaining questions в TUI review flow.
  - [x] Baseline session: сохранять outcome marker/summary, чтобы readiness отличал первичную baseline-оценку от обычной practice.
- [x] Calibration: добавить mock senior interview mode, который смешивает coding/theory/system design/debugging без ручного выбора topic.
  - [x] Mock interview planning: добавить service-level deterministic plan, который выбирает accepted questions для coding/theory/system design/debugging без ручного выбора topic.
  - [x] Mock interview session: запускать mixed practice session из service-level mock interview plan.
  - [x] Mock interview TUI: добавить Today/readiness action для старта mock senior interview без ручного выбора topic.
  - [x] Mock interview progress: показывать текущую section и remaining sections в practice review flow.
- [x] Calibration: добавить "must fix before interview" список из top gaps с конкретными drills.
- [x] Calibration: добавить повторную baseline session через 7 дней и сравнение readiness delta.
  - [x] Baseline repeat status: service-level статус определяет последнюю completed baseline, due date через 7 дней и последний readiness delta.
  - [x] Baseline repeat action: Today/readiness показывает повторную baseline session как action, когда статус due.
  - [x] Baseline delta comparison: после repeat baseline сравнивать readiness delta с предыдущей baseline и показывать summary.
- [x] Calibration: добавить export `interview-report` в Markdown: strengths, gaps, evidence answers, next plan.
- [x] Calibration: добавить manual override для rubric score, чтобы пользователь мог исправить ошибочную AI-оценку.
  - [x] Manual override foundation: добавить audit-поля, service/repository update и CLI `evaluation-override` для одной rubric dimension.
  - [x] Manual override readiness: учитывать effective override score в readiness/session outcome/report surfaces.
- [x] Calibration: добавить tests, что manual override влияет на readiness, но сохраняет original AI score для аудита.

## Known limitations

- Notes editor в TUI сохраняет draft в `manual_notes` и восстанавливает его при возврате в session/topic/global context; именованные manual notes сохраняются через `/save-note` и видны в `/notebook`, но отдельного edit/delete flow для них пока нет.
- Learning dialog persistence сохраняет и восстанавливает последние реплики по теме; focused learning layout умеет листать длинный загруженный диалог компактными командами.
- Уже пройденные practice sessions видны в read-only `/history` с деталями ответов; session outcomes уже имеют SQLite/repository storage foundation, создаются автоматически для completed sessions с ответами и показываются на TUI ended screen и через `/finish-session`, но пока не показываются в history/CLI.
- AI-объяснения из learning mode и named manual notes уже доступны через `/notebook`; topic/subtopic/competency filters подключены, но edit/delete flow для named manual notes пока нет.
- System Design Mock Interview сохраняет transcript, design artifact sections, промежуточные `/sd-checkpoint` и `/sd-pressure` как interviewer transcript messages, итоговый feedback artifact, seeded system design rubric dimensions и structured rubric evaluation после `/sd-feedback`; TUI history показывает final feedback и rubric scores через `/history system-design`, а CLI `system-design-history` показывает saved scenarios, transcript, artifacts, feedback и rubric scores.
- В `infra/seed.py` остается минимальный bootstrap/fallback по одному общему вопросу на тему; полноценный generated curriculum lifecycle еще не стал first-run default.
- Generated curriculum structure из `generate-seed` сохраняется идемпотентно: topics переиспользуются по `slug`/`source`, subtopics — по parent/`slug`/`source`, objectives — по scope/text/source.
- Generated questions/materials/scenarios уже сохраняются; generated questions проходят консервативный same-topic duplicate check и pending review через CLI/TUI. Background generated questions уже получают автопривязку tags/known competencies из LLM metadata.
- TUI `/materials` уже показывает generated artifacts, версии artifacts внутри темы, latest/конкретный выбор, preview полного artifact без входа в другой режим, выбрать сохраненный material/scenario, фильтровать learning materials и system design scenarios по текущему контексту или всем темам, а также архивировать неудачные learning materials и system design scenarios через `/archive-material <id> confirm [reason]` и `/archive-scenario <id> confirm [reason]`.
- TUI `/content` уже показывает список queued/running/failed generation jobs, `/generate-curriculum` ставит background curriculum job, TUI worker можно ставить на паузу через `/pause-content`, возобновлять через `/resume-content` и безопасно возвращать failed job в queued через `/retry-job <id>`. CLI `content-enqueue --kind reference-answer` ставит регенерацию эталонных ответов существующих вопросов темы.
- TUI использует многострочный composer вместо однострочного input bar; Enter отправляет сообщение, Shift+Enter вставляет newline, а длинный draft расширяет composer до capped scrollable области.
- Теги вопросов уже хранятся в SQLite и отображаются в CLI `questions` и TUI practice workflow; CLI `questions --tag <slug>` фильтрует список вопросов по тегу.
- AI feedback зависит от доступности локальной Ollama; при недоступности после timeout возвращается fallback checklist.
- Статистика простая и пока не строит readiness dashboard, competency coverage и rubric-score динамику.
- Старый CLI `session` не спрашивает self-score и не участвует в новом rubric workflow; TUI остается основным интерфейсом practice.
