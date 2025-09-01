"""
Discord Bot Implementation
Handles Discord interactions and command processing
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from datetime import datetime, timedelta
from steam_api import SteamAPI
from translator import Translator
from config import Config

logger = logging.getLogger(__name__)

class SteamNewsBot(commands.Bot):
    def __init__(self):
        # Configure bot intents - using minimal intents to avoid privileged intent requirements
        intents = discord.Intents.default()
        intents.message_content = False  # Disable to avoid privileged intent requirement
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # Disable default help since we'll use slash commands
        )
        
        # Initialize API clients
        self.steam_api = SteamAPI()
        self.translator = Translator()
        
        # Rate limiting storage
        self.user_cooldowns = {}
        
        # Add commands
        self.add_commands()
        self.add_slash_commands()
    
    def add_commands(self):
        """Add bot commands"""
        
        @self.command(name='steam-news', help='Get Steam game news in French. Usage: !steam-news [game_name]')
        async def steam_news(ctx, *, game_name: str):
            """Command to fetch and translate Steam game news"""
            try:
                # Check if game name is provided
                if not game_name:
                    await ctx.send("❌ Please provide a game name. Usage: `!steam-news [game_name]`")
                    return
                
                # Check rate limiting
                if not self.check_rate_limit(ctx.author.id):
                    cooldown_time = self.get_cooldown_remaining(ctx.author.id)
                    await ctx.send(f"⏰ Please wait {cooldown_time} seconds before using this command again.")
                    return
                
                # Send typing indicator
                async with ctx.typing():
                    # Search for the game
                    await ctx.send(f"🔍 Searching for Steam news about '{game_name}'...")
                    
                    game_data = await self.steam_api.search_game(game_name)
                    
                    if not game_data:
                        await ctx.send(f"❌ Could not find a game named '{game_name}' on Steam.")
                        return
                    
                    app_id = game_data['appid']
                    game_title = game_data['name']
                    
                    # Fetch news
                    await ctx.send(f"📰 Fetching latest news for '{game_title}'...")
                    news_items = await self.steam_api.get_game_news(app_id)
                    
                    if not news_items:
                        await ctx.send(f"❌ No recent news found for '{game_title}'.")
                        return
                    
                    # Process and translate news
                    for i, news in enumerate(news_items[:Config.MAX_NEWS_ITEMS]):
                        await ctx.send(f"🔄 Translating news article {i+1}/{min(len(news_items), Config.MAX_NEWS_ITEMS)}...")
                        
                        # Translate content
                        translated_title = await self.translator.translate_text(news['title'])
                        translated_content = await self.translator.translate_text(news['contents'][:500])  # Limit content length
                        
                        # Create embed
                        embed = discord.Embed(
                            title=f"📰 {translated_title}",
                            description=translated_content + ("..." if len(news['contents']) > 500 else ""),
                            color=0x1e3a8a,
                            timestamp=datetime.fromtimestamp(news['date'])
                        )
                        
                        embed.set_author(name=f"Steam News - {game_title}")
                        embed.add_field(name="🌐 Original Title", value=news['title'][:100] + ("..." if len(news['title']) > 100 else ""), inline=False)
                        embed.add_field(name="✍️ Author", value=news.get('author', 'Steam'), inline=True)
                        embed.add_field(name="🔗 Read More", value=f"[View on Steam]({news['url']})", inline=True)
                        embed.set_footer(text="Translated from English to French")
                        
                        await ctx.send(embed=embed)
                        
                        # Small delay between messages to avoid rate limits
                        if i < len(news_items[:Config.MAX_NEWS_ITEMS]) - 1:
                            await asyncio.sleep(1)
                    
                    await ctx.send("✅ News translation complete!")
                    
            except Exception as e:
                logger.error(f"Error in steam_news command: {e}")
                await ctx.send(f"❌ An error occurred while fetching news: {str(e)}")
        
        @self.command(name='help-steam', help='Get help for Steam news commands')
        async def help_steam(ctx):
            """Custom help command for Steam bot"""
            embed = discord.Embed(
                title="🎮 Steam News Bot Help",
                description="Get the latest Steam game news translated to French!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📰 !steam-news [game_name]",
                value="Fetches recent news for a Steam game and translates it to French.\n"
                      "Example: `!steam-news Counter-Strike 2`",
                inline=False
            )
            
            embed.add_field(
                name="⏰ Rate Limiting",
                value=f"Commands can be used once every {Config.RATE_LIMIT_SECONDS} seconds per user.",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Features",
                value="• Automatic game search\n"
                      "• French translation\n"
                      "• Rich embeds with links\n"
                      "• Error handling",
                inline=False
            )
            
            embed.set_footer(text="Steam News Bot • Made with discord.py")
            
            await ctx.send(embed=embed)
    
    def add_slash_commands(self):
        """Add slash commands for better compatibility"""
        
        @self.tree.command(name='steam-news', description='Get Steam game news translated to French')
        @app_commands.describe(game_name='Name of the Steam game to get news for')
        async def steam_news_slash(interaction: discord.Interaction, game_name: str):
            """Slash command version of steam news"""
            try:
                # Defer the response since this will take time
                await interaction.response.defer()
                
                # Check rate limiting
                if not self.check_rate_limit(interaction.user.id):
                    cooldown_time = self.get_cooldown_remaining(interaction.user.id)
                    await interaction.followup.send(f"⏰ Veuillez attendre {cooldown_time} secondes avant d'utiliser cette commande à nouveau.")
                    return
                
                # All processing in background with single loading message
                await interaction.followup.send(f"🔍 Recherche et traduction des actualités Steam pour '{game_name}'...")
                
                # Search for the game
                game_data = await self.steam_api.search_game(game_name)
                
                if not game_data:
                    await interaction.edit_original_response(content=f"❌ Impossible de trouver un jeu nommé '{game_name}' sur Steam.")
                    return
                
                app_id = game_data['appid']
                game_title = game_data['name']
                
                # Fetch news
                news_items = await self.steam_api.get_game_news(app_id)
                
                if not news_items:
                    await interaction.edit_original_response(content=f"❌ Aucune actualité récente trouvée pour '{game_title}'.")
                    return
                
                # Edit the loading message to show completion
                await interaction.edit_original_response(content=f"✅ Actualités trouvées pour **{game_title}** :")
                
                # Process and translate news (send embeds only)
                for i, news in enumerate(news_items[:Config.MAX_NEWS_ITEMS]):
                    # Translate content
                    translated_title = await self.translator.translate_text(news['title'])
                    translated_content = await self.translator.translate_text(news['contents'][:500])  # Limit content length
                    
                    # Create embed
                    embed = discord.Embed(
                        title=f"📰 {translated_title}",
                        description=translated_content + ("..." if len(news['contents']) > 500 else ""),
                        color=0x1e3a8a,
                        timestamp=datetime.fromtimestamp(news['date'])
                    )
                    
                    embed.set_author(name=f"Steam News - {game_title}")
                    embed.add_field(name="🌐 Titre Original", value=news['title'][:100] + ("..." if len(news['title']) > 100 else ""), inline=False)
                    embed.add_field(name="✍️ Auteur", value=news.get('author', 'Steam'), inline=True)
                    embed.add_field(name="🔗 Lire Plus", value=f"[Voir sur Steam]({news['url']})", inline=True)
                    embed.set_footer(text="Traduit de l'anglais vers le français")
                    
                    await interaction.followup.send(embed=embed)
                    
                    # Small delay between messages to avoid rate limits
                    if i < len(news_items[:Config.MAX_NEWS_ITEMS]) - 1:
                        await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in steam_news slash command: {e}")
                error_msg = f"❌ Une erreur s'est produite lors de la récupération des actualités : {str(e)}"
                if not interaction.response.is_done():
                    await interaction.response.send_message(error_msg)
                else:
                    await interaction.followup.send(error_msg)
        
        @self.tree.command(name='help-steam', description='Aide pour les commandes Steam news')
        async def help_steam_slash(interaction: discord.Interaction):
            """Slash command version of help"""
            embed = discord.Embed(
                title="🎮 Bot Actualités Steam - Aide",
                description="Obtenez les dernières actualités des jeux Steam traduites en français !",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📰 /steam-news [nom_du_jeu]",
                value="Récupère les actualités récentes d'un jeu Steam et les traduit en français.\n"
                      "Exemple : `/steam-news OUTBRK`",
                inline=False
            )
            
            embed.add_field(
                name="⏰ Limitation de Débit",
                value=f"Les commandes peuvent être utilisées une fois toutes les {Config.RATE_LIMIT_SECONDS} secondes par utilisateur.",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Fonctionnalités",
                value="• Recherche automatique de jeux\n"
                      "• Traduction française\n"
                      "• Messages riches avec liens\n"
                      "• Gestion d'erreurs",
                inline=False
            )
            
            embed.set_footer(text="Bot Actualités Steam • Créé avec discord.py")
            
            await interaction.response.send_message(embed=embed)
    
    def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit"""
        now = datetime.now()
        
        if user_id in self.user_cooldowns:
            time_diff = (now - self.user_cooldowns[user_id]).total_seconds()
            if time_diff < Config.RATE_LIMIT_SECONDS:
                return False
        
        self.user_cooldowns[user_id] = now
        return True
    
    def get_cooldown_remaining(self, user_id: int) -> int:
        """Get remaining cooldown time for user"""
        if user_id not in self.user_cooldowns:
            return 0
        
        now = datetime.now()
        time_diff = (now - self.user_cooldowns[user_id]).total_seconds()
        remaining = Config.RATE_LIMIT_SECONDS - time_diff
        
        return max(0, int(remaining))
    
    async def on_ready(self):
        """Called when bot is ready"""
        if self.user:
            logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
            
            # Sync slash commands
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} command(s)")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
            
            # Set bot status
            activity = discord.Game(name="Steam News | /steam-news")
            await self.change_presence(activity=activity)
            
            print(f"✅ Bot is ready! Logged in as {self.user}")
        else:
            logger.error("Bot user is None - this should not happen")
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ Command not found. Use `!help-steam` for available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument. Use `!help {ctx.command}` for usage information.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send("❌ An unexpected error occurred. Please try again later.")
    
    async def on_error(self, event, *args, **kwargs):
        """Handle general bot errors"""
        logger.error(f"Bot error in event {event}: {args}, {kwargs}")
