#!/usr/bin/env python3
import os
import time

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
        user_agent=os.getenv("REDDIT_USER_AGENT", "1st-reddit-bot/0.1 by script"),
    )

    subreddit_name = os.getenv("REDDIT_SUBREDDIT", "test")
    trigger = os.getenv("REDDIT_TRIGGER", "!ping").lower()
    reply_text = os.getenv("REDDIT_REPLY", "pong")
    poll_seconds = int(os.getenv("POLL_SECONDS", "30"))

    print(f"Bot started for r/{subreddit_name}. Trigger: {trigger}")

    replied_ids: set[str] = set()

    while True:
        try:
            for comment in reddit.subreddit(subreddit_name).stream.comments(skip_existing=True):
                body = (comment.body or "").strip().lower()
                if trigger in body and comment.id not in replied_ids and str(comment.author) != reddit.user.me().name:
                    comment.reply(reply_text)
                    replied_ids.add(comment.id)
                    print(f"Replied to comment {comment.id}")
        except Exception as exc:
            print(f"Error: {exc}. Retrying in {poll_seconds}s")
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
