#!/usr/bin/env python3
"""Microphone-agnostic ROS 2 PCM stream to text adapter."""

from collections import deque
import io
import math
import queue
import threading
import wave

from audio_common_msgs.msg import AudioData
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import webrtcvad

from local_stt.recognizer import DEFAULT_HOTWORDS, LocalWhisperRecognizer


class SpeechToText(Node):
    """Receive generic mono PCM audio and publish recognized text."""

    def __init__(self):
        super().__init__("speech_to_text")

        self.sample_rate = int(self.declare_parameter("sample_rate", 16000).value)
        self.sample_width = int(self.declare_parameter("sample_width", 2).value)
        self.input_mode = str(
            self.declare_parameter("input_mode", "stream").value
        ).strip().lower()
        self.language = str(self.declare_parameter("language", "auto").value)
        self.beam_size = int(self.declare_parameter("beam_size", 5).value)
        self.hotwords = str(
            self.declare_parameter("hotwords", DEFAULT_HOTWORDS).value
        )

        model_path = str(
            self.declare_parameter("model_path", "/models/faster-whisper").value
        )
        cpu_threads = int(self.declare_parameter("cpu_threads", 8).value)
        input_topic = str(self.declare_parameter("input_topic", "/audio").value)
        output_topic = str(
            self.declare_parameter("output_topic", "/speech_text").value
        )

        self.frame_ms = int(self.declare_parameter("frame_ms", 30).value)
        speech_start_ms = int(
            self.declare_parameter("speech_start_ms", 150).value
        )
        silence_ms = int(self.declare_parameter("silence_ms", 700).value)
        pre_roll_ms = int(self.declare_parameter("pre_roll_ms", 300).value)
        max_utterance_sec = float(
            self.declare_parameter("max_utterance_sec", 20.0).value
        )
        vad_aggressiveness = int(
            self.declare_parameter("vad_aggressiveness", 2).value
        )

        if self.input_mode not in ("stream", "utterance"):
            raise ValueError("input_mode must be 'stream' or 'utterance'")
        if self.sample_width not in (1, 2, 4):
            raise ValueError("sample_width must be 1, 2, or 4 bytes")
        if self.input_mode == "stream":
            if self.sample_width != 2:
                raise ValueError("stream mode VAD requires signed PCM16 (sample_width=2)")
            if self.sample_rate not in (8000, 16000, 32000, 48000):
                raise ValueError(
                    "stream mode sample_rate must be 8000, 16000, 32000, or 48000"
                )
            if self.frame_ms not in (10, 20, 30):
                raise ValueError("frame_ms must be 10, 20, or 30")

        self.get_logger().info(
            "Loading faster-whisper model from %s (CPU INT8, threads=%d)"
            % (model_path, cpu_threads)
        )
        self.recognizer = LocalWhisperRecognizer(
            model_path=model_path,
            cpu_threads=cpu_threads,
        )

        self.text_pub = self.create_publisher(String, output_topic, 10)
        self.audio_sub = self.create_subscription(
            AudioData, input_topic, self.audio_callback, 20
        )

        self._jobs = queue.Queue(maxsize=2)
        self._stopping = threading.Event()
        self._worker = threading.Thread(
            target=self._recognition_worker,
            name="whisper-worker",
            daemon=True,
        )
        self._worker.start()

        self._pending = bytearray()
        self._active = False
        self._utterance_frames = []
        self._voiced_run = 0
        self._silent_run = 0

        if self.input_mode == "stream":
            self._vad = webrtcvad.Vad(vad_aggressiveness)
            samples_per_frame = self.sample_rate * self.frame_ms // 1000
            self._frame_bytes = samples_per_frame * self.sample_width
            self._start_frames = max(1, math.ceil(speech_start_ms / self.frame_ms))
            self._end_frames = max(1, math.ceil(silence_ms / self.frame_ms))
            self._max_frames = max(
                1, math.ceil(max_utterance_sec * 1000 / self.frame_ms)
            )
            self._pre_roll = deque(
                maxlen=max(1, math.ceil(pre_roll_ms / self.frame_ms))
            )

        self.get_logger().info(
            "Ready: %s (%s, %d Hz mono PCM%d) -> %s"
            % (
                input_topic,
                self.input_mode,
                self.sample_rate,
                self.sample_width * 8,
                output_topic,
            )
        )

    def audio_callback(self, msg):
        raw_audio = bytes(msg.data)
        if not raw_audio:
            return

        if self.input_mode == "utterance":
            self._enqueue(raw_audio)
            return

        self._pending.extend(raw_audio)
        while len(self._pending) >= self._frame_bytes:
            frame = bytes(self._pending[: self._frame_bytes])
            del self._pending[: self._frame_bytes]
            self._handle_stream_frame(frame)

    def _handle_stream_frame(self, frame):
        voiced = self._vad.is_speech(frame, self.sample_rate)

        if not self._active:
            self._pre_roll.append(frame)
            self._voiced_run = self._voiced_run + 1 if voiced else 0
            if self._voiced_run >= self._start_frames:
                self._active = True
                self._utterance_frames = list(self._pre_roll)
                self._pre_roll.clear()
                self._silent_run = 0
                self.get_logger().debug("Speech started")
            return

        self._utterance_frames.append(frame)
        self._silent_run = 0 if voiced else self._silent_run + 1

        reached_silence = self._silent_run >= self._end_frames
        reached_limit = len(self._utterance_frames) >= self._max_frames
        if reached_silence or reached_limit:
            self._finish_utterance()

    def _finish_utterance(self):
        audio = b"".join(self._utterance_frames)
        self._active = False
        self._utterance_frames = []
        self._voiced_run = 0
        self._silent_run = 0
        self._enqueue(audio)

    def _enqueue(self, raw_audio):
        duration = len(raw_audio) / (self.sample_rate * self.sample_width)
        if duration < 0.15:
            return
        try:
            self._jobs.put_nowait(raw_audio)
            self.get_logger().info(
                "Queued %.2f seconds of audio for recognition" % duration
            )
        except queue.Full:
            self.get_logger().warning(
                "Recognition queue is full; dropping one utterance"
            )

    def _as_wav(self, raw_audio):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(raw_audio)
        output.seek(0)
        return output

    def _recognition_worker(self):
        while not self._stopping.is_set():
            try:
                raw_audio = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                text, confidence, detected_language = self.recognizer.transcribe(
                    self._as_wav(raw_audio),
                    language=self.language,
                    beam_size=self.beam_size,
                    vad_filter=False,
                    hotwords=self.hotwords,
                )
                if text:
                    self.text_pub.publish(String(data=text))
                    self.get_logger().info(
                        "Recognized [%s %.2f]: %s"
                        % (detected_language, confidence, text)
                    )
                else:
                    self.get_logger().info("No speech recognized")
            except Exception as exc:
                self.get_logger().error("Speech recognition failed: %s" % exc)
            finally:
                self._jobs.task_done()

    def close(self):
        self._stopping.set()
        try:
            self._worker.join(timeout=2.0)
        except KeyboardInterrupt:
            pass


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SpeechToText()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
            try:
                node.destroy_node()
            except KeyboardInterrupt:
                pass
        if rclpy.ok():
            try:
                rclpy.shutdown()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
