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
                                'date': item.get('date', 0),
                                'feed_label': item.get('feedlabel', ''),
                                'feed_name': item.get('feedname', ''),
                                'feed_type': item.get('feed_type', 0),
                                'appid': item.get('appid', app_id)
                            }
                            
                            # Try to extract image from content or fetch from URL
                            image_url = self._extract_image_from_content(item.get('contents', ''))
                            
                            # If no image in text content, try to fetch from the full Steam page
                            if not image_url and item.get('url'):
                                image_url = await self._get_image_from_steam_url(item['url'])
                            
                            if image_url:
                                processed_item['image'] = image_url
                            
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
    
    def _extract_image_from_content(self, content: str) -> Optional[str]:
        """
        Extract image URL from news content
        """
        if not content:
            return None
            
        import re
        
        # Look for Steam clan/community images (most common in announcements)
        clan_pattern = r'https://clan\.fastly\.steamstatic\.com/images/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)'
        clan_match = re.search(clan_pattern, content, re.IGNORECASE)
        if clan_match:
            return clan_match.group(0)
        
        # Look for Steam CDN images 
        steam_cdn_pattern = r'https://cdn\.akamai\.steamstatic\.com/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)'
        steam_match = re.search(steam_cdn_pattern, content, re.IGNORECASE)
        if steam_match:
            return steam_match.group(0)
        
        # Look for steamstatic images
        steamstatic_pattern = r'https://[^"\s<>]*steamstatic[^"\s<>]*\.(?:jpg|jpeg|png|gif|webp)'
        steamstatic_match = re.search(steamstatic_pattern, content, re.IGNORECASE)
        if steamstatic_match:
            return steamstatic_match.group(0)
        
        # Look for general image URLs in img tags
        img_tag_pattern = r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp))["\'][^>]*>'
        img_match = re.search(img_tag_pattern, content, re.IGNORECASE)
        if img_match:
            img_url = img_match.group(1)
            # Only return if it's a valid HTTP(S) URL
            if img_url.startswith(('http://', 'https://')):
                return img_url
        
        # Look for direct image URLs in content
        direct_img_pattern = r'https?://[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)'
        direct_match = re.search(direct_img_pattern, content, re.IGNORECASE)
        if direct_match:
            return direct_match.group(0)
        
        return None
    
    async def _get_image_from_steam_url(self, url: str) -> Optional[str]:
        """
        Fetch images from Steam announcement page (prioritize content images over header)
        """
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Look for images in the full HTML content
                    import re
                    
                    # First check if this is a Steam Community URL, try to find the actual content
                    if 'steamcommunity.com' in url:
                        # Look for announcement content section
                        content_section = content
                        for section_id in ['news_content', 'bodytext', 'announcement_content', 'content']:
                            if f'id="{section_id}"' in content:
                                try:
                                    start_marker = f'id="{section_id}"'
                                    start_idx = content.find(start_marker)
                                    if start_idx != -1:
                                        # Find the opening tag
                                        tag_start = content.rfind('<', 0, start_idx + len(start_marker))
                                        if tag_start != -1:
                                            tag_name = content[tag_start+1:content.find(' ', tag_start)].split('>')[0]
                                            # Find closing tag
                                            end_marker = f'</{tag_name}>'
                                            end_idx = content.find(end_marker, start_idx)
                                            if end_idx != -1:
                                                content_section = content[start_idx:end_idx]
                                                break
                                except:
                                    continue
                    else:
                        content_section = content
                    
                    # Find ALL Steam clan images in the content section
                    clan_pattern = r'https://clan\.fastly\.steamstatic\.com/images/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)'
                    clan_matches = re.findall(clan_pattern, content_section, re.IGNORECASE)
                    
                    # Also look for steamcdn and other Steam image patterns
                    other_patterns = [
                        r'https://steamcdn-a\.akamaihd\.net/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)',
                        r'https://cdn\.akamai\.steamstatic\.com/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)',
                        r'https://shared\.fastly\.steamstatic\.com/[^"\s<>]+\.(?:jpg|jpeg|png|gif|webp)'
                    ]
                    
                    all_images = clan_matches.copy()
                    for pattern in other_patterns:
                        matches = re.findall(pattern, content_section, re.IGNORECASE)
                        all_images.extend(matches)
                    
                    if all_images:
                        # Remove duplicates while preserving order
                        unique_images = list(dict.fromkeys(all_images))
                        
                        # Filter out small images (likely icons) and header images
                        content_images = []
                        
                        for img_url in unique_images:
                            # Skip likely icon/header images
                            if any(skip_term in img_url.lower() for skip_term in ['icon', 'avatar', 'thumb', 'small', 'capsule_184x69']):
                                continue
                            
                            # Skip header images (they usually have specific pattern)
                            if 'header' in img_url.lower():
                                continue
                                
                            content_images.append(img_url)
                        
                        # Return the first content image (not header/icon)
                        if content_images:
                            return content_images[0]
                        
                        # If no content images, return first image as fallback
                        return unique_images[0]
                        
        except Exception as e:
            logger.debug(f"Could not fetch image from Steam URL {url}: {e}")
        
        return None
    
    async def get_game_header_image(self, app_id: int) -> Optional[str]:
        """
        Get the header image for a game from Steam store
        """
        try:
            # Steam store header image URL format
            header_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
            
            session = await self.get_session()
            async with session.head(header_url) as response:
                if response.status == 200:
                    return header_url
        except Exception as e:
            logger.debug(f"Could not get header image for app {app_id}: {e}")
        
        return None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
