"""Real fine-tuning of XTTS v2's GPT layer on a speaker's own recordings.

This is NOT the lightweight zero-shot reference-clip curation in voice_store.py
— it's actual gradient-based training, ported from Coqui's official recipe
(TTS/demos/xtts_ft_demo/utils/gpt_train.py in the installed TTS==0.22.0
package). We don't import that module directly since TTS/demos/ isn't public
API (Gradio-UI-oriented, not meant for library use) — this is our own
maintained copy of the relevant config, trimmed of the demo/UI-only bits.

Only the GPT layer is trained; the rest of Xtts (HiFi-GAN decoder, speaker
encoder) stays frozen, but the saved checkpoint is still a full model that
must be loaded as its own Xtts instance at inference time (see
TTSService._load_finetuned in trainme/home/tts_service.py) — there's no
lightweight "delta" to apply.

Not covered by the automated test suite beyond export_dataset() — actually
running run_finetune() needs a GPU and real audio data. Verify manually via
`python manage.py finetune_voice <username>`.
"""
import csv
import gc
import os
import shutil
from pathlib import Path

from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.datasets import load_tts_samples
from TTS.tts.layers.xtts.trainer.gpt_trainer import GPTArgs, GPTTrainer, GPTTrainerConfig, XttsAudioConfig
from TTS.utils.generic_utils import get_user_data_dir
from TTS.utils.manage import ModelManager
from trainer import Trainer, TrainerArgs

# Cache dir TTSService's base-model load (TTS("tts_models/multilingual/multi-
# dataset/xtts_v2")) already populates — reuse it instead of re-downloading.
BASE_MODEL_CACHE_DIR = Path(get_user_data_dir("tts")) / "tts_models--multilingual--multi-dataset--xtts_v2"

DVAE_CHECKPOINT_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/dvae.pth"
MEL_NORM_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/mel_stats.pth"
TOKENIZER_FILE_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/vocab.json"
XTTS_CHECKPOINT_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/model.pth"
XTTS_CONFIG_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/config.json"


def export_dataset(samples, out_dir, eval_fraction=0.15):
    """Writes (wav_path, text) samples into metadata_train.csv / metadata_eval.csv
    using the "coqui" formatter's format (TTS.tts.datasets.formatters.coqui):
    pipe-separated audio_file|text|speaker_name, audio_file relative to out_dir.
    Returns (train_csv, eval_csv) as Path objects. Raises ValueError if no
    sample has non-empty text."""
    out_dir = Path(out_dir)
    wavs_dir = out_dir / "wavs"
    wavs_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, (wav_path, text) in enumerate(samples):
        text = (text or "").strip()
        if not text:
            continue
        dest = wavs_dir / f"clip_{i:05d}.wav"
        shutil.copyfile(wav_path, dest)
        rows.append((f"wavs/{dest.name}", text, "speaker"))

    if not rows:
        raise ValueError("No usable (audio, text) samples to export.")

    split_idx = max(1, int(len(rows) * (1 - eval_fraction)))
    train_rows = rows[:split_idx]
    eval_rows = rows[split_idx:] or rows[-1:]

    train_csv = out_dir / "metadata_train.csv"
    eval_csv = out_dir / "metadata_eval.csv"
    _write_csv(train_csv, train_rows)
    _write_csv(eval_csv, eval_rows)
    return train_csv, eval_csv


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(["audio_file", "text", "speaker_name"])
        writer.writerows(rows)


def _resolve_base_checkpoint_files(work_dir: Path):
    """Returns (xtts_checkpoint, tokenizer_file, dvae_checkpoint, mel_norm_file)
    paths. Reuses the base model TTSService already downloaded when present;
    otherwise downloads whatever's missing, same as the official recipe."""
    aux_dir = work_dir / "base_model_files"
    aux_dir.mkdir(parents=True, exist_ok=True)

    xtts_checkpoint = BASE_MODEL_CACHE_DIR / "model.pth"
    tokenizer_file = BASE_MODEL_CACHE_DIR / "vocab.json"
    if not (xtts_checkpoint.is_file() and tokenizer_file.is_file()):
        xtts_checkpoint = aux_dir / "model.pth"
        tokenizer_file = aux_dir / "vocab.json"
        if not (xtts_checkpoint.is_file() and tokenizer_file.is_file()):
            ModelManager._download_model_files(
                [TOKENIZER_FILE_LINK, XTTS_CHECKPOINT_LINK, XTTS_CONFIG_LINK],
                str(aux_dir), progress_bar=True,
            )

    dvae_checkpoint = aux_dir / "dvae.pth"
    mel_norm_file = aux_dir / "mel_stats.pth"
    if not (dvae_checkpoint.is_file() and mel_norm_file.is_file()):
        ModelManager._download_model_files(
            [MEL_NORM_LINK, DVAE_CHECKPOINT_LINK], str(aux_dir), progress_bar=True,
        )

    return xtts_checkpoint, tokenizer_file, dvae_checkpoint, mel_norm_file


