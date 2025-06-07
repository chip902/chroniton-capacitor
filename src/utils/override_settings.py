"""
Override settings to bypass problematic environment variable parsing
"""
from typing import Dict, Any, List

# Create hardcoded settings that will be used directly in main.py without parsing from env
override_settings = {
    # Core application settings
    "APP_NAME": "Chroniton Capacitor",
    "DEBUG": True,
    "ENVIRONMENT": "development",
    "LOG_LEVEL": "DEBUG",
    
    # API settings
    "API_PREFIX": "/api",
    "API_HOST": "0.0.0.0",
    "API_PORT": 8008,
    
    # CORS settings - hardcoded to allow all origins
    "CORS_ORIGINS": ["*"],
    
    # Security settings
    "SECRET_KEY": "development_secret_key_not_for_production_abcdefghijklmnopqrstuvwxyz1234",
    "ALLOWED_HOSTS": ["*"],
    
    # Redis settings - from docker-compose
    "REDIS_HOST": "redis",
    "REDIS_PORT": 6379,
    "REDIS_DB": 0,
    "REDIS_PASSWORD": "",
    "REDIS_SSL": False
}

# Create a simple class to mimic the Settings object but using our hardcoded values
class OverrideSettings:
    def __init__(self, settings_dict: Dict[str, Any]):
        for key, value in settings_dict.items():
            setattr(self, key, value)
            
    def __getattr__(self, name):
        # Return None for attributes that don't exist instead of raising an error
        return None

# Create an instance that can be imported directly
settings = OverrideSettings(override_settings)
