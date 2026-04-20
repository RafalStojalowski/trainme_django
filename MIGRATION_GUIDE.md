# 🔄 Migration & Database Setup Guide

## Overview

This guide walks you through setting up the database for the new transcription features.

---

## ⚡ Quick Migration (5 minutes)

```bash
# 1. Create migrations
python manage.py makemigrations home

# 2. Review migrations (optional)
python manage.py showmigrations home

# 3. Apply migrations
python manage.py migrate home

# 4. Verify tables were created
python manage.py dbshell
# .tables (in SQLite shell)
```

---

## 📋 Step-by-Step Instructions

### Step 1: Verify Django App

```bash
# Check that home app is in INSTALLED_APPS
python manage.py check

# Output should show: System check identified no issues
```

### Step 2: Create Migrations

```bash
# Generate migration files from models
python manage.py makemigrations home

# Output:
# Migrations for 'home':
#   home/migrations/000X_auto_YYYYMMDD_HHMM.py
#     - Create model TranscriptionSession
#     - Create model TranscriptionSentence
```

### Step 3: Review Migrations (Optional)

```bash
# See pending migrations
python manage.py showmigrations home

# Output:
# home
#  [ ] 000X_auto_YYYYMMDD_HHMM
#       - Create model TranscriptionSession
#       - Create model TranscriptionSentence
```

### Step 4: Apply Migrations

```bash
# Execute migrations to create tables
python manage.py migrate home

# Output:
# Running migrations:
#   Applying home.000X_auto_YYYYMMDD_HHMM... OK
```

### Step 5: Verify Database

```bash
# Connect to database
python manage.py dbshell

# List tables (SQLite)
.tables

# You should see:
# home_transcriptionsession
# home_transcriptionsentence
# (and other existing tables)

# View table structure
.schema home_transcriptionsession
.schema home_transcriptionsentence

# Exit
.exit
```

---

## 🔍 Verify Tables Were Created

### Using Django Shell

```bash
python manage.py shell

# Test imports
>>> from home.models import TranscriptionSession, TranscriptionSentence
>>> 
>>> # Check if models are registered
>>> TranscriptionSession.objects.model._meta.db_table
'home_transcriptionsession'
>>> 
>>> TranscriptionSentence.objects.model._meta.db_table
'home_transcriptionsentence'
>>>
>>> # Get count (should be 0 initially)
>>> TranscriptionSession.objects.count()
0
>>>
>>> # Exit
>>> exit()
```

### Using SQL

```bash
python manage.py dbshell

-- List all tables
.tables

-- Show TranscriptionSession columns
PRAGMA table_info(home_transcriptionsession);

-- Show TranscriptionSentence columns
PRAGMA table_info(home_transcriptionsentence);

-- Check for any data
SELECT COUNT(*) FROM home_transcriptionsession;
SELECT COUNT(*) FROM home_transcriptionsentence;

.exit
```

---

## 📊 Table Structure

### TranscriptionSession Table

```sql
CREATE TABLE home_transcriptionsession (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcription_id VARCHAR(255) NOT NULL UNIQUE,
    full_text TEXT,
    sentence_count INTEGER NOT NULL,
    audio_file_path VARCHAR(500),
    transcription_dir_path VARCHAR(500),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

### TranscriptionSentence Table

```sql
CREATE TABLE home_transcriptionsentence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    sentence_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    file_path VARCHAR(500),
    created_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES home_transcriptionsession (id),
    UNIQUE(session_id, sentence_number)
);
```

---

## 🚀 Common Migration Tasks

### Task 1: Show All Migrations

```bash
python manage.py showmigrations

# Shows entire migration history including dependencies
```

### Task 2: Apply All Pending Migrations

```bash
python manage.py migrate

# Applies all pending migrations across all apps
```

### Task 3: Rollback Last Migration

```bash
# First find the migration before the current one
python manage.py showmigrations home

# Then migrate to that specific migration
python manage.py migrate home 0001_initial

# (Replace 0001_initial with actual migration name)
```

### Task 4: Fake Migration (if you modified database manually)

```bash
# Mark migration as applied without running it
python manage.py migrate home 0002_auto --fake

# Use with caution - only if you know what you're doing!
```

### Task 5: Check Migration Status

```bash
python manage.py showmigrations home

# [ ] = Not applied
# [X] = Applied
```

---

## 🔄 Fresh Database Setup

If you want to start completely fresh:

```bash
# ⚠️ WARNING: This deletes all data!

# 1. Delete database file (SQLite)
rm db.sqlite3

# 2. Run all migrations from scratch
python manage.py migrate

# 3. Create superuser (if needed)
python manage.py createsuperuser

# 4. Verify
python manage.py check
```

---

## 🐛 Troubleshooting Migrations

### Issue: "No changes detected in models"

**Cause**: Models haven't changed since last migration

**Solution**: 
- Check if you actually modified models.py
- Check app is in INSTALLED_APPS
- Try: `python manage.py makemigrations home --empty --name fix_something`

### Issue: "Migration conflicts"

**Cause**: Multiple migrations with same number

**Solution**:
```bash
# Resolve conflicts
python manage.py makemigrations --merge

# Review generated merge migration
# Apply it
python manage.py migrate
```

### Issue: "Table already exists"

**Cause**: You ran migrations manually or partially

**Solution**:
```bash
# Check current state
python manage.py showmigrations

# See what's been applied
python manage.py migrate home --list

# Fake-apply pending migrations
python manage.py migrate home --fake
```

### Issue: "Migration fails on migrate"

**Cause**: Syntax error or logic error in migration

**Solution**:
```bash
# Rollback to previous working migration
python manage.py migrate home 0001_initial

