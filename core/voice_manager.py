"""
Voice Manager - Handles speech recognition and text-to-speech
"""

import speech_recognition as sr
import pyttsx3
import threading
import queue
import time
from typing import Optional, Callable
import logging

class VoiceManager:
    """Manages voice input/output operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        
        # Initialize text-to-speech
        self.tts_engine = pyttsx3.init()
        self._setup_tts()
        
        # Audio queue for processing
        self.audio_queue = queue.Queue()
        self.is_listening = False
        
        # Callback for when speech is detected
        self.on_speech_detected: Optional[Callable] = None
        
        self.logger.info("Voice Manager initialized")
    
    def _setup_tts(self):
        """Setup text-to-speech engine"""
        try:
            # Get available voices
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Try to set a good default voice
                for voice in voices:
                    if 'en' in voice.id.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
            
            # Set speech rate and volume
            self.tts_engine.setProperty('rate', 180)  # Words per minute
            self.tts_engine.setProperty('volume', 0.9)  # Volume level
            
        except Exception as e:
            self.logger.error(f"Failed to setup TTS: {e}")
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen for voice input and return transcribed text"""
        try:
            with sr.Microphone() as source:
                self.logger.info("Listening for voice input...")
                
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Listen for audio
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                
                # Transcribe audio to text
                text = self.recognizer.recognize_google(audio)
                
                if text:
                    self.logger.info(f"Recognized: {text}")
                    return text.lower().strip()
                
        except sr.WaitTimeoutError:
            self.logger.debug("No speech detected within timeout")
        except sr.UnknownValueError:
            self.logger.debug("Speech was unintelligible")
        except sr.RequestError as e:
            self.logger.error(f"Speech recognition service error: {e}")
        except Exception as e:
            self.logger.error(f"Error in voice recognition: {e}")
        
        return None
    
    def speak(self, text: str, async_mode: bool = True):
        """Convert text to speech"""
        try:
            if async_mode:
                # Run TTS in background thread
                thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
                thread.start()
            else:
                self._speak_sync(text)
                
        except Exception as e:
            self.logger.error(f"Error in text-to-speech: {e}")
    
    def _speak_sync(self, text: str):
        """Synchronous text-to-speech"""
        try:
            self.logger.info(f"Speaking: {text}")
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            self.logger.error(f"Error in synchronous TTS: {e}")
    
    def start_continuous_listening(self, callback: Callable[[str], None]):
        """Start continuous listening mode"""
        self.is_listening = True
        self.on_speech_detected = callback
        
        def listen_loop():
            while self.is_listening:
                try:
                    text = self.listen(timeout=1)
                    if text and self.on_speech_detected:
                        self.on_speech_detected(text)
                    time.sleep(0.1)
                except Exception as e:
                    self.logger.error(f"Error in continuous listening: {e}")
                    time.sleep(1)
        
        self.listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self.listen_thread.start()
        self.logger.info("Continuous listening started")
    
    def stop_continuous_listening(self):
        """Stop continuous listening mode"""
        self.is_listening = False
        self.logger.info("Continuous listening stopped")
    
    def set_voice_properties(self, rate: int = None, volume: float = None, voice_id: str = None):
        """Set TTS voice properties"""
        try:
            if rate is not None:
                self.tts_engine.setProperty('rate', rate)
            if volume is not None:
                self.tts_engine.setProperty('volume', volume)
            if voice_id is not None:
                self.tts_engine.setProperty('voice', voice_id)
                
            self.logger.info("Voice properties updated")
        except Exception as e:
            self.logger.error(f"Failed to update voice properties: {e}")
    
    def get_available_voices(self) -> list:
        """Get list of available TTS voices"""
        try:
            voices = self.tts_engine.getProperty('voices')
            return [{'id': voice.id, 'name': voice.name, 'languages': voice.languages} for voice in voices]
        except Exception as e:
            self.logger.error(f"Failed to get available voices: {e}")
            return []
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.stop_continuous_listening()
            if hasattr(self, 'tts_engine'):
                self.tts_engine.stop()
            self.logger.info("Voice Manager cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")