import os
import json
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from pathlib import Path

# Thêm import config
import config.config as cfg

def F(size=12, weight="normal"):
    return ("Segoe UI", size, weight)

# Định nghĩa các tone màu chủ đạo chuyên nghiệp (Đồng bộ với main_gui)
BG = "#11111B"
BG2 = "#1E1E2E"
BG3 = "#252538"
BG4 = "#313244"
C_BORDER = "#45475A"
T1 = "#CDD6F4"
T2 = "#A6ADC8"
T_MUTED = "#585B70"
BLU = "#89B4FA"
GRN = "#A6E3A1"
RED = "#F38BA8"
ORG = "#FAB387"

class BatchCutterApp(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG)
        
        # Biến quản lý trạng thái
        self.input_dir = None
        self.input_files = []
        self.output_dir = None
        self.video_queue = []
        self.is_processing = False
        self.stop_requested = False
        
        # Load settings lưu sẵn
        self.load_settings()
        
        # Cấu hình grid co giãn
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Cột trái 320px
        self.grid_columnconfigure(1, weight=1) # Cột phải co giãn
        
        self._build_left_panel()
        self._build_right_panel()
        
        # Tự động quét thư mục hoặc file lẻ nếu đã được lưu sẵn
        if self.input_dir:
            self.scan_input_directory()
        elif self.input_files:
            self.scan_input_files()

    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "batch_cutter_settings.json")
        self.var_distort_val = False
        self.var_speed_val = "1.0x"
        self.input_files = []
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.input_dir = settings.get("input_dir", None)
                    self.input_files = settings.get("input_files", [])
                    self.output_dir = settings.get("output_dir", None)
                    legacy_speed_up = settings.get("speed_up_voice", False)
                    self.var_distort_val = settings.get("distort_voice", legacy_speed_up)
                    self.var_speed_val = settings.get("speed_factor", "1.5x" if legacy_speed_up else "1.0x")
                    return
            except Exception as e:
                print(f"Failed to load batch cutter settings: {e}")
        self.input_dir = None
        self.input_files = []
        self.output_dir = None

    def save_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "batch_cutter_settings.json")
        try:
            settings = {
                "input_dir": self.input_dir,
                "input_files": getattr(self, 'input_files', []),
                "output_dir": self.output_dir,
                "distort_voice": self.var_distort.get(),
                "speed_factor": self.var_speed.get()
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("Thành Công", "Đã lưu cấu hình mặc định thành công!")
        except Exception as e:
            messagebox.showerror("Thất Bại", f"Không thể lưu cấu hình: {e}")

    def _build_left_panel(self):
        self.left_panel = ctk.CTkFrame(self, width=320, fg_color=BG2, corner_radius=12, border_width=1, border_color=C_BORDER)
        self.left_panel.grid(row=0, column=0, padx=(15, 10), pady=15, sticky="nsew")
        self.left_panel.pack_propagate(False)
        
        # Header Tiêu đề
        lbl_title = ctk.CTkLabel(self.left_panel, text="✂️ CẮT VIDEO HÀNG LOẠT", font=F(16, "bold"), text_color=T1)
        lbl_title.pack(pady=(15, 10))
        
        lbl_desc = ctk.CTkLabel(
            self.left_panel, 
            text="Chia đôi video cực nhanh không mất chất lượng\n(Giữ nguyên 100% metadata gốc)", 
            font=F(11), 
            text_color=T2, 
            justify="center"
        )
        lbl_desc.pack(pady=(0, 15))
        
        # Nhóm Thư mục
        f_folders = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8, border_width=1, border_color=C_BORDER)
        f_folders.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(f_folders, text="ĐƯỜNG DẪN & VIDEO NGUỒN", font=F(12, "bold"), text_color=BLU).pack(pady=(10, 5))
        
        # Thư mục nguồn
        btn_in = ctk.CTkButton(f_folders, text="📂 Chọn Thư Mục Nguồn", command=self.choose_input_dir, fg_color=BG4, text_color=T1, height=28)
        btn_in.pack(pady=4, padx=10, fill="x")
        
        # Chọn video lẻ
        btn_in_files = ctk.CTkButton(f_folders, text="🎥 Chọn Video Lẻ", command=self.choose_input_files, fg_color=BG4, text_color=T1, height=28)
        btn_in_files.pack(pady=4, padx=10, fill="x")
        
        # Label hiển thị thông tin nguồn đã chọn
        initial_source_text = "Nguồn: Chưa chọn..."
        if self.input_dir:
            initial_source_text = f"Nguồn: {self._get_dir_basename(self.input_dir)}"
        elif hasattr(self, 'input_files') and self.input_files:
            initial_source_text = f"Đã chọn {len(self.input_files)} video lẻ"
            
        self.lbl_in_dir = ctk.CTkLabel(f_folders, text=initial_source_text, font=F(11), text_color=T2)
        self.lbl_in_dir.pack(pady=2)
        
        # Thư mục đầu ra
        btn_out = ctk.CTkButton(f_folders, text="📂 Chọn Thư Mục Đầu Ra", command=self.choose_output_dir, fg_color=BG4, text_color=T1, height=28)
        btn_out.pack(pady=4, padx=10, fill="x")
        self.lbl_out_dir = ctk.CTkLabel(f_folders, text=f"Đầu ra: {self._get_dir_basename(self.output_dir)}", font=F(11), text_color=T2)
        self.lbl_out_dir.pack(pady=2)
        
        # Nút Lưu cấu hình
        self.btn_save_settings = ctk.CTkButton(f_folders, text="💾 Lưu Cấu Hình Mặc Định", command=self.save_settings, fg_color=BG4, text_color=T2, height=28)
        self.btn_save_settings.pack(pady=(5, 10), padx=10, fill="x")

        # Nhóm Cấu hình phụ
        f_options = ctk.CTkFrame(self.left_panel, fg_color=BG3, corner_radius=8, border_width=1, border_color=C_BORDER)
        f_options.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(f_options, text="CẤU HÌNH HẬU XỬ LÝ", font=F(12, "bold"), text_color=BLU).pack(pady=(8, 2))
        
        # Checkbox bóp méo giọng
        self.var_distort = tk.BooleanVar(value=self.var_distort_val)
        self.cb_distort = ctk.CTkCheckBox(
            f_options, 
            text="Bóp méo giọng nói (Chipmunk)", 
            variable=self.var_distort,
            font=F(11),
            text_color=T1,
            fg_color=BLU,
            hover_color="#5892F8"
        )
        self.cb_distort.pack(pady=5, padx=15, anchor="w")
        
        # Dropdown chọn tốc độ
        f_speed = ctk.CTkFrame(f_options, fg_color="transparent")
        f_speed.pack(fill="x", padx=15, pady=(5, 10))
        
        ctk.CTkLabel(f_speed, text="Tốc độ:", font=F(11), text_color=T2).pack(side="left")
        
        self.var_speed = tk.StringVar(value=self.var_speed_val)
        self.opt_speed = ctk.CTkOptionMenu(
            f_speed,
            values=["1.0x", "1.25x", "1.5x", "1.75x", "2.0x"],
            variable=self.var_speed,
            font=F(11),
            fg_color=BG4,
            button_color=BG4,
            button_hover_color=C_BORDER,
            text_color=T1,
            width=90,
            height=24
        )
        self.opt_speed.pack(side="right")
        
        # Spacer đẩy nút xuống
        self.spacer = ctk.CTkLabel(self.left_panel, text="", fg_color="transparent")
        self.spacer.pack(pady=5, fill="both", expand=True)
        
        # Trạng thái hiện tại
        self.lbl_status = ctk.CTkLabel(self.left_panel, text="", font=F(12), text_color=ORG)
        self.lbl_status.pack(pady=5)
        
        # Nút bắt đầu cắt
        self.btn_process = ctk.CTkButton(self.left_panel, text="🚀 CẮT VIDEO HÀNG LOẠT", command=self.start_batch_cutting, fg_color=GRN, text_color=BG, font=F(14, "bold"), height=40)
        self.btn_process.pack(fill="x", padx=15, pady=(5, 15))

    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(self, fg_color=BG2, corner_radius=12, border_width=1, border_color=C_BORDER)
        self.right_panel.grid(row=0, column=1, padx=(10, 15), pady=15, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)
        
        # Header hàng đợi
        f_header = ctk.CTkFrame(self.right_panel, fg_color="transparent", height=40)
        f_header.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")
        
        lbl_queue = ctk.CTkLabel(f_header, text="📋 DANH SÁCH VIDEO CHỜ CẮT", font=F(14, "bold"), text_color=T1)
        lbl_queue.pack(side="left")
        
        self.lbl_overall_percent = ctk.CTkLabel(f_header, text="0%", font=F(13, "bold"), text_color=BLU)
        self.lbl_overall_percent.pack(side="right")
        
        # Scrollable list
        self.scroll_list = ctk.CTkScrollableFrame(self.right_panel, fg_color=BG, corner_radius=8, border_width=1, border_color=C_BORDER)
        self.scroll_list.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        
        # Thanh tiến trình tổng thể
        self.progress_bar = ctk.CTkProgressBar(self.right_panel, fg_color=BG4, progress_color=BLU, height=8)
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")

    def _get_dir_basename(self, path):
        if not path: return "Chưa chọn..."
        p = Path(path)
        if len(p.parts) > 2:
            return ".../" + os.path.join(p.parts[-2], p.parts[-1])
        return path

    def choose_input_dir(self):
        d = filedialog.askdirectory(title="Chọn Thư Mục Video Nguồn")
        if d:
            self.input_dir = d
            self.input_files = []  # Clear input_files when folder is selected
            self.lbl_in_dir.configure(text=f"Nguồn: {self._get_dir_basename(d)}")
            self.scan_input_directory()

    def choose_input_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn các video cần cắt",
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.flv *.webm *.m4v"), ("All files", "*.*")]
        )
        if files:
            self.input_files = list(files)
            self.input_dir = None  # Clear input_dir when files are selected
            self.lbl_in_dir.configure(text=f"Đã chọn {len(files)} video lẻ")
            self.scan_input_files()

    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Chọn Thư Mục Lưu Đầu Ra")
        if d:
            self.output_dir = d
            self.lbl_out_dir.configure(text=f"Đầu ra: {self._get_dir_basename(d)}")

    def scan_input_directory(self):
        if not self.input_dir or not os.path.exists(self.input_dir):
            return
            
        self.video_queue = []
        valid_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".m4v"}
        
        try:
            for item in sorted(os.listdir(self.input_dir)):
                ext = os.path.splitext(item)[1].lower()
                if ext in valid_exts:
                    self.video_queue.append({
                        "filename": item,
                        "path": os.path.join(self.input_dir, item),
                        "status": "Chờ xử lý"
                    })
        except Exception as e:
            print(f"Lỗi khi quét thư mục nguồn: {e}")
            
        self.render_queue_list()
        self.update_overall_progress(0.0, f"Đã tìm thấy {len(self.video_queue)} video.")

    def scan_input_files(self):
        if not hasattr(self, 'input_files') or not self.input_files:
            return
        self.video_queue = []
        for file_path in self.input_files:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                self.video_queue.append({
                    "filename": filename,
                    "path": file_path,
                    "status": "Chờ xử lý"
                })
        self.render_queue_list()
        self.update_overall_progress(0.0, f"Đã tìm thấy {len(self.video_queue)} video lẻ.")

    def render_queue_list(self):
        # Xóa các widget cũ
        for widget in self.scroll_list.winfo_children():
            widget.destroy()
            
        for i, item in enumerate(self.video_queue):
            f_item = ctk.CTkFrame(self.scroll_list, fg_color=BG3, corner_radius=6, height=36)
            f_item.pack(fill="x", pady=3, padx=5)
            f_item.pack_propagate(False)
            
            # Icon / STT
            lbl_stt = ctk.CTkLabel(f_item, text=f"{i+1}.", font=F(11, "bold"), text_color=T_MUTED, width=28)
            lbl_stt.pack(side="left", padx=5)
            
            # Tên file
            lbl_name = ctk.CTkLabel(f_item, text=item["filename"], font=F(11), text_color=T1, anchor="w")
            lbl_name.pack(side="left", fill="x", expand=True, padx=5)
            
            # Trạng thái
            status = item["status"]
            color = T2
            if "Hoàn tất" in status: color = GRN
            elif "Lỗi" in status: color = RED
            elif "Đang" in status: color = ORG
            
            lbl_status = ctk.CTkLabel(f_item, text=status, font=F(11, "bold"), text_color=color, width=90)
            lbl_status.pack(side="right", padx=10)

    def update_overall_progress(self, val, status_text=None):
        self.progress_bar.set(val)
        self.lbl_overall_percent.configure(text=f"{int(val * 100)}%")
        if status_text is not None:
            self.lbl_status.configure(text=status_text)

    def start_batch_cutting(self):
        if self.is_processing:
            # Yêu cầu dừng
            self.stop_requested = True
            self.btn_process.configure(text="Đang dừng...")
            return
            
        has_source = (self.input_dir and os.path.exists(self.input_dir)) or (hasattr(self, 'input_files') and self.input_files)
        if not has_source:
            messagebox.showerror("Lỗi", "Vui lòng chọn Thư mục nguồn hoặc các Video lẻ trước!")
            return
            
        if not self.output_dir or not os.path.exists(self.output_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn Thư mục đầu ra trước!")
            return
            
        if not self.video_queue:
            messagebox.showerror("Lỗi", "Không tìm thấy video nào để cắt!")
            return
            
        self.is_processing = True
        self.stop_requested = False
        self.btn_process.configure(text="🛑 DỪNG CẮT HÀNG LOẠT", fg_color=RED, hover_color="#D20F39")
        
        # Chạy Worker chạy ngầm
        threading.Thread(target=self._queue_worker_thread, daemon=True).start()

    def _get_video_duration(self, video_path):
        """Sử dụng ffprobe để lấy độ dài giây của video chuẩn xác"""
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
        
        cmd = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            try:
                return float(res.stdout.strip())
            except:
                pass
        raise Exception("Không thể đọc thời lượng video bằng ffprobe.")

    def _get_audio_info(self, video_path):
        """Kiểm tra luồng audio và lấy sample rate sử dụng ffprobe"""
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
        
        cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "a", 
            "-show_entries", "stream=sample_rate", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode == 0 and res.stdout.strip():
            try:
                return True, int(res.stdout.strip().split('\n')[0])
            except:
                pass
        return False, 44100

    def _queue_worker_thread(self):
        total_files = len(self.video_queue)
        success_count = 0
        fail_count = 0
        
        env = os.environ.copy()
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
        
        for item in self.video_queue:
            item["status"] = "Chờ xử lý"
            
        self.after(0, self.render_queue_list)
        
        for index, item in enumerate(self.video_queue):
            if self.stop_requested:
                item["status"] = "Đã dừng"
                continue
                
            item["status"] = "Đang xử lý..."
            self.after(0, self.render_queue_list)
            
            progress = (index / total_files)
            self.after(0, lambda p=progress, i=index: self.update_overall_progress(p, f"Đang xử lý: {i}/{total_files}"))
            
            try:
                video_path = item["path"]
                filename_without_ext = os.path.splitext(item["filename"])[0]
                ext = os.path.splitext(item["filename"])[1]
                
                # 1. Lấy duration bằng ffprobe
                duration = self._get_video_duration(video_path)
                if duration <= 0:
                    raise Exception("Độ dài video không hợp lệ.")
                    
                t_half = duration / 2.0
                
                # 2. Tạo thư mục riêng cho video này tại thư mục đầu ra
                target_folder = os.path.join(self.output_dir, filename_without_ext)
                os.makedirs(target_folder, exist_ok=True)
                
                out_part1 = os.path.join(target_folder, f"Phần 1 - {filename_without_ext}{ext}")
                out_part2 = os.path.join(target_folder, f"Phần 2 - {filename_without_ext}{ext}")
                
                # Phân tích cài đặt tốc độ và bóp giọng
                try:
                    speed = float(self.var_speed.get().replace("x", ""))
                except:
                    speed = 1.0
                distort = self.var_distort.get()
                need_reencode = (speed != 1.0) or distort
                
                # 3. Chạy FFmpeg cắt đôi
                self.after(0, lambda: self.lbl_status.configure(text=f"Cắt Phần 1: {item['filename']}...", text_color=ORG))
                
                if need_reencode:
                    has_audio, sample_rate = self._get_audio_info(video_path)
                    v_filter = f"[0:v]setpts=(PTS-STARTPTS)/{speed}[v]"
                    
                    if has_audio:
                        if distort:
                            pitch_factor = 1.35
                            atempo_factor = speed / pitch_factor
                            a_filter = f"[0:a]asetrate=r={int(sample_rate * pitch_factor)},atempo={atempo_factor:.5f},aresample={sample_rate}[a]"
                        else:
                            a_filter = f"[0:a]atempo={speed}[a]"
                            
                        cmd1 = [
                            "ffmpeg", "-y",
                            "-ss", "0",
                            "-to", f"{t_half:.3f}",
                            "-i", video_path,
                            "-filter_complex", f"{v_filter};{a_filter}",
                            "-map", "[v]",
                            "-map", "[a]",
                            "-c:v", "libx264", "-preset", "superfast", "-crf", "20",
                            "-c:a", "aac",
                            out_part1
                        ]
                    else:
                        cmd1 = [
                            "ffmpeg", "-y",
                            "-ss", "0",
                            "-to", f"{t_half:.3f}",
                            "-i", video_path,
                            "-filter_complex", v_filter,
                            "-map", "[v]",
                            "-c:v", "libx264", "-preset", "superfast", "-crf", "20",
                            out_part1
                        ]
                else:
                    cmd1 = [
                        "ffmpeg", "-y",
                        "-ss", "0",
                        "-to", f"{t_half:.3f}",
                        "-i", video_path,
                        "-c", "copy",
                        "-map", "0",
                        out_part1
                    ]
                
                res1 = subprocess.run(cmd1, capture_output=True, env=env)
                if res1.returncode != 0:
                    raise Exception(f"Lỗi cắt Phần 1: {res1.stderr.decode('utf-8', errors='ignore')}")
                
                self.after(0, lambda: self.lbl_status.configure(text=f"Cắt Phần 2: {item['filename']}...", text_color=ORG))
                
                if need_reencode:
                    has_audio, sample_rate = self._get_audio_info(video_path)
                    v_filter = f"[0:v]setpts=(PTS-STARTPTS)/{speed}[v]"
                    
                    if has_audio:
                        if distort:
                            pitch_factor = 1.35
                            atempo_factor = speed / pitch_factor
                            a_filter = f"[0:a]asetrate=r={int(sample_rate * pitch_factor)},atempo={atempo_factor:.5f},aresample={sample_rate}[a]"
                        else:
                            a_filter = f"[0:a]atempo={speed}[a]"
                            
                        cmd2 = [
                            "ffmpeg", "-y",
                            "-ss", f"{t_half:.3f}",
                            "-i", video_path,
                            "-filter_complex", f"{v_filter};{a_filter}",
                            "-map", "[v]",
                            "-map", "[a]",
                            "-c:v", "libx264", "-preset", "superfast", "-crf", "20",
                            "-c:a", "aac",
                            out_part2
                        ]
                    else:
                        cmd2 = [
                            "ffmpeg", "-y",
                            "-ss", f"{t_half:.3f}",
                            "-i", video_path,
                            "-filter_complex", v_filter,
                            "-map", "[v]",
                            "-c:v", "libx264", "-preset", "superfast", "-crf", "20",
                            out_part2
                        ]
                else:
                    cmd2 = [
                        "ffmpeg", "-y",
                        "-ss", f"{t_half:.3f}",
                        "-i", video_path,
                        "-c", "copy",
                        "-map", "0",
                        out_part2
                    ]
                
                res2 = subprocess.run(cmd2, capture_output=True, env=env)
                if res2.returncode != 0:
                    raise Exception(f"Lỗi cắt Phần 2: {res2.stderr.decode('utf-8', errors='ignore')}")
                
                item["status"] = "Hoàn tất"
                success_count += 1
                
            except Exception as cut_err:
                item["status"] = f"Lỗi: {str(cut_err)}"
                fail_count += 1
                
            self.after(0, self.render_queue_list)
            
        # Kết thúc vòng lặp
        self.is_processing = False
        self.after(0, lambda: self.update_overall_progress(1.0, f"Đã hoàn thành! Thành công {success_count}, Thất bại {fail_count}"))
        self.after(0, lambda: self.btn_process.configure(text="🚀 CẮT VIDEO HÀNG LOẠT", fg_color=GRN, hover_color="#40A02B"))
