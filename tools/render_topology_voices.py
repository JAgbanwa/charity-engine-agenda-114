#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import gzip
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import edge_tts
import numpy as np

SRT_DATA = "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"

VOICE = os.environ.get("VOICE", "en-GB-RyanNeural")
OUTPUT_NAME = os.environ.get("OUTPUT_NAME", "topology_voice.m4a")
TTS_RATE = os.environ.get("TTS_RATE", "+0%")
SAMPLE_RATE = 48_000
TOTAL_DURATION = 2328.160
MAX_CONCURRENCY = int(os.environ.get("TTS_CONCURRENCY", "3"))


@dataclass(frozen=True)
class Cue:
    number: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Segment:
    number: int
    start: float
    end: float
    text: str
    cues: tuple[int, ...]


def parse_time(value: str) -> float:
    hour, minute, rest = value.split(":")
    second, millisecond = rest.split(",")
    return int(hour) * 3600 + int(minute) * 60 + int(second) + int(millisecond) / 1000


def parse_srt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        start_text, end_text = lines[1].split(" --> ", 1)
        spoken = re.sub(r"<[^>]+>", "", " ".join(lines[2:])).replace("&amp;", "and")
        cues.append(Cue(int(lines[0]), parse_time(start_text), parse_time(end_text), spoken))
    if not cues:
        raise RuntimeError("No subtitle cues were parsed")
    return cues


def group_cues(cues: list[Cue]) -> list[Segment]:
    groups: list[list[Cue]] = []
    current = [cues[0]]
    for cue in cues[1:]:
        if cue.start - current[-1].end > 0.2:
            groups.append(current)
            current = [cue]
        else:
            current.append(cue)
    groups.append(current)
    return [
        Segment(i + 1, group[0].start, group[-1].end, " ".join(c.text for c in group), tuple(c.number for c in group))
        for i, group in enumerate(groups)
    ]


def run(command: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def media_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture=True,
    )
    return float(result.stdout.decode().strip())


def atempo_chain(factor: float) -> str:
    factors: list[float] = []
    while factor > 2.0:
        factors.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        factors.append(0.5)
        factor /= 0.5
    factors.append(factor)
    return ",".join(f"atempo={value:.8f}" for value in factors)


async def synthesize(segment: Segment, target: Path, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        for attempt in range(1, 9):
            try:
                communication = edge_tts.Communicate(
                    segment.text,
                    VOICE,
                    rate=TTS_RATE,
                    volume="+0%",
                    pitch="+0Hz",
                    connect_timeout=25,
                    receive_timeout=120,
                )
                await communication.save(str(target))
                if target.exists() and target.stat().st_size > 1000:
                    return
                raise RuntimeError("The TTS service returned an empty file")
            except Exception as exc:
                target.unlink(missing_ok=True)
                if attempt == 8:
                    raise RuntimeError(f"Segment {segment.number} failed: {exc}") from exc
                await asyncio.sleep(min(35.0, 1.8 ** attempt + random.random() * 2.0))


async def synthesize_all(segments: list[Segment], folder: Path) -> list[Path]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    paths = [folder / f"segment_{segment.number:03d}.mp3" for segment in segments]
    tasks = [asyncio.create_task(synthesize(segment, path, semaphore)) for segment, path in zip(segments, paths)]
    completed = 0
    for task in asyncio.as_completed(tasks):
        await task
        completed += 1
        if completed % 10 == 0 or completed == len(tasks):
            print(f"Synthesized {completed}/{len(tasks)} natural speech segments", flush=True)
    return paths


def decode_and_fit(source: Path, available_seconds: float) -> tuple[np.ndarray, float, float]:
    source_seconds = media_duration(source)
    speed_factor = max(1.0, source_seconds / max(available_seconds, 0.2))
    filters = [
        "aresample=48000",
        "aformat=sample_fmts=s16:channel_layouts=mono",
    ]
    if speed_factor > 1.0005:
        filters.append(atempo_chain(speed_factor))
    filters.extend(["highpass=f=45", "lowpass=f=15500", "afade=t=in:st=0:d=0.020"])
    result = run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-af", ",".join(filters), "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "pipe:1",
        ],
        capture=True,
    )
    samples = np.frombuffer(result.stdout, dtype="<i2").copy()
    maximum = int(round(available_seconds * SAMPLE_RATE))
    if len(samples) > maximum:
        samples = samples[:maximum]
    fade = min(len(samples), int(0.035 * SAMPLE_RATE))
    if fade > 1:
        samples[-fade:] = np.rint(
            samples[-fade:].astype(np.float32) * np.linspace(1.0, 0.0, fade, dtype=np.float32)
        ).astype(np.int16)
    return samples, source_seconds, speed_factor


