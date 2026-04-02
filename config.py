"""Configuration loader for the Reddit bot.

Reads settings from environment variables or a .env file.
Copy .env.example to .env and fill in your credentials before running.
"""

import os

from dotenv import load_dotenv

# Load .env file if present (silently ignored when absent)
load_dotenv()


def _require(key: str) -> str:
    """Return the value of *key* or raise an error if it is missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


# Reddit API credentials
CLIENT_ID: str = _require("REDDIT_CLIENT_ID")
CLIENT_SECRET: str = _require("REDDIT_CLIENT_SECRET")
USERNAME: str = _require("REDDIT_USERNAME")
PASSWORD: str = _require("REDDIT_PASSWORD")
USER_AGENT: str = os.getenv(
    "REDDIT_USER_AGENT", f"reddit-bot/1.0 by u/{os.getenv('REDDIT_USERNAME', 'unknown')}"
)

# Bot behaviour
SUBREDDITS: list[str] = [
    s.strip()
    for s in os.getenv("SUBREDDITS", "testingground4bots").split(",")
    if s.strip()
]
TRIGGER_KEYWORD: str = os.getenv("TRIGGER_KEYWORD", "!hello").lower()
REPLY_MESSAGE: str = os.getenv(
    "REPLY_MESSAGE",
    "Hello! I am a Reddit bot. Type !hello to say hi to me.",
)
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "30"))
