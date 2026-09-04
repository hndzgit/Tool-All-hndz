import os
import re
import datetime
import asyncio
import edge_tts

def parse_srt(srt_file):
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = re.compile(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n(.*?)(?=\n\n|\Z)', re.DOTALL)
    matches = pattern.findall(content)
    sentences = []
    for match in matches:
        text = match.strip().replace('\n', ' ')
        if text: sentences.append(text)
    return sentences

async def _async_generate_edge_audio(text, voice_code, output_path):
    communicate = edge_tts.Communicate(text, voice_code)
    await communicate.save(output_path)

def generate_edge_audio_from_srt(srt_path, output_mp3_path):
    import config.config as cfg
    voice_code = cfg.VBEE_VOICE
    if voice_code.startswith("edge:"):
        voice_code = voice_code[5:]
    
    sentences = parse_srt(srt_path)
    if not sentences:
        print("⚠️ SRT trống, không có chữ để đọc.")
        return None
        
    full_text = " . ".join(sentences)
    print(f"🎙️ Đang gọi Edge-TTS (Giọng: {voice_code})...")
    
    try:
        # Run Edge TTS Async Task
        asyncio.run(_async_generate_edge_audio(full_text, voice_code, output_mp3_path))
        print(f"✅ Đã tải file TTS Edge thành công: {output_mp3_path}")
        
        # --- TỰ ĐỘNG CẬP NHẬT TIMEOUT SRT THEO ĐỘ DÀI AUDIO MỚI ---
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(output_mp3_path) as audio_clip:
                audio_duration = audio_clip.duration
                
            total_chars = sum(len(s) for s in sentences)
            if total_chars > 0:
                char_duration = audio_duration / total_chars
                current_time = 0.0
                
                def format_srt_time(seconds):
                    milliseconds = int((seconds - int(seconds)) * 1000)
                    dt = datetime.datetime.utcfromtimestamp(int(seconds))
                    return f"{dt.strftime('%H:%M:%S')},{milliseconds:03d}"
                
                with open(srt_path, "w", encoding="utf-8") as f:
                    for i, sentence in enumerate(sentences):
                        sentence_duration = len(sentence) * char_duration
                        start_str = format_srt_time(current_time)
                        current_time += sentence_duration
                        end_str = format_srt_time(current_time)
                        
                        f.write(f"{i+1}\n")
                        f.write(f"{start_str} --> {end_str}\n")
                        f.write(f"{sentence}\n\n")
                        
                print(f"✅ Đã đồng bộ lại timeline SRT khớp với Audio Edge mới ({audio_duration:.2f}s).")
        except Exception as e:
            print(f"⚠️ Cảnh báo: Lỗi khi đồng bộ lại timeline file SRT: {e}")
            
        return output_mp3_path
        
    except Exception as e:
        print(f"❌ Lỗi khi gọi Edge TTS: {e}")
        raise e

def test_edge_voice(voice_code):
    import tempfile
    if voice_code.startswith("edge:"):
        voice_code = voice_code[5:]
        
    test_text = "Xin chào bạn, đây là giọng đọc siêu chuẩn từ hệ thống trí tuệ nhân tạo của Microsoft Edge. Cảm ơn bạn đã lắng nghe."
    temp_file = os.path.join(tempfile.gettempdir(), f"edge_test_{voice_code}.mp3")
    
    try:
        asyncio.run(_async_generate_edge_audio(test_text, voice_code, temp_file))
        return temp_file
    except Exception as e:
        print(f"❌ Lỗi Test Edge API: {e}")
        return None
