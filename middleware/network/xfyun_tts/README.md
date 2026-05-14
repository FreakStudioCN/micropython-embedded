# 讯飞语音合成（XfyunTTS）MicroPython 驱动

## 目录

- [简介](#简介)
- [主要功能](#主要功能)
- [运行环境](#运行环境)
- [软件环境](#软件环境)
- [文件结构](#文件结构)
- [文件说明](#文件说明)
- [快速开始](#快速开始)
- [API 参考](#api-参考)
- [注意事项](#注意事项)
- [版本记录](#版本记录)
- [联系方式](#联系方式)
- [许可协议](#许可协议)

## 简介

本驱动为讯飞在线语音合成（TTS）服务的 MicroPython 实现，基于 WebSocket API 将文字实时转换为 PCM 音频。支持动态配置发音人、语速、音量、音高等参数，适用于 ESP32-S3、Raspberry Pi Pico 2W 等支持 WiFi 的 MicroPython 平台。可用于智能语音播报、语音助手、无障碍辅助等场景。

## 主要功能

- ✅ **多发音人支持**：内置小燕、小露、许久等多种发音人，可动态切换
- ✅ **参数动态调节**：支持语速 [0-100]、音量 [0-100]、音高 [0-100] 实时调整
- ✅ **链式调用**：所有 setter 方法支持链式调用，代码简洁优雅
- ✅ **实时播放**：边合成边播放，减少首字节延迟约 1-2 秒
- ✅ **多种编码格式**：支持 raw PCM、MP3、Opus、Speex 等音频编码
- ✅ **采样率可选**：支持 8kHz / 16kHz 采样率切换
- ✅ **背景音控制**：可开启/关闭背景音效果
- ✅ **英文/数字发音**：支持英文按单词/字母发音，数字按数值/字符串发音
- ✅ **文件保存**：支持保存为 PCM 或 WAV 格式（带标准文件头）
- ✅ **调试模式**：内置 debug 开关，方便开发调试

## 运行环境

### 网络要求

- **WiFi 连接**：2.4GHz WiFi，能访问 `tts-api.xfyun.cn`（讯飞 TTS API 服务器）
- **NTP 时间同步**：需通过 `ntptime.settime()` 同步系统时间，用于 API 鉴权签名

### API 凭证要求

需在讯飞开放平台（https://www.xfyun.cn/）注册并创建应用，获取以下凭证：

| 参数名 | 类型 | 说明 |
|--------|------|------|
| app_id | str | 讯飞开放平台 APPID |
| api_key | str | API Key |
| api_secret | str | API Secret（Base64 编码原文） |

### 可选外设

| 外设 | 用途 | 是否必需 |
|------|------|----------|
| I2S 音频模块 | 实时播放合成音频（如 MAX98357A） | 否（可仅保存文件） |

### I2S 引脚说明（以 ESP32-S3 为例）

| 引脚 | 功能描述 |
|------|----------|
| GPIO 14 | I2S SCK（串行时钟） |
| GPIO 15 | I2S WS（字选择/左右声道） |
| GPIO 16 | I2S SD（串行数据） |
| GPIO 17 | 功放 SD（关断控制，高电平开启） |

## 软件环境

- **MicroPython 固件**：v1.23.0 或更高版本
- **驱动版本**：v1.1.0
- **依赖库**：
  - `async_websocketclient`：WebSocket 客户端库（需单独安装）
  - `ntptime`：NTP 时间同步（MicroPython 内置）
  - `network`：WiFi 网络管理（MicroPython 内置）
  - `asyncio`：异步 I/O 框架（MicroPython 内置）

## 文件结构

```
xfyun_tts/
├── code/
│   ├── xfyun_tts.py       # 核心驱动文件
│   └── main.py            # 综合测试示例
├── README.md              # 本说明文档
└── package.json           # 包配置文件（upypi）
```

## 文件说明

| 文件名 | 说明 |
|--------|------|
| `xfyun_tts.py` | 核心驱动类 `XfyunTTS`，实现 WebSocket 通信、鉴权签名、音频流处理 |
| `main.py` | 综合测试示例，包含 8 个测试场景：发音人切换、语速/音量/音高调节、链式调用、采样率切换、背景音、英文/数字发音、实时播放 |

## 快速开始

### 1. 复制文件

将 `xfyun_tts.py` 和 `main.py` 复制到 MicroPython 设备的根目录或项目目录。

### 2. 安装依赖

使用 `mip` 或 `upip` 安装 WebSocket 客户端库：

```python
import mip
mip.install("async_websocketclient")
```

### 3. 配置凭证

编辑 `main.py`，替换以下占位符为你的实际凭证：

```python
# 请替换为你的实际 WiFi SSID
WIFI_SSID     = "your_wifi_ssid"
# 请替换为你的实际 WiFi 密码
WIFI_PASSWORD = "your_wifi_password"

# 请替换为你的实际讯飞 APPID
TTS_APPID  = "your_app_id"
# 请替换为你的实际讯飞 API Key
TTS_KEY    = "your_api_key"
# 请替换为你的实际讯飞 API Secret
TTS_SECRET = "your_api_secret"
```

### 4. 接线（可选，用于实时播放）

如需实时播放音频，按以下方式连接 I2S 音频模块（以 MAX98357A 为例）：

| ESP32-S3 引脚 | MAX98357A 引脚 |
|---------------|----------------|
| GPIO 14 | BCLK |
| GPIO 15 | LRC |
| GPIO 16 | DIN |
| GPIO 17 | SD (可选，功放开关) |
| 3.3V | VIN |
| GND | GND |

### 5. 运行测试

通过 mpremote 或 Thonny 运行完整测试：

```bash
mpremote run main.py
```

或在 REPL 中最小化测试：

```python
import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS
from machine import I2S, Pin

# 连接 WiFi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("your_wifi_ssid", "your_wifi_password")
while not wlan.isconnected():
    time.sleep(1)
print("WiFi connected, IP:", wlan.ifconfig()[0])

# 同步 NTP 时间
ntptime.settime()

# 初始化 TTS 驱动
tts = XfyunTTS(
    app_id="your_app_id",
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# 初始化 I2S 音频输出（可选）
audio_out = I2S(0, sck=Pin(14), ws=Pin(15), sd=Pin(16),
                mode=I2S.TX, bits=16, format=I2S.MONO, rate=16000, ibuf=20000)
amp_sd = Pin(17, Pin.OUT)

# 合成并播放
async def test():
    await tts.synthesize_and_play("你好，这是语音合成测试", audio_out, amp_sd, rate=16000)

asyncio.run(test())
```

## API 参考

### XfyunTTS 类

#### 构造函数

```python
XfyunTTS(app_id, api_key, api_secret, vcn="x4_xiaoyan", aue="raw", 
         auf="audio/L16;rate=8000", speed=50, volume=50, pitch=50, 
         debug=False, **kwargs)
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| app_id | str | 必填 | 讯飞开放平台 APPID |
| api_key | str | 必填 | API Key |
| api_secret | str | 必填 | API Secret（Base64 编码） |
| vcn | str | "x4_xiaoyan" | 发音人（见常量表） |
| aue | str | "raw" | 音频编码（见常量表） |
| auf | str | "audio/L16;rate=8000" | 音频格式 |
| speed | int | 50 | 语速 [0-100] |
| volume | int | 50 | 音量 [0-100] |
| pitch | int | 50 | 音高 [0-100] |
| debug | bool | False | 调试日志开关 |

**高级参数（kwargs）**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| bgs | int | 0 | 背景音 0/1 |
| tte | str | "UTF8" | 文本编码 |
| reg | str | "0" | 英文发音方式 [0-2] |
| rdn | str | "0" | 数字发音方式 [0-3] |
| sfl | int | None | 流式返回 mp3（配合 aue=lame） |

#### 类常量

**发音人常量**：

| 常量 | 值 | 说明 |
|------|-----|------|
| VOICE_XIAOYAN | "x4_xiaoyan" | 讯飞小燕 |
| VOICE_YEZI | "x4_yezi" | 讯飞小露 |
| VOICE_JIUXU | "aisjiuxu" | 讯飞许久 |
| VOICE_JINGER | "aisjinger" | 讯飞小婧 |
| VOICE_BABYXU | "aisbabyxu" | 讯飞许小宝 |

**音频编码常量**：

| 常量 | 值 | 说明 |
|------|-----|------|
| AUE_RAW | "raw" | 原始 PCM |
| AUE_LAME | "lame" | MP3 |
| AUE_OPUS | "opus" | Opus 8k |
| AUE_OPUS_WB | "opus-wb" | Opus 16k |
| AUE_SPEEX | "speex;7" | 讯飞定制 Speex 8k |
| AUE_SPEEX_WB | "speex-wb;7" | 讯飞定制 Speex 16k |

**采样率常量**：

| 常量 | 值 | 说明 |
|------|-----|------|
| AUF_8K | "audio/L16;rate=8000" | 8kHz 采样率 |
| AUF_16K | "audio/L16;rate=16000" | 16kHz 采样率 |

#### 公共方法

##### set_voice(vcn) -> XfyunTTS

设置发音人，下次合成时生效。

**参数**：
- `vcn` (str): 发音人参数值，如 "x4_xiaoyan"

**返回**：self（支持链式调用）

##### set_speed(speed) -> XfyunTTS

设置语速 [0-100]，下次合成时生效。

**参数**：
- `speed` (int): 语速值，范围 [0-100]

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数超出范围时抛出

##### set_volume(volume) -> XfyunTTS

设置音量 [0-100]，下次合成时生效。

**参数**：
- `volume` (int): 音量值，范围 [0-100]

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数超出范围时抛出

##### set_pitch(pitch) -> XfyunTTS

设置音高 [0-100]，下次合成时生效。

**参数**：
- `pitch` (int): 音高值，范围 [0-100]

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数超出范围时抛出

##### set_background_sound(enabled) -> XfyunTTS

设置背景音，下次合成时生效。

**参数**：
- `enabled` (bool): True 开启背景音，False 关闭背景音

**返回**：self（支持链式调用）

##### set_audio_encoding(aue, sfl=None) -> XfyunTTS

设置音频编码格式，下次合成时生效。

**参数**：
- `aue` (str): 音频编码，如 "raw"、"lame"、"opus" 等
- `sfl` (int, optional): 流式返回 mp3，仅在 aue="lame" 时有效

**返回**：self（支持链式调用）

##### set_sample_rate(rate) -> XfyunTTS

设置采样率，下次合成时生效。

**参数**：
- `rate` (int): 采样率，支持 8000 或 16000

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数不是 8000 或 16000 时抛出

##### set_text_encoding(tte) -> XfyunTTS

设置文本编码格式，下次合成时生效。

**参数**：
- `tte` (str): 文本编码，如 "UTF8"、"GBK"、"GB2312" 等

**返回**：self（支持链式调用）

##### set_english_pronunciation(reg) -> XfyunTTS

设置英文发音方式，下次合成时生效。

**参数**：
- `reg` (str): 英文发音方式
  - "0": 自动判断，不确定按单词发音（默认）
  - "1": 所有英文按字母发音
  - "2": 自动判断，不确定按字母发音

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数不是 "0"、"1" 或 "2" 时抛出

##### set_digit_pronunciation(rdn) -> XfyunTTS

设置数字发音方式，下次合成时生效。

**参数**：
- `rdn` (str): 数字发音方式
  - "0": 自动判断（默认）
  - "1": 完全数值
  - "2": 完全字符串
  - "3": 字符串优先

**返回**：self（支持链式调用）

**异常**：
- `ValueError`: 参数不是 "0"、"1"、"2" 或 "3" 时抛出

##### async synthesize(text, filepath=None)

连接讯飞 TTS 服务，发送合成请求，逐帧接收并流式写入文件（或内存）。

**参数**：
- `text` (str): 待合成的文字内容
- `filepath` (str, optional): 目标文件路径。提供时每帧立即写入文件，内存中峰值仅为单帧大小（约 1~4 KB）；为 None 时在内存中积累并返回 bytes（仅适合极短文本）

**返回**：
- `int`: filepath 不为 None 时，返回写入的总字节数；失败返回 0
- `bytes`: filepath 为 None 时，返回完整 PCM 字节串；失败返回 b""

**注意**：
- 调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间
- 服务端 status==2 表示最后一帧，收到后主动关闭连接
- 若 filepath 以 `.wav` 结尾，自动添加 WAV 文件头

##### async synthesize_and_play(text, audio_out, amp_sd, rate=16000)

连接讯飞 TTS，收到每个音频 chunk 立即写入 I2S，无需等待全部合成完成。相比 synthesize()+play_pcm() 可减少约 1~2 秒首字节延迟。

**参数**：
- `text` (str): 待合成文字
- `audio_out` (I2S): 已初始化的 I2S TX 实例
- `amp_sd` (Pin): 功放 SD 引脚，合成前置高，播完后置低
- `rate` (int): 采样率，默认 16000，用于计算尾部等待时长

**返回**：
- `int`: 实际写入 I2S 的总字节数；失败返回 0

**注意**：
- 实时播放模式，边合成边播放
- 需要硬件支持 I2S 音频输出
- 功放 SD 引脚自动控制开关

##### deinit()

释放资源，关闭 WebSocket 连接。

**注意**：
- 调用后驱动实例不可再使用
- 建议在程序退出前调用

## 注意事项

| 类别 | 说明 |
|------|------|
| **网络要求** | 需稳定的 WiFi 连接，能访问讯飞 TTS API 服务器（tts-api.xfyun.cn） |
| **时间同步** | 必须通过 ntptime.settime() 同步系统时间，否则鉴权签名失败 |
| **API 限额** | 讯飞免费版有调用次数限制，超出需购买套餐 |
| **音频格式** | 默认输出 8kHz 16bit 单声道 PCM，可通过 set_sample_rate() 切换为 16kHz |
| **内存限制** | 长文本合成建议使用 filepath 参数流式写入文件，避免内存溢出 |
| **I2S 兼容性** | 实时播放功能需硬件支持 I2S，ESP32-S3 / Pico 2W 已验证可用 |
| **异步调用** | synthesize() 和 synthesize_and_play() 为异步方法，需在 async 函数中调用 |
| **链式调用** | 所有 setter 方法返回 self，支持链式调用，如 `tts.set_speed(60).set_volume(80)` |

## 版本记录

| 版本号 | 日期 | 作者 | 修改说明 |
|--------|------|------|----------|
| v1.1.0 | 2026-04-12 | leeqingsui | 新增动态参数配置、链式调用、实时播放、多发音人支持 |
| v1.0.0 | 2026-04-10 | leeqingsui | 初始版本，基础 TTS 功能 |

## 联系方式

- **作者**：leeqingsui
- **GitHub**：https://github.com/FreakStudioCN/MicroPython_Skills

## 许可协议

MIT License

Copyright (c) 2026 leeqingsui

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
