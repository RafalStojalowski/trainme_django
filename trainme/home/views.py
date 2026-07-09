from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User
from django.conf import settings
import json
import os
import threading
from .transcription_service import TranscriptionService
from .audio_service import AudioService
from .tts_service import TTSService
from .persona_service import PersonaService
from .voice_service import VoiceService
from .voice_finetune_service import VoiceFinetuneService
from .models import TranscriptionSession, TranscriptionSentence, Conversation, Message, AudioRecord
from llm_engine.emotion import classify_emotion


tts_service = TTSService()
persona_service = PersonaService()
voice_service = VoiceService()
voice_finetune_service = VoiceFinetuneService()


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email']


# Initialize services
transcription_service = TranscriptionService()
audio_service = AudioService()


def home(request):
    return render(request, 'home/home.html')


def _get_or_create_conversation(request):
    """Get active conversation from session or create a new one."""
    conversation_id = request.session.get('conversation_id')
    if conversation_id:
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            pass
    conversation = Conversation.objects.create(
        user=request.user if request.user.is_authenticated else None
    )
    request.session['conversation_id'] = conversation.id
    return conversation


def speech_input(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Get transcription text
            text = data.get("text", "").strip()

            # Get audio data if provided (base64 encoded)
            audio_data = data.get("audio", None)

            # Get session flag - True if session ended, False if interim
            is_session_end = data.get("is_session_end", False)

            if text:
                print("USER SAID:", text)

            if is_session_end and text:
                print("🔄 Processing session end...")
                # Generate unique transcription ID
                transcription_id = transcription_service.generate_transcription_id()
                print(f"📍 Transcription ID: {transcription_id}")

                # Split text into sentences
                sentences = transcription_service.split_transcription_into_sentences(text)
                print(f"✂️ Split into {len(sentences)} sentences")

                # Save full transcription
                full_path = transcription_service.save_full_transcription(
                    transcription_id,
                    text
                )
                print(f"✅ Full transcription saved: {full_path}")

                # Save individual sentences
                sentence_paths = transcription_service.save_sentence_transcriptions(
                    transcription_id,
                    sentences
                )
                print(f"✅ Sentence files saved: {len(sentence_paths)} files")

                # Save audio file if provided
                audio_path = None
                if audio_data:
                    try:
                        print(f"🎵 Attempting to save audio... (size: {len(audio_data)} chars)")
                        audio_path = audio_service.save_audio_from_base64(
                            transcription_id,
                            audio_data
                        )
                        print(f"✅ Audio file saved: {audio_path}")
                    except Exception as e:
                        print(f"⚠️ Audio save error: {str(e)}")

                # Save to TranscriptionSession (existing flow)
                session = TranscriptionSession.objects.create(
                    transcription_id=transcription_id,
                    full_text=text,
                    sentence_count=len(sentences),
                    audio_file_path=audio_path or "",
                    transcription_dir_path=str(transcription_service.get_transcription_path(transcription_id))
                )

                # Create sentence records
                for idx, sentence in enumerate(sentences, 1):
                    sentence_file_path = transcription_service.transcription_root / transcription_id / f"{transcription_id}_sentence_{idx}.txt"
                    TranscriptionSentence.objects.create(
                        session=session,
                        sentence_number=idx,
                        text=sentence,
                        file_path=str(sentence_file_path)
                    )

                # Fetch/create conversation early so the student agent can see prior turns
                conversation = _get_or_create_conversation(request) if request.user.is_authenticated else None

                # Persona student: reply in-persona using the knowledge trained so far.
                # Training itself happens once, in batch, when the conversation ends
                # (see new_conversation) — not on every turn. Guests and any Ollama
                # failure fall back to the previous echo behavior.
                bot_text = text
                if request.user.is_authenticated:
                    try:
                        history = [
                            ("user" if m.from_user else "assistant", m.text)
                            for m in conversation.messages.order_by('-message_number')[:6]
                        ][::-1]
                        bot_text = persona_service.generate_reply(request.user, text, history) or text
                    except Exception as e:
                        print(f"⚠️ StudentAgent błąd, fallback na echo: {e}")
                else:
                    print("ℹ️ Gość — generyczna odpowiedź (echo), brak profilu")

                # Generate TTS audio for bot response. Prefer the curated set of
                # reference clips (built up over past conversations) for a more
                # stable voice clone; fall back to this utterance's own recording
                # for guests or before any clips have been curated yet.
                speaker_reference = audio_path
                finetuned_checkpoint_dir = None
                if request.user.is_authenticated:
                    try:
                        stored_clips = voice_service.get_reference_clips_for_user(request.user)
                        if stored_clips:
                            speaker_reference = stored_clips
                    except Exception as e:
                        print(f"⚠️ Nie udało się pobrać klipów referencyjnych głosu: {e}")
                    try:
                        finetuned_checkpoint_dir = voice_finetune_service.checkpoint_dir_for_user(request.user)
                    except Exception as e:
                        print(f"⚠️ Nie udało się sprawdzić fine-tunowanego checkpointu: {e}")

                bot_audio_url = None
                if audio_path:
                    try:
                        bot_audio_path = tts_service.synthesize(
                            bot_text, speaker_reference,
                            finetuned_checkpoint_dir=finetuned_checkpoint_dir,
                        )
                        bot_audio_url  = settings.MEDIA_URL + "tts/" + os.path.basename(bot_audio_path)
                        mode = "fine-tune" if finetuned_checkpoint_dir else "zero-shot"
                        print(f"🔊 TTS wygenerowany ({mode}): {bot_audio_path}")
                    except Exception as e:
                        print(f"⚠️ TTS błąd: {e}")

                # Save to Conversation / Message / AudioRecord (logged-in users only)
                conversation_id = None
                message_number  = None
                if request.user.is_authenticated:
                    message_number = conversation.messages.count() + 1
                    message = Message.objects.create(
                        conversation=conversation,
                        text=text,
                        from_user=True,
                        message_number=message_number,
                    )
                    if audio_path:
                        AudioRecord.objects.create(
                            conversation=conversation,
                            wav_path=audio_path,
                            text_message=message,
                        )
                    Message.objects.create(
                        conversation=conversation,
                        text=bot_text,
                        from_user=False,
                        message_number=message_number + 1,
                    )
                    conversation_id = conversation.id
                    print(f"✅ Conversation #{conversation_id} | Message #{message_number} zapisany")
                else:
                    print("ℹ️ Gość — pomijam zapis konwersacji")

                return JsonResponse({
                    "status":           "session_complete",
                    "transcription_id": transcription_id,
                    "sentence_count":   len(sentences),
                    "audio_saved":      bool(audio_path),
                    "conversation_id":  conversation_id,
                    "message_number":   message_number,
                    "bot_response":     bot_text,
                    "bot_audio_url":    bot_audio_url,
                })

            return JsonResponse({"status": "ok"})

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            print(f"❌ {error_msg}")
            return JsonResponse({"status": "error", "message": error_msg}, status=400)
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error: {error_msg}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "status": "error",
                "message": error_msg
            }, status=500)

    return JsonResponse({"status": "error", "message": "POST method required"}, status=405)


