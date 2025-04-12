import time

import discord
import aiohttp
import asyncio
import tempfile
import os
import datetime
from bilibili_api import video
from collections import defaultdict


async def _send_error_to_voice_channel(error_message: str, ctx: discord.ApplicationContext):
    await ctx.respond(error_message, ephemeral=True)

class TTSPlayerService:
    def __init__(self, bot: discord.Bot, ffmpeg_path="ffmpeg"):
        self.bot = bot
        self.ffmpeg_path = ffmpeg_path
        self.queues: dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.playing_tasks: dict[int, asyncio.Task] = {}
        self.current_voice_clients: dict[int, discord.VoiceClient] = {}

    @staticmethod
    def log(guild_id: int, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [GUILD {guild_id}] {message}")

    async def _add_queue(self, guild_id, message, ctx):
        self.log(guild_id, f"✅ 加入播放队列：{message}")

        if guild_id not in self.playing_tasks or self.playing_tasks[guild_id].done():
            task = asyncio.create_task(self._player_loop(guild_id, ctx))
            self.playing_tasks[guild_id] = task

    async def join_and_speak(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, message, speak_api_url))
        try:
            await self._add_queue(guild_id, message, ctx)
        except Exception as e:
            await _send_error_to_voice_channel(f"❌ 播放语音时发生错误: {str(e)}", ctx)

    async def join_and_play_url(self, voice_channel: discord.VoiceChannel, audio_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, audio_url, None))  # None 表示是 URL 播放
        try:
            await self._add_queue(guild_id, audio_url, ctx)
        except Exception as e:
            await _send_error_to_voice_channel(f"❌ 播放 URL 时发生错误: {str(e)}", ctx)

    async def join_and_stream_url(self, voice_channel: discord.VoiceChannel, stream_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, f"stream:{stream_url}", None))  # 使用特殊前缀标记为流式播放
        try:
            await self._add_queue(guild_id, f"[流式播放] {stream_url}", ctx)
        except Exception as e:
            await _send_error_to_voice_channel(f"❌ 流式播放时发生错误: {str(e)}", ctx)

    async def join_and_play_bilibili(self, voice_channel: discord.VoiceChannel, bvid: str, ctx: discord.ApplicationContext, page=0):
        v = video.Video(bvid=bvid)
        download_url = await v.get_download_url(page)
        d = video.VideoDownloadURLDataDetecter(download_url)
        info = await v.get_info()
        a = d.detect_best_streams()
        audio_url = a[1].url

        embed = discord.Embed(title=info["title"], description=info["desc"])
        embed.set_thumbnail(url=info["pic"])
        embed.add_field(name="发布时间", value=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info["pubdate"])), inline=False)
        embed.add_field(name="播放量", value=info["stat"]["view"], inline=True)
        embed.add_field(name="投币数", value=info["stat"]["coin"], inline=True)
        embed.add_field(name="收藏数", value=info["stat"]["favorite"], inline=True)
        embed.set_author(name=info["owner"]["name"], icon_url=info["owner"]["face"])
        otto_respond = "接下来播放："+info["title"]
        await ctx.respond(otto_respond, embed=embed)

        if audio_url is None:
            raise Exception("无法解析该视频的音频流")
        await self.join_and_speak(voice_channel, otto_respond, str(os.getenv("SPEAK_API_URL")), ctx)
        await self.join_and_stream_url(voice_channel, audio_url, ctx)

    async def _player_loop(self, guild_id: int, ctx: discord.ApplicationContext):
        queue = self.queues[guild_id]

        while not queue.empty():
            voice_channel, content, speak_api_url = await queue.get()
            try:
                if speak_api_url:  # TTS 播放
                    await self._play_once(voice_channel, content, speak_api_url, ctx)
                elif content.startswith("stream:"):  # 流式播放 URL
                    await self._stream_url(voice_channel, content.replace("stream:", "", 1), ctx)
                else:  # 默认行为：先下载再播放
                    await self._play_url(voice_channel, content, ctx)

            except Exception as e:
                self.log(guild_id, f"❌ 播放失败：{e}")
                await _send_error_to_voice_channel(f"❌ 播放时发生错误: {str(e)}", ctx)

    async def _play_once(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        self.log(guild_id, "🌐 请求语音合成")

        audio_data = await self._fetch_tts_audio(speak_api_url, message)
        if audio_data is None:
            self.log(guild_id, "❌ 获取语音数据失败，跳过播放")
            raise Exception("❌ 获取语音数据失败，跳过播放")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_data)
            temp_path = tmp_file.name

        self.log(guild_id, f"📁 写入临时文件完成：{temp_path}")

        vc = await self._prepare_voice_client(voice_channel, guild_id)
        if vc is None:
            os.remove(temp_path)
            return

        await self._play_audio_file(guild_id, vc, temp_path, message, ctx)

    async def _play_url(self, voice_channel: discord.VoiceChannel, audio_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        self.log(guild_id, f"🌐 请求音频下载：{audio_url}")

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(audio_url) as resp:
                    if resp.status != 200:
                        error_message = f"❌ 下载失败：HTTP {resp.status}"
                        self.log(guild_id, error_message)
                        raise Exception(f"HTTP {resp.status}")
                    audio_data = await resp.read()
        except Exception as e:
            error_message = f"❌ 下载音频时发生错误: {str(e)}"
            self.log(guild_id, error_message)
            raise e

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_data)
            temp_path = tmp_file.name

        self.log(guild_id, f"📁 写入临时文件完成：{temp_path}")

        vc = await self._prepare_voice_client(voice_channel, guild_id)
        if vc is None:
            os.remove(temp_path)
            return

        await self._play_audio_file(guild_id, vc, temp_path, f"URL: {audio_url}", ctx)

    async def _stream_url(self, voice_channel: discord.VoiceChannel, audio_url: str, ctx: discord.ApplicationContext):
        guild_id = voice_channel.guild.id
        self.log(guild_id, f"📡 正在流式播放：{audio_url}")

        vc = await self._prepare_voice_client(voice_channel, guild_id)
        if vc is None:
            await _send_error_to_voice_channel("❌ 无法连接语音频道", ctx)
            return

        finished = asyncio.Event()

        def after_play(error):
            if error:
                self.log(guild_id, f"❌ 流式播放回调错误：{error}")
            else:
                self.log(guild_id, "🎵 流式播放完成")
            self.bot.loop.call_soon_threadsafe(finished.set)

        try:
            self.current_voice_clients[guild_id] = vc

            if vc.is_playing():
                self.log(guild_id, "⏳ 等待当前播放完成")
                wait_event = asyncio.Event()
                def temp_after(): wait_event.set()
                vc._player.after = temp_after
                await wait_event.wait()

            audio_source = discord.FFmpegPCMAudio(audio_url, executable=self.ffmpeg_path, before_options="-headers 'Referer: https://www.bilibili.com\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")
            vc.play(audio_source, after=after_play)
            await finished.wait()

        except Exception as e:
            self.log(guild_id, f"❌ 流式播放异常：{e}")
            await _send_error_to_voice_channel(f"❌ 流式播放异常：{e}", ctx)
        finally:
            self.current_voice_clients.pop(guild_id, None)

        if self.queues[guild_id].empty() and vc.is_connected():
            self.log(guild_id, "🔇 队列播放完毕，断开语音连接")
            await vc.disconnect()

    async def _play_audio_file(self, guild_id: int, vc: discord.VoiceClient, temp_path: str, description: str, ctx: discord.ApplicationContext):
        self.log(guild_id, f"🎧 准备播放：{description}")
        finished = asyncio.Event()

        def after_play(error):
            if error:
                self.log(guild_id, f"❌ 播放回调报错：{error}")
            else:
                self.log(guild_id, "🎵 播放完成")

            # 线程安全地设置事件
            self.bot.loop.call_soon_threadsafe(finished.set)

        try:
            self.current_voice_clients[guild_id] = vc

            # 如果正在播放，等待其完成
            if vc.is_playing():
                self.log(guild_id, f"⏳ 正在等待当前音频播放结束...")
                wait_event = asyncio.Event()

                def temp_after():
                    wait_event.set()

                vc._player.after = temp_after
                await wait_event.wait()

            audio_source = discord.FFmpegPCMAudio(temp_path, executable=self.ffmpeg_path)
            vc.play(audio_source, after=after_play)
            await finished.wait()

        except Exception as e:
            self.log(guild_id, f"❌ 播放异常：{e}")
            await _send_error_to_voice_channel(f"❌ 播放异常：{e}", ctx)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            self.current_voice_clients.pop(guild_id, None)

        if self.queues[guild_id].empty() and vc.is_connected():
            self.log(guild_id, "🔇 队列播放完毕，断开语音连接")
            await vc.disconnect()

    async def _prepare_voice_client(self, voice_channel: discord.VoiceChannel, guild_id: int):
        vc: discord.VoiceClient = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)

        if vc and vc.is_connected():
            if vc.channel.id == voice_channel.id:
                self.log(guild_id, f"🔗 已在目标语音频道，直接播放")
                return vc
            else:
                self.log(guild_id, f"🔁 已连接到其他语音频道（{vc.channel}），准备切换")
                await vc.disconnect(force=True)

        return await self._safe_connect(voice_channel, guild_id)

    async def _safe_connect(self, voice_channel: discord.VoiceChannel, guild_id: int, retries: int = 3, delay: float = 2.0):
        existing_vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)

        # ✅ 如果已连接到目标频道，直接复用
        if existing_vc and existing_vc.is_connected() and existing_vc.channel.id == voice_channel.id:
            self.log(guild_id, f"🔗 已连接到目标频道，复用连接")
            return existing_vc

        # ✅ 如果连接在其他频道，先断开
        if existing_vc and existing_vc.is_connected():
            self.log(guild_id, f"🔁 正在断开已有频道：{existing_vc.channel}")
            await existing_vc.disconnect(force=True)

        for attempt in range(1, retries + 1):
            try:
                self.log(guild_id, f"🔌 第 {attempt} 次尝试连接语音频道...")
                vc = await asyncio.wait_for(voice_channel.connect(), timeout=10)
                self.log(guild_id, "✅ 成功连接语音频道")
                return vc

            except asyncio.TimeoutError:
                self.log(guild_id, f"⏰ 第 {attempt} 次连接超时")

            except discord.ClientException as e:
                msg = str(e)
                self.log(guild_id, f"⚠️ 第 {attempt} 次连接失败：{msg}")
                existing_vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)
                if existing_vc:
                    self.log(guild_id, f"⚠️ 检测到连接残留，尝试强制断开")
                    try:
                        await existing_vc.disconnect(force=True)
                    except Exception as disconnect_err:
                        self.log(guild_id, f"⚠️ 强制断开失败：{disconnect_err}")

            await asyncio.sleep(delay)

        self.log(guild_id, "❌ 多次尝试仍无法连接语音频道，跳过播放")
        raise Exception("❌ 多次尝试仍无法连接语音频道，跳过播放")

    async def _fetch_tts_audio(self, url: str, message: str):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json={"message": message}) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        self.log(0, f"❌ TTS 接口响应错误: {resp.status}")
                        raise Exception(f"❌ TTS 接口响应错误: {resp.status}")
        except Exception as e:
            self.log(0, f"❌ TTS 请求异常：{e}")
            raise e

    async def skip(self, guild_id: int):
        vc = self.current_voice_clients.get(guild_id)
        if vc and vc.is_playing():
            vc.stop()
            self.log(guild_id, "⏭️ 手动跳过当前播放")
        else:
            self.log(guild_id, "⚠️ 当前没有播放中的音频")
            raise Exception("当前没有播放中的音频")
