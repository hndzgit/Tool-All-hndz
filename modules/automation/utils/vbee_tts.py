import requests
import json
import time
import os
import re

def check_vbee_key():
    import config.config as cfg
    live_cfg = cfg.load_settings()
    VBEE_API_KEY = live_cfg.get("vbee_api_key", "")
    VBEE_APP_ID = live_cfg.get("vbee_app_id", "")
    if not VBEE_API_KEY or len(VBEE_API_KEY) < 10 or not VBEE_APP_ID:
        raise ValueError("Chưa thiết lập VBEE API Key hoặc App ID. Vui lòng vào 'Cấu hình API' để nhập đầy đủ.")
    return VBEE_APP_ID, VBEE_API_KEY

def parse_srt(srt_file):
    """Đọc file SRT và trích xuất danh sách các câu văn"""
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Pattern tìm text: bỏ qua số thứ tự và timecode
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

VBEE_API_VOICE_MAP = {
    "hn_male_minhquan_yt_24k-pre": "hn_male_minhquan_yt-stable",
    "hn_female_ngochuyen_full_24k-st": "hn_female_ngochuyen_full_48k-fhg",
}

def resolve_vbee_voice_code(code):
    if not code:
        return code
    if code.startswith("vbee:"):
        code = code[5:]
    return VBEE_API_VOICE_MAP.get(code, code)

