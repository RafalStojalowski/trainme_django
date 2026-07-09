from django.conf import settings

from tts_engine.voice_store import DEFAULT_EMOTION, VoiceStore


class VoiceService:
    def __init__(self):
        self.store = VoiceStore(
            base_dir=settings.TTS_VOICES_DIR,
            max_clips=settings.TTS_VOICE_MAX_CLIPS,
        )

    def add_clip_for_user(self, user, wav_path, emotion=DEFAULT_EMOTION) -> list:
        return self.store.add_clip(user.id, wav_path, emotion=emotion)

    def get_reference_clips_for_user(self, user, emotion=DEFAULT_EMOTION) -> list:
        return self.store.get_reference_clips(user.id, emotion=emotion)
