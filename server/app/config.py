"""
Configuration settings for the StubHub Proxy API Server
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Define basic settings class - without complex types that might cause parsing issues
class Settings:
    """Application settings"""
    # Server settings
    APP_NAME: str = "stubhub-proxy-api"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # API Auth
    API_KEY: str = os.getenv("API_KEY", "")
    
    # Browser automation settings
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
    MAX_BROWSER_INSTANCES: int = int(os.getenv("MAX_BROWSER_INSTANCES", "3"))
    BROWSER_TIMEOUT_SECONDS: int = int(os.getenv("BROWSER_TIMEOUT_SECONDS", "60"))
    
    # GoLogin settings
    GOLOGIN_API_KEY: str = os.getenv("GOLOGIN_API_KEY", "")
    # Handle profile IDs manually
    _GOLOGIN_PROFILE_IDS: str = os.getenv("GOLOGIN_PROFILE_IDS", "")
    
    # Caching settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    
    # Stealth settings
    MIN_PAGE_DELAY_MS: int = int(os.getenv("MIN_PAGE_DELAY_MS", "1000"))
    MAX_PAGE_DELAY_MS: int = int(os.getenv("MAX_PAGE_DELAY_MS", "5000"))
    ADD_RANDOM_ACTIONS: bool = os.getenv("ADD_RANDOM_ACTIONS", "True").lower() == "true"
    
    # StubHub settings
    STUBHUB_BASE_URL: str = "https://www.stubhub.com"
    
    # Rate limits
    MAX_REQUESTS_PER_SESSION: int = int(os.getenv("MAX_REQUESTS_PER_SESSION", "20"))
    MIN_REQUEST_INTERVAL_SECONDS: int = int(os.getenv("MIN_REQUEST_INTERVAL_SECONDS", "10"))
    
    @property
    def GOLOGIN_PROFILE_IDS(self) -> List[str]:
        """Convert string ID to list of profile IDs"""
        if not self._GOLOGIN_PROFILE_IDS:
            return []
        return self._GOLOGIN_PROFILE_IDS.split(",")


# Create settings instance
settings = Settings()

# Print config for debugging
if __name__ == "__main__":
    print(f"Loaded configuration for {settings.APP_NAME}")
    print(f"GOLOGIN_PROFILE_IDS: {settings.GOLOGIN_PROFILE_IDS}")
