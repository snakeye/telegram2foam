import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("telegram2foam")


@dataclass
class BotConfig:
    token: str
    repo_root: Path
    notes_dir: Path
    local_tz: ZoneInfo

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

        repo_root = Path(os.getenv("REPO_ROOT", Path.cwd()))
        notes_dir_env = os.getenv("DAILY_NOTES_DIR", "notes")
        notes_dir = repo_root / notes_dir_env if notes_dir_env else repo_root

        tz_name = os.getenv("LOCAL_TIMEZONE")
        local_tz = ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
        if local_tz is None:
            local_tz = ZoneInfo("UTC")

        return cls(
            token=token,
            repo_root=repo_root,
            notes_dir=notes_dir,
            local_tz=local_tz,
        )


def ensure_directories(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def format_entry(text: str, author: Optional[str], local_time: datetime) -> str:
    clean_text = text.strip()
    author_label = f"{author}: " if author else ""
    body = clean_text.replace("\n", "\n  ")
    return f"- [{local_time:%H:%M}] {author_label}{body}\n"


def run_git(repo_root: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("git %s failed: %s", " ".join(args), result.stdout + result.stderr)
        return False

    if result.stdout.strip():
        logger.info(result.stdout.strip())
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    config: BotConfig = context.bot_data["config"]

    local_time = message.date.astimezone(config.local_tz)
    date_str = local_time.strftime("%Y-%m-%d")
    note_path = config.notes_dir / f"{date_str}.md"

    try:
        if not run_git(config.repo_root, "pull", "--rebase"):
            return

        ensure_directories(note_path)

        author = None
        if message.from_user:
            parts = [
                message.from_user.full_name or "",
                f"@{message.from_user.username}" if message.from_user.username else "",
            ]
            author = " ".join(part for part in parts if part).strip() or None

        with note_path.open("a", encoding="utf-8") as fh:
            fh.write(format_entry(message.text, author, local_time))

        note_for_git = note_path
        if note_path.is_relative_to(config.repo_root):
            note_for_git = note_path.relative_to(config.repo_root)

        if not run_git(config.repo_root, "add", str(note_for_git)):
            return

        commit_msg = f"note: telegram {local_time:%Y-%m-%d %H:%M}"
        if not run_git(config.repo_root, "commit", "-m", commit_msg):
            return

        if not run_git(config.repo_root, "push"):
            logger.error("git push failed")
    except Exception:
        logger.exception("Failed to process message")


def main() -> None:
    load_dotenv()
    config = BotConfig.from_env()
    logger.info("Starting bot; writing notes to %s", config.notes_dir)

    application = ApplicationBuilder().token(config.token).build()
    application.bot_data["config"] = config
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
