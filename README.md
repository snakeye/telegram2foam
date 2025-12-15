telegram2foam
==============

Telegram → Foam capture bot that appends incoming text messages to a daily Markdown note and commits the change to Git.

Behavior
- Text messages only; other content types are ignored.
- Appends `- [HH:MM] Author: message` to `<DAILY_NOTES_DIR>/<YYYY-MM-DD>.md` in local time.
- Runs `git pull --rebase`, `git add`, `git commit`, and `git push` for every message.
- Logs all errors to stdout but keeps running.

Configuration (env)
- `TELEGRAM_BOT_TOKEN` (required)
- `LOCAL_TIMEZONE` (optional, e.g. `Europe/Berlin`; falls back to system tz)
- `REPO_ROOT` (default: current working directory)
- `DAILY_NOTES_DIR` (default: `notes`; set empty to use repo root)

Local run
```bash
uv run python main.py
```

Docker
Build the image:
```bash
docker build -t telegram2foam .
```

Docker Compose example:
```yaml
services:
  bot:
    build: .
    environment:
      TELEGRAM_BOT_TOKEN: "${TELEGRAM_BOT_TOKEN}"
      LOCAL_TIMEZONE: "Europe/Berlin"
      REPO_ROOT: /notes
      DAILY_NOTES_DIR: notes
    volumes:
      - /path/to/foam-repo:/notes
      - ~/.ssh:/root/.ssh:ro
    restart: unless-stopped
```
Ensure the mounted repo is already cloned with SSH access and contains the desired notes folder.
