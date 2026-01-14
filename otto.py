import os
import re
from typing import Optional

import discord
import dotenv
import aiohttp
from discord import Option
from discord.ext import commands
from discord.ui import View, Select, Button

from tts_player_service import TTSPlayerService

dotenv.load_dotenv()
token = str(os.getenv("TOKEN"))
speak_api_url = str(os.getenv("SPEAK_API_URL"))
musix_api_url = str(os.getenv("MUSIX_API_URL"))

# 尝试加载 Opus 库
if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus('libopus.so.0')
    except Exception as e:
        print(f"⚠️  无法加载 Opus 库: {e}")
        print("💡 请安装 libopus: sudo apt install libopus0  # Ubuntu/Debian")
        print("💡 或: sudo dnf install opus              # Fedora/RHEL")
        print("💡 或: sudo pacman -S opus                # Arch Linux")

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)
tts_service = TTSPlayerService(bot)

# 跟踪每个用户的最后搜索消息 (key: user_id, value: message)
last_search_messages = {}

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
        message: Option(str, description="需要棍哥朗诵的内容")  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"{message}")
        await tts_service.join_and_speak(
            ctx.author.voice.channel,  # type: ignore
            message,
            speak_api_url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="play_url", description="播放在线音频（mp3/wav 等）")
async def play_url(
        ctx: discord.ApplicationContext,
        url: Option(str, "音频文件url")  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"🎧 准备播放音频：{url}")
        await tts_service.join_and_play_url(
            ctx.author.voice.channel,  # type: ignore
            url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="skip", description="跳过当前播放的音频")
async def skip(ctx: discord.ApplicationContext):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await tts_service.skip(ctx.guild.id if ctx.guild else 0)  # type: ignore
        await ctx.respond("⏭️ 已尝试跳过当前播放")
    except Exception as e:
        await ctx.respond(f"❌ 跳过失败：{e}", ephemeral=True)