def run_finetune(train_csv, eval_csv, output_dir, language="pl", num_epochs=10,
                  batch_size=4, grad_acumm=1, max_audio_length_sec=11) -> Path:
    """Fine-tunes XTTS v2's GPT layer on the given dataset. Returns the output
    directory containing the trained checkpoint (best_model.pth/config.json)."""
    train_csv, eval_csv = str(train_csv), str(eval_csv)
    output_dir = Path(output_dir)
    out_path = output_dir / "run" / "training"
    out_path.mkdir(parents=True, exist_ok=True)

    xtts_checkpoint, tokenizer_file, dvae_checkpoint, mel_norm_file = \
        _resolve_base_checkpoint_files(output_dir)

    config_dataset = BaseDatasetConfig(
        formatter="coqui",
        dataset_name="ft_dataset",
        path=os.path.dirname(train_csv),
        meta_file_train=train_csv,
        meta_file_val=eval_csv,
        language=language,
    )

    model_args = GPTArgs(
        max_conditioning_length=132300,  # 6s
        min_conditioning_length=66150,  # 3s
        max_wav_length=int(max_audio_length_sec * 22050),
        max_text_length=200,
        mel_norm_file=str(mel_norm_file),
        dvae_checkpoint=str(dvae_checkpoint),
        xtts_checkpoint=str(xtts_checkpoint),
        tokenizer_file=str(tokenizer_file),
        gpt_num_audio_tokens=1026,
        gpt_start_audio_token=1024,
        gpt_stop_audio_token=1025,
        gpt_use_masking_gt_prompt_approach=True,
        gpt_use_perceiver_resampler=True,
    )
    audio_config = XttsAudioConfig(sample_rate=22050, dvae_sample_rate=22050, output_sample_rate=24000)
    config = GPTTrainerConfig(
        epochs=num_epochs,
        output_path=str(out_path),
        model_args=model_args,
        run_name="GPT_XTTS_FT",
        project_name="TrainMe_voice",
        dashboard_logger="tensorboard",
        audio=audio_config,
        batch_size=batch_size,
        batch_group_size=48,
        eval_batch_size=batch_size,
        num_loader_workers=8,
        eval_split_max_size=256,
        print_step=50,
        save_step=1000,
        save_n_checkpoints=1,
        save_checkpoints=True,
        print_eval=False,
        optimizer="AdamW",
        optimizer_wd_only_on_weights=True,
        optimizer_params={"betas": [0.9, 0.96], "eps": 1e-8, "weight_decay": 1e-2},
        lr=5e-06,
        lr_scheduler="MultiStepLR",
        lr_scheduler_params={"milestones": [900000, 2700000, 5400000], "gamma": 0.5, "last_epoch": -1},
        test_sentences=[],
    )

    model = GPTTrainer.init_from_config(config)
    train_samples, eval_samples = load_tts_samples(
        [config_dataset], eval_split=True,
        eval_split_max_size=config.eval_split_max_size,
        eval_split_size=config.eval_split_size,
    )

    trainer = Trainer(
        TrainerArgs(restore_path=None, skip_train_epoch=False,
                    start_with_eval=False, grad_accum_steps=grad_acumm),
        config, output_path=str(out_path), model=model,
        train_samples=train_samples, eval_samples=eval_samples,
    )
    trainer.fit()

    trainer_out_path = Path(trainer.output_path)

    del model, trainer, train_samples, eval_samples
    gc.collect()

    return trainer_out_path
