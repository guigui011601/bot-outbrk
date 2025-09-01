"""
Configuration settings for the Steam News Discord Bot
Contains all configurable parameters and constants
"""

import os

class Config:
    """Configuration class for bot settings"""
    
    # Discord Bot Settings
    COMMAND_PREFIX = '!'
    
    # Rate Limiting Settings
    RATE_LIMIT_SECONDS = 30  # Cooldown between commands per user
    
    # Steam API Settings
    MAX_NEWS_ITEMS = 3  # Maximum number of news items to fetch per request
    API_TIMEOUT = 30  # Timeout for API requests in seconds
    
    # Translation Settings
    MAX_TRANSLATION_LENGTH = 1500  # Maximum characters to translate
    TRANSLATION_RATE_LIMIT = 20  # Maximum translations per minute
    MIN_TRANSLATION_INTERVAL = 1.0  # Minimum seconds between translation requests
    
    # Supported Languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'fr': 'French',
        'es': 'Spanish',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese'
    }
    
    # Default language settings
    DEFAULT_SOURCE_LANG = 'en'
    DEFAULT_TARGET_LANG = 'fr'
    
    # Bot Status and Presence
    DEFAULT_ACTIVITY = "Steam News | !help-steam"
    
    # Logging Settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = 'bot.log'
    
    # Error Messages
    ERROR_MESSAGES = {
        'no_game_found': "❌ Could not find a game with that name on Steam.",
        'no_news_found': "❌ No recent news found for this game.",
        'translation_failed': "❌ Translation service is currently unavailable.",
        'api_error': "❌ Steam API is currently unavailable. Please try again later.",
        'rate_limited': "⏰ Please wait before using this command again.",
        'invalid_command': "❌ Invalid command. Use `!help-steam` for available commands.",
        'missing_argument': "❌ Please provide a game name. Usage: `!steam-news [game_name]`"
    }
    
    # Success Messages
    SUCCESS_MESSAGES = {
        'search_start': "🔍 Searching for Steam news about '{game_name}'...",
        'fetch_start': "📰 Fetching latest news for '{game_title}'...",
        'translate_start': "🔄 Translating news article {current}/{total}...",
        'complete': "✅ News translation complete!"
    }
    
    # Embed Colors (Discord embed colors in hex)
    COLORS = {
        'primary': 0x1e3a8a,      # Blue
        'success': 0x16a34a,      # Green
        'warning': 0xeab308,      # Yellow
        'error': 0xdc2626,        # Red
        'info': 0x6b7280          # Gray
    }
    
    # Steam URLs
    STEAM_URLS = {
        'base_api': 'https://api.steampowered.com',
        'store_api': 'https://store.steampowered.com/api',
        'store_page': 'https://store.steampowered.com/app/{app_id}'
    }
    
    @classmethod
    def get_env_bool(cls, key: str, default: bool = False) -> bool:
        """Get boolean value from environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    @classmethod
    def get_env_int(cls, key: str, default: int) -> int:
        """Get integer value from environment variable"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    @classmethod
    def get_env_float(cls, key: str, default: float) -> float:
        """Get float value from environment variable"""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

# Environment-specific overrides
if os.getenv('ENVIRONMENT') == 'development':
    Config.LOG_LEVEL = 'DEBUG'
    Config.RATE_LIMIT_SECONDS = 10  # Shorter cooldown for development
    Config.MAX_NEWS_ITEMS = 2

elif os.getenv('ENVIRONMENT') == 'production':
    Config.LOG_LEVEL = 'WARNING'
    Config.RATE_LIMIT_SECONDS = 60  # Longer cooldown for production
    Config.TRANSLATION_RATE_LIMIT = 15  # More conservative rate limiting
