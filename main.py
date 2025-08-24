#!/usr/bin/env python3
"""
AI Voice Bot - Your Personal AI Assistant
Controls system, automates tasks, and responds to voice commands
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import threading
import time

# Import our modules
from core.voice_manager import VoiceManager
from core.ai_engine import AIEngine
from core.task_executor import TaskExecutor
from core.system_controller import SystemController
from core.web_automation import WebAutomation
from core.file_manager import FileManager
from gui.main_window import MainWindow
from utils.config import Config
from utils.logger import setup_logger

class AIVoiceBot:
    """Main AI Voice Bot class that orchestrates all functionality"""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger()
        
        # Initialize core components
        self.voice_manager = VoiceManager()
        self.ai_engine = AIEngine(self.config.get_openai_key())
        self.task_executor = TaskExecutor()
        self.system_controller = SystemController()
        self.web_automation = WebAutomation()
        self.file_manager = FileManager()
        
        # Bot state
        self.is_listening = False
        self.is_running = True
        self.current_task = None
        
        # Register task handlers
        self._register_task_handlers()
        
        self.logger.info("AI Voice Bot initialized successfully")
    
    def _register_task_handlers(self):
        """Register all available task handlers"""
        handlers = {
            'system': self.system_controller,
            'web': self.web_automation,
            'file': self.file_manager,
            'ai': self.ai_engine
        }
        
        for category, handler in handlers.items():
            self.task_executor.register_handler(category, handler)
    
    def start(self):
        """Start the AI Voice Bot"""
        try:
            self.logger.info("Starting AI Voice Bot...")
            
            # Start voice listening in background
            self.start_voice_listening()
            
            # Start GUI
            self.start_gui()
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            sys.exit(1)
    
    def start_voice_listening(self):
        """Start voice listening in background thread"""
        def listen_loop():
            while self.is_running:
                try:
                    if self.is_listening:
                        # Listen for voice input
                        audio_input = self.voice_manager.listen()
                        if audio_input:
                            self.process_voice_command(audio_input)
                    time.sleep(0.1)
                except Exception as e:
                    self.logger.error(f"Error in voice listening: {e}")
        
        self.voice_thread = threading.Thread(target=listen_loop, daemon=True)
        self.voice_thread.start()
        self.logger.info("Voice listening started")
    
    def process_voice_command(self, audio_input: str):
        """Process voice command through AI and execute tasks"""
        try:
            self.logger.info(f"Processing voice command: {audio_input}")
            
            # Get AI response and task
            response, task = self.ai_engine.process_command(audio_input)
            
            if task:
                # Execute the task
                result = self.task_executor.execute_task(task)
                self.logger.info(f"Task executed: {result}")
                
                # Provide voice feedback
                self.voice_manager.speak(f"Task completed: {result}")
            else:
                # Just speak the response
                self.voice_manager.speak(response)
                
        except Exception as e:
            self.logger.error(f"Error processing voice command: {e}")
            self.voice_manager.speak("Sorry, I encountered an error processing your command")
    
    def start_gui(self):
        """Start the GUI interface"""
        try:
            self.gui = MainWindow(self)
            self.gui.run()
        except Exception as e:
            self.logger.error(f"Failed to start GUI: {e}")
            # Fallback to command line mode
            self.start_cli_mode()
    
    def start_cli_mode(self):
        """Start command line interface mode"""
        self.logger.info("Starting CLI mode...")
        print("AI Voice Bot - CLI Mode")
        print("Type 'quit' to exit")
        
        while self.is_running:
            try:
                command = input("Bot> ").strip()
                if command.lower() == 'quit':
                    self.stop()
                    break
                elif command:
                    self.process_voice_command(command)
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                self.logger.error(f"CLI error: {e}")
    
    def stop(self):
        """Stop the AI Voice Bot"""
        self.logger.info("Stopping AI Voice Bot...")
        self.is_running = False
        self.is_listening = False
        
        if hasattr(self, 'voice_manager'):
            self.voice_manager.cleanup()
        
        self.logger.info("AI Voice Bot stopped")

def main():
    """Main entry point"""
    try:
        bot = AIVoiceBot()
        bot.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()