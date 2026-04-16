# aiohttps

**版本：1.1.2**

适用于 MicroPython 的异步 HTTPS/HTTP 客户端库，支持流式上传与下载、SSE 逐行读取，已在树莓派 Pico 2W 上通过验证。

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

`aiohttps` 是一个专为 MicroPython 设计的轻量级异步 HTTP/HTTPS 客户端库。它基于 MicroPython 内置的 `socket`、`ssl`、`asyncio` 模块实现，**无任何外部依赖**，支持非阻塞异步请求、流式下载写文件和流式上传文件，特别适合内存受限的嵌入式设备（如 Pico 2W）与云端 API（LLM、TTS、IoT 平台）的对接。

---

## 主要功能

- **异步非阻塞**：基于 `asyncio` 事件循环，请求期间每 5ms 让出 CPU，不阻塞其他协程
- **HTTPS / HTTP 双协议**：自动根据 URL scheme 选择 TLS 加密或明文连接
- **URL 无正则解析**：纯字符串操作解析 URL，规避 MicroPython `ure` 引擎递归溢出
- **流式下载**：`resp.save(filepath)` 边接收边写盘，内存峰值仅为单块大小（1 KB）
- **流式上传**：`data=filepath` 时先读文件大小填入 `Content-Length`，再分块发送
- **大 body 分块发送**：`data=str/bytes` 时按 1 KB 分块写入 socket，避免大 payload（如 base64 图片）阻塞非阻塞缓冲区
- **读取超时**：`request(timeout_ms=30000)` / `get()` / `post()` 均支持超时参数，超时后抛出 `OSError("timeout")`，避免服务端无响应时永久阻塞
- **全量读取**：`resp.text` / `resp.json()` 适合小响应（JSON、文本，几 KB）
- **SSE 流式读取**：`resp.iter_lines()` 逐行读取，适合 LLM 流式输出（text/event-stream）
- **任意 HTTP 方法**：`get()`、`post()` 便捷函数，或通过 `request(method, ...)` 支持 PUT、DELETE 等
- **非 2xx 不抛异常**：服务端错误状态码由调用方通过 `resp.status` 自行判断

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 WiFi 的 MicroPython 设备） |
| 固件 | MicroPython v1.23.0 及以上 |
| 网络 | 2.4GHz WiFi，需能访问目标 HTTPS 服务 |
| 额外硬件 | 无（纯软件库，不依赖任何外设） |

---

## 文件说明

```
aiohttps/
├── code/
│   ├── aiohttps.py     # 驱动核心实现
│   └── main.py         # 使用示例 / 测试代码
├── package.json        # mip 包配置
├── README.md           # 使用文档
└── LICENSE             # MIT 开源协议
```

| 文件 | 说明 |
|------|------|
| `code/aiohttps.py` | 核心实现：URL 解析、socket 管理、TLS 握手、请求构造、响应读取 |
| `code/main.py` | 全量测试示例，覆盖 GET/POST/PUT、json()/text/save()、HTTP/HTTPS、404 状态码 |
| `package.json` | mip 包描述文件，无外部依赖 |
| `LICENSE` | MIT 开源协议文本 |

---

## 软件设计核心思想

### 1. 非阻塞异步读写

MicroPython 的 `asyncio` 要求 I/O 操作不能长时间独占 CPU。`aiohttps` 将 socket 设为非阻塞模式，所有读写循环内均插入 `await asyncio.sleep_ms(5)`，让出 CPU 给其他协程，与 `async_websocket_client` 保持完全一致的轮询节奏。

```
sock.setblocking(False)
while data is None:
    data = sock.read(size)
    await asyncio.sleep_ms(5)   ← 每轮让出 CPU
```

### 2. 流式读写，内存峰值恒定

Pico 2W 可用堆内存约 100~150 KB，大文件若在内存中一次性拼接会 OOM 崩溃。本库采用 1 KB 分块策略：

```
下载（save）：每次读 1 KB → 立即写盘 → 释放该块内存
上传（file）：每次读 1 KB → 立即发送 → 释放该块内存
上传（str/bytes body）：按 1 KB 分块写入 socket → 每块让出 CPU
```

无论响应体多大，内存中同时仅存在一个 1 KB 块。

### 3. URL 无正则解析

MicroPython `ure` 引擎采用递归 NFA 实现，对长 URL（如鉴权参数超过 200 字符）会触发 `maximum recursion depth exceeded`。`aiohttps` 使用 `str.startswith` / `str.find` / 切片实现零递归 URL 解析：

```
https://host:port/path?query
  ↓ startswith 判断 scheme
  ↓ find("/") 分离 host 与 path
  ↓ find(":") 分离 host 与 port
```

---

## 使用说明

### 第一步：部署驱动文件

将 `code/aiohttps.py` 上传到设备根目录 `/`：

```bash
mpremote cp code/aiohttps.py :aiohttps.py
```

或通过 mip 安装（发布后可用）：

```bash
mpremote mip install github:FreakStudioCN/GraftSense-Drivers-MicroPython/communication/aiohttps
```

### 第二步：导入与使用

