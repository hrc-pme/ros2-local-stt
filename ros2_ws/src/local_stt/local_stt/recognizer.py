"""Shared faster-whisper recognizer used by ROS and file entry points."""

import math

from faster_whisper import WhisperModel
from opencc import OpenCC


DEFAULT_HOTWORDS = ""


def normalize_language(language):
    value = str(language or "").strip().lower().replace("_", "-")
    if value in ("", "auto", "none"):
        return None
    if value.startswith("zh"):
        return "zh"
    if value.startswith("en"):
        return "en"
    return value.split("-", 1)[0]


class LocalWhisperRecognizer:
    def __init__(
        self,
        *,
        model_path="/models/faster-whisper",
        device="cpu",
        compute_type="int8",
        cpu_threads=8,
        traditional_chinese=True,
    ):
        self.model = WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            local_files_only=True,
        )
        self.opencc = OpenCC("s2twp") if traditional_chinese else None

    def transcribe(
        self,
        audio,
        *,
        language="auto",
        beam_size=5,
        vad_filter=True,
        hotwords=DEFAULT_HOTWORDS,
    ):
        generated, info = self.model.transcribe(
            audio,
            language=normalize_language(language),
            task="transcribe",
            beam_size=beam_size,
            vad_filter=vad_filter,
            multilingual=True,
            hotwords=hotwords or None,
            condition_on_previous_text=False,
        )
        segments = list(generated)
        text = "".join(segment.text for segment in segments).strip()
        if text and self.opencc is not None:
            text = self.opencc.convert(text)
        return text, self._confidence(segments), info.language

    @staticmethod
    def _confidence(segments):
        weighted_sum = 0.0
        total_duration = 0.0
        for segment in segments:
            duration = max(float(segment.end - segment.start), 0.01)
            probability = math.exp(min(float(segment.avg_logprob), 0.0))
            weighted_sum += probability * duration
            total_duration += duration
        if total_duration == 0.0:
            return 0.0
        return max(0.0, min(1.0, weighted_sum / total_duration))
