"""Regression tests for VoiceStore — the reference-clip curation logic behind
voice-cloning TTS. Pure unittest (no Django dependency), uses real temp-dir
file I/O since this is just file copying/pruning, nothing worth mocking.

Run with:  python -m unittest tts_engine.tests   (from the repo root)
"""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from tts_engine.voice_store import VoiceStore


class VoiceStoreTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base_dir, ignore_errors=True)
        self.store = VoiceStore(base_dir=self.base_dir, max_clips=3)

    def _make_source_wav(self, content=b"fake wav bytes"):
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self.base_dir)
        f.write(content)
        f.close()
        return f.name

    def test_get_reference_clips_is_empty_for_new_speaker(self):
        self.assertEqual(self.store.get_reference_clips(1), [])

    def test_add_clip_copies_file_into_speaker_dir(self):
        source = self._make_source_wav(b"hello")

        clips = self.store.add_clip(1, source)

        self.assertEqual(len(clips), 1)
        self.assertTrue(Path(clips[0]).exists())
        self.assertEqual(Path(clips[0]).read_bytes(), b"hello")
        # source file itself must be untouched (copy, not move)
        self.assertTrue(Path(source).exists())

    def test_add_clip_scopes_to_speaker_id(self):
        self.store.add_clip(1, self._make_source_wav())
        self.store.add_clip(2, self._make_source_wav())

        self.assertEqual(len(self.store.get_reference_clips(1)), 1)
        self.assertEqual(len(self.store.get_reference_clips(2)), 1)

    def test_add_clip_accumulates_up_to_max_clips(self):
        for _ in range(3):
            self.store.add_clip(1, self._make_source_wav())
            time.sleep(0.01)

        self.assertEqual(len(self.store.get_reference_clips(1)), 3)

    def test_add_clip_prunes_oldest_beyond_max_clips(self):
        first = self.store.add_clip(1, self._make_source_wav(b"first"))[0]
        time.sleep(0.01)
        self.store.add_clip(1, self._make_source_wav(b"second"))
        time.sleep(0.01)
        self.store.add_clip(1, self._make_source_wav(b"third"))
        time.sleep(0.01)

        clips = self.store.add_clip(1, self._make_source_wav(b"fourth"))

        self.assertEqual(len(clips), 3)
        self.assertFalse(Path(first).exists(), "oldest clip should have been pruned")
        contents = [Path(c).read_bytes() for c in clips]
        self.assertEqual(contents, [b"second", b"third", b"fourth"])

    def test_get_reference_clips_returns_oldest_first(self):
        self.store.add_clip(1, self._make_source_wav(b"a"))
        time.sleep(0.01)
        self.store.add_clip(1, self._make_source_wav(b"b"))

        clips = self.store.get_reference_clips(1)

        contents = [Path(c).read_bytes() for c in clips]
        self.assertEqual(contents, [b"a", b"b"])


class VoiceStoreEmotionBucketingTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base_dir, ignore_errors=True)
        self.store = VoiceStore(base_dir=self.base_dir, max_clips=2)

    def _make_source_wav(self, content=b"fake wav bytes"):
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self.base_dir)
        f.write(content)
        f.close()
        return f.name

    def test_default_emotion_is_neutral(self):
        self.store.add_clip(1, self._make_source_wav(b"x"))

        self.assertEqual(len(self.store.get_reference_clips(1, emotion="neutral")), 1)

    def test_different_emotions_are_kept_separate(self):
        self.store.add_clip(1, self._make_source_wav(b"happy clip"), emotion="excited")
        self.store.add_clip(1, self._make_source_wav(b"calm clip"), emotion="calm")

        excited = self.store.get_reference_clips(1, emotion="excited")
        calm = self.store.get_reference_clips(1, emotion="calm")

        self.assertEqual(len(excited), 1)
        self.assertEqual(len(calm), 1)
        self.assertEqual(Path(excited[0]).read_bytes(), b"happy clip")
        self.assertEqual(Path(calm[0]).read_bytes(), b"calm clip")

    def test_max_clips_applies_per_emotion_not_globally(self):
        for _ in range(2):
            self.store.add_clip(1, self._make_source_wav(), emotion="excited")
            time.sleep(0.01)
        self.store.add_clip(1, self._make_source_wav(), emotion="calm")

        self.assertEqual(len(self.store.get_reference_clips(1, emotion="excited")), 2)
        self.assertEqual(len(self.store.get_reference_clips(1, emotion="calm")), 1)

    def test_falls_back_to_neutral_when_requested_emotion_has_no_clips(self):
        self.store.add_clip(1, self._make_source_wav(b"neutral clip"), emotion="neutral")

        clips = self.store.get_reference_clips(1, emotion="sad")

        self.assertEqual(len(clips), 1)
        self.assertEqual(Path(clips[0]).read_bytes(), b"neutral clip")

    def test_no_fallback_when_neutral_also_empty(self):
        self.assertEqual(self.store.get_reference_clips(1, emotion="sad"), [])


if __name__ == "__main__":
    unittest.main()
