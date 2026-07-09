import math

from ollama import embed

from .agents import TeacherAgent, StudentAgent


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class PersonaTrainer:
    """Iteratively refines a user's persona knowledge doc, gradient-descent style:
    each iteration the Teacher rewrites the doc, the Student attempts a reply, and
    cosine similarity to the real session transcript scores how close the attempt
    got. Stops when the score plateaus (|delta| < convergence_eps) or after
    max_iterations, since this runs synchronously inside a request."""

    def __init__(self, chat_model="qwen3:8b", embed_model="nomic-embed-text",
                 max_iterations=5, convergence_eps=0.02):
        self.teacher = TeacherAgent(model=chat_model)
        self.student = StudentAgent(model=chat_model)
        self.embed_model = embed_model
        self.max_iterations = max_iterations
        self.convergence_eps = convergence_eps

    def _embed(self, text):
        return embed(model=self.embed_model, input=text).embeddings[0]

    def train(self, current_knowledge, session_text):
        target_emb = self._embed(session_text)
        knowledge = current_knowledge
        best_knowledge, best_score = knowledge, -1.0
        last_reply, last_score, prev_score = None, None, None
        iterations = 0

        for i in range(self.max_iterations):
            iterations = i + 1
            knowledge = self.teacher.refine_knowledge(
                knowledge, session_text, last_reply, last_score
            )
            reply = self.student.reply(knowledge, session_text)
            score = cosine_similarity(self._embed(reply), target_emb)

            if score > best_score:
                best_knowledge, best_score = knowledge, score

            converged = prev_score is not None and abs(score - prev_score) < self.convergence_eps
            last_reply, last_score, prev_score = reply, score, score
            if converged:
                break

        return best_knowledge, best_score, iterations
