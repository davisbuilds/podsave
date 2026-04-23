from __future__ import annotations

import json
from pathlib import Path

from src.errors import TranscriptNotFoundError
from src.models import VideoMeta
from src.storage import paths


def _transcript_path(video_id: str) -> Path:
    return paths.transcripts_dir() / f"{video_id}.json"


def _meta_path(video_id: str) -> Path:
    return paths.transcripts_dir() / f"{video_id}.meta.json"


def has(video_id: str) -> bool:
    """True iff both the transcript JSON and metadata sidecar exist."""
    return _transcript_path(video_id).exists() and _meta_path(video_id).exists()


def save(video_id: str, raw_transcript: dict, meta: VideoMeta) -> tuple[Path, Path]:
    """Persist the AssemblyAI raw response + a VideoMeta sidecar. Returns (transcript, meta)."""
    paths.transcripts_dir().mkdir(parents=True, exist_ok=True)
    tp = _transcript_path(video_id)
    mp = _meta_path(video_id)
    tp.write_text(json.dumps(raw_transcript, indent=2))
    mp.write_text(meta.model_dump_json(indent=2))
    return tp, mp


def load(video_id: str) -> tuple[dict, VideoMeta]:
    """Return (raw_transcript_dict, VideoMeta). Raises if missing."""
    if not has(video_id):
        raise TranscriptNotFoundError(
            f"no cached transcript for video_id={video_id} in {paths.transcripts_dir()}"
        )
    raw = json.loads(_transcript_path(video_id).read_text())
    meta = VideoMeta.model_validate_json(_meta_path(video_id).read_text())
    return raw, meta
