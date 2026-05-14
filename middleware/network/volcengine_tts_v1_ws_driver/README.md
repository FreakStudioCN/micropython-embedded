# 火山引擎 TTS V1 WebSocket 客户端驱动 - MicroPython版本

## 目录

- [简介](#简介)
- [主要功能](#主要功能)
- [运行环境](#运行环境)
- [软件环境](#软件环境)
- [文件结构](#文件结构)
- [文件说明](#文件说明)
- [快速开始](#快速开始)
- [注意事项](#注意事项)
- [版本记录](#版本记录)
- [联系方式](#联系方式)
- [许可协议](#许可协议)

---

## 简介

`volcengine_tts_v1_ws` 是火山引擎语音合成（TTS）V1 WebSocket 协议的 MicroPython 客户端驱动。它通过 WebSocket 长连接与火山引擎 TTS 服务通信，支持流式边合成边播放（低延迟）和非流式合成保存到文件两种模式。适用于需要在 ESP32 等 MicroPython 设备上实现语音播报、智能对话、角色扮演等场景。

---

## 主要功能

- **流式播放**：边接收音频帧边写入 I2S，首字节延迟低
- **非流式合成**：将完整音频保存为 PCM/WAV/MP3/OGG_OPUS 文件
- **70+ 内置音色**：覆盖中文角色扮演、通用、多情感、英语（美式/英式）、日语、西班牙语
- **多情感支持**：通过 `style` 参数指定情感（开心、愤怒、撒娇等）
- **参数临时覆盖**：每次调用可临时指定音色、语速、音调、音量，不影响默认配置
- **asyncio 异步架构**：全异步设计，与 MicroPython asyncio 生态无缝集成
- **凭证参数校验**：`__init__` 对 `app_id`/`access_token` 做 None + 类型双重校验

---

## 运行环境

### 网络要求

| 项目 | 要求 |
|------|------|
| WiFi 频段 | 2.4GHz |
| 目标服务器 | `openspeech.bytedance.com`（需能正常访问） |
| 协议 | WSS（WebSocket over TLS） |

### API 凭证要求

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `app_id` | str | 火山引擎控制台 → 语音技术 → 应用管理 → App ID |
| `access_token` | str | 火山引擎控制台 → 语音技术 → 应用管理 → Access Token |

> 凭证申请地址：[火山引擎语音技术控制台](https://console.volcengine.com/speech)

### 可选外设（流式播放）

| 外设 | 说明 |
|------|------|
| I2S 音频模块 | 用于流式播放，如 MAX98357A；非必须，非流式模式无需此模块 |
| 功放 SD 引脚 | 控制功放静音，播放前置高，播完后置低 |

**测试硬件引脚（ESP32，参考 main.py）：**

| 引脚 | 功能 |
|------|------|
| GPIO14 | I2S SCK（位时钟） |
| GPIO15 | I2S WS（字选择） |
| GPIO16 | I2S SD（数据输出） |
| GPIO17 | 功放 SD（静音控制） |

---

## 软件环境

| 项目 | 版本 |
|------|------|
| MicroPython 固件 | v1.23.0 |
| 驱动版本 | v1.0.0 |
| 依赖库 | `async_websocketclient`（需提前上传至设备） |
| 目标平台 | ESP32（已验证） |

---

## 文件结构

```
volcengine_tts_v1_ws/
├── volcengine_tts_v1_ws.py   # 核心驱动
├── main.py                   # 测试示例（多音色/多语种/流式&非流式）
└── README.md                 # 说明文档
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `volcengine_tts_v1_ws.py` | 核心驱动，包含 `VolcengineTTSV1WS` 类，实现 V1 WebSocket 协议帧构造、响应解析、流式/非流式合成 |
| `main.py` | 测试示例，覆盖 30+ 音色场景，包含中文角色扮演、多情感、英语、日语、语速/语调边界测试 |
| `README.md` | 本说明文档 |

---

## 快速开始

### 步骤一：上传文件

将以下文件上传至 MicroPython 设备根目录：

```
volcengine_tts_v1_ws.py
async_websocketclient.py   （依赖库）
```

### 步骤二：获取 API 凭证

登录 [火山引擎控制台](https://console.volcengine.com/speech)，创建应用，获取 `App ID` 和 `Access Token`。

### 步骤三：最小可运行示例

```python
import asyncio
import network
import time
from machine import I2S, Pin
from volcengine_tts_v1_ws import VolcengineTTSV1WS

# 连接 WiFi
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect("your_ssid", "your_password")
while not sta.isconnected():
    time.sleep(0.5)

# 初始化 I2S
amp_sd    = Pin(17, Pin.OUT, value=0)
audio_out = I2S(1, sck=Pin(14), ws=Pin(15), sd=Pin(16),
                mode=I2S.TX, bits=16, format=I2S.MONO,
                rate=16000, ibuf=40000)

# 初始化 TTS 客户端
tts = VolcengineTTSV1WS(
    app_id="your_app_id",
    access_token="your_access_token",
)

async def main():
    # 流式播放
    await tts.synthesize_and_play("你好，世界！", audio_out, amp_sd)
    # 或保存到文件
    await tts.synthesize("你好，世界！", output_path="out.pcm")
    audio_out.deinit()

asyncio.run(main())
```

### 步骤四：运行完整测试

修改 `main.py` 中的 `WIFI_SSID`、`WIFI_PASS`、`APP_ID`、`ACCESS_TOKEN`，然后运行：

```python
import main
```

### API 参考

#### `VolcengineTTSV1WS.__init__`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `app_id` | str | 必填 | 火山引擎 App ID |
| `access_token` | str | 必填 | 火山引擎 Access Token |
| `voice_type` | str | `VOICE_BV701_STREAMING` | 默认音色 |
| `format` | str | `"pcm"` | 默认音频格式（pcm/wav/mp3/ogg_opus） |
| `sample_rate` | int | `16000` | 默认采样率（Hz） |
| `volume` | float | `1.0` | 默认音量（0.1~3.0） |
| `speed` | float | `1.0` | 默认语速（0.2~3.0） |
| `pitch` | float | `1.0` | 默认音调（0.1~3.0） |
| `language` | str | `"zh"` | 默认语言（zh/en/ja） |
| `style` | str | `None` | 默认情感（如 happy/sad/angry） |
| `enable_subtitle` | int | `0` | 字幕级别（0/1/2/3） |
| `debug` | bool | `False` | 调试日志开关 |

#### `synthesize(text, output_path=None, **kwargs)`

合成语音到文件或内存。

- `output_path` 不为 None 时，写入文件并返回字节数（`int`）
- `output_path` 为 None 时，返回完整音频数据（`bytes`）
- `**kwargs` 可临时覆盖 `voice_type`/`volume`/`speed`/`pitch`/`style`/`format`/`sample_rate`/`language`/`enable_subtitle`

#### `synthesize_and_play(text, audio_out, amp_sd, rate=16000, **kwargs)`

流式合成并写入 I2S，返回总字节数（`int`）；失败返回 `0`。

- `audio_out`：已初始化的 I2S TX 实例
- `amp_sd`：功放 SD 引脚（`Pin` 实例），播放前置高，播完后置低
- `rate`：采样率，用于计算尾部等待时长

---

## 注意事项

| 类别 | 说明 |
|------|------|
| 网络 | 设备必须能访问 `openspeech.bytedance.com:443`，部分网络环境需配置代理 |
| 凭证安全 | `APP_ID`/`ACCESS_TOKEN` 不要提交到公开代码仓库 |
| 音频格式 | `synthesize_and_play` 固定使用 PCM 格式；`synthesize` 支持 pcm/wav/mp3/ogg_opus |
| 采样率 | I2S 初始化的 `rate` 参数须与 TTS 请求的 `sample_rate` 一致，否则播放速度异常 |
| I2S 缓冲区 | `ibuf` 建议设置 ≥ 20000 字节，过小会导致播放卡顿 |
| 依赖库 | `async_websocketclient` 须提前上传至设备，否则导入失败 |
| MicroPython 版本 | 已在 v1.23.0 验证；低于 v1.20 的固件可能不支持 `asyncio.StreamWriter` |

---

## 版本记录

| 版本号 | 日期 | 作者 | 修改说明 |
|--------|------|------|----------|
| v1.0.0 | 2026-05-14 | AI Assistant | 初始版本，支持流式/非流式合成，70+ 内置音色 |

---

## 联系方式

- 邮箱：your_email@example.com
- GitHub：https://github.com/your_username

---

## 许可协议

MIT License

Copyright (c) 2026 AI Assistant

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
