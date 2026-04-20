# 🚀 Quick Setup Guide - Transcription Feature

## ⚠️ Latest Updates (April 20, 2026)

### Fixed Issues
- ✅ Duplicate sentence files issue resolved
- ✅ Database configuration fixed
- ✅ Setup process now fully working
- ✅ Admin credentials configured

---

## Installation Steps

### 1. Activate Virtual Environment

```bash
# On Windows
.\venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Django 4.2.8
- scipy (for audio processing)
- numpy (for numerical operations)

### 3. Create Database Migrations

```bash
python trainme/manage.py makemigrations
python trainme/manage.py migrate
```

This creates two new database tables:
- `home_transcriptionsession` - Tracks complete sessions
- `home_transcriptionsentence` - Stores individual sentences

### 4. Create Superuser (Admin Account)

```bash
# If not already created
python trainme/manage.py createsuperuser

# Or use existing:
# Username: admin
# Password: admin123
```

### 5. Create Media Directories

Media folders will be automatically created when Django starts:
- `media/text_transcription/` - Transcription files
- `media/wavs/` - Audio recordings

### 6. Run Development Server

```bash
python trainme/manage.py runserver
```

Navigate to: 
- **Application**: `http://localhost:8000`
- **Admin Panel**: `http://localhost:8000/admin/`

Login with:
```
Username: admin
Password: admin123
```

### 6. Access Admin Panel (Optional)

```
http://localhost:8000/admin/
```

Login with your superuser credentials to view:
- Transcription Sessions
- Individual Sentences

## How It Works

### Flow Diagram

```
User speaks
    ↓
[Browser Recording Audio + Speech-to-Text]
    ↓
Click "Stop" button
    ↓
[Generate unique ID: 20260420_143052_a1b2c3d4]
    ↓
[Backend Processing]
    ├── Split text into sentences
    ├── Save full transcription: ID_full.txt
    ├── Save sentences: ID_sentence_1.txt, ID_sentence_2.txt, etc.
    └── Save audio: ID.wav
    ↓
[Database Storage]
    ├── TranscriptionSession record
    └── TranscriptionSentence records (one per sentence)
    ↓
User gets confirmation ✅
```

## File Structure Created

After one recording session:

```
trainme_django-main/
├── media/
│   ├── text_transcription/
│   │   └── 20260420_143052_a1b2c3d4/
│   │       ├── 20260420_143052_a1b2c3d4_full.txt
│   │       ├── 20260420_143052_a1b2c3d4_sentence_1.txt
│   │       ├── 20260420_143052_a1b2c3d4_sentence_2.txt
│   │       └── ...
│   └── wavs/
│       └── 20260420_143052_a1b2c3d4.wav
├── trainme/
│   ├── home/
│   │   ├── models.py (Updated ✅)
│   │   ├── views.py (Updated ✅)
│   │   ├── admin.py (Updated ✅)
│   │   ├── transcription_service.py (New ✅)
│   │   ├── audio_service.py (New ✅)
│   │   ├── static/
│   │   │   └── home/
│   │   │       └── app.js (Updated ✅)
│   │   └── ...
│   ├── settings.py (Updated ✅)
│   └── ...
├── requirements.txt (Updated ✅)
└── ...
```

## Testing the Feature

### Test Sequence

1. **Start Recording**
   - Click "Start Talking" button
   - Button changes to "Stop" with listening indicator
   - Microphone access required

2. **Speak**
   - Speak clearly in Polish (set to pl-PL)
   - Watch real-time transcription appear
   - Audio is being recorded simultaneously

3. **End Session**
   - Click "Stop" button
   - System processes the transcription
   - Files are created and saved
   - Database is updated
   - You see: `✅ Sesja ukończona! ID: [transcription_id] Zdań: [count]`

4. **Verify Files**
   - Check `media/text_transcription/[ID]/` folder
   - Check `media/wavs/[ID].wav` file
   - Open Admin panel to see database records

## Available Endpoints

### Speech Processing Endpoint

**POST** `/speech/`

**Interim Request** (while speaking):
```json
{
    "text": "interim transcription text",
    "is_session_end": false
}
```

**Final Request** (when done speaking):
```json
{
    "text": "full transcription text",
    "audio": "base64_encoded_audio_data",
    "is_session_end": true
}
```

**Response on Completion**:
```json
{
    "status": "session_complete",
    "transcription_id": "20260420_143052_a1b2c3d4",
    "sentence_count": 5,
    "audio_saved": true
}
```

## Troubleshooting

### Issue: "Microphone access denied"
**Solution**: 
- Grant microphone permissions in browser settings
- Refresh the page
- Try a different browser

### Issue: "Audio files not being saved"
**Solution**:
- Verify `media/wavs/` directory exists
- Check file permissions: `chmod 755 media/`
- Check Django logs for errors

### Issue: "Transcription files not created"
**Solution**:
- Verify `media/text_transcription/` directory exists
- Check disk space
- Review Django console output

### Issue: "Database tables not created"
**Solution**:
```bash
python manage.py makemigrations home
python manage.py migrate
```

## Key Files Modified/Created

### New Files:
- ✅ `home/transcription_service.py` - Transcription management
- ✅ `home/audio_service.py` - Audio file handling
- ✅ `TRANSCRIPTION_FEATURE.md` - Full documentation

### Modified Files:
- ✅ `home/models.py` - Added TranscriptionSession and TranscriptionSentence
- ✅ `home/views.py` - Updated speech_input view
- ✅ `home/admin.py` - Registered models in admin
- ✅ `home/static/home/app.js` - Added audio recording
- ✅ `trainme/settings.py` - Added media configuration
- ✅ `requirements.txt` - Added dependencies

## Next Steps (Optional)

Consider implementing:
1. API endpoint to retrieve transcriptions
2. Download transcription files
3. Edit and save corrections
4. Export to different formats
5. Multi-language support
6. Real-time transcription updates
7. Transcription search functionality
8. Batch transcription processing

## Support & Documentation

- Full feature documentation: [TRANSCRIPTION_FEATURE.md](TRANSCRIPTION_FEATURE.md)
- Django documentation: https://docs.djangoproject.com/
- Web Audio API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
