#!/bin/bash
# Ẩn cảnh báo gRPC INFO khi fork tiến trình con (như chạy ffmpeg/playwright)
export GRPC_VERBOSITY=ERROR
export GRPC_ENABLE_FORK_SUPPORT=false

# Trỏ thẳng vào thư mục con modules
cd "$(dirname "$0")"
./modules/run.sh