from django.db import models
from django.contrib.auth.models import User


class TranscriptionSession(models.Model):
    transcription_id = models.CharField(max_length=255, unique=True,
        help_text='Unique identifier for the transcription session')
    full_text = models.TextField(blank=True, null=True,
        help_text='Full transcription text')
    sentence_count = models.IntegerField(default=0,
        help_text='Number of sentences in the transcription')
    audio_file_path = models.CharField(max_length=500, blank=True, null=True,
        help_text='Path to the WAV audio file')
    transcription_dir_path = models.CharField(max_length=500, blank=True, null=True,
        help_text='Path to the transcription directory')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transcription Session'
        verbose_name_plural = 'Transcription Sessions'
        ordering = ['-created_at']

    def __str__(self):
        return self.transcription_id


class TranscriptionSentence(models.Model):
    session = models.ForeignKey(TranscriptionSession, on_delete=models.CASCADE,
        related_name='sentences')
    sentence_number = models.IntegerField(
        help_text='Sentence sequence number within the session')
    text = models.TextField(help_text='The sentence text')
    file_path = models.CharField(max_length=500, blank=True, null=True,
        help_text='Path to the sentence text file')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transcription Sentence'
        verbose_name_plural = 'Transcription Sentences'
        ordering = ['sentence_number']
        unique_together = [('session', 'sentence_number')]

    def __str__(self):
        return f"{self.session.transcription_id} – zdanie {self.sentence_number}"


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Conversation #{self.pk} ({self.created_at:%Y-%m-%d %H:%M})"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
        related_name='messages')
    text = models.TextField()
    from_user = models.BooleanField()
    message_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['message_number']

    def __str__(self):
        speaker = "user" if self.from_user else "bot"
        return f"[{speaker}] msg #{self.message_number}: {self.text[:60]}"


class AudioRecord(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
        related_name='audio_records')
    wav_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    text_message = models.ForeignKey(Message, on_delete=models.CASCADE,
        related_name='audio_records')

    def __str__(self):
        return f"Audio for msg #{self.text_message.message_number} in conv #{self.conversation_id}"
