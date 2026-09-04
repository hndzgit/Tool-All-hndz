import edge_tts
import asyncio
import os
from config.config import TTS_VOICE

async def _generate_audio_async(text, output_path):
    """Hàm chạy ngầm (async) để tải giọng AI từ máy chủ Microsoft"""
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(output_path)

def generate_ai_audio(text_list, output_path):
    """
    Nhận 1 mảng các câu tiếng Việt, lọc bỏ các câu trùng lặp,
    nối lại thành 1 đoạn văn và chuyển thành file MP3 AI.
    """
    if not text_list:
        text_list = ["Không có nội dung nhận diện được trong video này."]
    
    # Mẹo quan trọng: Xóa các câu bị trùng lặp (Vì 1 dòng chữ hiển thị trên video
    # trong 3 giây sẽ bị AI quét ra rất nhiều lần, nếu không xóa trùng, AI sẽ đọc lắp bắp).
    unique_texts = []
    for text in text_list:
        if text not in unique_texts:
            unique_texts.append(text)
            
    # Nối các câu lại, cách nhau dấu chấm để AI đọc biết ngắt nghỉ cho tự nhiên
    final_text = ". ".join(unique_texts)
    
    print(f"🎙️ Đang tạo giọng AI cho: {final_text[:50]}...")
    
    # Chạy hàm async trong môi trường sync bình thường
    asyncio.run(_generate_audio_async(final_text, output_path))
    
    print(f"✅ Đã tạo xong file âm thanh AI: {output_path}")
    return output_path