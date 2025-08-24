"""
System Controller - Handles system-level operations
"""

import subprocess
import psutil
import pyautogui
import logging
import os
from typing import Optional

class SystemController:
    """Controls system operations like shutdown, restart, volume, etc."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        pyautogui.FAILSAFE = True
        self.logger.info("System Controller initialized")
    
    def shutdown(self) -> str:
        """Shutdown the system"""
        try:
            subprocess.run(['shutdown', '-h', 'now'], check=True)
            return "System shutdown initiated"
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            return f"Shutdown failed: {e}"
    
    def restart(self) -> str:
        """Restart the system"""
        try:
            subprocess.run(['reboot'], check=True)
            return "System restart initiated"
        except Exception as e:
            self.logger.error(f"Restart failed: {e}")
            return f"Restart failed: {e}"
    
    def lock_screen(self) -> str:
        """Lock the screen"""
        try:
            subprocess.run(['gnome-screensaver-command', '--lock'], check=True)
            return "Screen locked"
        except Exception as e:
            self.logger.error(f"Screen lock failed: {e}")
            return f"Screen lock failed: {e}"
    
    def volume_up(self) -> str:
        """Increase system volume"""
        try:
            subprocess.run(['amixer', 'set', 'Master', '5%+'], check=True)
            return "Volume increased"
        except Exception as e:
            self.logger.error(f"Volume up failed: {e}")
            return f"Volume up failed: {e}"
    
    def volume_down(self) -> str:
        """Decrease system volume"""
        try:
            subprocess.run(['amixer', 'set', 'Master', '5%-'], check=True)
            return "Volume decreased"
        except Exception as e:
            self.logger.error(f"Volume down failed: {e}")
            return f"Volume down failed: {e}"
    
    def open_app(self, app_name: str) -> str:
        """Open an application"""
        try:
            subprocess.Popen([app_name])
            return f"Opened {app_name}"
        except Exception as e:
            self.logger.error(f"Failed to open {app_name}: {e}")
            return f"Failed to open {app_name}: {e}"
    
    def close_app(self, app_name: str) -> str:
        """Close an application"""
        try:
            subprocess.run(['pkill', app_name], check=True)
            return f"Closed {app_name}"
        except Exception as e:
            self.logger.error(f"Failed to close {app_name}: {e}")
            return f"Failed to close {app_name}: {e}"
    
    def get_system_info(self) -> dict:
        """Get system information"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'battery_percent': psutil.sensors_battery().percent if psutil.sensors_battery() else None
            }
        except Exception as e:
            self.logger.error(f"Failed to get system info: {e}")
            return {}
    
    def take_screenshot(self, filename: str = "screenshot.png") -> str:
        """Take a screenshot"""
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return f"Screenshot saved as {filename}"
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return f"Screenshot failed: {e}"
    
    def get_available_actions(self) -> list:
        """Get list of available actions"""
        return [
            'shutdown', 'restart', 'lock_screen', 'volume_up', 'volume_down',
            'open_app', 'close_app', 'get_system_info', 'take_screenshot'
        ]