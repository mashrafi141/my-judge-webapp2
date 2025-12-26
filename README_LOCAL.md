# Local Run (Windows) – No Python 3.11 Needed

Because python-telegram-bot is not stable on Python 3.13, **run only the WebApp/API locally**:

## Option 1 (recommended)
Double click: `start_local.bat`

## Option 2
```bash
python keep_alive.py
```

Then open:
- WebApp: http://127.0.0.1:8080/webapp?user_id=12345
- API: http://127.0.0.1:8080/api/problems

## Render
On Render, use the provided Gunicorn start command and bot will run normally (Render uses Python 3.11/3.12).
