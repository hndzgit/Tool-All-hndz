import os
import sys
import json
import time
import re
import threading
import tempfile
import subprocess
import platform
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Premium Palette (Matching main_gui)
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

# Helper module imports
try:
    from automation.config import config as cfg
    from automation.utils.vbee_tts import check_vbee_key, test_vbee_voice, generate_vbee_audio_from_srt, process_single_vbee_sentence, parse_srt
except ImportError:
    try:
        import config.config as cfg
        from utils.vbee_tts import check_vbee_key, test_vbee_voice, generate_vbee_audio_from_srt, process_single_vbee_sentence, parse_srt
    except Exception:
        cfg = None

class TTSApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color=BG, **kwargs)

        self.is_running = False
        self.stop_event = threading.Event()
        self.current_audio_process = None

        # Danh sách giọng đọc Vbee yêu cầu + bổ sung
        self.vbee_voice_dict = {
            "Minh Quân Pro Beta (24k-pre)": "hn_male_minhquan_yt_24k-pre",
            "Minh Quân YT 24k (Stable)": "hn_male_minhquan_yt-stable",
            "Ngọc Huyền 48k (Nữ HN)": "hn_female_ngochuyen_full_48k-fhg",
            "Mạnh Dũng 24k (Nam HN)": "hn_male_manhdung_full_24k-st",
            "Ngọc Huyền 2.0 (24k-st)": "hn_female_ngochuyen_full_24k-st",
            "Mai Phương (Nữ HN)": "hn_female_maiphuong_ngam_48k-fhg",
            "Thảo Trinh (Nữ HN)": "hn_female_thaotrinh_full_48k-fhg",
            "Hương Giang (Nữ SG)": "sg_female_huonggiang_full_48k-fhg",
            "Minh Hoàng (Nam SG)": "sg_male_minhhoang_full_48k-fhg",
            "Phú Thăng (Nam HN)": "hn_male_phuthang_news65dt_44k-fhg",
            "Duy Phương (Nam Huế)": "hue_male_duyphuong_full_48k-fhg",
            "Chị Google (Tiếng Việt)": "gtts:vi",
            "Chị Google (Tiếng Anh)": "gtts:en"
        }

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Configure layout Grid (Left: Controls/Input, Right: Logs/Player)
        self.grid_columnconfigure(0, weight=6)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------
        # LEFT PANEL: CONFIG & TEXT INPUT
        # ----------------------------------------------------
        left_frame = ctk.CTkFrame(self, fg_color=BG2, corner_radius=12, border_width=1, border_color=C_BORDER)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(15, 10), pady=15)
        left_frame.grid_rowconfigure(3, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # 1. Header
        hdr_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        
        lbl_title = ctk.CTkLabel(
            hdr_frame, 
            text="🗣️ TEXT TO SPEECH (VBEE AI)", 
            font=F(16, "bold"), 
            text_color=BLU
        )
        lbl_title.pack(anchor="w")
        
        lbl_sub = ctk.CTkLabel(
            hdr_frame, 
            text="Chuyển văn bản thành giọng nói AI chuyên nghiệp với các mã giọng Vbee chất lượng cao.", 
            font=F(11), 
            text_color=T3
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # 2. Vbee API Key & Voice Selection Box
        api_box = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8, border_width=1, border_color=C_BORDER)
        api_box.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        api_box.grid_columnconfigure(1, weight=1)

        # Row 0: Vbee App ID & Key
        ctk.CTkLabel(api_box, text="App ID:", font=F(11, "bold"), text_color=T2).grid(row=0, column=0, padx=(10, 5), pady=8, sticky="w")
        self.ent_app_id = ctk.CTkEntry(api_box, font=F(11), placeholder_text="Nhập Vbee App ID...", fg_color=BG2, border_color=C_BORDER, height=28)
        self.ent_app_id.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        ctk.CTkLabel(api_box, text="API Key:", font=F(11, "bold"), text_color=T2).grid(row=0, column=2, padx=(10, 5), pady=8, sticky="w")
        self.ent_api_key = ctk.CTkEntry(api_box, font=F(11), show="•", placeholder_text="Nhập Vbee API Key...", fg_color=BG2, border_color=C_BORDER, height=28)
        self.ent_api_key.grid(row=0, column=3, padx=5, pady=8, sticky="ew")

        btn_save_key = ctk.CTkButton(
            api_box, 
            text="💾 Lưu Key", 
            width=75, 
            height=28, 
            font=F(11, "bold"), 
            fg_color=BLU, 
            hover_color="#5895F6", 
            command=self.save_api_settings
        )
        btn_save_key.grid(row=0, column=4, padx=(5, 10), pady=8)

        # Row 1: Voice Selector & Mode
        ctk.CTkLabel(api_box, text="Giọng đọc AI:", font=F(11, "bold"), text_color=T2).grid(row=1, column=0, padx=(10, 5), pady=(0, 8), sticky="w")
        
        voice_names = list(self.vbee_voice_dict.keys())
        self.cbo_voice = ctk.CTkOptionMenu(
            api_box, 
            values=voice_names, 
            font=F(12), 
            fg_color=BG2, 
            button_color=BG4, 
            button_hover_color=BLU, 
            dropdown_font=F(12), 
            height=30
        )
        self.cbo_voice.grid(row=1, column=1, columnspan=2, padx=5, pady=(0, 8), sticky="ew")
        self.cbo_voice.set("Ngọc Huyền 48k (Nữ HN)")

        self.btn_test_voice = ctk.CTkButton(
            api_box, 
            text="🎧 Nghe Thử Giọng", 
            height=30, 
            font=F(11, "bold"), 
            fg_color=BG4, 
            hover_color=BLU, 
            command=self.test_selected_voice
        )
        self.btn_test_voice.grid(row=1, column=3, columnspan=2, padx=(5, 10), pady=(0, 8), sticky="ew")

        # 3. Output Path Bar
        out_box = ctk.CTkFrame(left_frame, fg_color="transparent")
        out_box.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))
        out_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(out_box, text="Thư mục xuất:", font=F(11, "bold"), text_color=T2).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.ent_output_dir = ctk.CTkEntry(out_box, font=F(11), fg_color=BG3, border_color=C_BORDER, height=28)
        self.ent_output_dir.grid(row=0, column=1, sticky="ew")
        
        btn_browse_out = ctk.CTkButton(
            out_box, 
            text="📁 Chọn Thư Mục", 
            width=110, 
            height=28, 
            font=F(11), 
            fg_color=BG4, 
            hover_color=BLU, 
            command=self.browse_output_dir
        )
        btn_browse_out.grid(row=0, column=2, padx=(8, 4))

        btn_open_out = ctk.CTkButton(
            out_box, 
            text="📂 Mở Thư Mục", 
            width=100, 
            height=28, 
            font=F(11), 
            fg_color=BG4, 
            hover_color=BLU, 
            command=self.open_output_folder
        )
        btn_open_out.grid(row=0, column=3, padx=(0, 0))

        # 4. Text Input Area
        text_box_hdr = ctk.CTkFrame(left_frame, fg_color="transparent")
        text_box_hdr.grid(row=3, column=0, sticky="ew", padx=15, pady=(5, 0))
        
        ctk.CTkLabel(text_box_hdr, text="Văn bản cần đọc (Nội dung Kịch bản):", font=F(12, "bold"), text_color=T1).pack(side="left")
        
        btn_clear_text = ctk.CTkButton(
            text_box_hdr, 
            text="🧹 Xóa văn bản", 
            width=90, 
            height=24, 
            font=F(10), 
            fg_color="transparent", 
            hover_color=BG4, 
            text_color=RED, 
            command=lambda: self.txt_input.delete("1.0", "end")
        )
        btn_clear_text.pack(side="right", padx=(5, 0))

        btn_load_file = ctk.CTkButton(
            text_box_hdr, 
            text="📂 Nhập file (.txt/.srt)", 
            width=130, 
            height=24, 
            font=F(10, "bold"), 
            fg_color=BG4, 
            hover_color=BLU, 
            command=self.import_text_file
        )
        btn_load_file.pack(side="right")

        self.txt_input = ctk.CTkTextbox(
            left_frame, 
            font=F(13), 
            fg_color=BG3, 
            text_color=T1, 
            border_color=C_BORDER, 
            border_width=1, 
            corner_radius=8, 
            wrap="word"
        )
        self.txt_input.grid(row=4, column=0, sticky="nsew", padx=15, pady=(5, 10))

        # 5. Options & Start Action Buttons
        opt_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        opt_frame.grid(row=5, column=0, sticky="ew", padx=15, pady=(0, 15))

        self.chk_export_srt = ctk.CTkCheckBox(
            opt_frame, 
            text="Xuất kèm file phụ đề (.SRT) chuẩn thời gian", 
            font=F(11), 
            text_color=T2, 
            fg_color=BLU, 
            hover_color="#5895F6"
        )
        self.chk_export_srt.pack(side="left")
        self.chk_export_srt.select()

        self.btn_start = ctk.CTkButton(
            opt_frame, 
            text="▶ TẠO GIỌNG NÓI AI", 
            width=160, 
            height=36, 
            font=F(13, "bold"), 
            fg_color=GRN, 
            text_color="#11111B", 
            hover_color="#8BD486", 
            command=self.start_tts_process
        )
        self.btn_start.pack(side="right", padx=(10, 0))

        self.btn_stop = ctk.CTkButton(
            opt_frame, 
            text="⏹ DỪNG", 
            width=80, 
            height=36, 
            font=F(12, "bold"), 
            fg_color=RED, 
            text_color="#11111B", 
            hover_color="#E86E8D", 
            command=self.stop_process, 
            state="disabled"
        )
        self.btn_stop.pack(side="right")

        # ----------------------------------------------------
        # RIGHT PANEL: LOGS & PLAYER
        # ----------------------------------------------------
        right_frame = ctk.CTkFrame(self, fg_color=BG2, corner_radius=12, border_width=1, border_color=C_BORDER)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Log Header
        log_hdr = ctk.CTkFrame(right_frame, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        ctk.CTkLabel(log_hdr, text="📋 TIẾN TRÌNH XỬ LÝ", font=F(13, "bold"), text_color=BLU).pack(side="left")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(right_frame, height=6, fg_color=BG3, progress_color=BLU)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(40, 0))
        self.progress_bar.set(0)

        # Log Text Box
        self.txt_log = ctk.CTkTextbox(
            right_frame, 
            font=("Menlo", 11), 
            fg_color=BG3, 
            text_color=T2, 
            border_color=C_BORDER, 
            border_width=1, 
            corner_radius=8
        )
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        # Audio Player Frame
        player_frame = ctk.CTkFrame(right_frame, fg_color=BG3, corner_radius=8, border_width=1, border_color=C_BORDER)
        player_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))

        self.lbl_playing = ctk.CTkLabel(player_frame, text="🎧 Trình nghe thử audio:", font=F(11, "bold"), text_color=T2)
        self.lbl_playing.pack(anchor="w", padx=10, pady=(8, 2))

        self.lbl_file_info = ctk.CTkLabel(player_frame, text="Chưa có file audio nào được mở", font=F(10), text_color=T3)
        self.lbl_file_info.pack(anchor="w", padx=10, pady=(0, 8))

        btn_ctrl_frame = ctk.CTkFrame(player_frame, fg_color="transparent")
        btn_ctrl_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_play_audio = ctk.CTkButton(
            btn_ctrl_frame, 
            text="▶ Phát Audio", 
            font=F(11, "bold"), 
            fg_color=BLU, 
            hover_color="#5895F6", 
            height=28, 
            command=self.play_current_audio
        )
        self.btn_play_audio.pack(side="left", padx=(0, 5), expand=True, fill="x")

        self.btn_stop_audio = ctk.CTkButton(
            btn_ctrl_frame, 
            text="⏹ Dừng", 
            font=F(11, "bold"), 
            fg_color=BG4, 
            hover_color=RED, 
            height=28, 
            command=self.stop_current_audio
        )
        self.btn_stop_audio.pack(side="left", padx=5, expand=True, fill="x")

        self.last_generated_audio = None

    def log(self, text):
        """Thêm dòng thông báo vào khung Log"""
        self.txt_log.insert("end", f"{text}\n")
        self.txt_log.see("end")

    def load_settings(self):
        """Tải cấu hình từ file settings.json chung của app"""
        if cfg and hasattr(cfg, 'load_settings'):
            s = cfg.load_settings()
            app_id = s.get("vbee_app_id", "")
            api_key = s.get("vbee_api_key", "")
            voice_code = s.get("vbee_voice", "hn_female_ngochuyen_full_48k-fhg")
            output_dir = s.get("output_dir", os.path.expanduser("~/Documents"))
        else:
            app_id = ""
            api_key = ""
            voice_code = "hn_female_ngochuyen_full_48k-fhg"
            output_dir = os.path.expanduser("~/Documents")

        self.ent_app_id.delete(0, "end")
        self.ent_app_id.insert(0, app_id)

        self.ent_api_key.delete(0, "end")
        self.ent_api_key.insert(0, api_key)

        self.ent_output_dir.delete(0, "end")
        self.ent_output_dir.insert(0, output_dir)

        # Chọn giọng đọc tương ứng
        for name, code in self.vbee_voice_dict.items():
            if code == voice_code or code == f"vbee:{voice_code}":
                self.cbo_voice.set(name)
                break

    def save_api_settings(self):
        """Lưu App ID và API Key vào settings.json"""
        app_id = self.ent_app_id.get().strip()
        api_key = self.ent_api_key.get().strip()
        voice_name = self.cbo_voice.get()
        voice_code = self.vbee_voice_dict.get(voice_name, "hn_female_ngochuyen_full_48k-fhg")

        if cfg and hasattr(cfg, 'save_settings'):
            cfg.save_settings({
                "vbee_app_id": app_id,
                "vbee_api_key": api_key,
                "vbee_voice": voice_code
            })
            messagebox.showinfo("Thành công", "Đã lưu Vbee API Key & App ID thành công!")
            self.log("✅ Đã cập nhật Vbee API Key vào cấu hình ứng dụng.")
        else:
            messagebox.showerror("Lỗi", "Không thể lưu cấu hình hệ thống.")

    def browse_output_dir(self):
        folder = filedialog.askdirectory(title="Chọn thư mục lưu file audio")
        if folder:
            self.ent_output_dir.delete(0, "end")
            self.ent_output_dir.insert(0, folder)

    def open_output_folder(self):
        folder = self.ent_output_dir.get().strip()
        if folder and os.path.exists(folder):
            if platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            elif platform.system() == "Windows":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
        else:
            messagebox.showwarning("Cảnh báo", "Thư mục xuất không tồn tại hoặc chưa được tạo!")

    def import_text_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file văn bản hoặc phụ đề",
            filetypes=[("Text & SRT Files", "*.txt *.srt"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.txt_input.delete("1.0", "end")
            self.txt_input.insert("1.0", content)
            self.log(f"📄 Đã nạp thành công nội dung từ file: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Lỗi đọc file", f"Không thể đọc file: {e}")

    def test_selected_voice(self):
        """Chạy thử nghiệm 1 câu với giọng đọc Vbee đã chọn"""
        app_id = self.ent_app_id.get().strip()
        api_key = self.ent_api_key.get().strip()
        voice_name = self.cbo_voice.get()
        voice_code = self.vbee_voice_dict.get(voice_name, "hn_female_ngochuyen_full_48k-fhg")

        if voice_code.startswith("vbee:"):
            voice_code = voice_code[5:]

        if not voice_code.startswith("gtts:"):
            if not app_id or not api_key:
                messagebox.showwarning("Thiếu API Key", "Vui lòng nhập Vbee App ID và API Key trước khi thử giọng!")
                return

        # Lưu nhanh API key trước khi thử
        if cfg and hasattr(cfg, 'save_settings'):
            cfg.save_settings({"vbee_app_id": app_id, "vbee_api_key": api_key})

        self.log(f"🎙️ Đang nghe thử giọng Vbee [{voice_name}] ({voice_code})...")
        
        def run_test():
            try:
                if voice_code.startswith("gtts:"):
                    from gtts import gTTS
                    temp_mp3 = os.path.join(tempfile.gettempdir(), "test_gtts.mp3")
                    tts = gTTS(text="Chào bạn, đây là giọng đọc thử nghiệm Google TTS.", lang=voice_code.split(":")[1])
                    tts.save(temp_mp3)
                    audio_path = temp_mp3
                else:
                    audio_path = test_vbee_voice(voice_code)

                if audio_path and os.path.exists(audio_path):
                    self.log(f"✅ Tạo thử giọng thành công: {audio_path}")
                    self.last_generated_audio = audio_path
                    self.lbl_file_info.configure(text=f"File: {os.path.basename(audio_path)}")
                    self.play_audio_file(audio_path)
                else:
                    self.log(f"❌ Nghe thử thất bại. Vui lòng kiểm tra lại App ID/API Key Vbee.")
            except Exception as e:
                self.log(f"❌ Lỗi nghe thử giọng: {e}")

        threading.Thread(target=run_test, daemon=True).start()

    def start_tts_process(self):
        text_content = self.txt_input.get("1.0", "end").strip()
        if not text_content:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập hoặc dán nội dung văn bản cần chuyển thành giọng nói!")
            return

        app_id = self.ent_app_id.get().strip()
        api_key = self.ent_api_key.get().strip()
        voice_name = self.cbo_voice.get()
        voice_code = self.vbee_voice_dict.get(voice_name, "hn_female_ngochuyen_full_48k-fhg")

        if not voice_code.startswith("gtts:") and (not app_id or not api_key):
            messagebox.showwarning("Thiếu API Key", "Vui lòng nhập Vbee App ID và API Key trước khi thực hiện!")
            return

        out_dir = self.ent_output_dir.get().strip()
        if not out_dir:
            out_dir = os.path.expanduser("~/Documents")
            self.ent_output_dir.delete(0, "end")
            self.ent_output_dir.insert(0, out_dir)

        os.makedirs(out_dir, exist_ok=True)

        # Lưu cài đặt API key
        if cfg and hasattr(cfg, 'save_settings'):
            cfg.save_settings({"vbee_app_id": app_id, "vbee_api_key": api_key, "vbee_voice": voice_code})

        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)

        threading.Thread(target=self.process_worker, args=(text_content, voice_code, out_dir), daemon=True).start()

    def stop_process(self):
        if self.is_running:
            self.stop_event.set()
            self.is_running = False
            self.log("⏹ Người dùng đã nhấn dừng tiến trình.")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def process_worker(self, text_content, voice_code, out_dir):
        try:
            self.log("=" * 45)
            self.log("🚀 Bắt đầu tiến trình chuyển đổi văn bản sang giọng nói...")
            self.progress_bar.set(0.1)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            temp_srt = os.path.join(tempfile.gettempdir(), f"tts_script_{timestamp}.srt")
            out_mp3 = os.path.join(out_dir, f"vbee_audio_{timestamp}.mp3")
            out_srt = os.path.join(out_dir, f"vbee_audio_{timestamp}.srt")

            # 1. Phân tích nội dung văn bản thành định dạng câu/SRT
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]
            if not lines:
                raise Exception("Không tìm thấy dòng chữ nào để xử lý.")

            # Nếu văn bản đã có timecode SRT hoặc chỉ là văn bản thường
            is_srt_format = bool(re.search(r'\d{2}:\d{2}:\d{2},\d{3}', text_content))
            
            if is_srt_format:
                with open(temp_srt, "w", encoding="utf-8") as f:
                    f.write(text_content)
            else:
                # Tạo file SRT tạm với thời lượng ước tính cho từng câu
                with open(temp_srt, "w", encoding="utf-8") as f:
                    for idx, line in enumerate(lines):
                        f.write(f"{idx+1}\n")
                        f.write(f"00:00:00,000 --> 00:00:05,000\n")
                        f.write(f"{line}\n\n")

            self.log(f"🎙️ Giọng đọc chọn: {voice_code}")
            self.log(f"📝 Số câu cần tổng hợp giọng nói: {len(lines)}")
            self.progress_bar.set(0.3)

            # 2. Xử lý Vbee API đa luồng từ vbee_tts.py
            clean_voice_code = voice_code[5:] if voice_code.startswith("vbee:") else voice_code

            if voice_code.startswith("gtts:"):
                from gTTS import gTTS
                self.log("🎙️ Đang tạo audio bằng Google TTS...")
                lang_code = voice_code.split(":")[1]
                full_text = ". ".join(lines)
                tts = gTTS(text=full_text, lang=lang_code)
                tts.save(out_mp3)
            else:
                self.log("⚡ Gọi Vbee Multithread Engine (AI Pipeline)...")
                res_path = generate_vbee_audio_from_srt(temp_srt, out_mp3, voice_code=clean_voice_code)
                if not res_path or not os.path.exists(out_mp3):
                    raise Exception("Không thể tạo file âm thanh từ Vbee API.")

            self.progress_bar.set(0.9)

            # 3. Xuất file SRT nếu người dùng bật tùy chọn
            if self.chk_export_srt.get() and os.path.exists(temp_srt):
                import shutil
                shutil.copy(temp_srt, out_srt)
                self.log(f"📜 Đã xuất file phụ đề SRT: {out_srt}")

            self.progress_bar.set(1.0)
            self.log("🎉 XỬ LÝ HOÀN TẤT CHUẨN XÁC 100%!")
            self.log(f"🔊 File Audio MP3: {out_mp3}")
            self.log("=" * 45)

            self.last_generated_audio = out_mp3
            self.lbl_file_info.configure(text=f"File: {os.path.basename(out_mp3)}")

            # Tự động mở trình nghe audio file vừa tạo
            self.play_audio_file(out_mp3)

        except Exception as e:
            self.log(f"❌ Lỗi tiến trình TTS: {e}")
        finally:
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def play_current_audio(self):
        if self.last_generated_audio and os.path.exists(self.last_generated_audio):
            self.play_audio_file(self.last_generated_audio)
        else:
            messagebox.showinfo("Thông báo", "Chưa có file audio nào để phát. Vui lòng tạo giọng nói trước!")

    def play_audio_file(self, file_path):
        """Phát audio qua hệ thống không làm treo GUI"""
        self.stop_current_audio()
        
        def run_player():
            try:
                system_name = platform.system()
                if system_name == "Darwin":  # macOS
                    self.current_audio_process = subprocess.Popen(["afplay", file_path])
                elif system_name == "Windows":
                    self.current_audio_process = subprocess.Popen(["powershell", "-c", f'(New-Object Media.SoundPlayer "{file_path}").PlaySync()'])
                else:  # Linux
                    self.current_audio_process = subprocess.Popen(["aplay", file_path])
                
                self.current_audio_process.wait()
            except Exception as e:
                print(f"Lỗi khi phát audio: {e}")

        threading.Thread(target=run_player, daemon=True).start()

    def stop_current_audio(self):
        if self.current_audio_process and self.current_audio_process.poll() is None:
            try:
                self.current_audio_process.terminate()
            except Exception:
                pass
            self.current_audio_process = None
