import os
import discord
import dotenv
from discord.ext import commands
from tts_player_service import TTSPlayerService

dotenv.load_dotenv()
token = str(os.getenv("TOKEN"))
speak_api_url = str(os.getenv("SPEAK_API_URL"))

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)
tts_service = TTSPlayerService(bot)

@bot.event
async def on_ready():
    print(f"✅ 登录成功，机器人名字是 {bot.user}")

@bot.slash_command(name="say", description="播放语音（通过 TTS）")
async def say(ctx: discord.ApplicationContext, message: str):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"{message}")
        await tts_service.join_and_speak(
            ctx.author.voice.channel,
            message,
            speak_api_url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="play_url", description="播放在线音频（mp3/wav 等）")
async def play_url(ctx: discord.ApplicationContext, url: str):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"🎧 准备播放音频：{url}")
        await tts_service.join_and_play_url(
            ctx.author.voice.channel,
            url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="skip", description="跳过当前播放的音频")
async def skip(ctx: discord.ApplicationContext):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await tts_service.skip(ctx.guild.id)
        await ctx.respond("⏭️ 已尝试跳过当前播放")
    except Exception as e:
        await ctx.respond(f"❌ 跳过失败：{e}", ephemeral=True)

@bot.slash_command(name="stream_url", description="播放流式音频（直播/广播）")
async def stream_url(ctx: discord.ApplicationContext, url: str):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"📡 正在流式播放：{url}")
        await tts_service.join_and_stream_url(
            ctx.author.voice.channel,
            url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="play_bilibili", description="解析播放bilibili视频的音频")
async def play_bilibili(ctx: discord.ApplicationContext, bvid:str, page:int=0):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await tts_service.join_and_play_bilibili(
            ctx.author.voice.channel,
            bvid,
            ctx,
            page
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

bot.run(token)
