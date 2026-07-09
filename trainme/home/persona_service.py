import json
from pathlib import Path

from django.conf import settings

from llm_engine.agents import StudentAgent, empty_knowledge
from llm_engine.training import PersonaTrainer


class PersonaService:
    def __init__(self):
        self.trainer = PersonaTrainer(
            chat_model=settings.OLLAMA_MODEL,
            embed_model=settings.OLLAMA_EMBED_MODEL,
            max_iterations=settings.PERSONA_TRAIN_MAX_ITERATIONS,
            convergence_eps=settings.PERSONA_TRAIN_CONVERGENCE_EPS,
        )
        self.student = StudentAgent(model=settings.OLLAMA_MODEL)

    def _path(self, user) -> Path:
        return Path(settings.PERSONA_DIR) / f"user_{user.id}.json"

    def load_knowledge(self, user) -> dict:
        path = self._path(user)
        if not path.exists():
            return empty_knowledge()
        return json.loads(path.read_text(encoding="utf-8"))

    def train_for_user(self, user, session_text) -> float:
        knowledge, score, iterations = self.trainer.train(
            self.load_knowledge(user), session_text
        )
        self._path(user).write_text(
            json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"🧑‍🏫 Trening: {iterations} iteracji, score={score:.3f}")
        return score

    def generate_reply(self, user, user_text, history=None) -> str:
        return self.student.reply(self.load_knowledge(user), user_text, history)
