#!/usr/bin/env python3
import os
import time
from collections import deque

import praw


def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    reddit = praw.Reddit(
        client_id=get_env("REDDIT_CLIENT_ID"),
        client_secret=get_env("REDDIT_CLIENT_SECRET"),
        username=get_env("REDDIT_USERNAME"),
        password=get_env("REDDIT_PASSWORD"),
        user_agent=get_env("REDDIT_USER_AGENT"),
    )

    subreddit_name = os.getenv("REDDIT_SUBREDDIT", "test")
    trigger = os.getenv("REDDIT_TRIGGER", "!ping").lower()
    reply_text = os.getenv("REDDIT_REPLY", "pong")
    retry_seconds = int(os.getenv("RETRY_SECONDS", "30"))
    replied_cache_size = int(os.getenv("REPLIED_CACHE_SIZE", "10000"))
    print(f"Bot started for r/{subreddit_name}. Trigger: {trigger}")

    replied_ids: set[str] = set()
    replied_order: deque[str] = deque()
    bot_username = ""

    while True:
        try:
            if not bot_username:
                bot_username = reddit.user.me().name
            for comment in reddit.subreddit(subreddit_name).stream.comments(skip_existing=True):
                words = comment.body.strip().lower().split()
                if trigger in words and comment.id not in replied_ids and str(comment.author) != bot_username:
                    comment.reply(reply_text)
                    replied_ids.add(comment.id)
                    replied_order.append(comment.id)
                    if len(replied_order) > replied_cache_size:
                        oldest_id = replied_order.popleft()
                        replied_ids.discard(oldest_id)
                    print(f"Replied to comment {comment.id}")
        except Exception as exc:
            print(f"Error ({type(exc).__name__}): {exc}. Retrying in {retry_seconds}s")
            time.sleep(retry_seconds)


if __name__ == "__main__":
    main()
