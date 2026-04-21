# AsyncMicRecorder

适用于 MicroPython 的异步 VAD 麦克风录音驱动，基于 `asyncio.StreamReader` + I2S，通过 RMS 能量阈值检测语音起止，将完整一句话写入 PCM 文件，已在树莓派 Pico 2W 上通过验证。

---

## 目录

- [简介](#简介)
- [主要功能](#主要功能)
- [硬件要求](#硬件要求)
- [文件说明](#文件说明)
- [软件设计核心思想](#软件设计核心思想)
- [使用说明](#使用说明)
- [示例程序](#示例程序)
- [注意事项](#注意事项)
- [联系方式](#联系方式)
- [许可协议](#许可协议)

---

## 简介

`AsyncMicRecorder` 是一个专为 MicroPython 设计的轻量级异步 VAD 录音驱动。它使用 `asyncio.StreamReader` 包装 I2S 外设，实现非阻塞帧读取，通过 RMS 能量阈值检测语音起止，将完整一句话零拷贝写入 PCM 文件。

- **无外部依赖**，仅使用 MicroPython 内置模块
- 使用 **PSRAM 预分配 + memoryview** 实现零拷贝写入，彻底消除录音过程中的 GC 停顿
- 支持**能量回调**和**事件回调**，与上层业务完全解耦

---

## 主要功能

- **异步非阻塞**：基于 `asyncio.StreamReader`，不阻塞事件循环
- **VAD 检测**：RMS 能量阈值，可调灵敏度
- **零拷贝写入**：PSRAM 预分配缓冲区 + memoryview，无 GC 停顿
- **预热丢帧**：可配置预热帧数，消除 I2S 启动噪声
- **回调解耦**：`on_energy(e)` 实时能量，`on_event(msg)` 状态事件
- **完整参数校验**：`__init__` 和 `listen()` 均对入参做 None / 类型 / 值范围三级校验

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 I2S 的 MicroPython 设备） |
| 麦克风 | INMP441 或其他 I2S 麦克风（16-bit，单声道） |
| 固件 | MicroPython v1.23.0 及以上 |
| 额外硬件 | 无网络要求（纯本地录音） |

**I2S 接线（Pico 2W 默认引脚）：**

| 麦克风引脚 | Pico 2W 引脚 | 说明 |
|-----------|-------------|------|
| SCK | GP5 | 位时钟 |
| WS | GP4 | 声道选择 |
| SD | GP6 | 数据输出 |
| L/R | GND | 选择左声道 |

---

## 文件说明

```
async_mic_recorder/
├── code/
│   ├── async_mic_recorder.py   # 驱动核心实现
│   └── main.py                 # 使用示例 / 测试代码
├── package.json                # mip 包配置
├── README.md                   # 使用文档
└── LICENSE                     # MIT 开源协议
```

| 文件 | 说明 |
|------|------|
| `code/async_mic_recorder.py` | 驱动核心类 `AsyncMicRecorder`，包含 VAD、零拷贝缓冲、回调全部逻辑 |
| `code/main.py` | 完整使用示例，演示 I2S 初始化、录音、保存 PCM 文件的完整流程 |
| `package.json` | mip 包描述文件 |
| `LICENSE` | MIT 开源协议文本 |

---

## 软件设计核心思想

### 1. VAD 状态机

```
[监听中] → energy > threshold → [录音中] → silence_cnt >= silence_frames
                                              ↓
                              voice_cnt >= min_voice_frames ?
                                  是 → 写文件 → 返回路径
                                  否 → emit "too_short" → [监听中]
```

### 2. 零拷贝写入

录音开始前一次性预分配 PSRAM 缓冲区（`rate × 2 × max_seconds` 字节），使用 `memoryview` 切片直接写入，避免 `pcm_buf += frame` 的动态分配导致 GC 停顿：

```python
pcm_buf = bytearray(rate * 2 * max_seconds)   # 一次性分配
mv      = memoryview(pcm_buf)
# 录音中：
mv[write_pos:write_pos + frame_bytes] = read_buf  # 零拷贝
```

### 3. 事件字符串协议

| 事件字符串 | 触发时机 |
|-----------|---------|
| `"ready"` | `start()` 预热完成 |
| `"voice_start"` | 检测到语音，开始录音 |
| `"too_short"` | 语音过短（< min_voice_frames），重置监听 |
| `"saved:path:size"` | 录音写入完成，`path` 为文件路径，`size` 为字节数 |

---

## 使用说明

### 第一步：部署驱动文件

```bash
mpremote connect COM55 cp code/async_mic_recorder.py :async_mic_recorder.py
```

### 第二步：初始化 I2S 并创建录音器

```python
from machine import I2S, Pin
from async_mic_recorder import AsyncMicRecorder

audio_in = I2S(
    0,
    sck=Pin(5), ws=Pin(4), sd=Pin(6),
    mode=I2S.RX, bits=16, format=I2S.MONO,
    rate=16000, ibuf=40000,
)

recorder = AsyncMicRecorder(
    audio_in,
    rate=16000,
    threshold=600,       # VAD 能量阈值，越大越不灵敏
    silence_frames=40,   # 连续静音帧数触发停止（40×64ms≈2.6s）
    min_voice_frames=5,  # 最短有效语音帧
    max_seconds=30,      # 最大录音时长
    warmup_frames=15,    # 预热帧数
)
```

### 第三步：预热并录音

```python
import asyncio

async def main():
    await recorder.start()              # 预热，消除启动噪声
    path = await recorder.listen("mic.pcm")  # 阻塞直到录到一句话
    print("Saved:", path)
    recorder.stop()

asyncio.run(main())
```

### API 速查

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `await start()` | `None` | 预热麦克风，必须在 `listen()` 前调用一次 |
| `await listen(output_file)` | `str` 文件路径 | 阻塞直到录到完整一句话 |
| `stop()` | `None` | 释放 I2S 资源 |

### 初始化参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `i2s` | I2S | — | machine.I2S 实例（mode=RX，bits=16，format=MONO） |
| `rate` | int | `16000` | 采样率，Hz |
| `threshold` | int | `600` | VAD 能量阈值，越大越不灵敏 |
| `silence_frames` | int | `40` | 连续静音帧数触发停止 |
| `min_voice_frames` | int | `5` | 最短有效语音帧数 |
| `frame_bytes` | int | `2048` | 每帧字节数（影响延迟） |
| `max_seconds` | int | `30` | 最大录音时长（秒），决定 PSRAM 预分配大小 |
| `warmup_frames` | int | `15` | 预热丢弃帧数 |
| `on_energy` | callable | `None` | 每帧能量回调 `fn(energy: int)` |
| `on_event` | callable | `None` | 状态事件回调 `fn(msg: str)` |

---

## 示例程序

完整代码见 `code/main.py`：

```python
from machine import I2S, Pin
import asyncio
import time
from async_mic_recorder import AsyncMicRecorder

def on_energy(e):
    print("energy:", e, end="\r")

def on_event(msg):
    if msg == "ready":
        print("AsyncMicRecorder ready")
    elif msg == "voice_start":
        print("\nVoice detected, recording...")
    elif msg == "too_short":
        print("\nVoice too short, listening...")
    elif msg.startswith("saved:"):
        _, path, size = msg.split(":")
        print("Saved -> {} ({} bytes)".format(path, size))

async def main():
    recorder = AsyncMicRecorder(
        audio_in, rate=16000, threshold=600,
        on_energy=on_energy, on_event=on_event,
    )
    await recorder.start()
    path = await recorder.listen("mic.pcm")
    print("Recording saved:", path)
    recorder.stop()

time.sleep(3)
print("FreakStudio: test AsyncMicRecorder now")

audio_in = I2S(
    0, sck=Pin(5), ws=Pin(4), sd=Pin(6),
    mode=I2S.RX, bits=16, format=I2S.MONO,
    rate=16000, ibuf=40000,
)

asyncio.run(main())
```

**预期输出：**

```
FreakStudio: test AsyncMicRecorder now
AsyncMicRecorder ready
energy: 312
energy: 287
...
Voice detected, recording...
Saved -> mic.pcm (92160 bytes)
Recording saved: mic.pcm
```

---

## 注意事项

1. **PSRAM 要求**：`max_seconds=30` 时预分配约 960KB（16000×2×30），需确保设备有足够 PSRAM（ESP32-S3 8MB PSRAM 可满足）。

2. **ibuf 大小**：I2S `ibuf=40000` 用于覆盖文件写入延迟，过小会导致 I2S 溢出和录音断续。

3. **threshold 调参**：安静环境建议 400~600，嘈杂环境建议 800~1200。可通过 `on_energy` 回调观察实际能量值后调整。

4. **与 ASR 衔接**：`listen()` 返回的 PCM 文件可直接传入 `XfyunASR.recognize(filepath)`，采样率需保持一致（均为 16000 Hz）。

5. **L/R 引脚**：INMP441 的 L/R 引脚接 GND 选择左声道，I2S `format=I2S.MONO` 自动取左声道数据。

---

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

---

## 许可协议

本项目基于 [MIT License](LICENSE) 开源协议发布。
