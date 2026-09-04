from __future__ import annotations

import logging
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.douyin.com/",
}

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class DouyinDownloaderError(Exception):
    """Base class for expected downloader errors."""


class InvalidDouyinURLError(DouyinDownloaderError):
    """Raised when input does not contain a valid URL."""


class LinkResolutionError(DouyinDownloaderError):
    """Raised when short link resolution fails."""


class VideoIdExtractionError(DouyinDownloaderError):
    """Raised when no video ID can be extracted."""


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if it does not exist and return its Path."""
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def setup_logging(log_dir: str | Path = "logs", logger_name: str = "douyin_downloader") -> logging.Logger:
    """Configure console + rotating file logging."""
    log_folder = ensure_directory(log_dir)
    log_path = log_folder / "app.log"

    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def extract_first_url(text: str) -> str:
    """Extract first URL from user input or share text."""
    match = URL_PATTERN.search(text)
    if not match:
        raise InvalidDouyinURLError("No valid URL found in the provided input.")
    candidate = match.group(0).strip().strip('"').strip("'")
    return candidate.rstrip(").,;!?")


def resolve_redirect_url(
    session: requests.Session,
    share_url: str,
    timeout: tuple[int, int],
    max_retries: int,
    backoff_factor: float,
    logger: logging.Logger | None = None,
) -> str:
    """Resolve final URL from a short share link with retries."""
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                share_url,
                timeout=timeout,
                allow_redirects=True,
                headers=DEFAULT_HEADERS,
            )
            response.raise_for_status()
            if not response.url:
                raise LinkResolutionError("Redirect URL was empty.")
            return response.url
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_retries:
                break
            sleep_seconds = backoff_factor * (2 ** (attempt - 1))
            if logger:
                logger.warning(
                    "Link resolution failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    max_retries,
                    exc,
                    sleep_seconds,
                )
            time.sleep(sleep_seconds)

    raise LinkResolutionError("Could not resolve Douyin share link.") from last_error


def extract_video_id(url: str) -> str:
    """Extract Douyin video ID from URL path or query parameters."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    for key in ("modal_id", "item_ids", "group_id", "aweme_id"):
        values = query.get(key)
        if not values:
            continue
        match = re.search(r"(\d{8,24})", values[0])
        if match:
            return match.group(1)

    for pattern in (r"/video/(\d{8,24})", r"/note/(\d{8,24})", r"/(\d{8,24})(?:/|$)"):
        match = re.search(pattern, parsed.path)
        if match:
            return match.group(1)

    fallback = re.search(r"(?<!\d)(\d{8,24})(?!\d)", url)
    if fallback:
        return fallback.group(1)

    raise VideoIdExtractionError("Unable to extract video ID from resolved URL.")