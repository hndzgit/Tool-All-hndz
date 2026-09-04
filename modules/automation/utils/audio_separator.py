import os
import subprocess
import threading

# Ổ khóa xếp hàng M1 Neural Engine: 
# Không cho phép 2 tiến trình MDX-Net vắt kiệt RAM cùng một lúc.
mdx_lock = threading.Lock()

def separate_audio(input_audio, output_dir):
    """
    Tách âm thanh thành 2 track: Vocals (giọng nói) và No Vocals (nhạc nền)
    Sử dụng model MDX-Net hoặc Demucs thông qua thư viện audio-separator
    """
    if not os.path.exists(input_audio):
        return None, None
        
    print(f"🎵 Đang tách nhạc nền và giọng nói (Demucs/MDX): {os.path.basename(input_audio)}")
    
    # Tự động dọn dẹp model nếu tải dở (corrupted/thiếu dung lượng)
    model_path = "/tmp/audio-separator-models/Kim_Vocal_2.onnx"
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        if size_mb < 60.0:  # File chuẩn là 66.8MB, nếu < 60MB chắc chắn là lỗi tải dở
            print(f"⚠️ Phát hiện file model {model_path} bị lỗi/thiếu dung lượng ({size_mb:.2f}MB < 60MB). Tiến hành xoá để tải lại...")
            try:
                os.remove(model_path)
            except Exception as e:
                print(f"⚠️ Không thể xoá file model lỗi: {e}")
                
    # Model Kim_Vocal_2 (MDX-Net) rất nhanh và chuyên tách Vocals
    # Trả về output tại output_dir
    cmd = [
        "audio-separator",
        input_audio,
        "--model_filename", "Kim_Vocal_2.onnx",
        "--output_dir", output_dir,
        "--output_format", "mp3",
        "--mdxc_batch_size", "4" # Tối ưu hóa Apple M1: Giải phóng băng thông RAM 16GB để MDX tách vocal cực nhanh
    ]
    
    try:
        # Tối ưu hóa Apple M1: Cấp quyền cho ONNXRuntime truy cập vào lõi Neural Engine (CoreML)
        # Thay vì dùng CPU chậm chạp, CoreML sẽ gánh vác việc xử lý mạng nơ-ron MDX-Net.
        custom_env = os.environ.copy()
        custom_env["ONNX_PROVIDERS"] = "CoreMLExecutionProvider,CPUExecutionProvider"
        
        # Chạy ẩn không hiện log loằng ngoằng. Phải XẾP HÀNG chờ nếu có tiến trình khác đang chạy để chống đứng máy!
        with mdx_lock:
            try:
                subprocess.run(cmd, env=custom_env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError as e1:
                print(f"⚠️ Thử tách âm thanh bằng CoreML thất bại. Đang thử cứu hộ mặc định (CPU/Auto, Batch Size = 1)...")
                if e1.stderr:
                    print(f"--- Chi tiết lỗi CoreML ---\n{e1.stderr.strip()}\n-------------------------")
                cmd_fallback = cmd.copy()
                for idx, arg in enumerate(cmd_fallback):
                    if arg == "--mdxc_batch_size":
                        cmd_fallback[idx + 1] = "1"
                # Chạy không áp đặt ONNX_PROVIDERS của CoreML
                subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        
        # Audio separator thường tạo file theo cú pháp:
        # [original_name]_(Vocals)_[model].mp3 và [original_name]_(Instrumental)_[model].mp3
        base_name = os.path.splitext(os.path.basename(input_audio))[0]
        
        # Quét thư mục output_dir tìm 2 file tạo thành
        vocals_path = None
        no_vocals_path = None
        
        for f in os.listdir(output_dir):
            if base_name in f and f.endswith(".mp3"):
                if "(Vocals)" in f:
                    vocals_path = os.path.join(output_dir, f)
                elif "(Instrumental)" in f:
                    no_vocals_path = os.path.join(output_dir, f)
                    
        return vocals_path, no_vocals_path
        
    except Exception as e:
        print(f"❌ Lỗi tách âm thanh: {e}")
        return None, None
