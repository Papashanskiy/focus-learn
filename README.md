# Interview Prep

Локальное терминальное Python-приложение для ежедневной 60-минутной подготовки middle+/senior Python backend-разработчика к собеседованиям.

## Цель продукта

Приложение должно снижать когнитивную нагрузку во время подготовки. Целевой сценарий: открыть TUI и сразу заниматься, без ручного управления генерацией материалов и без необходимости помнить служебные команды.

Текущий статус: технический MVP работает, но продуктовый UX еще развивается. В частности, в проекте остался только минимальный bootstrap/fallback набор тем и вопросов, а полноценный LLM-generated curriculum и focused TUI layout продолжают развиваться.

## Возможности

- SQLite-хранилище тем, вопросов, сессий и ответов.
- Минимальный bootstrap тем и fallback-вопросов по Python runtime, asyncio, БД, system design и engineering quality.
- Полноэкранный TUI workspace для ежедневной интерактивной сессии.
- Служебные CLI-команды для init/topics/questions/session/stats.
- Режим "только вопросы".
- Сохранение текстовых ответов, самооценки и истории сессий.
- Показ эталонного ответа после ответа пользователя.
- AI feedback на русском через локальную Ollama-модель `gemma4:e4b`.
- Fallback LLM на русском, если Ollama недоступна или не отвечает вовремя.
- Добавление своих вопросов из свободного текста через LLM-структурирование.
- TUI-режим System Design Mock Interview с ИИ-интервьюером и итоговым feedback.
- Markdown в AI feedback, учебных ответах, system design replies и preview generated artifacts отображается через Rich Markdown renderer.
- Генерация расширенного starter pack тем, subtopics, learning objectives и вопросов через локальную LLM командой `generate-seed`.
- Автоматическая фоновая генерация дополнительных вопросов из TUI, когда по выбранной теме мало контента.
- Статистика: сессии, ответы, последние сессии, динамика по темам.
- Read-only TUI history browser завершенных practice sessions по topic/session/date с просмотром вопроса, ответа, self-score, эталона и AI feedback; `/history learning` показывает saved learning dialogs по session/context, `/history learning <session-id>` открывает конкретный learning dialog read-only, `/history learning <topic-id> <YYYY-MM-DD>` оставлен для legacy-группировки по дате, а `/history system-design` показывает сохраненный final feedback и rubric scores system design mock sessions.
- Минимальный read-only WSGI adapter skeleton для будущего web UI: `/api/smoke`, `/api/dashboard`, `/api/readiness`, `/api/competencies`, `/api/sessions/<id>`, `/api/notebook` и health endpoints поверх существующего service facade.

## Установка

