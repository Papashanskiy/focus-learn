# Project Memory

## Назначение

`interview-prep` — локальное Python-приложение для ежедневной подготовки middle+/senior Python backend-разработчика к собеседованиям. Первая версия работает в терминале и хранит все данные локально в SQLite.

## Product direction

Проект больше не рассматривается как "просто MVP". Новые изменения должны проектироваться как качественные фичи, которые будут использоваться и развиваться дальше.

Главная цель приложения — уменьшить когнитивную нагрузку пользователя. Целевой сценарий: открыть приложение и заниматься. Пользователь не должен вручную помнить, какие служебные команды запустить, какие материалы сгенерировать и где искать следующий шаг.

LLM и фоновые процессы должны быть встроены в основной flow:

- приложение само предлагает, что учить дальше;
- приложение само готовит недостающие вопросы, объяснения и system design scenarios;
- пользователь видит понятные статусы, но не обязан управлять генерацией контента вручную;
- fallback должен сохранять работоспособность без потери учебного flow.

TUI должен адаптироваться к режиму работы. Текущая трехпанельная компоновка не считается финальной: в learning mode объяснение и диалог с ИИ должны занимать основное пространство экрана, а не правую панель при простаивающих остальных 2/3 интерфейса.

## Текущий статус

MVP реализован:

- CLI-команды для инициализации, тем, вопросов, сессий, добавления вопросов и статистики.
- TUI workspace через `python -m interview_prep tui` и alias `app`.
- Read-only WSGI adapter skeleton для будущего web UI поверх `services.read`: `/api/smoke`, `/api/dashboard`, `/api/readiness`, `/api/competencies`, `/api/sessions/<id>`, `/api/notebook`, `/health`; TUI остается основным интерфейсом.
- Нижний TUI input заменен на многострочный composer для ответов и slash commands; Enter отправляет текущий draft, Shift+Enter вставляет перенос строки внутри ответа, а длинный draft расширяет composer до capped scrollable области.
- Учебный TUI-режим `/learn` для разъяснений с ИИ без сохранения текста как interview answer; последние учебные реплики сохраняются, восстанавливаются по теме и листаются командами `/learn-older`/`/learn-newer`.
- TUI system design mode поддерживает `/sd-checkpoint`: короткую промежуточную проверку от интервьюера без создания final feedback artifact/evaluation, и `/sd-pressure`: targeted pressure follow-up по capacity, hot keys, retries, idempotency, migrations и abuse protection. Сохраненный final feedback и structured rubric scores доступны в TUI history через `/history system-design` и в CLI через `system-design-history`.
- TUI имеет scrollable панели, command palette `/commands` и notes editor `/notes`; draft заметок сохраняется и восстанавливается через `manual_notes` по session/topic/global context, а `/note-from-answer` сохраняет gap из последнего AI feedback в notebook.
- SQLite-схема и минимальный русскоязычный bootstrap/fallback стартовых тем и вопросов.
- LLM-generated starter pack доступен через `generate-seed`; команда сохраняет topics/questions и generated curriculum structure: curriculum topics, subtopics и learning objectives. Повторный запуск не дублирует curriculum structure: topics переиспользуются по `slug`/`source`, subtopics — по parent/`slug`/`source`, objectives — по scope/text/source. `infra/seed.py` больше не должен быть основной базой учебного контента.
- CLI `curriculum-status` показывает read-only покрытие generated curriculum: количество curriculum topics, subtopics, learning objectives, generated questions и пустые зоны bootstrap/fallback.
- Generated questions сохраняются со статусом `pending_review` и проходят review через CLI `questions-review` или TUI `/questions-review`; accept/archive меняет `source_quality_status` без удаления строки.
- `CurriculumService.suggest_next_topic()` выбирает следующую тему для practice: сначала первая новая тема по generated curriculum order, затем слабая тема по self-score, затем самая давно отвеченная тема.
- TUI показывает Today panel при старте: Enter запускает primary recommended drill, а конкретную рекомендованную practice-тему можно принять slash-командой `/accept-topic` или ручным выбором темы. `/readiness` дополнительно показывает `Must fix before interview` drills по top readiness gaps.
- Фоновая генерация контента есть через SQLite jobs, CLI-команды и автоматический TUI-flow: при выборе темы TUI может сам поставить `question` job, `/learn` ставит `learning-material`, `/system-design` ставит `system-design-scenario`, а служебный CLI может поставить `reference-answer` job для регенерации эталонных ответов темы; затем background worker обрабатывает несколько queued jobs.
- Service-level лимит фоновой генерации не дает иметь больше одной `queued`/`running` job на одну пару topic/kind; transient worker failures автоматически возвращаются в `queued` с retry/backoff metadata до `max_attempts`, а ручной retry failed job проходит через тот же лимит.
- Верхняя строка TUI показывает компактный status фоновой генерации: состояние worker, счетчики queued/running/failed и последний done/failed generation result без открытия CLI.
- TUI service screen `/content` показывает `queued`/`running`/`failed` background jobs с id, типом, темой, заметкой, retry/backoff metadata и ошибкой; TUI worker можно поставить на паузу через `/pause-content` без удаления queued jobs и возобновить через `/resume-content`; retryable failures отображаются как scheduled retry, а failed job после исчерпания попыток можно вернуть в очередь командой `/retry-job <id>` без выхода в CLI.
- TUI read-only экран `/history` показывает завершенные practice sessions по session id, topic, started/ended date, числу ответов и средней self-score; `/history <session-id>` открывает конкретную завершенную session и показывает вопрос, ответ пользователя, self-score, эталонный ответ и AI feedback; `/history learning` показывает saved learning dialogs по session/context, `/history learning <session-id>` открывает конкретный сохраненный learning dialog read-only, а `/history learning <topic-id> <YYYY-MM-DD>` оставлен для legacy-группировки по дате.
- Сервисный слой для сессий, вопросов, feedback и статистики.
- LLM-authored markdown в TUI отображается через Rich Markdown renderer для AI feedback, learning answers, system design replies и preview generated artifacts; пользовательский ввод по-прежнему escape-ится как обычный текст.
- Ollama-интеграция с default runtime `gemma4:e4b` и fallback-клиентом.
- Config-файл `config/interview_prep.toml` для Ollama model/base_url/timeout; env vars имеют приоритет.
- Тесты ключевых сценариев.

