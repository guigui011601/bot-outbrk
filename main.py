"""
Discord Steam News Bot - Main Entry Point
Starts the Discord bot with proper error handling and logging
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from bot import SteamNewsBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to start the Discord bot"""
    try:
        # Get Discord bot token from environment variables
        discord_token = os.getenv('DISCORD_BOT_TOKEN')
        
        if not discord_token:
            logger.error("DISCORD_BOT_TOKEN not found in environment variables")
            return
        
        # Initialize and start the bot
        bot = SteamNewsBot()
        await bot.start(discord_token)
        
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrupted")