def build_timeline(segments: list[Segment], files: list[Path], output_wav: Path) -> list[dict]:
    timeline = np.zeros(int(math.ceil(TOTAL_DURATION * SAMPLE_RATE)), dtype=np.int16)
    statistics: list[dict] = []
    for index, (segment, source) in enumerate(zip(segments, files), start=1):
        window = segment.end - segment.start
        lead = min(0.045, window * 0.03)
        tail = min(0.055, window * 0.03)
        samples, source_seconds, speed_factor = decode_and_fit(source, max(0.2, window - lead - tail))
        start = int(round((segment.start + lead) * SAMPLE_RATE))
        end = min(len(timeline), start + len(samples))
        timeline[start:end] = samples[: end - start]
        statistics.append(
            {
                "segment": segment.number,
                "start": segment.start,
                "end": segment.end,
                "source_seconds": round(source_seconds, 3),
                "speed_factor": round(speed_factor, 4),
                "cues": list(segment.cues),
            }
        )
        if index % 10 == 0 or index == len(segments):
            print(f"Aligned {index}/{len(segments)} segments", flush=True)
    with wave.open(str(output_wav), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        chunk = SAMPLE_RATE * 30
        for start in range(0, len(timeline), chunk):
            writer.writeframes(timeline[start : start + chunk].tobytes())
    return statistics


def encode(input_wav: Path, output_m4a: Path) -> None:
    output_m4a.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_wav),
            "-af", "loudnorm=I=-18:TP=-1.5:LRA=8", "-c:a", "aac", "-b:a", "128k",
            "-ar", str(SAMPLE_RATE), "-ac", "1", "-t", f"{TOTAL_DURATION:.3f}",
            "-movflags", "+faststart", str(output_m4a),
        ]
    )


def main() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")
    srt_text = gzip.decompress(base64.b64decode(SRT_DATA)).decode("utf-8")
    cues = parse_srt(srt_text)
    segments = group_cues(cues)
    print(f"Voice: {VOICE}; cues: {len(cues)}; speech segments: {len(segments)}", flush=True)
    work = Path(tempfile.mkdtemp(prefix="topology_tts_"))
    try:
        audio_folder = work / "audio"
        audio_folder.mkdir()
        files = asyncio.run(synthesize_all(segments, audio_folder))
        timeline_wav = work / "timeline.wav"
        statistics = build_timeline(segments, files, timeline_wav)
        output = Path("output") / OUTPUT_NAME
        encode(timeline_wav, output)
        duration = media_duration(output)
        if abs(duration - TOTAL_DURATION) > 0.3:
            raise RuntimeError(f"Output duration {duration:.3f}s differs from target {TOTAL_DURATION:.3f}s")
        manifest = {
            "voice": VOICE,
            "duration_seconds": duration,
            "subtitle_cues": len(cues),
            "speech_segments": len(segments),
            "rate": TTS_RATE,
            "speed_factor_min": min(item["speed_factor"] for item in statistics),
            "speed_factor_max": max(item["speed_factor"] for item in statistics),
            "speed_factor_mean": sum(item["speed_factor"] for item in statistics) / len(statistics),
            "segments": statistics,
        }
        (Path("output") / f"{Path(OUTPUT_NAME).stem}.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps({key: value for key, value in manifest.items() if key != "segments"}, indent=2), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
