from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import json
from .transcription_service import TranscriptionService
from .audio_service import AudioService
from .models import TranscriptionSession, TranscriptionSentence


# Initialize services
transcription_service = TranscriptionService()
audio_service = AudioService()


def home(request):
    return render(request, 'home/home.html')



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
                        # Don't fail the entire request if audio fails
                
                # Save to database
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
                
                print("✅ Database records created")
                return JsonResponse({
                    "status": "session_complete",
                    "transcription_id": transcription_id,
                    "sentence_count": len(sentences),
                    "audio_saved": bool(audio_path)
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