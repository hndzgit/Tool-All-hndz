# Douyin Downloader

Professional Douyin downloader with:
- Short link resolution
- Watermark-free video download (`playwm` -> `play`)
- Audio-only download
- Cover image download
- Exponential-backoff retries
- Chunked streaming download with progress
- Logging to `logs/app.log`
- CLI + optional Flask web app

## Requirements

- Python 3.10+
- `requests`
- Optional web mode: `Flask`

Install dependencies:

```bash
pip install -r requirements.txt
```

## CLI Usage

Run with prompt:

```bash
python main.py
```

Run with arguments:

```bash
python main.py "https://v.douyin.com/xxxxx/" --mode video
python main.py "https://v.douyin.com/xxxxx/" --mode audio
python main.py "https://v.douyin.com/xxxxx/" --mode cover
```

## Flask Web App

Local run:

```bash
python app.py
```

Then open `http://127.0.0.1:5000`.

## Railway / Render Deployment

This repo includes:
- `Procfile`
- `runtime.txt`
- `requirements.txt`

Recommended start command:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```