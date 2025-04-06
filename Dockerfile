# 使用官方 Python 镜像
FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /

# 复制项目文件到容器中
COPY . .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 运行程序
CMD ["python", "otto.py"]
