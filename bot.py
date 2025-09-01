"""
Discord Bot Implementation
Handles Discord interactions and command processing
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import asyncio
import json
import os
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
        
        # Auto-posting system
        self.published_news_file = "published_news.json"
        self.published_news = self.load_published_news()
        self.auto_channel_id = None  # Will be set later
        
        # Add commands
        self.add_commands()
        self.add_slash_commands()
        self.setup_auto_commands()
    
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
                # Check rate limiting FIRST before deferring
                if not self.check_rate_limit(interaction.user.id):
                    cooldown_time = self.get_cooldown_remaining(interaction.user.id)
                    await interaction.response.send_message(f"⏰ Veuillez attendre {cooldown_time} secondes avant d'utiliser cette commande à nouveau.", ephemeral=True)
                    return
                
                # Send immediate ephemeral response
                await interaction.response.send_message(f"🔍 Recherche et publication des actualités pour '{game_name}' en cours...", ephemeral=True)
                
                # Process news and post directly to channel (not via interaction)
                asyncio.create_task(self._process_and_post_news(interaction, game_name))
                
            except Exception as e:
                logger.error(f"Error in steam_news slash command: {e}")
                error_msg = f"❌ Une erreur s'est produite lors de la récupération des actualités."
                
                try:
                    await interaction.edit_original_response(content=error_msg)
                except discord.NotFound:
                    # Interaction already expired, can't respond
                    logger.warning("Interaction expired, cannot send error message")
                except Exception as followup_error:
                    logger.error(f"Could not send error message: {followup_error}")
    
    async def _process_and_post_news(self, interaction: discord.Interaction, game_name: str):
        """Process news and post directly to channel (not via interaction)"""
        try:
            await asyncio.sleep(0.5)  # Small delay to ensure initial response is processed
            
            # Search for the game
            game_data = await self.steam_api.search_game(game_name)
            
            if not game_data:
                await interaction.edit_original_response(content=f"❌ Impossible de trouver un jeu nommé '{game_name}' sur Steam.")
                return
            
            app_id = game_data['appid']
            game_title = game_data['name']
            
            # Update ephemeral message
            await interaction.edit_original_response(content=f"🔍 Jeu trouvé: **{game_title}**\n📰 Récupération des actualités...")
            
            # Fetch news
            news_items = await self.steam_api.get_game_news(app_id)
            
            if not news_items:
                await interaction.edit_original_response(content=f"❌ Aucune actualité récente trouvée pour '{game_title}'.")
                return
                
            # Update ephemeral message
            await interaction.edit_original_response(content=f"✅ **{len(news_items[:Config.MAX_NEWS_ITEMS])} actualité(s) trouvée(s) pour {game_title}**\n🔄 Traduction et publication en cours...")
            
            # Get game header image once for fallback
            game_header_image = await self.steam_api.get_game_header_image(app_id)
            
            # Get the channel where the command was used
            channel = interaction.channel
            
            # Process and translate news (post directly to channel)
            for i, news in enumerate(news_items[:Config.MAX_NEWS_ITEMS]):
                # Translate content
                translated_title = await self.translator.translate_text(news['title'])
                translated_content = await self.translator.translate_text(news['contents'][:600])
                
                # Create improved embed with Steam-like design
                embed = discord.Embed(
                    title=translated_title,
                    description=translated_content + ("..." if len(news['contents']) > 600 else ""),
                    color=0x1b2838,  # Steam dark blue/gray
                    timestamp=datetime.fromtimestamp(news['date'])
                )
                
                # Use game title as author with Steam icon
                embed.set_author(
                    name=f"🎮 {game_title}",
                    icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                )
                
                # Add main image if available
                if 'image' in news and news['image']:
                    embed.set_image(url=news['image'])
                    # Also add game header as thumbnail for better visual
                    if game_header_image:
                        embed.set_thumbnail(url=game_header_image)
                elif game_header_image:
                    # Use game header as main image if no news image
                    embed.set_image(url=game_header_image)
                
                # Add fields with better formatting (more compact)
                if news['title'] != translated_title and len(news['title']) > 10:
                    embed.add_field(
                        name="🌐 Titre Original", 
                        value=f"*{news['title'][:120]}{'...' if len(news['title']) > 120 else ''}*", 
                        inline=False
                    )
                
                # Create a more compact info line
                info_parts = []
                if news.get('author') and news['author'] != 'Steam':
                    info_parts.append(f"👤 {news['author']}")
                info_parts.append(f"📅 <t:{news['date']}:R>")
                
                if len(info_parts) == 2:
                    embed.add_field(name="👤 Auteur", value=info_parts[0].replace("👤 ", ""), inline=True)
                    embed.add_field(name="📅 Publié", value=info_parts[1].replace("📅 ", ""), inline=True)
                    embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                else:
                    embed.add_field(name="📅 Publié", value=info_parts[-1].replace("📅 ", ""), inline=True)
                    embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for alignment
                
                # Footer with translation info and Steam branding
                embed.set_footer(
                    text="🇫🇷 Traduit automatiquement • Actualités Steam",
                    icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                )
                
                # Post directly to channel (public)
                try:
                    await channel.send(embed=embed)
                    logger.info(f"Successfully posted news to channel: {translated_title[:30]}...")
                except Exception as e:
                    logger.error(f"Failed to send embed to channel: {e}")
                    # Try sending as simple text instead
                    try:
                        await channel.send(f"**{translated_title}**\n\n{translated_content[:500]}...\n\n🔗 {news['url']}")
                    except Exception as e2:
                        logger.error(f"Failed to send text to channel too: {e2}")
                
                # Small delay between messages to avoid rate limits
                if i < len(news_items[:Config.MAX_NEWS_ITEMS]) - 1:
                    await asyncio.sleep(1)
            
            # Update final ephemeral message
            await interaction.edit_original_response(content=f"✅ **Publication terminée !**\n📰 {len(news_items[:Config.MAX_NEWS_ITEMS])} actualité(s) de **{game_title}** publiée(s) dans le canal.")
                    
        except Exception as e:
            logger.error(f"Error in news processing: {e}")
            try:
                await interaction.edit_original_response(content="❌ Une erreur s'est produite lors de la récupération des actualités.")
            except:
                pass

    async def _process_news_via_interaction(self, interaction: discord.Interaction, game_name: str):
        """Process news via interaction followups to bypass channel permission issues"""
        try:
            await asyncio.sleep(0.5)  # Small delay to ensure defer is processed
            
            # Search for the game
            game_data = await self.steam_api.search_game(game_name)
            
            if not game_data:
                await interaction.followup.send(f"❌ Impossible de trouver un jeu nommé '{game_name}' sur Steam.")
                return
            
            app_id = game_data['appid']
            game_title = game_data['name']
            
            # Fetch news
            news_items = await self.steam_api.get_game_news(app_id)
            
            if not news_items:
                await interaction.followup.send(f"❌ Aucune actualité récente trouvée pour '{game_title}'.")
                return
                
            # Get game header image once for fallback
            game_header_image = await self.steam_api.get_game_header_image(app_id)
            
            # Send a confirmation message first
            await interaction.followup.send(f"📰 **Actualités {game_title}** :")
            
            # Process and translate news (send embeds via followup)
            for i, news in enumerate(news_items[:Config.MAX_NEWS_ITEMS]):
                # Translate content
                translated_title = await self.translator.translate_text(news['title'])
                translated_content = await self.translator.translate_text(news['contents'][:600])
                
                # Create improved embed with Steam-like design
                embed = discord.Embed(
                    title=translated_title,
                    description=translated_content + ("..." if len(news['contents']) > 600 else ""),
                    color=0x1b2838,  # Steam dark blue/gray
                    timestamp=datetime.fromtimestamp(news['date'])
                )
                
                # Use game title as author with Steam icon
                embed.set_author(
                    name=f"🎮 {game_title}",
                    icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                )
                
                # Add main image if available
                if 'image' in news and news['image']:
                    embed.set_image(url=news['image'])
                    # Also add game header as thumbnail for better visual
                    if game_header_image:
                        embed.set_thumbnail(url=game_header_image)
                elif game_header_image:
                    # Use game header as main image if no news image
                    embed.set_image(url=game_header_image)
                
                # Add fields with better formatting (more compact)
                if news['title'] != translated_title and len(news['title']) > 10:
                    embed.add_field(
                        name="🌐 Titre Original", 
                        value=f"*{news['title'][:120]}{'...' if len(news['title']) > 120 else ''}*", 
                        inline=False
                    )
                
                # Create a more compact info line
                info_parts = []
                if news.get('author') and news['author'] != 'Steam':
                    info_parts.append(f"👤 {news['author']}")
                info_parts.append(f"📅 <t:{news['date']}:R>")
                
                if len(info_parts) == 2:
                    embed.add_field(name="👤 Auteur", value=info_parts[0].replace("👤 ", ""), inline=True)
                    embed.add_field(name="📅 Publié", value=info_parts[1].replace("📅 ", ""), inline=True)
                    embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                else:
                    embed.add_field(name="📅 Publié", value=info_parts[-1].replace("📅 ", ""), inline=True)
                    embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Empty field for alignment
                
                # Footer with translation info and Steam branding
                embed.set_footer(
                    text="🇫🇷 Traduit automatiquement • Actualités Steam",
                    icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                )
                
                # Send via interaction followup (this should work even with limited permissions)
                try:
                    await interaction.followup.send(embed=embed)
                    logger.info(f"Successfully sent news via followup: {translated_title[:30]}...")
                except Exception as e:
                    logger.error(f"Failed to send embed via followup: {e}")
                    # Try sending as simple text instead
                    try:
                        await interaction.followup.send(f"**{translated_title}**\n\n{translated_content[:500]}...\n\n🔗 {news['url']}")
                    except Exception as e2:
                        logger.error(f"Failed to send text via followup too: {e2}")
                
                # Small delay between messages to avoid rate limits
                if i < len(news_items[:Config.MAX_NEWS_ITEMS]) - 1:
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error in interaction news processing: {e}")
            try:
                await interaction.followup.send("❌ Une erreur s'est produite lors de la récupération des actualités.")
            except:
                pass
    def setup_help_command(self):
        """Setup help command separately to avoid duplicate registration"""
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
            
            # Start auto news checking
            if not self.auto_news_checker.is_running():
                self.auto_news_checker.start()
                logger.info("Started automatic news checking for OUTBRK")
            
            # Set bot status
            activity = discord.Game(name="Steam News | /steam-news")
            await self.change_presence(activity=activity)
            
            print(f"✅ Bot is ready! Logged in as {self.user}")
        else:
            logger.error("Bot user is None - this should not happen")
    
    def load_published_news(self):
        """Load previously published news from file"""
        try:
            if os.path.exists(self.published_news_file):
                with open(self.published_news_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            logger.error(f"Error loading published news: {e}")
            return set()
    
    def save_published_news(self):
        """Save published news to file"""
        try:
            with open(self.published_news_file, 'w') as f:
                json.dump(list(self.published_news), f)
        except Exception as e:
            logger.error(f"Error saving published news: {e}")
    
    @tasks.loop(hours=1)  # Check every hour
    async def auto_news_checker(self):
        """Automatically check for new OUTBRK news and post them"""
        try:
            if not self.auto_channel_id:
                logger.warning("Auto channel not set, skipping auto news check")
                return
            
            channel = self.get_channel(self.auto_channel_id)
            if not channel:
                logger.error(f"Could not find channel {self.auto_channel_id}")
                return
            
            logger.info("Checking for new OUTBRK news...")
            
            # Get OUTBRK news (app_id: 1107320)
            news_items = await self.steam_api.get_game_news(1107320)
            
            if not news_items:
                return
            
            # Get game header image once for fallback
            game_header_image = await self.steam_api.get_game_header_image(1107320)
            
            new_news_found = False
            
            # Check each news item
            for news in news_items[:Config.MAX_NEWS_ITEMS]:
                news_id = f"{news['gid']}"  # Unique identifier
                
                if news_id not in self.published_news:
                    # This is a new news item!
                    new_news_found = True
                    logger.info(f"Found new OUTBRK news: {news['title'][:50]}...")
                    
                    # Translate content
                    translated_title = await self.translator.translate_text(news['title'])
                    translated_content = await self.translator.translate_text(news['contents'][:600])
                    
                    # Create embed with Steam-like design
                    embed = discord.Embed(
                        title=translated_title,
                        description=translated_content + ("..." if len(news['contents']) > 600 else ""),
                        color=0x1b2838,  # Steam dark blue/gray
                        timestamp=datetime.fromtimestamp(news['date'])
                    )
                    
                    # Use game title as author with Steam icon
                    embed.set_author(
                        name="🎮 OUTBRK",
                        icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                    )
                    
                    # Add main image if available
                    if 'image' in news and news['image']:
                        embed.set_image(url=news['image'])
                        if game_header_image:
                            embed.set_thumbnail(url=game_header_image)
                    elif game_header_image:
                        embed.set_image(url=game_header_image)
                    
                    # Add fields
                    if news['title'] != translated_title and len(news['title']) > 10:
                        embed.add_field(
                            name="🌐 Titre Original", 
                            value=f"*{news['title'][:120]}{'...' if len(news['title']) > 120 else ''}*", 
                            inline=False
                        )
                    
                    info_parts = []
                    if news.get('author') and news['author'] != 'Steam':
                        info_parts.append(f"👤 {news['author']}")
                    info_parts.append(f"📅 <t:{news['date']}:R>")
                    
                    if len(info_parts) == 2:
                        embed.add_field(name="👤 Auteur", value=info_parts[0].replace("👤 ", ""), inline=True)
                        embed.add_field(name="📅 Publié", value=info_parts[1].replace("📅 ", ""), inline=True)
                        embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                    else:
                        embed.add_field(name="📅 Publié", value=info_parts[-1].replace("📅 ", ""), inline=True)
                        embed.add_field(name="🔗 Source", value=f"[Lire sur Steam]({news['url']})", inline=True)
                        embed.add_field(name="\u200b", value="\u200b", inline=True)
                    
                    # Footer
                    embed.set_footer(
                        text="🇫🇷 Traduit automatiquement • Actualités Steam",
                        icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                    )
                    
                    try:
                        # Send only the embed, no additional message
                        await channel.send(embed=embed)
                        
                        # Mark as published
                        self.published_news.add(news_id)
                        self.save_published_news()
                        
                        logger.info(f"Successfully posted new OUTBRK news: {translated_title[:30]}...")
                        
                        # Small delay between multiple news
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Failed to post auto news: {e}")
            
            if not new_news_found:
                logger.info("No new OUTBRK news found")
                
        except Exception as e:
            logger.error(f"Error in auto news checker: {e}")
    
    @auto_news_checker.before_loop
    async def before_auto_news_checker(self):
        """Wait for bot to be ready before starting auto checker"""
        await self.wait_until_ready()
    
    def setup_auto_commands(self):
        """Setup automatic posting commands"""
        @self.tree.command(name='setup-auto', description='Configurer la publication automatique OUTBRK dans ce channel')
        async def setup_auto_slash(interaction: discord.Interaction):
            """Setup automatic posting in this channel"""
            try:
                self.auto_channel_id = interaction.channel.id
                
                embed = discord.Embed(
                    title="🤖 Publication automatique activée !",
                    description=f"Les nouvelles actualités OUTBRK seront automatiquement publiées dans {interaction.channel.mention}",
                    color=0x1b2838
                )
                
                embed.add_field(
                    name="📅 Fréquence", 
                    value="Vérification toutes les heures", 
                    inline=True
                )
                embed.add_field(
                    name="🎮 Jeu surveillé", 
                    value="OUTBRK (ID: 1107320)", 
                    inline=True
                )
                embed.add_field(
                    name="🇫🇷 Langue", 
                    value="Traduction française automatique", 
                    inline=True
                )
                
                embed.set_footer(
                    text="Le bot vérifiera automatiquement les nouvelles actualités",
                    icon_url="https://cdn.akamai.steamstatic.com/steamcommunity/public/images/steamworks_docs/english/steam_icon.png"
                )
                
                await interaction.response.send_message(embed=embed)
                logger.info(f"Auto posting setup for channel {interaction.channel.id}")
                
            except Exception as e:
                logger.error(f"Error in setup_auto command: {e}")
                await interaction.response.send_message("❌ Erreur lors de la configuration.", ephemeral=True)
        
        @self.tree.command(name='stop-auto', description='Arrêter la publication automatique')
        async def stop_auto_slash(interaction: discord.Interaction):
            """Stop automatic posting"""
            try:
                if self.auto_channel_id:
                    self.auto_channel_id = None
                    embed = discord.Embed(
                        title="🛑 Publication automatique désactivée",
                        description="La publication automatique des actualités OUTBRK a été arrêtée.",
                        color=0xff6b35
                    )
                    await interaction.response.send_message(embed=embed)
                    logger.info("Auto posting stopped")
                else:
                    await interaction.response.send_message("❌ La publication automatique n'était pas activée.", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error in stop_auto command: {e}")
                await interaction.response.send_message("❌ Erreur lors de l'arrêt.", ephemeral=True)
    
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
