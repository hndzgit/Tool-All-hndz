# ✦ Video AI Pro Studio (Tool All)

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![UI Framework](https://img.shields.io/badge/GUI-CustomTkinter-orange.svg)
![Copyright](https://img.shields.io/badge/Copyright-%C2%A9%202026%20Tr%E1%BA%A7n%20Ho%C3%A0i%20Nam-blue.svg)

**Video AI Pro Studio** (Tool All) là bộ công cụ tất-cả-trong-một (All-in-One) dành cho Creators, Marketers và NPH Video. Được tích hợp công nghệ AI (Gemini Vision, Vbee TTS, Edge-TTS, Playwright), phần mềm giúp tự động hóa toàn bộ quy trình từ tải video nguồn, lách bản quyền, dịch thuật OCR, tạo giọng đọc, biên tập video cho đến đăng tải tự động lên các nền tảng mạng xã hội.

---

## 🌟 Tính Năng Nổi Bật

### 🎬 1. Xử Lý & Edit Video Tự Động
- **▶ AI Pipeline (Chính)**: Tự động OCR dịch chữ trên video, chuyển đổi ngôn ngữ, tạo giọng đọc truyền cảm (Vbee/Edge-TTS) và ghép phụ đề chuẩn khung hình.
- **🤖 Video AI Cặp**: Phân tích ảnh đơn hàng/ảnh sản phẩm bằng Gemini Vision API và tự động tạo video giới thiệu.
- **🎬 Edit & Lách Bản Quyền (YouTube / TikTok)**: Áp dụng các thuật toán lách bản quyền nâng cao (Crop, Mirror, Color adjustment, Speed modification, Audio pitch, EQ filter).
- **✂️ Cắt Video (59s & Hàng Loạt)**: Cắt nhỏ video dài thành các clip ngắn dưới 59 giây tối ưu cho Shorts/Reels/TikTok.
- **📱 Đổi Tỷ Lệ (Ngang ➔ Dọc)**: Chuyển đổi video ngang 16:9 sang dạng 9:16 mượt mà.
- **🎥 Ghép & Edit Video YT (YouTube Compiler)**: Tự động tổng hợp nhiều video ngắn thành video dài, tích hợp tính năng tự tạo Thumbnail.
- **🎵 Gắn Nhạc Hàng Loạt (BGM Injector)**: Chèn nhạc nền cho hàng trăm video cùng lúc với khả năng tinh chỉnh âm lượng voice/music.
- **💧 Auto Watermark**: Đóng dấu logo/chữ bảo vệ bản quyền thương hiệu hàng loạt.

### 🌐 2. Đăng Tải & Quản Lý Mạng Xã Hội
- **🎵 TikTok Auto-Up**: Đăng video tự động lên TikTok thông qua Playwright chống bóp tương tác.
- **🧵 Threads Affiliate**: Tự động sinh Caption bán hàng bằng Gemini AI và đăng bài kèm link affiliate lên Threads.
- **📥 Tải Nguồn MXH**: Tải video chất lượng cao không dính logo từ Douyin, TikTok, Kuaishou,...

### 🛠️ 3. Công Cụ Phụ Trợ
- **💬 Telegram Bot**: Điều khiển và nhận thông báo tiến trình xử lý video từ xa qua Telegram.
- **🗣️ Text to Speech (TTS Tool)**: Chuyển văn bản thành giọng đọc đa ngôn ngữ với nhiều giọng đọc chất lượng cao.

---

## 📁 Cấu Trúc Dự Án

```text
Tool All/
├── run.sh                  # Script khởi chạy ứng dụng chính trên macOS/Linux
├── build_mac_app.sh        # Script đóng gói ứng dụng macOS (.app)
├── modules/
│   ├── main_gui.py         # Giao diện ứng dụng chính (CustomTkinter)
│   ├── automation/         # Core AI Pipeline, OCR, TTS & Subtitle Engine
│   ├── ai_video/           # Module xử lý video cặp bằng Gemini Vision
│   ├── manual_editor/      # Trình chỉnh sửa & lách bản quyền video
│   ├── trimmer/            # Công cụ cắt video 59s
│   ├── ratio_converter/    # Công cụ chuyển đổi khung hình ngang ➔ dọc
│   ├── yt_compiler/        # Công cụ biên tập & ghép video YouTube dài
│   ├── bgm_injector/       # Công cụ chèn nhạc nền hàng loạt
│   ├── watermark/          # Module đóng dấu logo hàng loạt
│   ├── tiktok_upload/      # Tự động hóa đăng video TikTok (Playwright)
│   ├── threads/            # Tự động hóa đăng bài Threads Affiliate
│   ├── douyin/             # Module tải video nguồn từ Douyin/TikTok
│   ├── bot/                # Telegram Bot điều khiển
│   └── tts_tool/           # Công cụ chuyển đổi Text-to-Speech
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 1. Yêu Cầu Hệ Thống
- **Python**: v3.10 trở lên
- **FFmpeg**: Cần thiết cho quá trình xử lý video (`brew install ffmpeg` trên macOS hoặc tải FFmpeg trên Windows)

### 2. Cài Đặt Môi Trường

```bash
# Clone repository về máy
git clone https://github.com/hndzgit/Tool-All-hndz.git
cd Tool-All-hndz

# Tạo môi trường ảo Python (Virtual Environment)
python3 -m venv .venv
source .venv/bin/activate  # Trên macOS/Linux
# Hoặc .venv\Scripts\activate trên Windows

# Cài đặt các thư viện phụ thuộc
pip install -r modules/requirements.txt

# Cài đặt trình duyệt cho Playwright (dành cho module TikTok / Threads)
playwright install chromium
```

### 3. Khởi Chạy Ứng Dụng

- **Chạy trực tiếp qua Python**:
  ```bash
  python modules/main_gui.py
  ```

- **Chạy qua Script Bash (macOS/Linux)**:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```

---

## ⚙️ Cấu Hinh API Key (Tùy chọn)

Để sử dụng đầy đủ các tính năng AI (Gemini, Vbee TTS), bạn có thể cấu hình API Key trực tiếp trên giao diện của ứng dụng trong phần **Cài đặt AI Pipeline** hoặc chỉnh sửa trong file `modules/automation/config/settings.json`:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "vbee_api_key": "YOUR_VBEE_API_KEY"
}
```

---

## ⚖️ Bản Quyền (Copyright)

© 2026 **Trần Hoài Nam**. All rights reserved.  
Bản quyền toàn bộ dự án thuộc về **Trần Hoài Nam**.

---

<p align="center">Developed with ❤️ by <b>Trần Hoài Nam</b></p>