def conversation_list(request):
    active_id = request.session.get('conversation_id')
    qs = Conversation.objects.prefetch_related('messages')
    if request.user.is_authenticated:
        qs = qs.filter(user=request.user)
    else:
        qs = qs.filter(user__isnull=True)
    convs = qs.order_by('-created_at')[:40]
    data = []
    for c in convs:
        first_msg = c.messages.filter(from_user=True).first()
        data.append({
            'id': c.id,
            'created_at': c.created_at.isoformat(),
            'message_count': c.messages.count(),
            'preview': first_msg.text[:60] if first_msg else '',
            'active': c.id == active_id,
        })
    return JsonResponse({'conversations': data})


def conversation_messages(request, conv_id):
    try:
        conv = Conversation.objects.get(id=conv_id)
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    msgs = []
    for m in conv.messages.order_by('message_number'):
        audio = m.audio_records.first()
        audio_url = None
        if audio and audio.wav_path:
            audio_url = settings.MEDIA_URL + 'wavs/' + os.path.basename(audio.wav_path)
        msgs.append({
            'id': m.id,
            'text': m.text,
            'from_user': m.from_user,
            'created_at': m.created_at.isoformat(),
            'audio_url': audio_url,
        })

    request.session['conversation_id'] = conv_id
    return JsonResponse({'messages': msgs, 'conversation_id': conv_id})


