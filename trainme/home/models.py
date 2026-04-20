from django.db import models
from django.utils import timezone


class TranscriptionSession(models.Model):
    """Model to track transcription sessions with unique identifiers."""
    
    transcription_id = models.CharField(
        max_length=255, 
        unique=True, 
        help_text="Unique identifier for the transcription session"
    )
    full_text = models.TextField(
        blank=True, 
        null=True,
        help_text="Full transcription text"
    )
    sentence_count = models.IntegerField(
        default=0,
        help_text="Number of sentences in the transcription"
    )
    audio_file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to the WAV audio file"
    )
    transcription_dir_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to the transcription directory"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session {self.transcription_id} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Transcription Session"
        verbose_name_plural = "Transcription Sessions"


class TranscriptionSentence(models.Model):
    """Model to track individual sentences within a transcription."""
    
    session = models.ForeignKey(
        TranscriptionSession,
        on_delete=models.CASCADE,
        related_name='sentences'
    )
    sentence_number = models.IntegerField(
        help_text="Sentence sequence number within the session"
    )
    text = models.TextField(
        help_text="The sentence text"
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to the sentence text file"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Sentence {self.sentence_number} from {self.session.transcription_id}"
    
    class Meta:
        ordering = ['sentence_number']
        unique_together = ('session', 'sentence_number')
        verbose_name = "Transcription Sentence"
        verbose_name_plural = "Transcription Sentences"
