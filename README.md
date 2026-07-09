# TrainMe

Asystent głosowy: nagrywa usera (STT), odpowiada jego własnym sklonowanym głosem (XTTS v2) w jego stylu (agenci Teacher/Student na Ollama).

## Setup

```bash
uv sync
ollama serve
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

## Uruchomienie

```bash
cd trainme
python manage.py runserver
```

Bez działającego `ollama serve` appka nie wywala się — persona po prostu fallbackuje na echo (log ostrzeżenia w konsoli).

## Testy

```bash
# agenci (Teacher/Student/PersonaTrainer) — bez Django, bez Ollama
python -m unittest llm_engine.tests

# kuracja klipów głosowych — bez Django
python -m unittest tts_engine.tests

# Django (widoki, PersonaService, VoiceService)
cd trainme
python manage.py test
```

## Struktura

- `llm_engine/` — agenci Teacher/Student + pętla treningowa (`PersonaTrainer`), niezależne od Django.
- `tts_engine/` — `VoiceStore`: kuracja max kilku referencyjnych klipów głosu per user (nie trening — XTTS robi zero-shot cloning z listy plików), niezależne od Django.
- `trainme/home/persona_service.py` — spina agentów z per-userowymi plikami wiedzy `media/personas/user_<id>.json`.
- `trainme/home/voice_service.py` — spina `VoiceStore` z per-userowymi klipami w `tts_engine/voices/user_<id>/` (poza `media/` — to surowe dane głosowe, gitignored).
- `trainme/home/views.py`:
  - `speech_input` — generuje odpowiedź w stylu persony i syntezuje ją głosem usera (curated klipy jeśli są, inaczej bieżące nagranie).
  - `new_conversation` — przy końcu rozmowy: trenuje personę w tle (wątek) i kuruje najdłuższe nagranie z tej rozmowy do zestawu głosowego.
