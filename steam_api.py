"""
Steam API Integration
Handles communication with Steam Web API for game search and news retrieval
"""

import aiohttp
import logging
import asyncio
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class SteamAPI:
    def __init__(self):
        self.base_url = "https://api.steampowered.com"
        self.store_api_url = "https://store.steampowered.com/api"
        self.session = None
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)
            )
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_game(self, game_name: str) -> Optional[Dict]:
        """
        Search for a game by name using Steam API
        Returns the first matching game data
        """
        try:
            session = await self.get_session()
            
            # First, try to get app list (this might be cached)
            search_url = f"{self.store_api_url}/storesearch"
            params = {
                'term': game_name,
                'l': 'english',
                'cc': 'US'
            }
            
            async with session.get(search_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'items' in data and data['items']:
                        # Return the first match
                        first_match = data['items'][0]
                        return {
                            'appid': first_match['id'],
                            'name': first_match['name']
                        }
                else:
                    logger.warning(f"Steam search API returned status {response.status}")
            
            # Fallback: Try alternative search method
            return await self._fallback_game_search(game_name)
            
        except Exception as e:
            logger.error(f"Error searching for game '{game_name}': {e}")
            return None
    
    async def _fallback_game_search(self, game_name: str) -> Optional[Dict]:
        """
        Fallback search method using app list
        """
        try:
            session = await self.get_session()
            
            # Get app list (this is a large response, so we'll search through it)
            app_list_url = f"{self.base_url}/ISteamApps/GetAppList/v2/"
            
            async with session.get(app_list_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'applist' in data and 'apps' in data['applist']:
                        apps = data['applist']['apps']
                        
                        # Search for matching game name (case insensitive)
                        game_name_lower = game_name.lower()
                        
                        for app in apps:
                            if game_name_lower in app['name'].lower():
                                return {
                                    'appid': app['appid'],
                                    'name': app['name']
                                }
                
        except Exception as e:
            logger.error(f"Error in fallback game search: {e}")
        
        return None
    
    async def get_game_news(self, app_id: int, count: int = 3) -> List[Dict]:
        """
        Get news for a specific Steam app ID
        """
        try:
            session = await self.get_session()
            
            news_url = f"{self.base_url}/ISteamNews/GetNewsForApp/v2/"
            params = {
                'appid': app_id,
                'count': min(count, Config.MAX_NEWS_ITEMS),
                'maxlength': 1000,
                'format': 'json'
            }
            
            async with session.get(news_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'appnews' in data and 'newsitems' in data['appnews']:
                        news_items = data['appnews']['newsitems']
                        
                        # Process and clean news items
                        processed_news = []
                        for item in news_items:
                            processed_item = {
                                'title': self._clean_html(item.get('title', '')),
                                'contents': self._clean_html(item.get('contents', '')),
                                'url': item.get('url', ''),
                                'author': item.get('author', ''),
                                'date': item.get('date', 0)
                            }
                            processed_news.append(processed_item)
                        
                        return processed_news
                else:
                    logger.warning(f"Steam news API returned status {response.status} for app_id {app_id}")
                    
        except Exception as e:
            logger.error(f"Error fetching news for app_id {app_id}: {e}")
        
        return []
    
    def _clean_html(self, text: str) -> str:
        """
        Clean HTML tags and entities from text
        """
        if not text:
            return ""
        
        # Simple HTML tag removal (for basic cleaning)
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Replace common HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' '
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
