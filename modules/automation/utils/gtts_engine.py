import os
import datetime
from gtts import gTTS

def parse_srt(srt_file):
    import re
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = re.compile(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n(.*?)(?=\n\n|\Z)', re.DOTALL)
    matches = pattern.findall(content)
    sentences = []
    for match in matches:
        text = match.strip().replace('\n', ' ')
        if text: sentences.append(text)
    return sentences

def format_srt_time(seconds):
    import datetime
    milliseconds = int((seconds - int(seconds)) * 1000)
    dt = datetime.datetime.utcfromtimestamp(int(seconds))
    return f"{dt.strftime('%H:%M:%S')},{milliseconds:03d}"

def generate_gtts_audio_from_srt(srt_path, output_mp3_path, voice_code="vi"):
    """
    Syntax:
    - Lấy list text từ SRT.
    - Duyệt từng câu (Sentence) -> Gọi gTTS tải mp3 cục bộ.
    - Mod frequency lên 27600Hz trực tiếp.
    - Đo độ dài Audio cục bộ chính xác bằng AudioFileClip. Ghi vô SRT.
    - Nối các mảnh Audio lại bằng pydub và chèn 300ms nghỉ.
    """
    from pydub import AudioSegment
    from moviepy import AudioFileClip
    import subprocess, shutil, tempfile
    
    if voice_code.startswith("gtts:"):
        voice_code = voice_code[5:]
        
    sentences = parse_srt(srt_path)
    if not sentences:
        print("Trống, không có phụ đề để đọc gTTS.")
        return None
        
    print(f"🎙️ Đang gọi Google TTS (Ngôn ngữ: {voice_code}) Từng Câu...")
    
    temp_files = []
    current_time = 0.0
    combined = AudioSegment.empty()
    gap_duration_ms = 300
    gap_audio = AudioSegment.silent(duration=gap_duration_ms)
    
    try:
        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, sentence in enumerate(sentences):
                # 1. Tải TTS riêng cho câu này
                seg_file = os.path.join(tempfile.gettempdir(), f"gtts_seg_{idx}.mp3")
                tts = gTTS(text=sentence, lang=voice_code, slow=False)
                tts.save(seg_file)
                
                # 2. Mod giọng cao
                seg_pitch = seg_file.replace(".mp3", "_pitched.mp3")
                cmd = ['ffmpeg', '-y', '-i', seg_file, '-af', 'asetrate=27600,aresample=44100', seg_pitch]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0 and os.path.exists(seg_pitch):
                    shutil.move(seg_pitch, seg_file)
                    
                # 3. Đo đạc mili-giây tuyệt đối
                with AudioFileClip(seg_file) as audio_clip:
                    seg_duration = audio_clip.duration
                
                # 4. SRT Mốc
                start_str = format_srt_time(current_time)
                current_time += seg_duration
                end_str = format_srt_time(current_time)
                
                f.write(f"{idx+1}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{sentence}\n\n")
                
                # 5. Đưa vào Queue
                temp_files.append(seg_file)
                
                # Tịnh tiến time thêm khoảnh nghỉ
                current_time += (gap_duration_ms / 1000.0)

        # 6. Ghép file âm thanh
        print(f"✅ Ghi xong SRT 100% khớp Audio từng câu. Đang ráp đoạn mp3...")
        for idx, tf in enumerate(temp_files):
            combined += AudioSegment.from_file(tf)
            if idx < len(temp_files) - 1:
                combined += gap_audio
            os.remove(tf)
            
        combined.export(output_mp3_path, format="mp3")
        print(f"✅ Đã tạo Google Audio Tổng hợp: {output_mp3_path}")
        return output_mp3_path
        
        
    except Exception as e:
        print(f"❌ Lỗi khi gọi Google TTS: {e}")
        raise e

def test_gtts_voice(voice_code):
    import tempfile
    if voice_code.startswith("gtts:"):
        voice_code = voice_code[5:]
        
    if voice_code == "en":
        test_text = "Hello there! This is a super fast AI voice from the Google translation system. Have a great day!"
    elif voice_code == "zh-CN":
        test_text = "你好！这是来自谷歌翻译系统的人工智能语音。祝你有美好的一天。"
    elif voice_code == "ja":
        test_text = "こんにちは！これはGoogle翻訳システムからの無料AI音声です。良い一日を。"
    else:
        test_text = "Xin chào bạn, đây là giọng đọc miễn phí siêu tốc từ hệ thống Google Translate. Chúc bạn một ngày vui vẻ."
        
    temp_file = os.path.join(tempfile.gettempdir(), f"gtts_test_{voice_code}.mp3")
    
    try:
        tts = gTTS(text=test_text, lang=voice_code, slow=False)
        tts.save(temp_file)
        
        # Mod test
        import subprocess, shutil
        temp_pitch = temp_file.replace(".mp3", "_pitched.mp3")
        cmd = ['ffmpeg', '-y', '-i', temp_file, '-af', 'asetrate=27600,aresample=44100', temp_pitch]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.exists(temp_pitch):
            shutil.move(temp_pitch, temp_file)
            
        return temp_file
    except Exception as e:
        print(f"❌ Lỗi Test gTTS API: {e}")
        return None