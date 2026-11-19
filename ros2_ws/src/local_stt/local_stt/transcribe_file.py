#!/usr/bin/env python3
"""Command-line transcription for an audio file mounted into the container."""

import argparse

from local_stt.recognizer import LocalWhisperRecognizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file")
    parser.add_argument("--model-path", default="/models/faster-whisper")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--cpu-threads", type=int, default=8)
    args = parser.parse_args()

    recognizer = LocalWhisperRecognizer(
        model_path=args.model_path,
        cpu_threads=args.cpu_threads,
    )
    text, confidence, language = recognizer.transcribe(
        args.audio_file,
        language=args.language,
    )
    print("language=%s confidence=%.3f" % (language, confidence))
    print(text)


if __name__ == "__main__":
    main()
