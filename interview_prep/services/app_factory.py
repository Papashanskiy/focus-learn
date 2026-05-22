from __future__ import annotations
from pathlib import Path

from interview_prep.infra.config import DEFAULT_CONFIG_PATH, load_config
from interview_prep.infra.database import DEFAULT_DB_PATH, connect, init_db
from interview_prep.infra.llm import OllamaClient, ResilientLLMClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.content_generation_service import ContentGenerationService
from interview_prep.services.curriculum_service import CurriculumService
from interview_prep.services.evaluation_service import EvaluationService
from interview_prep.services.question_service import QuestionService
from interview_prep.services.readiness_service import ReadinessService
from interview_prep.services.learning_service import LearningService
from interview_prep.services.read_facade import ReadOnlyApplicationFacade
from interview_prep.services.session_service import SessionService
from interview_prep.services.stats_service import StatsService
from interview_prep.services.system_design_service import SystemDesignService


class AppServices:
    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        config_path: str | Path | None = DEFAULT_CONFIG_PATH,
    ):
        self.config = load_config(config_path)
        self.connection = connect(db_path)
        self._closed = False
        init_db(self.connection)
        self.repository = SQLiteRepository(self.connection)
        self.repository.seed_defaults()
        self.llm = ResilientLLMClient(
            OllamaClient(
                model=self.config.ollama.model,
                base_url=self.config.ollama.base_url,
                timeout_seconds=self.config.ollama.timeout_seconds,
            )
        )
        self.content_generation = ContentGenerationService(self.repository, self.llm)
        self.curriculum = CurriculumService(self.repository, self.llm)
        self.questions = QuestionService(self.repository, self.llm)
        self.evaluations = EvaluationService(self.repository, self.llm)
        self.learning = LearningService(self.repository, self.llm)
        self.system_design = SystemDesignService(self.repository, self.llm)
        self.sessions = SessionService(self.repository, self.llm)
        self.stats = StatsService(self.repository)
        self.readiness = ReadinessService(self.repository)
        self.read = ReadOnlyApplicationFacade(
            questions=self.questions,
            sessions=self.sessions,
            stats=self.stats,
            learning=self.learning,
            content_generation=self.content_generation,
            curriculum=self.curriculum,
            repository=self.repository,
            readiness=self.readiness,
        )

    def close(self) -> None:
        if getattr(self, "_closed", True):
            return
        if hasattr(self, "repository"):
            self.repository.close()
        elif hasattr(self, "connection"):
            self.connection.close()
        self._closed = True

    def __del__(self) -> None:
        self.close()
