import requests
import json
import sys

def test_vbee(app_id, token):
    url = "https://vbee.vn/api/v1/tts"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Test 1: app_id in body
    data1 = {
        "app_id": app_id,
        "input_text": "Xin chào",
        "voice": "hn-quynhanh",
        "audio_type": "mp3"
    }
    print("Test 1 (app_id in body):")
    res1 = requests.post(url, headers=headers, json=data1)
    print(res1.status_code, res1.text)

    # Test 2: app_id in header
    headers2 = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "app_id": app_id
    }
    data2 = {
        "input_text": "Xin chào",
        "voice": "hn-quynhanh",
        "audio_type": "mp3"
    }
    print("\\nTest 2 (app_id in header):")
    res2 = requests.post(url, headers=headers2, json=data2)
    print(res2.status_code, res2.text)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_vbee.py <app_id> <token>")
        sys.exit(1)
    test_vbee(sys.argv[1], sys.argv[2])