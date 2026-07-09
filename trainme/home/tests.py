"""Regression tests for the persona feature's Django-facing glue: per-user file
storage (PersonaService) and how it's wired into speech_input (guest fallback,
graceful degradation when Ollama fails, response shape). Ollama itself is never
called here — the trainer/student/service boundary is mocked, matching the
approach in llm_engine/tests.py.
"""
import json
import shutil
import tempfile
import threading
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from llm_engine.agents import empty_knowledge

from . import views
from .models import AudioRecord, Conversation, Message
from .persona_service import PersonaService
from .voice_finetune_service import VoiceFinetuneService
from .voice_service import VoiceService


def _make_wav_file(path, duration_seconds=1.0, sample_rate=16000):
    """Writes a minimal valid (silent) WAV file — enough for soundfile.info()
    to report an accurate duration."""
    n_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b'\x00\x00' * n_frames)


class PersonaServiceTests(TestCase):
    def setUp(self):
        self.persona_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.persona_dir, ignore_errors=True)
        self.enterContext(override_settings(PERSONA_DIR=self.persona_dir))

        self.user = User.objects.create_user(username="alice", password="x")
        self.service = PersonaService()
        self.service.trainer = MagicMock()
        self.service.student = MagicMock()

    def _persona_path(self, user=None):
        return self.persona_dir / f"user_{(user or self.user).id}.json"

    def test_load_knowledge_returns_empty_dict_when_no_file_exists(self):
        self.assertEqual(self.service.load_knowledge(self.user), empty_knowledge())

    def test_load_knowledge_reads_existing_file(self):
        custom = {"vocabulary": ["siema"], "tone": [], "topics": [], "phrases": []}
        self._persona_path().write_text(json.dumps(custom), encoding="utf-8")

        self.assertEqual(self.service.load_knowledge(self.user), custom)

    def test_train_for_user_writes_best_knowledge_and_returns_score(self):
        trained = {"vocabulary": ["siema"], "tone": ["luźny"], "topics": [], "phrases": []}
        self.service.trainer.train.return_value = (trained, 0.77, 3)

        score = self.service.train_for_user(self.user, "user said something")

        self.assertEqual(score, 0.77)
        saved = json.loads(self._persona_path().read_text(encoding="utf-8"))
        self.assertEqual(saved, trained)
        self.service.trainer.train.assert_called_once_with(empty_knowledge(), "user said something")

    def test_generate_reply_uses_loaded_knowledge_and_history(self):
        profile = {"vocabulary": [], "tone": ["ciepły"], "topics": [], "phrases": []}
        self._persona_path().write_text(json.dumps(profile), encoding="utf-8")
        self.service.student.reply.return_value = "cześć!"

        result = self.service.generate_reply(self.user, "hej", history=[("user", "hej")])

        self.assertEqual(result, "cześć!")
        self.service.student.reply.assert_called_once_with(profile, "hej", [("user", "hej")])

    def test_persona_path_is_scoped_per_user(self):
        other = User.objects.create_user(username="bob", password="x")

        self.assertNotEqual(self.service._path(self.user), self.service._path(other))


