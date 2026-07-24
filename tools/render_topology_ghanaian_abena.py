#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

import render_topology_voices as base

ENDPOINT = "https://abena.mobobi.com/playground/api/v1/tts/synthesize/"
VOICE_ID = "kwabena_eng"
SHARD_INDEX = int(os.environ.get("SHARD_INDEX", "0"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "4"))
MAX_TEXT_CHARS = 490
OUTPUT_NAME = os.environ.get("OUTPUT_NAME", f"ghanaian_shard_{SHARD_INDEX + 1}.m4a")


def group_for_api(cues: list[base.Cue]) -> list[base.Segment]:
    groups: list[list[base.Cue]] = []
    current = [cues[0]]
    for cue in cues[1:]:
        proposed = " ".join(item.text for item in current + [cue])
        gap = cue.start - current[-1].end
        if gap > 0.2 or len(proposed) > MAX_TEXT_CHARS:
            groups.append(current)
            current = [cue]
        else:
            current.append(cue)
    groups.append(current)
    segments = [
        base.Segment(
            number=index + 1,
            start=group[0].start,
            end=group[-1].end,
            text=" ".join(item.text for item in group),
            cues=tuple(item.number for item in group),
        )
        for index, group in enumerate(groups)
    ]
    if max(len(segment.text) for segment in segments) > 500:
        raise RuntimeError("A grouped segment exceeds the 500-character API limit")
    return segments


def synthesize_segment(session: requests.Session, segment: base.Segment, target: Path) -> None:
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
                raise RuntimeError("The API returned an empty audio file")
            return
        except Exception as exc:
            target.unlink(missing_ok=True)
            if attempt == 8:
                raise RuntimeError(f"Segment {segment.number} failed after retries: {exc}") from exc
            delay = min(45.0, 2.0 ** attempt + random.random() * 2.0)
            print(f"Segment {segment.number}, attempt {attempt}: {exc}; retrying", flush=True)
            time.sleep(delay)


def encode_partial(input_wav: Path, output_m4a: Path) -> None:
    output_m4a.parent.mkdir(parents=True, exist_ok=True)
    base.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_wav),
            "-c:a", "aac", "-b:a", "128k", "-ar", str(base.SAMPLE_RATE), "-ac", "1",
            "-t", f"{base.TOTAL_DURATION:.3f}", "-movflags", "+faststart", str(output_m4a),
        ]
    )


def main() -> None:
    if SHARD_COUNT < 1 or not 0 <= SHARD_INDEX < SHARD_COUNT:
        raise ValueError("Invalid shard configuration")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")

    srt_text = base.gzip.decompress(base.base64.b64decode(base.SRT_DATA)).decode("utf-8")
    cues = base.parse_srt(srt_text)
    segments = group_for_api(cues)
    selected = [segment for segment in segments if (segment.number - 1) % SHARD_COUNT == SHARD_INDEX]
    print(
        f"Ghanaian voice {VOICE_ID}; total segments={len(segments)}; "
        f"shard={SHARD_INDEX + 1}/{SHARD_COUNT}; selected={len(selected)}",
        flush=True,
    )

    work = Path(tempfile.mkdtemp(prefix=f"ghana_voice_{SHARD_INDEX}_"))
    try:
        audio_folder = work / "audio"
        audio_folder.mkdir()
        session = requests.Session()
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "TopologyLessonRenderer/1.0",
            }
        )
        files: list[Path] = []
        for index, segment in enumerate(selected, start=1):
            target = audio_folder / f"segment_{segment.number:03d}.wav"
            synthesize_segment(session, segment, target)
            files.append(target)
            print(f"Synthesized {index}/{len(selected)} in shard", flush=True)
            time.sleep(0.25)

        timeline = work / "partial_timeline.wav"
        statistics = base.build_timeline(selected, files, timeline)
        output = Path("output") / OUTPUT_NAME
        encode_partial(timeline, output)
        duration = base.media_duration(output)
        if abs(duration - base.TOTAL_DURATION) > 0.3:
            raise RuntimeError(f"Output duration {duration:.3f}s differs from target")
        manifest = {
            "voice": VOICE_ID,
            "region": "Ghana",
            "gender": "male",
            "duration_seconds": duration,
            "total_segments": len(segments),
            "shard_index": SHARD_INDEX,
            "shard_count": SHARD_COUNT,
            "selected_segments": len(selected),
            "speed_factor_min": min(item["speed_factor"] for item in statistics),
            "speed_factor_max": max(item["speed_factor"] for item in statistics),
            "speed_factor_mean": sum(item["speed_factor"] for item in statistics) / len(statistics),
            "segments": statistics,
        }
        (Path("output") / f"{Path(OUTPUT_NAME).stem}.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps({key: value for key, value in manifest.items() if key != "segments"}, indent=2))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
