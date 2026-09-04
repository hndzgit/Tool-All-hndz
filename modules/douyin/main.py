from __future__ import annotations

import argparse
import sys
from pathlib import Path

from downloader import (
    ContentTypeValidationError,
    DouyinAPIError,
    DouyinDownloader,
    DownloadFailedError,
)
from utils import (
    DouyinDownloaderError,
    InvalidDouyinURLError,
    LinkResolutionError,
    VideoIdExtractionError,
    setup_logging,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Professional Douyin downloader (video/audio/cover).")
    parser.add_argument("url", nargs="?", help="Douyin share URL or copied share text.")
    parser.add_argument(
        "--mode",
        choices=["video", "audio", "cover"],
        default="video",
        help="What to download.",
    )
    parser.add_argument(
        "--output-dir",
        default="downloads",
        help="Directory for downloaded files (default: downloads).",
    )
    parser.add_argument("--connect-timeout", type=int, default=10, help="Connection timeout in seconds.")
    parser.add_argument("--read-timeout", type=int, default=30, help="Read timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Maximum retry attempts.")
    parser.add_argument("--backoff-factor", type=float, default=1.0, help="Exponential backoff base.")
    return parser


def safe_console_text(value: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    try:
        value.encode(encoding)
        return value
    except UnicodeEncodeError:
        return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    logs_dir = base_dir / "logs"
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir

    logger = setup_logging(log_dir=logs_dir)
    share_input = (args.url or input("Paste Douyin link: ")).strip()
    if not share_input:
        print("No input was provided.")
        return 1

    downloader = DouyinDownloader(
        output_dir=output_dir,
        timeout=(args.connect_timeout, args.read_timeout),
        max_retries=args.retries,
        backoff_factor=args.backoff_factor,
        logger=logger,
    )

    try:
        result = downloader.download_from_share_url(
            share_input=share_input,
            mode=args.mode,
            show_progress=True,
        )
    except (
        InvalidDouyinURLError,
        LinkResolutionError,
        VideoIdExtractionError,
        DouyinAPIError,
        DownloadFailedError,
        ContentTypeValidationError,
        DouyinDownloaderError,
    ) as exc:
        logger.error("Download failed: %s", exc)
        print(f"Error: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error occurred: %s", exc)
        print("Unexpected error occurred. Check logs/app.log for details.")
        return 1
    finally:
        downloader.close()

    print(f"Video ID: {result.video_id}")
    print(f"Title: {safe_console_text(result.title)}")
    print(f"Saved to: {result.file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())