class SpeechInputPersonaWiringTests(TestCase):
    """Pins down the observable contract of the persona wiring in speech_input
    so future refactors of views.py don't silently break it."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")

        mock_transcription = MagicMock()
        mock_transcription.generate_transcription_id.return_value = "sess-1"
        mock_transcription.split_transcription_into_sentences.return_value = ["Cześć."]
        mock_transcription.save_full_transcription.return_value = "full.txt"
        mock_transcription.save_sentence_transcriptions.return_value = ["s1.txt"]
        mock_transcription.get_transcription_path.return_value = "path"
        mock_transcription.transcription_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, mock_transcription.transcription_root, ignore_errors=True)
        self.enterContext(patch("home.views.transcription_service", mock_transcription))
        self.enterContext(patch("home.views.audio_service", MagicMock()))

        self.mock_persona = self.enterContext(patch("home.views.persona_service"))

    def _post_session_end(self, text="Cześć, jak się masz?"):
        return self.client.post(
            reverse("speech_input"),
            data={"text": text, "is_session_end": True},
            content_type="application/json",
        )

    def test_guest_gets_echo_and_no_persona_calls(self):
        response = self._post_session_end("Cześć świecie")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bot_response"], "Cześć świecie")
        self.mock_persona.train_for_user.assert_not_called()
        self.mock_persona.generate_reply.assert_not_called()

    def test_authenticated_user_gets_persona_reply_and_conversation_saved(self):
        self.client.force_login(self.user)
        self.mock_persona.generate_reply.return_value = "Cześć! U mnie super."

        response = self._post_session_end("Cześć, jak się masz?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bot_response"], "Cześć! U mnie super.")
        self.mock_persona.generate_reply.assert_called_once()
        # Training happens once, in batch, when the conversation ends — not per turn.
        self.mock_persona.train_for_user.assert_not_called()

        conversation = Conversation.objects.get(user=self.user)
        messages = list(conversation.messages.order_by('message_number'))
        self.assertEqual(len(messages), 2)
        self.assertTrue(messages[0].from_user)
        self.assertEqual(messages[0].text, "Cześć, jak się masz?")
        self.assertFalse(messages[1].from_user)
        self.assertEqual(messages[1].text, "Cześć! U mnie super.")

    def test_generate_reply_failure_falls_back_to_echo_without_500(self):
        self.client.force_login(self.user)
        self.mock_persona.generate_reply.side_effect = ConnectionError("Ollama not running")

        response = self._post_session_end("Cześć, jak się masz?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bot_response"], "Cześć, jak się masz?")

    def test_response_shape_unchanged_for_frontend(self):
        response = self._post_session_end("test")

        data = response.json()
        for key in ("status", "transcription_id", "sentence_count", "audio_saved",
                    "conversation_id", "message_number", "bot_response", "bot_audio_url"):
            self.assertIn(key, data)


class NewConversationTrainingTests(TestCase):
    """The frontend's is_session_end fires per utterance (silence/stop), not per
    conversation — so persona training is batched here instead, at the point the
    conversation actually ends (the "Nowa rozmowa" action, idle timeout, or tab
    close all POST to the same endpoint).

    Training is kicked off in a background thread (see _start_persona_training in
    views.py) so the request doesn't hang for tens of seconds waiting on Ollama —
    that blocking was exactly what made "Nowa rozmowa" look broken. These tests
    patch _start_persona_training itself (the synchronous boundary within the
    request) rather than persona_service, since asserting on calls made inside a
    detached thread would be racy.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.mock_start_training = self.enterContext(
            patch("home.views._start_persona_training")
        )

    def _new_conversation(self):
        return self.client.post(reverse("new_conversation"))

    def _seed_conversation(self, *texts):
        conversation = Conversation.objects.create(user=self.user)
        session = self.client.session
        session['conversation_id'] = conversation.id
        session.save()
        for i, (text, from_user) in enumerate(texts, start=1):
            Message.objects.create(conversation=conversation, text=text,
                                    from_user=from_user, message_number=i)
        return conversation

    def test_trains_on_full_user_transcript_when_conversation_ends(self):
        self.client.force_login(self.user)
        self._seed_conversation(
            ("Cześć, jak leci?", True),
            ("Wszystko super, dzięki!", False),
            ("Generalnie mówię szybko.", True),
        )

        response = self._new_conversation()

        self.assertEqual(response.status_code, 200)
        self.mock_start_training.assert_called_once_with(
            self.user, "Cześć, jak leci?\nGeneralnie mówię szybko."
        )

    def test_clears_conversation_id_from_session(self):
        self.client.force_login(self.user)
        self._seed_conversation(("Cześć", True))

        self._new_conversation()

        self.assertNotIn('conversation_id', self.client.session)

    def test_no_training_call_when_no_conversation_in_session(self):
        self.client.force_login(self.user)

        response = self._new_conversation()

        self.assertEqual(response.status_code, 200)
        self.mock_start_training.assert_not_called()

    def test_no_training_call_for_guest(self):
        self._seed_conversation(("Cześć", True))

        response = self._new_conversation()

        self.assertEqual(response.status_code, 200)
        self.mock_start_training.assert_not_called()

    def test_no_training_call_when_conversation_has_no_user_messages(self):
        self.client.force_login(self.user)
        self._seed_conversation(("Cześć! Jestem Train.me.", False))

        self._new_conversation()

        self.mock_start_training.assert_not_called()

