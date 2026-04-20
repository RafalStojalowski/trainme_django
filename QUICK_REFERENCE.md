# 🚀 Quick Reference Guide

## ⚡ TL;DR - Just Get Started

### Installation (5 minutes)
```bash
# 1. Navigate to project
cd trainme_django-main

# 2. Activate virtual environment
.\venv\Scripts\activate  # On Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create database tables
python trainme/manage.py makemigrations
python trainme/manage.py migrate

# 5. Start the server
python trainme/manage.py runserver

# 6. Open browser
# http://localhost:8000
# Admin panel: http://localhost:8000/admin/
```

### Admin Panel Credentials
```
Username: admin
Password: admin123
```

### First Test
1. Click **"Start Talking"**
2. Speak in Polish
3. Click **"Stop"**
4. Wait for confirmation ✅

### Check Results
```bash
# View files
ls media/text_transcription/
ls media/wavs/

# View database (in admin)
http://localhost:8000/admin/
Login with: admin / admin123
```

---

## 🔧 Recent Fixes (April 20, 2026)

### ✅ Fixed Issues
1. **Duplicate Sentences Bug** - Fixed excessive sentence file updates during interim transcription
2. **Missing Database Config** - Added DATABASES configuration to settings.py
3. **Interim Request Spam** - Removed sendToBackend interim calls to prevent duplicate sentences

### ✅ Applied Improvements
- Sentences now only saved when session ends (no interim spam)
- Database fully configured with SQLite
- Setup process now works without errors
- Admin panel credentials created

---

## 📁 File Locations Quick Map

| What | Where |
|-----|-------|
| Transcription files | `media/text_transcription/[ID]/` |
| Audio files (.wav) | `media/wavs/` |
| Transcription service | `home/transcription_service.py` |
| Audio service | `home/audio_service.py` |
| Database models | `home/models.py` |
| API endpoint | `home/views.py::speech_input()` |
| Frontend script | `home/static/home/app.js` |
| Configuration | `trainme/settings.py` |

---

## 🎯 Key Features at a Glance

### Feature 1: Unique Session ID
```
Format: YYYYMMDD_HHMMSS_XXXXXXXX
Example: 20260420_143052_a1b2c3d4
Purpose: Identifies each recording uniquely
```

### Feature 2: Automatic File Organization
```
media/text_transcription/20260420_143052_a1b2c3d4/
├── 20260420_143052_a1b2c3d4_full.txt          # Complete text
├── 20260420_143052_a1b2c3d4_sentence_1.txt    # First sentence
├── 20260420_143052_a1b2c3d4_sentence_2.txt    # Second sentence
└── ...
```

### Feature 3: Audio Recording
```
media/wavs/20260420_143052_a1b2c3d4.wav        # WAV format
```

### Feature 4: Database Storage
```
TranscriptionSession table:
- transcription_id (UNIQUE)
- full_text
- sentence_count
- audio_file_path
- timestamps

TranscriptionSentence table:
- session (foreign key)
- sentence_number
- text
- file_path
```

---

## 🔧 Common Tasks

### Task 1: View All Recordings
```python
# In Django shell: python manage.py shell
from home.models import TranscriptionSession

# Get all sessions
sessions = TranscriptionSession.objects.all()
for session in sessions:
    print(f"{session.transcription_id}: {session.sentence_count} sentences")
```

### Task 2: Get Recording Details
```python
session = TranscriptionSession.objects.get(transcription_id='20260420_143052_a1b2c3d4')
print(session.full_text)
print(f"Sentences: {session.sentence_count}")
print(f"Audio: {session.audio_file_path}")
```

### Task 3: List All Sentences
```python
session = TranscriptionSession.objects.get(transcription_id='...')
sentences = session.sentences.all().order_by('sentence_number')
for sentence in sentences:
    print(f"{sentence.sentence_number}: {sentence.text}")
```

### Task 4: Find Recent Recordings
```python
from django.utils import timezone
from datetime import timedelta

# Last 24 hours
recent = TranscriptionSession.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
)
```

### Task 5: Export Transcription
```python
session = TranscriptionSession.objects.get(transcription_id='...')
text = session.full_text

# Save to file
with open('export.txt', 'w', encoding='utf-8') as f:
    f.write(text)
```

---

## 🎙️ Frontend - What Users See

### Before Recording
```
🎤 Speech Recognition
[Start Talking]
Kliknij i zacznij mówić
```

### During Recording
```
🎤 Speech Recognition
[Stop]
Nasłuchiwanie ⚫ (pulsing)
(real-time text appears)
```

### After Recording
```
🎤 Speech Recognition
[Start Talking]
Kliknij i zacznij mówić

✅ Sesja ukończona!
ID: 20260420_143052_a1b2c3d4
Zdań: 5
```

---

## 📱 API Reference

### Endpoint: POST /speech/

#### Request - Interim (while speaking)
```json
{
    "text": "partial transcription",
    "is_session_end": false
}
```

#### Request - Final (when done)
```json
{
    "text": "complete transcription text",
    "audio": "base64_encoded_audio_data",
    "is_session_end": true
}
```

