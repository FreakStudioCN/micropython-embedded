# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/16
# @Author  : leeqingsui
# @File    : main.py
# @Description : uopenai async OpenAI client test for MicroPython on Raspberry Pi Pico 2W

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import time
import json
import ntptime
import os
from uopenai import OpenAI

# ======================================== 全局变量 ============================================

WIFI_SSID = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

# OpenAI 兼容接口配置（替换为你的实际 key 和 base_url）
API_KEY = "your_api_key"
BASE_URL = "https://api.openai.com/v1"
MODEL_CHAT = "your_chat_model"
MODEL_VISION = "your_vision_model"

# 测试用小图片文件（需提前上传到设备，建议 < 50 KB）
TEST_IMAGE_FILE = "test_image.jpg"

# 测试用 ~5KB 图片（base64 视觉测试用，建议 < 6 KB）
TEST_20KB_IMAGE = "test_5kb.jpg"

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
        print("Connecting to WiFi: {}".format(WIFI_SSID))
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print("Connecting... {}s remaining".format(timeout))

        if wlan.isconnected():
            print("WiFi connected, IP: {}".format(wlan.ifconfig()[0]))
        else:
            print("WiFi connection failed")
            return None
    else:
        print("WiFi already connected")

    return wlan


def sync_ntp():
    """
    通过 NTP 同步系统时间。

    ==========================================

    Sync system time via NTP.
    """
    for host in ("ntp.aliyun.com", "ntp.tencent.com", "pool.ntp.org"):
        try:
            ntptime.host = host
            ntptime.settime()
            t = time.gmtime()
            print("NTP synced via {}: {}-{:02d}-{:02d} {:02d}:{:02d}:{:02d} UTC".format(host, t[0], t[1], t[2], t[3], t[4], t[5]))
            return
        except Exception as e:
            print("NTP failed ({}): {}".format(host, e))
    print("NTP sync unavailable.")


def prepare_test_image():
    """
    生成一个极小的合法 JPEG 文件（1x1 白色像素），用于测试 encode_image()。
    如果设备上已有 test_image.jpg，跳过生成。

    ==========================================

    Generate a minimal valid JPEG (1x1 white pixel) for encode_image() testing.
    Skipped if file already exists.
    """
    try:
        os.stat(TEST_IMAGE_FILE)
        print("  image file already exists, skip generation")
    except OSError:
        # 最小合法 JPEG（1x1 白色像素），固定字节序列
        minimal_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1b"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
            b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br'
            b"\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJ"
            b"STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd4P\x00\x00\x00\xff\xd9"
        )
        with open(TEST_IMAGE_FILE, "wb") as f:
            f.write(minimal_jpeg)
        print("  generated minimal JPEG: {} ({} bytes)".format(TEST_IMAGE_FILE, len(minimal_jpeg)))


