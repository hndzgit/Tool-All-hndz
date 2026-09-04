import os
import json
import threading
import time
import subprocess
import platform
from datetime import datetime
import customtkinter as ctk
from customtkinter import filedialog
from pathlib import Path

# Add douyin dir to path to import its modules properly
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from douyin.downloader import DouyinDownloader
from douyin.tiktok_downloader import TikTokDownloader
from douyin.utils import setup_logging

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "downloads"
CONFIG_FILE = BASE_DIR / "config.json"
LOGGER = setup_logging(LOGS_DIR)

class DouyinApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.current_download_dir = str(DEFAULT_DOWNLOAD_DIR)
        self.saved_links = ""
        self.download_logs = []
        
        # Thread control variables
        self.pause_event = threading.Event()
        self.pause_event.set()  # Running initially
        self.is_stopped = False
        self.is_downloading = False
        
        self.load_config()
        self.setup_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    saved_path = config.get("download_dir", "")
                    if saved_path and os.path.isdir(saved_path):
                        self.current_download_dir = saved_path
                    self.saved_links = config.get("saved_links", "")
                    self.download_logs = config.get("download_logs", [])
                    self.saved_browser = config.get("saved_browser", "None")
            except Exception as e:
                LOGGER.error(f"Failed to load config: {e}")

    def save_config(self):
        try:
            links = self.entry_link.get("1.0", "end-1c").strip() if hasattr(self, 'entry_link') else self.saved_links
            browser = self.combo_cookies.get() if hasattr(self, 'combo_cookies') else getattr(self, 'saved_browser', 'None')
            config = {
                "download_dir": self.current_download_dir,
                "saved_links": links,
                "download_logs": self.download_logs,
                "saved_browser": browser
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            LOGGER.error(f"Failed to save config: {e}")

    def auto_save_links(self):
        self.saved_links = self.entry_link.get("1.0", "end-1c").strip()
        self.save_config()

    def setup_ui(self):
        title_label = ctk.CTkLabel(self, text="MULTI-PLATFORM DOWNLOADER", font=("Arial", 24, "bold"))
        title_label.pack(pady=20)

        # Input
        frame_input = ctk.CTkFrame(self, fg_color="transparent")
        frame_input.pack(fill="x", padx=40, pady=10)
        
        ctk.CTkLabel(frame_input, text="Link Video (FB, TikTok, Douyin, IG, YT...)\n(Mỗi link/text 1 dòng):", justify="left").pack(side="left", padx=(0, 10))
        self.entry_link = ctk.CTkTextbox(frame_input, width=500, height=120)
        self.entry_link.pack(side="left", padx=5, fill="both", expand=True)
        if self.saved_links:
            self.entry_link.insert("1.0", self.saved_links)
        self.entry_link.bind("<KeyRelease>", lambda e: self.auto_save_links())

        # Path Selection
        frame_path = ctk.CTkFrame(self, fg_color="transparent")
        frame_path.pack(fill="x", padx=40, pady=5)
        
        ctk.CTkLabel(frame_path, text="Lưu tại:").pack(side="left", padx=5)
        self.entry_path = ctk.CTkEntry(frame_path, width=400)
        self.entry_path.insert(0, self.current_download_dir)
        self.entry_path.configure(state="readonly")
        self.entry_path.pack(side="left", padx=5, fill="x", expand=True)
        
        self.btn_browse = ctk.CTkButton(frame_path, text="Thư mục", width=80, command=self.choose_directory)
        self.btn_browse.pack(side="left", padx=5)

        # Options
        frame_options = ctk.CTkFrame(self, fg_color="transparent")
        frame_options.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(frame_options, text="Chế độ tải:").pack(side="left", padx=5)
        self.combo_mode = ctk.CTkComboBox(frame_options, values=["Video (no watermark)", "Audio only", "Cover image"], width=200)
        self.combo_mode.set("Video (no watermark)")
        self.combo_mode.pack(side="left", padx=5)

        ctk.CTkLabel(frame_options, text="Cookie trình duyệt:").pack(side="left", padx=(20, 5))
        self.combo_cookies = ctk.CTkComboBox(
            frame_options, 
            values=["None", "Chrome", "Safari", "Firefox", "Edge"], 
            width=120,
            command=lambda e: self.save_config()
        )
        if hasattr(self, 'saved_browser') and self.saved_browser in ["None", "Chrome", "Safari", "Firefox", "Edge"]:
            self.combo_cookies.set(self.saved_browser)
        else:
            self.combo_cookies.set("None")
        self.combo_cookies.pack(side="left", padx=5)

        # Download Controls
        frame_controls = ctk.CTkFrame(self, fg_color="transparent")
        frame_controls.pack(pady=15)

        self.btn_download = ctk.CTkButton(
            frame_controls, 
            text="⬇ TẢI XUỐNG", 
            font=("Arial", 14, "bold"), 
            height=40, 
            command=self.start_download
        )
        self.btn_download.pack(side="left", padx=5)

        self.btn_pause = ctk.CTkButton(
            frame_controls, 
            text="⏸ TẠM DỪNG", 
            font=("Arial", 14, "bold"), 
            height=40, 
            fg_color="#F39C12", 
            hover_color="#E67E22", 
            state="disabled", 
            command=self.toggle_pause
        )
        self.btn_pause.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(
            frame_controls, 
            text="⏹ DỪNG TẢI", 
            font=("Arial", 14, "bold"), 
            height=40, 
            fg_color="#E74C3C", 
            hover_color="#C0392B", 
            state="disabled", 
            command=self.stop_download
        )
        self.btn_stop.pack(side="left", padx=5)

        # Status
        self.lbl_status = ctk.CTkLabel(self, text="Sẵn sàng!", text_color="green", font=("Arial", 13, "bold"))
        self.lbl_status.pack(pady=(0, 10))

        # Log History Area
        frame_logs = ctk.CTkFrame(self, fg_color="transparent")
        frame_logs.pack(fill="both", expand=True, padx=40, pady=(10, 20))

        header_frame = ctk.CTkFrame(frame_logs, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(header_frame, text="Lịch sử tải xuống (Bấm để copy link):", font=("Arial", 13, "bold")).pack(side="left")
        
        self.btn_clear_logs = ctk.CTkButton(
            header_frame, 
            text="Xóa lịch sử", 
            width=100, 
            height=26, 
            fg_color="#7F8C8D", 
            hover_color="#95A5A6", 
            command=self.clear_logs
        )
        self.btn_clear_logs.pack(side="right")

        self.log_scrollable = ctk.CTkScrollableFrame(frame_logs, height=200, fg_color=("white", "#2E2E3E"))
        self.log_scrollable.pack(fill="both", expand=True)

        self.log_scrollable.grid_columnconfigure(0, weight=1)  # Time
        self.log_scrollable.grid_columnconfigure(1, weight=3)  # Link
        self.log_scrollable.grid_columnconfigure(2, weight=1)  # Mode
        self.log_scrollable.grid_columnconfigure(3, weight=2)  # Status
        self.log_scrollable.grid_columnconfigure(4, weight=1)  # Action

        self.render_logs()

    def choose_directory(self):
        selected_dir = filedialog.askdirectory(initialdir=self.current_download_dir, title="Chọn thư mục tải về")
        if selected_dir:
            self.current_download_dir = selected_dir
            self.entry_path.configure(state="normal")
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, self.current_download_dir)
            self.entry_path.configure(state="readonly")
            self.save_config()

    def toggle_pause(self):
        if not self.is_downloading:
            return
        if self.pause_event.is_set():
            # Pause
            self.pause_event.clear()
            self.btn_pause.configure(text="▶ TIẾP TỤC", fg_color="#2ECC71", hover_color="#27AE60")
            self.lbl_status.configure(text="Đang tạm dừng...", text_color="orange")
        else:
            # Resume
            self.pause_event.set()
            self.btn_pause.configure(text="⏸ TẠM DỪNG", fg_color="#F39C12", hover_color="#E67E22")
            self.lbl_status.configure(text="Đang tiếp tục tải...", text_color="orange")

    def stop_download(self):
        if not self.is_downloading:
            return
        self.is_stopped = True
        self.pause_event.set()  # Unblock if paused
        self.btn_stop.configure(state="disabled")
        self.btn_pause.configure(state="disabled")
        self.lbl_status.configure(text="Đang dừng tải...", text_color="red")

    def reset_ui_buttons(self):
        self.is_downloading = False
        self.btn_download.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="⏸ TẠM DỪNG", fg_color="#F39C12", hover_color="#E67E22")
        self.btn_stop.configure(state="disabled")

    def check_if_already_downloaded(self, link):
        import re
        video_id = None
        
        # 1. First, check if the EXACT link is already in our history logs with "Thành công" or "Đã có (Bỏ qua)" status
        for log in self.download_logs:
            if log.get("link") == link and log.get("status") in ("Thành công", "Đã có (Bỏ qua)"):
                fpath = log.get("file_path", "")
                vid = log.get("video_id", "")
                if fpath and os.path.exists(fpath):
                    return fpath, vid
                return "remembered_in_history", vid

        # 2. Try regex on the URL to see if it contains the video ID directly
        match = re.search(r"/video/(\d{8,25})", link)
        if match:
            video_id = match.group(1)
        else:
            match = re.search(r"modal_id=(\d{8,25})", link)
            if match:
                video_id = match.group(1)
            else:
                match = re.search(r"item_ids=(\d{8,25})", link)
                if match:
                    video_id = match.group(1)
                else:
                    # YouTube
                    match = re.search(r"(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", link)
                    if match:
                        video_id = match.group(1)
                    else:
                        # FB watch / videos / reel
                        match = re.search(r"(?:watch\/\?v=|videos\/|reel\/|v=)(\d{8,25})", link)
                        if match:
                            video_id = match.group(1)
                        else:
                            # Instagram post/reel
                            match = re.search(r"\/(?:p|reel|reels|tv)\/([a-zA-Z0-9_-]+)", link)
                            if match:
                                video_id = match.group(1)

        # 3. If no ID found directly, resolve redirect
        if not video_id:
            try:
                import requests
                from douyin.utils import DEFAULT_HEADERS, extract_video_id, extract_first_url
                
                share_url = extract_first_url(link)
                session = requests.Session()
                response = session.head(
                    share_url,
                    allow_redirects=True,
                    timeout=5,
                    headers=DEFAULT_HEADERS
                )
                resolved_url = response.url
                if resolved_url:
                    video_id = extract_video_id(resolved_url)
            except Exception as e:
                LOGGER.warning(f"Could not extract video ID from redirect for link {link}: {e}")

        # 4. Check if the video_id matches any successfully downloaded item in our logs
        if video_id:
            for log in self.download_logs:
                log_vid = log.get("video_id", "")
                log_link = log.get("link", "")
                log_status = log.get("status", "")
                log_fpath = log.get("file_path", "")
                
                if log_status in ("Thành công", "Đã có (Bỏ qua)"):
                    if (log_vid and log_vid == video_id) or video_id in log_link or (log_fpath and video_id in os.path.basename(log_fpath)):
                        if log_fpath and os.path.exists(log_fpath):
                            return log_fpath, video_id
                        return "remembered_in_history", video_id

            # 5. Check if file with video_id exists in the output directory
            output_path = Path(self.current_download_dir)
            if output_path.exists():
                for file in output_path.glob(f"{video_id}.*"):
                    if file.is_file():
                        return str(file), video_id
        return None, video_id

    def start_download(self):
        raw_text = self.entry_link.get("1.0", "end").strip()
        if not raw_text:
            self.lbl_status.configure(text="Vui lòng nhập link!", text_color="red")
            return
            
        links = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not links: return

        mode_str = self.combo_mode.get()
        mode_map = {
            "Video (no watermark)": "video",
            "Audio only": "audio",
            "Cover image": "cover"
        }
        mode = mode_map.get(mode_str, "video")

        # Update controls UI
        self.is_downloading = True
        self.is_stopped = False
        self.pause_event.set()
        
        self.btn_download.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="⏸ TẠM DỪNG", fg_color="#F39C12", hover_color="#E67E22")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="Đang bắt đầu tải...", text_color="orange")

        cookie_browser = self.combo_cookies.get()
        # Chạy tải trên luồng riêng để không đơ UI
        threading.Thread(target=self.download_thread, args=(links, mode, cookie_browser), daemon=True).start()

    def download_thread(self, links, mode, cookie_browser="None"):
        success_count = 0
        fail_count = 0
        total = len(links)
        try:
            # Khởi tạo sãn Downloader cho Douyin
            douyin_dl = DouyinDownloader(
                output_dir=self.current_download_dir,
                timeout=(10, 30),
                max_retries=3,
                backoff_factor=1.0,
                logger=LOGGER,
            )
            # Khởi tạo sãn Downloader cho TikTok / Universal
            tiktok_dl = TikTokDownloader(
                output_dir=self.current_download_dir,
                logger=LOGGER,
                browser_cookies=cookie_browser
            )
            
            with douyin_dl, tiktok_dl:
                for idx, link in enumerate(links, 1):
                    # Check stop before starting this download
                    if self.is_stopped:
                        break
                    
                    # Check pause before starting this download
                    if not self.pause_event.is_set():
                        self.lbl_status.configure(text=f"Đang tạm dừng... ({idx-1}/{total})", text_color="orange")
                        self.update_log_status(links[idx-2] if idx > 1 else link, mode, "Tạm dừng")
                        self.pause_event.wait()
                    
                    if self.is_stopped:
                        break
                    
                    # Check if already downloaded in the selected output folder
                    self.lbl_status.configure(text=f"Kiểm tra trùng lặp ({idx}/{total})...", text_color="orange")
                    existing_file, resolved_video_id = self.check_if_already_downloaded(link)
                    if existing_file:
                        success_count += 1
                        file_display_name = os.path.basename(existing_file) if existing_file != "remembered_in_history" else "Lịch sử tải"
                        self.lbl_status.configure(text=f"Đã có: {file_display_name}", text_color="green")
                        save_path = existing_file if existing_file != "remembered_in_history" else ""
                        self.update_log_status(link, mode, "Đã có (Bỏ qua)", file_path=save_path, video_id=resolved_video_id)
                        time.sleep(0.5)
                        continue
                        
                    self.lbl_status.configure(text=f"Đang tải ({idx}/{total})...", text_color="orange")
                    self.update_log_status(link, mode, "Đang tải...")
                    
                    try:
                        # Tự động chọn downloader tùy thuộc vào link
                        link_lower = link.lower()
                        is_douyin = "douyin.com" in link_lower or "iesdouyin.com" in link_lower
                        
                        if is_douyin:
                            downloader = douyin_dl
                            LOGGER.info(f"Using DouyinDownloader for {link}")
                        else:
                            downloader = tiktok_dl
                            LOGGER.info(f"Using UniversalDownloader for {link}")

                        try:
                            result = downloader.download_from_share_url(
                                share_input=link,
                                mode=mode,
                                show_progress=False,
                            )
                        except Exception as e:
                            # Fallback from DouyinDownloader to UniversalDownloader (yt-dlp) if it failed
                            if is_douyin:
                                LOGGER.warning(f"Douyin API failed. Falling back to Universal Downloader for {link}: {e}")
                                downloader = tiktok_dl
                                result = downloader.download_from_share_url(
                                    share_input=link,
                                    mode=mode,
                                    show_progress=False,
                                )
                            else:
                                raise e

                        success_count += 1
                        self.lbl_status.configure(text=f"Tải xong {idx}/{total}: {result.file_path}", text_color="green")
                        self.update_log_status(link, mode, "Thành công", file_path=result.file_path, video_id=result.video_id)
                        
                        # Sleep 2s in chunks to allow fast pause/stop response
                        for _ in range(20):
                            if self.is_stopped or not self.pause_event.is_set():
                                break
                            time.sleep(0.1)
                            
                    except Exception as e:
                        err_msg = str(e)
                        if "router data" in err_msg or "DouyinAPIError" in err_msg:
                            LOGGER.warning(f"Bị chặn IP tại {link}. Triggering Auto-Pause...")
                            self.lbl_status.configure(text=f"Bị chặn IP! Đang tạm dừng chờ IP mới... ({idx}/{total})", text_color="red")
                            self.update_log_status(link, mode, "Bị chặn IP (Chờ IP mới)")
                            
                            # Vòng lặp Auto-Resume vĩnh viễn kiểm tra lại mỗi 10 giây
                            resolved = False
                            while not resolved and not self.is_stopped:
                                # Check user pause/resume inside this retry loop
                                if not self.pause_event.is_set():
                                    self.lbl_status.configure(text=f"Đang tạm dừng... ({idx}/{total})", text_color="orange")
                                    self.pause_event.wait()
                                    
                                if self.is_stopped:
                                    break
                                    
                                # Wait 10 seconds in chunks
                                for _ in range(100):
                                    if self.is_stopped or not self.pause_event.is_set():
                                        break
                                    time.sleep(0.1)
                                
                                if self.is_stopped:
                                    break
                                if not self.pause_event.is_set():
                                    continue
                                    
                                self.lbl_status.configure(text=f"Đang thử lại kết nối... ({idx}/{total})", text_color="orange")
                                try:
                                    result_retry = downloader.download_from_share_url(
                                        share_input=link,
                                        mode=mode,
                                        show_progress=False,
                                    )
                                    success_count += 1
                                    self.lbl_status.configure(text=f"Tải xong {idx}/{total}: {result_retry.file_path}", text_color="green")
                                    self.update_log_status(link, mode, "Thành công", file_path=result_retry.file_path, video_id=result_retry.video_id)
                                    resolved = True
                                    
                                    # Sleep 2s checking stop/pause
                                    for _ in range(20):
                                        if self.is_stopped or not self.pause_event.is_set():
                                            break
                                        time.sleep(0.1)
                                except Exception as retry_e:
                                    retry_err_msg = str(retry_e)
                                    if "router data" in retry_err_msg or "DouyinAPIError" in retry_err_msg:
                                        self.lbl_status.configure(text=f"Vẫn bị chặn. Vui lòng đổi IP hoặc chờ... ({idx}/{total})", text_color="red")
                                    else:
                                        fail_count += 1
                                        self.lbl_status.configure(text=f"Lỗi tải mục {idx}: {retry_err_msg}", text_color="red")
                                        self.update_log_status(link, mode, f"Lỗi: {retry_err_msg}")
                                        resolved = True # Thoát lặp chờ vì lỗi khác (Không phải block)
                                        
                        else:
                            LOGGER.error(f"Lỗi tải {link}: {e}")
                            fail_count += 1
                            self.lbl_status.configure(text=f"Lỗi tải mục {idx}: {err_msg}", text_color="red")
                            self.update_log_status(link, mode, f"Lỗi: {err_msg}")
                
                if self.is_stopped:
                    msg = f"⏹ Đã dừng tải! Thành công: {success_count}/{total}"
                    if fail_count > 0: msg += f" (Lỗi: {fail_count})"
                    self.lbl_status.configure(text=msg, text_color="orange")
                else:
                    msg = f"✅ Xong! Thành công: {success_count}/{total}"
                    if fail_count > 0: msg += f" (Lỗi: {fail_count})"
                    self.lbl_status.configure(text=msg, text_color="green" if fail_count == 0 else "orange")
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Lỗi hệ thống: {str(e)}", text_color="red")
        finally:
            self.after(0, self.reset_ui_buttons)

    def update_log_status(self, link, mode, status, file_path=None, video_id=None):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ensure values are cast to string for JSON serialization
        if file_path is not None:
            file_path = str(file_path)
        if video_id is not None:
            video_id = str(video_id)
            
        found = False
        for log in self.download_logs:
            if log.get("link") == link and log.get("mode") == mode:
                log["status"] = status
                log["timestamp"] = now_str
                if file_path:
                    log["file_path"] = file_path
                if video_id:
                    log["video_id"] = video_id
                found = True
                break
                
        if not found:
            new_log = {
                "timestamp": now_str,
                "video_id": video_id or "",
                "link": link,
                "mode": mode,
                "status": status,
                "file_path": file_path or ""
            }
            self.download_logs.append(new_log)
            # Limit logs to 100 entries to prevent config bloat
            if len(self.download_logs) > 100:
                self.download_logs = self.download_logs[-100:]
                
        self.save_config()
        self.after(0, self.render_logs)

    def render_logs(self):
        # Clear existing widgets in log_scrollable
        for widget in self.log_scrollable.winfo_children():
            widget.destroy()

        # Table Headers
        headers = ["Thời gian", "Liên kết", "Chế độ", "Trạng thái", "Thao tác"]
        for col_idx, text in enumerate(headers):
            lbl = ctk.CTkLabel(
                self.log_scrollable, 
                text=text, 
                font=("Arial", 12, "bold"), 
                text_color=("#34495E", "#BDC3C7"),
                anchor="w"
            )
            lbl.grid(row=0, column=col_idx, padx=10, pady=5, sticky="ew")

        # Table separator line
        sep = ctk.CTkFrame(self.log_scrollable, height=2, fg_color=("#BDC3C7", "#7F8C8D"))
        sep.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(0, 5))

        # Render each log row (reverse order to show newest first)
        for row_idx, log in enumerate(reversed(self.download_logs), start=2):
            time_str = log.get("timestamp", "")
            link = log.get("link", "")
            mode = log.get("mode", "")
            status = log.get("status", "")
            file_path = log.get("file_path", "")

            # Format link to show only domain/id if it's too long
            short_link = link
            if len(link) > 40:
                short_link = link[:20] + "..." + link[-15:]

            # Color coding for status
            status_color = "#2ECC71"  # green
            if "Lỗi" in status or "bị chặn" in status:
                status_color = "#E74C3C"  # red
            elif "Đang tải" in status or "chờ" in status or "tạm dừng" in status or "Tạm dừng" in status:
                status_color = "#F39C12"  # orange

            # Row background (alternating colors for better table scan)
            bg_color = "transparent" if row_idx % 2 == 0 else ("#F2F4F4", "#24252D")
            row_frame = ctk.CTkFrame(self.log_scrollable, fg_color=bg_color, corner_radius=0)
            row_frame.grid(row=row_idx, column=0, columnspan=5, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=3)
            row_frame.grid_columnconfigure(2, weight=1)
            row_frame.grid_columnconfigure(3, weight=2)
            row_frame.grid_columnconfigure(4, weight=1)

            # Widgets inside row_frame
            lbl_time = ctk.CTkLabel(row_frame, text=time_str, font=("Arial", 11), anchor="w")
            lbl_time.grid(row=0, column=0, padx=10, pady=4, sticky="w")

            lbl_link = ctk.CTkLabel(row_frame, text=short_link, font=("Arial", 11), text_color=("#2980B9", "#3498DB"), anchor="w", cursor="hand2")
            lbl_link.grid(row=0, column=1, padx=10, pady=4, sticky="w")
            lbl_link.bind("<Button-1>", lambda e, l=link: self.copy_to_clipboard(l))

            lbl_mode = ctk.CTkLabel(row_frame, text=mode, font=("Arial", 11), anchor="w")
            lbl_mode.grid(row=0, column=2, padx=10, pady=4, sticky="w")

            lbl_status = ctk.CTkLabel(row_frame, text=status, font=("Arial", 11, "bold"), text_color=status_color, anchor="w")
            lbl_status.grid(row=0, column=3, padx=10, pady=4, sticky="w")

            if file_path and os.path.exists(file_path):
                btn_open = ctk.CTkButton(
                    row_frame, 
                    text="📁 Finder", 
                    width=60, 
                    height=20, 
                    font=("Arial", 10),
                    command=lambda p=file_path: self.reveal_in_finder(p)
                )
                btn_open.grid(row=0, column=4, padx=10, pady=4, sticky="e")
            else:
                lbl_na = ctk.CTkLabel(row_frame, text="-", font=("Arial", 11), anchor="e")
                lbl_na.grid(row=0, column=4, padx=25, pady=4, sticky="e")

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.lbl_status.configure(text="Đã sao chép liên kết vào bộ nhớ tạm!", text_color="green")

    def clear_logs(self):
        self.download_logs = []
        self.save_config()
        self.render_logs()
        self.lbl_status.configure(text="Đã xóa toàn bộ lịch sử log!", text_color="green")

    def reveal_in_finder(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", os.path.normpath(path)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            LOGGER.error(f"Failed to open path: {e}")

if __name__ == "__main__":
    app = ctk.CTk()
    app.geometry("800x600")
    frame = DouyinApp(app)
    frame.pack(fill="both", expand=True)
    app.mainloop()