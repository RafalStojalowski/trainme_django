from django.contrib import admin
from .models import (
    TranscriptionSession, TranscriptionSentence,
    Conversation, Message, AudioRecord,
)


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


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'ended_at', 'message_count')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Wiadomości'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'message_number', 'from_user', 'text_preview', 'created_at')
    list_filter = ('from_user', 'created_at')
    search_fields = ('text',)
    readonly_fields = ('created_at',)

    def text_preview(self, obj):
        return obj.text[:80]
    text_preview.short_description = 'Tekst'


@admin.register(AudioRecord)
class AudioRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'text_message', 'wav_path', 'created_at')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
