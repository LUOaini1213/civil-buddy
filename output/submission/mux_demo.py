"""按录制打点把口播摆上时间轴，与 webm 合成 h264+aac 成片。"""
import json
import struct
import subprocess
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUB = Path(r"C:\Users\LW\civil-buddy\output/submission")
TTS = SUB / "tts_demo"
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

sched = json.loads((SUB / "rec_schedule.json").read_text(encoding="utf-8"))
total = sched["total"]
marks = sched["marks"]
webm = Path(sched["video"])
assert webm.exists()

# 1) 整条 WAV：静音底 + 每段按打点摆放
with wave.open(str(TTS / "s0_intro.wav")) as w0:
    params = w0.getparams()
rate, sw, ch = params.framerate, params.sampwidth, params.nchannels
total_frames = int((total + 0.5) * rate)
buf = bytearray(total_frames * sw * ch)
for seg, start in marks:
    with wave.open(str(TTS / f"{seg}.wav")) as w:
        frames = w.readframes(w.getnframes())
    off = int(start * rate) * sw * ch
    end = min(off + len(frames), len(buf))
    buf[off:end] = frames[: end - off]
full = SUB / "narration_demo_full.wav"
with wave.open(str(full), "wb") as out:
    out.setparams(params)
    out.writeframes(bytes(buf))
print(f"音轨 {len(buf)/(rate*sw*ch):.1f}s")

# 2) 合成（h264+aac+faststart）
final = SUB / "02-介绍视频-CivilBuddy.mp4"
r = subprocess.run(
    [FFMPEG, "-y", "-i", str(webm), "-i", str(full),
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
     "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
     str(final)],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
)
assert r.returncode == 0, (r.stderr or "")[-600:]

# 3) 终验
d = final.read_bytes()
i = d.find(b"mvhd")
ver = d[i + 4]
if ver == 0:
    ts, dur = struct.unpack(">II", d[i + 16:i + 24])
else:
    ts = struct.unpack(">I", d[i + 24:i + 28])[0]
    dur = struct.unpack(">Q", d[i + 28:i + 36])[0]
sec = dur / ts
mb = final.stat().st_size / 1e6
assert sec <= 120.0, sec
print(f"FINAL {final.name}  {sec:.1f}s  {mb:.1f}MB  真机录屏+口播")
