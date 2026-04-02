# Reddit Bot

A simple Python Reddit bot built with [PRAW](https://praw.readthedocs.io/).  
It monitors one or more subreddits and automatically replies to comments that contain a configurable trigger keyword (default: `!hello`).

---

## Features

- Streams new comments in real time using PRAW's comment stream
- Replies when a configurable keyword is detected (e.g. `!hello`)
- Skips its own comments to avoid infinite loops
- Skips comments it has already replied to (no duplicate replies)
- Handles Reddit API errors gracefully and retries automatically
- Fully configurable via environment variables or a `.env` file

---

## Quick start

### 1 — Create a Reddit app

1. Log in to Reddit and go to <https://www.reddit.com/prefs/apps>
2. Click **"create another app …"**
3. Choose **script**, give it a name, and set the redirect URI to `http://localhost:8080`
4. Note the **client ID** (under the app name) and **client secret**

### 2 — Configure the bot

```bash
cp .env.example .env
# Open .env and fill in your credentials
```

| Variable | Description | Default |
|---|---|---|
| `REDDIT_CLIENT_ID` | App client ID (required) | — |
| `REDDIT_CLIENT_SECRET` | App client secret (required) | — |
| `REDDIT_USERNAME` | Reddit account username (required) | — |
| `REDDIT_PASSWORD` | Reddit account password (required) | — |
| `REDDIT_USER_AGENT` | User-agent string | `reddit-bot/1.0 by u/<username>` |
| `SUBREDDITS` | Comma-separated subreddits to monitor | `testingground4bots` |
| `TRIGGER_KEYWORD` | Keyword that triggers a reply | `!hello` |
| `REPLY_MESSAGE` | Message the bot posts as a reply | *(see .env.example)* |
| `POLL_INTERVAL` | Seconds to wait after a recoverable error | `30` |

### 3 — Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4 — Run the bot

```bash
python reddit_bot.py
```

The bot will log activity to stdout.  Press **Ctrl+C** to stop it.

---

## Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

---

## Project structure

```
.
├── .env.example      # Template for credentials / settings
├── config.py         # Loads configuration from environment / .env
├── reddit_bot.py     # Main bot logic
├── requirements.txt  # Python dependencies
└── tests/
    └── test_reddit_bot.py  # Unit tests (no live Reddit connection needed)
```

---

## Notes

- The Reddit account used by the bot must have a verified email address.
- For subreddits that require a certain account age or karma to post, the bot may be silently blocked.  Use `r/testingground4bots` for initial testing.
- Never commit your `.env` file — it is listed in `.gitignore`.
