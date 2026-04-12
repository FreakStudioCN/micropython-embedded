# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  : leeqingsui
# @File    : main.py
# @Description : iFlytek TTS usage example for MicroPython on Raspberry Pi Pico 2W
# @License : MIT

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS

# ======================================== 全局变量 ============================================

WIFI_SSID = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

APPID = "your_appid"
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"

OUTPUT_FILE = "output.pcm"
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
            print("NTP synced via {}: {}-{:02d}-{:02d} {:02d}:{:02d}:{:02d} UTC".format(host, t[0], t[1], t[2], t[3], t[4], t[5]))
            return
        except Exception as e:
            print("NTP failed ({}):".format(host), e)
    print("NTP sync unavailable; signature timestamp may be rejected.")


async def run_tts(text):
    """
    调用 XfyunTTS 流式合成指定文本，直接将 PCM 数据写入本地文件。

    Args:
        text (str): 待合成的文本内容。

    ==========================================

    Synthesize the given text using XfyunTTS in streaming mode,
    writing PCM data directly to a local file.

    Args:
        text (str): Text to synthesize.
    """
    print("Synthesizing:", text)
    total = await tts.synthesize(text, filepath=OUTPUT_FILE)

    if total:
        print("Saved", total, "bytes ->", OUTPUT_FILE)
    else:
        print("Synthesis failed: no audio data received.")


async def run_tts_wav(text):
    """
    调用 XfyunTTS 流式合成指定文本，直接将带 WAV 头的音频写入本地文件。
    WAV 文件可在 PC 上直接用任意播放器打开，无需指定格式参数。

    Args:
        text (str): 待合成的文本内容。

    ==========================================

    Synthesize the given text using XfyunTTS in streaming mode,
    writing a WAV file (with header) directly to local storage.
    The WAV file can be opened on PC by any audio player without extra parameters.

    Args:
        text (str): Text to synthesize.
    """
    print("Synthesizing (WAV):", text)
    total = await tts.synthesize(text, filepath=OUTPUT_WAV)

    if total:
        print("Saved", total, "bytes PCM +44 bytes header ->", OUTPUT_WAV)
    else:
        print("Synthesis failed: no audio data received.")


# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

tts = XfyunTTS(
    app_id=APPID,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    time.sleep(3)
    print("--- FreakStudio iFlytek TTS Demo ---")

    if not connect_wifi():
        print("Aborting: WiFi unavailable.")
    else:
        sync_ntp()

        # Demo 1: raw PCM output
        asyncio.run(run_tts("Hello, I am Xiaozhi. Nice to meet you."))

        # Demo 2: WAV output — open output.wav directly on PC to verify
        asyncio.run(run_tts_wav("Hi there, this is a WAV format test from Pico 2W."))
