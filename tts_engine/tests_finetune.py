"""Regression tests for tts_engine.finetune.export_dataset — the dataset-manifest
step of the real XTTS fine-tuning pipeline. run_finetune() itself (actual GPU
training) is intentionally NOT covered here: it needs a GPU and real audio
data, and is verified manually via `manage.py finetune_voice` (see plan/README).

Run with:  python -m unittest tts_engine.tests_finetune   (from the repo root)
"""
import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from tts_engine.finetune import export_dataset


class ExportDatasetTests(unittest.TestCase):
    def setUp(self):
        self.src_dir = Path(tempfile.mkdtemp())
        self.out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.src_dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.out_dir, ignore_errors=True)

    def _make_wav(self, name, content=b"fake wav bytes"):
        path = self.src_dir / name
        path.write_bytes(content)
        return str(path)

    def _read_csv(self, path):
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.reader(f, delimiter="|"))

    def test_writes_pipe_separated_csv_with_header(self):
        samples = [(self._make_wav("a.wav"), "cześć")]

        train_csv, _eval_csv = export_dataset(samples, self.out_dir)

        rows = self._read_csv(train_csv)
        self.assertEqual(rows[0], ["audio_file", "text", "speaker_name"])
        self.assertEqual(rows[1][1], "cześć")
        self.assertEqual(rows[1][2], "speaker")

    def test_copies_audio_into_wavs_subdir_with_relative_path(self):
        samples = [(self._make_wav("a.wav", b"hello"), "cześć")]

        train_csv, _eval_csv = export_dataset(samples, self.out_dir)

        rows = self._read_csv(train_csv)
        audio_file = rows[1][0]
        self.assertTrue(audio_file.startswith("wavs/"))
        self.assertEqual((self.out_dir / audio_file).read_bytes(), b"hello")

    def test_splits_into_train_and_eval(self):
        samples = [(self._make_wav(f"{i}.wav"), f"text {i}") for i in range(10)]

        train_csv, eval_csv = export_dataset(samples, self.out_dir, eval_fraction=0.2)

        train_rows = self._read_csv(train_csv)[1:]
        eval_rows = self._read_csv(eval_csv)[1:]
        self.assertEqual(len(train_rows), 8)
        self.assertEqual(len(eval_rows), 2)

    def test_keeps_at_least_one_eval_sample_even_with_few_inputs(self):
        samples = [(self._make_wav("a.wav"), "cześć"), (self._make_wav("b.wav"), "hej")]

        train_csv, eval_csv = export_dataset(samples, self.out_dir, eval_fraction=0.1)

        eval_rows = self._read_csv(eval_csv)[1:]
        self.assertGreaterEqual(len(eval_rows), 1)

    def test_skips_samples_with_empty_text(self):
        samples = [
            (self._make_wav("a.wav"), "cześć"),
            (self._make_wav("b.wav"), "   "),
            (self._make_wav("c.wav"), ""),
        ]

        train_csv, eval_csv = export_dataset(samples, self.out_dir)

        # A single usable sample degenerately ends up in both train and eval
        # (there's nothing else to hold out) — what matters here is that the
        # blank-text samples never appear anywhere.
        all_texts = {row[1] for row in self._read_csv(train_csv)[1:] + self._read_csv(eval_csv)[1:]}
        self.assertEqual(all_texts, {"cześć"})

    def test_raises_when_no_usable_samples(self):
        samples = [(self._make_wav("a.wav"), ""), (self._make_wav("b.wav"), "   ")]

        with self.assertRaises(ValueError):
            export_dataset(samples, self.out_dir)


if __name__ == "__main__":
    unittest.main()
