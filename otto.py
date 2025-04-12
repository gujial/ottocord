import os
import re

import discord
import dotenv
from discord import Option
from discord.ext import commands
from discord.ui import View, Select, Button

from tts_player_service import TTSPlayerService
from bilibili_api import search, sync

dotenv.load_dotenv()
token = str(os.getenv("TOKEN"))
speak_api_url = str(os.getenv("SPEAK_API_URL"))

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)
tts_service = TTSPlayerService(bot)

def clean_html_tags(text):
    """移除所有HTML标签"""
    if not isinstance(text, str):
        return text
    return re.sub(r'<[^>]+>', '', text)

@bot.event
async def on_ready():
    print(f"✅ 登录成功，机器人名字是 {bot.user}")

@bot.slash_command(name="say", description="播放语音（通过 TTS）")
async def say(
        ctx: discord.ApplicationContext,
        message: Option(str, description="需要棍哥朗诵的内容")
):
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
async def play_url(
        ctx: discord.ApplicationContext,
        url: Option(str, "音频文件url")
):
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
async def stream_url(
        ctx: discord.ApplicationContext,
        url: Option(str, "流式音频url")
):
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
async def play_bilibili(
        ctx: discord.ApplicationContext,
        bvid: Option(str, description="BV号"),
        page: Option(int, description="分P号") = 1
):
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

@bot.slash_command(name="search_bilibili", description="搜索bilibili视频")
async def search_bilibili(
        ctx: discord.ApplicationContext,
        keywords: str,
        page: Option(int, "页码", min_value=1, default=1) = 1,
        original_message: Option(discord.Message, "原始消息，一般指向搜索结果") = None
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        if original_message:
            try:
                await original_message.delete()
            except:
                pass

        response = sync(search.search(keywords, page=page))

        video_results = []
        for result in response['result']:
            if result['result_type'] == 'video':
                video_results = result['data']
                break

        if not video_results:
            await ctx.respond("🔍 没有找到相关视频", ephemeral=True)
            return

        select = Select(
            placeholder="选择要播放的视频",
            options=[
                discord.SelectOption(
                    label=clean_html_tags(video['title'])[:50],
                    description=f"UP: {video['author']} | 时长: {video['duration']}",
                    value=str(idx),
                    emoji="🎬"
                ) for idx, video in enumerate(video_results)
            ]
        )

        view = View(timeout=60)
        view.add_item(select)

        if page > 1:
            previous_page_button = Button(
                label="上一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"previous_page_{page}"
            )

            async def previous_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_bilibili(ctx, keywords, page - 1, original_message=current_message)

            previous_page_button.callback = previous_page_callback
            view.add_item(previous_page_button)

        if page < response["numPages"]:
            next_page_button = Button(
                label="下一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"next_page_{page}"
            )

            async def next_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_bilibili(ctx, keywords, page + 1, original_message=current_message)

            next_page_button.callback = next_page_callback
            view.add_item(next_page_button)

        # 选择视频的回调
        async def select_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ 这不是你的搜索请求!", ephemeral=True)
                return

            selected_idx = int(select.values[0])
            selected_video = video_results[selected_idx]
            bvid = selected_video['bvid']

            await interaction.response.edit_message(
                content=f"✅ {interaction.user.mention} 选择了: {clean_html_tags(selected_video['title'])}",
                view=None,
            )

            await play_bilibili(ctx, bvid)

        select.callback = select_callback

        await ctx.respond(
            f"🔍 第 {page} 页 | 找到 {len(video_results)} 个结果，请选择:",
            view=view,
            ephemeral=False
        )

    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{str(e)}", ephemeral=True)

bot.run(token)
