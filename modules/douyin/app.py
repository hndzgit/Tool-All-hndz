from pathlib import Path

from downloader import (
    ContentTypeValidationError,
    DouyinAPIError,
    DouyinDownloader,
    DownloadFailedError,
)
from utils import (
    InvalidDouyinURLError,
    LinkResolutionError,
    VideoIdExtractionError,
    setup_logging,
)


BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOGGER = setup_logging(LOGS_DIR)


def main():
    share_input = input("Nhập link Douyin: ").strip()

    print("\nChọn chế độ:")
    print("1 = Video (no watermark)")
    print("2 = Audio only")
    print("3 = Cover image")

    choice = input("Nhập lựa chọn [1]: ").strip() or "1"

    mode_map = {
        "1": "video",
        "2": "audio",
        "3": "cover",
    }

    mode = mode_map.get(choice, "video")

    with DouyinDownloader(
        output_dir=DOWNLOAD_DIR,
        timeout=(10, 30),
        max_retries=3,
        backoff_factor=1.0,
        logger=LOGGER,
    ) as downloader:
        try:
            result = downloader.download_from_share_url(
                share_input=share_input,
                mode=mode,
                show_progress=True,
            )

            print("\n✅ Download thành công!")
            print("File:", result.file_path)

        except Exception as exc:
            print("❌ Lỗi:", exc)


if __name__ == "__main__":
    main()