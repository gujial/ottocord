import discord
import aiohttp
import asyncio
import tempfile
import os
import datetime
from collections import defaultdict


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

    async def _add_queue(self, guild_id, message):
        self.log(guild_id, f"✅ 加入播放队列：{message}")

        try:
            if guild_id not in self.playing_tasks or self.playing_tasks[guild_id].done():
                task = asyncio.create_task(self._player_loop(guild_id))
                await task
                self.playing_tasks[guild_id] = task
        except Exception as e:
            raise e

    async def join_and_speak(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, message, speak_api_url))
        try:
            await self._add_queue(guild_id, message)
        except Exception as e:
            raise e

    async def join_and_play_url(self, voice_channel: discord.VoiceChannel, audio_url: str):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, audio_url, None))  # None 表示是 URL 播放
        try:
            await self._add_queue(guild_id, audio_url)
        except Exception as e:
            raise e

    async def _player_loop(self, guild_id: int):
        queue = self.queues[guild_id]

        while not queue.empty():
            voice_channel, content, speak_api_url = await queue.get()
            try:
                if speak_api_url:  # TTS
                    await self._play_once(voice_channel, content, speak_api_url)
                else:  # URL
                    await self._play_url(voice_channel, content)
            except Exception as e:
                self.log(guild_id, f"❌ 播放失败：{e}")
                raise e

    async def _play_once(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str):
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

        await self._play_audio_file(guild_id, vc, temp_path, message)

    async def _play_url(self, voice_channel: discord.VoiceChannel, audio_url: str):
        guild_id = voice_channel.guild.id
        self.log(guild_id, f"🌐 请求音频下载：{audio_url}")

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(audio_url) as resp:
                    if resp.status != 200:
                        self.log(guild_id, f"❌ 下载失败：HTTP {resp.status}")
                        raise Exception(f"HTTP {resp.status}")
                    audio_data = await resp.read()
        except Exception as e:
            self.log(guild_id, f"❌ 下载音频异常：{e}")
            raise e

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_data)
            temp_path = tmp_file.name

        self.log(guild_id, f"📁 写入临时文件完成：{temp_path}")

        vc = await self._prepare_voice_client(voice_channel, guild_id)
        if vc is None:
            os.remove(temp_path)
            return

        await self._play_audio_file(guild_id, vc, temp_path, f"URL: {audio_url}")

    async def _play_audio_file(self, guild_id: int, vc: discord.VoiceClient, temp_path: str, description: str):
        self.log(guild_id, f"🎧 准备播放：{description}")
        finished = asyncio.Event()

        def after_play(error):
            if error:
                self.log(guild_id, f"❌ 播放回调报错：{error}")
            else:
                self.log(guild_id, "🎵 播放完成")
            finished.set()

        try:
            self.current_voice_clients[guild_id] = vc
            audio_source = discord.FFmpegPCMAudio(temp_path, executable=self.ffmpeg_path)
            vc.play(audio_source, after=after_play)
            await finished.wait()
        except Exception as e:
            self.log(guild_id, f"❌ 播放异常：{e}")
        finally:
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

                if "Already connected" in msg and attempt >= 2:
                    # 第二次或之后，如果提示已连接，则复用现有连接
                    existing_vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)
                    if existing_vc and existing_vc.is_connected():
                        self.log(guild_id, f"✅ 检测到已连接语音频道，尝试复用现有连接")
                        return existing_vc

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
