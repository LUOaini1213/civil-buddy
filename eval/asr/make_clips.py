"""Synthesise the voice-input eval clips (Windows only; the clips are committed).

Each sentence in sentences.json is spoken by two Windows Mandarin voices,
then encoded as webm/opus — the container and codec Chrome's MediaRecorder sends
to /api/asr — so the eval also exercises the real decode path.

This is synthetic speech: clean, standard Mandarin, no site noise, no accent.
run_eval.py adds a seeded-noise condition, but neither stands in for a person
on a construction site. The committed clips let anyone rerun run_eval.py
without SAPI.

    python eval/asr/make_clips.py            # writes eval/asr/clips/*.webm + manifest.json
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = HERE / "clips"
# Only two distinct voices render through System.Speech on this machine. Asking for
# "Microsoft Kangkang" (male) reports Kangkang but produces byte-identical audio to
# "Microsoft Yaoyao"; "Microsoft Huihui" equals "Huihui Desktop". A first run with three
# voice names therefore held two copies of one voice. check_distinct() now refuses that.
VOICES = {
    "huihui": "Microsoft Huihui Desktop",
    "yaoyao": "Microsoft Yaoyao",
}
BITRATE = 32_000

PS_SCRIPT = r"""
param([string]$JobFile)
Add-Type -AssemblyName System.Speech
$jobs = Get-Content -Raw -Encoding UTF8 $JobFile | ConvertFrom-Json
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($j in $jobs) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice($j.voice)
  $s.SetOutputToWaveFile($j.wav, $fmt)
  $s.Speak($j.text)
  $s.Dispose()
}
"""


def load_items() -> list[dict]:
    return json.loads((HERE / "sentences.json").read_text(encoding="utf-8"))["items"]


def find_pwsh() -> str:
    # System.Speech in PowerShell 7 reaches the OneCore voices (Kangkang, Yaoyao);
    # Windows PowerShell 5.1 only sees the SAPI5 Desktop voice.
    exe = shutil.which("pwsh")
    if not exe:
        sys.exit("need PowerShell 7 (pwsh) on PATH: winget install Microsoft.PowerShell")
    return exe


def encode_webm(wav: Path, out: Path) -> float:
    import av

    with av.open(str(wav)) as src, av.open(str(out), "w", format="webm") as dst:
        stream = dst.add_stream("libopus", rate=48_000, layout="mono")
        stream.bit_rate = BITRATE
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48_000)
        samples = 0
        for frame in src.decode(audio=0):
            for piece in resampler.resample(frame):
                samples += piece.samples
                for packet in stream.encode(piece):
                    dst.mux(packet)
        for piece in resampler.resample(None):
            for packet in stream.encode(piece):
                dst.mux(packet)
        for packet in stream.encode(None):
            dst.mux(packet)
    return samples / 48_000


def check_distinct(jobs: list[dict]) -> None:
    """Fail if any two voices produced the same PCM for a sentence (silent voice fallback)."""
    import wave

    by_id: dict[str, dict[str, bytes]] = {}
    for job in jobs:
        with wave.open(job["wav"], "rb") as w:
            by_id.setdefault(job["id"], {})[job["voice_key"]] = w.readframes(w.getnframes())
    for sid, pcm in by_id.items():
        if len(set(pcm.values())) < len(pcm):
            sys.exit(f"{sid}: two voices rendered identical audio; SAPI fell back silently")


def main() -> None:
    items = load_items()
    CLIPS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        jobs = [
            {"voice": name, "text": item["text"], "wav": str(tmp / f"{item['id']}_{key}.wav"),
             "clip": f"{item['id']}_{key}.webm", "id": item["id"], "voice_key": key}
            for item in items for key, name in VOICES.items()
        ]
        (tmp / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        (tmp / "tts.ps1").write_text(PS_SCRIPT, encoding="utf-8")
        subprocess.run([find_pwsh(), "-NoProfile", "-File", str(tmp / "tts.ps1"), str(tmp / "jobs.json")], check=True)
        check_distinct(jobs)
        manifest = []
        for job in jobs:
            out = CLIPS / job["clip"]
            seconds = encode_webm(Path(job["wav"]), out)
            data = out.read_bytes()
            manifest.append({
                "clip": job["clip"], "id": job["id"], "voice": job["voice_key"],
                "seconds": round(seconds, 2), "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    total = sum(m["bytes"] for m in manifest)
    print(f"{len(manifest)} clips, {sum(m['seconds'] for m in manifest):.0f} s audio, {total / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
