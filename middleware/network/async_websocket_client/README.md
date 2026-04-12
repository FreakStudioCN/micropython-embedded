# AsyncWebsocketClient

适用于 MicroPython 的异步 WebSocket 客户端驱动，支持 `ws://` 与 `wss://` 协议，基于 `asyncio` 实现非阻塞通信。

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

`AsyncWebsocketClient` 是一个专为 MicroPython 设计的轻量级异步 WebSocket 客户端库。它封装了 WebSocket 握手、帧编解码、TLS 加密连接等底层细节，提供简洁的 `send` / `recv` 接口，开发者无需关心协议细节即可快速接入 WebSocket 服务。

该库适用于需要与云端 API（如语音识别、语音合成、大模型等）进行实时双向通信的嵌入式场景，已在树莓派 Pico 2W 上通过验证。

---

## 主要功能

- **双协议支持**：同时支持明文 `ws://`（端口 80）和加密 `wss://`（端口 443，TLS）
- **异步非阻塞**：基于 `asyncio`，通过轮询方式实现非阻塞 I/O，不阻塞事件循环
- **帧类型处理**：支持文本帧（OP_TEXT）、二进制帧（OP_BYTES）、关闭帧（OP_CLOSE）
- **自动 PING/PONG**：收到服务端 PING 时自动回复 PONG，保持长连接心跳
- **TLS 灵活配置**：支持不验证证书（`cert_reqs=0`）、可选验证、强制验证及客户端证书（双向 TLS）
- **自定义 HTTP 头**：握手阶段支持注入额外请求头，满足 API 鉴权需求
- **URL 内嵌鉴权**：鉴权参数（如讯飞 API 的 `authorization`）可直接拼入查询字符串，无需额外头部

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 WiFi 的 MicroPython 设备） |
| 固件 | MicroPython v1.23.0 及以上 |
| 网络 | 2.4GHz WiFi，需能访问目标 WebSocket 服务器 |
| 额外硬件 | 无（纯软件库，不依赖任何外设） |

---

## 文件说明

```
async_websocket_client/
├── code/
│   ├── async_websocketclient.py    # 驱动核心实现
│   └── main.py                     # 使用示例 / 测试代码
├── package.json                    # mip 包配置
└── README.md                       # 使用文档
```

| 文件 | 说明 |
|------|------|
| `code/async_websocketclient.py` | WebSocket 客户端核心类 `AsyncWebsocketClient`，包含握手、收发、帧处理全部逻辑 |
| `code/main.py` | 完整使用示例，演示 WiFi 连接、WSS 握手、消息收发、连接关闭的完整流程 |
| `package.json` | mip 包描述文件，定义包名、版本、作者及文件映射 |

---

## 软件设计核心思想

### 1. 异步非阻塞轮询

MicroPython 的 socket 在设置为非阻塞模式（`setblocking(False)`）后，`read()` 在数据未就绪时返回 `None` 而非阻塞等待。本库通过在每次轮询后执行 `await asyncio.sleep_ms(delay_read)` 主动让出 CPU，使其他协程得以运行，实现真正的非阻塞并发。

```
socket.read() → None（未就绪）
      ↓
await sleep_ms(delay_read)   ← 让出 CPU 给其他协程
      ↓
socket.read() → bytes（就绪）
```

### 2. WebSocket 帧结构

每条消息被封装为标准 RFC 6455 帧：

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M|  Payload    |    Extended payload length    |
|I|S|S|S|  (4)  |A|   length    |          (if 16/64 bit)       |
|N|V|V|V|       |S|    (7)      |                               |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+-------------------------------+
|           Masking-key (32 bit, client→server 必须掩码)         |
+---------------------------------------------------------------+
|                    Payload Data                               |
+---------------------------------------------------------------+
```

客户端发送的帧**必须携带 4 字节随机掩码**（RFC 6455 强制要求），`write_frame()` 自动处理掩码生成与异或运算。

### 3. 状态管理与互斥锁

连接状态 `_open` 通过 `asyncio.Lock` 保护，防止多协程并发访问时的竞态条件：

```python
await self._lock_for_open.acquire()
# ... 读写 _open ...
self._lock_for_open.release()
```

### 4. TLS 通过 ssl.wrap_socket 实现

`wss://` 连接在 TCP 连接建立后，通过 MicroPython 内置的 `ssl.wrap_socket()` 将裸 socket 升级为 TLS socket，对上层透明，后续读写接口完全一致。

---

## 使用说明

### 第一步：导入与初始化

```python
from async_websocketclient import AsyncWebsocketClient

# ms_delay_for_read：轮询间隔（毫秒）
# 越小延迟越低，越大 CPU 占用越低，建议 5~20
ws = AsyncWebsocketClient(ms_delay_for_read=10)
```

### 第二步：建立连接

```python
import asyncio

async def main():
    # ws:// 明文连接
    await ws.handshake("ws://192.168.1.100:8765")

    # wss:// 加密连接（不验证证书）
    await ws.handshake("wss://api.example.com/ws", cert_reqs=0)

    # wss:// 带鉴权参数（URL 查询字符串方式，适用于讯飞等 API）
    await ws.handshake("wss://tts-api.xfyun.cn/v2/tts?authorization=xxx&date=xxx&host=xxx", cert_reqs=0)
```

### 第三步：发送与接收

```python
    # 发送文本（自动使用 OP_TEXT 帧）
    await ws.send("Hello World")

    # 发送二进制（自动使用 OP_BYTES 帧）
    await ws.send(b"\x01\x02\x03")

    # 接收一条消息
    msg = await ws.recv()
    # msg 为 str（文本帧）、bytes（二进制帧）或 None（连接关闭）
```

