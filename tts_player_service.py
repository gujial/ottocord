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

    def log(self, guild_id: int, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [GUILD {guild_id}] {message}")

    async def join_and_speak(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str):
        guild_id = voice_channel.guild.id
        queue = self.queues[guild_id]

        await queue.put((voice_channel, message, speak_api_url))
        self.log(guild_id, f"✅ 加入播放队列：{message}")

        if guild_id not in self.playing_tasks or self.playing_tasks[guild_id].done():
            self.playing_tasks[guild_id] = asyncio.create_task(self._player_loop(guild_id))

    async def _player_loop(self, guild_id: int):
        queue = self.queues[guild_id]

        while not queue.empty():
            voice_channel, message, speak_api_url = await queue.get()
            try:
                await self._play_once(voice_channel, message, speak_api_url)
            except Exception as e:
                self.log(guild_id, f"❌ 播放失败：{e}")

    async def _play_once(self, voice_channel: discord.VoiceChannel, message: str, speak_api_url: str):
        guild_id = voice_channel.guild.id
        self.log(guild_id, "🌐 请求语音合成")

        audio_data = await self._fetch_tts_audio(speak_api_url, message)
        if audio_data is None:
            self.log(guild_id, "❌ 获取语音数据失败，跳过播放")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_data)
            temp_path = tmp_file.name

        self.log(guild_id, f"📁 写入临时文件完成：{temp_path}")

        # 尝试复用连接
        vc: discord.VoiceClient = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)

        if vc and vc.is_connected():
            if vc.channel.id == voice_channel.id:
                self.log(guild_id, f"🔗 已在目标语音频道，直接播放")
            else:
                self.log(guild_id, f"🔁 已连接到其他语音频道（{vc.channel}），准备切换")
                await vc.disconnect(force=True)
                vc = await self._safe_connect(voice_channel, guild_id)
        else:
            vc = await self._safe_connect(voice_channel, guild_id)

        if vc is None:
            self.log(guild_id, "❌ 多次尝试仍无法连接语音频道，跳过播放")
            os.remove(temp_path)
            return

        # 播放音频
        self.log(guild_id, f"🎧 准备播放：{message}")
        finished = asyncio.Event()

        def after_play(error):
            if error:
                self.log(guild_id, f"❌ 播放回调报错：{error}")
            else:
                self.log(guild_id, "🎵 播放完成")
            finished.set()

        try:
            audio_source = discord.FFmpegPCMAudio(temp_path, executable=self.ffmpeg_path)
            vc.play(audio_source, after=after_play)
            await finished.wait()
        except Exception as e:
            self.log(guild_id, f"❌ 播放异常：{e}")
        finally:
            os.remove(temp_path)

        # 如果播放队列为空，自动断开连接
        if self.queues[guild_id].empty() and vc.is_connected():
            self.log(guild_id, "🔇 队列播放完毕，断开语音连接")
            await vc.disconnect()

    async def _safe_connect(self, voice_channel: discord.VoiceChannel, guild_id: int, retries: int = 3,
                            delay: float = 2.0):
        existing_vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)

        # ✅ 如果已连接到目标频道，复用
        if existing_vc and existing_vc.is_connected() and existing_vc.channel.id == voice_channel.id:
            self.log(guild_id, f"🔗 已连接到目标频道，复用连接")
            return existing_vc

        # ✅ 如果连接在其他频道，先断开
        if existing_vc and existing_vc.is_connected():
            self.log(guild_id, f"🔁 正在断开已有频道：{existing_vc.channel}")
            await existing_vc.disconnect(force=True)

        timed_out_once = False

        for attempt in range(1, retries + 1):
            try:
                self.log(guild_id, f"🔌 第 {attempt} 次尝试连接语音频道...")
                vc = await asyncio.wait_for(voice_channel.connect(), timeout=10)
                self.log(guild_id, "✅ 成功连接语音频道")
                return vc
            except asyncio.TimeoutError:
                timed_out_once = True
                self.log(guild_id, f"⏰ 第 {attempt} 次连接超时")
            except discord.ClientException as e:
                if "Already connected" in str(e) and timed_out_once:
                    self.log(guild_id, f"⚠️ 第 {attempt} 次连接失败但检测到已连接，尝试复用连接")
                    existing_vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)
                    if existing_vc and existing_vc.is_connected():
                        return existing_vc
                self.log(guild_id, f"⚠️ 第 {attempt} 次连接失败：{e}")
            await asyncio.sleep(delay)

        return None

    async def _fetch_tts_audio(self, url: str, message: str):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json={"message": message}) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        self.log(0, f"❌ TTS 接口响应错误: {resp.status}")
                        return None
        except Exception as e:
            self.log(0, f"❌ TTS 请求异常：{e}")
            return None
