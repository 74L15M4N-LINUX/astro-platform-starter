"""
Task Executor - Executes tasks from different categories
"""

import logging
from typing import Dict, Any, Optional
from core.ai_engine import Task

class TaskExecutor:
    """Executes tasks from different categories"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handlers: Dict[str, Any] = {}
        
        self.logger.info("Task Executor initialized")
    
    def register_handler(self, category: str, handler: Any):
        """Register a handler for a specific task category"""
        self.handlers[category] = handler
        self.logger.info(f"Registered handler for category: {category}")
    
    def execute_task(self, task: Task) -> str:
        """Execute a task and return the result"""
        try:
            self.logger.info(f"Executing task: {task.action} in category: {task.category}")
            
            # Validate task
            if not self._validate_task(task):
                return f"Invalid task: {task.action}"
            
            # Get handler for category
            handler = self.handlers.get(task.category)
            if not handler:
                return f"No handler registered for category: {task.category}"
            
            # Execute the task
            result = self._execute_with_handler(handler, task)
            
            self.logger.info(f"Task completed successfully: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Error executing task {task.action}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def _validate_task(self, task: Task) -> bool:
        """Validate task before execution"""
        if not task or not task.action or not task.category:
            return False
        
        # Check if category has a handler
        if task.category not in self.handlers:
            return False
        
        return True
    
    def _execute_with_handler(self, handler: Any, task: Task) -> str:
        """Execute task using the appropriate handler"""
        try:
            # Get the method name from the task action
            method_name = task.action
            
            # Check if handler has the method
            if hasattr(handler, method_name):
                method = getattr(handler, method_name)
                
                # Call the method with parameters
                if task.parameters:
                    result = method(**task.parameters)
                else:
                    result = method()
                
                return str(result) if result else "Task completed successfully"
            
            else:
                # Try to use a generic execute method
                if hasattr(handler, 'execute'):
                    result = handler.execute(task)
                    return str(result) if result else "Task completed successfully"
                
                # Fallback: try to call the handler directly
                if callable(handler):
                    result = handler(task)
                    return str(result) if result else "Task completed successfully"
                
                return f"Handler {type(handler).__name__} doesn't support action: {method_name}"
                
        except Exception as e:
            self.logger.error(f"Handler execution error: {e}")
            return f"Execution failed: {str(e)}"
    
    def get_available_tasks(self) -> Dict[str, list]:
        """Get list of available tasks for each category"""
        available_tasks = {}
        
        for category, handler in self.handlers.items():
            if hasattr(handler, 'get_available_actions'):
                available_tasks[category] = handler.get_available_actions()
            else:
                # Try to get methods from handler
                methods = [method for method in dir(handler) 
                          if not method.startswith('_') and callable(getattr(handler, method))]
                available_tasks[category] = methods
        
        return available_tasks
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task (for async tasks)"""
        # This could be expanded for tracking long-running tasks
        return {
            'task_id': task_id,
            'status': 'completed',  # Placeholder
            'result': None
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        # This could be expanded for canceling long-running tasks
        self.logger.info(f"Task cancellation requested for: {task_id}")
        return True
    
    def get_execution_history(self) -> list:
        """Get history of executed tasks"""
        # This could be expanded to track task execution history
        return []
    
    def clear_history(self):
        """Clear task execution history"""
        self.logger.info("Task execution history cleared")
    
    def get_handler_info(self, category: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific handler"""
        handler = self.handlers.get(category)
        if handler:
            return {
                'category': category,
                'handler_type': type(handler).__name__,
                'available_actions': self.get_available_tasks().get(category, []),
                'description': getattr(handler, '__doc__', 'No description available')
            }
        return None
    
    def test_handler(self, category: str) -> bool:
        """Test if a handler is working properly"""
        handler = self.handlers.get(category)
        if not handler:
            return False
        
        try:
            # Try to call a test method or check basic functionality
            if hasattr(handler, 'test'):
                return handler.test()
            elif hasattr(handler, 'is_available'):
                return handler.is_available()
            else:
                # Basic availability check
                return True
        except Exception as e:
            self.logger.error(f"Handler test failed for {category}: {e}")
            return False