# 🔧 Implementation Details - Developer Guide

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Browser)                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │  app.js - Speech Recognition & Audio Recording   │  │
│  │  ├── SpeechRecognition API (pl-PL)              │  │
│  │  ├── MediaRecorder API (Audio)                  │  │
│  │  └── Blob to Base64 Conversion                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓ (HTTP POST)
┌─────────────────────────────────────────────────────────┐
│                 Django Backend                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  views.py - speech_input() endpoint              │  │
│  │  └── Receives text & audio data                  │  │
│  └───────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  transcription_service.py                         │  │
│  │  ├── Generate unique ID                          │  │
│  │  ├── Create directory structure                  │  │
│  │  ├── Save full transcription                     │  │
│  │  └── Split & save sentences                      │  │
│  └───────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  audio_service.py                                │  │
│  │  ├── Decode Base64 audio                         │  │
│  │  └── Save as WAV file                            │  │
│  └───────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  models.py - Database Storage                    │  │
│  │  ├── TranscriptionSession                        │  │
│  │  └── TranscriptionSentence                       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓ (File System)
┌─────────────────────────────────────────────────────────┐
│                  File Storage                            │
│  ├── media/text_transcription/[ID]/                    │
│  │   ├── [ID]_full.txt                              │  │
│  │   ├── [ID]_sentence_1.txt                        │  │
│  │   ├── [ID]_sentence_2.txt                        │  │
│  │   └── ...                                        │  │
│  └── media/wavs/[ID].wav                            │  │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Session Lifecycle

```
1. USER STARTS RECORDING
   ├── JavaScript: setupAudioRecording()
   ├── Start SpeechRecognition.start()
   └── Start MediaRecorder.start()

2. DURING RECORDING
   ├── Speech API: recognition.onresult (interim)
   │   └── Send interim transcription to backend
   ├── Audio API: Collect audio chunks
   └── UI: Display real-time text

3. USER STOPS RECORDING
   ├── JavaScript: recognition.stop()
   ├── JavaScript: mediaRecorder.stop()
   └── Audio collected into Blob

4. SESSION ENDS (recognition.onend)
   ├── Convert audio Blob to Base64
   ├── Gather final transcription text
   └── POST to /speech/ endpoint

5. BACKEND PROCESSING
   ├── Generate unique transcription_id
   ├── Split text into sentences
   ├── Save transcription files
   ├── Decode and save audio
   └── Create database records

6. RESPONSE TO CLIENT
   ├── Return session_complete status
   ├── Include transcription_id
   ├── Include sentence_count
   └── Show confirmation to user

7. FILES CREATED
   ├── media/text_transcription/[ID]_full.txt
   ├── media/text_transcription/[ID]_sentence_N.txt
   └── media/wavs/[ID].wav
```

## Key Classes and Methods

### TranscriptionService

```python
class TranscriptionService:
    
    # ID Generation
    def generate_transcription_id() -> str
        # Returns: "20260420_143052_a1b2c3d4"
    
    # Directory Management
    def create_transcription_directory(transcription_id: str) -> Path
        # Creates: media/text_transcription/[ID]/
    
    def ensure_root_exists() -> None
        # Ensures root directory exists
    
    # File Operations
    def save_full_transcription(transcription_id: str, full_text: str) -> Path
        # Saves: [ID]_full.txt
    
    def save_sentence_transcriptions(transcription_id: str, sentences: List[str]) -> List[Path]
        # Saves: [ID]_sentence_1.txt, [ID]_sentence_2.txt, ...
    
    # Text Processing
    def split_transcription_into_sentences(text: str) -> List[str]
        # Splits text by sentence terminators (. ! ?)
    
    # Utilities
    def get_transcription_path(transcription_id: str) -> Path
    def list_transcriptions() -> List[str]
```

### AudioService

```python
class AudioService:
    
    # Setup
    def ensure_audio_dir_exists() -> None
        # Creates media/wavs/
    
    # File Saving
    def save_audio_from_base64(transcription_id: str, audio_base64: str) -> str
        # Decodes Base64 and saves WAV
    
    def save_audio_from_blob(transcription_id: str, audio_data, sample_rate=16000) -> str
        # Saves numpy array as WAV
    
    # Utilities
    def audio_exists(transcription_id: str) -> bool
    def get_audio_path(transcription_id: str) -> Path
    def list_audio_files() -> List[str]
    def delete_audio_file(transcription_id: str) -> bool
```

### Models

```python
class TranscriptionSession(models.Model):
    transcription_id: CharField(unique=True)
    full_text: TextField()
    sentence_count: IntegerField()
    audio_file_path: CharField()
    transcription_dir_path: CharField()
    created_at: DateTimeField(auto_now_add=True)
    updated_at: DateTimeField(auto_now=True)

class TranscriptionSentence(models.Model):
    session: ForeignKey(TranscriptionSession)
    sentence_number: IntegerField()
    text: TextField()
    file_path: CharField()
    created_at: DateTimeField(auto_now_add=True)
```

## Frontend JavaScript Functions

### Core Functions

