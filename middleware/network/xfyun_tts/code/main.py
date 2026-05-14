# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  : leeqingsui
# @File    : main.py
# @Description : iFlytek TTS comprehensive test for MicroPython (ESP32-S3 / Pico 2W)
# @License : MIT

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import time
import ntptime
from xfyun_tts import XfyunTTS
from machine import I2S, Pin

# ======================================== 全局变量 ============================================

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

# I2S 扬声器引脚配置（ESP32-S3）
spk_sck = 14
spk_ws  = 15
spk_sd  = 16
amp_sd_pin  = 17

# 输出文件路径
output_pcm = "test_output.pcm"
output_wav = "test_output.wav"

# 全局 I2S 和功放对象
audio_out = None
amp_sd = None

# ======================================== 功能函数 ============================================

def connect_wifi():
    """
    连接 WiFi 并返回网络对象。

    Returns:
        network.WLAN: 已连接的 WLAN 对象；连接失败时返回 None。
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


async def run_tts_and_play(text):
    """
    调用 XfyunTTS 边合成边播放。

    Args:
        text (str): 待合成的文本内容。
    """
    print("\n[Test] Synthesizing and playing:", text)

    try:
        # 调用实时播放接口
        total = await tts.synthesize_and_play(text, audio_out, amp_sd, rate=16000)

        if total:
            print("[Success] Played", total, "bytes")
        else:
            print("[Failed] Synthesis failed: no audio data received.")
        return total
    except Exception as e:
        print("[Error] Playback failed:", e)
        return 0


async def run_tts(text):
    """
    调用 XfyunTTS 流式合成指定文本，直接将 PCM 数据写入本地文件。

    Args:
        text (str): 待合成的文本内容。
    """
    print("\n[Test] Synthesizing:", text)
    # 合成并保存为 PCM 文件
    total = await tts.synthesize(text, filepath=output_pcm)

    if total:
        print("[Success] Saved", total, "bytes ->", output_pcm)
    else:
        print("[Failed] Synthesis failed: no audio data received.")
    return total


async def run_tts_wav(text):
    """
    调用 XfyunTTS 流式合成指定文本，直接将带 WAV 头的音频写入本地文件。
    WAV 文件可在 PC 上直接用任意播放器打开，无需指定格式参数。

    Args:
        text (str): 待合成的文本内容。
    """
    print("\n[Test] Synthesizing (WAV):", text)
    # 合成并保存为 WAV 文件
    total = await tts.synthesize(text, filepath=output_wav)

    if total:
        print("[Success] Saved", total, "bytes PCM +44 bytes header ->", output_wav)
    else:
        print("[Failed] Synthesis failed: no audio data received.")
    return total




async def test_voice_switching():
    """
    测试不同发音人切换。
    """
    print("\n" + "="*60)
    print("TEST 1: Voice Switching (发音人切换)")
    print("="*60)

    voices = [
        (XfyunTTS.VOICE_XIAOYAN, "我是讯飞小燕"),
        (XfyunTTS.VOICE_YEZI, "我是讯飞小露"),
        (XfyunTTS.VOICE_JIUXU, "我是讯飞许久"),
    ]

    for voice, text in voices:
        # 设置发音人
        tts.set_voice(voice)
        print("\n[Voice]", voice)
        await run_tts_and_play(text)
        await asyncio.sleep(1)


async def test_speed_volume_pitch():
    """
    测试语速、音量、音高调整。
    """
    print("\n" + "="*60)
    print("TEST 2: Speed, Volume, Pitch (语速、音量、音高)")
    print("="*60)

    # 恢复默认发音人
    tts.set_voice(XfyunTTS.VOICE_XIAOYAN)

    # 测试语速
    print("\n[Speed Test]")
    tts.set_speed(30)
    await run_tts_and_play("这是慢速语音测试")
    await asyncio.sleep(1)

    tts.set_speed(80)
    await run_tts_and_play("这是快速语音测试")
    await asyncio.sleep(1)

    # 测试音量
    print("\n[Volume Test]")
    tts.set_speed(50).set_volume(30)
    await run_tts_and_play("这是低音量测试")
    await asyncio.sleep(1)

    tts.set_volume(90)
    await run_tts_and_play("这是高音量测试")
    await asyncio.sleep(1)

    # 测试音高
    print("\n[Pitch Test]")
    tts.set_volume(50).set_pitch(30)
    await run_tts_and_play("这是低音高测试")
    await asyncio.sleep(1)

    tts.set_pitch(70)
    await run_tts_and_play("这是高音高测试")
    await asyncio.sleep(1)


async def test_chaining():
    """
    测试链式调用。
    """
    print("\n" + "="*60)
    print("TEST 3: Method Chaining (链式调用)")
    print("="*60)

    # 链式设置多个参数并播放
    print("\n[Test] Synthesizing and playing: 链式调用测试成功")
    total = await (tts.set_voice(XfyunTTS.VOICE_YEZI)
                      .set_speed(60)
                      .set_volume(70)
                      .set_pitch(55)
                      .synthesize_and_play("链式调用测试成功", audio_out, amp_sd, rate=16000))
    if total:
        print("[Success] Played", total, "bytes")
    await asyncio.sleep(1)


async def test_sample_rate():
    """
    测试不同采样率。
    """
    print("\n" + "="*60)
    print("TEST 4: Sample Rate (采样率)")
    print("="*60)

    # 8kHz 采样率测试
    tts.set_sample_rate(8000).set_speed(50).set_volume(50).set_pitch(50)
    print("\n[Sample Rate] 8kHz")
    await run_tts_and_play("这是8千赫兹采样率测试")
    await asyncio.sleep(1)

    # 16kHz 采样率测试
    tts.set_sample_rate(16000)
    print("\n[Sample Rate] 16kHz")
    await run_tts_and_play("这是16千赫兹采样率测试")
    await asyncio.sleep(1)


async def test_background_sound():
    """
    测试背景音。
    """
    print("\n" + "="*60)
    print("TEST 5: Background Sound (背景音)")
    print("="*60)

    # 开启背景音
    tts.set_background_sound(True)
    print("\n[Background Sound] Enabled")
    await run_tts_and_play("这是带背景音的语音")
    await asyncio.sleep(1)

    # 关闭背景音
    tts.set_background_sound(False)
    print("\n[Background Sound] Disabled")
    await run_tts_and_play("这是无背景音的语音")
    await asyncio.sleep(1)


async def test_english_pronunciation():
    """
    测试英文发音方式。
    """
    print("\n" + "="*60)
    print("TEST 6: English Pronunciation (英文发音)")
    print("="*60)

    test_text = "Hello World, this is a test"

    # 模式 0: 自动判断，按单词发音
    tts.set_english_pronunciation("0")
    print("\n[English Mode] 0 - Auto (word)")
    await run_tts_and_play(test_text)
    await asyncio.sleep(1)

    # 模式 1: 按字母发音
    tts.set_english_pronunciation("1")
    print("\n[English Mode] 1 - Letter")
    await run_tts_and_play(test_text)
    await asyncio.sleep(1)


async def test_digit_pronunciation():
    """
    测试数字发音方式。
    """
    print("\n" + "="*60)
    print("TEST 7: Digit Pronunciation (数字发音)")
    print("="*60)

    test_text = "今天是2026年5月15日"

    # 恢复英文发音默认值
    tts.set_english_pronunciation("0")

    # 模式 0: 自动判断
    tts.set_digit_pronunciation("0")
    print("\n[Digit Mode] 0 - Auto")
    await run_tts_and_play(test_text)
    await asyncio.sleep(1)

    # 模式 1: 完全数值
    tts.set_digit_pronunciation("1")
    print("\n[Digit Mode] 1 - Numeric")
    await run_tts_and_play(test_text)
    await asyncio.sleep(1)

    # 模式 2: 完全字符串
    tts.set_digit_pronunciation("2")
    print("\n[Digit Mode] 2 - String")
    await run_tts_and_play(test_text)
    await asyncio.sleep(1)


async def test_realtime_playback():
    """
    测试实时播放（边合成边播放）。
    需要硬件支持 I2S。
    """
    print("\n" + "="*60)
    print("TEST 8: Real-time Playback (实时播放)")
    print("="*60)

    # 恢复默认设置
    tts.set_voice(XfyunTTS.VOICE_XIAOYAN)
    tts.set_speed(50).set_volume(70).set_pitch(50)
    tts.set_digit_pronunciation("0")
    tts.set_sample_rate(16000)
    tts.set_english_pronunciation("0")

    print("\n[Test] Real-time playback with default settings...")
    await run_tts_and_play("实时播放测试，边合成边播放，减少延迟")


async def run_all_tests():
    """
    运行所有测试用例。
    """
    global audio_out, amp_sd

    print("\n" + "="*60)
    print("XfyunTTS v1.1.0 Comprehensive Test Suite")
    print("="*60)

    # 初始化 I2S 音频输出
    try:
        print("\n[I2S] Initializing audio output...")
        audio_out = I2S(
            0,
            sck=Pin(spk_sck),
            ws=Pin(spk_ws),
            sd=Pin(spk_sd),
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=16000,
            ibuf=20000
        )
        amp_sd = Pin(amp_sd_pin, Pin.OUT)
        print("[I2S] Audio output initialized successfully")
    except Exception as e:
        print("[Error] I2S initialization failed:", e)
        print("[Info] Tests will run without audio playback")
        return

    # 执行所有测试场景
    await test_voice_switching()
    await test_speed_volume_pitch()
    await test_chaining()
    await test_sample_rate()
    await test_background_sound()
    await test_english_pronunciation()
    await test_digit_pronunciation()
    await test_realtime_playback()

    # 清理 I2S 资源
    try:
        audio_out.deinit()
        print("\n[I2S] Audio output deinitialized")
    except Exception:
        pass

    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

time.sleep(3)
print("FreakStudio: Testing XfyunTTS v1.1.0 driver...")

# 实例化 TTS 驱动
tts = XfyunTTS(
    app_id     = TTS_APPID,
    api_key    = TTS_KEY,
    api_secret = TTS_SECRET,
)

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("XfyunTTS v1.1.0 Comprehensive Test")
    print("="*60)

    # 连接 WiFi
    if not connect_wifi():
        print("\n[Error] Aborting: WiFi unavailable.")
    else:
        # 同步 NTP 时间
        sync_ntp()

        print("\n[Info] Starting comprehensive test suite...")
        print("[Info] This will test all new features in v1.1.0")

        try:
            # 运行所有测试
            asyncio.run(run_all_tests())
        except KeyboardInterrupt:
            print("\n[Info] Test interrupted by user")
        except OSError as e:
            print("\n[Error] Hardware communication error:", e)
        except Exception as e:
            print("\n[Error] Test failed:", e)
        finally:
            # 清理资源
            print("\n[Info] Cleaning up resources...")
            try:
                tts.deinit()
            except Exception:
                pass
            print("[Info] Test session completed")

