# uopenai

**版本：1.0.0**

适用于 MicroPython 的 OpenAI 兼容异步客户端库，依赖 `aiohttps`，已在树莓派 Pico 2W 上通过验证。

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

`uopenai` 是一个专为 MicroPython 设计的轻量级 OpenAI 兼容异步客户端库。它基于 `aiohttps` 实现，**无其他外部依赖**，支持非流式和流式（SSE）文字对话、视觉模型图片输入、base64 图片编码，特别适合内存受限的嵌入式设备（如 Pico 2W）与 OpenAI 兼容云端 API（DeepSeek、豆包、Moonshot 等）的对接。

---

## 主要功能

- **文字对话（非流式）**：`chat.completions.create()` 返回完整响应对象，含 `id`、`model`、`usage`、`choices`
- **文字对话（流式 SSE）**：`stream=True` 返回 `aiohttps.Response`，通过 `iter_lines()` 逐块读取
- **视觉模型**：支持 `content` 为列表格式，传入 `image_url`（base64 data URI）
- **图片编码**：`OpenAI.encode_image(filepath)` 静态方法，将本地图片编码为 base64 字符串
- **请求超时**：`create(timeout_ms=30000)` 支持自定义超时，避免服务端无响应时永久阻塞
- **接口兼容**：与 PC 端 `openai` SDK 保持最大接口兼容，`base_url` 可替换为任意 OpenAI 兼容服务

---

## 硬件要求

| 项目 | 要求 |
|------|------|
| 主控 | 树莓派 Pico 2W（或其他支持 WiFi 的 MicroPython 设备） |
| 固件 | MicroPython v1.23.0 及以上 |
| 网络 | 2.4GHz WiFi，需能访问目标 HTTPS API |
| 额外硬件 | 无（纯软件库，不依赖任何外设） |

---

## 文件说明

```
uopenai/
├── code/
│   ├── uopenai.py      # 驱动核心实现
│   ├── main.py         # 使用示例 / 测试代码
│   └── test_4kb.jpg    # 视觉测试用图（3516 字节，128x128）
├── package.json        # mip 包配置（含 aiohttps 依赖）
├── README.md           # 使用文档
└── LICENSE             # MIT 开源协议
```

| 文件 | 说明 |
|------|------|
| `code/uopenai.py` | 核心实现：OpenAI 客户端、chat/completions、encode_image |
| `code/main.py` | 全量测试示例，覆盖 14 项测试（12 PASS + 2 SKIP） |
| `code/test_4kb.jpg` | 视觉测试用图，128x128 彩色 JPEG，约 3.5 KB |
| `package.json` | mip 包描述文件，声明 aiohttps 依赖 |
| `LICENSE` | MIT 开源协议文本 |

---

## 软件设计核心思想

### 1. 接口兼容性

与 PC 端 `openai` SDK 保持最大接口兼容：

```python
# PC 端 openai SDK
from openai import OpenAI
client = OpenAI(api_key="...", base_url="...")
resp = client.chat.completions.create(model="...", messages=[...])

# uopenai（MicroPython）
from uopenai import OpenAI
client = OpenAI(api_key="...", base_url="...")
resp = await client.chat.completions.create(model="...", messages=[...])
```

唯一区别：所有 `create()` 方法均为 `async`，需在 `asyncio` 事件循环中调用。

### 2. 流式 SSE 读取

`stream=True` 时直接返回底层 `aiohttps.Response`，调用方通过 `iter_lines()` 逐行读取 SSE 数据，内存峰值仅为单行大小：

```python
stream_resp = await client.chat.completions.create(
    model="...", messages=[...], stream=True
)
async for line in stream_resp.iter_lines():
    if line.startswith(b"data: ") and line != b"data: [DONE]":
        delta = json.loads(line[6:])["choices"][0]["delta"]
        print(delta.get("content", ""), end="")
```

### 3. 视觉模型与 base64 限制

`encode_image()` 将整个图片文件读入内存后编码，适合小图片（< 6 KB 原图）。Pico 2W 可用 RAM 约 150 KB，base64 编码后体积约为原图的 1.37 倍，总 JSON payload 需控制在 12 KB 以内以确保服务端正常响应。

---

## 使用说明

### 第一步：安装依赖

通过 mip 安装（设备联网后在 REPL 中运行）：

```python
import mip
mip.install("github:FreakStudioCN/GraftSense-Drivers-MicroPython/communication/uopenai")
```

或通过 mpremote 手动上传：

```bash
mpremote cp code/uopenai.py :uopenai.py
mpremote cp code/aiohttps.py :aiohttps.py   # 需先安装 aiohttps
```

### 第二步：导入与使用