async def test_uopenai():
    """
    uopenai 库全量测试。

    Test 1:  OpenAI() 初始化 + 非法参数校验
    Test 2:  chat.completions.create() 非流式，单轮对话
    Test 3:  chat.completions.create() 非流式，带 temperature/max_tokens kwargs
    Test 4:  chat.completions.create() 非流式，多轮对话（system + user）
    Test 5:  chat.completions.create() 流式（stream=True），iter_lines() 读 SSE
    Test 6:  encode_image() 静态方法，base64 编码
    Test 7:  max_tokens=2048 非流式文字
    Test 8:  max_tokens=2048 流式文字
    Test 9:  ~6KB base64 图片非流式视觉
    Test 10: base_url 末尾斜杠自动去除
    Test 11: 非法参数全覆盖（ValueError / TypeError）
    Test 12: 响应对象属性完整性 + doubao 文字对话
    Test 13: audio.speech.create() — SKIP (TODO)
    Test 14: images.generations.create() — SKIP (TODO)

    ==========================================

    Full test suite for uopenai library.
    """
    # 1. 连接 WiFi
    if not connect_wifi():
        return

    # 2. 同步 NTP
    sync_ntp()

    print("--- uopenai Test Start ---")

    # ------------------------------------------------------------------ #
    # Test 1: 初始化 + 非法参数校验
    # ------------------------------------------------------------------ #
    print("[1/14] OpenAI() init + invalid param guard")
    try:
        # 正常初始化
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        ok = hasattr(client, "chat") and hasattr(client, "audio")

        # 空 api_key 应抛 ValueError
        caught = False
        try:
            OpenAI(api_key="")
        except ValueError:
            caught = True

        print("  [1/14] PASS" if ok and caught else "  [1/14] FAIL")
    except Exception as e:
        print("  [1/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 2: 非流式单轮对话
    # ------------------------------------------------------------------ #
    print("[2/14] chat.completions.create() non-stream single turn")
    try:
        resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        )
        content = resp.choices[0].message.content
        print("  reply:", content)
        print("  [2/14] PASS" if len(content) > 0 else "  [2/14] FAIL (empty content)")
    except Exception as e:
        print("  [2/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 3: 非流式，带 kwargs（temperature / max_tokens）
    # ------------------------------------------------------------------ #
    print("[3/14] chat.completions.create() with temperature + max_tokens")
    try:
        resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "user", "content": "Say hello in one word."}],
            temperature=0.0,
            max_tokens=10,
        )
        content = resp.choices[0].message.content
        print("  reply:", content)
        print("  [3/14] PASS" if len(content) > 0 else "  [3/14] FAIL")
    except Exception as e:
        print("  [3/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 4: 非流式，多轮对话（system + user）
    # ------------------------------------------------------------------ #
    print("[4/14] chat.completions.create() multi-turn (system + user)")
    try:
        resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Reply concisely."},
                {"role": "user", "content": "What is 1+1?"},
            ],
        )
        content = resp.choices[0].message.content
        print("  reply:", content)
        # 回答应包含 "2"
        print("  [4/14] PASS" if "2" in content else "  [4/14] FAIL (no '2' in reply)")
    except Exception as e:
        print("  [4/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 5: 流式对话（stream=True），iter_lines() 读 SSE
    # ------------------------------------------------------------------ #
    print("[5/14] chat.completions.create() stream=True + iter_lines()")
    try:
        stream_resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "user", "content": "Count from 1 to 3, one number per line."}],
            stream=True,
            max_tokens=50,
        )
        chunks_received = 0
        full_text = ""
        async for line in stream_resp.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line == b"data: [DONE]":
                break
            # SSE 格式：b"data: {...}"
            if line.startswith(b"data: "):
                raw = line[6:]
                try:
                    obj = json.loads(raw)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    piece = delta.get("content", "")
                    if piece:
                        full_text += piece
                        chunks_received += 1
                except Exception:
                    pass
        print("  chunks received:", chunks_received)
        print("  assembled text:", full_text)
        print("  [5/14] PASS" if chunks_received > 0 else "  [5/14] FAIL (no chunks)")
    except Exception as e:
        print("  [5/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 6: encode_image() 静态方法
    # ------------------------------------------------------------------ #
    print("[6/14] OpenAI.encode_image()")
    try:
        prepare_test_image()
        b64 = OpenAI.encode_image(TEST_IMAGE_FILE)
        print("  base64 length:", len(b64))
        # base64 字符只含 A-Z a-z 0-9 + / =
        valid = all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in b64)
        print("  [6/14] PASS" if len(b64) > 0 and valid else "  [6/14] FAIL (invalid base64)")
    except Exception as e:
        print("  [6/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 7: max_tokens=2048 非流式文字
    # ------------------------------------------------------------------ #
    print("[7/14] max_tokens=2048 non-stream text")
    try:
        resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "user", "content": "Write a short poem about the ocean in 3 lines."}],
            max_tokens=2048,
        )
        content = resp.choices[0].message.content
        finish = resp.choices[0].finish_reason
        print("  reply:", content)
        print("  finish_reason:", finish)
        print("  [7/14] PASS" if len(content) > 0 and finish == "stop" else "  [7/14] FAIL")
    except Exception as e:
        print("  [7/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 12: max_tokens=2048 流式文字
    # ------------------------------------------------------------------ #
    print("[8/14] max_tokens=2048 stream text")
    try:
        stream_resp = await client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "user", "content": "Write a short poem about the ocean in 3 lines."}],
            stream=True,
            max_tokens=2048,
        )
        full_text = ""
        async for line in stream_resp.iter_lines():
            line = line.strip()
            if not line or line == b"data: [DONE]":
                continue
            if line.startswith(b"data: "):
                try:
                    delta = json.loads(line[6:]).get("choices", [{}])[0].get("delta", {})
                    full_text += delta.get("content", "")
                except Exception:
                    pass
        print("  assembled:", full_text)
        print("  [8/14] PASS" if len(full_text) > 0 else "  [8/14] FAIL")
    except Exception as e:
        print("  [8/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 9: ~5KB base64 图片非流式视觉
    # ------------------------------------------------------------------ #
    print("[9/14] ~5KB base64 image non-stream vision")
    try:
        import gc

        gc.collect()
        print("  free RAM before encode:", gc.mem_free())
        b64 = OpenAI.encode_image("test_4kb.jpg")
        gc.collect()
        print("  base64 length:", len(b64), "free RAM after encode:", gc.mem_free())
        resp = await client.chat.completions.create(
            model=MODEL_VISION,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                        {"type": "text", "text": "What colors do you see? Reply in one sentence."},
                    ],
                }
            ],
            max_tokens=100,
            timeout_ms=60000,
        )
        gc.collect()
        print("  free RAM after request:", gc.mem_free())
        content = resp.choices[0].message.content
        print("  reply:", content)
        print("  [9/14] PASS" if len(content) > 0 else "  [9/14] FAIL (empty reply)")
    except Exception as e:
        print("  [9/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 12: base_url 末尾斜杠自动去除
    # ------------------------------------------------------------------ #
    print("[10/14] base_url trailing slash strip")
    try:
        c2 = OpenAI(api_key="dummy", base_url="https://api.openai.com/v1/")
        ok = not c2._base_url.endswith("/")
        print("  _base_url:", c2._base_url)
        print("  [10/14] PASS" if ok else "  [10/14] FAIL (slash not stripped)")
    except Exception as e:
        print("  [10/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 11: 非法参数校验（api_key / model / messages / filepath）
    # ------------------------------------------------------------------ #
    print("[11/14] invalid param guards (ValueError / TypeError)")
    try:
        results = []

        # api_key 为 None
        try:
            OpenAI(api_key=None)
            results.append(False)
        except ValueError:
            results.append(True)

        # model 为空
        try:
            await client.chat.completions.create(model="", messages=[{"role": "user", "content": "hi"}])
            results.append(False)
        except ValueError:
            results.append(True)

        # messages 为空列表
        try:
            await client.chat.completions.create(model=MODEL_CHAT, messages=[])
            results.append(False)
        except ValueError:
            results.append(True)

        # transcriptions filepath 为空
        try:
            await client.audio.transcriptions.create(model="whisper-1", filepath="")
            results.append(False)
        except ValueError:
            results.append(True)

        # encode_image filepath 为 None
        try:
            OpenAI.encode_image(None)
            results.append(False)
        except ValueError:
            results.append(True)

        all_ok = all(results)
        print("  guard results:", results)
        print("  [11/14] PASS" if all_ok else "  [11/14] FAIL")
    except Exception as e:
        print("  [11/14] ERROR:", e)

    # ------------------------------------------------------------------ #
    # Test 12: 响应对象属性完整性 + doubao vision model 文字对话
    # ------------------------------------------------------------------ #
    print("[12/14] response attributes check + vision model text chat")
    try:
        resp = await client.chat.completions.create(
            model=MODEL_VISION,
            messages=[{"role": "user", "content": "Say yes."}],
        )
        has_id = isinstance(resp.id, str)
        has_model = isinstance(resp.model, str)
        has_usage = isinstance(resp.usage, dict)
        has_choice = len(resp.choices) > 0
        has_role = resp.choices[0].message.role == "assistant"
        has_reason = isinstance(resp.choices[0].finish_reason, str)

        print("  id:", resp.id)
        print("  model:", resp.model)
        print("  usage:", resp.usage)
        print("  finish_reason:", resp.choices[0].finish_reason)
        print("  role:", resp.choices[0].message.role)

        ok = has_id and has_model and has_usage and has_choice and has_role and has_reason
        print("  [12/14] PASS" if ok else "  [12/14] FAIL")
    except Exception as e:
        print("  [12/14] ERROR:", e)

    print("--- uopenai Test Done ---")

    # ------------------------------------------------------------------ #
    # Test 13: audio.speech.create() — SKIP (TODO)
    # ------------------------------------------------------------------ #
    print("[13/14] audio.speech.create() -- SKIP (TODO: WebSocket streaming TTS)")

    # ------------------------------------------------------------------ #
    # Test 14: images.generations.create() — SKIP (TODO)
    # ------------------------------------------------------------------ #
    print("[14/14] images.generations.create() -- SKIP (TODO: low-res image gen model)")


# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

time.sleep(3)
print("FreakStudio: uopenai async OpenAI client test")

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    asyncio.run(test_uopenai())
