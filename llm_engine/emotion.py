from ollama import chat

EMOTION_LABELS = ("neutral", "excited", "calm", "serious", "sad")

_CLASSIFY_SYSTEM_PROMPT = """Oceń dominującą emocję poniższej wypowiedzi. Odpowiedz
WYŁĄCZNIE jednym słowem z tej listy, bez żadnego innego tekstu: neutral, excited,
calm, serious, sad."""


def classify_emotion(text, model="qwen3:8b") -> str:
    """Classifies the dominant emotion of `text` into one of EMOTION_LABELS.
    Falls back to "neutral" if the model returns anything outside that set —
    this is a cheap, best-effort label for bucketing voice reference clips,
    not something worth failing loudly over."""
    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    label = response.message.content.strip().lower()
    for candidate in EMOTION_LABELS:
        if candidate in label:
            return candidate
    return "neutral"
