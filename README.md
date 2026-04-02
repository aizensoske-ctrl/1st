# 1st

Simple Reddit bot in Python.

## Setup

1. Create a Reddit app and collect credentials.
2. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Set environment variables:

```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USERNAME="your_username"
export REDDIT_PASSWORD="your_password"
export REDDIT_USER_AGENT="1st-reddit-bot/0.1 by your_username"
export REDDIT_SUBREDDIT="test"
export REDDIT_TRIGGER="!ping"
export REDDIT_REPLY="pong"
```

## Run

```bash
python bot.py
```

The bot watches comments in the configured subreddit and replies when the trigger text appears.
