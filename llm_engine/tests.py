"""Regression tests for the persona teacher/student agents and training loop.

Pure unittest (no Django dependency, matching llm_engine's design goal of being
usable outside the Django app). Ollama itself is never called — `chat`/`embed`
are mocked at the module boundary, so these run offline and fast, and are meant
to be re-run during future development to catch behavior regressions.

Run with:  python -m unittest llm_engine.tests   (from the repo root)
"""
import unittest
from unittest.mock import MagicMock, patch

from llm_engine.agents import (
    StudentAgent,
    TeacherAgent,
    TEACHER_SYSTEM_PROMPT,
    empty_knowledge,
    format_knowledge,
)
from llm_engine.emotion import EMOTION_LABELS, classify_emotion
from llm_engine.training import PersonaTrainer, cosine_similarity


def _chat_response(content):
    return MagicMock(message=MagicMock(content=content))


def _embed_response(vector):
    return MagicMock(embeddings=[vector])


class TeacherAgentTests(unittest.TestCase):
    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_parses_json_response(self, mock_chat):
        mock_chat.return_value = _chat_response(
            '{"vocabulary": ["siema"], "tone": [], "topics": [], "phrases": []}'
        )
        teacher = TeacherAgent(model="test-model")

        result = teacher.refine_knowledge(empty_knowledge(), "user said something")

        self.assertEqual(result, {"vocabulary": ["siema"], "tone": [], "topics": [], "phrases": []})
        kwargs = mock_chat.call_args.kwargs
        self.assertEqual(kwargs["model"], "test-model")
        messages = kwargs["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": TEACHER_SYSTEM_PROMPT})
        self.assertIn("user said something", messages[1]["content"])

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_tolerates_markdown_code_fence(self, mock_chat):
        mock_chat.return_value = _chat_response(
            '```json\n{"vocabulary": [], "tone": ["luźny"], "topics": [], "phrases": []}\n```'
        )
        teacher = TeacherAgent()

        result = teacher.refine_knowledge(empty_knowledge(), "session text")

        self.assertEqual(result["tone"], ["luźny"])

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_fills_in_missing_keys(self, mock_chat):
        mock_chat.return_value = _chat_response('{"vocabulary": ["cześć"]}')
        teacher = TeacherAgent()

        result = teacher.refine_knowledge(empty_knowledge(), "session text")

        self.assertEqual(result, {"vocabulary": ["cześć"], "tone": [], "topics": [], "phrases": []})

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_raises_on_unparseable_response(self, mock_chat):
        mock_chat.return_value = _chat_response("przepraszam, nie mogę pomóc")
        teacher = TeacherAgent()

        with self.assertRaises(ValueError):
            teacher.refine_knowledge(empty_knowledge(), "session text")

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_sends_existing_profile_as_json(self, mock_chat):
        mock_chat.return_value = _chat_response(
            '{"vocabulary": [], "tone": [], "topics": [], "phrases": []}'
        )
        teacher = TeacherAgent()
        existing = {"vocabulary": ["siema"], "tone": [], "topics": [], "phrases": []}

        teacher.refine_knowledge(existing, "session text")

        user_msg = mock_chat.call_args.kwargs["messages"][1]["content"]
        self.assertIn('"siema"', user_msg)

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_includes_feedback_when_previous_attempt_given(self, mock_chat):
        mock_chat.return_value = _chat_response(
            '{"vocabulary": [], "tone": [], "topics": [], "phrases": []}'
        )
        teacher = TeacherAgent()

        teacher.refine_knowledge(empty_knowledge(), "session text",
                                  last_student_reply="cześć, siema", last_score=0.42)

        user_msg = mock_chat.call_args.kwargs["messages"][1]["content"]
        self.assertIn("cześć, siema", user_msg)
        self.assertIn("0.420", user_msg)

    @patch("llm_engine.agents.chat")
    def test_refine_knowledge_omits_feedback_on_first_iteration(self, mock_chat):
        mock_chat.return_value = _chat_response(
            '{"vocabulary": [], "tone": [], "topics": [], "phrases": []}'
        )
        teacher = TeacherAgent()

        teacher.refine_knowledge(empty_knowledge(), "session text")

        user_msg = mock_chat.call_args.kwargs["messages"][1]["content"]
        self.assertNotIn("POPRZEDNIA PRÓBA", user_msg)


