import os
import uuid
from pathlib import Path


def _patch_torchaudio_load():
    """Replace torchaudio.load with a soundfile backend to avoid torchcodec/FFmpeg dependency."""
    import torchaudio
    import soundfile as sf
    import torch
    import numpy as np

    def _sf_load(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, **kwargs):
        frames = num_frames if num_frames != -1 else -1
        data, sample_rate = sf.read(
            str(uri),
            start=frame_offset,
            frames=frames,
            always_2d=True,
            dtype='float32',
        )
        # soundfile: (frames, channels) → torch audio: (channels, frames)
        tensor = torch.from_numpy(
            data.T.copy() if channels_first else data.copy()
        )
        return tensor, sample_rate

    torchaudio.load = _sf_load


_patch_torchaudio_load()


class TTSService:
    def __init__(self):
        self._tts = None
        self._finetuned = {}

    def _load(self):
        if self._tts is None:
            import torch
            from TTS.api import TTS
            # PyTorch 2.6 changed torch.load default to weights_only=True, which
            # breaks Coqui TTS checkpoint loading. Patch for the duration of load.
            _orig = torch.load
            torch.load = lambda *a, **kw: _orig(*a, **{**{'weights_only': False}, **kw})
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"🔊 Ładowanie XTTS v2 na {device}...")
                self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
                if device == "cuda":
                    print(f"✅ XTTS v2 załadowany na GPU: {torch.cuda.get_device_name(0)}")
                else:
                    print("✅ XTTS v2 załadowany na CPU")
            finally:
                torch.load = _orig
        return self._tts

    def _load_finetuned(self, checkpoint_dir: str):
        """Lazily loads (and caches) a per-user fine-tuned Xtts checkpoint —
        this is a full, separate model instance, not a delta applied to the
        base model (fine-tuning only touches GPT weights, but the saved
        checkpoint is still a complete Xtts state)."""
        if checkpoint_dir not in self._finetuned:
            import torch
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts

            _orig = torch.load
            torch.load = lambda *a, **kw: _orig(*a, **{**{'weights_only': False}, **kw})
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"🔊 Ładowanie fine-tunowanego głosu z {checkpoint_dir} na {device}...")
                config = XttsConfig()
                config.load_json(str(Path(checkpoint_dir) / "config.json"))
                model = Xtts.init_from_config(config)
                model.load_checkpoint(config, checkpoint_dir=str(checkpoint_dir), use_deepspeed=False)
                model.to(device)
                self._finetuned[checkpoint_dir] = model
                print("✅ Fine-tunowany głos załadowany")
            finally:
                torch.load = _orig
        return self._finetuned[checkpoint_dir]

    def synthesize(self, text: str, speaker_wav, finetuned_checkpoint_dir=None, language: str = "pl") -> str:
        from django.conf import settings
        out_dir = Path(settings.MEDIA_ROOT) / "tts"
        out_dir.mkdir(exist_ok=True)
        out_path = str(out_dir / f"{uuid.uuid4().hex}.wav")

        if finetuned_checkpoint_dir:
            import soundfile as sf
            model = self._load_finetuned(finetuned_checkpoint_dir)
            # Fine-tuning specializes the GPT weights for this speaker, but XTTS
            # inference is still conditioned per-call on a reference clip — a
            # fine-tuned model isn't a "speaker_wav-free" model, it's just much
            # better at using that reference for this specific voice.
            output = model.synthesize(text, model.config, speaker_wav=speaker_wav, language=language)
            sf.write(out_path, output["wav"], samplerate=model.config.audio.output_sample_rate)
            return out_path

        tts = self._load()
        tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=out_path,
        )
        return out_path
