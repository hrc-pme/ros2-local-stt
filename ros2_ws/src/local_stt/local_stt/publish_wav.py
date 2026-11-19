#!/usr/bin/env python3
"""Publish a mono PCM WAV as real-time ROS AudioData chunks for testing."""

import argparse
import time
import wave

from audio_common_msgs.msg import AudioData
import rclpy
from rclpy.node import Node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_file")
    parser.add_argument("--topic", default="/audio")
    parser.add_argument("--chunk-ms", type=int, default=20)
    parser.add_argument("--trailing-silence", type=float, default=1.0)
    args = parser.parse_args()

    with wave.open(args.wav_file, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        if channels != 1 or sample_width != 2:
            raise ValueError("test WAV must be mono PCM16")
        chunk_frames = max(1, sample_rate * args.chunk_ms // 1000)
        chunks = []
        while True:
            data = wav_file.readframes(chunk_frames)
            if not data:
                break
            chunks.append(data)

    silence_chunks = max(1, int(args.trailing_silence * 1000 / args.chunk_ms))
    silence = bytes(chunk_frames * sample_width)

    rclpy.init()
    node = Node("wav_audio_publisher")
    publisher = node.create_publisher(AudioData, args.topic, 20)
    node.get_logger().info(
        "Publishing %s to %s (%d Hz mono PCM16)"
        % (args.wav_file, args.topic, sample_rate)
    )

    try:
        discovery_deadline = time.monotonic() + 3.0
        while publisher.get_subscription_count() == 0:
            if time.monotonic() >= discovery_deadline:
                node.get_logger().warning("No subscriber discovered; publishing anyway")
                break
            rclpy.spin_once(node, timeout_sec=0.1)

        period = args.chunk_ms / 1000.0
        for data in chunks:
            publisher.publish(AudioData(data=list(data)))
            rclpy.spin_once(node, timeout_sec=0.0)
            time.sleep(period)
        for _ in range(silence_chunks):
            publisher.publish(AudioData(data=list(silence)))
            rclpy.spin_once(node, timeout_sec=0.0)
            time.sleep(period)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
