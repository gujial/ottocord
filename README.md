# ottocord
[![Discord Bot Invite](https://img.shields.io/badge/Invite_My_Bot_to_Your_Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1358306377159675940&permissions=2150648320&integration_type=0&scope=bot+applications.commands)
</br>棍哥点歌机器人

## 功能
- [x] bilibili 视频搜索和播放（只播放音频）
- [x] 网易云音乐搜索和播放
- [x] 棍哥深情朗诵
- [x] 直接播放音乐文件 url
- [x] 直接播放流式音频 url

## 使用说明

### 搜索 bilibili 视频
```shell
/bilibili_search keywords:<关键词> page:[页码]
```

### 搜索网易云音乐
```shell
/netease_search keywords:<关键词> page:[页码]
```

### 播放 bilibili 视频
```shell
/play_bilibili bvid:<BV号>
```

### 播放网易云音乐
```shell
/play_netease id:<歌曲id>
```

### 棍哥深情朗诵
```shell
/say message<内容>
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

#### 创建 .env 文件
文件内容如下
```.dotenv
TOKEN=<机器人的token>
SPEAK_API_URL=<上一步中部署的 ottoTTS_server 的 url>
SESSDATA=[可选 bilibili coockie 数据]
BILI_JCT=[可选 bilibili coockie 数据]
BUVID3=[可选 bilibili coockie 数据]
DEDEUSERID=[可选 bilibili coockie 数据]
AC_TIME_VALUE=[可选 bilibili coockie 数据]
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

#### 部署 ottoTTS_server
参考[ottoTTS_server](https://github.com/gujial/ottoTTS_server)

#### 运行容器
带环境变量运行：
```bash
docker run -d --name [容器名] \
  -e "TOKEN=<机器人的token>" \
  -e "SPEAK_API_URL=<上一步中部署的 ottoTTS_server 的 url>" \
  gujial114514/ottocord:latest
```
环境变量与上一种部署方法中的相同

## 使用到的开源库
- [bilibili-api](https://github.com/nemo2011/bilibili-api)
- [pyncm](https://github.com/mos9527/pyncm)
- [pycord](https://github.com/Pycord-Development/pycord/)