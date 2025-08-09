#!/usr/bin/env python3
"""
Memory Curator Configuration
Hardware-flexible configuration for different deployment scenarios
"""
import os

class CuratorConfig:
    """Configuration for Memory Curator Agent"""
    
    # Service Configuration
    SERVICE_PORT = int(os.getenv('CURATOR_PORT', 8004))
    SERVICE_HOST = os.getenv('CURATOR_HOST', '0.0.0.0')
    
    # Model Configuration (Hardware Flexible)
    MODEL_SIZE = os.getenv('CURATOR_MODEL_SIZE', '1.5B')
    ENABLE_EMBEDDING = os.getenv('CURATOR_ENABLE_EMBEDDING', 'false').lower() == 'true'
    ENABLE_RERANK = os.getenv('CURATOR_ENABLE_RERANK', 'false').lower() == 'true'
    ENABLE_STATISTICAL = os.getenv('CURATOR_ENABLE_STATISTICAL', 'false').lower() == 'true'
    
    # Integration URLs
    WORKING_MEMORY_URL = os.getenv('WORKING_MEMORY_URL', 'http://localhost:8002')
    EPISODIC_MEMORY_URL = os.getenv('EPISODIC_MEMORY_URL', 'http://localhost:8003')
    
    # Performance Settings
    MAX_CONVERSATION_HISTORY = int(os.getenv('CURATOR_MAX_HISTORY', 50))
    MAX_ACTIVE_VALIDATIONS = int(os.getenv('CURATOR_MAX_VALIDATIONS', 100))
    VALIDATION_TIMEOUT_SECONDS = int(os.getenv('CURATOR_VALIDATION_TIMEOUT', 30))
    
    # Validation Thresholds
    CONFIDENCE_THRESHOLD = float(os.getenv('CURATOR_CONFIDENCE_THRESHOLD', 0.7))
    UNCERTAINTY_THRESHOLD = float(os.getenv('CURATOR_UNCERTAINTY_THRESHOLD', 0.5))
    CONTRADICTION_THRESHOLD = float(os.getenv('CURATOR_CONTRADICTION_THRESHOLD', 0.8))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('CURATOR_LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('CURATOR_LOG_FILE', '/tmp/curator.log')
    
    # Group Chat Configuration
    MAX_CHAT_PARTICIPANTS = int(os.getenv('CURATOR_MAX_PARTICIPANTS', 10))
    CHAT_SESSION_TIMEOUT_HOURS = int(os.getenv('CURATOR_CHAT_TIMEOUT', 24))
    AUTO_ARCHIVE_CHATS = os.getenv('CURATOR_AUTO_ARCHIVE', 'true').lower() == 'true'
    
    @classmethod
    def get_model_config(cls):
        """Get current model configuration summary"""
        return {
            'primary_model': cls.MODEL_SIZE,
            'optional_models': {
                'embedding': cls.ENABLE_EMBEDDING,
                'rerank': cls.ENABLE_RERANK,
                'statistical': cls.ENABLE_STATISTICAL
            },
            'performance_profile': cls._get_performance_profile()
        }
    
    @classmethod
    def _get_performance_profile(cls):
        """Determine performance profile based on enabled models"""
        enabled_count = sum([
            cls.ENABLE_EMBEDDING,
            cls.ENABLE_RERANK, 
            cls.ENABLE_STATISTICAL
        ])
        
        if enabled_count == 0:
            return 'minimal'
        elif enabled_count <= 2:
            return 'balanced'
        else:
            return 'full'
    
    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""
        issues = []
        
        # Check required settings
        if cls.SERVICE_PORT < 1024 or cls.SERVICE_PORT > 65535:
            issues.append("SERVICE_PORT must be between 1024 and 65535")
        
        if cls.CONFIDENCE_THRESHOLD < 0 or cls.CONFIDENCE_THRESHOLD > 1:
            issues.append("CONFIDENCE_THRESHOLD must be between 0 and 1")
        
        if cls.MAX_CONVERSATION_HISTORY < 10:
            issues.append("MAX_CONVERSATION_HISTORY should be at least 10")
        
        return issues

# Environment-specific configurations
class DevelopmentConfig(CuratorConfig):
    """Development environment configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(CuratorConfig):
    """Production environment configuration"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    # Enable all models for production if hardware supports
    ENABLE_EMBEDDING = True
    ENABLE_RERANK = True

class TestConfig(CuratorConfig):
    """Test environment configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    MAX_CONVERSATION_HISTORY = 10
    MAX_ACTIVE_VALIDATIONS = 5
    VALIDATION_TIMEOUT_SECONDS = 5

# Configuration factory
def get_config(env=None):
    """Get configuration based on environment"""
    env = env or os.getenv('CURATOR_ENV', 'development')
    
    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'test': TestConfig
    }
    
    return configs.get(env, DevelopmentConfig)