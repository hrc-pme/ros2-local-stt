from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    arguments = [
        DeclareLaunchArgument("model_path", default_value="/models/faster-whisper"),
        DeclareLaunchArgument("language", default_value="auto"),
        DeclareLaunchArgument("cpu_threads", default_value="8"),
        DeclareLaunchArgument("input_topic", default_value="/audio"),
        DeclareLaunchArgument("output_topic", default_value="/speech_text"),
        DeclareLaunchArgument("sample_rate", default_value="16000"),
        DeclareLaunchArgument("input_mode", default_value="stream"),
        DeclareLaunchArgument("vad_aggressiveness", default_value="2"),
        DeclareLaunchArgument("silence_ms", default_value="700"),
    ]

    node = Node(
        package="local_stt",
        executable="speech_to_text",
        name="speech_to_text",
        output="screen",
        parameters=[{
            "model_path": LaunchConfiguration("model_path"),
            "language": LaunchConfiguration("language"),
            "cpu_threads": ParameterValue(
                LaunchConfiguration("cpu_threads"), value_type=int),
            "input_topic": LaunchConfiguration("input_topic"),
            "output_topic": LaunchConfiguration("output_topic"),
            "sample_rate": ParameterValue(
                LaunchConfiguration("sample_rate"), value_type=int),
            "input_mode": LaunchConfiguration("input_mode"),
            "vad_aggressiveness": ParameterValue(
                LaunchConfiguration("vad_aggressiveness"), value_type=int),
            "silence_ms": ParameterValue(
                LaunchConfiguration("silence_ms"), value_type=int),
        }],
    )

    return LaunchDescription(arguments + [node])
