import os
import base64
import wave
from pathlib import Path
from django.conf import settings
import numpy as np


class AudioService:
    """Service for handling audio recording and processing in WAV format."""
    
    def __init__(self):
        self.audio_dir = settings.AUDIO_DIR
        self.ensure_audio_dir_exists()
    
    def ensure_audio_dir_exists(self):
        """Ensure audio directory exists."""
        os.makedirs(self.audio_dir, exist_ok=True)
    
    def save_audio_from_base64(self, transcription_id, audio_base64_string):
        """
        Save audio from base64 encoded string to WAV file.
        
        Args:
            transcription_id: Unique transcription identifier
            audio_base64_string: Base64 encoded audio data from WebAudio API
            
        Returns:
            Path to saved WAV file
        """
        try:
            # Decode base64 to binary
            audio_binary = base64.b64decode(audio_base64_string)
            
            # Create file path
            audio_file_path = self.audio_dir / f"{transcription_id}.wav"
            
            # Write binary data to WAV file
            with open(audio_file_path, 'wb') as f:
                f.write(audio_binary)
            
            return str(audio_file_path)
        except Exception as e:
            raise ValueError(f"Failed to save audio file: {str(e)}")
    
    def save_audio_from_blob(self, transcription_id, audio_data, sample_rate=16000, channels=1):
        """
        Save audio data to WAV file.
        
        Args:
            transcription_id: Unique transcription identifier
            audio_data: Audio samples as numpy array or list
            sample_rate: Sample rate in Hz (default 16000)
            channels: Number of audio channels (default 1 - mono)
            
        Returns:
            Path to saved WAV file
        """
        try:
            if isinstance(audio_data, list):
                audio_data = np.array(audio_data, dtype=np.float32)
            
            # Ensure data is in correct format for WAV
            if audio_data.dtype == np.float32:
                # Convert float32 to int16
                audio_data = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)
            
            # Create file path
            audio_file_path = self.audio_dir / f"{transcription_id}.wav"
            
            # Write WAV file
            with wave.open(audio_file_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 2 bytes for int16
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            return str(audio_file_path)
        except Exception as e:
            raise ValueError(f"Failed to create WAV file: {str(e)}")
    
    def get_audio_path(self, transcription_id):
        """Get the path to an audio file."""
        return self.audio_dir / f"{transcription_id}.wav"
    
    def audio_exists(self, transcription_id):
        """Check if audio file exists for given transcription ID."""
        audio_path = self.get_audio_path(transcription_id)
        return audio_path.exists()
    
    def list_audio_files(self):
        """List all saved audio files."""
        if not self.audio_dir.exists():
            return []
        
        return [f.name for f in self.audio_dir.iterdir() if f.suffix == '.wav']
    
    def delete_audio_file(self, transcription_id):
        """Delete audio file for given transcription ID."""
        audio_path = self.get_audio_path(transcription_id)
        if audio_path.exists():
            audio_path.unlink()
            return True
        return False