#### Response - Success
```json
{
    "status": "session_complete",
    "transcription_id": "20260420_143052_a1b2c3d4",
    "sentence_count": 5,
    "audio_saved": true
}
```

#### Response - Error
```json
{
    "status": "error",
    "message": "Error description"
}
```

---

## 🐛 Troubleshooting Quick Fix

| Problem | Solution |
|---------|----------|
| "Microphone access denied" | Grant permission in browser settings |
| "No files being created" | Check `media/` folder exists and is writable |
| "Database error" | Run `python manage.py migrate` |
| "Audio not recording" | Check browser console for errors |
| "No transcription" | Speak clearly in Polish (pl-PL) |
| "Server won't start" | Check `pip install -r requirements.txt` |

---

## 📊 Database Queries Cheat Sheet

### Get all sessions
```sql
SELECT * FROM home_transcriptionsession 
ORDER BY created_at DESC;
```

### Get today's recordings
```sql
SELECT * FROM home_transcriptionsession 
WHERE DATE(created_at) = CURDATE();
```

### Get sentences for a session
```sql
SELECT * FROM home_transcriptionsentence 
WHERE session_id = 1
ORDER BY sentence_number;
```

### Count total recordings
```sql
SELECT COUNT(*) FROM home_transcriptionsession;
```

### Most recent session
```sql
SELECT * FROM home_transcriptionsession 
ORDER BY created_at DESC LIMIT 1;
```

---

## 🔍 File Contents Example

### Example: 20260420_143052_a1b2c3d4_full.txt
```
Cześć jak się masz? Jestem w porządku. Dziękuję za pytanie!
```

### Example: 20260420_143052_a1b2c3d4_sentence_1.txt
```
Cześć jak się masz?
```

### Example: 20260420_143052_a1b2c3d4_sentence_2.txt
```
Jestem w porządku.
```

### Example: 20260420_143052_a1b2c3d4_sentence_3.txt
```
Dziękuję za pytanie!
```

---

## 🚀 Performance Tips

1. **Optimize Sentence Splitting**: Use NLP library for better results
2. **Batch Operations**: Group database writes
3. **Audio Compression**: Reduce file size in future updates
4. **Cache Results**: Cache frequent queries
5. **Index Database**: Add indexes on frequently searched fields

---

## 📚 Documentation Links

| Document | Purpose |
|----------|---------|
| TRANSCRIPTION_FEATURE.md | Complete feature details |
| SETUP_GUIDE.md | Installation instructions |
| IMPLEMENTATION_DETAILS.md | Technical implementation |
| FEATURE_SUMMARY.md | Visual overview |
| CHANGES.md | Complete changelog |

---

## ✅ Pre-Launch Checklist

- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Database migrated: `python manage.py migrate`
- [ ] Media folders exist: `media/text_transcription/` and `media/wavs/`
- [ ] Admin accessible: `http://localhost:8000/admin/`
- [ ] Server runs: `python manage.py runserver`
- [ ] Button appears: "Start Talking"
- [ ] Test recording works
- [ ] Files created in `media/`
- [ ] Database records appear in admin
- [ ] No console errors

---

## 🎓 Learning Resources

### For Django Development
- Django Models: https://docs.djangoproject.com/en/4.2/topics/db/models/
- Django Admin: https://docs.djangoproject.com/en/4.2/ref/contrib/admin/
- Django Views: https://docs.djangoproject.com/en/4.2/topics/http/views/

### For Web Audio
- MediaRecorder API: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- Web Audio API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
- Speech Recognition API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API

### For Database
- SQLite: https://www.sqlite.org/docs.html
- SQL Basics: https://www.w3schools.com/sql/

---

## 🤝 Getting Help

1. **Check Logs**: Look at terminal output for errors
2. **Check Browser Console**: F12 → Console tab
3. **Django Shell**: `python manage.py shell` to test queries
4. **Admin Interface**: View recorded data in admin panel
5. **Documentation**: Read the included MD files

---

## 🎉 Success Indicators

You'll know it's working when you see:
- ✅ "Start Talking" button appears
- ✅ Microphone permission request
- ✅ Real-time text in browser
- ✅ "✅ Sesja ukończona!" message
- ✅ Files in `media/text_transcription/`
- ✅ .wav file in `media/wavs/`
- ✅ Records in admin panel
- ✅ No console errors

---

## 🚀 Ready to Launch?

```bash
# Final check
python manage.py check

# Install any missing packages
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver

# Open browser
# http://localhost:8000
```

**You're ready to go! 🚀**

---

## 📞 Quick Support

**Issue**: Features not working
→ Check: Browser console errors

**Issue**: Files not saving
→ Check: `media/` directory permissions

**Issue**: Database empty
→ Check: `python manage.py migrate`

**Issue**: Server won't start
→ Check: `pip install -r requirements.txt`

**Last Resort**: Restart everything
```bash
python manage.py migrate --noinput
python manage.py runserver
```

Good luck! 🎯
