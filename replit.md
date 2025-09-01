# Steam News Discord Bot

## Overview

This is a Discord bot that fetches Steam game news and translates it to French (or other supported languages). The bot allows users to search for games and retrieve the latest news articles, automatically translating them from English to the user's preferred language. It implements rate limiting, error handling, and integrates with both the Steam Web API and Google Translate services.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Architecture
- **Framework**: Built using discord.py library with command extension support
- **Command Pattern**: Uses Discord's command system with prefix-based commands (`!steam-news`)
- **Async Design**: Fully asynchronous implementation using Python's asyncio for non-blocking operations
- **Modular Structure**: Separated into distinct modules for bot logic, Steam API integration, translation services, and configuration

### Core Components
- **SteamNewsBot**: Main bot class that handles Discord interactions and command processing
- **SteamAPI**: Dedicated service for Steam Web API integration and game search functionality
- **Translator**: Translation service wrapper around Google Translate with rate limiting
- **Config**: Centralized configuration management for all bot settings

### Rate Limiting Strategy
- **User Cooldowns**: Per-user command rate limiting (30-second cooldown by default)
- **Translation Rate Limiting**: Built-in throttling for Google Translate API requests
- **API Timeouts**: Configurable timeout settings for external API calls

### Error Handling
- **Comprehensive Logging**: Multi-level logging with both file and console output
- **Graceful Degradation**: Proper error handling for API failures and network issues
- **Session Management**: Automatic aiohttp session creation and cleanup

### Configuration Management
- **Environment Variables**: Uses .env file for sensitive configuration like bot tokens
- **Centralized Config**: Single configuration class with all customizable parameters
- **Multi-language Support**: Configurable language mappings for translation services

## External Dependencies

### APIs and Services
- **Steam Web API**: For game search and news retrieval
  - Store API endpoint for game search functionality
  - News API for fetching game-specific news articles
- **Google Translate**: For translating news content between languages
  - Supports 10+ languages including English, French, Spanish, German, etc.

### Third-party Libraries
- **discord.py**: Discord API wrapper for bot functionality
- **aiohttp**: Async HTTP client for Steam API communication
- **googletrans**: Google Translate API client
- **python-dotenv**: Environment variable management

### Infrastructure Requirements
- **Discord Bot Token**: Required for Discord API authentication
- **Internet Connectivity**: For Steam API and Google Translate service access
- **Logging Storage**: File-based logging system for monitoring and debugging