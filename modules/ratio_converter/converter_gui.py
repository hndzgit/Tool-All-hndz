import os
import threading
import time
import subprocess
import platform
import customtkinter as ctk
from customtkinter import filedialog

class ConverterApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.video_paths = []
        self.output_dir = ""
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        # UI Colors
        T1, T2, T3 = "#FFFFFF", "#E2E8F0", "#94A3B8"
        BORDER = "#334155"
        ORG = "#F59E0B"
        GRN = "#22C55E"
        RED = "#EF4444"

        # --- ĐẦU VÀO ---
        f_in = ctk.CTkFrame(self, fg_color="transparent")
        f_in.pack(fill="x", padx=40, pady=(20, 5))
        
        self.btn_load_dir = ctk.CTkButton(f_in, text="📂 Chọn Thư Mục", font=ctk.CTkFont(size=13, weight="bold"), height=35, fg_color=BORDER, command=self.load_directory)
        self.btn_load_dir.pack(side="left", padx=(0, 10))
        
        self.btn_load_files = ctk.CTkButton(f_in, text="🎞 Chọn File Tùy Ý", font=ctk.CTkFont(size=13, weight="bold"), height=35, fg_color=BORDER, command=self.load_files)
        self.btn_load_files.pack(side="left")
        
        self.lbl_loaded = ctk.CTkLabel(f_in, text="Chưa nạp video", text_color=T3, font=ctk.CTkFont(size=13))
        self.lbl_loaded.pack(side="left", padx=15)

        # --- ĐẦU RA ---
        f_out = ctk.CTkFrame(self, fg_color="transparent")
        f_out.pack(fill="x", padx=40, pady=(5, 10))
        
        self.btn_out = ctk.CTkButton(f_out, text="💾 Chọn Nơi Lưu", font=ctk.CTkFont(size=13, weight="bold"), height=35, fg_color="#3B82F6", hover_color="#2563EB", command=self.choose_output_dir)
        self.btn_out.pack(side="left", padx=(0, 10))
        
        self.lbl_out = ctk.CTkLabel(f_out, text="Mặc định: Tự lưu vào thư mục gốc của video", text_color=T3, font=ctk.CTkFont(size=13))
        self.lbl_out.pack(side="left")
        
        # --- CẤU HÌNH ---
        f_config = ctk.CTkFrame(self, fg_color="transparent")
        f_config.pack(fill="x", padx=40, pady=10)
        
        ctk.CTkLabel(f_config, text="ℹ️ Chức năng: Tự động chuyển đổi video từ màn hình Ngang (16:9) sang màn hình Dọc (9:16).", text_color=T2, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        
        # --- ACTIONS ---
        f_actions = ctk.CTkFrame(self, fg_color="transparent")
        f_actions.pack(pady=20)
        
        self.btn_start = ctk.CTkButton(f_actions, text="🔄 BẮT ĐẦU CHUYỂN ĐỔI", font=ctk.CTkFont(size=16, weight="bold"), height=50, width=250, fg_color=ORG, hover_color="#D97706", command=self.start_conversion)
        self.btn_start.pack(side="left", padx=10)
        
        self.btn_stop = ctk.CTkButton(f_actions, text="🛑 DỪNG", font=ctk.CTkFont(size=16, weight="bold"), height=50, width=120, fg_color=RED, hover_color="#CC0000", command=self.stop_conversion, state="disabled")
        self.btn_stop.pack(side="left", padx=10)

        # --- LOGS ---
        self.logs = ctk.CTkTextbox(self, text_color="#A3E635", fg_color="#0D1117", corner_radius=10, border_width=1, border_color="#30363D")
        self.logs.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        self.logs.configure(state="disabled")

        info_text = "💡 Lưu ý: Việc chuyển đổi tỷ lệ khung hình có dùng hiệu ứng Blur sẽ mất khoảng 1-2 phút mỗi video.\nHệ thống đã bật tăng tốc phần cứng (VideoToolbox trên Mac) để tiết kiệm thời gian chờ."
        self.log(info_text)

    def log(self, msg):
        def _append():
            self.logs.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs.insert("end", f"[{ts}] {msg}\n")
            self.logs.see("end")
            self.logs.configure(state="disabled")
        self.after(0, _append)

    def load_directory(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Chứa Video Ngang")
        if not folder: return
        
        files = os.listdir(folder)
        self.video_paths = [os.path.join(folder, f) for f in files if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
        
        self._update_loaded_label()

    def load_files(self):
        files = filedialog.askopenfilenames(title="Chọn Các Video Cần Đổi", filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if not files: return
        self.video_paths = list(files)
        self._update_loaded_label()
        
    def _update_loaded_label(self):
        if self.video_paths:
            self.lbl_loaded.configure(text=f"Nạp thành công: {len(self.video_paths)} Videos", text_color="#22C55E")
            self.log(f"🔎 Đã nạp {len(self.video_paths)} video vào danh sách chờ.")
        else:
            self.lbl_loaded.configure(text="Không tìm thấy video nào!", text_color="#EF4444")

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Lưu Video Dọc")
        if folder:
            self.output_dir = folder
            self.lbl_out.configure(text=f"Đầu ra: {folder}", text_color="#22C55E")

    def stop_conversion(self):
        if self.is_running:
            self.log("🛑 Đang huỷ tiến trình...")
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="ĐANG HUỶ...")

    def start_conversion(self):
        if self.is_running: return
        if not self.video_paths:
            self.log("⚠️ Không có video nào để xử lý! Hãy nạp video trước.")
            return
            
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", fg_color="#94A3B8")
        self.btn_stop.configure(state="normal", text="🛑 DỪNG")
        self.btn_load_dir.configure(state="disabled")
        self.btn_load_files.configure(state="disabled")
        
        threading.Thread(target=self.converter_worker, daemon=True).start()

    def converter_worker(self):
        success = 0
        total = len(self.video_paths)
        
        if self.output_dir:
            self.log(f"\n🚀 BẮT ĐẦU CHUYỂN ĐỔI NGANG -> DỌC {total} VIDEO...")
            self.log(f"📂 Lưu tất cả tại: {self.output_dir}")
        else:
            self.log(f"\n🚀 BẮT ĐẦU CHUYỂN ĐỔI NGANG -> DỌC {total} VIDEO...")
        
        # Hardware acceleration
        codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
        preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "ultrafast"]
        
        for idx, input_path in enumerate(self.video_paths):
            if self.stop_event.is_set():
                self.log("🛑 Quá trình đã bị dừng bởi người dùng.")
                break
                
            v_name = os.path.basename(input_path)
            
            if self.output_dir:
                out_folder = self.output_dir
            else:
                out_folder = os.path.join(os.path.dirname(input_path), "Vertical_9x16")
                os.makedirs(out_folder, exist_ok=True)
                
            output_path = os.path.join(out_folder, v_name)
            
            # Skip if already exists
            if os.path.exists(output_path):
                self.log(f"[{idx+1}/{total}] ⏭ Bỏ qua (Đã tồn tại): {v_name}")
                success += 1
                continue
                
            # Fast downsample blur: scale to 90x160, boxblur=3:3, scale back up to 1080x1920
            filter_str = (
                "[0:v]scale=90:160:force_original_aspect_ratio=increase,crop=90:160,"
                "boxblur=3:3,scale=1080:1920[bg];"
                "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v_bokeh]"
            )
            
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", filter_str,
                "-map", "[v_bokeh]",
                "-map", "0:a?",
                "-c:v", codec
            ] + preset_args + [
                "-c:a", "copy",
                output_path
            ]
            
            try:
                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode != 0 and codec == "h264_videotoolbox":
                    # Fallback to CPU encoding if videotoolbox fails
                    fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in cmd]
                    # Inject preset args for libx264
                    try:
                        idx_codec = fallback_cmd.index("libx264")
                        fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "ultrafast"] + fallback_cmd[idx_codec+1:]
                    except ValueError:
                        pass
                    result = subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if result.returncode == 0:
                    self.log(f"   ✅ Xong: {v_name}")
                    success += 1
                else:
                    self.log(f"   ❌ Lỗi xử lý FFMPEG: {v_name}")
            except Exception as e:
                self.log(f"   ❌ Lỗi hệ thống: {e}")
                
        self.log(f"\n✅ HOÀN THÀNH: Đã chuyển đổi thành công {success}/{total} Videos!")
        
        # Reset UI
        self.is_running = False
        self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.btn_start.configure(state="normal", fg_color="#F59E0B")
        self.btn_stop.configure(state="disabled", text="🛑 DỪNG")
        self.btn_load_dir.configure(state="normal")
        self.btn_load_files.configure(state="normal")