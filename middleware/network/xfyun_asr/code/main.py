# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/14
# @Author  : leeqingsui
# @File    : main.py
# @Description : iFlytek TTS + ASR demo for MicroPython on Raspberry Pi Pico 2W

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS
from xfyun_asr import XfyunASR

# ======================================== 全局变量 ============================================

WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

# TTS 凭据（需在讯飞控制台开通语音合成服务）
TTS_APPID      = "your_tts_appid"
TTS_API_KEY    = "your_tts_api_key"
TTS_API_SECRET = "your_tts_api_secret"

# ASR 凭据（需在讯飞控制台开通中英识别大模型服务）
ASR_APPID      = "your_asr_appid"
ASR_API_KEY    = "your_asr_api_key"
ASR_API_SECRET = "your_asr_api_secret"

OUTPUT_PCM = "output.pcm"
OUTPUT_WAV = "output.wav"

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
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print("Connecting...", timeout, "s remaining")

        if wlan.isconnected():
            ip_info = wlan.ifconfig()
            print("WiFi connected")
            print("IP:", ip_info[0])
            print("Gateway:", ip_info[2])
        else:
            print("WiFi connection failed")
            return None
    else:
        print("WiFi already connected")

    return wlan


def sync_ntp():
    """
    通过 NTP 同步系统时间，为讯飞 API 鉴权签名提供准确时间戳。
    依次尝试多个 NTP 服务器，全部失败时打印警告但不中断流程。

    ==========================================

    Sync system time via NTP for iFlytek API authentication signature.
    Tries multiple NTP servers in order; prints a warning if all fail.
    """
    servers = ("ntp.aliyun.com", "ntp.tencent.com", "pool.ntp.org")
    for host in servers:
        try:
            ntptime.host = host
            ntptime.settime()
            t = time.gmtime()
            print("NTP synced via {}: {}-{:02d}-{:02d} {:02d}:{:02d}:{:02d} UTC".format(
                host, t[0], t[1], t[2], t[3], t[4], t[5]))
            return
        except Exception as e:
            print("NTP failed ({}):".format(host), e)
    print("NTP sync unavailable; signature timestamp may be rejected.")


async def run_tts(text):
    """
    调用 XfyunTTS 流式合成指定文本，将 PCM 数据写入 output.pcm。

    Args:
        text (str): 待合成的文本内容。

    ==========================================

    Synthesize text via XfyunTTS and write raw PCM to output.pcm.

    Args:
        text (str): Text to synthesize.
    """
    print("Synthesizing:", text)
    total = await tts.synthesize(text, filepath=OUTPUT_PCM)

    if total:
        print("Saved", total, "bytes ->", OUTPUT_PCM)
    else:
        print("Synthesis failed: no audio data received.")


async def run_tts_wav(text):
    """
    调用 XfyunTTS 流式合成指定文本，将带 WAV 头的音频写入 output.wav。

    Args:
        text (str): 待合成的文本内容。

    ==========================================

    Synthesize text via XfyunTTS and write WAV file to output.wav.

    Args:
        text (str): Text to synthesize.
    """
    print("Synthesizing (WAV):", text)
    total = await tts.synthesize(text, filepath=OUTPUT_WAV)

    if total:
        print("Saved", total, "bytes PCM +44 bytes header ->", OUTPUT_WAV)
    else:
        print("Synthesis failed: no audio data received.")


async def run_asr(filepath):
    """
    调用 XfyunASR 识别指定 PCM 文件，打印识别结果。

    Args:
        filepath (str): 待识别的 PCM 文件路径。

    ==========================================

    Recognize a PCM file via XfyunASR and print the result.

    Args:
        filepath (str): Path to the PCM file to recognize.
    """
    print("Recognizing:", filepath)
    text = await asr.recognize(filepath)

    if text:
        print("ASR result:", text)
    else:
        print("Recognition failed: no text returned.")

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

time.sleep(3)
print("FreakStudio: iFlytek TTS + ASR Demo")

tts = XfyunTTS(
    app_id     = TTS_APPID,
    api_key    = TTS_API_KEY,
    api_secret = TTS_API_SECRET,
)

# ASR 采样率须与 TTS 输出一致（TTS 默认 auf=audio/L16;rate=8000 → 8000 Hz）
asr = XfyunASR(
    app_id      = ASR_APPID,
    api_key     = ASR_API_KEY,
    api_secret  = ASR_API_SECRET,
    sample_rate = 8000,
)

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    if not connect_wifi():
        print("Aborting: WiFi unavailable.")
    else:
        sync_ntp()

        # Demo 1: TTS 合成中英混合文本 → output.pcm
        asyncio.run(run_tts("大家好一块吃饭吧hello"))

        # Demo 2: ASR 识别 output.pcm → 打印文字
        asyncio.run(run_asr(OUTPUT_PCM))

        # Demo 3: TTS 合成 → output.wav（可在 PC 上直接播放验证）
        asyncio.run(run_tts_wav("Hi there, this is a WAV format test from Pico 2W."))
