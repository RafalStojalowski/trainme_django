import os
from pathlib import Path
from django.conf import settings
import uuid
from datetime import datetime


class TranscriptionService:
    """Service for managing transcriptions with unique IDs and directory structure."""
    
    def __init__(self):
        self.transcription_root = settings.TRANSCRIPTION_DIR
        self.ensure_root_exists()
    
    def ensure_root_exists(self):
        """Ensure transcription root directory exists."""
        os.makedirs(self.transcription_root, exist_ok=True)
    
    def generate_transcription_id(self):
        """Generate a unique transcription ID."""
        # Using timestamp + uuid for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_suffix = str(uuid.uuid4())[:8]
        transcription_id = f"{timestamp}_{unique_suffix}"
        return transcription_id
    
    def create_transcription_directory(self, transcription_id):
        """Create a directory for specific transcription."""
        transcription_dir = self.transcription_root / transcription_id
        os.makedirs(transcription_dir, exist_ok=True)
        return transcription_dir
    
    def save_full_transcription(self, transcription_id, full_text):
        """Save the full transcription text to a file."""
        transcription_dir = self.create_transcription_directory(transcription_id)
        full_file_path = transcription_dir / f"{transcription_id}_full.txt"
        
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        return full_file_path
    
    def save_sentence_transcriptions(self, transcription_id, sentences):
        """
        Save individual sentences from the transcription.
        
        Args:
            transcription_id: Unique transcription identifier
            sentences: List of sentences (strings)
        """
        transcription_dir = self.create_transcription_directory(transcription_id)
        file_paths = []
        
        for idx, sentence in enumerate(sentences, 1):
            sentence_file_path = transcription_dir / f"{transcription_id}_sentence_{idx}.txt"
            
            with open(sentence_file_path, 'w', encoding='utf-8') as f:
                f.write(sentence)
            
            file_paths.append(sentence_file_path)
        
        return file_paths
    
    def split_transcription_into_sentences(self, text):
        """
        Split transcription text into sentences.
        Simple implementation - can be enhanced with NLP libraries.
        """
        # Replace common sentence endings with a marker
        import re
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Split by sentence terminators
        sentences = re.split(r'([.!?])', text)
        
        # Reconstruct sentences with their terminators
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip() + sentences[i + 1]
            if sentence.strip():
                result.append(sentence.strip())
        
        # Handle last sentence if no terminator
        if len(sentences) > 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result if result else [text]
    
    def get_transcription_path(self, transcription_id):
        """Get the path to a transcription directory."""
        return self.transcription_root / transcription_id
    
    def list_transcriptions(self):
        """List all available transcriptions."""
        if not self.transcription_root.exists():
            return []
        
        return [d.name for d in self.transcription_root.iterdir() if d.is_dir()]
