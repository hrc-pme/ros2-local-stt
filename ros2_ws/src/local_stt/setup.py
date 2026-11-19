from glob import glob
import os

from setuptools import find_packages, setup


package_name = "local_stt"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="PME",
    maintainer_email="pme@example.com",
    description="Microphone-agnostic ROS 2 speech-to-text using faster-whisper",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "speech_to_text = local_stt.speech_to_text:main",
            "transcribe_file = local_stt.transcribe_file:main",
            "publish_wav = local_stt.publish_wav:main",
        ],
    },
)