def _train_persona_async(user, transcript):
    try:
        persona_service.train_for_user(user, transcript)
    except Exception as e:
        print(f"⚠️ Trening persony (koniec rozmowy) nie powiódł się: {e}")


def _start_persona_training(user, transcript):
    # Training takes several Ollama round-trips (multiple iterations) — running it
    # inline would make "Nowa rozmowa" (and the idle/unload auto-finalize) hang for
    # tens of seconds. Fire-and-forget in a background thread instead; the response
    # to the client doesn't depend on training having finished.
    threading.Thread(target=_train_persona_async, args=(user, transcript), daemon=True).start()


def _best_audio_record(conversation):
    """Picks the largest (roughly: longest) recording from the conversation as
    the one worth keeping as a voice reference — cheap proxy for "most useful
    sample" without any real audio analysis."""
    records = list(AudioRecord.objects.filter(conversation=conversation))
    if not records:
        return None

    def size(record):
        try:
            return os.path.getsize(record.wav_path)
        except OSError:
            return 0

    return max(records, key=size)


def _curate_voice_clip_async(user, wav_path, transcript):
    try:
        emotion = classify_emotion(transcript)
    except Exception as e:
        print(f"⚠️ Klasyfikacja emocji nie powiodła się, fallback na neutral: {e}")
        emotion = "neutral"
    try:
        voice_service.add_clip_for_user(user, wav_path, emotion=emotion)
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać klipu głosowego: {e}")


def _start_voice_curation(user, wav_path, transcript):
    # Same reasoning as _start_persona_training: classify_emotion is an Ollama
    # call, so keep it off the request path that new_conversation needs to
    # answer quickly.
    threading.Thread(
        target=_curate_voice_clip_async, args=(user, wav_path, transcript), daemon=True
    ).start()


def new_conversation(request):
    if request.method == 'POST':
        conversation_id = request.session.get('conversation_id')
        if request.user.is_authenticated and conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
                transcript = "\n".join(
                    m.text for m in
                    conversation.messages.filter(from_user=True).order_by('message_number')
                )
                if transcript.strip():
                    _start_persona_training(request.user, transcript)

                best_audio = _best_audio_record(conversation)
                if best_audio:
                    _start_voice_curation(request.user, best_audio.wav_path, transcript)

                try:
                    if voice_finetune_service.is_ready(request.user):
                        print(
                            f"🎙️ {request.user.username} ma wystarczająco nagrań do fine-tuningu głosu "
                            f"(uruchom: python manage.py finetune_voice {request.user.username})"
                        )
                except Exception as e:
                    print(f"⚠️ Nie udało się sprawdzić gotowości do fine-tuningu: {e}")
            except Conversation.DoesNotExist:
                pass
        request.session.pop('conversation_id', None)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)


def delete_conversation(request, conv_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Musisz być zalogowany'}, status=403)
    try:
        conversation = Conversation.objects.get(id=conv_id, user=request.user)
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    conversation.delete()
    if request.session.get('conversation_id') == conv_id:
        request.session.pop('conversation_id', None)
    return JsonResponse({'status': 'ok'})


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'home/register.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)

    conv_count = Conversation.objects.filter(user=request.user).count()
    msg_count  = Message.objects.filter(
        conversation__user=request.user, from_user=True
    ).count()

    return render(request, 'home/profile.html', {
        'form':       form,
        'conv_count': conv_count,
        'msg_count':  msg_count,
    })