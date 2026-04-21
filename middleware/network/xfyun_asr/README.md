# XfyunASR

适用于 MicroPython 的讯飞中英识别大模型（ASR）驱动，通过 WebSocket 连接讯飞开放平台，将 PCM 音频文件实时识别为文字，已在树莓派 Pico 2W 上通过验证。

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

`XfyunASR` 是一个专为 MicroPython 设计的轻量级讯飞在线 ASR 驱动。它依赖 [`async_websocket_client`](https://upypi.net/zh/pkgs/async_websocket_client) 库建立 WSS 连接，在设备端实现 HMAC-SHA256 签名鉴权、JSON 请求构造与流式音频发送，将识别结果拼接后以字符串返回。

- 支持**中文、英文及 202 种方言**免切换识别
- 内存峰值仅为单帧大小（**1280 字节**），与音频时长完全无关

---

## 主要功能

- **HMAC-SHA256 签名鉴权**：纯 MicroPython 实现，不依赖标准 `hmac` 模块
- **RFC1123 时间格式**：手写实现，不依赖 `wsgiref`
- **URL 百分号编码**：手写实现，不依赖 `urllib.parse`
- **流式分帧发送**：每帧 1280 字节，间隔 40ms，符合 API 实时发送规范
- **先发后收策略**：规避 MicroPython 单线程 asyncio 无法真正并发收发的限制
- **两层结果解码**：`payload.result.text` → Base64 解码 → JSON 解析 → 拼接文字
- **正则递归绕过**：通过子类覆盖 `urlparse()`，规避 MicroPython `ure` 引擎对长 URL 的递归溢出
- **完整参数校验**：`__init__` 和 `recognize()` 均对入参做 None / 类型 / 值范围三级校验
- **超时保护**：`handshake()` 和 `recv()` 均有 10 秒超时，网络异常时自动返回空字符串而非永久阻塞

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 WiFi 的 MicroPython 设备） |
| 固件 | MicroPython v1.23.0 及以上 |
| 网络 | 2.4GHz WiFi，需能访问 `iat.xf-yun.com`（讯飞 ASR 服务） |
| 额外硬件 | 无（纯软件库，不依赖任何外设） |

---

## 文件说明

```
xfyun_asr/
├── code/
│   ├── xfyun_asr.py    # 驱动核心实现
│   └── main.py         # 使用示例 / 测试代码
├── package.json        # mip 包配置（含依赖声明）
├── README.md           # 使用文档
└── LICENSE             # MIT 开源协议
```

| 文件 | 说明 |
|------|------|
| `code/xfyun_asr.py` | 驱动核心类 `XfyunASR`，包含鉴权、帧构造、流式发送与结果解析全部逻辑 |
| `code/main.py` | 完整使用示例，演示 WiFi 连接、NTP 同步、TTS 合成 + ASR 识别的完整流程 |
| `package.json` | mip 包描述文件，声明包名、版本、作者及对 `async_websocket_client` 的依赖 |
| `LICENSE` | MIT 开源协议文本 |

---

## 软件设计核心思想

### 1. HMAC-SHA256 鉴权流程

讯飞 ASR API 采用与 TTS 完全相同的基于时间戳的签名鉴权：

```
获取当前 UTC 时间（RFC1123 格式，依赖 NTP 同步）
    ↓
构造签名原文：
    "host: iat.xf-yun.com\n
     date: {RFC1123 时间}\n
     GET /v1 HTTP/1.1"
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

### 2. 流式分帧发送 + 先发后收策略

MicroPython 的 asyncio 是单线程协程，无法真正并发发送和接收。本驱动采用"先发完所有帧，再进入接收循环"的策略：

```
打开 PCM 文件
    ↓
循环读 1280 字节/帧 → Base64 → 构造 JSON → ws.send()
    status: 0（首帧，附带 parameter.iat）
           1（中间帧）
           2（末帧，audio 可为空）
    seq 每帧递增，每帧间隔 asyncio.sleep_ms(40)
    ↓
所有帧发送完毕
    ↓
进入接收循环：while ws.open() → ws.recv()
    payload.result.text → Base64 解码 → JSON → 拼接 ws[].cw[].w
    header.status == 2 → break
    ↓
关闭连接，返回完整识别文字
```

内存中同时仅存在单帧数据（1280 字节），识别结果为纯文字，无内存压力。

### 3. 规避 MicroPython 正则递归限制

与 `xfyun_tts` 驱动相同，讯飞鉴权 URL 约 400 字符，会触发 `ure` 引擎的递归溢出。通过继承 `AsyncWebsocketClient` 创建私有子类 `_WsClient`，仅覆盖 `urlparse()` 方法，改用 `str.startswith` / `str.find` / 切片实现零递归的 URL 解析。

---

## 使用说明

### 第一步：安装依赖

> ⚠️ **运行 `main.py` 之前，必须先安装以下两个依赖库：**

**1. 安装 `async_websocket_client`**

前往 [upypi.net](https://upypi.net) 搜索 `async_websocket_client`，复制安装命令后在终端运行，例如：

```bash
mpremote mip install https://upypi.net/pkgs/async_websocket_client/1.0.0
```

**2. 安装 `xfyun_tts`**（`main.py` 中同时演示了 TTS，需要此库）

前往 [upypi.net](https://upypi.net) 搜索 `xfyun_tts`，复制安装命令后在终端运行，例如：

```bash
mpremote mip install https://upypi.net/pkgs/xfyun_tts/1.0.0
```

> 如果你只使用 `XfyunASR` 而不使用 TTS，则仅需安装 `async_websocket_client`。

### 第二步：部署驱动文件

将 `code/xfyun_asr.py` 上传到设备根目录 `/`：

```bash
mpremote cp code/xfyun_asr.py :xfyun_asr.py
```

### 第三步：同步时间（必须）

讯飞 API 验证时间窗口（±300 秒），NTP 同步是必要步骤：

```python
import ntptime
ntptime.host = "ntp.aliyun.com"
ntptime.settime()
```

### 第四步：导入与初始化

```python
from xfyun_asr import XfyunASR

asr = XfyunASR(
    app_id      = "your_appid",
    api_key     = "your_api_key",
    api_secret  = "your_api_secret",  # 平台提供的原始字符串，勿 Base64 解码
    sample_rate = 8000,               # 须与音频文件采样率一致
)
```

### 第五步：识别音频文件

```python
import asyncio

# 识别 PCM 文件，返回识别文字字符串
text = asyncio.run(asr.recognize("output.pcm"))
print(text)
```

### API 速查

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `XfyunASR(app_id, api_key, api_secret, ...)` | 见下表 | 实例 | 初始化驱动 |
| `await recognize(filepath)` | `filepath`: PCM 文件路径 | `str` | 识别并返回文字 |

### 初始化参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `app_id` | str | — | 讯飞开放平台 APPID |
| `api_key` | str | — | API Key |
| `api_secret` | str | — | API Secret（平台提供的原始字符串） |
| `sample_rate` | int | `16000` | 音频采样率，`8000` 或 `16000` |
| `accent` | str | `"mandarin"` | 口音/方言（如 `"cantonese"`、`"sichuan"`） |
| `eos` | int | `6000` | 静音停止阈值（毫秒，范围 500~60000） |

---

## 示例程序

以下为 `code/main.py` 完整内容，演示 WiFi 连接、NTP 同步、TTS 合成与 ASR 识别的完整流程：

> ⚠️ **运行前请确保已按"使用说明 第一步"安装 `async_websocket_client` 和 `xfyun_tts` 两个依赖库。**

```python
# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/14
# @Author  : leeqingsui
# @File    : main.py
# @Description : iFlytek TTS + ASR demo for MicroPython on Raspberry Pi Pico 2W

import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS
from xfyun_asr import XfyunASR

WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

TTS_APPID      = "your_tts_appid"
TTS_API_KEY    = "your_tts_api_key"
TTS_API_SECRET = "your_tts_api_secret"

ASR_APPID      = "your_asr_appid"
ASR_API_KEY    = "your_asr_api_key"
ASR_API_SECRET = "your_asr_api_secret"

# ... （完整代码见 code/main.py）
```

**预期输出：**

```
FreakStudio: iFlytek TTS + ASR Demo
WiFi already connected
NTP synced via ntp.aliyun.com: 2026-04-14 09:38:15 UTC
Synthesizing: 大家好一块吃饭吧hello
Connecting to iFlytek TTS...
Connected, sending request...
Chunk received, bytes: 11520
...
Saved 39252 bytes -> output.pcm
Recognizing: output.pcm
Connecting to iFlytek ASR...
Connected, sending audio frames...
All frames sent (31), receiving results...
Recognition complete.
ASR result: 大家好，一块吃饭吧，hello。
```

---

## 注意事项

1. **NTP 时间同步是必须步骤**：鉴权签名包含当前时间戳，讯飞服务器验证时间窗口（±300 秒）。未同步时间将导致 HTTP 401 Unauthorized。

2. **API Secret 不得 Base64 解码**：平台下发的 API Secret 字符串应直接以 UTF-8 编码作为 HMAC 密钥。Base64 解码后使用会导致签名错误（401）。

3. **采样率必须一致**：`sample_rate` 参数须与 PCM 文件的实际采样率严格匹配。若使用 `xfyun_tts` 生成的 `output.pcm`，TTS 默认采样率为 8000 Hz，ASR 也应设置 `sample_rate=8000`。

4. **TTS 与 ASR 需分别开通服务**：讯飞控制台中，语音合成（TTS）和中英识别大模型（ASR）是独立的服务，需分别在对应产品页面获取免费额度或购买套餐，同一 APPID 可同时开通两项服务。

5. **运行 `main.py` 必须先安装依赖**：`main.py` 同时依赖 `async_websocket_client` 和 `xfyun_tts` 两个库，请先前往 [upypi.net](https://upypi.net) 搜索对应包名，复制安装命令在终端运行。

6. **音频格式要求**：输入 PCM 文件须为 16-bit 有符号，单声道，采样率 8000 Hz 或 16000 Hz。PC 验证命令：
   ```bash
   ffplay -f s16le -ar 8000 -ac 1 output.pcm
   ```

7. **`wss://` 首次 TLS 握手较慢**：Pico 2W 使用软件 TLS（lwIP），首次握手耗时约 2~4 秒，属正常现象。

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