class StudentAgentTests(unittest.TestCase):
    @patch("llm_engine.agents.chat")
    def test_reply_renders_knowledge_dict_into_system_prompt(self, mock_chat):
        mock_chat.return_value = _chat_response("  odpowiedź  ")
        student = StudentAgent(model="test-model")
        knowledge = {"vocabulary": [], "tone": ["Luźny"], "topics": [], "phrases": []}

        result = student.reply(knowledge, "cześć")

        self.assertEqual(result, "odpowiedź")
        messages = mock_chat.call_args.kwargs["messages"]
        self.assertIn("Luźny", messages[0]["content"])
        self.assertEqual(messages[-1], {"role": "user", "content": "cześć"})

    @patch("llm_engine.agents.chat")
    def test_reply_with_empty_knowledge_uses_placeholder_text(self, mock_chat):
        mock_chat.return_value = _chat_response("ok")
        student = StudentAgent()

        student.reply(empty_knowledge(), "cześć")

        messages = mock_chat.call_args.kwargs["messages"]
        self.assertIn("Brak jeszcze danych", messages[0]["content"])

    @patch("llm_engine.agents.chat")
    def test_reply_includes_history_between_system_and_new_message(self, mock_chat):
        mock_chat.return_value = _chat_response("ok")
        student = StudentAgent()
        history = [("user", "hej"), ("assistant", "siema")]

        student.reply(empty_knowledge(), "co słychać", history=history)

        messages = mock_chat.call_args.kwargs["messages"]
        self.assertEqual(messages[1], {"role": "user", "content": "hej"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "siema"})
        self.assertEqual(messages[3], {"role": "user", "content": "co słychać"})

    @patch("llm_engine.agents.chat")
    def test_reply_with_no_history_sends_only_system_and_user(self, mock_chat):
        mock_chat.return_value = _chat_response("ok")
        student = StudentAgent()

        student.reply(empty_knowledge(), "cześć")

        messages = mock_chat.call_args.kwargs["messages"]
        self.assertEqual(len(messages), 2)


class ClassifyEmotionTests(unittest.TestCase):
    @patch("llm_engine.emotion.chat")
    def test_returns_recognized_label(self, mock_chat):
        mock_chat.return_value = _chat_response("excited")

        self.assertEqual(classify_emotion("Świetnie się bawię!"), "excited")

    @patch("llm_engine.emotion.chat")
    def test_extracts_label_from_extra_text(self, mock_chat):
        mock_chat.return_value = _chat_response("Emocja: calm.")

        self.assertEqual(classify_emotion("Wszystko w porządku."), "calm")

    @patch("llm_engine.emotion.chat")
    def test_falls_back_to_neutral_for_unrecognized_response(self, mock_chat):
        mock_chat.return_value = _chat_response("nie jestem pewien")

        self.assertEqual(classify_emotion("..."), "neutral")

    @patch("llm_engine.emotion.chat")
    def test_uses_given_model(self, mock_chat):
        mock_chat.return_value = _chat_response("sad")

        classify_emotion("Szkoda mi tego.", model="test-model")

        self.assertEqual(mock_chat.call_args.kwargs["model"], "test-model")

    def test_all_labels_are_lowercase_single_words(self):
        for label in EMOTION_LABELS:
            self.assertEqual(label, label.lower())
            self.assertNotIn(" ", label)


class FormatKnowledgeTests(unittest.TestCase):
    def test_renders_only_non_empty_sections(self):
        knowledge = {"vocabulary": ["siema"], "tone": [], "topics": [], "phrases": []}

        rendered = format_knowledge(knowledge)

        self.assertIn("inspiracja", rendered.lower())
        self.assertIn("- siema", rendered)
        self.assertNotIn("## Ton i styl", rendered)

    def test_empty_knowledge_renders_placeholder(self):
        self.assertEqual(format_knowledge(empty_knowledge()), "Brak jeszcze danych o rozmówcy.")

    def test_supports_partial_knowledge_for_future_selective_injection(self):
        # A future retrieval step would pass in only the most relevant items
        # across categories (not necessarily all four keys) — format_knowledge
        # must render that without requiring the full dict shape.
        partial = {"phrases": ["no wiesz"]}

        rendered = format_knowledge(partial)

        self.assertIn("- no wiesz", rendered)
        self.assertEqual(len(rendered.splitlines()), 2)


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors_have_similarity_one(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal_vectors_have_similarity_zero(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors_have_similarity_minus_one(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [-1, 0]), -1.0)

    def test_zero_vector_does_not_raise_and_returns_zero(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 1]), 0.0)


