import os
import sys
from pathlib import Path
import yt_dlp
from typing import Optional, NamedTuple

class DownloadResult(NamedTuple):
    video_id: str
    title: str
    mode: str
    file_path: Path
    resolved_url: str

def find_ffmpeg():
    """Tự động tìm kiếm ffmpeg trong PATH hoặc các thư mục mặc định"""
    # 1. Check in PATH
    for path in os.environ.get("PATH", "").split(os.pathsep):
        loc = os.path.join(path, "ffmpeg")
        if os.path.exists(loc):
            return path
            
    # 2. Check Homebrew / Mac common paths
    brew_locs = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg"
    ]
    for loc in brew_locs:
        if os.path.exists(loc):
            return os.path.dirname(loc)
    return None

class UniversalDownloader:
    def __init__(self, output_dir="downloads", logger=None, browser_cookies="None"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.browser_cookies = browser_cookies
        
        # Prepend macOS Homebrew / common paths to PATH to ensure ffmpeg is found
        extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
        current_path = os.environ.get("PATH", "")
        new_paths = []
        for path in extra_paths:
            if path not in current_path:
                new_paths.append(path)
        if new_paths:
            os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + current_path

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def download_from_share_url(self, share_input: str, mode: str = "video", show_progress: bool = False) -> DownloadResult:
        # Standard ytdlp options
        ydl_opts = {
            'outtmpl': os.path.join(str(self.output_dir), '%(title)s [%(id)s].%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'nopart': True,
            'restrictfilenames': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }
        
        ffmpeg_dir = find_ffmpeg()
        if ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = ffmpeg_dir
            if self.logger:
                self.logger.info(f"Using FFmpeg from location: {ffmpeg_dir}")
        
        if self.browser_cookies and self.browser_cookies.lower() != "none":
            if self.logger:
                self.logger.info(f"Using cookies from browser: {self.browser_cookies}")
            ydl_opts['cookiesfrombrowser'] = (self.browser_cookies.lower(),)
            
        # Audio mode or Video mode
        if mode == "audio":
            ydl_opts['format'] = 'bestaudio[acodec^=mp4a]/bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            ydl_opts['outtmpl'] = os.path.join(str(self.output_dir), '%(title)s [%(id)s].%(ext)s')
        elif mode == "cover":
            ydl_opts['skip_download'] = True
            ydl_opts['writethumbnail'] = True
            ydl_opts['outtmpl'] = os.path.join(str(self.output_dir), '%(title)s [%(id)s].%(ext)s')
        else: # video
            # Download best MP4 compatible H.264 video + AAC audio, merge into MP4 container
            # This is 100% compatible with macOS Finder/QuickTime Player!
            ydl_opts['format'] = 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]/best'
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.logger:
                self.logger.info(f"Extracting/downloading metadata and media for {share_input}")
            
            info_dict = ydl.extract_info(share_input, download=True)
            video_id = info_dict.get('id', 'unknown')
            title = info_dict.get('title', f"video_{video_id}")
            
            # Retrieve final path correctly from info_dict (takes care of output template and mergers)
            expected_file = Path(info_dict.get('_filename', ''))
            req_downloads = info_dict.get('requested_downloads', [])
            if req_downloads and req_downloads[0].get('filepath'):
                expected_file = Path(req_downloads[0].get('filepath'))
                
            # If path resolution from yt-dlp dictionary is blank, fallback to predicting it
            if not expected_file or not expected_file.exists():
                ext = 'mp3' if mode == 'audio' else ('jpg' if mode == 'cover' else 'mp4')
                # Predict fallback filenames
                predicted_name = f"{title} [{video_id}].{ext}"
                # Clean invalid chars in template fallback (yt-dlp default replacement)
                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    predicted_name = predicted_name.replace(char, '_')
                expected_file = self.output_dir / predicted_name
                
                # Check actual files on disk
                if mode == 'cover':
                    for img_ext in ['jpg', 'jpeg', 'webp', 'png']:
                        test_p = expected_file.with_suffix(f".{img_ext}")
                        if test_p.exists():
                            expected_file = test_p
                            break
                elif mode == 'video':
                    for vid_ext in ['mp4', 'webm', 'mkv', 'mov']:
                        test_p = expected_file.with_suffix(f".{vid_ext}")
                        if test_p.exists():
                            expected_file = test_p
                            break
                elif mode == 'audio':
                    for aud_ext in ['mp3', 'm4a', 'wav']:
                        test_p = expected_file.with_suffix(f".{aud_ext}")
                        if test_p.exists():
                            expected_file = test_p
                            break

            if self.logger:
                self.logger.info(f"Download completed successfully. Saved to {expected_file}")

            return DownloadResult(
                video_id=video_id,
                title=title,
                mode=mode,
                file_path=expected_file,
                resolved_url=share_input
            )

# Maintain backward compatibility for existing code referring to TikTokDownloader
TikTokDownloader = UniversalDownloader