class StartPersonaTrainingTests(TestCase):
    """_start_persona_training is the one bit of real threading.Thread usage —
    verify training actually runs, and runs off the calling (request) thread,
    which is what makes new_conversation return without waiting on Ollama."""

    def test_runs_training_on_a_background_thread(self):
        user = User.objects.create_user(username="alice", password="x")
        calling_thread = threading.current_thread()
        done = threading.Event()
        seen = {}

        def fake_train_for_user(u, transcript):
            seen['thread'] = threading.current_thread()
            seen['args'] = (u, transcript)
            done.set()

        with patch("home.views.persona_service") as mock_persona:
            mock_persona.train_for_user.side_effect = fake_train_for_user
            views._start_persona_training(user, "transkrypt")
            self.assertTrue(done.wait(timeout=2), "background training never ran")

        self.assertNotEqual(seen['thread'], calling_thread)
        self.assertEqual(seen['args'], (user, "transkrypt"))


class TrainPersonaAsyncTests(TestCase):
    """_train_persona_async runs inside the background thread started by
    _start_persona_training — it must swallow Ollama failures itself since
    there's no request/response left to report them through."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")

    def test_swallows_persona_service_errors(self):
        with patch("home.views.persona_service") as mock_persona:
            mock_persona.train_for_user.side_effect = ConnectionError("Ollama not running")
            views._train_persona_async(self.user, "some transcript")  # must not raise

    def test_calls_persona_service_train_for_user(self):
        with patch("home.views.persona_service") as mock_persona:
            views._train_persona_async(self.user, "some transcript")

            mock_persona.train_for_user.assert_called_once_with(self.user, "some transcript")


class DeleteConversationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.other = User.objects.create_user(username="bob", password="x")

    def test_owner_can_delete_conversation(self):
        conv = Conversation.objects.create(user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(reverse("delete_conversation", args=[conv.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())

    def test_deleting_conversation_cascades_messages(self):
        conv = Conversation.objects.create(user=self.user)
        Message.objects.create(conversation=conv, text="hej", from_user=True, message_number=1)
        self.client.force_login(self.user)

        self.client.post(reverse("delete_conversation", args=[conv.id]))

        self.assertEqual(Message.objects.filter(conversation_id=conv.id).count(), 0)

    def test_clears_session_when_deleting_active_conversation(self):
        conv = Conversation.objects.create(user=self.user)
        self.client.force_login(self.user)
        session = self.client.session
        session['conversation_id'] = conv.id
        session.save()

        self.client.post(reverse("delete_conversation", args=[conv.id]))

        self.assertNotIn('conversation_id', self.client.session)

    def test_cannot_delete_another_users_conversation(self):
        conv = Conversation.objects.create(user=self.other)
        self.client.force_login(self.user)

        response = self.client.post(reverse("delete_conversation", args=[conv.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Conversation.objects.filter(id=conv.id).exists())

    def test_guest_cannot_delete(self):
        conv = Conversation.objects.create(user=self.user)

        response = self.client.post(reverse("delete_conversation", args=[conv.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Conversation.objects.filter(id=conv.id).exists())

    def test_get_not_allowed(self):
        conv = Conversation.objects.create(user=self.user)
        self.client.force_login(self.user)

        response = self.client.get(reverse("delete_conversation", args=[conv.id]))

        self.assertEqual(response.status_code, 405)


class VoiceServiceTests(TestCase):
    """VoiceService is a thin Django-settings-driven wrapper around
    tts_engine.VoiceStore (whose own curation/pruning logic is covered in
    tts_engine/tests.py) — these just check the wiring: settings feed through,
    and clips are scoped per user.id."""

    def setUp(self):
        self.voices_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.voices_dir, ignore_errors=True)
        self.enterContext(override_settings(TTS_VOICES_DIR=self.voices_dir, TTS_VOICE_MAX_CLIPS=2))

        self.user = User.objects.create_user(username="alice", password="x")
        self.service = VoiceService()

    def _make_wav(self, content=b"data"):
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self.voices_dir)
        f.write(content)
        f.close()
        return f.name

    def test_get_reference_clips_for_user_empty_initially(self):
        self.assertEqual(self.service.get_reference_clips_for_user(self.user), [])

    def test_add_clip_for_user_then_retrievable(self):
        self.service.add_clip_for_user(self.user, self._make_wav(b"hello"))

        clips = self.service.get_reference_clips_for_user(self.user)

        self.assertEqual(len(clips), 1)
        self.assertEqual(Path(clips[0]).read_bytes(), b"hello")

    def test_respects_max_clips_from_settings(self):
        for i in range(3):
            self.service.add_clip_for_user(self.user, self._make_wav(str(i).encode()))

        self.assertEqual(len(self.service.get_reference_clips_for_user(self.user)), 2)


class SpeechInputVoiceWiringTests(TestCase):
    """Pins down speaker_wav selection in speech_input: curated voice clips
    (from past conversations) take priority over this turn's own recording
    once any exist; guests and lookup failures fall back to the recording."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")

        mock_transcription = MagicMock()
        mock_transcription.generate_transcription_id.return_value = "sess-1"
        mock_transcription.split_transcription_into_sentences.return_value = ["Cześć."]
        mock_transcription.save_full_transcription.return_value = "full.txt"
        mock_transcription.save_sentence_transcriptions.return_value = ["s1.txt"]
        mock_transcription.get_transcription_path.return_value = "path"
        mock_transcription.transcription_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, mock_transcription.transcription_root, ignore_errors=True)
        self.enterContext(patch("home.views.transcription_service", mock_transcription))

        mock_audio = MagicMock()
        mock_audio.save_audio_from_base64.return_value = "/fake/audio.wav"
        self.enterContext(patch("home.views.audio_service", mock_audio))

        self.mock_persona = self.enterContext(patch("home.views.persona_service"))
        self.mock_persona.generate_reply.return_value = "odpowiedź"

        self.mock_voice = self.enterContext(patch("home.views.voice_service"))
        self.mock_finetune = self.enterContext(patch("home.views.voice_finetune_service"))
        self.mock_finetune.checkpoint_dir_for_user.return_value = None

        self.mock_tts = self.enterContext(patch("home.views.tts_service"))
        self.mock_tts.synthesize.return_value = "/fake/out.wav"

    def _post_with_audio(self, text="Cześć"):
        return self.client.post(
            reverse("speech_input"),
            data={"text": text, "audio": "ZmFrZQ==", "is_session_end": True},
            content_type="application/json",
        )

    def test_uses_curated_clips_when_available(self):
        self.client.force_login(self.user)
        self.mock_voice.get_reference_clips_for_user.return_value = [
            "/voices/user_1/a.wav", "/voices/user_1/b.wav",
        ]

        self._post_with_audio()

        self.mock_tts.synthesize.assert_called_once_with(
            "odpowiedź", ["/voices/user_1/a.wav", "/voices/user_1/b.wav"],
            finetuned_checkpoint_dir=None,
        )

    def test_falls_back_to_current_recording_when_no_curated_clips(self):
        self.client.force_login(self.user)
        self.mock_voice.get_reference_clips_for_user.return_value = []

        self._post_with_audio()

        self.mock_tts.synthesize.assert_called_once_with(
            "odpowiedź", "/fake/audio.wav", finetuned_checkpoint_dir=None
        )

    def test_guest_always_uses_current_recording(self):
        self._post_with_audio()

        self.mock_tts.synthesize.assert_called_once_with(
            "Cześć", "/fake/audio.wav", finetuned_checkpoint_dir=None
        )
        self.mock_voice.get_reference_clips_for_user.assert_not_called()
        self.mock_finetune.checkpoint_dir_for_user.assert_not_called()

    def test_voice_lookup_failure_falls_back_to_current_recording(self):
        self.client.force_login(self.user)
        self.mock_voice.get_reference_clips_for_user.side_effect = ConnectionError("boom")

        response = self._post_with_audio()

        self.assertEqual(response.status_code, 200)
        self.mock_tts.synthesize.assert_called_once_with(
            "odpowiedź", "/fake/audio.wav", finetuned_checkpoint_dir=None
        )

    def test_uses_finetuned_checkpoint_when_available(self):
        self.client.force_login(self.user)
        self.mock_voice.get_reference_clips_for_user.return_value = ["/voices/user_1/a.wav"]
        self.mock_finetune.checkpoint_dir_for_user.return_value = "/finetune/user_1/best"

        self._post_with_audio()

        self.mock_tts.synthesize.assert_called_once_with(
            "odpowiedź", ["/voices/user_1/a.wav"],
            finetuned_checkpoint_dir="/finetune/user_1/best",
        )

    def test_finetune_lookup_failure_falls_back_to_zero_shot(self):
        self.client.force_login(self.user)
        self.mock_voice.get_reference_clips_for_user.return_value = []
        self.mock_finetune.checkpoint_dir_for_user.side_effect = OSError("boom")

        response = self._post_with_audio()

        self.assertEqual(response.status_code, 200)
        self.mock_tts.synthesize.assert_called_once_with(
            "odpowiedź", "/fake/audio.wav", finetuned_checkpoint_dir=None
        )