@bot.slash_command(name="stream_url", description="播放流式音频（直播/广播）")
async def stream_url(
        ctx: discord.ApplicationContext,
        url: Option(str, "流式音频url")  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await ctx.respond(f"📡 正在流式播放：{url}")
        await tts_service.join_and_stream_url(
            ctx.author.voice.channel,  # type: ignore
            url,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="play_bilibili", description="解析播放bilibili视频的音频")
async def play_bilibili(
        ctx: discord.ApplicationContext,
        bvid: Option(str, description="BV号"),  # type: ignore
        page: Option(int, description="分P号") = 0  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await tts_service.join_and_play_bilibili(
            ctx.author.voice.channel,  # type: ignore
            bvid,
            ctx,
            page
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="play_netease", description="解析播放网易云音乐")
async def play_netease(
        ctx: discord.ApplicationContext,
        id: Option(int, description="歌曲ID")  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        await tts_service.join_and_play_netease(
            ctx.author.voice.channel,  # type: ignore
            id,
            ctx
        )
    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{e}", ephemeral=True)

@bot.slash_command(name="search_bilibili", description="搜索bilibili视频")
async def search_bilibili(
        ctx: discord.ApplicationContext,
        keywords: str,
        page: Option(int, "页码", min_value=1, default=1) = 1,  # type: ignore
        original_message: Optional[discord.Message] = None  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        # 删除用户的上一次搜索消息
        user_id = ctx.author.id
        if user_id in last_search_messages:
            try:
                await last_search_messages[user_id].delete()
            except:
                pass
            del last_search_messages[user_id]

        if original_message:
            try:
                await original_message.delete()
            except:
                pass

        # 使用musix API搜索
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{musix_api_url}/bilibili/search", params={"keywords": keywords, "page": page}) as resp:
                if resp.status != 200:
                    await ctx.respond(f"❌ 搜索失败: HTTP {resp.status}", ephemeral=True)
                    return
                result = await resp.json()
                
                # 检查API响应格式
                if "data" not in result:
                    await ctx.respond(f"❌ API响应格式错误: {result}", ephemeral=True)
                    return
                
                response_data = result.get("data", {})
                video_results = response_data.get("items", [])
                pagination = response_data.get("pagination", {})
                total_pages = pagination.get("total_pages", 1)

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
            bilibili_previous_page_button = Button(
                label="上一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"bilibili_previous_page_{page}"
            )

            async def bilibili_previous_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_bilibili(ctx, keywords, page - 1, original_message=current_message)

            bilibili_previous_page_button.callback = bilibili_previous_page_callback
            view.add_item(bilibili_previous_page_button)

        if page < total_pages:
            bilibili_next_page_button = Button(
                label="下一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"bilibili_next_page_{page}"
            )

            async def bilibili_next_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_bilibili(ctx, keywords, page + 1, original_message=current_message)

            bilibili_next_page_button.callback = bilibili_next_page_callback
            view.add_item(bilibili_next_page_button)

        # 选择视频的回调
        async def bilibili_select_callback(interaction):
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

        select.callback = bilibili_select_callback

        response_msg = await ctx.respond(
            f"🔍 第 {page} 页 | 找到 {len(video_results)} 个结果，请选择:",
            view=view,
            ephemeral=False
        )
        
        # 保存这次搜索的消息
        if hasattr(response_msg, 'message'):
            last_search_messages[user_id] = response_msg.message
        elif isinstance(response_msg, discord.Message):
            last_search_messages[user_id] = response_msg

    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{str(e)}", ephemeral=True)

@bot.slash_command(name="search_netease", description="搜索网易云音乐")
async def search_netease(
        ctx: discord.ApplicationContext,
        keywords: str,
        page: Option(int, "页数", min_value=1, default=1) = 1,  # type: ignore
        original_message: Optional[discord.Message] = None  # type: ignore
):
    page_limit = 25
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        # 删除用户的上一次搜索消息
        user_id = ctx.author.id
        if user_id in last_search_messages:
            try:
                await last_search_messages[user_id].delete()
            except:
                pass
            del last_search_messages[user_id]

        if original_message:
            try:
              await original_message.delete()
            except:
                pass

        # 使用musix API搜索
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{musix_api_url}/netease/search", params={"keywords": keywords, "page": page, "limit": page_limit}) as resp:
                if resp.status != 200:
                    await ctx.respond(f"❌ 搜索失败: HTTP {resp.status}", ephemeral=True)
                    return
                result = await resp.json()
                
                # 检查API响应格式
                if "data" not in result:
                    await ctx.respond(f"❌ API响应格式错误: {result}", ephemeral=True)
                    return
                
                response_data = result.get("data", {})
                music_results = response_data.get("items", [])
                pagination = response_data.get("pagination", {})
                total_count = pagination.get("total_count", 0)
                total_pages = pagination.get("total_pages", 1)

        if not music_results:
            await ctx.respond("🔍 没有找到相关歌曲", ephemeral=True)
            return

        # 构建选项列表，安全地处理数据格式
        options = []
        for idx, music in enumerate(music_results):
            name = music.get('name', '未知歌曲')[:50]
            
            # 安全地获取艺术家名称
            artists = music.get('artists', [])
            if artists and len(artists) > 0:
                author = artists[0].get('name', '未知')
            else:
                author = '未知'
            
            options.append(discord.SelectOption(
                label=name,
                description=f"作者: {author}",
                value=str(idx),
                emoji="🎵"
            ))

        select = Select(
            placeholder="选择要播放的歌曲",
            options=options
        )

        view = View(timeout=60)
        view.add_item(select)

        if page > 1:
            netease_previous_page_button = Button(
                label="上一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"netease_previous_page_{page}"
            )

            async def netease_previous_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_netease(ctx, keywords, page - 1, original_message=current_message)

            netease_previous_page_button.callback = netease_previous_page_callback
            view.add_item(netease_previous_page_button)

        if page < total_pages:
            netease_next_page_button = Button(
                label="下一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"netease_next_page_{page}"
            )

            async def netease_next_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await search_netease(ctx, keywords, page + 1, original_message=current_message)

            netease_next_page_button.callback = netease_next_page_callback
            view.add_item(netease_next_page_button)

        async def netease_select_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ 这不是你的搜索请求!", ephemeral=True)
                return

            selected_idx = int(select.values[0])
            selected_music = music_results[selected_idx]
            id = selected_music['id']

            await interaction.response.edit_message(
                content=f"✅ {interaction.user.mention} 选择了: {selected_music['name']}",
                view=None,
            )

            await play_netease(ctx, id)

        select.callback = netease_select_callback

        response_msg = await ctx.respond(
            f"🔍 第 {page} 页 | 找到 {len(music_results)} 个结果，请选择:",
            view=view,
            ephemeral=False
        )
        
        # 保存这次搜索的消息
        if hasattr(response_msg, 'message'):
            last_search_messages[user_id] = response_msg.message
        elif isinstance(response_msg, discord.Message):
            last_search_messages[user_id] = response_msg

    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{str(e)}", ephemeral=True)

@bot.slash_command(name="get_bilibili_popular", description="获取bilibili热门视频")
async def get_bilibili_popular(
        ctx: discord.ApplicationContext,
        tag: Option(str, "标签名称（如编程、音乐等）", required=False) = None,  # type: ignore
        page: Option(int, "页码", min_value=1, default=1) = 1,  # type: ignore
        page_size: Option(int, "每页数量（最大50）", min_value=1, max_value=50, default=20) = 20,  # type: ignore
        days: Option(int, "时间范围（天数）：1=当天，7=本周，30=本月", choices=[1, 7, 30], required=False) = None,  # type: ignore
        original_message: Optional[discord.Message] = None  # type: ignore
):
    try:
        if not ctx.author.voice or not ctx.author.voice.channel:  # type: ignore
            await ctx.respond("❗ 请先加入一个语音频道。", ephemeral=True)
            return

        # 删除用户的上一次搜索消息
        user_id = ctx.author.id
        if user_id in last_search_messages:
            try:
                await last_search_messages[user_id].delete()
            except:
                pass
            del last_search_messages[user_id]

        if original_message:
            try:
                await original_message.delete()
            except:
                pass

        # 构建请求参数
        params = {
            "page": page,
            "page_size": page_size
        }
        if tag:
            params["tag"] = tag
        if days:
            params["days"] = days

        # 使用musix API获取热门视频
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{musix_api_url}/bilibili/popular", params=params) as resp:
                if resp.status != 200:
                    await ctx.respond(f"❌ 获取热门视频失败: HTTP {resp.status}", ephemeral=True)
                    return
                result = await resp.json()
                
                # 检查API响应格式
                if "data" not in result:
                    await ctx.respond(f"❌ API响应格式错误: {result}", ephemeral=True)
                    return
                
                response_data = result.get("data", {})
                video_results = response_data.get("items", [])
                pagination = response_data.get("pagination", {})
                total_pages = pagination.get("total_pages", 1)

        if not video_results:
            await ctx.respond("🔍 没有找到热门视频", ephemeral=True)
            return

        # 构建标题信息
        title_parts = ["🔥 热门视频"]
        if tag:
            title_parts.append(f"「{tag}」")
        if days == 1:
            title_parts.append("| 当天")
        elif days == 7:
            title_parts.append("| 本周")
        elif days == 30:
            title_parts.append("| 本月")
        title = " ".join(title_parts)

        select = Select(
            placeholder="选择要播放的视频",
            options=[
                discord.SelectOption(
                    label=clean_html_tags(video['title'])[:50],
                    description=f"UP: {video['author']} | 播放: {video['play']} | 时长: {video['duration']}",
                    value=str(idx),
                    emoji="🔥"
                ) for idx, video in enumerate(video_results)
            ]
        )

        view = View(timeout=60)
        view.add_item(select)

        # 添加翻页按钮
        if page > 1:
            popular_previous_page_button = Button(
                label="上一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"popular_previous_page_{page}"
            )

            async def popular_previous_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await get_bilibili_popular(ctx, tag, page - 1, page_size, days, original_message=current_message)

            popular_previous_page_button.callback = popular_previous_page_callback
            view.add_item(popular_previous_page_button)

        if page < total_pages:
            popular_next_page_button = Button(
                label="下一页",
                style=discord.ButtonStyle.primary,
                custom_id=f"popular_next_page_{page}"
            )

            async def popular_next_page_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有发起搜索的人可以翻页！", ephemeral=True)
                    return

                current_message = interaction.message
                await interaction.response.defer()

                await get_bilibili_popular(ctx, tag, page + 1, page_size, days, original_message=current_message)

            popular_next_page_button.callback = popular_next_page_callback
            view.add_item(popular_next_page_button)

        # 选择视频的回调
        async def popular_select_callback(interaction):
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

        select.callback = popular_select_callback

        response_msg = await ctx.respond(
            f"{title} | 第 {page} 页 | 找到 {len(video_results)} 个结果，请选择:",
            view=view,
            ephemeral=False
        )
        
        # 保存这次搜索的消息
        if hasattr(response_msg, 'message'):
            last_search_messages[user_id] = response_msg.message
        elif isinstance(response_msg, discord.Message):
            last_search_messages[user_id] = response_msg

    except Exception as e:
        await ctx.respond(f"❌ 出现错误：{str(e)}", ephemeral=True)

bot.run(token)
