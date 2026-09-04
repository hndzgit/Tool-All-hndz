import os
import sys
import subprocess
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class WatermarkApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

        self.input_folder = ""
        self.output_folder = ""

        self.setup_ui()

    def setup_ui(self):
        title_label = ctk.CTkLabel(self, text="AUTO WATERMARK VIDEO", font=("Arial", 24, "bold"))
        title_label.pack(pady=20)

        frame_input = ctk.CTkFrame(self, fg_color="transparent")
        frame_input.pack(fill="x", padx=20, pady=5)
        self.btn_input = ctk.CTkButton(frame_input, text="Chọn thư mục chứa Video", command=self.browse_input)
        self.btn_input.pack(side="left")
        self.lbl_input = ctk.CTkLabel(frame_input, text="Chưa chọn...", text_color="gray")
        self.lbl_input.pack(side="left", padx=10)

        frame_output = ctk.CTkFrame(self, fg_color="transparent")
        frame_output.pack(fill="x", padx=20, pady=15)
        self.btn_output = ctk.CTkButton(frame_output, text="Chọn thư mục lưu Video", command=self.browse_output)
        self.btn_output.pack(side="left")
        self.lbl_output = ctk.CTkLabel(frame_output, text="Chưa chọn...", text_color="gray")
        self.lbl_output.pack(side="left", padx=10)

        self.entry_text = ctk.CTkEntry(self, placeholder_text="Nhập tên của bạn (Ví dụ: @BanQuyenCuaToi)", width=400)
        self.entry_text.pack(pady=10)

        frame_settings = ctk.CTkFrame(self, fg_color="transparent")
        frame_settings.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frame_settings, text="Cỡ chữ:").pack(side="left")
        self.entry_size = ctk.CTkEntry(frame_settings, width=60)
        self.entry_size.insert(0, "40")
        self.entry_size.pack(side="left", padx=5)

        ctk.CTkLabel(frame_settings, text="Độ mờ (0.1 - 1.0):").pack(side="left", padx=(15, 0))
        self.entry_opacity = ctk.CTkEntry(frame_settings, width=50)
        self.entry_opacity.insert(0, "0.5")
        self.entry_opacity.pack(side="left", padx=5)

        ctk.CTkLabel(frame_settings, text="Vị trí:").pack(side="left", padx=(15, 0))
        self.combo_pos = ctk.CTkComboBox(frame_settings, values=["Giữa màn hình", "Góc trái - trên", "Góc phải - trên", "Góc trái - dưới", "Góc phải - dưới"], width=130)
        self.combo_pos.set("Góc phải - dưới")
        self.combo_pos.pack(side="left", padx=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(self, text="Sẵn sàng!", text_color="green")
        self.lbl_status.pack()

        self.btn_start = ctk.CTkButton(self, text="BẮT ĐẦU CHẠY", font=("Arial", 16, "bold"), height=50, command=self.start_processing_thread)
        self.btn_start.pack(pady=20)

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder = folder
            self.lbl_input.configure(text=folder[-35:] + "..." if len(folder) > 35 else folder)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.lbl_output.configure(text=folder[-35:] + "..." if len(folder) > 35 else folder)

    def start_processing_thread(self):
        if not self.input_folder or not self.output_folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn đầy đủ thư mục Input và Output!")
            return
        watermark_text = self.entry_text.get().strip()
        if not watermark_text:
            messagebox.showerror("Lỗi", "Vui lòng nhập nội dung Watermark!")
            return

        self.btn_start.configure(state="disabled")
        self.lbl_status.configure(text="Đang xử lý...", text_color="orange")
        threading.Thread(target=self.process_videos, args=(watermark_text,), daemon=True).start()

    def process_videos(self, text):
        font_size = self.entry_size.get()
        opacity = self.entry_opacity.get()
        position = self.combo_pos.get()

        valid_extensions = ('.mp4', '.mov', '.avi', '.mkv')
        video_files = [f for f in os.listdir(self.input_folder) if f.lower().endswith(valid_extensions)]
        
        total_videos = len(video_files)
        if total_videos == 0:
            self.lbl_status.configure(text="Không tìm thấy video nào trong thư mục Input!", text_color="red")
            self.btn_start.configure(state="normal")
            return

        if position == "Giữa màn hình": pos_xy = "x=(w-text_w)/2:y=(h-text_h)/2"
        elif position == "Góc trái - trên": pos_xy = "x=20:y=20"
        elif position == "Góc phải - trên": pos_xy = "x=w-text_w-20:y=20"
        elif position == "Góc trái - dưới": pos_xy = "x=20:y=h-text_h-20"
        else: pos_xy = "x=w-text_w-20:y=h-text_h-20"

        # TÌM FONT CHỮ CỰC KỲ KỸ CÀNG TRÊN MAC
        font_path = ""
        if sys.platform == "win32":
            font_path = "C\\:/Windows/Fonts/arial.ttf"
        elif sys.platform == "darwin":
            # Quét các thư mục font có thể có trên macOS
            mac_fonts = [
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc", # Font dự phòng nếu ko có Arial
                "/Library/Fonts/Times New Roman.ttf"
            ]
            for f in mac_fonts:
                if os.path.exists(f):
                    font_path = f
                    break
        else:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        if not font_path:
            messagebox.showerror("Lỗi Font chữ", "Không tìm thấy bất kỳ font chữ nào trên máy Mac của bạn để chèn vào video!")
            self.btn_start.configure(state="normal")
            self.lbl_status.configure(text="Lỗi hệ thống!", text_color="red")
            return
        
        safe_text = text.replace("'", "").replace(":", "")
        drawtext_filter = f"drawtext=fontfile='{font_path}':text='{safe_text}':fontsize={font_size}:fontcolor=white@{opacity}:{pos_xy}"

        for index, filename in enumerate(video_files):
            input_path = os.path.join(self.input_folder, filename)
            output_path = os.path.join(self.output_folder, f"WM_{filename}")

            self.lbl_status.configure(text=f"Đang render: {filename} ({index + 1}/{total_videos})")
            
            codec = "h264_videotoolbox" if sys.platform == "darwin" else "libx264"
            preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "ultrafast"]

            command = [
                'ffmpeg',
                '-i', input_path,
                '-vf', drawtext_filter,
                '-c:v', codec
            ] + preset_args + [
                '-b:v', '5000k',             # Giữ bitrate cao để video không bị mờ
                '-codec:a', 'copy',          # Âm thanh copy nguyên bản (siêu tốc)
                '-y',
                output_path
            ]

            try:
                # Dùng capture_output để bắt lỗi chi tiết nếu FFmpeg thất bại
                kwargs = {'capture_output': True, 'text': True}
                if sys.platform == "win32":
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

                process = subprocess.run(command, **kwargs)

                # Fallback to libx264 if hardware encoder fails
                if process.returncode != 0 and codec == "h264_videotoolbox":
                    fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in command]
                    try:
                        idx_codec = fallback_cmd.index("libx264")
                        fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "ultrafast"] + fallback_cmd[idx_codec+1:]
                    except ValueError:
                        pass
                    process = subprocess.run(fallback_cmd, **kwargs)

                # NẾU FFMPEG CHẠY LỖI SẼ BÁO NGAY Ở ĐÂY
                if process.returncode != 0:
                    error_msg = process.stderr[-300:] # Lấy 300 ký tự cuối của thông báo lỗi
                    messagebox.showerror("Lỗi FFmpeg", f"Video {filename} bị lỗi!\nChi tiết lỗi:\n{error_msg}")
                    self.btn_start.configure(state="normal")
                    self.lbl_status.configure(text="Render bị lỗi!", text_color="red")
                    return

            except FileNotFoundError:
                messagebox.showerror("Lỗi", "Không tìm thấy FFmpeg!\nBật Terminal và gõ: brew install ffmpeg")
                self.btn_start.configure(state="normal")
                return

            progress = (index + 1) / total_videos
            self.progress_bar.set(progress)

        self.lbl_status.configure(text="HOÀN THÀNH TẤT CẢ!", text_color="green")
        self.btn_start.configure(state="normal")
        messagebox.showinfo("Thành công", f"Đã đóng dấu xong {total_videos} video! Mở thư mục Output để kiểm tra.")

if __name__ == "__main__":
    app = ctk.CTk()
    app.geometry("600x600")
    app.title("Tool Đóng Dấu Video")
    app.grid_rowconfigure(0, weight=1)
    app.grid_columnconfigure(0, weight=1)
    frame = WatermarkApp(app)
    frame.grid(row=0, column=0, sticky="nsew")
    app.mainloop()