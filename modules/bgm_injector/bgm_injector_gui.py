import os
import json
import threading
import subprocess
import platform
import random
import time
import shutil
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image

# Add standard directories to PATH to ensure ffmpeg and ffprobe are found on macOS
extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
current_path = os.environ.get("PATH", "")
new_paths = [p for p in extra_paths if p not in current_path]
if new_paths:
    os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + current_path

# Premium Palette (matching main_gui)
BG = "#11111B"
BG2 = "#1E1E2E"
BG3 = "#252538"
BG4 = "#313244"
C_BORDER = "#45475A"
T1 = "#CDD6F4"
T2 = "#A6ADC8"
T3 = "#94A3B8"
ORG = "#FAB387"
GRN = "#A6E3A1"
RED = "#F38BA8"
BLU = "#89B4FA"

def F(size=12, weight="normal"):
    return ("Inter", size, weight)

def get_video_info(file_path):
    """Get video info via ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,avg_frame_rate,duration,codec_type",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(res.stdout)
        
        info = {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "duration": 0.0,
            "has_audio": False
        }
        
        streams = data.get("streams", [])
        for s in streams:
            codec_type = s.get("codec_type")
            if codec_type == "video":
                info["width"] = int(s.get("width", 1920))
                info["height"] = int(s.get("height", 1080))
                if "duration" in s:
                    try:
                        info["duration"] = float(s["duration"])
                    except:
                        pass
            elif codec_type == "audio":
                info["has_audio"] = True
                
        if info["duration"] == 0.0 and "format" in data:
            try:
                info["duration"] = float(data["format"].get("duration", 0.0))
            except:
                pass
                
        return info
    except Exception as e:
        print(f"Error reading video info: {e}")
        return {"width": 1920, "height": 1080, "fps": 30.0, "duration": 0.0, "has_audio": False}

class BgmInjectorApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color=BG, **kwargs)

        self.video_paths = []
        self.bgm_path = "" # Can be file or folder
        self.output_dir = ""
        self.is_running = False
        self.stop_event = threading.Event()

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Configure layout Grid (Left: Controls, Right: Logs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL: CONTROLS ---
        left_frame = ctk.CTkScrollableFrame(self, fg_color=BG2, corner_radius=10, scrollbar_button_color=BG4)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        ctk.CTkLabel(left_frame, text="🎵 GẮN NHẠC NỀN HÀNG LOẠT", font=F(16, "bold"), text_color=ORG).pack(pady=(15, 10))

        # 1. INPUT VIDEOS
        f_in = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_in.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_in, text="1. Chọn Video Đầu Vào", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))
        
        f_in_btns = ctk.CTkFrame(f_in, fg_color="transparent")
        f_in_btns.pack(fill="x", padx=10, pady=4)
        self.btn_load_dir = ctk.CTkButton(f_in_btns, text="📂 Chọn Thư Mục", command=self.choose_input_dir, fg_color=BG4, text_color=T1, height=28)
        self.btn_load_dir.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_load_files = ctk.CTkButton(f_in_btns, text="🎞 Chọn Tệp Lẻ", command=self.choose_input_files, fg_color=BG4, text_color=T1, height=28)
        self.btn_load_files.pack(side="right", fill="x", expand=True, padx=(2, 0))

        self.lbl_loaded = ctk.CTkLabel(f_in, text="Chưa nạp video", font=F(11), text_color=T3)
        self.lbl_loaded.pack(pady=(0, 10))

        # 2. BGM INPUT
        f_bgm = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_bgm.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_bgm, text="2. Chọn Nhạc Nền (BGM/Video Nhạc)", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        f_bgm_btns = ctk.CTkFrame(f_bgm, fg_color="transparent")
        f_bgm_btns.pack(fill="x", padx=10, pady=4)
        self.btn_bgm_file = ctk.CTkButton(f_bgm_btns, text="🎵 Chọn File Nhạc/Video", command=self.choose_bgm_file, fg_color=BG4, text_color=T1, height=28)
        self.btn_bgm_file.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_bgm_dir = ctk.CTkButton(f_bgm_btns, text="📂 Chọn Thư Mục Nhạc", command=self.choose_bgm_dir, fg_color=BG4, text_color=T1, height=28)
        self.btn_bgm_dir.pack(side="right", fill="x", expand=True, padx=(2, 0))

        self.lbl_bgm = ctk.CTkLabel(f_bgm, text="Chưa chọn nhạc", font=F(11), text_color=T3)
        self.lbl_bgm.pack(pady=2)

        # Loop BGM checkbox
        self.loop_bgm_var = ctk.BooleanVar(value=True)
        self.chk_loop = ctk.CTkCheckBox(f_bgm, text="Lặp lại nhạc (nếu nhạc ngắn hơn video)\n* Tắt để tự nối tiếp nhạc ngẫu nhiên khác", variable=self.loop_bgm_var, font=F(11), text_color=T2)
        self.chk_loop.pack(pady=(0, 10))

        # 3. SETTINGS
        f_cfg = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_cfg.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_cfg, text="3. Cài Đặt Âm Lượng & Độ Phân Giải", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Original Video volume
        f_v_vol = ctk.CTkFrame(f_cfg, fg_color="transparent")
        f_v_vol.pack(fill="x", padx=10, pady=2)
        self.lbl_v_vol = ctk.CTkLabel(f_v_vol, text="Âm lượng video gốc: 100%", font=F(11), text_color=T2)
        self.lbl_v_vol.pack(side="left")
        self.slider_v_vol = ctk.CTkSlider(f_cfg, from_=0.0, to=1.5, number_of_steps=150, height=16, command=self.on_v_vol_changed)
        self.slider_v_vol.set(1.0)
        self.slider_v_vol.pack(fill="x", padx=10, pady=(0, 5))

        # BGM volume (default to 35% as requested: 30-40% range)
        f_b_vol = ctk.CTkFrame(f_cfg, fg_color="transparent")
        f_b_vol.pack(fill="x", padx=10, pady=2)
        self.lbl_b_vol = ctk.CTkLabel(f_b_vol, text="Âm lượng nhạc nền BGM: 35%", font=F(11), text_color=T2)
        self.lbl_b_vol.pack(side="left")
        self.slider_b_vol = ctk.CTkSlider(f_cfg, from_=0.0, to=1.5, number_of_steps=150, height=16, command=self.on_b_vol_changed)
        self.slider_b_vol.set(0.35)
        self.slider_b_vol.pack(fill="x", padx=10, pady=(0, 10))

        # Resolution dropdown
        f_res = ctk.CTkFrame(f_cfg, fg_color="transparent")
        f_res.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_res, text="Độ phân giải đầu ra:", font=F(11), text_color=T2).pack(side="left")
        self.combo_res = ctk.CTkComboBox(
            f_res, 
            values=["Giữ nguyên độ phân giải gốc", "1080p (Ngang 1920x1080 / Dọc 1080x1920)", "720p (Ngang 1280x720 / Dọc 720x1280)"], 
            width=180, height=24, font=F(11)
        )
        self.combo_res.set("1080p (Ngang 1920x1080 / Dọc 1080x1920)")
        self.combo_res.pack(side="right")

        # 4. OUTPUT DIR
        f_out = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_out.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_out, text="4. Chọn Thư Mục Lưu Video", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))
        self.btn_out = ctk.CTkButton(f_out, text="💾 Chọn Nơi Lưu", command=self.choose_output_dir, fg_color=BLU, text_color=BG, font=F(11, "bold"), height=28)
        self.btn_out.pack(fill="x", padx=10, pady=4)
        self.lbl_out_dir = ctk.CTkLabel(f_out, text="Mặc định: outputs/BGM_Injector", font=F(11), text_color=T3)
        self.lbl_out_dir.pack(pady=(0, 5))

        # Save settings button
        self.btn_save_cfg = ctk.CTkButton(left_frame, text="💾 LƯU CẤU HÌNH & THIẾT LẬP", command=self.save_settings, fg_color=BG4, text_color=T1, height=32)
        self.btn_save_cfg.pack(fill="x", padx=10, pady=10)

        # ACTION BUTTONS
        self.btn_start = ctk.CTkButton(left_frame, text="🚀 BẮT ĐẦU GHÉP NHẠC HÀNG LOẠT", command=self.start_processing, fg_color=GRN, text_color=BG, font=F(14, "bold"), height=40)
        self.btn_start.pack(fill="x", padx=10, pady=5)
        self.btn_stop = ctk.CTkButton(left_frame, text="🛑 DỪNG LẠI", command=self.stop_processing, fg_color=RED, text_color=BG, font=F(14, "bold"), height=40, state="disabled")
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 15))


        # --- RIGHT PANEL: LOGS ---
        right_frame = ctk.CTkFrame(self, fg_color=BG2, corner_radius=10)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)

        ctk.CTkLabel(right_frame, text="📋 NHẬT KÝ HOẠT ĐỘNG", font=F(14, "bold"), text_color=T1).pack(pady=(15, 5))

        self.progress_bar = ctk.CTkProgressBar(right_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=5)

        self.lbl_status = ctk.CTkLabel(right_frame, text="Sẵn sàng...", font=F(12, "bold"), text_color=ORG)
        self.lbl_status.pack(pady=2)

        self.logs_box = ctk.CTkTextbox(right_frame, font=F(11, "bold"), fg_color="#0D1117", text_color="#A3E635")
        self.logs_box.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.logs_box.configure(state="disabled")

    # --- EVENT HANDLERS ---
    def on_v_vol_changed(self, val):
        self.lbl_v_vol.configure(text=f"Âm lượng video gốc: {int(float(val)*100)}%")

    def on_b_vol_changed(self, val):
        self.lbl_b_vol.configure(text=f"Âm lượng nhạc nền BGM: {int(float(val)*100)}%")

    def choose_input_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Chứa Video Gốc")
        if folder:
            valid_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.ts', '.3gp')
            self.video_paths = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(valid_exts)]
            self._update_loaded_label()

    def choose_input_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn các video tệp lẻ",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.3gp"), ("All Files", "*.*")]
        )
        if files:
            self.video_paths = list(files)
            self._update_loaded_label()

    def _update_loaded_label(self):
        if self.video_paths:
            self.lbl_loaded.configure(text=f"Đã nạp: {len(self.video_paths)} videos", text_color=GRN)
            self.log(f"🔎 Đã nạp {len(self.video_paths)} video vào danh sách chờ xử lý.")
        else:
            self.lbl_loaded.configure(text="Chưa nạp video", text_color=T3)

    def choose_bgm_file(self):
        path = filedialog.askopenfilename(
            title="Chọn Tệp Nhạc Nền BGM (Audio/Video)",
            filetypes=[("Media Files", "*.mp3 *.wav *.m4a *.ogg *.aac *.mp4 *.mov *.avi *.mkv"), ("All Files", "*.*")]
        )
        if path:
            self.bgm_path = path
            self.lbl_bgm.configure(text=os.path.basename(path), text_color=GRN)
            self.log(f"🎵 Đã chọn nhạc nền lẻ: {os.path.basename(path)}")

    def choose_bgm_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Nhạc Nền")
        if folder:
            self.bgm_path = folder
            self.lbl_bgm.configure(text=f"Thư mục: .../{os.path.basename(folder)}", text_color=GRN)
            self.log(f"📂 Đã chọn thư mục nhạc nền: {folder}")

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Lưu Video Thành Phẩm")
        if folder:
            self.output_dir = folder
            self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(folder)}", text_color=GRN)
            self.log(f"📂 Thư mục đầu ra được đổi thành: {folder}")

    def log(self, message):
        def _append():
            self.logs_box.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs_box.insert("end", f"[{ts}] {message}\n")
            self.logs_box.see("end")
            self.logs_box.configure(state="disabled")
        self.after(0, _append)

        # Write to log file
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_injector_run.log")
        try:
            full_ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{full_ts}] {message}\n")
        except Exception as e:
            print(f"Failed to append to log file: {e}")

    # --- SAVE / LOAD CONFIGS ---
    def save_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_injector_settings.json")
        try:
            data = {
                "bgm_path": self.bgm_path,
                "loop_bgm": self.loop_bgm_var.get(),
                "v_vol": float(self.slider_v_vol.get()),
                "b_vol": float(self.slider_b_vol.get()),
                "resolution": self.combo_res.get(),
                "output_dir": self.output_dir
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.log("💾 Đã lưu cấu hình và thiết lập gắn nhạc thành công!")
            messagebox.showinfo("Lưu cấu hình", "Lưu cấu hình giao diện thành công!")
        except Exception as e:
            self.log(f"❌ Không thể lưu cấu hình: {e}")
            messagebox.showerror("Lỗi lưu", f"Lỗi khi lưu cấu hình: {e}")

    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_injector_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.bgm_path = data.get("bgm_path", "")
                if self.bgm_path:
                    if os.path.isdir(self.bgm_path):
                        self.lbl_bgm.configure(text=f"Thư mục: .../{os.path.basename(self.bgm_path)}", text_color=GRN)
                    else:
                        self.lbl_bgm.configure(text=os.path.basename(self.bgm_path), text_color=GRN)

                self.loop_bgm_var.set(data.get("loop_bgm", True))
                
                v_vol = data.get("v_vol", 1.0)
                self.slider_v_vol.set(v_vol)
                self.on_v_vol_changed(v_vol)

                b_vol = data.get("b_vol", 0.35)
                self.slider_b_vol.set(b_vol)
                self.on_b_vol_changed(b_vol)

                self.combo_res.set(data.get("resolution", "1080p (Ngang 1920x1080 / Dọc 1080x1920)"))
                
                self.output_dir = data.get("output_dir", "")
                if self.output_dir and os.path.exists(self.output_dir):
                    self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(self.output_dir)}", text_color=GRN)

                self.log("💾 Đã tự động nạp cấu hình gắn nhạc nền thành công.")
            except Exception as e:
                print(f"Failed to load settings: {e}")

    # --- PROCESS TIMELINE ---
    def start_processing(self):
        if self.is_running:
            return
        if not self.video_paths:
            self.log("⚠️ Không có video nào để gắn nhạc! Vui lòng nạp video trước.")
            messagebox.showwarning("Thiếu video", "Vui lòng chọn thư mục hoặc tệp video đầu vào!")
            return
        if not self.bgm_path or not os.path.exists(self.bgm_path):
            self.log("⚠️ Chưa chọn nhạc nền BGM hợp lệ!")
            messagebox.showwarning("Thiếu nhạc nền", "Vui lòng chọn tệp nhạc hoặc thư mục nhạc nền!")
            return

        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", fg_color="#94A3B8")
        self.btn_stop.configure(state="normal")
        self.btn_load_dir.configure(state="disabled")
        self.btn_load_files.configure(state="disabled")
        self.btn_bgm_file.configure(state="disabled")
        self.btn_bgm_dir.configure(state="disabled")
        self.btn_out.configure(state="disabled")

        threading.Thread(target=self.processing_worker, daemon=True).start()

    def stop_processing(self):
        if self.is_running:
            self.log("🛑 Đang dừng tiến trình xử lý hàng loạt...")
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="ĐANG DỪNG...")

    def processing_worker(self):
        try:
            out_dir = self.output_dir
            if not out_dir:
                # Default output directory
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                out_dir = os.path.join(current_dir, "outputs", "BGM_Injector")
            os.makedirs(out_dir, exist_ok=True)

            self.log(f"🚀 BẮT ĐẦU TIẾN TRÌNH GẮN NHẠC HÀNG LOẠT ({len(self.video_paths)} VIDEOS)...")
            self.log(f"📂 Thư mục xuất bản: {out_dir}")

            codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
            preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "superfast", "-crf", "20"]

            # Scan BGM directory if a folder is selected
            bgm_files = []
            if os.path.isdir(self.bgm_path):
                # Accept both audio files and video files containing audio!
                valid_media_exts = ('.mp3', '.wav', '.m4a', '.ogg', '.aac', '.mp4', '.mov', '.avi', '.mkv', '.webm')
                all_files = [os.path.join(self.bgm_path, f) for f in os.listdir(self.bgm_path) if f.lower().endswith(valid_media_exts)]
                # Filter to only keep files that have audio track
                for f in all_files:
                    inf = get_video_info(f)
                    if inf["has_audio"]:
                        bgm_files.append(f)

                if not bgm_files:
                    raise ValueError(f"Không tìm thấy tệp chứa nhạc hợp lệ nào trong thư mục: {self.bgm_path}")
                self.log(f"🔎 Đã quét và chọn lọc được {len(bgm_files)} tệp nhạc nền trong thư mục.")

            success_count = 0
            total_videos = len(self.video_paths)
            resolution_mode = self.combo_res.get()
            video_vol = float(self.slider_v_vol.get())
            bgm_vol = float(self.slider_b_vol.get())
            loop_bgm = self.loop_bgm_var.get()

            for idx, v_path in enumerate(self.video_paths):
                if self.stop_event.is_set():
                    raise InterruptedError("Dừng bởi người dùng.")

                v_name = os.path.basename(v_path)
                self.log(f"[{idx+1}/{total_videos}] ⚙️ Đang ghép nhạc cho video: {v_name}")
                self.after(0, lambda i=idx, n=total_videos, vn=v_name: (
                    self.progress_bar.set((i + 1) / n),
                    self.lbl_status.configure(text=f"Đang xử lý {i+1}/{n}: {vn}")
                ))

                # Analyze video info
                info = get_video_info(v_path)
                v_dur = info["duration"] if info["duration"] > 0 else 30.0

                # Determine BGM sequence for this video
                bgm_seq = []
                if bgm_files and not loop_bgm:
                    # Random playlist mode: pick multiple random songs until we cover the video length
                    accumulated_dur = 0.0
                    safety_count = 0
                    while accumulated_dur < v_dur and safety_count < 30:
                        choice = random.choice(bgm_files)
                        choice_info = get_video_info(choice)
                        choice_dur = choice_info["duration"] if choice_info["duration"] > 0 else 180.0
                        bgm_seq.append((choice, choice_info))
                        accumulated_dur += choice_dur
                        safety_count += 1
                else:
                    # Single file or loop BGM mode
                    if bgm_files:
                        choice = random.choice(bgm_files)
                        bgm_seq.append((choice, get_video_info(choice)))
                    else:
                        bgm_seq.append((self.bgm_path, get_video_info(self.bgm_path)))

                # Output resolution configuration
                filter_parts = []
                w_out, h_out = info["width"], info["height"]

                if "1080p" in resolution_mode:
                    if info["width"] >= info["height"]:
                        w_out, h_out = 1920, 1080
                    else:
                        w_out, h_out = 1080, 1920
                elif "720p" in resolution_mode:
                    if info["width"] >= info["height"]:
                        w_out, h_out = 1280, 720
                    else:
                        w_out, h_out = 720, 1280

                # Video filter complex vs stream copy optimization
                use_copy = False
                if resolution_mode == "Giữ nguyên độ phân giải gốc":
                    use_copy = True
                elif w_out == info["width"] and h_out == info["height"]:
                    use_copy = True

                v_stream_out = "0:v"
                if not use_copy:
                    v_stream_out = "[v_scaled]"
                    filter_parts.append(f"[0:v]scale={w_out}:{h_out},format=yuv420p{v_stream_out}")

                # Build BGM audio inputs and filter chains
                # Input 0: Video file
                # Input 1 to N: BGM files
                cmd = ["ffmpeg", "-y", "-i", v_path]
                
                if len(bgm_seq) == 1 and loop_bgm:
                    # Loop a single BGM file infinitely
                    cmd.extend(["-stream_loop", "-1", "-i", bgm_seq[0][0]])
                else:
                    # Add each unique BGM file in the playlist sequence as an input
                    for bgm_item in bgm_seq:
                        cmd.extend(["-i", bgm_item[0]])

                # Format and normalize BGM audio streams to standard stereo 44.1kHz
                bgm_filter_outs = []
                for i in range(len(bgm_seq)):
                    in_idx = i + 1
                    a_out = f"[bgm_conv{i}]"
                    filter_parts.append(f"[{in_idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,aresample=async=1{a_out}")
                    bgm_filter_outs.append(a_out)

                # Concatenate BGM playlist sequence in-memory
                if len(bgm_filter_outs) > 1:
                    concat_in = "".join(bgm_filter_outs)
                    filter_parts.append(f"{concat_in}concat=n={len(bgm_filter_outs)}:v=0:a=1[bgm_concat]")
                    bgm_merged = "[bgm_concat]"
                else:
                    bgm_merged = bgm_filter_outs[0]

                # Mix BGM and primary audio
                filter_parts.append(f"{bgm_merged}volume={bgm_vol}[bgm_final]")

                a_stream_out = "[a_final]"
                if info["has_audio"]:
                    filter_parts.append(f"[0:a]volume={video_vol}[v_a]")
                    filter_parts.append(f"[v_a][bgm_final]amix=inputs=2:duration=first:dropout_transition=2{a_stream_out}")
                else:
                    # BGM only
                    filter_parts.append(f"[bgm_final]aformat=sample_rates=44100:channel_layouts=stereo{a_stream_out}")

                # Configure mapping and filters
                cmd.extend(["-filter_complex", ";".join(filter_parts)])
                cmd.extend(["-map", v_stream_out, "-map", a_stream_out])

                # Stop output when video duration ends
                if v_dur > 0:
                    cmd.extend(["-t", f"{v_dur:.3f}"])
                else:
                    cmd.extend(["-shortest"])

                # Add CapCut-Style iPhone metadata tags for anti-reup
                capcut_meta = [
                    "-map_metadata", "-1",
                    "-fflags", "+bitexact",
                    "-flags:v", "+bitexact",
                    "-flags:a", "+bitexact",
                    "-metadata:g", "major_brand=qt",
                    "-metadata:g", "minor_version=512",
                    "-metadata:g", "compatible_brands=qt",
                    "-metadata:g", "com.apple.quicktime.full-frame-rate-playback-intent=1",
                    "-metadata:g", "com.apple.quicktime.make=Apple",
                    "-metadata:g", "com.apple.quicktime.model=iPhone 17 Pro Max",
                    "-metadata:g", "com.apple.quicktime.software=19.5",
                    "-metadata:g", "software=CapCut Mac v26.0.1",
                    "-metadata:s:v:0", "handler_name=Core Media Video",
                    "-metadata:s:v:0", "encoder=H.264",
                    "-metadata:s:a:0", "handler_name=Core Media Audio",
                    "-tag:v", "avc1"
                ]
                
                final_output_path = os.path.join(out_dir, f"BGM_{v_name}")
                v_codec = "copy" if use_copy else codec
                v_preset_args = [] if (use_copy or codec == "h264_videotoolbox") else ["-preset", "superfast", "-crf", "20"]

                cmd.extend([
                    "-c:v", v_codec
                ] + v_preset_args + [
                    "-c:a", "aac",
                    "-b:a", "192k"
                ] + capcut_meta + [final_output_path])

                # Run compilation
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Check for errors and run fallback
                if res.returncode != 0 and codec == "h264_videotoolbox":
                    fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in cmd]
                    try:
                        idx_codec = fallback_cmd.index("libx264")
                        fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "superfast", "-crf", "20"] + fallback_cmd[idx_codec+1:]
                    except ValueError:
                        pass
                    res = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if res.returncode == 0:
                    self.log(f"   ✅ Hoàn thành: {v_name}")
                    success_count += 1
                else:
                    self.log(f"   ❌ Lỗi ghép nhạc: {res.stderr.decode('utf-8', errors='ignore')}")

            self.log(f"\n🎉 HOÀN THÀNH: Đã ghép nhạc thành công {success_count}/{total_videos} videos!")
            self.after(0, lambda: self.lbl_status.configure(text=f"Hoàn thành {success_count}/{total_videos} videos!", text_color=GRN))

            # Copy log file to output directory
            try:
                dest_log = os.path.join(out_dir, "bgm_injector_run.log")
                src_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_injector_run.log")
                if os.path.exists(src_log):
                    shutil.copy2(src_log, dest_log)
            except Exception as log_err:
                print(f"Failed to copy log: {log_err}")

            self.after(0, lambda: messagebox.showinfo("Hoàn tất", f"Đã gắn nhạc thành công {success_count}/{total_videos} videos!"))

        except InterruptedError:
            self.log("🛑 Tiến trình đã bị dừng bởi người dùng.")
            self.after(0, lambda: self.lbl_status.configure(text="Đã dừng", text_color=RED))
        except Exception as e:
            self.log(f"❌ Có lỗi xảy ra trong quá trình ghép nhạc: {e}")
            self.after(0, lambda: (
                self.lbl_status.configure(text="Lỗi xảy ra!", text_color=RED),
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}")
            ))
        finally:
            self.is_running = False
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.btn_start.configure(state="normal", fg_color=GRN)
        self.btn_stop.configure(state="disabled", text="🛑 DỪNG LẠI")
        self.btn_load_dir.configure(state="normal")
        self.btn_load_files.configure(state="normal")
        self.btn_bgm_file.configure(state="normal")
        self.btn_bgm_dir.configure(state="normal")
        self.btn_out.configure(state="normal")
