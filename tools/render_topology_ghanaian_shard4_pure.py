#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import os
import random
import shutil
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import requests

import render_topology_voices as base
from render_topology_ghanaian_abena import ENDPOINT, MAX_TEXT_CHARS, VOICE_ID, group_for_api

SAMPLE_RATE = 48_000
TOTAL_DURATION = 2328.160
SHARD_INDEX = 3
SHARD_COUNT = 4


def synthesize(session: requests.Session, segment: base.Segment, target: Path) -> None:
    payload = {"text": segment.text, "voice": VOICE_ID, "speed": 1.0}
    for attempt in range(1, 9):
        try:
            response = session.post(ENDPOINT, json=payload, timeout=180)
            if response.status_code == 429:
                raise RuntimeError("rate limited")
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success" or not data.get("audio_base64"):
                raise RuntimeError(data.get("message") or data.get("error") or str(data)[:300])
            target.write_bytes(base64.b64decode(data["audio_base64"]))
            if target.stat().st_size < 1000:
                raise RuntimeError("empty audio")
            return
        except Exception as exc:
            target.unlink(missing_ok=True)
            if attempt == 8:
                raise RuntimeError(f"Segment {segment.number} failed: {exc}") from exc
            print(f"Segment {segment.number}, attempt {attempt}: {exc}; retrying", flush=True)
            time.sleep(min(45.0, 2.0 ** attempt + random.random() * 2.0))


def read_pcm(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as reader:
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        rate = reader.getframerate()
        frames = reader.readframes(reader.getnframes())
    if width == 1:
        values = (np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128) << 8
    elif width == 2:
        values = np.frombuffer(frames, dtype="<i2").astype(np.int16)
    elif width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        values32 = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        values32 = np.where(values32 & 0x800000, values32 - 0x1000000, values32)
        values = np.clip(values32 >> 8, -32768, 32767).astype(np.int16)
    elif width == 4:
        values = np.clip(np.frombuffer(frames, dtype="<i4") >> 16, -32768, 32767).astype(np.int16)
    else:
        raise RuntimeError(f"Unsupported WAV sample width: {width}")
    if channels > 1:
        values = np.rint(values.reshape(-1, channels).astype(np.float32).mean(axis=1)).astype(np.int16)
    return values, rate


def resample(values: np.ndarray, source_rate: int, target_count: int | None = None) -> np.ndarray:
    if target_count is None:
        target_count = int(round(len(values) * SAMPLE_RATE / source_rate))
    if len(values) == 0 or target_count <= 0:
        return np.zeros(max(0, target_count), dtype=np.int16)
    if len(values) == target_count:
        return values.copy()
    source_positions = np.linspace(0.0, 1.0, len(values), endpoint=False)
    target_positions = np.linspace(0.0, 1.0, target_count, endpoint=False)
    return np.clip(np.rint(np.interp(target_positions, source_positions, values.astype(np.float32))), -32768, 32767).astype(np.int16)


def build(selected: list[base.Segment], files: list[Path], output: Path) -> list[dict]:
    timeline = np.zeros(int(math.ceil(TOTAL_DURATION * SAMPLE_RATE)), dtype=np.int16)
    statistics: list[dict] = []
    for index, (segment, path) in enumerate(zip(selected, files), start=1):
        raw, source_rate = read_pcm(path)
        natural = resample(raw, source_rate)
        window = segment.end - segment.start
        lead = min(0.045, window * 0.03)
        tail = min(0.055, window * 0.03)
        available_count = max(1, int(round(max(0.2, window - lead - tail) * SAMPLE_RATE)))
        speed_factor = max(1.0, len(natural) / available_count)
        fitted = resample(natural, SAMPLE_RATE, available_count) if len(natural) > available_count else natural
        fade = min(len(fitted), int(0.035 * SAMPLE_RATE))
        if fade > 1:
            fitted[-fade:] = np.rint(fitted[-fade:].astype(np.float32) * np.linspace(1.0, 0.0, fade, dtype=np.float32)).astype(np.int16)
        start = int(round((segment.start + lead) * SAMPLE_RATE))
        end = min(len(timeline), start + len(fitted))
        timeline[start:end] = fitted[: end - start]
        statistics.append({
            "segment": segment.number,
            "start": segment.start,
            "end": segment.end,
            "source_seconds": round(len(natural) / SAMPLE_RATE, 3),
            "speed_factor": round(speed_factor, 4),
            "cues": list(segment.cues),
        })
        print(f"Aligned {index}/{len(selected)}", flush=True)
    with wave.open(str(output), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        chunk = SAMPLE_RATE * 30
        for start in range(0, len(timeline), chunk):
            writer.writeframes(timeline[start:start + chunk].tobytes())
    return statistics


def main() -> None:
    srt_text = base.gzip.decompress(base.base64.b64decode(base.SRT_DATA)).decode("utf-8")
    cues = base.parse_srt(srt_text)
    segments = group_for_api(cues)
    selected = [segment for segment in segments if (segment.number - 1) % SHARD_COUNT == SHARD_INDEX]
    print(f"Pure-Python shard 4: {len(selected)} of {len(segments)} segments", flush=True)
    work = Path(tempfile.mkdtemp(prefix="ghana_shard4_pure_"))
    try:
        audio = work / "audio"
        audio.mkdir()
        session = requests.Session()
        session.headers.update({"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "TopologyLessonRenderer/1.0"})
        files: list[Path] = []
        for index, segment in enumerate(selected, start=1):
            target = audio / f"segment_{segment.number:03d}.wav"
            synthesize(session, segment, target)
            files.append(target)
            print(f"Synthesized {index}/{len(selected)}", flush=True)
            time.sleep(0.25)
        Path("output").mkdir(exist_ok=True)
        output = Path("output/topology_ghanaian_shard_4.wav")
        statistics = build(selected, files, output)
        manifest = {
            "voice": VOICE_ID,
            "region": "Ghana",
            "gender": "male",
            "duration_seconds": TOTAL_DURATION,
            "total_segments": len(segments),
            "shard_index": SHARD_INDEX,
            "shard_count": SHARD_COUNT,
            "selected_segments": len(selected),
            "speed_factor_min": min(item["speed_factor"] for item in statistics),
            "speed_factor_max": max(item["speed_factor"] for item in statistics),
            "speed_factor_mean": sum(item["speed_factor"] for item in statistics) / len(statistics),
            "segments": statistics,
        }
        Path("output/topology_ghanaian_shard_4.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps({key: value for key, value in manifest.items() if key != "segments"}, indent=2))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
