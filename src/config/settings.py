"""
Application settings management using Pydantic.
"""
from typing import Optional
from pydantic import BaseSettings, Field, PostgresDsn, validator


class Settings(BaseSettings):
    """
    Application settings model with environment variable support.
    
    Settings will be loaded from environment variables or .env file.
    """
    # Project info
    project_name: str = "Ticket Tracker"
    version: str = "1.0.0"
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Google Sheets
    google_sheet_id: str = Field(..., env="GOOGLE_SHEET_ID")
    google_credentials_file: str = Field(
        default="credentials.json", 
        env="GOOGLE_SHEETS_CREDENTIALS_FILE"
    )
    events_worksheet_name: str = Field(
        default="Events", 
        env="EVENTS_WORKSHEET_NAME"
    )
    
    # Database Settings
    db_host: str = Field(..., env="DB_HOST")
    db_port: int = Field(..., env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    db_schema: str = Field(default="public", env="DB_SCHEMA")
    db_uri: Optional[PostgresDsn] = None
    
    # Scraping Settings
    base_scrape_interval_hours: float = Field(
        default=12.0, 
        env="BASE_SCRAPE_INTERVAL_HOURS"
    )
    stubhub_api_base_url: str = Field(
        default="https://stubhub.com/api/events",
        env="STUBHUB_API_BASE_URL"
    )
    
    # Randomization Settings
    min_random_factor: float = Field(default=0.7, env="MIN_RANDOM_FACTOR")
    max_random_factor: float = Field(default=1.3, env="MAX_RANDOM_FACTOR")
    default_randomization_strategy: str = Field(
        default="poisson", 
        env="DEFAULT_RANDOMIZATION_STRATEGY"
    )
    normal_std_dev_factor: float = Field(
        default=0.2, 
        env="NORMAL_STD_DEV_FACTOR"
    )
    poisson_min_factor: float = Field(
        default=0.5, 
        env="POISSON_MIN_FACTOR"
    )
    poisson_max_factor: float = Field(
        default=2.0, 
        env="POISSON_MAX_FACTOR"
    )
    concurrency_limit: int = Field(
        default=5, 
        env="CONCURRENCY_LIMIT"
    )
    request_timeout_seconds: float = Field(
        default=30.0, 
        env="REQUEST_TIMEOUT_SECONDS"
    )
    
    @validator("db_uri", pre=True, always=True)
    def assemble_db_uri(cls, v, values):
        """Build the database URI from individual components."""
        if v:
            return v
            
        host = values.get("db_host")
        port = values.get("db_port")
        user = values.get("db_user")
        password = values.get("db_password")
        name = values.get("db_name")
        
        if all([host, str(port), user, password, name]):
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        
        return None
        
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
settings = Settings()
