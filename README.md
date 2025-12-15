telegram2foam
==============

Telegram → Foam capture bot that appends incoming text messages to a daily Markdown note and commits the change to Git.

Behavior
- Text messages only; other content types are ignored.
- Appends messages to `journal/YYYY/MM/DD/note.md` (local time) under the repo root.
- When the note is new/empty it is initialized with:
  - Template file: `note_template.md` (can be overridden via `NOTE_TEMPLATE_PATH`)
  - Defaults to:
    ```
    ---
    tags: []
    ---

    # YYYY-MM-DD, Weekday
    ```
- Each message is appended as:
  - Template file: `message_template.md` (can be overridden via `MESSAGE_TEMPLATE_PATH`)
  - Defaults to:
    ```
    ## HH:MM telegram update

    message text
    ```
- Runs `git pull --rebase`, `git add`, `git commit`, and `git push` for every message.
- Logs all errors to stdout but keeps running.

Configuration (env)
- `TELEGRAM_BOT_TOKEN` (required)
- `LOCAL_TIMEZONE` (optional, e.g. `Europe/Berlin`; falls back to system tz)
- `REPO_ROOT` (default: `/app/repo` inside container)
- `GIT_USER_NAME` / `GIT_USER_EMAIL` (required for commits)
- `NOTE_TEMPLATE_PATH` / `MESSAGE_TEMPLATE_PATH` (optional; defaults to `note_template.md` / `message_template.md` in working dir)
- `POLL_INTERVAL` (optional; seconds, default 10)

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
      REPO_ROOT: /app/repo
      GIT_USER_NAME: "Foam Bot"
      GIT_USER_EMAIL: "bot@example.com"
    volumes:
      - /srv/foam/repo:/app/repo
      - /srv/foam/.ssh:/app/.ssh:ro
    restart: unless-stopped
```
Ensure the mounted repo is already cloned with SSH access and contains a `journal` directory (created automatically if missing).