```python
import asyncio
import aiohttps

async def main():
    # GET 请求，读取 JSON
    resp = await aiohttps.get("https://httpbin.org/get")
    data = await resp.json()
    print(data["origin"])

    # POST 请求，发送 JSON 字符串
    resp = await aiohttps.post(
        "https://api.example.com/chat",
        headers={"Authorization": "Bearer YOUR_TOKEN",
                 "Content-Type": "application/json"},
        data='{"message": "hello"}',
    )
    print(await resp.text)

    # 流式下载大文件
    resp = await aiohttps.get("https://example.com/audio.pcm")
    n = await resp.save("audio.pcm")
    print("downloaded", n, "bytes")

asyncio.run(main())
```

### API 速查

| 函数 / 方法 | 参数 | 返回值 | 说明 |
|------------|------|--------|------|
| `await get(url, headers)` | url: str; headers: dict | Response | 发起 GET 请求 |
| `await post(url, headers, data)` | url: str; headers: dict; data: str\|bytes | Response | 发起 POST 请求 |
| `await request(method, url, headers, data)` | method: str; 其余同上 | Response | 发起任意方法请求 |
| `resp.status` | — | int | HTTP 状态码 |
| `resp.headers` | — | dict | 响应头（键小写） |
| `await resp.json()` | — | dict | 全量读取并解析 JSON |
| `await resp.text` | — | str | 全量读取为 UTF-8 字符串 |
| `await resp.save(filepath)` | filepath: str | int | 流式写入文件，返回总字节数 |
| `resp.close()` | — | None | 手动关闭底层 socket |
| `resp.iter_lines()` | — | _LineIter | 流式逐行读取，适合 SSE |

### data 参数说明

| 类型 | 行为 |
|------|------|
| `None` | 无请求体（GET 等） |
| `str`（文件路径且存在） | 流式上传文件，Content-Length 自动填入 |
| `str`（普通字符串） | 编码为 UTF-8 字节发送 |
| `bytes` | 直接发送 |

---

## 示例程序

以下为 `code/main.py` 完整内容，演示 9 项核心功能测试：

```python
# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/15
# @Author  : leeqingsui
# @File    : main.py
# @Description : aiohttps async HTTPS client test for MicroPython on Raspberry Pi Pico 2W

import network
import asyncio
import time
import json
import ntptime
import aiohttps

WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

async def test_aiohttps():
    # ... 见 code/main.py
    pass

time.sleep(3)
print("FreakStudio: aiohttps async HTTPS client test")

if __name__ == "__main__":
    asyncio.run(test_aiohttps())
```

**预期输出：**

```
FreakStudio: aiohttps async HTTPS client test
WiFi connected, IP: 192.168.x.x
NTP synced via ntp.aliyun.com: 2026-04-15 08:21:30 UTC
--- aiohttps Test Start ---
[1/8] GET https://httpbin.org/get
  status: 200
  origin IP: x.x.x.x
  [1/8] PASS
[2/8] POST https://httpbin.org/post (str body)
  [2/8] PASS
[3/8] GET https://httpbin.org/bytes/4096 -> save test.bin
  saved: 4096 bytes
  [3/8] PASS
[4/8] GET https://httpbin.org/status/404
  status: 404
  [4/8] PASS
[5/8] GET https://httpbin.org/encoding/utf8 -> text
  text length: 7808
  [5/8] PASS
[6/8] POST https://httpbin.org/post (bytes body)
  [6/8] PASS
[7/8] PUT https://httpbin.org/put
  [7/8] PASS
[8/9] GET http://httpbin.org/get (plain HTTP)
  status: 200
  origin IP: x.x.x.x
  [8/9] PASS
[9/9] GET https://httpbin.org/stream/3 -> iter_lines()
  status: 200
  line 1: 2 bytes
  line 2: 186 bytes
  line 3: 2 bytes
  line 4: 186 bytes
  line 5: 2 bytes
  line 6: 186 bytes
  line 7: 1 bytes
  [9/9] PASS
--- aiohttps Test Done ---
```

---

## 注意事项

1. **`text` / `json()` / `save()` / `iter_lines()` 只能调用其中一个**：四者均会消费响应体并关闭 socket，重复调用返回空值。

2. **`save()` 适合大响应**：Pico 2W 可用 RAM 约 100~150 KB，超过此大小的响应体必须使用 `save()` 流式写入，否则 OOM 崩溃。

3. **非 2xx 状态码不抛异常**：`resp.status` 需由调用方主动判断，例如 `if resp.status != 200: ...`。

4. **不验证服务端证书**：TLS 握手使用 `cert_reqs=0`（CERT_NONE），适合资源受限设备，生产环境如需验证证书请自行扩展。

5. **首次 TLS 握手较慢**：Pico 2W 使用软件 TLS（lwIP），首次握手耗时约 2~4 秒，属正常现象。

6. **文件流式上传检测方式**：`data` 为 `str` 时，库通过 `os.stat(data)` 判断是否为文件路径。若字符串恰好与某文件路径相同，将被当作文件上传而非字符串发送，请注意区分。

7. **大 JSON body 自动分块发送**：`data` 为 `str` 或 `bytes` 时（如 base64 图片），库按 1 KB 分块写入 socket 并每块让出 CPU，避免大 payload 阻塞非阻塞缓冲区导致发送不完整。

8. **读取超时**：`request()`、`get()`、`post()` 均支持 `timeout_ms` 参数（默认 30000ms）。超时后抛出 `OSError("timeout")`，避免服务端无响应时永久阻塞。视觉模型等慢接口建议设置更大值，如 `timeout_ms=60000`。

---

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

---

## 许可协议

本项目基于 [MIT License](LICENSE) 开源协议发布。