Требуется Python 3.11+; в текущем окружении проверено на Python 3.13.9.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m interview_prep init
```

Зависимости также указаны в `pyproject.toml`.

## Ollama

По умолчанию приложение обращается к:

```text
http://localhost:11434/api/generate
```

Модель по умолчанию:

```text
gemma4:e4b
```

Если Ollama не запущена или модель недоступна, приложение продолжит работать с fallback-ответами. Ответ пользователя и сессия сохраняются независимо от состояния LLM.

Проверка подключения:

```bash
python -m interview_prep llm-check
```

Настройки можно переопределить через переменные окружения:

```bash
INTERVIEW_PREP_OLLAMA_MODEL=gemma4:e4b
INTERVIEW_PREP_OLLAMA_BASE_URL=http://localhost:11434
INTERVIEW_PREP_OLLAMA_TIMEOUT=180
```

Или через локальный config-файл:

```bash
python -m interview_prep config-init
python -m interview_prep config-show
```

Файл по умолчанию: `config/interview_prep.toml`.
Пример есть в `config.example.toml`.
Переменные окружения имеют приоритет над config-файлом.

## Команды

Основной интерфейс:

```bash
python -m interview_prep tui
python -m interview_prep app
```

Инициализация базы:

```bash
python -m interview_prep init
```

Список тем:

```bash
python -m interview_prep topics
```

Режим "только вопросы":

```bash
python -m interview_prep questions
python -m interview_prep questions --topic 1
python -m interview_prep questions --tag concurrency
python -m interview_prep questions-audit
python -m interview_prep questions-cleanup accepted-generic
python -m interview_prep questions-source refresh --dry-run
python -m interview_prep questions-source candidates
python -m interview_prep questions-source auto-curate --dry-run
python -m interview_prep questions-source auto-curate
python -m interview_prep questions-source audit --status accepted
python -m interview_prep questions-source undo --question 42
python -m interview_prep questions-review
python -m interview_prep questions-review accept 42
python -m interview_prep questions-review archive 42
```

`questions-audit` — read-only диагностика качества базы вопросов. Команда выводит generic, duplicate и too-long prompts с `id`, `topic`, `source`, `source_quality` и текущим `status`, не меняя строки SQLite.

`questions-cleanup accepted-generic` архивирует только accepted generated-вопросы из источников `background-llm`/`llm-seed`, если audit помечает их как generic. Архивные и pending-review вопросы не попадают в practice selection.

`questions-source refresh --dry-run` показывает whitelisted source snapshot metadata (`url`, `retrieved_at`, `title`, checksum, category hints) для будущих source-backed candidates без записи в SQLite и без создания practice-вопросов. Без `--dry-run` команда сохраняет только metadata snapshots в отдельную таблицу; вопросы в practice не добавляются.

`questions-source candidates` преобразует сохраненные source snapshots в собственные source-backed candidate questions со статусом `pending_auto_review`, `source_url`, `source_retrieved_at`, category hints и frequency hint. Эти вопросы не попадают в practice loop, пока auto-curation не переведет high-confidence rows в `accepted`; `--dry-run` показывает candidates без записи.

`questions-source auto-curate --dry-run` классифицирует pending source-backed candidates как `auto_accepted`, `auto_archived` или `quarantined` по deterministic gates и показывает confidence, quality flags, rationale и source evidence без изменения SQLite. Запуск без `--dry-run` применяет deterministic decisions: `auto_accepted` переводит в `accepted`, `auto_archived` переводит в `archived`, а `quarantined` остается `pending_auto_review` вне practice до audit/undo flow. Опционально `--llm-curator` прогоняет quarantined candidates через strict JSON LLM rubric перед применением статусов; невалидный или low-confidence ответ безопасно оставляет вопрос в quarantine.

`questions-source audit [--question <id>] [--topic <id>] [--status accepted|archived|pending_auto_review]` read-only показывает сохраненные auto-curation decisions: previous/resulting/current status, source metadata/evidence, quality flags, curator model/version и rationale.

`questions-source undo [--question <id>]` безопасно откатывает последний matching auto-curation decision: команда восстанавливает previous status только если текущий status вопроса все еще равен audited resulting status. Audit row остается в SQLite для истории; если вопрос уже изменился вручную или другим decision, undo откажется перезаписывать status.

`questions-review` показывает generated questions со статусом `pending_review`. Команда `accept` переводит вопрос в `accepted`, а `archive` скрывает слабый generated question из будущего practice loop без удаления строки из SQLite.

Запуск ежедневной сессии:

```bash
python -m interview_prep session
python -m interview_prep session --topic 1 --minutes 60
```

Добавление вопроса из свободного текста:

```bash
python -m interview_prep add-question --topic 2 "Хочу вопрос про backpressure в asyncio worker"
```

Генерация расширенного starter pack через Ollama/fallback:

```bash
python -m interview_prep generate-seed --topics 3 --questions-per-topic 3
python -m interview_prep generate-seed --topics 2 --questions-per-topic 2 --dry-run
python -m interview_prep curriculum-status
```

`generate-seed` просит локальную LLM сгенерировать темы, subtopics, learning objectives, вопросы, подсказки, эталонные ответы и mock scenarios. При записи в SQLite темы создаются или обновляются по `slug`, curriculum topics/subtopics/objectives переиспользуются по slug/source или scope/text/source, а вопросы сохраняются без дублей по `topic/source/prompt`.

`curriculum-status` показывает read-only сводку generated curriculum: количество curriculum topics, subtopics, learning objectives, generated questions и пустые зоны, где не хватает subtopics/objectives/questions или база работает только на bootstrap/fallback.

Фоновая генерация контента:

```bash
python -m interview_prep content-enqueue --topic 1 "Вопрос про descriptors в ORM"
python -m interview_prep content-enqueue --topic 1 --kind learning-material "Разбор descriptors перед практикой"
python -m interview_prep content-enqueue --topic 4 --kind system-design-scenario "Mock interview про notification service"
python -m interview_prep content-enqueue --topic 1 --kind reference-answer "Освежи эталонные ответы темы"
python -m interview_prep content-jobs
python -m interview_prep content-worker --once --limit 1
python -m interview_prep content-retry 1
```

`content-enqueue` кладет задачу генерации в SQLite-очередь. Поддержанные типы:

- `question` — генерирует новый вопрос и сохраняет его с `source='background-llm'`;
- `learning-material` — генерирует учебный разбор темы и сохраняет его в `learning_materials`;
- `system-design-scenario` — генерирует scenario для mock interview и сохраняет его в `system_design_scenarios`;
- `reference-answer` — регенерирует эталонные ответы существующих вопросов выбранной темы, не меняя сами вопросы и подсказки.

`content-worker` можно запускать отдельным терминальным процессом; он берет queued jobs, вызывает Ollama/fallback и сохраняет результат. Для постоянной фоновой обработки запусти `content-worker` без `--once`.
Сервис генерации держит лимит активных задач: для одной пары topic/kind одновременно допускается не больше одной `queued` или `running` job.

В обычном TUI-flow ручной запуск этих команд не обязателен: при выборе темы приложение само проверяет, хватает ли вопросов, ставит `question` job и запускает background worker. При входе в `/learn` TUI сначала загружает последний сохраненный `learning_materials` для темы, а если его нет — ставит `learning-material` job. При входе в `/system-design` TUI сначала загружает последний сохраненный `system_design_scenarios`, а если его нет — ставит `system-design-scenario` job. Статус виден в верхней строке как `Content: ...`: TUI показывает состояние worker, компактные счетчики queued/running/failed и последний done/failed generation result. CLI-команды остаются для диагностики и ручного управления очередью.

В TUI также есть служебный экран `/content`: он показывает списки `queued`, `running` и `failed` background jobs с id, типом, темой, заметкой, retry/backoff metadata и ошибкой. Команда `/generate-curriculum` ставит безопасную фоновую `curriculum` job для starter pack и запускает TUI worker. TUI worker можно поставить на паузу через `/pause-content`, чтобы queued jobs остались в SQLite без обработки, и возобновить через `/resume-content`. Failed job можно вернуть в очередь прямо из TUI командой `/retry-job <id>`; команда использует тот же service-level retry flow, очищает stale backoff и запускает background worker, если worker не на паузе.

Статистика:

```bash
python -m interview_prep stats
```

Просмотр сохраненной rubric evaluation для ответа:

```bash
python -m interview_prep evaluations --answer 1
python -m interview_prep evaluation-override --evaluation 1 --dimension correctness --score 4 --reason "AI недооценила конкретику ответа"
```

`evaluation-override` сохраняет manual override для одной rubric dimension: в `evaluations` остается виден original AI score и причина ручной правки.

Просмотр сохраненного итога завершенной practice session:

```bash
python -m interview_prep session-summary 1
```

Markdown-отчет перед интервью по последней или выбранной completed session:

```bash
python -m interview_prep interview-report
python -m interview_prep interview-report --session 1
```

Просмотр сохраненной system design history:

```bash
python -m interview_prep system-design-history
python -m interview_prep system-design-history --scenario 1
python -m interview_prep system-design-history --feedback 1
```

Config:

```bash
python -m interview_prep config-init
python -m interview_prep config-show
python -m interview_prep --config config/interview_prep.toml tui
python -m interview_prep tui --config config/interview_prep.toml
```

Путь к базе можно передавать до или после подкоманды:

```bash
python -m interview_prep --db data/custom.db stats
python -m interview_prep stats --db data/custom.db
```

## Сессия

В TUI есть:

- верхняя строка со статусом темы, вопроса, времени и Ollama;
- обычный practice layout с левой панелью тем, центральной рабочей областью и правой панелью истории/feedback/notes;
- focused layout для learning и system design режимов: боковые панели скрываются, а основная работа переносится в центральную область;
- нижний многострочный composer для ответа и slash commands: Enter отправляет draft, Shift+Enter вставляет перенос строки, длинный draft расширяет composer до scrollable области.

Команды внутри TUI:

```text
/hint
/answer
/feedback
/recheck-feedback
/accept-topic
/commands
/content
/questions-review
/questions-review accept <id>
/questions-review archive <id>
/generate-curriculum
/history
/history <session-id>
/history learning
/history learning <session-id>
/history learning <topic-id> <YYYY-MM-DD>
/history system-design
/history system-design <feedback-id>
/notebook
/notebook all
/notebook topic <id>
/notebook subtopic <id>
/notebook competency <slug>
/notebook entry <id>
/save-note <title>
/note-from-answer
/readiness
/pause-content
/resume-content
/retry-job <id>
/materials
/materials current
/materials all
/materials scenarios current
/materials scenarios all
/preview-material <id|latest>
/material <id|latest>
/archive-material <id> confirm [reason]
/preview-scenario <id|latest>
/scenario <id|latest>
/archive-scenario <id> confirm [reason]
/learn
/learn-older
/learn-newer
/system-design
/sd-checkpoint
/sd-pressure
/sd-feedback
/req
/api
/data
/decision
/risk
/notes
/practice
/skip
/stats
/quit
```

Обычный текст без `/` считается ответом. После ответа TUI сохраняет ответ, просит самооценку `1-5`, показывает эталонный ответ и позволяет запросить feedback через `/feedback`; `/recheck-feedback` повторно запрашивает feedback для последнего ответа с более строгим prompt.
AI feedback по последнему ответу показывается в центральной области рядом с вопросом, твоим ответом и эталоном.

## AI feedback и readiness

AI feedback в приложении — это учебная подсказка, а не источник истины о готовности к senior-интервью. Он может помочь заметить пробелы, сформулировать следующий шаг и быстро перепроверить ответ, но его свободный текст может ошибаться или хвалить слишком широко.

Для оценки прогресса основной сигнал — structured rubric evaluation: score `1-5` по rubric dimensions, evidence из текста ответа кандидата, gaps и next drills. В TUI этот блок показывается после самооценки перед эталоном и свободным AI feedback; в CLI сохраненную rubric evaluation можно посмотреть через `python -m interview_prep evaluations --answer <id>`. Если feedback помечен как fallback или suspicious, TUI показывает предупреждение, а `/recheck-feedback` запрашивает более строгую перепроверку. После полезного feedback команда `/note-from-answer` сохраняет его gap в `/notebook` для повторения.

`/readiness` открывает focused dashboard по senior competencies: readiness score, количество evidence answers/rubric evaluations, coverage, причины gap, next action и список `Must fix before interview` с конкретными drills по top gaps.

`/questions-review` открывает focused TUI-экран pending generated questions. На нем можно принять полезный вопрос командой `/questions-review accept <id>` или архивировать слабый через `/questions-review archive <id>` без удаления строки из SQLite.

`/learn` включает учебный режим: обычный текст начинает диалог с ИИ по текущей теме или вопросу. Этот диалог не сохраняется как interview answer. При входе в режим приложение показывает последние сохраненные учебные реплики и последний учебный материал по теме или автоматически ставит фоновую задачу на генерацию материала; когда материал готов, он появляется в центральной области. Для длинного диалога доступны `/learn-older` и `/learn-newer`. `/practice` возвращает к прохождению вопросов.

`/notebook` открывает read-only тетрадь сохраненных AI explanations из learning mode, feedback gaps из `/note-from-answer` и named manual notes из `/save-note`. Доступны фильтры `/notebook topic <id>`, `/notebook subtopic <id>`, `/notebook competency <slug>`, `/notebook all` и просмотр одной AI-записи через `/notebook entry <id>`.

`/system-design` включает mock interview по проектированию сервиса. Обычный текст считается репликой кандидата, а ИИ отвечает как интервьюер: фиксирует ход решения, подсвечивает пробел и задает следующий вопрос. При входе в режим приложение показывает последний сохраненный system design scenario или автоматически ставит фоновую задачу на генерацию нового; если transcript еще пустой, готовый scenario заменяет дефолтный. `/sd <сценарий>` запускает режим со своим сценарием, `/sd-checkpoint` дает короткую промежуточную проверку без финальной оценки, `/sd-pressure` задает один pressure follow-up по capacity, hot keys, retries, idempotency, migrations или abuse protection, `/sd-feedback` генерирует итоговый feedback по senior-критериям, `/history system-design` показывает сохраненный final feedback и rubric scores, а CLI `system-design-history` показывает scenarios, transcript, artifacts, feedback и stored rubric scores. `/practice` возвращает к обычным вопросам.

`/materials` открывает focused-экран сохраненных generated artifacts. На нем доступны:

```text
/materials current
/materials all
/materials scenarios current
/materials scenarios all
/preview-material <id|latest>
/material <id|latest>
/archive-material <id> confirm [reason]
/preview-scenario <id|latest>
/scenario <id|latest>
/archive-scenario <id> confirm [reason]
/regen-material
/regen-scenario
```

`/materials current` показывает learning materials только для текущей темы, `/materials all` показывает learning materials по всем темам. `/materials scenarios current` показывает system design scenarios для текущего system design контекста, `/materials scenarios all` показывает scenarios по всем темам. Экран показывает версии artifacts внутри темы как `vN/total` и отмечает последнюю версию. `/preview-material <id|latest>` и `/preview-scenario <id|latest>` показывают полный artifact прямо на экране `/materials`, не входя в learning/system design режим. `/material <id|latest>` открывает сохраненный учебный материал в learning mode. `/archive-material <id> confirm [reason]` архивирует неудачный learning material, сохраняет optional reason и скрывает его из списков/latest без физического удаления строки. `/scenario <id|latest>` открывает сохраненный system design scenario в mock interview. `/archive-scenario <id> confirm [reason]` архивирует неудачный system design scenario, сохраняет optional reason и скрывает его из списков/latest без физического удаления строки. `/regen-material` и `/regen-scenario` ставят новую background job без выхода в CLI.

В system design mode можно фиксировать артефакты дизайна:

```text
/req SLA 99.9%, публичное чтение коротких ссылок
/api POST /links и GET /{code}
/data links(id, code, target_url, created_at)
/decision Redis cache для hot links
/risk hot keys, abuse и provider failures
```

Правая панель включает отдельный notes editor. Используй `/notes` или `Ctrl+N`, чтобы перейти к заметкам; `Esc` возвращает фокус в composer. Draft заметок сохраняется и восстанавливается для текущего session/topic/global context. Команда `/save-note <title>` сохраняет текст из multiline composer как named manual note: первая строка — команда с title, затем `Shift+Enter` и тело заметки; `/note-from-answer` сохраняет gap из последнего AI feedback как notebook entry текущей темы. Saved notes и feedback gaps видны в `/notebook` рядом с AI explanations. `Ctrl+P` или `/commands` показывает command palette со списком команд.

Старый CLI `session` оставлен для быстрых терминальных сценариев. В нем обычный ответ вводится одной строкой и завершается Enter. Для многострочного ответа сначала введи `/multi`, затем заверши ввод пустой строкой или строкой с одной точкой:

```text
My answer line 1
My answer line 2
.
```

## Тесты

Основной набор:

```bash
python -m unittest discover -s tests -v
```

Optional live smoke для Ollama:

```bash
RUN_OLLAMA_TESTS=1 python -m unittest discover -s tests -v
```

## Архитектура

- `interview_prep/domain` — сущности и простые бизнес-правила.
- `interview_prep/services` — сценарии приложения: сессии, вопросы, статистика, обучение, system design mock interview, генерация curriculum.
- `interview_prep/infra` — SQLite, bootstrap/fallback данные, generated artifacts, очередь фоновой генерации, Ollama/fallback LLM, репозиторий.
- `interview_prep/ui` — терминальный CLI.
- `tests` — тесты ключевой логики.

UI зависит от сервисов, сервисы зависят от репозитория и LLM-интерфейса, домен не зависит от инфраструктуры. Это позволяет позже добавить web UI или Textual TUI поверх тех же сервисов.

### Web adapter boundaries

Будущий web UI должен идти через `ReadOnlyApplicationFacade` или новые service-level use cases, а не обращаться к `SQLiteRepository` напрямую из adapter/view кода. Текущий WSGI adapter в `interview_prep/ui/web.py` остается тонким read-only слоем: он валидирует HTTP path/query params, выбирает facade method и сериализует JSON/HTML diagnostics.

Если web UI понадобится write-сценарий, сначала добавляется явный command/service method с тестами, затем adapter вызывает этот метод. Repository остается инфраструктурной зависимостью services/facades, а не частью web contract.
