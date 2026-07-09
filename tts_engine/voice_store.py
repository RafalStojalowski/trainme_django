import shutil
import time
from pathlib import Path

DEFAULT_EMOTION = "neutral"


class VoiceStore:
    """Curates a small, capped set of reference audio clips per speaker for
    voice-cloning TTS (Coqui XTTS accepts speaker_wav as a list and averages
    the speaker embedding across all of them). This is NOT a trained model —
    there's no gradient descent here, just accumulating good reference samples
    and pruning the oldest once the cap is hit, refreshed once per finished
    conversation (mirroring how PersonaTrainer runs once per conversation).

    Clips are bucketed per emotion (subfolder per label, e.g. "excited",
    "calm") so callers can pick a reference set matching the tone they want to
    speak in; the cap applies per-bucket, not globally."""

    def __init__(self, base_dir, max_clips=3):
        self.base_dir = Path(base_dir)
        self.max_clips = max_clips

    def _emotion_dir(self, speaker_id, emotion) -> Path:
        d = self.base_dir / f"user_{speaker_id}" / emotion
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _clips(self, emotion_dir: Path):
        return sorted(emotion_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)

    def add_clip(self, speaker_id, source_wav_path, emotion=DEFAULT_EMOTION) -> list:
        """Copies source_wav_path into the speaker's reference set for `emotion`,
        pruning the oldest clip in that bucket once over max_clips. Returns the
        updated list of clip paths (str) for that bucket, oldest first."""
        emotion_dir = self._emotion_dir(speaker_id, emotion)
        dest = emotion_dir / f"{int(time.time() * 1000)}.wav"
        shutil.copyfile(source_wav_path, dest)

        clips = self._clips(emotion_dir)
        while len(clips) > self.max_clips:
            clips.pop(0).unlink(missing_ok=True)

        return [str(p) for p in clips]

    def get_reference_clips(self, speaker_id, emotion=DEFAULT_EMOTION) -> list:
        """Returns the speaker's current reference clips (str paths, oldest
        first) for `emotion`. Falls back to the neutral bucket if the
        requested emotion has no clips yet (and neutral does)."""
        clips = self._clips(self._emotion_dir(speaker_id, emotion))
        if not clips and emotion != DEFAULT_EMOTION:
            clips = self._clips(self._emotion_dir(speaker_id, DEFAULT_EMOTION))
        return [str(p) for p in clips]