# Edit migration file to fix error
# Then try again
python manage.py migrate home
```

### Issue: "Cannot find migration"

**Cause**: Wrong app name or missing migrations folder

**Solution**:
```bash
# Check migrations folder exists
ls trainme/home/migrations/

# Ensure __init__.py exists
ls trainme/home/migrations/__init__.py

# Use correct app name
python manage.py migrate home
```

---

## 📝 Migration File Anatomy

### Sample Migration File

```python
# Generated migration file name: 0001_initial.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    # Which migrations this depends on
    dependencies = [
    ]

    # Operations to apply
    operations = [
        # Create TranscriptionSession table
        migrations.CreateModel(
            name='TranscriptionSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, 
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('transcription_id', models.CharField(max_length=255, 
                 unique=True)),
                ('full_text', models.TextField(blank=True, null=True)),
                ('sentence_count', models.IntegerField(default=0)),
                ('audio_file_path', models.CharField(blank=True, 
                 max_length=500, null=True)),
                ('transcription_dir_path', models.CharField(blank=True, 
                 max_length=500, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Transcription Session',
                'verbose_name_plural': 'Transcription Sessions',
                'ordering': ['-created_at'],
            },
        ),
        
        # Create TranscriptionSentence table
        migrations.CreateModel(
            name='TranscriptionSentence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, 
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('sentence_number', models.IntegerField()),
                ('text', models.TextField()),
                ('file_path', models.CharField(blank=True, max_length=500, 
                 null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                 related_name='sentences', to='home.transcriptionsession')),
            ],
            options={
                'verbose_name': 'Transcription Sentence',
                'verbose_name_plural': 'Transcription Sentences',
                'ordering': ['sentence_number'],
                'unique_together': {('session', 'sentence_number')},
            },
        ),
    ]
```

---

## ✅ Post-Migration Checklist

After running migrations:

- [ ] No errors in console
- [ ] `python manage.py check` shows all OK
- [ ] Database file exists (db.sqlite3)
- [ ] Tables created in database
- [ ] Can import models in Django shell
- [ ] Admin interface loads
- [ ] Can add records in admin
- [ ] Can view records in admin

---

## 🔐 Production Deployment

### Before Going Live

```bash
# 1. Test migrations on fresh database
rm db.sqlite3
python manage.py migrate

# 2. Run checks
python manage.py check --deploy

# 3. Create admin user
python manage.py createsuperuser

# 4. Test everything works
python manage.py runserver
# Visit http://localhost:8000

# 5. Collect static files (if needed)
python manage.py collectstatic --noinput

# 6. Check permissions
chmod 755 media/
chmod 755 media/text_transcription/
chmod 755 media/wavs/
```

### On Production Server

```bash
# 1. Pull code changes
git pull origin main

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate --no-input

# 4. Collect static files
python manage.py collectstatic --no-input

# 5. Restart application server
systemctl restart django_app
# or
supervisorctl restart trainme
```

---

## 📊 Monitoring

### Check Migration Status

```python
# In Django shell
python manage.py shell

from django.db.migrations.loader import MigrationLoader
from django.db.backends.utils import truncate_name

loader = MigrationLoader(None, ignore_no_migrations=True)
graph = loader.graph

# Show all applied migrations
for migration_key in graph.leaf_nodes():
    print(migration_key)

exit()
```

### Database Size

```bash
# Check SQLite database size
ls -lh db.sqlite3

# Expected: Growing with each record added
```

### Performance

```sql
-- Count records
SELECT COUNT(*) FROM home_transcriptionsession;
SELECT COUNT(*) FROM home_transcriptionsentence;

-- Show indexes
PRAGMA index_list(home_transcriptionsession);

-- Show query plan
EXPLAIN QUERY PLAN
SELECT * FROM home_transcriptionsession 
WHERE transcription_id = '...';
```

---

## 🔄 Zero-Downtime Migration Strategy

For production with existing data:

```bash
# 1. Deploy code changes
git pull origin main

# 2. Run migrations (non-blocking for most changes)
python manage.py migrate --no-input

# 3. Monitor for issues
tail -f logs/django.log

# 4. Rollback if needed (keep old migration)
python manage.py migrate home 0001_initial

# 5. Quick restart
systemctl restart django_app
```

---

## 📚 Additional Resources

### Django Migration Documentation
https://docs.djangoproject.com/en/4.2/topics/migrations/

### Django Models Documentation
https://docs.djangoproject.com/en/4.2/topics/db/models/

### SQLite Documentation
https://www.sqlite.org/

---

## ✨ Success Indicators

Migrations are successful when:
- ✅ No errors in console output
- ✅ Tables appear in database
- ✅ Models can be imported
- ✅ Admin interface shows models
- ✅ Can create records via admin
- ✅ Application starts without errors

---

## 🎯 Next Steps

After migrations are complete:

1. **Test the Feature**
   - Start recording
   - Verify files are created
   - Check database entries

2. **Backup Database**
   - Copy db.sqlite3 to backup location
   - Set up automated backups

3. **Monitor**
   - Watch application logs
   - Check disk space for media files
   - Monitor database growth

4. **Scale Up**
   - Consider separate database (PostgreSQL)
   - Set up media file storage (S3, etc.)
   - Implement caching if needed

---

## 📞 Need Help?

**Migration Issues?**
- Check Django documentation
- Review error messages carefully
- Check console output for hints
- Look at migration file contents

**Database Questions?**
- Use Django shell to test
- Check admin interface
- Run SQL queries directly
- Monitor logs

**Still Stuck?**
- Rollback and try again
- Check SETUP_GUIDE.md
- Review IMPLEMENTATION_DETAILS.md

---

Good luck with your migrations! 🚀
