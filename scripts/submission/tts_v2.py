"""强化版口播：edge-tts 神经语音（XiaoxiaoNeural）→ 统一 24kHz mono WAV，量时长。"""
import asyncio
import json
import subprocess
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUB = Path(r"C:\Users\LW\civil-buddy\output\submission")
OUT = SUB / "tts_v2"
OUT.mkdir(exist_ok=True)
import edge_tts
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

cfg = json.loads((SUB / "narration_v2.json").read_text(encoding="utf-8"))

async def synth():
    for seg in cfg["segments"]:
        mp3 = OUT / f"{seg['id']}.mp3"
        await edge_tts.Communicate(seg["text"], cfg["voice"]).save(str(mp3))

asyncio.run(synth())

total = 0.0
for seg in cfg["segments"]:
    mp3 = OUT / f"{seg['id']}.mp3"
    wav = OUT / f"{seg['id']}.wav"
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, timeout=120,
    )
    assert r.returncode == 0 and wav.exists(), seg["id"]
    with wave.open(str(wav)) as w:
        d = w.getnframes() / w.getframerate()
    total += d
    print(f"  {seg['id']:11s} {d:5.1f}s")
print(f"口播合计 {total:.1f}s")
