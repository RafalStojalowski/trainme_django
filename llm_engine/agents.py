import json
import re

from ollama import chat

KNOWLEDGE_KEYS = ("vocabulary", "tone", "topics", "phrases")

_SECTION_TITLES = {
    "vocabulary": "Przykładowe słowa/frazy (inspiracja, NIE ograniczaj się do nich)",
    "tone": "Ton i styl",
    "topics": "Tematy",
    "phrases": "Charakterystyczne zwroty (użyj, jeśli pasują — nie na siłę)",
}

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

TEACHER_SYSTEM_PROMPT = """Jesteś "nauczycielem", który buduje i aktualizuje strukturalny
profil sposobu mówienia jednej, konkretnej osoby na podstawie transkrypcji jej wypowiedzi.
Otrzymujesz ISTNIEJĄCY profil (JSON) oraz NOWĄ transkrypcję z najnowszej sesji (czasem też
poprzednią próbę ucznia i wynik podobieństwa do transkryptu).

Zwróć WYŁĄCZNIE poprawny JSON (bez bloków kodu markdown, bez komentarza) z DOKŁADNIE tymi
czterema kluczami, każdy jako lista krótkich stringów po polsku:
{"vocabulary": [...], "tone": [...], "topics": [...], "phrases": [...]}
- vocabulary: charakterystyczne słowa i frazy
- tone: obserwacje o tonie, tempie, stylu wypowiedzi
- topics: poruszane tematy
- phrases: powtarzalne, charakterystyczne zwroty

Scal nowe obserwacje z istniejącymi, usuwaj przestarzałe/zduplikowane wpisy, każda lista
maks. 15 elementów. Jeśli dostałeś poprzednią próbę ucznia i wynik podobieństwa, popraw
profil tak, aby uczeń w kolejnej próbie brzmiał BARDZIEJ podobnie do transkryptu."""

STUDENT_SYSTEM_PROMPT_HEADER = """Jesteś cyfrowym bliźniakiem (digital twin) osoby opisanej
poniższym profilem. Twój PRIORYTET to sensowna, trafna odpowiedź na to, co mówi rozmówca —
dopiero potem styl. Profil to inspiracja (ton, tempo, ulubione tematy i zwroty), a NIE
lista słów, do której musisz się ograniczać — nie wciskaj fraz z profilu na siłę, gdy nie
pasują do kontekstu; używaj normalnego, pełnego słownictwa polskiego, kiedy trzeba.
Odpowiadaj PO POLSKU, krótko i naturalnie (1-3 zdania, jak w rozmowie telefonicznej),
bez wyjaśnień, że jesteś AI.

PROFIL ROZMÓWCY (inspiracja stylu, nie ograniczenie słownictwa):
"""


def empty_knowledge() -> dict:
    """Fresh, empty persona knowledge dict matching KNOWLEDGE_KEYS."""
    return {key: [] for key in KNOWLEDGE_KEYS}


def _normalize_knowledge(data: dict) -> dict:
    return {key: list(data.get(key) or []) for key in KNOWLEDGE_KEYS}


def _parse_knowledge_json(raw: str) -> dict:
    """Extracts a JSON object from the model's reply, tolerating stray text or
    markdown code fences around it (models don't always follow "JSON only")."""
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        raise ValueError(f"Model nie zwrócił JSON-a z profilem: {raw[:200]!r}")
    return _normalize_knowledge(json.loads(match.group(0)))


def format_knowledge(knowledge: dict) -> str:
    """Renders a (possibly partial/filtered) knowledge dict as prompt text.
    Callers can pass a subset of items (e.g. only the most relevant ones for
    the current turn) without any change needed here."""
    sections = []
    for key in KNOWLEDGE_KEYS:
        items = knowledge.get(key) or []
        if not items:
            continue
        bullet_list = "\n".join(f"- {item}" for item in items)
        sections.append(f"## {_SECTION_TITLES[key]}\n{bullet_list}")
    return "\n\n".join(sections) if sections else "Brak jeszcze danych o rozmówcy."


class TeacherAgent:
    def __init__(self, model="qwen3:8b"):
        self.model = model

    def refine_knowledge(self, current_knowledge, session_text,
                          last_student_reply=None, last_score=None):
        feedback = ""
        if last_student_reply is not None:
            feedback = (
                f"\n\nPOPRZEDNIA PRÓBA UCZNIA: {last_student_reply}\n"
                f"PODOBIEŃSTWO DO PRAWDZIWEJ WYPOWIEDZI (0-1): {last_score:.3f}\n"
                "Popraw profil tak, aby uczeń brzmiał BARDZIEJ podobnie do transkryptu."
            )
        response = chat(
            model=self.model,
            messages=[
                {"role": "system", "content": TEACHER_SYSTEM_PROMPT},
                {"role": "user", "content":
                    f"ISTNIEJĄCY PROFIL (JSON):\n{json.dumps(current_knowledge, ensure_ascii=False)}\n\n"
                    f"TRANSKRYPT SESJI:\n{session_text}{feedback}"},
            ],
        )
        return _parse_knowledge_json(response.message.content)


class StudentAgent:
    def __init__(self, model="qwen3:8b"):
        self.model = model

    def reply(self, knowledge, user_text, history=None):
        system_prompt = STUDENT_SYSTEM_PROMPT_HEADER + format_knowledge(knowledge)
        messages = [{"role": "system", "content": system_prompt}]
        for role, content in (history or []):
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        response = chat(model=self.model, messages=messages)
        return response.message.content.strip()
