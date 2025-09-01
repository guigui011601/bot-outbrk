"""
Translation Service
Handles text translation from English to French using Google Translate
"""

import asyncio
import logging
from typing import Optional
from googletrans import Translator as GoogleTranslator
import time
from config import Config

logger = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        self.translator = GoogleTranslator()
        self.last_request_time = 0
        self.request_count = 0
        self.reset_time = time.time()
    
    async def translate_text(self, text: str, source_lang: str = 'en', target_lang: str = 'fr') -> str:
        """
        Translate text from source language to target language
        Includes rate limiting to respect Google Translate API limits
        """
        if not text or not text.strip():
            return text
        
        try:
            # Apply rate limiting
            await self._apply_rate_limit()
            
            # Clean and prepare text
            clean_text = self._prepare_text_for_translation(text)
            
            if len(clean_text) > Config.MAX_TRANSLATION_LENGTH:
                clean_text = clean_text[:Config.MAX_TRANSLATION_LENGTH] + "..."
            
            # Perform translation in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._translate_sync, 
                clean_text, 
                source_lang, 
                target_lang
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            # Return original text if translation fails
            return f"[Translation failed] {text}"
    
    def _translate_sync(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Synchronous translation method (run in executor)
        """
        try:
            result = self.translator.translate(
                text, 
                src=source_lang, 
                dest=target_lang
            )
            return result.text
        except Exception as e:
            logger.error(f"Google Translate error: {e}")
            raise
    
    async def _apply_rate_limit(self):
        """
        Apply rate limiting to prevent hitting Google Translate limits
        """
        current_time = time.time()
        
        # Reset counter every minute
        if current_time - self.reset_time >= 60:
            self.request_count = 0
            self.reset_time = current_time
        
        # Check if we've hit the rate limit
        if self.request_count >= Config.TRANSLATION_RATE_LIMIT:
            wait_time = 60 - (current_time - self.reset_time)
            if wait_time > 0:
                logger.info(f"Translation rate limit reached. Waiting {wait_time:.1f} seconds.")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.reset_time = time.time()
        
        # Ensure minimum time between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < Config.MIN_TRANSLATION_INTERVAL:
            wait_time = Config.MIN_TRANSLATION_INTERVAL - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _prepare_text_for_translation(self, text: str) -> str:
        """
        Prepare text for translation by cleaning and formatting
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove or replace problematic characters
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = text.replace('\t', ' ')
        
        # Trim to reasonable length
        if len(text) > Config.MAX_TRANSLATION_LENGTH:
            # Try to cut at a sentence boundary
            sentences = text.split('. ')
            result = ""
            for sentence in sentences:
                if len(result + sentence + '. ') <= Config.MAX_TRANSLATION_LENGTH:
                    result += sentence + '. '
                else:
                    break
            
            if result:
                text = result.rstrip('. ')
            else:
                text = text[:Config.MAX_TRANSLATION_LENGTH]
        
        return text.strip()
    
    async def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of given text
        """
        if not text or not text.strip():
            return None
        
        try:
            await self._apply_rate_limit()
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.translator.detect(text[:100])  # Only check first 100 chars
            )
            
            return result.lang
            
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return None
    
    async def translate_batch(self, texts: list, source_lang: str = 'en', target_lang: str = 'fr') -> list:
        """
        Translate multiple texts with proper rate limiting
        """
        results = []
        
        for i, text in enumerate(texts):
            try:
                translated = await self.translate_text(text, source_lang, target_lang)
                results.append(translated)
                
                # Add delay between batch items
                if i < len(texts) - 1:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error translating batch item {i}: {e}")
                results.append(f"[Translation failed] {text}")
        
        return results
