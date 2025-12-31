# 使用官方 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装 uv (极速 Python 包管理器)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖文件
COPY pyproject.toml .
# 如果有 uv.lock 也复制 (假设可能没有，先忽略)
# COPY uv.lock .

# 安装依赖 (不创建 venv，直接安装到系统)
RUN uv pip install --system -r pyproject.toml

# 复制源代码
COPY src ./src
COPY .env .env

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
