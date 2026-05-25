from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import NamedTuple


DEFAULT_DB_PATH = Path("data/interview_prep.db")
CURRENT_SCHEMA_VERSION = 13


class MigrationStep(NamedTuple):
    name: str
    sql: str


MIGRATION_STEPS = (
    MigrationStep(
        "001_schema_version",
        """
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "002_core_practice_tables",
        """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    difficulty TEXT NOT NULL,
    prompt TEXT NOT NULL,
    hint TEXT NOT NULL,
    reference_answer TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'bootstrap',
    source_quality_status TEXT NOT NULL DEFAULT 'accepted'
        CHECK (source_quality_status IN ('pending_review', 'accepted', 'archived')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    target_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    user_answer TEXT NOT NULL,
    self_score INTEGER,
    ai_feedback TEXT,
    answered_at TEXT NOT NULL
);
""",
    ),
    MigrationStep(
        "003_curriculum_tables",
        """
CREATE TABLE IF NOT EXISTS curriculum_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    order_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS curriculum_subtopics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curriculum_topic_id INTEGER NOT NULL REFERENCES curriculum_topics(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT NOT NULL,
    order_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS curriculum_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curriculum_topic_id INTEGER NOT NULL REFERENCES curriculum_topics(id) ON DELETE CASCADE,
    curriculum_subtopic_id INTEGER REFERENCES curriculum_subtopics(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    order_index INTEGER NOT NULL
);
""",
    ),
    MigrationStep(
        "004_question_tag_tables",
        """
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS question_tags (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (question_id, tag_id)
);
""",
    ),
    MigrationStep(
        "005_content_generation_tables",
        """
CREATE TABLE IF NOT EXISTS content_generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "006_generated_artifact_tables",
        """
CREATE TABLE IF NOT EXISTS learning_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    archive_reason TEXT
);

CREATE TABLE IF NOT EXISTS system_design_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    scenario TEXT NOT NULL,
    focus_areas_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    archive_reason TEXT
);
""",
    ),
    MigrationStep(
        "007_learning_tables",
        """
CREATE TABLE IF NOT EXISTS learning_dialog_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    dialog_session_id TEXT,
    context_type TEXT,
    context_id TEXT,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notebook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    curriculum_subtopic_id INTEGER REFERENCES curriculum_subtopics(id) ON DELETE SET NULL,
    dialog_session_id TEXT,
    source_message_id INTEGER REFERENCES learning_dialog_messages(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "008_system_design_tables",
        """
CREATE TABLE IF NOT EXISTS system_design_transcript_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    scenario_id INTEGER REFERENCES system_design_scenarios(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('candidate', 'interviewer')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_design_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    scenario_id INTEGER REFERENCES system_design_scenarios(id) ON DELETE CASCADE,
    section TEXT NOT NULL CHECK (
        section IN ('requirements', 'api', 'data_model', 'decisions', 'risks')
    ),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "009_system_design_feedback_artifacts",
        """
CREATE TABLE IF NOT EXISTS system_design_feedback_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    scenario_id INTEGER REFERENCES system_design_scenarios(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "010_competency_tables",
        """
CREATE TABLE IF NOT EXISTS competencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    level TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "011_question_competency_tables",
        """
CREATE TABLE IF NOT EXISTS question_competencies (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    competency_id INTEGER NOT NULL REFERENCES competencies(id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    weight REAL NOT NULL DEFAULT 1.0 CHECK (weight > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (question_id, competency_id)
);
""",
    ),
    MigrationStep(
        "012_rubric_evaluation_tables",
        """
CREATE TABLE IF NOT EXISTS rubric_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    next_drills_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answer_evaluation_scores (
    evaluation_id INTEGER NOT NULL REFERENCES answer_evaluations(id) ON DELETE CASCADE,
    rubric_dimension_id INTEGER NOT NULL REFERENCES rubric_dimensions(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    evidence TEXT NOT NULL,
    gaps TEXT NOT NULL,
    next_drill TEXT,
    PRIMARY KEY (evaluation_id, rubric_dimension_id)
);
""",
    ),
    MigrationStep(
        "013_session_outcome_tables",
        """
CREATE TABLE IF NOT EXISTS session_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    outcome_type TEXT NOT NULL DEFAULT 'practice'
        CHECK (outcome_type IN ('practice', 'calibration_baseline')),
    summary TEXT NOT NULL,
    strengths_json TEXT NOT NULL DEFAULT '[]',
    gaps_json TEXT NOT NULL DEFAULT '[]',
    next_drills_json TEXT NOT NULL DEFAULT '[]',
    readiness_delta REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "014_system_design_rubric_tables",
        """
CREATE TABLE IF NOT EXISTS system_design_rubric_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "015_system_design_evaluation_tables",
        """
CREATE TABLE IF NOT EXISTS system_design_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_artifact_id INTEGER NOT NULL UNIQUE
        REFERENCES system_design_feedback_artifacts(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    scenario_id INTEGER REFERENCES system_design_scenarios(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    next_drills_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_design_evaluation_scores (
    evaluation_id INTEGER NOT NULL REFERENCES system_design_evaluations(id) ON DELETE CASCADE,
    system_design_rubric_dimension_id INTEGER NOT NULL
        REFERENCES system_design_rubric_dimensions(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    evidence TEXT NOT NULL,
    gaps TEXT NOT NULL,
    next_drill TEXT,
    PRIMARY KEY (evaluation_id, system_design_rubric_dimension_id)
);
""",
    ),
    MigrationStep(
        "016_manual_note_tables",
        """
CREATE TABLE IF NOT EXISTS manual_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    context_type TEXT,
    context_id TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""",
    ),
    MigrationStep(
        "017_indexes",
        """
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic_id);
CREATE INDEX IF NOT EXISTS idx_question_tags_question ON question_tags(question_id);
CREATE INDEX IF NOT EXISTS idx_question_tags_tag ON question_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_competencies_category_order
    ON competencies(category, order_index, id);
CREATE INDEX IF NOT EXISTS idx_question_competencies_question
    ON question_competencies(question_id);
CREATE INDEX IF NOT EXISTS idx_question_competencies_competency
    ON question_competencies(competency_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_question_competencies_primary
    ON question_competencies(question_id)
    WHERE is_primary = 1;
CREATE INDEX IF NOT EXISTS idx_curriculum_topics_source_order
    ON curriculum_topics(source, order_index, id);
CREATE INDEX IF NOT EXISTS idx_curriculum_topics_topic
    ON curriculum_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_subtopics_topic
    ON curriculum_subtopics(curriculum_topic_id, order_index, id);
CREATE INDEX IF NOT EXISTS idx_curriculum_objectives_topic
    ON curriculum_objectives(curriculum_topic_id, curriculum_subtopic_id, order_index, id);
CREATE INDEX IF NOT EXISTS idx_answers_session ON answers(session_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_content_jobs_status ON content_generation_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_learning_materials_topic ON learning_materials(topic_id, created_at);
CREATE INDEX IF NOT EXISTS idx_learning_dialog_messages_topic ON learning_dialog_messages(topic_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notebook_entries_topic
    ON notebook_entries(topic_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_notebook_entries_subtopic
    ON notebook_entries(curriculum_subtopic_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_notebook_entries_session
    ON notebook_entries(dialog_session_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_notebook_entries_source_message
    ON notebook_entries(source_message_id);
CREATE INDEX IF NOT EXISTS idx_manual_notes_topic
    ON manual_notes(topic_id, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_manual_notes_session
    ON manual_notes(session_id, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_manual_notes_context
    ON manual_notes(context_type, context_id, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_system_design_scenarios_topic ON system_design_scenarios(topic_id, created_at);
CREATE INDEX IF NOT EXISTS idx_system_design_transcript_topic
    ON system_design_transcript_messages(topic_id, scenario_id, created_at);
CREATE INDEX IF NOT EXISTS idx_system_design_artifacts_topic
    ON system_design_artifacts(topic_id, scenario_id, section, created_at);
CREATE INDEX IF NOT EXISTS idx_system_design_feedback_artifacts_topic
    ON system_design_feedback_artifacts(topic_id, scenario_id, session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_rubric_dimensions_order
    ON rubric_dimensions(order_index, id);
CREATE INDEX IF NOT EXISTS idx_system_design_rubric_dimensions_order
    ON system_design_rubric_dimensions(order_index, id);
CREATE INDEX IF NOT EXISTS idx_system_design_evaluations_topic
    ON system_design_evaluations(topic_id, scenario_id, session_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_system_design_evaluations_feedback
    ON system_design_evaluations(feedback_artifact_id);
CREATE INDEX IF NOT EXISTS idx_system_design_evaluation_scores_dimension
    ON system_design_evaluation_scores(system_design_rubric_dimension_id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_answer
    ON answer_evaluations(answer_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_session
    ON answer_evaluations(session_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_question
    ON answer_evaluations(question_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluation_scores_dimension
    ON answer_evaluation_scores(rubric_dimension_id);
CREATE INDEX IF NOT EXISTS idx_session_outcomes_created
    ON session_outcomes(created_at, id);
""",
    ),
)

SCHEMA = "PRAGMA foreign_keys = ON;\n\n" + "\n\n".join(step.sql.strip() for step in MIGRATION_STEPS)


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in MIGRATION_STEPS:
        connection.executescript(migration.sql)
    _record_schema_version(connection)
    _ensure_column(connection, "learning_materials", "archived_at", "TEXT")
    _ensure_column(connection, "learning_materials", "archive_reason", "TEXT")
    _ensure_column(
        connection,
        "questions",
        "source_quality_status",
        "TEXT NOT NULL DEFAULT 'accepted' CHECK (source_quality_status IN ('pending_review', 'accepted', 'archived'))",
    )
    _ensure_column(connection, "learning_dialog_messages", "dialog_session_id", "TEXT")
    _ensure_column(connection, "learning_dialog_messages", "context_type", "TEXT")
    _ensure_column(connection, "learning_dialog_messages", "context_id", "TEXT")
    _ensure_column(connection, "system_design_scenarios", "archived_at", "TEXT")
    _ensure_column(connection, "system_design_scenarios", "archive_reason", "TEXT")
    _ensure_column(
        connection,
        "sessions",
        "status",
        "TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned'))",
    )
    _ensure_column(
        connection,
        "session_outcomes",
        "outcome_type",
        "TEXT NOT NULL DEFAULT 'practice' CHECK (outcome_type IN ('practice', 'calibration_baseline'))",
    )
    _backfill_session_status(connection)
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_status_started
        ON sessions(status, started_at, id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_questions_source_quality_status
        ON questions(source_quality_status, source, topic_id, id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_dialog_messages_session
        ON learning_dialog_messages(dialog_session_id, created_at)
        """
    )
    connection.commit()


def _record_schema_version(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO schema_version (id, version)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            version = CASE
                WHEN schema_version.version < excluded.version THEN excluded.version
                ELSE schema_version.version
            END,
            applied_at = CASE
                WHEN schema_version.version < excluded.version THEN CURRENT_TIMESTAMP
                ELSE schema_version.applied_at
            END
        """,
        (CURRENT_SCHEMA_VERSION,),
    )


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    existing_columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _backfill_session_status(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE sessions
        SET status = CASE
            WHEN ended_at IS NOT NULL THEN 'completed'
            ELSE 'in_progress'
        END
        WHERE status IS NULL
           OR status = ''
           OR status NOT IN ('in_progress', 'completed', 'abandoned')
           OR (status = 'in_progress' AND ended_at IS NOT NULL)
        """
    )
