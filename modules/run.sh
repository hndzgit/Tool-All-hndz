#!/bin/bash
# Ẩn cảnh báo gRPC INFO khi fork tiến trình con (như chạy ffmpeg/playwright)
export GRPC_VERBOSITY=ERROR
export GRPC_ENABLE_FORK_SUPPORT=false

# Lấy thư mục hiện tại của script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "    TOOLKIT SUITE - BY PYTHON"
echo "=========================================="

# Kiểm tra xem venv đã tồn tại chưa
if [ ! -d "venv_main" ]; then
    echo "[+] Đang tạo môi trường ảo (Virtual Environment)..."
    /opt/homebrew/bin/python3.11 -m venv venv_main
fi

# Kích hoạt venv
echo "[+] Kích hoạt môi trường ảo..."
source venv_main/bin/activate

# Cập nhật pip và cài requirements
echo "[+] Cài đặt các thư viện cần thiết..."
pip install --upgrade pip
pip install -r requirements.txt
playwright install

# Chạy app
echo "[+] Đang khởi động ứng dụng..."
python main_gui.py