def process_single_vbee_sentence(idx, sentence, voice_code, app_id, token):
    """
    Xử lý gọi Vbee cho 1 đoạn văn nhỏ độc lập. Có tính năng tự động Thử lại và Cứu hộ (Fallback).
    """
    import tempfile
    from gtts import gTTS
    voice_code = resolve_vbee_voice_code(voice_code)
    url = "https://vbee.vn/api/v1/tts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "app_id": app_id,
        "inputText": sentence,
        "voiceCode": voice_code,
        "callbackUrl": "https://vbee.vn/"
    }
    seg_file = os.path.join(tempfile.gettempdir(), f"vbee_seg_{idx}.mp3")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            
            if res_data.get("status") == 1:
                request_id = res_data.get("result", {}).get("request_id")
                if not request_id:
                    raise Exception("Không nhận được request_id từ Vbee API")
                    
                poll_url = f"https://vbee.vn/api/v1/tts/{request_id}"
                max_poll_retries = 30
                for _ in range(max_poll_retries):
                    time.sleep(2)
                    poll_res = requests.get(poll_url, headers=headers, timeout=15)
                    poll_res.raise_for_status()
                    poll_data = poll_res.json()
                    status_code = poll_data.get("result", {}).get("status")
                    
                    if status_code == "SUCCESS" or status_code == 1:
                        audio_url = poll_data.get("result", {}).get("audio_link")
                        if audio_url:
                            mp3_res = requests.get(audio_url, timeout=20)
                            mp3_res.raise_for_status()
                            with open(seg_file, "wb") as f:
                                f.write(mp3_res.content)
                            return idx, sentence, seg_file
                        else:
                            raise Exception("Vbee API trả về SUCCESS nhưng mất audio_url.")
                    elif status_code == "FAILURE" or status_code == 2:
                        raise Exception(f"Vbee render thất bại: {poll_data.get('error_message')}")
                raise Exception("Timeout khi chờ Vbee render.")
            else:
                err_code = res_data.get("error_code")
                if err_code == 1045:
                    if data["voiceCode"] == "hn_male_minhquan_yt_24k-pre":
                        print("⚠️ Giọng Minh Quân Pro (24k-pre) chưa được mở quyền trên App ID này. Đang chuyển sang giọng Minh Quân YT Stable...")
                        data["voiceCode"] = "hn_male_minhquan_yt-stable"
                        continue
                    elif data["voiceCode"] == "hn_female_ngochuyen_full_24k-st":
                        print("⚠️ Giọng Ngọc Huyền 2.0 (24k-st) chưa được mở quyền trên App ID này. Đang chuyển sang giọng Ngọc Huyền 48k...")
                        data["voiceCode"] = "hn_female_ngochuyen_full_48k-fhg"
                        continue
                raise Exception(f"Lỗi Vbee API (Post): {res_data.get('error_message') or f'Error Code {err_code}'}")
                
        except Exception as e:
            err_msg = str(e).lower()
            print(f"⚠️ Vbee bị kẹt (Lần {attempt+1}/{max_retries}) câu {idx}: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)  # Nghỉ 3s cho Server Vbee thở trước khi thử lại
            else:
                print(f"🔄 Vbee gặp sự cố (hết token hoặc lỗi mạng/502) ở câu {idx}. Kích hoạt Giọng Cứu Hộ (Google TTS) để tránh mất tiếng...")
                try:
                    tts = gTTS(text=sentence, lang='vi', slow=False)
                    tts.save(seg_file)
                    return idx, sentence, seg_file
                except Exception as ex:
                    print(f"❌ Lỗi cứu hộ Google TTS câu {idx}: {ex}")
                    return idx, sentence, None
    
    return idx, sentence, None

def generate_vbee_audio_from_srt(srt_path, output_mp3_path, voice_code=None):
    """
    Tải audio từng câu bằng ThreadPool (chạy song song) để tiết kiệm thời gian.
    Đo độ dài từng mảnh và ghi mốc thời gian SRT tuyệt đối (100% khớp tiếng).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pydub import AudioSegment
    from moviepy import AudioFileClip
    
    if not voice_code:
        import config.config as cfg
        voice_code = cfg.VBEE_VOICE
    
    app_id, token = check_vbee_key()
    if voice_code.startswith("vbee:"):
        voice_code = voice_code[5:]
    
    sentences = parse_srt(srt_path)
    if not sentences:
        print("⚠️ SRT trống, không có chữ để đọc.")
        return None
        
    print(f"🎙️ Đang gọi Vbee API (Giọng: {voice_code}) Từng Câu (Multithread)...")
    
    results_map = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_single_vbee_sentence, i, s, voice_code, app_id, token): i for i, s in enumerate(sentences)}
        for future in as_completed(futures):
            idx, sent, seg_path = future.result()
            results_map[idx] = (sent, seg_path)
            
    # Kiểm tra xem có câu nào bị lỗi không
    temp_files = []
    current_time = 0.0
    combined = AudioSegment.empty()
    gap_duration_ms = 300
    gap_audio = AudioSegment.silent(duration=gap_duration_ms)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx in range(len(sentences)):
            sent, seg_file = results_map.get(idx, (sentences[idx], None))
            # Nếu vbee bị lỗi câu đó, ta chèn 1s khoảng lặng để chống tràn timeline
            if not seg_file or not os.path.exists(seg_file):
                print(f"⚠️ Dùng khoảng lặng bù vào do câu {idx} sinh lỗi.")
                seg_duration = 1.0
            else:
                try: # moviepy có thể kén mp3 tải thẳng
                    with AudioFileClip(seg_file) as audio_clip:
                        seg_duration = audio_clip.duration
                except Exception as e:
                    # Nếu moviepy lỗi đọc, dự đoán dựa trên pydub hoặc số lượng chữ
                    seg_duration = AudioSegment.from_file(seg_file).duration_seconds
                
                temp_files.append(seg_file)
                
            start_str = format_srt_time(current_time)
            current_time += seg_duration
            end_str = format_srt_time(current_time)
            
            f.write(f"{idx+1}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{sent}\n\n")
            
            current_time += (gap_duration_ms / 1000.0)
            
    # Gộp phím đàn
    print(f"✅ Ghi xong SRT 100% khớp Audio từng câu. Đang ráp đoạn mp3...")
    
    # Tạo output bằng pydub
    for idx in range(len(sentences)):
        sent, seg_file = results_map.get(idx, (None, None))
        if seg_file and os.path.exists(seg_file):
            combined += AudioSegment.from_file(seg_file)
            if idx < len(sentences) - 1:
                combined += gap_audio
            os.remove(seg_file)
        else:
            combined += AudioSegment.silent(duration=1000)
            if idx < len(sentences) - 1:
                combined += gap_audio
                
    combined.export(output_mp3_path, format="mp3")
    print(f"✅ Đã tạo Vbee Audio Tổng hợp Siêu Chuẩn: {output_mp3_path}")
    
    return output_mp3_path

def test_vbee_voice(voice_code):
    """
    Test nhanh giọng đọc Vbee
    """
    voice_code = resolve_vbee_voice_code(voice_code)
        
    app_id, token = check_vbee_key()
    test_text = "Chào bạn, đây là giọng đọc thử nghiệm từ hệ thống Vbee AI."
    
    url = "https://vbee.vn/api/v1/tts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "app_id": app_id,
        "inputText": test_text,
        "voiceCode": voice_code,
        "callbackUrl": "https://vbee.vn/"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        res_data = response.json()
        
        if res_data.get("status") == 1:
            request_id = res_data.get("result", {}).get("request_id")
            if not request_id: raise Exception("Không nhận được request_id từ Vbee API")
            
            poll_url = f"https://vbee.vn/api/v1/tts/{request_id}"
            for _ in range(15):
                time.sleep(2)
                poll_res = requests.get(poll_url, headers=headers)
                poll_res.raise_for_status()
                poll_data = poll_res.json()
                status_code = poll_data.get("result", {}).get("status")
                
                if status_code == "SUCCESS" or status_code == 1:
                    audio_url = poll_data.get("result", {}).get("audio_link")
                    if audio_url:
                        mp3_res = requests.get(audio_url)
                        mp3_res.raise_for_status()
                        import tempfile
                        temp_file = os.path.join(tempfile.gettempdir(), f"vbee_test_{voice_code}.mp3")
                        with open(temp_file, "wb") as f:
                            f.write(mp3_res.content)
                        return temp_file
                elif status_code == "FAILURE" or status_code == 2:
                    raise Exception(f"Vbee render thất bại: {poll_data.get('error_message')}")
            raise Exception("Hết thời gian chờ (Timeout) khi render test audio.")
        else:
            raise Exception(f"Lỗi Vbee API: {res_data.get('error_message')}")
    except Exception as e:
        print(f"❌ Lỗi Test Vbee API: {e}")
        return None