### 第四步：关闭连接

```python
    await ws.close()

asyncio.run(main())
```

### API 速查

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `handshake(uri, headers=[], cert_reqs=0, ...)` | URI 字符串 | `bool` | 建立连接并完成握手 |
| `send(buf)` | `str` 或 `bytes` | — | 发送一条消息 |
| `recv()` | — | `str` / `bytes` / `None` | 接收一条消息 |
| `close()` | — | `bool` | 关闭连接 |
| `open(new_val=None)` | `bool` 或 `None` | `bool` | 查询或设置连接状态 |

---

## 示例程序

以下为 `code/main.py` 完整内容，演示连接 WSS echo 服务器并进行 5 轮收发测试：

```python
# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  :
# @File    : main.py
# @Description : Async WebSocket client usage example for MicroPython

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import machine
import time
from async_websocketclient import AsyncWebsocketClient  # 导入你的WebSocket库

# ======================================== 全局变量 ============================================

# 配置WiFi (请替换为你的WiFi信息)
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

# 测试服务器地址 (Postman Echo)
TEST_URL = "wss://ws.postman-echo.com/raw"

# ======================================== 功能函数 ============================================

def connect_wifi():
    """
    连接 WiFi 并返回网络对象。

    Returns:
        network.WLAN: 已连接的 WLAN 对象；连接失败时返回 None。

    ==========================================

    Connect to WiFi and return the network object.

    Returns:
        network.WLAN: Connected WLAN object; None if connection fails.
    """
    # 初始化WiFi为STA模式（客户端模式）
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # 避免重复连接
    if not wlan.isconnected():
        print(f"Connecting to WiFi: {WIFI_SSID}")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        # 等待连接（最多等待10秒）
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(f"Connecting... {timeout}s remaining")

        if wlan.isconnected():
            # 打印连接信息（IP、子网掩码、网关、DNS）
            ip_info = wlan.ifconfig()
            print(f"WiFi connected")
            print(f"IP: {ip_info[0]}")
            print(f"Gateway: {ip_info[2]}")
            print(f"DNS: {ip_info[3]}")
        else:
            print("WiFi connection failed")
            return None
    else:
        print("WiFi already connected")

    return wlan

async def websocket_test():
    """
    WebSocket 测试主逻辑，依次完成连接、发送、接收和关闭。

    ==========================================

    Main WebSocket test logic: connect, send, receive, and close in sequence.
    """
    global ws_client

    try:
        # 1. 连接WiFi
        if not connect_wifi():
            return

        # 2. 连接WebSocket服务器
        print("Connecting: {}".format(TEST_URL))
        await ws_client.handshake(TEST_URL)
        print("WebSocket connected (WSS)")

        # 3. 发送测试消息
        test_message = "Hello from Pico2W!"
        print("Sending: {}".format(test_message))
        await ws_client.send(test_message)

        # 4. 循环接收消息
        for count in range(5):
            print("\nWaiting for message ({})...".format(count + 1))
            response = await ws_client.recv()

            if response:
                print("Received: {}".format(response))
                # 发送下一条消息
                next_msg = "Pico count: {}".format(count + 1)
                await ws_client.send(next_msg)
                await asyncio.sleep(1)
            else:
                print("No message received, connection may be closed")
                break

        # 5. 关闭连接
        print("\nTest complete, closing connection...")
        await ws_client.close()
        print("Connection closed")

    except Exception as e:
        print("\nException: {} - {}".format(type(e).__name__, e))
        await ws_client.close()

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

# 初始化WebSocket客户端
ws_client = AsyncWebsocketClient(ms_delay_for_read=5)

# ========================================  主程序  ===========================================

# 运行主程序
if __name__ == "__main__":
    asyncio.run(websocket_test())
```

**预期输出：**

```
WiFi connected
IP: 192.168.x.x
Gateway: 192.168.x.x
DNS: 192.168.x.x
Connecting: wss://ws.postman-echo.com/raw
WebSocket connected (WSS)
Sending: Hello from Pico2W!

Waiting for message (1)...
Received: Hello from Pico2W!

Waiting for message (2)...
Received: Pico count: 1
...
Test complete, closing connection...
Connection closed
```

---

## 注意事项

1. **`asyncio` 必须全程贯穿**：`AsyncWebsocketClient` 的所有 I/O 方法均为协程，必须在 `async` 函数内通过 `await` 调用，并使用 `asyncio.run()` 启动入口函数。

2. **`wss://` 首次 TLS 握手较慢**：Pico 2W 使用 lwIP 软件 TLS，首次握手耗时约 2~4 秒，属正常现象。

3. **不支持分片帧**：`recv()` 遇到 `fin=False` 的分片帧（`OP_CONT`）会抛出 `NotImplementedError`，大多数云端 API 单帧返回完整消息，不受影响。

4. **`cert_reqs=0` 不验证服务器证书**：适用于资源受限的嵌入式场景，生产环境如需严格验证，请提供 `cafile` 参数并设置 `cert_reqs=2`。

5. **`ms_delay_for_read` 调优**：
   - 低延迟场景（如实时语音）：设为 `5`
   - 低功耗场景：设为 `20~50`
   - 默认值 `5` 适合大多数情况

6. **全局变量区禁止实例化**：根据项目规范，`AsyncWebsocketClient` 实例应在初始化配置区创建，而非全局变量区。

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