class NewConversationVoiceCurationTests(TestCase):
    """The largest recording from a finished conversation gets curated into the
    user's reference-clip set (see _best_audio_record in views.py). Curation
    (which classifies emotion via Ollama) runs in a background thread, same
    reasoning as persona training — these tests patch _start_voice_curation,
    the synchronous boundary, rather than asserting on the threaded call."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.enterContext(patch("home.views._start_persona_training"))
        self.mock_finetune = self.enterContext(patch("home.views.voice_finetune_service"))
        self.mock_finetune.is_ready.return_value = False
        self.mock_start_curation = self.enterContext(patch("home.views._start_voice_curation"))
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _new_conversation(self):
        return self.client.post(reverse("new_conversation"))

    def _seed_conversation_with_audio(self, *sizes):
        conversation = Conversation.objects.create(user=self.user)
        session = self.client.session
        session['conversation_id'] = conversation.id
        session.save()
        for i, size in enumerate(sizes, start=1):
            msg = Message.objects.create(conversation=conversation, text=f"turn {i}",
                                          from_user=True, message_number=i)
            wav_path = self.tmp_dir / f"clip_{i}.wav"
            wav_path.write_bytes(b"x" * size)
            AudioRecord.objects.create(conversation=conversation, wav_path=str(wav_path),
                                        text_message=msg)
        return conversation

    def test_curates_the_largest_recording(self):
        self.client.force_login(self.user)
        self._seed_conversation_with_audio(100, 500, 200)

        self._new_conversation()

        called_path = self.mock_start_curation.call_args.args[1]
        self.assertTrue(called_path.endswith("clip_2.wav"))

    def test_passes_transcript_for_emotion_classification(self):
        self.client.force_login(self.user)
        self._seed_conversation_with_audio(100)

        self._new_conversation()

        called_transcript = self.mock_start_curation.call_args.args[2]
        self.assertEqual(called_transcript, "turn 1")

    def test_no_curation_call_when_conversation_has_no_audio(self):
        self.client.force_login(self.user)
        conversation = Conversation.objects.create(user=self.user)
        session = self.client.session
        session['conversation_id'] = conversation.id
        session.save()
        Message.objects.create(conversation=conversation, text="hej",
                                from_user=True, message_number=1)

        self._new_conversation()

        self.mock_start_curation.assert_not_called()

    def test_logs_readiness_without_raising_when_ready(self):
        self.client.force_login(self.user)
        self._seed_conversation_with_audio(100)
        self.mock_finetune.is_ready.return_value = True

        response = self._new_conversation()

        self.assertEqual(response.status_code, 200)

    def test_readiness_check_failure_does_not_break_the_request(self):
        self.client.force_login(self.user)
        self._seed_conversation_with_audio(100)
        self.mock_finetune.is_ready.side_effect = OSError("boom")

        response = self._new_conversation()

        self.assertEqual(response.status_code, 200)


class StartVoiceCurationTests(TestCase):
    """_start_voice_curation is the real threading.Thread usage behind voice
    clip curation — mirrors StartPersonaTrainingTests."""

    def test_runs_curation_on_a_background_thread(self):
        user = User.objects.create_user(username="alice", password="x")
        calling_thread = threading.current_thread()
        done = threading.Event()
        seen = {}

        def fake_add_clip_for_user(u, wav_path, emotion):
            seen['thread'] = threading.current_thread()
            seen['args'] = (u, wav_path, emotion)
            done.set()

        with patch("home.views.classify_emotion", return_value="calm"), \
             patch("home.views.voice_service") as mock_voice:
            mock_voice.add_clip_for_user.side_effect = fake_add_clip_for_user
            views._start_voice_curation(user, "/some/clip.wav", "transkrypt")
            self.assertTrue(done.wait(timeout=2), "background curation never ran")

        self.assertNotEqual(seen['thread'], calling_thread)
        self.assertEqual(seen['args'], (user, "/some/clip.wav", "calm"))


class CurateVoiceClipAsyncTests(TestCase):
    """_curate_voice_clip_async runs inside the background thread — it must
    swallow errors from both classify_emotion and voice_service itself, since
    there's no request/response left to report them through."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")

    def test_uses_classified_emotion(self):
        with patch("home.views.classify_emotion", return_value="excited") as mock_classify, \
             patch("home.views.voice_service") as mock_voice:
            views._curate_voice_clip_async(self.user, "/clip.wav", "wooo!")

            mock_classify.assert_called_once_with("wooo!")
            mock_voice.add_clip_for_user.assert_called_once_with(
                self.user, "/clip.wav", emotion="excited"
            )

    def test_emotion_classification_failure_falls_back_to_neutral(self):
        with patch("home.views.classify_emotion", side_effect=ConnectionError("boom")), \
             patch("home.views.voice_service") as mock_voice:
            views._curate_voice_clip_async(self.user, "/clip.wav", "transkrypt")

            mock_voice.add_clip_for_user.assert_called_once_with(
                self.user, "/clip.wav", emotion="neutral"
            )

    def test_voice_service_failure_does_not_raise(self):
        with patch("home.views.classify_emotion", return_value="calm"), \
             patch("home.views.voice_service") as mock_voice:
            mock_voice.add_clip_for_user.side_effect = OSError("disk full")

            views._curate_voice_clip_async(self.user, "/clip.wav", "transkrypt")  # must not raise