class PersonaTrainerTests(unittest.TestCase):
    """PersonaTrainer treats knowledge as an opaque value passed between the
    (mocked) teacher and student, so these tests use plain placeholder strings
    rather than real knowledge dicts — the trainer's convergence logic doesn't
    care about the storage format."""

    def _trainer(self, max_iterations=5, convergence_eps=0.02):
        return PersonaTrainer(max_iterations=max_iterations, convergence_eps=convergence_eps)

    @patch("llm_engine.training.embed")
    def test_stops_early_when_score_plateaus(self, mock_embed):
        trainer = self._trainer(max_iterations=5, convergence_eps=0.02)
        profiles = iter(["p1", "p2", "p3", "p4", "p5"])
        trainer.teacher.refine_knowledge = MagicMock(side_effect=lambda *a, **k: next(profiles))
        trainer.student.reply = MagicMock(return_value="reply")
        mock_embed.return_value = _embed_response([0.0])

        # iter1=0.5 (no prior score, can't converge yet) iter2=0.8 (delta .3, no)
        # iter3=0.81 (delta .01 < eps -> converge, stop after 3rd iteration)
        with patch("llm_engine.training.cosine_similarity", side_effect=[0.5, 0.8, 0.81, 0.9]):
            best_knowledge, best_score, iterations = trainer.train("initial", "session text")

        self.assertEqual(iterations, 3)
        self.assertAlmostEqual(best_score, 0.81)
        self.assertEqual(best_knowledge, "p3")

    @patch("llm_engine.training.embed")
    def test_runs_to_max_iterations_when_score_keeps_improving(self, mock_embed):
        trainer = self._trainer(max_iterations=3, convergence_eps=0.02)
        trainer.teacher.refine_knowledge = MagicMock(side_effect=lambda *a, **k: "profile")
        trainer.student.reply = MagicMock(return_value="reply")
        mock_embed.return_value = _embed_response([0.0])

        with patch("llm_engine.training.cosine_similarity", side_effect=[0.1, 0.3, 0.6]):
            best_knowledge, best_score, iterations = trainer.train("initial", "session text")

        self.assertEqual(iterations, 3)
        self.assertAlmostEqual(best_score, 0.6)

    @patch("llm_engine.training.embed")
    def test_keeps_best_knowledge_when_a_later_iteration_regresses(self, mock_embed):
        # convergence_eps=0 -> never plateaus early, so we get all 3 iterations
        # to confirm the best (not last) checkpoint is kept, gradient-descent-style.
        trainer = self._trainer(max_iterations=3, convergence_eps=0.0)
        profiles = iter(["p1", "p2", "p3"])
        trainer.teacher.refine_knowledge = MagicMock(side_effect=lambda *a, **k: next(profiles))
        trainer.student.reply = MagicMock(return_value="reply")
        mock_embed.return_value = _embed_response([0.0])

        with patch("llm_engine.training.cosine_similarity", side_effect=[0.9, 0.4, 0.5]):
            best_knowledge, best_score, iterations = trainer.train("initial", "session text")

        self.assertEqual(iterations, 3)
        self.assertEqual(best_knowledge, "p1")
        self.assertAlmostEqual(best_score, 0.9)

    @patch("llm_engine.training.embed")
    def test_teacher_receives_previous_reply_and_score_as_feedback(self, mock_embed):
        trainer = self._trainer(max_iterations=2, convergence_eps=0.0)
        trainer.teacher.refine_knowledge = MagicMock(side_effect=lambda *a, **k: "profile")
        trainer.student.reply = MagicMock(side_effect=["first reply", "second reply"])
        mock_embed.return_value = _embed_response([0.0])

        with patch("llm_engine.training.cosine_similarity", side_effect=[0.5, 0.6]):
            trainer.train("initial", "session text")

        first_call, second_call = trainer.teacher.refine_knowledge.call_args_list
        self.assertEqual(first_call.args, ("initial", "session text", None, None))
        self.assertEqual(second_call.args, ("profile", "session text", "first reply", 0.5))

    @patch("llm_engine.training.embed")
    def test_target_embedding_is_computed_once_from_session_text(self, mock_embed):
        trainer = self._trainer(max_iterations=2, convergence_eps=0.0)
        trainer.teacher.refine_knowledge = MagicMock(return_value="profile")
        trainer.student.reply = MagicMock(return_value="reply")
        mock_embed.return_value = _embed_response([0.0])

        trainer.train("initial", "session text")

        # 1 embed for the target (session_text) + 1 per iteration for the reply
        self.assertEqual(mock_embed.call_count, 1 + 2)
        mock_embed.assert_any_call(model=trainer.embed_model, input="session text")


if __name__ == "__main__":
    unittest.main()
