import os
import threading
import time
import customtkinter as ctk
from customtkinter import filedialog

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from .worker import run_threads_pipeline
from .styles import F, T1, T2, T3, BG2, BORDER, SEL, GRN, RED, ORG
from .poster_gui import PosterApp

class ThreadsApp(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.selected_files = []
        self.setup_ui()

    def setup_ui(self):
        title_label = ctk.CTkLabel(self, text="🧵 THREADS AFFILIATE & AUTO POST", font=F(22, "bold"), text_color=T1)
        title_label.pack(pady=15)
        
        info_label = ctk.CTkLabel(self, text="Tổ hợp tự động lách video hàng loạt và bắn API lên Threads độc quyền.", 
                                  font=F(12), text_color=T2, justify="center")
        info_label.pack(pady=(0, 10))

        # --- TAB VIEW ---
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_render = self.tabview.add("1. Render (Lách Video)")
        self.tab_post = self.tabview.add("2. Vũ Khí Đăng Tự Động")
        
        self.build_render_tab()
        self.build_post_tab()

    def build_render_tab(self):
        parent = self.tab_render
        # Select Files Button
        self.btn_select = ctk.CTkButton(parent, text="📂 Bấm Chọn Video", font=F(14, "bold"), 
                                        height=40, command=self.choose_files, fg_color=SEL)
        self.btn_select.pack(pady=10)

        # File List Box
        self.scroll = ctk.CTkScrollableFrame(parent, fg_color=BG2, border_width=1, border_color=BORDER, height=180)
        self.scroll.pack(fill="x", padx=40, pady=(0, 10))
        
        self.lbl_empty = ctk.CTkLabel(self.scroll, text="Chưa có video nào. Bấm 'Chọn Video' để bắt đầu.", font=F(12), text_color=T3)
        self.lbl_empty.pack(pady=20)

        # Output Folder Row
        from automation.config import config as cfg
        frame_out = ctk.CTkFrame(parent, fg_color="transparent")
        frame_out.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(frame_out, text="Thư mục Đầu Ra:", font=F(12), text_color=T2).pack(side="left")
        
        cfg_out = getattr(cfg, "OUTPUT_DIR", "")
        display_out = f"…/{os.path.basename(cfg_out)}/" if cfg_out else "Chưa chọn..."
        self.lbl_output_dir_display = ctk.CTkLabel(frame_out, text=display_out, font=F(12, "bold"), text_color=SEL)
        self.lbl_output_dir_display.pack(side="left", padx=10)
        
        btn_change_out = ctk.CTkButton(frame_out, text="Thay đổi", font=F(11), width=60, height=24, fg_color=BORDER, hover_color=BG2, command=self.change_output_dir)
        btn_change_out.pack(side="left")

        # Start Button
        self.btn_start = ctk.CTkButton(parent, text="🔥 BẮT ĐẦU CHẠY", font=F(16, "bold"), 
                                       height=45, fg_color=GRN, hover_color="#00A040", command=self.start_processing)
        self.btn_start.pack(pady=10)

        # Status Label
        self.lbl_status = ctk.CTkLabel(parent, text="Sẵn sàng cày cuốc!", font=F(13), text_color=GRN)
        self.lbl_status.pack()

        # Terminal / Logs
        log_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        log_hdr.pack(fill="x", padx=40, pady=(10, 0))
        ctk.CTkLabel(log_hdr, text="Nhật Ký Hệ Thống", font=F(12, "bold"), text_color=T2).pack(side="left")

        self.logs = ctk.CTkTextbox(parent, font=ctk.CTkFont("Consolas", 12), text_color="#A3E635", fg_color="#0D1117",
                                   wrap="word", corner_radius=10, border_width=1, border_color="#30363D", height=120)
        self.logs.pack(fill="both", expand=True, padx=40, pady=(4, 20))
        self.logs.configure(state="disabled")

    def build_post_tab(self):
        # We just pack PosterApp into self.tab_post
        self.poster_app = PosterApp(self.tab_post)
        self.poster_app.pack(fill="both", expand=True)

    def log(self, msg):
        def _append():
            self.logs.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.logs.insert("end", f"[{ts}] {msg}\n")
            self.logs.see("end")
            self.logs.configure(state="disabled")
        self.after(0, _append)

    def change_output_dir(self):
        from automation.config import config as cfg
        folder = filedialog.askdirectory()
        if folder:
            cfg.OUTPUT_DIR = folder
            cfg.save_settings({"output_dir": folder})
            self.lbl_output_dir_display.configure(text=f"…/{os.path.basename(folder)}/")
            self.log(f"📁 Đổi đầu ra → {folder}")

    def choose_files(self):
        paths = filedialog.askopenfilenames(title="Chọn Video", filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")])
        if paths:
            self.lbl_empty.pack_forget()
            for p in paths:
                if p not in self.selected_files:
                    self.selected_files.append(p)
                    lbl = ctk.CTkLabel(self.scroll, text=f"📄 {os.path.basename(p)}", font=F(12), text_color=T2, anchor="w")
                    lbl.pack(fill="x", pady=2, padx=10)
                    
            self.lbl_status.configure(text=f"Đã nạp {len(self.selected_files)} video.", text_color=T1)
            self.log(f"Đã chọn {len(paths)} video.")

    def start_processing(self):
        if not self.selected_files:
            self.lbl_status.configure(text="⚠️ Vui lòng chọn ít nhất 1 video!", text_color=RED)
            return

        self.btn_start.configure(state="disabled", fg_color=T3)
        self.btn_select.configure(state="disabled")
        
        threading.Thread(target=self.process_thread, daemon=True).start()

    def process_thread(self):
        total = len(self.selected_files)
        success = 0
        self.log(f"🚀 Bắt đầu quá trình Affiliate cho {total} video!")
        
        for idx, fp in enumerate(self.selected_files):
            name = os.path.basename(fp)
            self.lbl_status.configure(text=f"⏳ Đang chạy ({idx+1}/{total}): {name}", text_color=ORG)
            self.log(f"🎬 Bắt đầu chạy: {name}")
            
            try:
                def prog(pct):
                    pass # We can add progress bar later if needed
                    
                v_out, i_out = run_threads_pipeline(fp, progress_callback=prog)
                success += 1
                self.lbl_status.configure(text=f"✅ Xong {idx+1}/{total}: {name}", text_color=GRN)
                self.log(f"✅ Hoàn thành: {name}")
                time.sleep(1) # Nghỉ chút xíu
            except Exception as e:
                self.lbl_status.configure(text=f"❌ Lỗi {name}: {str(e)[:50]}", text_color=RED)
                self.log(f"❌ LỖI ({name}): {str(e)}")
                time.sleep(2)

        # Re-enable
        self.selected_files.clear()
        for w in self.scroll.winfo_children():
            w.destroy()
        self.lbl_empty = ctk.CTkLabel(self.scroll, text="Chưa có video nào. Bấm 'Chọn Video' để bắt đầu.", font=F(12), text_color=T3)
        self.lbl_empty.pack(pady=20)
        
        self.btn_start.configure(state="normal", fg_color=GRN)
        self.btn_select.configure(state="normal")
        self.lbl_status.configure(text=f"🎉 Hoàn thành! Thành công {success}/{total} video.", text_color=GRN)
        self.log(f"🎉 Chiến dịch kết thúc. Xong {success}/{total} video.")