```javascript
// Audio Setup
async function setupAudioRecording()
    // Requests microphone access
    // Creates MediaRecorder instance

// Transcription Processing
async function sendFinalTranscription(text: string)
    // Converts audio to Base64
    // Sends complete session data to backend
    // Handles response

// Data Conversion
function blobToBase64(blob: Blob) -> Promise<string>
    // Converts audio Blob to Base64 string

// Utilities
function getCookie(name: string) -> string
    // Retrieves CSRF token from cookies
```

### Event Handlers

```javascript
// Button Click
startBtn.onclick = () => {
    if (!isListening) {
        recognition.start()
        mediaRecorder.start()
    } else {
        recognition.stop()
        mediaRecorder.stop()
    }
}

// Speech Recognition Events
recognition.onstart = () => { /* Update UI */ }
recognition.onresult = (event) => { 
    /* Handle interim/final results */
    /* Collect final text */
}
recognition.onerror = (event) => { /* Handle errors */ }
recognition.onend = () => {
    /* Send final transcription */
    /* Update UI with results */
}

// Audio Recording
mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data)
}
```

## API Endpoint Details

### POST /speech/

#### Request (Interim):
```json
{
    "text": "some interim text",
    "is_session_end": false
}
```

#### Request (Final - Session End):
```json
{
    "text": "full transcription with all sentences",
    "audio": "base64_encoded_wav_data",
    "is_session_end": true
}
```

#### Response (OK):
```json
{"status": "ok"}
```

#### Response (Session Complete):
```json
{
    "status": "session_complete",
    "transcription_id": "20260420_143052_a1b2c3d4",
    "sentence_count": 5,
    "audio_saved": true
}
```

#### Response (Error):
```json
{
    "status": "error",
    "message": "Error description"
}
```

## Unique ID Generation

### Algorithm

```python
def generate_transcription_id():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Result: "20260420_143052"
    
    unique_suffix = str(uuid.uuid4())[:8]
    # Result: "a1b2c3d4" (first 8 chars of UUID)
    
    return f"{timestamp}_{unique_suffix}"
    # Result: "20260420_143052_a1b2c3d4"
```

### Advantages

- **Sortable**: Chronological order by timestamp
- **Unique**: UUID ensures no collisions
- **Readable**: Human-friendly format
- **Searchable**: Easy to find by date/time
- **Database-Ready**: Perfect for future indexing

## Sentence Splitting Algorithm

### Process

```python
def split_transcription_into_sentences(text):
    1. Replace multiple spaces with single space
    2. Split by sentence terminators (. ! ?)
    3. Keep terminators with sentences
    4. Filter out empty strings
    5. Strip whitespace from each sentence
    6. Return list of sentences
```

### Example

```
Input:  "Hello world. How are you? I'm fine! Great."

Process:
1. Replace spaces: "Hello world. How are you? I'm fine! Great."
2. Split: ["Hello world", ".", " How are you", "?", " I'm fine", "!", " Great", "."]
3. Reconstruct: ["Hello world.", "How are you?", "I'm fine!", "Great."]

Output: ["Hello world.", "How are you?", "I'm fine!", "Great."]
```

## Error Handling

### Frontend Error Handling

```javascript
// Microphone Access Error
setupAudioRecording()
    .catch(error => {
        console.error("Audio setup error:", error)
        statusText.textContent = "Błąd: Brak dostępu do mikrofonu"
    })

// Speech Recognition Error
recognition.onerror = (event) => {
    console.error("Recognition error:", event.error)
    statusText.textContent = "Błąd: " + event.error
}

// Network/Send Error
.catch(error => {
    console.error("Error sending transcription:", error)
    statusText.textContent = "Błąd: Nie udało się wysłać transkrypcji"
})
```

### Backend Error Handling

```python
try:
    data = json.loads(request.body)
    # ... processing ...
except json.JSONDecodeError:
    return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
except Exception as e:
    print(f"❌ Error: {str(e)}")
    return JsonResponse({"status": "error", "message": str(e)}, status=500)
```

## Performance Considerations

### Optimization Tips

1. **Audio File Size**
   - Reduce sample rate if needed
   - Consider compression in future

2. **File I/O**
   - Batch database operations when possible
   - Use async operations for large files

3. **Sentence Splitting**
   - Consider using NLP library (spaCy, NLTK) for better accuracy
   - Cache results if needed

4. **Database Queries**
   - Add indexes on `transcription_id`
   - Use `select_related()` for joins

### Example Optimization

```python
# Add index to database
class TranscriptionSession(models.Model):
    transcription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True  # Add this
    )
```

## Security Considerations

1. **CSRF Protection**: All POST requests include CSRF token
2. **File Validation**: Check file extensions and size
3. **Path Traversal**: Use pathlib for safe path operations
4. **User Input**: Sanitize transcription text
5. **Audio Data**: Validate Base64 encoding

## Testing Checklist

- [ ] Microphone permissions work
- [ ] Audio recording starts/stops correctly
- [ ] Transcription text is captured
- [ ] Files are created with correct names
- [ ] Unique IDs are generated properly
- [ ] Database records are created
- [ ] Sentences are split correctly
- [ ] Audio file is saved in WAV format
- [ ] UI shows completion status
- [ ] Error messages display correctly
