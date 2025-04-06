import os
import discord
import dotenv
from discord.ext import commands
from tts_player_service import TTSPlayerService

dotenv.load_dotenv()
token = str(os.getenv("TOKEN"))
speak_api_url = str(os.getenv("SPEAK_API_URL"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)
tts_service = TTSPlayerService(bot)

@bot.event
async def on_ready():
    print(f"登录成功，机器人名字是 {bot.user}")

@bot.slash_command(name="say", description="播放语音")
async def say(ctx: discord.ApplicationContext, message: str):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.respond("请先加入一个语音频道。", ephemeral=True)
        return

    await ctx.respond(f"{message}")
    await tts_service.join_and_speak(
        ctx.author.voice.channel,
        message,
        speak_api_url
    )

bot.run(token)
