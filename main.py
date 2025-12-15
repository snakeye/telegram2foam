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


def load_template(path: Path, default: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Template %s not found, using default", path)
        return default
    except Exception:
        logger.exception("Failed to read template %s, using default", path)
        return default


@dataclass
class BotConfig:
    token: str
    repo_root: Path
    journal_root: Path
    local_tz: ZoneInfo
    git_user_name: str
    git_user_email: str
    note_template: str
    message_template: str
    poll_interval: float

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

        repo_root = Path(os.getenv("REPO_ROOT", Path.cwd()))
        journal_root = repo_root / "journal"

        git_user_name = os.getenv("GIT_USER_NAME") or os.getenv("GIT_AUTHOR_NAME")
        git_user_email = os.getenv("GIT_USER_EMAIL") or os.getenv("GIT_AUTHOR_EMAIL")
        if not git_user_name or not git_user_email:
            raise RuntimeError(
                "Missing git identity (GIT_USER_NAME and GIT_USER_EMAIL)"
            )

        templates_root = Path(os.getenv("TEMPLATES_ROOT", Path.cwd()))
        note_template_path = Path(
            os.getenv("NOTE_TEMPLATE_PATH", templates_root / "note_template.md")
        )
        message_template_path = Path(
            os.getenv("MESSAGE_TEMPLATE_PATH", templates_root / "message_template.md")
        )

        note_template = load_template(
            note_template_path,
            default="---\ntags: []\n---\n\n# {date}\n",
        )
        message_template = load_template(
            message_template_path,
            default="## {time} telegram update\n\n{text}\n",
        )

        poll_interval = float(os.getenv("POLL_INTERVAL", "10"))

        tz_name = os.getenv("LOCAL_TIMEZONE")
        local_tz = ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
        if local_tz is None:
            local_tz = ZoneInfo("UTC")

        return cls(
            token=token,
            repo_root=repo_root,
            journal_root=journal_root,
            local_tz=local_tz,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            note_template=note_template,
            message_template=message_template,
            poll_interval=poll_interval,
        )


def ensure_directories(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_note_initialized(
    note_path: Path, local_time: datetime, config: BotConfig
) -> None:
    """Create note with template if it does not exist or is empty."""
    ensure_directories(note_path)
    needs_template = not note_path.exists() or note_path.stat().st_size == 0
    if needs_template:
        header_date = local_time.strftime("%Y-%m-%d, %A")
        content = config.note_template.format(date=header_date)
        if not content.endswith("\n"):
            content += "\n"
        note_path.write_text(content, encoding="utf-8")


def format_entry(
    text: str, author: Optional[str], local_time: datetime, config: BotConfig
) -> str:
    clean_text = text.strip()
    author_block = f"\n\nfrom: {author}" if author else ""
    rendered = config.message_template.format(
        time=f"{local_time:%H:%M}",
        text=clean_text,
        author_block=author_block,
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


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


def ensure_git_identity(config: BotConfig) -> bool:
    ok_name = run_git(config.repo_root, "config", "user.name", config.git_user_name)
    ok_email = run_git(config.repo_root, "config", "user.email", config.git_user_email)
    return ok_name and ok_email


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    config: BotConfig = context.bot_data["config"]

    local_time = message.date.astimezone(config.local_tz)
    note_path = (
        config.journal_root
        / f"{local_time:%Y}"
        / f"{local_time:%m}"
        / f"{local_time:%d}"
        / "note.md"
    )

    try:
        if not run_git(config.repo_root, "pull", "--rebase"):
            return

        ensure_note_initialized(note_path, local_time, config)

        author = None
        if message.from_user:
            parts = [
                message.from_user.full_name or "",
                f"@{message.from_user.username}" if message.from_user.username else "",
            ]
            author = " ".join(part for part in parts if part).strip() or None

        with note_path.open("a", encoding="utf-8") as fh:
            fh.write(format_entry(message.text, author, local_time, config))

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
    logger.info("Starting bot; writing notes under %s", config.journal_root)

    if not ensure_git_identity(config):
        raise SystemExit("Failed to configure git identity")

    application = ApplicationBuilder().token(config.token).build()
    application.bot_data["config"] = config
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.run_polling(
        poll_interval=config.poll_interval, allowed_updates=["message"]
    )


if __name__ == "__main__":
    main()
