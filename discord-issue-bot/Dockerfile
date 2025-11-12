FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY . .

WORKDIR /workspace/discord-issue-bot
RUN uv sync

CMD ["uv", "run", "bot.py"]
