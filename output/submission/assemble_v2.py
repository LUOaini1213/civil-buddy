"""强化版总装：片头卡 + 1080p 录屏 + 片尾卡，烧录 ASS 字幕，铺神经语音音轨。"""
import json
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUB = Path(r"C:\Users\LW\civil-buddy\output\submission")
TTS = SUB / "tts_v2"
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

cfg = json.loads((SUB / "narration_v2.json").read_text(encoding="utf-8"))
TEXT = {s["id"]: s["text"] for s in cfg["segments"]}

def wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()

DUR = {sid: wav_dur(TTS / f"{sid}.wav") for sid in TEXT}
sched = json.loads((SUB / "rec_v2_schedule.json").read_text(encoding="utf-8"))
demo_total = sched["total"]
marks = dict(sched["marks"])
webm = Path(sched["video"])

TITLE_DUR = round(DUR["t0_title"] + 0.6, 2)          # 8.2
END_DUR = round(DUR["s10_end"] + 0.6, 2)             # 12.5
TOTAL = TITLE_DUR + demo_total + END_DUR
print(f"片头 {TITLE_DUR}s + 演示 {demo_total:.1f}s + 片尾 {END_DUR}s = {TOTAL:.1f}s")
assert TOTAL <= 119.5, TOTAL

# ---------- 时间轴：每段口播的绝对开始时刻 ----------
starts = {"t0_title": 0.4, "s10_end": TITLE_DUR + demo_total + 0.35}
for sid, t in marks.items():
    starts[sid] = TITLE_DUR + t

# ---------- 1) 整条 WAV ----------
params = None
with wave.open(str(TTS / "t0_title.wav")) as w0:
    params = w0.getparams()
rate, sw, ch = params.framerate, params.sampwidth, params.nchannels
buf = bytearray(int((TOTAL + 0.3) * rate) * sw * ch)
for sid, st in starts.items():
    with wave.open(str(TTS / f"{sid}.wav")) as w:
        frames = w.readframes(w.getnframes())
    off = int(st * rate) * sw * ch
    end = min(off + len(frames), len(buf))
    buf[off:end] = frames[: end - off]
full = SUB / "narration_v2_full.wav"
with wave.open(str(full), "wb") as out:
    out.setparams(params)
    out.writeframes(bytes(buf))

# ---------- 2) ASS 字幕：按标点切块，块时长按字数占比 ----------
def ts(sec: float) -> str:
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def chunks(text: str) -> list[str]:
    parts = re.split(r"[，。；：、]|——", text)
    parts = [p.strip() for p in parts if p.strip()]
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) <= 18:
            cur += "，" + p
        else:
            if cur:
                out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return out

events = []
for sid, st in starts.items():
    cs = chunks(TEXT[sid])
    total_chars = sum(len(c) for c in cs)
    t = st
    for c in cs:
        d = DUR[sid] * len(c) / total_chars
        events.append((t, min(t + d, TOTAL - 0.1), c))
        t += d
events.sort()

ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080",
       "WrapStyle: 2", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: cb,Microsoft YaHei,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H7F000000,-1,0,0,0,100,100,0,0,3,4,0,2,60,60,48,134",
       "",
       "[Events]",
       "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for a, b, c in events:
    ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},cb,,0,0,0,,{c}")
(SUB / "subs_v2.ass").write_text("\n".join(ass), encoding="utf-8-sig")
print(f"字幕 {len(events)} 条")

# ---------- 3) ffmpeg 总装 ----------
final = SUB / "02-介绍视频-CivilBuddy.mp4"
cmd = [FFMPEG, "-y",
       "-loop", "1", "-t", str(TITLE_DUR), "-framerate", "25", "-i", str(SUB / "card_title.png"),
       "-i", str(webm),
       "-loop", "1", "-t", str(END_DUR), "-framerate", "25", "-i", str(SUB / "card_end.png"),
       "-i", str(full),
       "-filter_complex",
       "[0:v]scale=1920:1080,setsar=1,fps=25,format=yuv420p[v0];"
       "[1:v]scale=1920:1080,setsar=1,fps=25,format=yuv420p[v1];"
       "[2:v]scale=1920:1080,setsar=1,fps=25,format=yuv420p[v2];"
       "[v0][v1][v2]concat=n=3:v=1:a=0[vc];"
       "[vc]ass=subs_v2.ass[vo]",
       "-map", "[vo]", "-map", "3:a",
       "-c:v", "libx264", "-crf", "19", "-preset", "medium",
       "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
       str(final)]
r = subprocess.run(cmd, cwd=str(SUB), capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=1200)
assert r.returncode == 0, (r.stderr or "")[-800:]

# ---------- 4) 终验 ----------
d = final.read_bytes()
i = d.find(b"mvhd")
ver = d[i + 4]
if ver == 0:
    tsc, dur = struct.unpack(">II", d[i + 16:i + 24])
else:
    tsc = struct.unpack(">I", d[i + 24:i + 28])[0]
    dur = struct.unpack(">Q", d[i + 28:i + 36])[0]
sec = dur / tsc
mb = final.stat().st_size / 1e6
assert 110 <= sec <= 120.0, sec
print(f"FINAL {final.name}  {sec:.1f}s（1 分 {sec-60:.0f} 秒）  {mb:.1f}MB  1080p+字幕+神经口播")
