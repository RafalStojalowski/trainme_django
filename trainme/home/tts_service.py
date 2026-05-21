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
                print("✅ XTTS v2 załadowany")
            finally:
                torch.load = _orig
        return self._tts

    def synthesize(self, text: str, speaker_wav: str, language: str = "pl") -> str:
        from django.conf import settings
        tts = self._load()
        out_dir = Path(settings.MEDIA_ROOT) / "tts"
        out_dir.mkdir(exist_ok=True)
        out_path = str(out_dir / f"{uuid.uuid4().hex}.wav")
        tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=out_path,
        )
        return out_path
