from django.contrib import admin
from .models import TranscriptionSession, TranscriptionSentence


@admin.register(TranscriptionSession)
class TranscriptionSessionAdmin(admin.ModelAdmin):
    list_display = ('transcription_id', 'sentence_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('transcription_id', 'full_text')
    readonly_fields = ('created_at', 'updated_at', 'transcription_id')
    fieldsets = (
        ('Transcription Info', {
            'fields': ('transcription_id', 'full_text', 'sentence_count')
        }),
        ('File Paths', {
            'fields': ('transcription_dir_path', 'audio_file_path')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TranscriptionSentence)
class TranscriptionSentenceAdmin(admin.ModelAdmin):
    list_display = ('session', 'sentence_number', 'text', 'created_at')
    list_filter = ('created_at', 'session')
    search_fields = ('text', 'session__transcription_id')
    readonly_fields = ('created_at',)