class VoiceFinetuneServiceTests(TestCase):
    def setUp(self):
        self.finetune_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.finetune_dir, ignore_errors=True)
        self.enterContext(override_settings(
            TTS_FINETUNE_DIR=self.finetune_dir, TTS_FINETUNE_MIN_SECONDS=2,
        ))

        self.user = User.objects.create_user(username="alice", password="x")
        self.conversation = Conversation.objects.create(user=self.user)
        self.wav_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wav_dir, ignore_errors=True)
        self.service = VoiceFinetuneService()

    def _add_recording(self, text, duration_seconds, message_number=1):
        wav_path = self.wav_dir / f"{message_number}.wav"
        _make_wav_file(wav_path, duration_seconds=duration_seconds)
        msg = Message.objects.create(conversation=self.conversation, text=text,
                                      from_user=True, message_number=message_number)
        AudioRecord.objects.create(conversation=self.conversation, wav_path=str(wav_path),
                                    text_message=msg)
        return wav_path

    def test_training_samples_for_user_pairs_audio_with_text(self):
        wav_path = self._add_recording("cześć", 1.0)

        samples = self.service.training_samples_for_user(self.user)

        self.assertEqual(samples, [(str(wav_path), "cześć")])

    def test_total_duration_seconds_sums_across_recordings(self):
        self._add_recording("a", 1.0, message_number=1)
        self._add_recording("b", 1.5, message_number=2)

        self.assertAlmostEqual(self.service.total_duration_seconds(self.user), 2.5, places=1)

    def test_total_duration_ignores_unreadable_files(self):
        msg = Message.objects.create(conversation=self.conversation, text="broken",
                                      from_user=True, message_number=1)
        AudioRecord.objects.create(conversation=self.conversation,
                                    wav_path=str(self.wav_dir / "missing.wav"), text_message=msg)

        self.assertEqual(self.service.total_duration_seconds(self.user), 0.0)

    def test_is_ready_uses_settings_threshold(self):
        self._add_recording("a", 1.0)

        self.assertFalse(self.service.is_ready(self.user))  # 1.0s < 2s threshold

        self._add_recording("b", 1.5, message_number=2)

        self.assertTrue(self.service.is_ready(self.user))  # 2.5s >= 2s threshold

    def test_is_ready_accepts_explicit_threshold_override(self):
        self._add_recording("a", 1.0)

        self.assertTrue(self.service.is_ready(self.user, min_seconds=0.5))
        self.assertFalse(self.service.is_ready(self.user, min_seconds=10))

    def test_checkpoint_dir_for_user_none_when_never_trained(self):
        self.assertIsNone(self.service.checkpoint_dir_for_user(self.user))

    def test_checkpoint_dir_for_user_finds_completed_run(self):
        run_dir = self.finetune_dir / f"user_{self.user.id}" / "run" / "training" / "GPT_XTTS_FT-run"
        run_dir.mkdir(parents=True)
        (run_dir / "config.json").write_text("{}")
        (run_dir / "best_model.pth").write_bytes(b"fake")

        self.assertEqual(self.service.checkpoint_dir_for_user(self.user), run_dir)

    def test_checkpoint_dir_for_user_ignores_incomplete_run(self):
        run_dir = self.finetune_dir / f"user_{self.user.id}" / "run" / "training" / "incomplete-run"
        run_dir.mkdir(parents=True)
        (run_dir / "config.json").write_text("{}")
        # no model file written — run never finished

        self.assertIsNone(self.service.checkpoint_dir_for_user(self.user))
