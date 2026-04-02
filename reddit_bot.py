"""Reddit bot — monitors subreddits and replies to a configurable trigger keyword.

Usage
-----
1. Copy .env.example to .env and fill in your Reddit API credentials.
2. Install dependencies:  pip install -r requirements.txt
3. Run the bot:           python reddit_bot.py

The bot will stream new comments from the configured subreddits.  When it
finds a comment that contains the trigger keyword (default: ``!hello``) and
has not already been replied to, it posts a reply and logs the action.
"""

import logging
import time

import praw
import prawcore

import config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bot helpers
# ---------------------------------------------------------------------------

def create_reddit_client() -> praw.Reddit:
    """Create and return an authenticated PRAW Reddit client."""
    reddit = praw.Reddit(
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        username=config.USERNAME,
        password=config.PASSWORD,
        user_agent=config.USER_AGENT,
    )
    log.info("Authenticated as u/%s", reddit.user.me())
    return reddit


def already_replied(comment: praw.models.Comment, bot_username: str) -> bool:
    """Return True if the bot has already replied to *comment*."""
    comment.refresh()
    for reply in comment.replies:
        if reply.author and reply.author.name.lower() == bot_username.lower():
            return True
    return False


def handle_comment(comment: praw.models.Comment, bot_username: str) -> None:
    """Reply to *comment* if it contains the trigger keyword."""
    body = comment.body.lower()
    if config.TRIGGER_KEYWORD not in body:
        return

    # Skip the bot's own comments
    if comment.author and comment.author.name.lower() == bot_username.lower():
        return

    if already_replied(comment, bot_username):
        log.debug("Already replied to comment %s — skipping.", comment.id)
        return

    comment.reply(config.REPLY_MESSAGE)
    log.info(
        "Replied to comment %s by u/%s in r/%s",
        comment.id,
        comment.author,
        comment.subreddit,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(reddit: praw.Reddit) -> None:
    """Stream comments from the configured subreddits and handle triggers."""
    bot_username: str = reddit.user.me().name
    subreddit_str = "+".join(config.SUBREDDITS)
    subreddit = reddit.subreddit(subreddit_str)

    log.info(
        "Monitoring r/%s for keyword '%s' …",
        subreddit_str,
        config.TRIGGER_KEYWORD,
    )

    while True:
        try:
            for comment in subreddit.stream.comments(skip_existing=True):
                handle_comment(comment, bot_username)
        except prawcore.exceptions.ServerError as exc:
            log.warning("Reddit server error: %s — retrying in %ds …", exc, config.POLL_INTERVAL)
            time.sleep(config.POLL_INTERVAL)
        except prawcore.exceptions.ResponseException as exc:
            log.warning("Reddit response error: %s — retrying in %ds …", exc, config.POLL_INTERVAL)
            time.sleep(config.POLL_INTERVAL)
        except KeyboardInterrupt:
            log.info("Shutting down.")
            break


if __name__ == "__main__":
    reddit_client = create_reddit_client()
    run(reddit_client)