## Архитектура

- `domain`: dataclass-сущности `Topic`, `Question`, `Session`, `Answer`; правила сложности и совместимости старого nullable `self_score`.
- `services`: сценарии приложения без UI-логики.
- `infra`: SQLite connection/schema, repository, bootstrap/fallback данные, Ollama/fallback LLM.
- `ui`: CLI на стандартной библиотеке, Textual/Rich TUI и минимальный read-only WSGI adapter skeleton.
- `tests`: unittest-тесты сервисов и optional live Ollama smoke.

## Правила работы с проектом

- Использовать относительные пути в документации и командах.
- Не смешивать UI, БД и бизнес-логику.
- Новые сценарии сначала добавлять в `services`, затем подключать в `ui`.
- Все операции с SQLite должны идти через `SQLiteRepository`.
- Web adapter boundary: `interview_prep/ui/web.py` не должен обращаться к `SQLiteRepository` напрямую. Read-only endpoints идут через `ReadOnlyApplicationFacade`; будущие write endpoints должны сначала получить явный service/use-case method и только затем подключаться в adapter.
- LLM должна оставаться заменяемой через интерфейс `LLMClient`.
- Не добавлять новые hardcoded учебные материалы как основной путь развития. Hardcoded данные допустимы только как минимальный bootstrap/fallback; основной контент должен приходить из curriculum/generation pipeline.
- Фоновая генерация контента должна постепенно становиться автоматической частью приложения, а CLI-команды должны оставаться служебным интерфейсом для диагностики и ручного управления.
- `/content` — TUI-экран диагностики очереди фоновой генерации. Он показывает queued/running/failed jobs, retry/backoff metadata, поддерживает TUI-local pause/resume через `/pause-content` и `/resume-content` без удаления jobs, а также безопасный retry failed job через `/retry-job <id>`.
- `/questions-review` — TUI-экран проверки pending generated questions. Команды `/questions-review accept <id>` и `/questions-review archive <id>` должны идти через `QuestionService`, а не обновлять SQLite напрямую.
- `/history` — read-only TUI-экран завершенных practice sessions. `/history <session-id>` открывает детали конкретной завершенной practice session без изменения active practice state. `/history learning` показывает saved learning dialogs по session/context; `/history learning <session-id>` открывает конкретный saved learning dialog read-only; `/history learning <topic-id> <YYYY-MM-DD>` остается legacy-группировкой по дате. `/history system-design` показывает сохраненные system design final feedback artifacts и rubric scores; `/history system-design <feedback-id>` открывает конкретный feedback read-only. CLI `system-design-history` показывает saved scenarios, transcript, artifacts, final feedback и stored rubric scores для диагностики без запуска TUI.
- `/notebook` — read-only TUI-экран сохраненных AI explanations из learning mode, feedback gaps из `/note-from-answer` и named manual notes из `/save-note`. Он показывает notebook entries/manual notes, навигацию по topics/subtopics и поддерживает `/notebook all`, `/notebook topic <id>`, `/notebook subtopic <id>`, `/notebook competency <slug>`, `/notebook entry <id>` для AI-записей.
- Generated artifacts должны быть переиспользуемыми. `learning-material` сохраняется в `learning_materials`, `system-design-scenario` сохраняется в `system_design_scenarios`, а TUI подхватывает последние сохраненные записи перед постановкой новой job.
- TUI `/materials` показывает сохраненные generated artifacts, умеет переключать learning materials между текущей темой и всеми темами через `/materials current`/`/materials all`, переключать system design scenarios через `/materials scenarios current`/`/materials scenarios all`, показывает per-topic версии artifacts, preview полного artifact через `/preview-material <id|latest>`/`/preview-scenario <id|latest>`, `/material <id|latest>` открывает учебный материал, `/archive-material <id> confirm` архивирует неудачный learning material и скрывает его из списков/latest без физического удаления строки, `/scenario <id|latest>` открывает system design scenario, `/archive-scenario <id> confirm` архивирует неудачный system design scenario и скрывает его из списков/latest без физического удаления строки, `/regen-material` и `/regen-scenario` ставят ручную регенерацию.
- Следующий UX-шаг для artifacts — удаление/архивация и отдельный экран управления очередью.
- Настройки Ollama читать через `infra.config.load_config()`, не дублировать env parsing в UI или services.
- Если Ollama недоступна, приложение не должно терять пользовательский ответ.
- Пользовательский flow ведется на русском; AI prompts и fallback тоже должны отвечать на русском.
- Самооценка убрана из старой CLI-сессии, но используется в TUI и сохраняется в `self_score`.
- `/learn` должен оставаться учебным режимом: не оценивать пользователя и не писать учебные вопросы в таблицу `answers`.
- При изменении TUI приоритет у focused workflow: в каждом режиме основной экран должен показывать то, чем пользователь сейчас занимается.
- Notes editor сохраняет и восстанавливает один draft на session/topic/global context через `manual_notes`; именованные ручные заметки из `/save-note` и feedback gaps из `/note-from-answer` показываются в `/notebook`, а internal draft rows там скрыты.
- После крупных изменений обновлять `DEVELOPMENT_LOG.md` и `ROADMAP.md`.

## Команды проверки

```bash
python -m compileall interview_prep
python -m unittest discover -s tests -v
python -m interview_prep init
python -m interview_prep tui
python -m interview_prep stats
python -m interview_prep llm-check
python -m interview_prep config-show
```

Optional:

```bash
RUN_OLLAMA_TESTS=1 python -m unittest discover -s tests -v
```
