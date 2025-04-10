from enum import Enum
import logging
from datetime import datetime
import traceback
from typing import Optional, Dict, Any

class ErrorSection(Enum):
    AUTHENTICATION = "AUTH"
    MODEL_LOADING = "MODEL"
    MEMORY_MANAGEMENT = "MEM"
    REQUEST_PROCESSING = "REQ"
    RESPONSE_GENERATION = "RESP"
    RESOURCE_CLEANUP = "CLEAN"
    SYSTEM_HEALTH = "HEALTH"

class SectionLogger:
    def __init__(self, section: ErrorSection):
        self.section = section
        self.logger = logging.getLogger(f"{section.value}_logger")
        self.logger.setLevel(logging.INFO)
        
        # Add file handler for section-specific logging
        file_handler = logging.FileHandler(f'logs/{section.value.lower()}_errors.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(file_handler)
    
    def log_error(self, error_code: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an error with section-specific context"""
        error_id = f"{self.section.value}-{error_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        error_context = {
            'error_id': error_id,
            'section': self.section.value,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context or {},
            'traceback': traceback.format_exc()
        }
        
        self.logger.error(f"{error_id}: {message}")
        if context:
            self.logger.error(f"Context: {context}")
        self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return error_id
    
    def log_warning(self, warning_code: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning with section-specific context"""
        warning_id = f"{self.section.value}-{warning_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        warning_context = {
            'warning_id': warning_id,
            'section': self.section.value,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context or {}
        }
        
        self.logger.warning(f"{warning_id}: {message}")
        if context:
            self.logger.warning(f"Context: {context}")
        
        return warning_id
    
    def log_info(self, info_code: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an info message with section-specific context"""
        info_id = f"{self.section.value}-{info_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        info_context = {
            'info_id': info_id,
            'section': self.section.value,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context or {}
        }
        
        self.logger.info(f"{info_id}: {message}")
        if context:
            self.logger.info(f"Context: {context}")
        
        return info_id

# Create section-specific loggers
auth_logger = SectionLogger(ErrorSection.AUTHENTICATION)
model_logger = SectionLogger(ErrorSection.MODEL_LOADING)
memory_logger = SectionLogger(ErrorSection.MEMORY_MANAGEMENT)
request_logger = SectionLogger(ErrorSection.REQUEST_PROCESSING)
response_logger = SectionLogger(ErrorSection.RESPONSE_GENERATION)
cleanup_logger = SectionLogger(ErrorSection.RESOURCE_CLEANUP)
health_logger = SectionLogger(ErrorSection.SYSTEM_HEALTH)

# Error code constants
class ErrorCodes:
    # Authentication errors
    AUTH_INVALID_CREDENTIALS = "AUTH-001"
    AUTH_MISSING_HEADERS = "AUTH-002"
    AUTH_INVALID_FORMAT = "AUTH-003"
    
    # Model loading errors
    MODEL_LOAD_FAILED = "MODEL-001"
    MODEL_INIT_FAILED = "MODEL-002"
    MODEL_MEMORY_ERROR = "MODEL-003"
    
    # Memory management errors
    MEM_CRITICAL_USAGE = "MEM-001"
    MEM_CLEANUP_FAILED = "MEM-002"
    MEM_ALLOCATION_ERROR = "MEM-003"
    
    # Request processing errors
    REQ_INVALID_FORMAT = "REQ-001"
    REQ_PROCESSING_ERROR = "REQ-002"
    REQ_TIMEOUT = "REQ-003"
    
    # Response generation errors
    RESP_GENERATION_ERROR = "RESP-001"
    RESP_STREAM_ERROR = "RESP-002"
    RESP_FORMAT_ERROR = "RESP-003"
    
    # Resource cleanup errors
    CLEAN_MODEL_FAILED = "CLEAN-001"
    CLEAN_MEMORY_FAILED = "CLEAN-002"
    CLEAN_RESOURCE_FAILED = "CLEAN-003"
    
    # System health errors
    HEALTH_CRITICAL = "HEALTH-001"
    HEALTH_MONITOR_ERROR = "HEALTH-002"
    HEALTH_RECOVERY_FAILED = "HEALTH-003"
    
    # Model Memory Codes (MODEL-014 to MODEL-018)
    MODEL_MEM_INIT = "MODEL-014"  # Initial memory state
    MODEL_MEM_PREP = "MODEL-015"  # Memory after input preparation
    MODEL_MEM_GEN = "MODEL-016"   # Memory after generation
    MODEL_MEM_FINAL = "MODEL-017" # Final memory state
    MODEL_MEM_PEAK = "MODEL-018"  # Peak memory usage 