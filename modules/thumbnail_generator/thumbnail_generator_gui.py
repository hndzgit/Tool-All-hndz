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
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Import shared collage thumbnail helper
from yt_compiler.thumbnail_maker import create_collage_thumbnail, get_video_info

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

class ThumbnailGeneratorApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, fg_color=BG, **kwargs)

        self.video_paths = []
        self.output_dir = ""
        self.is_running = False
        self.stop_event = threading.Event()
        self.preview_thread_lock = threading.Lock()

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Configure layout Grid (Left: Controls, Right: Logs & Preview)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL: CONTROLS ---
        left_frame = ctk.CTkScrollableFrame(self, fg_color=BG2, corner_radius=10, scrollbar_button_color=BG4)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        ctk.CTkLabel(left_frame, text="🖼️ TẠO ẢNH BÌA YT HÀNG LOẠT", font=F(16, "bold"), text_color=ORG).pack(pady=(15, 10))

        # 1. INPUT VIDEOS
        f_in = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_in.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_in, text="1. Chọn Video Đầu Vào (Video Đã Ghép)", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))
        
        f_in_btns = ctk.CTkFrame(f_in, fg_color="transparent")
        f_in_btns.pack(fill="x", padx=10, pady=4)
        self.btn_load_dir = ctk.CTkButton(f_in_btns, text="📂 Chọn Thư Mục", command=self.choose_input_dir, fg_color=BG4, text_color=T1, height=28)
        self.btn_load_dir.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_load_files = ctk.CTkButton(f_in_btns, text="🎞 Chọn Tệp Lẻ", command=self.choose_input_files, fg_color=BG4, text_color=T1, height=28)
        self.btn_load_files.pack(side="right", fill="x", expand=True, padx=(2, 0))

        self.lbl_loaded = ctk.CTkLabel(f_in, text="Chưa nạp video", font=F(11), text_color=T3)
        self.lbl_loaded.pack(pady=(0, 10))

        # 2. BANNER TEXT SETTINGS
        f_text = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_text.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_text, text="2. Cài Đặt Chữ Tiêu Đề Banner", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))

        # Text Template
        f_temp = ctk.CTkFrame(f_text, fg_color="transparent")
        f_temp.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f_temp, text="Mẫu tiêu đề (sử dụng {index}):", font=F(11), text_color=T2).pack(anchor="w")
        self.entry_template = ctk.CTkEntry(f_temp, font=F(11), height=24)
        self.entry_template.insert(0, "Tổng Hợp | Vợ Thánh Đớp Đi Hốc | Phần {index}")
        self.entry_template.pack(fill="x", pady=2)

        # Start Index
        f_idx = ctk.CTkFrame(f_text, fg_color="transparent")
        f_idx.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f_idx, text="Chỉ số phần bắt đầu:", font=F(11), text_color=T2).pack(side="left")
        self.entry_start_idx = ctk.CTkEntry(f_idx, width=70, height=24, font=F(11), justify="center")
        self.entry_start_idx.insert(0, "1")
        self.entry_start_idx.pack(side="right")

        # Color Configuration
        f_colors = ctk.CTkFrame(f_text, fg_color="transparent")
        f_colors.pack(fill="x", padx=10, pady=(5, 10))
        
        # Border color
        ctk.CTkLabel(f_colors, text="Màu viền banner:", font=F(11), text_color=T2).pack(anchor="w")
        self.combo_border_color = ctk.CTkOptionMenu(
            f_colors, 
            values=["Cam (#FE640B)", "Đỏ (#D20F39)", "Đen (#000000)", "Xanh (#1E66F5)"], 
            font=F(11), height=22
        )
        self.combo_border_color.set("Cam (#FE640B)")
        self.combo_border_color.pack(fill="x", pady=(2, 6))

        # Text Fill color
        ctk.CTkLabel(f_colors, text="Màu chữ:", font=F(11), text_color=T2).pack(anchor="w")
        self.combo_text_color = ctk.CTkOptionMenu(
            f_colors, 
            values=["Đỏ (#D20F39)", "Cam (#FE640B)", "Vàng (#FFFF00)", "Xanh (#1E66F5)"], 
            font=F(11), height=22
        )
        self.combo_text_color.set("Đỏ (#D20F39)")
        self.combo_text_color.pack(fill="x", pady=(2, 6))

        # 3. OUTPUT DIR
        f_out = ctk.CTkFrame(left_frame, fg_color=BG3, corner_radius=8)
        f_out.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_out, text="3. Chọn Thư Mục Lưu Ảnh Bìa", font=F(12, "bold"), text_color=T1).pack(pady=(5, 2))
        self.btn_out = ctk.CTkButton(f_out, text="💾 Chọn Nơi Lưu", command=self.choose_output_dir, fg_color=BLU, text_color=BG, font=F(11, "bold"), height=28)
        self.btn_out.pack(fill="x", padx=10, pady=4)
        self.lbl_out_dir = ctk.CTkLabel(f_out, text="Mặc định: Thư mục chứa video gốc", font=F(11), text_color=T3)
        self.lbl_out_dir.pack(pady=(0, 5))

        # Save settings button
        self.btn_save_cfg = ctk.CTkButton(left_frame, text="💾 LƯU CẤU HÌNH & THIẾT LẬP", command=self.save_settings, fg_color=BG4, text_color=T1, height=32)
        self.btn_save_cfg.pack(fill="x", padx=10, pady=10)

        # ACTION BUTTONS
        self.btn_start = ctk.CTkButton(left_frame, text="🎨 BẮT ĐẦU TẠO ẢNH BÌA", command=self.start_processing, fg_color=GRN, text_color=BG, font=F(14, "bold"), height=40)
        self.btn_start.pack(fill="x", padx=10, pady=5)
        self.btn_stop = ctk.CTkButton(left_frame, text="🛑 DỪNG LẠI", command=self.stop_processing, fg_color=RED, text_color=BG, font=F(14, "bold"), height=40, state="disabled")
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 15))


        # --- RIGHT PANEL: PREVIEW & LOGS ---
        right_frame = ctk.CTkFrame(self, fg_color=BG2, corner_radius=10)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)

        ctk.CTkLabel(right_frame, text="👁️ XEM TRƯỚC ẢNH BÌA (LIVE PREVIEW)", font=F(14, "bold"), text_color=T1).pack(pady=(15, 5))

        # 16:9 Image Preview Frame (480x270 px)
        self.lbl_preview_img = ctk.CTkLabel(right_frame, text="[Nạp video để xem trước ảnh bìa]", fg_color="#0D1117", corner_radius=8, width=480, height=270, font=F(11))
        self.lbl_preview_img.pack(pady=10)

        # Progress / Status
        self.progress_bar = ctk.CTkProgressBar(right_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=5)

        self.lbl_status = ctk.CTkLabel(right_frame, text="Sẵn sàng...", font=F(12, "bold"), text_color=ORG)
        self.lbl_status.pack(pady=2)

        # Activity Logs Box
        self.logs_box = ctk.CTkTextbox(right_frame, font=F(11, "bold"), fg_color="#0D1117", text_color="#A3E635")
        self.logs_box.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.logs_box.configure(state="disabled")

        # Bind events for Live Preview updates
        self.entry_template.bind("<KeyRelease>", lambda e: self.update_preview())
        self.entry_start_idx.bind("<KeyRelease>", lambda e: self.update_preview())
        self.combo_border_color.configure(command=lambda choice: self.update_preview())
        self.combo_text_color.configure(command=lambda choice: self.update_preview())

    # --- LIVE PREVIEW WORKER ---
    def update_preview(self):
        if not self.video_paths:
            self._show_blank_preview()
            return
        threading.Thread(target=self._generate_preview_worker, daemon=True).start()

    def _show_blank_preview(self):
        self.lbl_preview_img.configure(image=None, text="[Nạp video để xem trước ảnh bìa]")

    def _generate_preview_worker(self):
        # Prevent concurrent preview rendering loops from stepping on each other
        if not self.preview_thread_lock.acquire(blocking=False):
            return
        try:
            v_path = self.video_paths[0]
            
            # Map labels to hex colors
            color_map = {
                "Cam (#FE640B)": "#FE640B",
                "Đỏ (#D20F39)": "#D20F39",
                "Đen (#000000)": "#000000",
                "Xanh (#1E66F5)": "#1E66F5",
                "Vàng (#FFFF00)": "#FFFF00"
            }
            border_hex = color_map.get(self.combo_border_color.get(), "#FE640B")
            text_hex = color_map.get(self.combo_text_color.get(), "#D20F39")
            stroke_hex = "#450a0a" if text_hex == "#D20F39" else "#000000"

            try:
                curr_idx = int(self.entry_start_idx.get())
            except:
                curr_idx = 1

            template_str = self.entry_template.get()
            title_text = template_str.replace("{index}", str(curr_idx))

            # Temporary preview JPG inside user folder
            temp_path = os.path.join(os.path.dirname(v_path), "temp_live_preview.jpg")

            # Stitch frame and overlay banner
            success = create_collage_thumbnail(
                video_list=[v_path],
                title_text=title_text,
                output_thumb_path=temp_path,
                banner_border_color=border_hex,
                text_fill_color=text_hex,
                text_stroke_color=stroke_hex
            )

            if success and os.path.exists(temp_path):
                img = Image.open(temp_path).convert("RGB")
                img_resized = img.resize((480, 270), Image.Resampling.LANCZOS)
                # Dispatch PhotoImage instantiation to main thread
                self.after(0, self._render_pil_preview, img_resized)
                try: os.remove(temp_path)
                except: pass
        except Exception as err:
            print(f"Error in preview generator thread: {err}")
        finally:
            self.preview_thread_lock.release()

    def _render_pil_preview(self, pil_img):
        try:
            photo = ImageTk.PhotoImage(pil_img)
            self.lbl_preview_img.configure(image=photo, text="")
            self.lbl_preview_img.image = photo
        except Exception as e:
            print(f"Failed to display preview image on main thread: {e}")

    # --- EVENT HANDLERS ---
    def choose_input_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Chứa Video Đã Ghép")
        if folder:
            valid_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.ts', '.3gp')
            self.video_paths = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(valid_exts)])
            self._update_loaded_label()
            self.update_preview()

    def choose_input_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn các video tệp lẻ",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.ts *.3gp"), ("All Files", "*.*")]
        )
        if files:
            self.video_paths = sorted(list(files))
            self._update_loaded_label()
            self.update_preview()

    def _update_loaded_label(self):
        if self.video_paths:
            self.lbl_loaded.configure(text=f"Đã nạp: {len(self.video_paths)} videos", text_color=GRN)
            self.log(f"🔎 Đã nạp {len(self.video_paths)} video vào danh sách tạo ảnh bìa.")
        else:
            self.lbl_loaded.configure(text="Chưa nạp video", text_color=T3)

    def choose_output_dir(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Lưu Ảnh Bìa")
        if folder:
            self.output_dir = folder
            self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(folder)}", text_color=GRN)
            self.log(f"📂 Thư mục xuất ảnh bìa: {folder}")

    def log(self, message):
        def _append():
            self.logs_box.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs_box.insert("end", f"[{ts}] {message}\n")
            self.logs_box.see("end")
            self.logs_box.configure(state="disabled")
        self.after(0, _append)

        # Write to log file
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumb_generator_run.log")
        try:
            full_ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{full_ts}] {message}\n")
        except Exception as e:
            print(f"Failed to append to log file: {e}")

    # --- SAVE / LOAD CONFIGS ---
    def save_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumb_generator_settings.json")
        try:
            data = {
                "template": self.entry_template.get(),
                "start_idx": self.entry_start_idx.get(),
                "border_color": self.combo_border_color.get(),
                "text_color": self.combo_text_color.get(),
                "output_dir": self.output_dir
            }
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.log("💾 Đã lưu cấu hình thiết kế ảnh bìa thành công!")
            messagebox.showinfo("Lưu cấu hình", "Lưu cấu hình giao diện thành công!")
        except Exception as e:
            self.log(f"❌ Không thể lưu cấu hình: {e}")
            messagebox.showerror("Lỗi lưu", f"Lỗi khi lưu cấu hình: {e}")

    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumb_generator_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.entry_template.delete(0, tk.END)
                self.entry_template.insert(0, data.get("template", "Tổng Hợp | Vợ Thánh Đớp Đi Hốc | Phần {index}"))

                self.entry_start_idx.delete(0, tk.END)
                self.entry_start_idx.insert(0, data.get("start_idx", "1"))

                self.combo_border_color.set(data.get("border_color", "Cam (#FE640B)"))
                self.combo_text_color.set(data.get("text_color", "Đỏ (#D20F39)"))
                
                self.output_dir = data.get("output_dir", "")
                if self.output_dir and os.path.exists(self.output_dir):
                    self.lbl_out_dir.configure(text=f"Lưu tại: .../{os.path.basename(self.output_dir)}", text_color=GRN)

                self.log("💾 Đã tự động nạp cấu hình tạo ảnh bìa hàng loạt.")
            except Exception as e:
                print(f"Failed to load settings: {e}")

    # --- PROCESS TIMELINE ---
    def start_processing(self):
        if self.is_running:
            return
        if not self.video_paths:
            self.log("⚠️ Không có video nào để tạo ảnh bìa! Vui lòng nạp video trước.")
            messagebox.showwarning("Thiếu video", "Vui lòng chọn thư mục hoặc tệp video đầu vào!")
            return

        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", fg_color="#94A3B8")
        self.btn_stop.configure(state="normal")
        self.btn_load_dir.configure(state="disabled")
        self.btn_load_files.configure(state="disabled")
        self.btn_out.configure(state="disabled")

        threading.Thread(target=self.processing_worker, daemon=True).start()

    def stop_processing(self):
        if self.is_running:
            self.log("🛑 Đang dừng tiến trình tạo ảnh bìa...")
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="ĐANG DỪNG...")

    def processing_worker(self):
        try:
            self.log(f"🚀 BẮT ĐẦU TẠO ẢNH BÌA HÀNG LOẠT CHO {len(self.video_paths)} VIDEOS...")
            
            # Parse colors
            b_color_sel = self.combo_border_color.get()
            t_color_sel = self.combo_text_color.get()
            
            # Map labels to hex colors
            color_map = {
                "Cam (#FE640B)": "#FE640B",
                "Đỏ (#D20F39)": "#D20F39",
                "Đen (#000000)": "#000000",
                "Xanh (#1E66F5)": "#1E66F5",
                "Vàng (#FFFF00)": "#FFFF00"
            }
            border_hex = color_map.get(b_color_sel, "#FE640B")
            text_hex = color_map.get(t_color_sel, "#D20F39")
            stroke_hex = "#450a0a" if text_hex == "#D20F39" else "#000000"

            # Parse start index
            try:
                curr_idx = int(self.entry_start_idx.get())
            except:
                curr_idx = 1

            template_str = self.entry_template.get()
            success_count = 0
            total_videos = len(self.video_paths)

            for idx, v_path in enumerate(self.video_paths):
                if self.stop_event.is_set():
                    raise InterruptedError("Dừng bởi người dùng.")

                v_name = os.path.basename(v_path)
                self.log(f"[{idx+1}/{total_videos}] 🎨 Đang chế tác ảnh bìa cho video: {v_name}")
                self.after(0, lambda i=idx, n=total_videos, vn=v_name: (
                    self.progress_bar.set((i + 1) / n),
                    self.lbl_status.configure(text=f"Đang tạo {i+1}/{n}: {vn}")
                ))

                # Determine output path
                if self.output_dir:
                    out_path = os.path.join(self.output_dir, os.path.splitext(v_name)[0] + ".jpg")
                else:
                    out_path = os.path.splitext(v_path)[0] + ".jpg"

                # Construct title text
                title_text = template_str.replace("{index}", str(curr_idx))

                # Call shared collage maker (uses 1 video to extract 3 frames)
                success = create_collage_thumbnail(
                    video_list=[v_path],
                    title_text=title_text,
                    output_thumb_path=out_path,
                    banner_border_color=border_hex,
                    text_fill_color=text_hex,
                    text_stroke_color=stroke_hex
                )

                if success:
                    self.log(f"   ✅ Đã tạo ảnh bìa: {os.path.basename(out_path)}")
                    success_count += 1
                else:
                    self.log(f"   ❌ Tạo ảnh bìa thất bại cho {v_name}")

                curr_idx += 1

            self.log(f"\n🎉 HOÀN THÀNH: Đã tạo xong {success_count}/{total_videos} ảnh bìa YouTube!")
            self.after(0, lambda: self.lbl_status.configure(text=f"Đã tạo {success_count}/{total_videos} ảnh bìa!", text_color=GRN))
            self.after(0, lambda: messagebox.showinfo("Hoàn tất", f"Đã tạo thành công {success_count}/{total_videos} ảnh bìa!"))

        except InterruptedError:
            self.log("🛑 Tiến trình đã bị dừng bởi người dùng.")
            self.after(0, lambda: self.lbl_status.configure(text="Đã dừng", text_color=RED))
        except Exception as e:
            self.log(f"❌ Lỗi trong quá trình tạo ảnh bìa: {e}")
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
        self.btn_out.configure(state="normal")
