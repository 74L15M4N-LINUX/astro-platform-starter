"""
AI Engine - Processes voice commands and generates intelligent responses
"""

import openai
import json
import logging
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class Task:
    """Represents a task to be executed"""
    action: str
    category: str
    parameters: Dict[str, Any]
    description: str

class AIEngine:
    """AI engine for processing voice commands and generating responses"""
    
    def __init__(self, api_key: str):
        self.logger = logging.getLogger(__name__)
        
        if api_key:
            openai.api_key = api_key
            self.client = openai.OpenAI(api_key=api_key)
            self.has_api_key = True
        else:
            self.has_api_key = False
            self.logger.warning("No OpenAI API key provided - using fallback responses")
        
        # Command patterns and responses
        self.command_patterns = {
            'system_control': [
                'shutdown', 'restart', 'sleep', 'lock', 'volume', 'brightness',
                'open app', 'close app', 'minimize', 'maximize'
            ],
            'file_operations': [
                'create file', 'delete file', 'move file', 'copy file',
                'search files', 'organize files', 'backup'
            ],
            'web_automation': [
                'open website', 'search web', 'fill form', 'click button',
                'scroll', 'take screenshot', 'download'
            ],
            'information': [
                'what time', 'weather', 'news', 'search', 'calculate',
                'define', 'translate'
            ]
        }
        
        self.logger.info("AI Engine initialized")
    
    def process_command(self, voice_input: str) -> Tuple[str, Optional[Task]]:
        """
        Process voice command and return response + task
        Returns: (response_text, task_object)
        """
        try:
            self.logger.info(f"Processing command: {voice_input}")
            
            if not self.has_api_key:
                return self._fallback_response(voice_input)
            
            # Use OpenAI to process the command
            response, task = self._process_with_openai(voice_input)
            
            if task:
                self.logger.info(f"Generated task: {task.action}")
                return response, task
            else:
                self.logger.info("No task generated, returning response only")
                return response, None
                
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return "I'm sorry, I encountered an error processing your command.", None
    
    def _process_with_openai(self, voice_input: str) -> Tuple[str, Optional[Task]]:
        """Process command using OpenAI API"""
        try:
            # Create system prompt
            system_prompt = """You are an AI assistant that can control a computer system. 
            Analyze the user's voice command and determine if it requires an action.
            
            If an action is needed, respond with a JSON task object in this format:
            {
                "action": "action_name",
                "category": "system|file|web|ai",
                "parameters": {"param1": "value1"},
                "description": "What this task will do"
            }
            
            Available actions:
            - system: shutdown, restart, sleep, lock, volume_up, volume_down, brightness_up, brightness_down, open_app, close_app
            - file: create_file, delete_file, move_file, copy_file, search_files, organize_files
            - web: open_website, search_web, fill_form, click_element, scroll_page, screenshot
            - ai: chat, search, calculate, translate
            
            If no action is needed, just provide a helpful response without JSON.
            """
            
            # Create user message
            user_message = f"User command: {voice_input}\n\nRespond with either a helpful message or a JSON task object."
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON task
            task = self._extract_task_from_response(response_text)
            
            if task:
                return f"I'll {task.description.lower()}.", task
            else:
                return response_text, None
                
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return self._fallback_response(voice_input)
    
    def _extract_task_from_response(self, response: str) -> Optional[Task]:
        """Extract task JSON from OpenAI response"""
        try:
            # Look for JSON in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
                task_data = json.loads(json_str)
                
                # Validate task data
                required_fields = ['action', 'category', 'parameters', 'description']
                if all(field in task_data for field in required_fields):
                    return Task(
                        action=task_data['action'],
                        category=task_data['category'],
                        parameters=task_data.get('parameters', {}),
                        description=task_data['description']
                    )
            
            return None
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse task JSON: {e}")
            return None
    
    def _fallback_response(self, voice_input: str) -> str:
        """Provide fallback response when OpenAI is not available"""
        input_lower = voice_input.lower()
        
        # Simple pattern matching for common commands
        if any(word in input_lower for word in ['shutdown', 'turn off', 'power off']):
            return "I can help you shut down the computer. Please use the GUI or type 'shutdown' in the command line."
        
        elif any(word in input_lower for word in ['restart', 'reboot']):
            return "I can help you restart the computer. Please use the GUI or type 'restart' in the command line."
        
        elif any(word in input_lower for word in ['volume', 'sound']):
            return "I can help you control the volume. Please use the volume controls or let me know if you want me to adjust it."
        
        elif any(word in input_lower for word in ['time', 'what time']):
            from datetime import datetime
            current_time = datetime.now().strftime("%I:%M %p")
            return f"The current time is {current_time}."
        
        elif any(word in input_lower for word in ['weather', 'temperature']):
            return "I can't check the weather right now, but you can ask me to open a weather website for you."
        
        elif any(word in input_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm your AI assistant. I can help you control your computer, manage files, and automate tasks. What would you like me to do?"
        
        else:
            return f"I heard you say '{voice_input}'. I'm here to help! You can ask me to control your computer, manage files, or help with various tasks."
    
    def get_command_suggestions(self) -> Dict[str, list]:
        """Get suggested commands for each category"""
        return self.command_patterns
    
    def validate_task(self, task: Task) -> bool:
        """Validate if a task is properly formatted"""
        try:
            # Check required fields
            if not all([task.action, task.category, task.description]):
                return False
            
            # Validate category
            valid_categories = ['system', 'file', 'web', 'ai']
            if task.category not in valid_categories:
                return False
            
            # Validate action format
            if not isinstance(task.action, str) or len(task.action) < 2:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Task validation error: {e}")
            return False
    
    def get_help_text(self) -> str:
        """Get help text explaining available commands"""
        help_text = """
        I can help you with various tasks:

        System Control:
        - "Shutdown the computer"
        - "Restart the system"
        - "Lock the screen"
        - "Open [application name]"
        - "Adjust volume up/down"
        - "Change screen brightness"

        File Operations:
        - "Create a new file"
        - "Delete [filename]"
        - "Move [filename] to [folder]"
        - "Search for files"
        - "Organize my documents"

        Web Automation:
        - "Open [website]"
        - "Search for [topic]"
        - "Fill out a form"
        - "Take a screenshot"

        Information & AI:
        - "What time is it?"
        - "Calculate [expression]"
        - "Define [word]"
        - "Translate [text] to [language]"

        Just speak naturally and I'll understand what you need!
        """
        return help_text.strip()