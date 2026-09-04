import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'automation')))
from config import config as cfg
from utils.vbee_tts import test_vbee_voice

voice_options = [
    "hn_female_ngochuyen_full_48k-fhg",
    "hn_female_maiphuong_ngam_48k-fhg",
    "hn_female_thaotrinh_full_48k-fhg",
    "sg_female_huonggiang_full_48k-fhg",
    "hn_male_minhhoang_full_48k-fhg",
    "bt_female_thaophuong_diem_48k-fhg"
]

print("Keys:", cfg.VBEE_APP_ID, cfg.VBEE_API_KEY)
for v in voice_options:
    print(f"Testing {v}...")
    res = test_vbee_voice(v)
    print(f"Result for {v}: {res}")