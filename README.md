# ottocord
[![Discord Bot Invite](https://img.shields.io/badge/Invite_My_Bot_to_Your_Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1358306377159675940&permissions=2150648320&integration_type=0&scope=bot+applications.commands)
</br>棍哥点歌机器人

## 功能
- [x] bilibili 视频搜索和播放（只播放音频）
- [x] bilibili 热门视频获取
- [x] 网易云音乐搜索和播放
- [x] 棍哥深情朗诵
- [x] 直接播放音乐文件 url
- [x] 直接播放流式音频 url
- [x] 多服务器独立播放队列支持

## 使用说明

### 搜索 bilibili 视频
```shell
/search_bilibili keywords:<关键词> page:[页码]
```

### 搜索网易云音乐
```shell
/search_netease keywords:<关键词> page:[页码]
```

### 获取 bilibili 热门视频
```shell
/get_bilibili_popular tag:[标签名称] page:[页码] page_size:[每页数量] days:[时间范围]
```
- `tag`: 可选，标签名称（如编程、音乐等）
- `page`: 可选，页码，默认为1
- `page_size`: 可选，每页数量（1-50），默认为20
- `days`: 可选，时间范围（1=当天，7=本周，30=本月）

### 播放 bilibili 视频
```shell
/play_bilibili bvid:<BV号> page:[分P号]
```

### 播放网易云音乐
```shell
/play_netease id:<歌曲id>
```

### 棍哥深情朗诵
```shell
/say message:<内容>
```

### 播放音频文件
```shell
/play_url url:<音频文件url>
```

### 播放流式音频
```shell
/stream_url url:<流式音频url>
```

### 跳过当前播放音频/终止流式音频播放
```shell
/skip
```

## 部署

### 直接部署

#### 克隆仓库
```shell
git clone https://github.com/gujial/ottocord.git
```

#### 部署 ottoTTS_server
参考[ottoTTS_server](https://github.com/gujial/ottoTTS_server?tab=readme-ov-file#%E9%83%A8%E7%BD%B2)

#### 部署 musix_server
参考[musix_server](https://github.com/gujial/musix_server)（用于解析 bilibili 和网易云音乐）

#### 创建 .env 文件
文件内容如下
```.dotenv
TOKEN=<机器人的token>
SPEAK_API_URL=<部署的 ottoTTS_server 的 url>
MUSIX_API_URL=<部署的 musix_server 的 url>
```

#### 运行
```shell
python ./otto.py
```

### 使用 docker

#### 拉取镜像
```bash
docker pull gujial114514/ottocord:latest
```

#### 部署 ottoTTS_server 和 musix_server
参考[ottoTTS_server](https://github.com/gujial/ottoTTS_server) 和 [musix_server](https://github.com/gujial/musix_server)

#### 运行容器
带环境变量运行：
```bash
docker run -d --name ottocord \
  -e "TOKEN=<机器人的token>" \
  -e "SPEAK_API_URL=<部署的 ottoTTS_server 的 url>" \
  -e "MUSIX_API_URL=<部署的 musix_server 的 url>" \
  gujial114514/ottocord:latest
```

### 使用 Docker Compose (推荐)

#### 克隆仓库
```bash
git clone https://github.com/gujial/ottocord.git
cd ottocord
```

#### 创建 .env 文件
在项目根目录创建 `.env` 文件，内容如下：
```.env
# Discord Bot Token (必需)
TOKEN=你的Discord机器人Token

# 网易云音乐凭据 (可选，用于提升音质和解锁VIP歌曲)
NETEASE_MUSIC_U=你的网易云MUSIC_U

# Bilibili 凭据 (可选，用于解锁高清画质和会员视频)
BILIBILI_SESSDATA=你的BilibiliSESSDATA
BILIBILI_BILI_JCT=你的Bilibili_jct
BILIBILI_BUVID3=你的BilibiliVID3

# API跨域设置 (可选，默认为*)
ALLOWED_ORIGINS=*
```

#### 启动服务
```bash
docker-compose up -d
```

#### 查看日志
```bash
docker-compose logs -f ottocord
```

#### 停止服务
```bash
docker-compose down
```

## 环境变量说明

| 变量名 | 必需 | 说明 | 默认值 |
|--------|------|------|--------|
| `TOKEN` | ✅ | Discord Bot Token | - |
| `SPEAK_API_URL` | ✅* | TTS 服务地址 | `http://ottoTTS_server:8080/speak` (Docker Compose) |
| `MUSIX_API_URL` | ✅* | 音乐解析服务地址 | `http://musix-api:8000/api/v1` (Docker Compose) |
| `NETEASE_MUSIC_U` | ❌ | 网易云音乐 Cookie (提升音质) | - |
| `BILIBILI_SESSDATA` | ❌ | Bilibili Cookie (解锁高清/会员) | - |
| `BILIBILI_BILI_JCT` | ❌ | Bilibili Cookie | - |
| `BILIBILI_BUVID3` | ❌ | Bilibili Cookie | - |
| `ALLOWED_ORIGINS` | ❌ | API 跨域设置 | `*` |

**注意**: 使用 Docker Compose 部署时，`SPEAK_API_URL` 和 `MUSIX_API_URL` 会自动配置为容器内部地址，无需手动设置。

## 相关项目
- [ottoTTS_server](https://github.com/gujial/ottoTTS_server) - 棍哥语音合成服务
- [musix_server](https://github.com/gujial/musix_server) - 音乐解析服务

## 使用到的开源库
- [pycord](https://github.com/Pycord-Development/pycord/) - Discord Bot 框架
- [aiohttp](https://github.com/aio-libs/aiohttp) - 异步 HTTP 客户端