```python
import asyncio
from uopenai import OpenAI

client = OpenAI(api_key="your_api_key", base_url="https://api.openai.com/v1")

async def main():
    # 非流式文字对话
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(resp.choices[0].message.content)

    # 流式文字对话
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Count 1 to 5."}],
        stream=True,
    )
    import json
    async for line in stream.iter_lines():
        line = line.strip()
        if line.startswith(b"data: ") and line != b"data: [DONE]":
            delta = json.loads(line[6:])["choices"][0]["delta"]
            print(delta.get("content", ""), end="")

asyncio.run(main())
```

### API 速查

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `OpenAI(api_key, base_url)` | api_key: str; base_url: str | OpenAI | 初始化客户端 |
| `await client.chat.completions.create(...)` | model, messages, stream=False, timeout_ms=30000, **kwargs | _ChatCompletionResponse \| Response | 文字/视觉对话 |
| `OpenAI.encode_image(filepath)` | filepath: str | str | 图片编码为 base64 |
| `resp.id` | — | str | 响应 ID |
| `resp.model` | — | str | 模型名称 |
| `resp.usage` | — | dict | token 用量 |
| `resp.choices[0].message.content` | — | str | 回复文本 |
| `resp.choices[0].finish_reason` | — | str | 结束原因 |

### kwargs 常用参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `temperature` | float | 随机性，0.0~2.0 |
| `max_tokens` | int | 最大输出 token 数 |
| `stream` | bool | 是否启用流式输出 |
| `timeout_ms` | int | 请求超时毫秒数，默认 30000 |

---

## 示例程序

`code/main.py` 覆盖 14 项测试：

| 测试 | 内容 | 状态 |
|------|------|------|
| 1 | OpenAI() 初始化 + 非法参数校验 | PASS |
| 2 | 非流式单轮对话 | PASS |
| 3 | 带 temperature / max_tokens | PASS |
| 4 | 多轮对话（system + user） | PASS |
| 5 | 流式 SSE + iter_lines() | PASS |
| 6 | encode_image() base64 编码 | PASS |
| 7 | max_tokens=2048 非流式 | PASS |
| 8 | max_tokens=2048 流式 | PASS |
| 9 | ~3.5KB base64 图片视觉（非流式） | PASS |
| 10 | base_url 末尾斜杠自动去除 | PASS |
| 11 | 非法参数全覆盖（ValueError / TypeError） | PASS |
| 12 | 响应对象属性完整性 + 视觉模型文字对话 | PASS |
| 13 | audio.speech.create() | SKIP (TODO) |
| 14 | images.generations.create() | SKIP (TODO) |

**预期输出（节选）：**

```
FreakStudio: uopenai async OpenAI client test
WiFi connected, IP: 192.168.x.x
NTP synced via ntp.aliyun.com: 2026-04-16 xx:xx:xx UTC
--- uopenai Test Start ---
[1/14] OpenAI() init + invalid param guard
  [1/14] PASS
[2/14] chat.completions.create() non-stream single turn
  reply: OK
  [2/14] PASS
...
[9/14] ~5KB base64 image non-stream vision
  base64 length: 4688  free RAM after encode: 421184
  reply: This image displays blended gradients of forest green...
  [9/14] PASS
...
--- uopenai Test Done ---
[13/14] audio.speech.create() -- SKIP (TODO: WebSocket streaming TTS)
[14/14] images.generations.create() -- SKIP (TODO: low-res image gen model)
```

---

## 注意事项

1. **依赖 aiohttps**：使用前必须先将 `aiohttps.py`（v1.1.3+）上传到设备根目录，mip 安装时会自动处理依赖。

2. **所有 create() 均为 async**：必须在 `asyncio` 事件循环中调用，不支持同步调用。

3. **不支持 `file=open(...)` 传参**：MicroPython 无标准 `file` 对象，改用 `filepath=` 字符串（`audio.transcriptions` 待实现）。

4. **视觉模型图片大小限制**：`encode_image()` 将整个文件读入内存，建议原图 < 6 KB（base64 后 < 8 KB），总 JSON payload 控制在 12 KB 以内。超出可能导致服务端拒绝或响应超时。

5. **超时设置**：默认 `timeout_ms=30000`（30 秒）。视觉模型响应较慢，建议设置 `timeout_ms=60000`。

6. **thinking 模型兼容**：部分模型（如 doubao-seed）返回 `"content": null`，库已自动处理为空字符串。

7. **待实现接口**：`audio.transcriptions.create()`、`audio.speech.create()`、`images.generations.create()` 当前为 TODO，调用后返回 `None`。嵌入式 TTS/ASR 推荐使用 WebSocket 流式连接实现，参考 `xfyun_tts` / `xfyun_asr`。

---

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

---

## 许可协议

本项目基于 [MIT License](LICENSE) 开源协议发布。
