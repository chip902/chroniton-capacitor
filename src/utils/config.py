from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Chroniton Capacitor"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # API settings
    API_PREFIX: str = "/api"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8008

    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://yourapp.com"
    ]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Remove any surrounding whitespace
            v = v.strip()
            
            # Handle wildcard as a special case
            if v == "*":
                return ["*"]  # Convert wildcard to a single-item list
                
            # Try to parse as JSON if it looks like JSON
            if (v.startswith('[') and v.endswith(']')) or (v.startswith('{') and v.endswith('}')):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict):  # Not expected, but handle just in case
                        return list(parsed.values())
                    return [str(parsed)]  # Convert to string and wrap in list as fallback
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to parse CORS_ORIGINS as JSON: {e}. Using as comma-separated string.")
            
            # Fallback to comma-separated format
            return [origin.strip() for origin in v.split(",") if origin.strip()]
            
        # If it's already a list or other non-string type, return as is
        return v

    # Security
    SECRET_KEY: str = Field("development_secret_key_not_for_production_abcdefghijklmnopqrstuvwxyz1234", min_length=32)
    ALLOWED_HOSTS: List[str] = ["*"]

    # Google Calendar settings
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""  # Will be auto-generated based on environment
    GOOGLE_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events.readonly"
    ]

    # Microsoft Graph settings
    MS_CLIENT_ID: str = ""
    MS_CLIENT_SECRET: str = ""
    MS_REDIRECT_URI: str = ""  # Will be auto-generated based on environment
    MS_TENANT_ID: str = "common"
    MS_AUTHORITY: str = "https://login.microsoftonline.com/common"
    MS_SCOPES: List[str] = [
        "Calendars.Read",
        "Calendars.Read.Shared", 
        "Calendars.ReadWrite",
        "Calendars.ReadWrite.Shared",
        "offline_access",
        "User.Read"
    ]

    # OAuth settings
    OAUTH_STATE_SECRET: str = Field("oauth_state_secret_change_in_production", min_length=16)
    OAUTH_SESSION_TIMEOUT_MINUTES: int = 30

    # Redis settings for caching
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_SSL: bool = False

    # JWT settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Storage settings
    STORAGE_PATH: str = "/app/storage"
    UPLOAD_FOLDER: str = "uploads"

    # Sync settings
    SYNC_INTERVAL_MINUTES: int = 5
    SYNC_ENABLED: bool = True

    # MCP settings
    MCP_SERVICE_NAME: str = "Calendar Integration Service"
    MCP_ENABLED: bool = True

    # TensorFlow settings
    TF_CPP_MIN_LOG_LEVEL: str = "2"  # 0=INFO, 1=WARNING, 2=ERROR, 3=FATAL

    # Application settings
    TIMEZONE: str = "UTC"

    @validator("STORAGE_PATH", pre=True)
    def ensure_storage_path_exists(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())

    @property
    def database_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def base_url(self) -> str:
        """Get the base URL for the application"""
        if self.is_production:
            # In production, this should be set explicitly or derived from environment
            return f"https://{self.API_HOST}:{self.API_PORT}"
        else:
            # In development, use localhost
            return f"http://localhost:{self.API_PORT}"

    @property
    def google_redirect_uri(self) -> str:
        """Get the Google OAuth redirect URI"""
        if self.GOOGLE_REDIRECT_URI:
            return self.GOOGLE_REDIRECT_URI
        return f"{self.base_url}/api/auth/google/callback"

    @property
    def microsoft_redirect_uri(self) -> str:
        """Get the Microsoft OAuth redirect URI"""
        if self.MS_REDIRECT_URI:
            return self.MS_REDIRECT_URI
        return f"{self.base_url}/api/auth/microsoft/callback"

    @property
    def google_oauth_configured(self) -> bool:
        """Check if Google OAuth is properly configured"""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def microsoft_oauth_configured(self) -> bool:
        """Check if Microsoft OAuth is properly configured"""
        return bool(self.MS_CLIENT_ID and self.MS_CLIENT_SECRET)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file


# Create settings instance
settings = Settings()
