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
from .transcription_service import TranscriptionService
from .audio_service import AudioService
from .tts_service import TTSService
from .models import TranscriptionSession, TranscriptionSentence, Conversation, Message, AudioRecord


tts_service = TTSService()


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

                # TODO: replace with real LLM call
                bot_text = text

                # Generate TTS audio for bot response
                bot_audio_url = None
                if audio_path:
                    try:
                        bot_audio_path = tts_service.synthesize(bot_text, audio_path)
                        bot_audio_url  = settings.MEDIA_URL + "tts/" + os.path.basename(bot_audio_path)
                        print(f"🔊 TTS wygenerowany: {bot_audio_path}")
                    except Exception as e:
                        print(f"⚠️ TTS błąd: {e}")

                # Save to Conversation / Message / AudioRecord (logged-in users only)
                conversation_id = None
                message_number  = None
                if request.user.is_authenticated:
                    conversation   = _get_or_create_conversation(request)
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


def new_conversation(request):
    if request.method == 'POST':
        request.session.pop('conversation_id', None)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)


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