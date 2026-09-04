from __future__ import annotations

import base64
import json
import logging
import re
import time
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from .utils import (
    DEFAULT_HEADERS,
    DouyinDownloaderError,
    extract_first_url,
    extract_video_id,
    resolve_redirect_url,
    setup_logging,
)


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
SUPPORTED_MODES = {"video", "audio", "cover"}
MOBILE_SHARE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}


class DouyinAPIError(DouyinDownloaderError):
    """Raised when Douyin API response is invalid."""


class DownloadFailedError(DouyinDownloaderError):
    """Raised when file download fails after retries."""


class ContentTypeValidationError(DouyinDownloaderError):
    """Raised when response content type is unexpected."""


@dataclass
class DownloadResult:
    video_id: str
    title: str
    mode: str
    file_path: Path
    resolved_url: str


class DouyinDownloader:
    API_URL = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"

    def __init__(
        self,
        output_dir: str | Path = "downloads",
        timeout: tuple[int, int] = (10, 30),
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logger or setup_logging()

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def __enter__(self) -> "DouyinDownloader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self.session.close()

    def download_from_share_url(
        self,
        share_input: str,
        mode: str = "video",
        show_progress: bool = True,
    ) -> DownloadResult:
        mode = mode.lower().strip()
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported mode: {mode}. Expected one of {sorted(SUPPORTED_MODES)}")

        share_url = extract_first_url(share_input)
        resolved_url = resolve_redirect_url(
            session=self.session,
            share_url=share_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            backoff_factor=self.backoff_factor,
            logger=self.logger,
        )
        video_id = extract_video_id(resolved_url)
        self.logger.info("Resolved video ID: %s", video_id)

        item_info = self._fetch_item_info(video_id=video_id, resolved_url=resolved_url)
        title = item_info.get("desc") or f"douyin_{video_id}"

        media_url, expected_types, extension = self._select_media_target(item_info, mode)
        target_path = self.output_dir / f"{video_id}{extension}"
        self._download_file(
            file_url=media_url,
            target_path=target_path,
            expected_content_prefixes=expected_types,
            show_progress=show_progress,
        )

        self.logger.info("Download complete: %s", target_path)
        return DownloadResult(
            video_id=video_id,
            title=title,
            mode=mode,
            file_path=target_path,
            resolved_url=resolved_url,
        )

    def _fetch_item_info(self, video_id: str, resolved_url: str) -> dict:
        params = {"item_ids": video_id}
        try:
            data = self._get_json_with_retry(self.API_URL, params=params)
            if data.get("status_code") not in (0, None):
                raise DouyinAPIError(
                    f"Douyin API returned non-zero status_code: {data.get('status_code')}"
                )
            item_list = data.get("item_list") or []
            if item_list:
                return item_list[0]
            raise DouyinAPIError("No item data found in Douyin API response.")
        except DouyinAPIError as exc:
            self.logger.warning(
                "Public item API unavailable for %s (%s). Falling back to share page parsing.",
                video_id,
                exc,
            )
            return self._fetch_item_info_from_share_page(video_id=video_id, resolved_url=resolved_url)

    def _get_json_with_retry(self, url: str, params: dict | None = None) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise requests.HTTPError(
                        f"Retryable HTTP {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                if not response.content:
                    raise ValueError("API response was empty.")
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                self.logger.warning(
                    "API request failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        raise DouyinAPIError("Failed to fetch item metadata from Douyin API.") from last_error

    def _fetch_item_info_from_share_page(self, video_id: str, resolved_url: str) -> dict:
        share_url = self._build_share_page_url(video_id=video_id, resolved_url=resolved_url)
        html = self._get_share_page_html(share_url)
        router_data = self._extract_router_data_json(html)

        if not router_data:
            raise DouyinAPIError("Unable to extract router data from Douyin share page.")

        item_info = self._extract_item_info_from_router_data(router_data)
        if not item_info:
            raise DouyinAPIError("Unable to extract item metadata from share page router data.")

        return item_info

    def _build_share_page_url(self, video_id: str, resolved_url: str) -> str:
        parsed = urlparse(resolved_url)
        if parsed.netloc and "iesdouyin.com" in parsed.netloc:
            return resolved_url
        return f"https://www.iesdouyin.com/share/video/{video_id}/"

    def _get_share_page_html(self, share_url: str) -> str:
        response = self.session.get(share_url, headers=MOBILE_SHARE_HEADERS, timeout=self.timeout)
        response.raise_for_status()
        html = response.text or ""

        # Douyin may return a JS WAF challenge first. Solve it and retry once.
        if self._is_waf_challenge_page(html):
            solved = self._solve_and_set_waf_cookie(html=html, page_url=share_url)
            if solved:
                response = self.session.get(
                    share_url,
                    headers=MOBILE_SHARE_HEADERS,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                html = response.text or ""
        return html

    @staticmethod
    def _is_waf_challenge_page(html: str) -> bool:
        return "Please wait..." in html and "wci=" in html and "cs=" in html

    def _solve_and_set_waf_cookie(self, html: str, page_url: str) -> bool:
        match = re.search(r'wci="([^"]+)"\s*,\s*cs="([^"]+)"', html)
        if not match:
            return False
        cookie_name, challenge_blob = match.groups()

        try:
            challenge_data = json.loads(self._decode_urlsafe_b64(challenge_blob).decode("utf-8"))
            prefix = self._decode_urlsafe_b64(challenge_data["v"]["a"])
            expected_digest = self._decode_urlsafe_b64(challenge_data["v"]["c"]).hex()
        except (KeyError, ValueError, TypeError):
            return False

        solved_value: int | None = None
        for candidate in range(1_000_001):
            digest = sha256(prefix + str(candidate).encode("utf-8")).hexdigest()
            if digest == expected_digest:
                solved_value = candidate
                break

        if solved_value is None:
            return False

        challenge_data["d"] = base64.b64encode(str(solved_value).encode("utf-8")).decode("utf-8")
        cookie_value = base64.b64encode(
            json.dumps(challenge_data, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")

        domain = urlparse(page_url).hostname or "www.iesdouyin.com"
        self.session.cookies.set(cookie_name, cookie_value, domain=domain, path="/")
        self.logger.info("Solved WAF challenge for %s using cookie %s", domain, cookie_name)
        return True

    @staticmethod
    def _decode_urlsafe_b64(value: str) -> bytes:
        normalized = value.replace("-", "+").replace("_", "/")
        normalized += "=" * (-len(normalized) % 4)
        return base64.b64decode(normalized)

    def _extract_router_data_json(self, html: str) -> dict:
        marker = "window._ROUTER_DATA = "
        start = html.find(marker)
        if start < 0:
            return {}

        index = start + len(marker)
        while index < len(html) and html[index].isspace():
            index += 1
        if index >= len(html) or html[index] != "{":
            return {}

        depth = 0
        in_string = False
        escaped = False

        for cursor in range(index, len(html)):
            char = html[cursor]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    payload = html[index : cursor + 1]
                    try:
                        return json.loads(payload)
                    except ValueError:
                        return {}

        return {}

    @staticmethod
    def _extract_item_info_from_router_data(router_data: dict) -> dict:
        loader_data = router_data.get("loaderData", {})
        if not isinstance(loader_data, dict):
            return {}

        for node in loader_data.values():
            if not isinstance(node, dict):
                continue
            video_info_res = node.get("videoInfoRes", {})
            if not isinstance(video_info_res, dict):
                continue
            item_list = video_info_res.get("item_list", [])
            if item_list and isinstance(item_list[0], dict):
                return item_list[0]

        return {}

    def _select_media_target(self, item_info: dict, mode: str) -> tuple[str, tuple[str, ...], str]:
        if mode == "video":
            play_urls = (
                item_info.get("video", {})
                .get("play_addr", {})
                .get("url_list", [])
            )
            if not play_urls:
                raise DouyinAPIError("Video play URL not found.")
            clean_url = play_urls[0].replace("playwm", "play")
            return clean_url, ("video/", "application/octet-stream"), ".mp4"

        if mode == "audio":
            music = item_info.get("music", {})
            audio_urls = music.get("play_url", {}).get("url_list", [])
            if not audio_urls:
                raise DouyinAPIError("Audio URL not found in metadata.")
            return audio_urls[0], ("audio/", "application/octet-stream"), ".mp3"

        video_meta = item_info.get("video", {})
        for key in ("cover", "origin_cover", "dynamic_cover"):
            cover_urls = video_meta.get(key, {}).get("url_list", [])
            if cover_urls:
                return cover_urls[0], ("image/",), ".jpg"

        raise DouyinAPIError("Cover image URL not found in metadata.")

    def _download_file(
        self,
        file_url: str,
        target_path: Path,
        expected_content_prefixes: tuple[str, ...],
        show_progress: bool,
        chunk_size: int = 64 * 1024,
    ) -> None:
        last_error: Exception | None = None
        temp_path = target_path.with_suffix(f"{target_path.suffix}.part")

        for attempt in range(1, self.max_retries + 1):
            try:
                with self.session.get(
                    file_url,
                    stream=True,
                    timeout=self.timeout,
                    allow_redirects=True,
                ) as response:
                    if response.status_code in RETRYABLE_STATUS_CODES: 
                        raise requests.HTTPError(
                            f"Retryable HTTP {response.status_code}",
                            response=response,
                        )
                    response.raise_for_status()

                    self._validate_content_type(
                        content_type=response.headers.get("Content-Type", ""),
                        expected_prefixes=expected_content_prefixes,
                    )

                    total_size = int(response.headers.get("Content-Length") or 0)
                    downloaded_size = 0
                    last_percent = -1

                    with temp_path.open("wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if not chunk:
                                continue
                            file_obj.write(chunk)
                            downloaded_size += len(chunk)

                            if show_progress:
                                if total_size > 0:
                                    percent = int(downloaded_size * 100 / total_size)
                                    if percent != last_percent:
                                        print(
                                            f"\rProgress: {percent:3d}% "
                                            f"({downloaded_size}/{total_size} bytes)",
                                            end="",
                                            flush=True,
                                        )
                                        last_percent = percent
                                else:
                                    print(
                                        f"\rDownloaded: {downloaded_size} bytes",
                                        end="",
                                        flush=True,
                                    )

                if show_progress:
                    print()

                temp_path.replace(target_path)
                return

            except ContentTypeValidationError:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                raise
            except (requests.RequestException, OSError) as exc:
                last_error = exc
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                if attempt == self.max_retries:
                    break
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                self.logger.warning(
                    "Download failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    sleep_seconds,
                )
                if show_progress:
                    print()
                time.sleep(sleep_seconds)

        raise DownloadFailedError(f"Failed to download media from URL: {file_url}") from last_error

    @staticmethod
    def _validate_content_type(content_type: str, expected_prefixes: tuple[str, ...]) -> None:
        normalized = content_type.split(";", maxsplit=1)[0].strip().lower()
        if not normalized:
            raise ContentTypeValidationError("Response did not include a valid Content-Type header.")
        if any(normalized.startswith(prefix) for prefix in expected_prefixes):
            return
        raise ContentTypeValidationError(
            f"Unexpected content type '{content_type}'. Expected one of {expected_prefixes}."
        )