# Generic ROS 2 Local STT

這是一個與麥克風硬體無關的 ROS 2 Humble 語音轉文字容器。

容器只負責：

```text
任意 ROS 2 麥克風節點
        |
        | /audio (audio_common_msgs/msg/AudioData)
        | mono signed PCM16 stream
        v
WebRTC VAD 自動分句 -> faster-whisper -> /speech_text (std_msgs/msg/String)
```

麥克風、音效卡、ALSA、PyAudio 與廠牌驅動都不包含在本專案內。使用者可自行選擇麥克風節點，只要它能發布相同的 ROS 2 音訊格式即可。

預設使用 CPU INT8 的 multilingual `small` 模型，支援中文、英文及中英混合；中文結果會轉成臺灣繁體。

## 快速開始

```bash
cp .env.example .env
docker compose build
bash scripts/download_model.sh
docker compose up -d
docker compose logs -f stt
```

模型會在執行下載腳本時存到主機的 `models/`，不會提交到 Git，也不會包進 Docker image。Docker image 重建後仍能繼續使用同一份模型。

看到以下訊息代表服務已準備完成：

```text
Ready: /audio (stream, 16000 Hz mono PCM16) -> /speech_text
```

辨識結果使用標準 ROS 訊息：

```bash
ros2 topic echo /speech_text
```

## 麥克風節點的資料介面

預設輸入 topic：

```text
topic: /audio
type:  audio_common_msgs/msg/AudioData
data:  單聲道、signed little-endian PCM16 byte stream
rate:  16000 Hz
```

麥克風節點可以持續發布任意大小的音訊 chunk。容器會重新切成 VAD frame，偵測有人說話與句尾靜音，再把完整句子交給 Whisper。

若麥克風使用其他 topic 或取樣率，修改 `.env`：

```dotenv
STT_INPUT_TOPIC=/my_microphone/audio
STT_SAMPLE_RATE=48000
```

stream 模式支援 8000、16000、32000、48000 Hz PCM16。Whisper 前處理會自動轉成模型所需的取樣率。

如果上游節點已經完成分句，每一則 `AudioData` 都是一整句，改用：

```dotenv
STT_INPUT_MODE=utterance
```

## 設定

`.env.example` 提供以下設定：

```dotenv
ROS_DOMAIN_ID=0
STT_MODEL_SIZE=small
STT_MODEL_DIR=./models
STT_LANGUAGE=auto
STT_CPU_THREADS=8
STT_INPUT_TOPIC=/audio
STT_OUTPUT_TOPIC=/speech_text
STT_SAMPLE_RATE=16000
STT_INPUT_MODE=stream
STT_VAD_AGGRESSIVENESS=2
STT_SILENCE_MS=700
```

- `STT_LANGUAGE=auto`：自動辨識中文、英文或混合語音。
- `STT_LANGUAGE=en` 或 `zh`：強制指定語言。
- `STT_VAD_AGGRESSIVENESS`：0 到 3，越高越積極排除非語音。
- `STT_SILENCE_MS`：句尾持續多少毫秒的靜音才送出辨識。
- `STT_MODEL_SIZE`：下載模型時使用；修改後需要重新執行下載腳本。

所有 ROS 2 節點必須使用相同的 `ROS_DOMAIN_ID`。

容器將 Fast DDS transport 設為 UDPv4，讓 ROS topic 能跨容器傳輸，而不必把容器加入主機 IPC namespace。

## 不接麥克風測試模型

可直接掛入 WAV、MP3、M4A 等 PyAV 支援的檔案：

```bash
docker compose run --rm --no-deps \
  -v "$(pwd)/sample.wav:/data/sample.wav:ro" \
  stt ros2 run local_stt transcribe_file /data/sample.wav --language auto
```

要測試完整的 ROS stream 與 VAD，可先把音檔轉成 16 kHz mono PCM16 WAV，啟動 STT 後再發布：

```bash
ffmpeg -i sample.wav -ar 16000 -ac 1 -c:a pcm_s16le sample-16k.wav

docker compose up -d
docker compose run --rm --no-deps \
  -v "$(pwd)/sample-16k.wav:/data/sample.wav:ro" \
  stt ros2 run local_stt publish_wav /data/sample.wav --topic /audio

ros2 topic echo /speech_text
```

`publish_wav` 只是測試工具，不會存取麥克風或音效卡。

## 更換模型

例如改用 `medium`：

```bash
STT_MODEL_SIZE=medium bash scripts/download_model.sh
```

下載會更新 `models/faster-whisper/`。模型較大時會需要更多磁碟、記憶體與 CPU 時間。

## 獨立成新的 Git repository

這個目錄本身已經是完整且自包含的專案，可複製出去後初始化 Git：

```bash
mkdir -p ~/local-ros2-stt
rsync -a --exclude models/ --exclude .env standalone_stt/ ~/local-ros2-stt/
cd ~/local-ros2-stt
git init
git add .
git commit -m "Initial generic ROS 2 speech-to-text service"
```

`models/`、`.env` 和 colcon build 產物都已列入 `.gitignore`。
