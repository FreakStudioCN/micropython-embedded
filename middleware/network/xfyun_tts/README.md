# XfyunTTS

适用于 MicroPython 的讯飞在线语音合成（TTS）驱动，通过 WebSocket 连接讯飞开放平台，将文字实时合成为 PCM 或 WAV 音频文件，已在树莓派 Pico 2W 上通过验证。

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

`XfyunTTS` 是一个专为 MicroPython 设计的轻量级讯飞在线 TTS 驱动。它依赖 [`async_websocket_client`](https://upypi.net/pkgs/async_websocket_client) 库建立 WSS 连接，在设备端实现 HMAC-SHA256 签名鉴权、JSON 请求构造与流式音频接收，并将音频直接写入 Flash 文件系统，规避了嵌入式设备有限 RAM 的限制。

支持两种输出格式：

- **RAW PCM**（`.pcm`）：裸 16-bit 有符号 PCM，可直接送入 I2S 接口播放
- **WAV**（`.wav`）：带标准 44 字节文件头的 PCM 容器，可在 PC 上用任意播放器直接打开

---

## 主要功能

- **HMAC-SHA256 签名鉴权**：纯 MicroPython 实现，不依赖标准 `hmac` 模块
- **RFC1123 时间格式**：手写实现，不依赖 `wsgiref`
- **URL 百分号编码**：手写实现，不依赖 `urllib.parse`
- **流式写入文件**：每收到一帧音频（约 1~4 KB）立即写入 Flash，内存峰值与音频总时长无关
- **WAV 文件自动生成**：先写占位头，接收完毕后 `seek(0)` 回填真实 data size
- **PCM / WAV 双格式**：根据 `filepath` 后缀（`.wav` / 其他）自动选择输出格式
- **正则递归绕过**：通过子类覆盖 `urlparse()`，规避 MicroPython `ure` 引擎对长 URL 的递归溢出
- **边收边播（synthesize_and_play）**：收到每帧音频立即写入 I2S，通过 asyncio StreamWriter 异步写入，减少播放卡顿
- **socket 资源保护**：每次新建连接前先关闭旧连接，避免 ESP32 TLS socket 资源耗尽
- **超时保护**：`handshake()` 和 `recv()` 均有 10 秒超时，网络异常时自动返回而非永久阻塞

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 WiFi 的 MicroPython 设备） |
| 固件 | MicroPython v1.23.0 及以上 |
| 网络 | 2.4GHz WiFi，需能访问 `tts-api.xfyun.cn`（讯飞 TTS 服务） |
| 额外硬件 | 无（纯软件库，不依赖任何外设） |

---

## 文件说明

```
xfyun_tts/
├── code/
│   ├── xfyun_tts.py    # 驱动核心实现
│   └── main.py         # 使用示例 / 测试代码
├── package.json        # mip 包配置（含依赖声明）
├── README.md           # 使用文档
└── LICENSE             # MIT 开源协议
```

| 文件 | 说明 |
|------|------|
| `code/xfyun_tts.py` | 驱动核心类 `XfyunTTS`，包含鉴权、请求构造、流式收音全部逻辑 |
| `code/main.py` | 完整使用示例，演示 WiFi 连接、NTP 同步、PCM 输出、WAV 输出的完整流程 |
| `package.json` | mip 包描述文件，声明包名、版本、作者及对 `async_websocket_client` 的依赖 |
| `LICENSE` | MIT 开源协议文本 |

---

## 软件设计核心思想

### 1. HMAC-SHA256 鉴权流程

讯飞 TTS API 采用基于时间戳的签名鉴权，每次请求的 WSS URL 均需携带实时计算的签名：

```
获取当前 UTC 时间（RFC1123 格式，依赖 NTP 同步）
    ↓
构造签名原文：
    "host: tts-api.xfyun.cn\n
     date: {RFC1123 时间}\n
     GET /v2/tts HTTP/1.1"
    ↓
HMAC-SHA256(API Secret 的 UTF-8 字节, 签名原文) → 32 字节摘要
    ↓
Base64 编码 → signature 字符串
    ↓
构造 authorization 原文 → Base64 编码 → URL 百分号编码
    ↓
拼入 WSS 查询字符串：?authorization=...&date=...&host=...
```

> **关键**：API Secret 直接以 UTF-8 字节作为 HMAC 密钥，**不得**对其 Base64 解码，否则签名错误将导致 HTTP 401。

### 2. 流式写入 + WAV 回填

MicroPython 可用堆内存有限（Pico 2W 约 100~150 KB），几十 KB 的音频若在内存中一次性拼接会触发 OOM 崩溃。本驱动采用边接收边写盘的流式方案：

```
打开文件（"wb"）
    ↓
若后缀为 .wav：写入 44 字节占位头（data_size = 0）
    ↓
循环接收音频帧（每帧约 1~4 KB）→ 立即 f.write(chunk)
    ↓
接收完毕（服务端 status == 2）
    ↓
若 .wav：f.seek(0) 回填真实 data_size → 标准 WAV 文件完成
    ↓
关闭文件
```

内存中同时仅存在单帧数据，峰值约 4 KB，与音频总时长完全无关。

### 3. 规避 MicroPython 正则递归限制

`async_websocketclient` 使用 `re.compile` 解析 WebSocket URL。MicroPython 的 `ure` 正则引擎采用递归 NFA 实现，`.+` 模式对每个匹配字符递归一次，讯飞鉴权 URL 约 400 字符的路径段会触发 `maximum recursion depth exceeded`。

`xfyun_tts.py` 内部通过继承 `AsyncWebsocketClient` 创建私有子类 `_WsClient`，仅覆盖 `urlparse()` 方法，改用 `str.startswith` / `str.find` / 切片实现零递归的 URL 解析，对外接口完全不变。

---

## 使用说明

### 第一步：安装依赖

```bash
mpremote mip install https://upypi.net/pkgs/async_websocket_client/1.0.0
```

### 第二步：部署驱动文件

将 `code/xfyun_tts.py` 上传到设备根目录 `/`：

```bash
mpremote cp code/xfyun_tts.py :xfyun_tts.py
```

### 第三步：同步时间（必须）

讯飞 API 验证时间窗口，NTP 同步是必要步骤：

```python
import ntptime
ntptime.host = "ntp.aliyun.com"
ntptime.settime()
```

### 第四步：导入与初始化

```python
from xfyun_tts import XfyunTTS

tts = XfyunTTS(
    app_id     = "your_appid",
    api_key    = "your_api_key",
    api_secret = "your_api_secret",  # 平台提供的原始字符串，勿 Base64 解码
)
```

### 第五步：合成音频

```python
import asyncio

# 输出 RAW PCM 文件
total = asyncio.run(tts.synthesize("Hello World", filepath="output.pcm"))
print(total, "bytes written")

# 输出 WAV 文件（直接可在 PC 上播放）
total = asyncio.run(tts.synthesize("Hello World", filepath="output.wav"))
print(total, "bytes PCM + 44 bytes header")

# 极短文本：不写文件，返回 bytes（仅适合极短文本）
pcm_bytes = asyncio.run(tts.synthesize("Hi"))
```

### API 速查

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `XfyunTTS(app_id, api_key, api_secret, ...)` | 见下表 | 实例 | 初始化驱动 |
| `await synthesize(text, filepath=None)` | `text`: 待合成文字；`filepath`: 目标文件路径 | `int` 或 `bytes` | 合成并写文件或返回内存数据 |
| `await synthesize_and_play(text, audio_out, amp_sd, rate=16000)` | `text`: 待合成文字；`audio_out`: I2S TX 实例；`amp_sd`: 功放 SD 引脚；`rate`: 采样率 | `int` | 边收边播，返回写入 I2S 的总字节数 |

### 初始化参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `app_id` | str | — | 讯飞开放平台 APPID |
| `api_key` | str | — | API Key |
| `api_secret` | str | — | API Secret（平台提供的原始字符串） |
| `vcn` | str | `"x4_xiaoyan"` | 发音人 |
| `aue` | str | `"raw"` | 音频编码，`raw` = 原始 PCM |
| `auf` | str | `"audio/L16;rate=8000"` | 音频格式，采样率 8000 Hz，16-bit 单声道 |

---

## 示例程序

以下为 `code/main.py` 完整内容，演示 WiFi 连接、NTP 同步、PCM 输出和 WAV 输出：

```python
# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  : leeqingsui
# @File    : main.py
# @Description : iFlytek TTS usage example for MicroPython on Raspberry Pi Pico 2W
# @License : MIT

import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS

WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

APPID      = "your_appid"
API_KEY    = "your_api_key"
API_SECRET = "your_api_secret"

OUTPUT_FILE = "output.pcm"
OUTPUT_WAV  = "output.wav"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
        if not wlan.isconnected():
            return None
    return wlan

def sync_ntp():
    for host in ("ntp.aliyun.com", "ntp.tencent.com", "pool.ntp.org"):
        try:
            ntptime.host = host
            ntptime.settime()
            print("NTP synced via", host)
            return
        except Exception as e:
            print("NTP failed:", e)

async def run_tts(text):
    total = await tts.synthesize(text, filepath=OUTPUT_FILE)
    print("Saved", total, "bytes ->", OUTPUT_FILE)

async def run_tts_wav(text):
    total = await tts.synthesize(text, filepath=OUTPUT_WAV)
    print("Saved", total, "bytes PCM +44 bytes header ->", OUTPUT_WAV)

tts = XfyunTTS(app_id=APPID, api_key=API_KEY, api_secret=API_SECRET)

if __name__ == "__main__":
    time.sleep(3)
    print("--- FreakStudio iFlytek TTS Demo ---")
    if not connect_wifi():
        print("Aborting: WiFi unavailable.")
    else:
        sync_ntp()
        asyncio.run(run_tts("Hello, I am Xiaozhi. Nice to meet you."))
        asyncio.run(run_tts_wav("Hi there, this is a WAV format test from Pico 2W."))
```

**预期输出：**

```
--- FreakStudio iFlytek TTS Demo ---
WiFi already connected
NTP synced via ntp.aliyun.com
Synthesizing: Hello, I am Xiaozhi. Nice to meet you.
Connecting to iFlytek TTS...
Connected, sending request...
Receiving audio chunks...
Chunk received, bytes: 3200
Chunk received, bytes: 3200
...
All audio received, total bytes: 62400
Saved 62400 bytes -> output.pcm
Synthesizing (WAV): Hi there, this is a WAV format test from Pico 2W.
...
All audio received, total bytes: 57600
Saved 57600 bytes PCM +44 bytes header -> output.wav
```

---

## 注意事项

1. **NTP 时间同步是必须步骤**：鉴权签名包含当前时间戳，讯飞服务器验证时间窗口（通常 ±5 分钟）。未同步时间将导致 HTTP 401 Unauthorized。

2. **API Secret 不得 Base64 解码**：平台下发的 API Secret 字符串应直接以 UTF-8 编码作为 HMAC 密钥。Base64 解码后使用会导致签名错误（401）。

3. **`filepath` 参数强烈建议提供**：Pico 2W 可用 RAM 约 100~150 KB。音频若在内存中一次性拼接会 OOM 崩溃；流式写入方案内存峰值仅约 4 KB。

4. **WAV 格式说明**：输出为 16-bit signed PCM，8000 Hz，单声道。PC 验证播放命令：
   ```bash
   ffplay -f s16le -ar 8000 -ac 1 output.pcm   # PCM 格式
   ffplay output.wav                             # WAV 格式（直接打开）
   ```

5. **`wss://` 首次 TLS 握手较慢**：Pico 2W 使用软件 TLS（lwIP），首次握手耗时约 2~4 秒，属正常现象。

6. **不支持分片帧**：讯飞 TTS 服务端每次返回完整单帧，不受此限制影响。

7. **全局变量区禁止实例化**：根据项目规范，`XfyunTTS` 实例应在初始化配置区创建，而非全局变量区。

---

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

---

## 许可协议

本项目基于 [MIT License](LICENSE) 开源协议发布。

```
MIT License

Copyright (c) 2026 FreakStudio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
