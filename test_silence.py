import os
import subprocess
import re

def is_audio_silent(filepath, deep_check=False):
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        
        ffmpeg_cmd = ['ffmpeg', '-i', filepath, '-af', 'volumedetect', '-f', 'null', 'NUL']
        print(f"Running: {' '.join(ffmpeg_cmd)}")
        res = subprocess.run(
            ffmpeg_cmd, 
            capture_output=True, text=True, timeout=30, creationflags=creationflags
        )
        out = res.stderr
        # print("FFmpeg output:")
        # print(out[:500])
        max_volume = None
        for line in out.split('\\n'):
            if 'max_volume' in line:
                try:
                    if '-inf' in line:
                        max_volume = float('-inf')
                    else:
                        m = re.search(r'max_volume:\s*([-\d.]+)\s*dB', line)
                        if m: max_volume = float(m.group(1))
                except ValueError:
                    continue
        
        print(f"Detected max_volume: {max_volume}")
        if max_volume is None: return False
        if max_volume == float('-inf') or max_volume <= -70:
            return True
        if deep_check and max_volume <= -60:
            return True
        return False
    except Exception as e:
        print(f"Exception: {e}")
        return False

# Generate a silent wav file
import wave
import struct

with wave.open("test_silent.wav", "w") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(44100)
    for _ in range(44100): # 1 second of silence
        f.writeframes(struct.pack('h', 0))

print("Is silent?", is_audio_silent("test_silent.wav"))
