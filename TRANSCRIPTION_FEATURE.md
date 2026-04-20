# 📝 Transcription and Audio Recording Feature

## Overview

This document describes the new transcription and audio recording features added to the TrainMe Django application.

## Features

### 1. 📁 Transcription File Management

The system automatically creates a unique folder structure for each conversation session:

```
media/
├── text_transcription/
│   └── [YYYYMMDD_HHMMSS_XXXXXXXX]/  # Unique transcription ID
│       ├── [ID]_full.txt              # Full transcription text
│       ├── [ID]_sentence_1.txt        # First sentence
│       ├── [ID]_sentence_2.txt        # Second sentence
│       └── [ID]_sentence_N.txt        # Nth sentence
└── wavs/
    └── [YYYYMMDD_HHMMSS_XXXXXXXX].wav # Audio recording
```

### 2. 🎙️ Audio Recording

- Records audio in **WAV format** (.wav extension)
- Automatically saves to `media/wavs/` folder
- File named with unique transcription ID for easy tracking
- Records the complete conversation session

### 3. 🔤 Text Processing

- **Full Transcription**: Complete conversation text saved in a single file
- **Sentence-by-Sentence**: Each sentence automatically extracted and saved in separate files
- **Automatic Numbering**: Sequential numbering for easy database implementation

## Unique ID Format

Each transcription session gets a unique ID combining:
- **Timestamp**: `YYYYMMDD_HHMMSS` (Date and time)
- **UUID suffix**: 8-character unique identifier

**Example ID**: `20260420_143052_a1b2c3d4`

## Database Models

### TranscriptionSession
Tracks each conversation session with:
- `transcription_id` - Unique identifier
- `full_text` - Complete transcription
- `sentence_count` - Number of sentences
- `audio_file_path` - Path to WAV file
- `transcription_dir_path` - Path to transcription folder
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### TranscriptionSentence
Stores individual sentences with:
- `session` - Reference to TranscriptionSession
- `sentence_number` - Sequential number
- `text` - Sentence text
- `file_path` - Path to text file
- `created_at` - Creation timestamp

## File Structure

### Services

#### `transcription_service.py`
Handles transcription management:
- Generate unique IDs
- Create directory structure
- Save full transcriptions
- Split and save individual sentences
- List all transcriptions

#### `audio_service.py`
Handles audio file management:
- Save audio from base64 encoded data
- Support for various audio formats
- Verify audio file existence
- Audio file operations (list, delete)

### Views

#### `speech_input()`
Processes both interim and final transcriptions:
- Accepts text and audio data
- Generates unique transcription ID on session end
- Saves transcription files
- Records audio
- Stores data in database
- Returns transcription summary

### Frontend

#### `app.js`
Enhanced JavaScript with:
- **Audio Recording**: Captures microphone input
- **Session Management**: Tracks session start/stop
- **Data Collection**: Gathers both text and audio
- **Backend Communication**: Sends data to Django backend
- **User Feedback**: Shows progress and completion status

## Usage

### Starting a Recording Session

1. Click "Start Talking" button
2. Speak into your microphone
3. Application records both audio and speech-to-text
4. Click "Stop" to end session

### Session End Process

When recording stops:
1. Full transcription is split into sentences
2. Files are created in `media/text_transcription/[ID]/` folder
3. Audio is saved in `media/wavs/[ID].wav`
4. Data is stored in the database
5. User receives confirmation with transcription ID and sentence count

## API Response

### Session Complete Response
```json
{
    "status": "session_complete",
    "transcription_id": "20260420_143052_a1b2c3d4",
    "sentence_count": 5,
    "audio_saved": true
}
```

## File Paths

### Configuration (settings.py)
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
TRANSCRIPTION_DIR = MEDIA_ROOT / 'text_transcription'
AUDIO_DIR = MEDIA_ROOT / 'wavs'
```

### Example File Paths
- **Full Transcription**: `media/text_transcription/20260420_143052_a1b2c3d4/20260420_143052_a1b2c3d4_full.txt`
- **Sentence 1**: `media/text_transcription/20260420_143052_a1b2c3d4/20260420_143052_a1b2c3d4_sentence_1.txt`
- **Audio**: `media/wavs/20260420_143052_a1b2c3d4.wav`

## Dependencies

Added to `requirements.txt`:
- `scipy>=1.11.0` - Audio processing
- `numpy>=1.24.0` - Numerical operations

Install with:
```bash
pip install -r requirements.txt
```

## Database Migration

Run migrations to create the new models:
```bash
python manage.py makemigrations
python manage.py migrate
```

## Admin Interface

Both models are registered in Django Admin with:
- **TranscriptionSession**: View all sessions, filter by date, search by ID
- **TranscriptionSentence**: View individual sentences, associated with sessions

Access at: `http://localhost:8000/admin/`

## Future Enhancements

Possible improvements:
- Speech recognition confidence scoring
- Timestamp markers for each sentence
- Batch processing of multiple sessions
- Export to various formats (CSV, PDF)
- Integration with NLP for better sentence segmentation
- Cloud storage integration
- Real-time transcription streaming
- Multi-language support

## Troubleshooting

### Audio Not Recording
- Check browser microphone permissions
- Verify `media/wavs/` folder exists
- Check Django MEDIA settings

### Transcription Files Not Created
- Verify `media/text_transcription/` folder exists
- Check file permissions
- Review Django console for errors

### Database Issues
- Run migrations: `python manage.py migrate`
- Check database permissions
- Verify models are registered in admin.py

## Support

For issues or questions, check the console output for detailed error messages.
