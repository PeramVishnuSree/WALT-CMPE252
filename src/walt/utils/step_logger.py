import logging
import time
from typing import Optional, Any

class StepLogger:
    """
    Centralized logger for tool steps.
    Logs step execution details including timing, status, and context.
    """
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.logger = logging.getLogger("walt.step_logger")
        
        # Ensure we have a handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - [STEP] - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_step_start(self, step_index: int, step_type: str, description: Optional[str] = None):
        """Log the start of a step execution."""
        if not self.enabled:
            return
            
        msg = f"START Step {step_index+1}: Type={step_type}"
        if description:
            msg += f", Desc='{description}'"
        self.logger.info(msg)

    def log_step_end(
        self, 
        step_index: int, 
        step_type: str, 
        success: bool, 
        duration: float, 
        current_url: str,
        error: Optional[str] = None
    ):
        """Log the completion of a step execution."""
        if not self.enabled:
            return

        status = "SUCCESS" if success else "FAILURE"
        msg = (
            f"END Step {step_index+1}: Type={step_type}, Status={status}, "
            f"Time={duration:.4f}s, URL='{current_url}'"
        )
        
        if error:
            msg += f", Error='{error}'"
            
        self.logger.info(msg)

# Global instance or factory can be used if needed, 
# but typically it will be instantiated in the executor with config.

