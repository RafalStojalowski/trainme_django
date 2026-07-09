from pathlib import Path

import soundfile as sf
from django.conf import settings

from tts_engine.finetune import export_dataset, run_finetune

from .models import AudioRecord


class VoiceFinetuneService:
    def _run_dir(self, user) -> Path:
        return Path(settings.TTS_FINETUNE_DIR) / f"user_{user.id}"

    def training_samples_for_user(self, user):
        """(wav_path, text) pairs for every recording of this user's own voice.
        AudioRecord is only ever created for from_user messages (see
        speech_input in views.py), so the bot's synthesized replies never end
        up in here — no risk of training the clone on its own TTS output."""
        records = (
            AudioRecord.objects.filter(conversation__user=user)
            .select_related('text_message')
        )
        return [(r.wav_path, r.text_message.text) for r in records]

    def total_duration_seconds(self, user) -> float:
        total = 0.0
        for wav_path, _text in self.training_samples_for_user(user):
            try:
                total += sf.info(wav_path).duration
            except Exception:
                continue
        return total

    def is_ready(self, user, min_seconds=None) -> bool:
        threshold = min_seconds if min_seconds is not None else settings.TTS_FINETUNE_MIN_SECONDS
        return self.total_duration_seconds(user) >= threshold

    def finetune_user(self, user) -> Path:
        """Exports the user's full recording history and runs real GPU
        fine-tuning. Slow (real training) — call only from the management
        command, never from a web request."""
        samples = self.training_samples_for_user(user)
        run_dir = self._run_dir(user)
        train_csv, eval_csv = export_dataset(samples, run_dir)
        return run_finetune(
            train_csv, eval_csv, run_dir,
            language=settings.TTS_FINETUNE_LANGUAGE,
            num_epochs=settings.TTS_FINETUNE_EPOCHS,
            batch_size=settings.TTS_FINETUNE_BATCH_SIZE,
        )

    def checkpoint_dir_for_user(self, user) -> Path | None:
        """Latest fine-tuned checkpoint dir for this user, if any training run
        has completed (looks for a model checkpoint file under the run dir)."""
        run_dir = self._run_dir(user) / "run" / "training"
        if not run_dir.exists():
            return None
        candidates = sorted(
            (d for d in run_dir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if (candidate / "config.json").exists() and (
                (candidate / "best_model.pth").exists() or (candidate / "model.pth").exists()
            ):
                return candidate
        return None
