# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/15
# @Author  : leeqingsui
# @File    : main.py
# @Description : aiohttps async HTTPS client test for MicroPython on Raspberry Pi Pico 2W

# ======================================== 导入相关模块 =========================================

import network
import asyncio
import time
import json
import ntptime
import aiohttps

# ======================================== 全局变量 ============================================

WIFI_SSID = "Y/OURSPACE"
WIFI_PASSWORD = "qc123456789"

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
    # 初始化 WiFi 为 STA 模式
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # 避免重复连接
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


async def test_aiohttps():
    """
    aiohttps 库全量测试，使用 httpbin.org 作为公开测试服务器。

    Test 1: GET  -> json()         HTTPS 握手 + 全量读取 + JSON 解析
    Test 2: POST -> json()         str 请求体上传 + 服务端回显
    Test 3: GET  -> save()         流式下载写文件（4096 字节）
    Test 4: GET  -> status 404     非 200 状态码不抛异常
    Test 5: GET  -> text           resp.text 属性读取
    Test 6: POST -> bytes body     bytes 类型请求体
    Test 7: PUT  -> request()      非 GET/POST 方法
    Test 8: GET  -> http://        HTTP 明文连接
    Test 9: GET  -> iter_lines()   SSE 流式逐行读取

    ==========================================

    Full test for aiohttps using httpbin.org as the public test server.
    """
    # 1. 连接 WiFi
    if not connect_wifi():
        return

    # 2. 同步 NTP
    sync_ntp()

    print("--- aiohttps Test Start ---")

    # Test 1: HTTPS GET -> json()
    print("[1/8] GET https://httpbin.org/get")
    try:
        resp = await aiohttps.get("https://httpbin.org/get")
        print("  status:", resp.status)
        data = await resp.json()
        print("  origin IP:", data.get("origin", "?"))
        print("  [1/8] PASS" if resp.status == 200 else "  [1/8] FAIL")
    except Exception as e:
        print("  [1/8] ERROR:", e)

    # Test 2: HTTPS POST str body -> json()
    print("[2/8] POST https://httpbin.org/post (str body)")
    try:
        body = json.dumps({"device": "pico2w", "lib": "aiohttps"})
        resp = await aiohttps.post(
            "https://httpbin.org/post",
            headers={"Content-Type": "application/json"},
            data=body,
        )
        data = await resp.json()
        echoed = data.get("json", {})
        ok = echoed.get("device") == "pico2w" and echoed.get("lib") == "aiohttps"
        print("  [2/8] PASS" if ok else "  [2/8] FAIL (echo mismatch)")
    except Exception as e:
        print("  [2/8] ERROR:", e)

    # Test 3: HTTPS GET -> save() streaming download
    print("[3/8] GET https://httpbin.org/bytes/4096 -> save test.bin")
    try:
        resp = await aiohttps.get("https://httpbin.org/bytes/4096")
        n = await resp.save("test.bin")
        print("  saved:", n, "bytes")
        print("  [3/8] PASS" if n == 4096 else "  [3/8] FAIL (expected 4096, got {})".format(n))
    except Exception as e:
        print("  [3/8] ERROR:", e)

    # Test 4: non-200 status code (404)
    print("[4/8] GET https://httpbin.org/status/404")
    try:
        resp = await aiohttps.get("https://httpbin.org/status/404")
        resp.close()
        print("  status:", resp.status)
        print("  [4/8] PASS" if resp.status == 404 else "  [4/8] FAIL (expected 404)")
    except Exception as e:
        print("  [4/8] ERROR:", e)

    # Test 5: resp.text property
    print("[5/8] GET https://httpbin.org/encoding/utf8 -> text")
    try:
        resp = await aiohttps.get("https://httpbin.org/encoding/utf8")
        t = await resp.text
        print("  text length:", len(t))
        print("  [5/8] PASS" if len(t) > 0 else "  [5/8] FAIL (empty text)")
    except Exception as e:
        print("  [5/8] ERROR:", e)

    # Test 6: POST bytes body
    print("[6/8] POST https://httpbin.org/post (bytes body)")
    try:
        body = b"\x00\x01\x02\x03\xff"
        resp = await aiohttps.post(
            "https://httpbin.org/post",
            headers={"Content-Type": "application/octet-stream"},
            data=body,
        )
        await resp.text  # 消费响应体（二进制回显不能 json()）
        ok = resp.status == 200
        print("  [6/8] PASS" if ok else "  [6/8] FAIL")
    except Exception as e:
        print("  [6/8] ERROR:", e)

    # Test 7: PUT method via request()
    print("[7/8] PUT https://httpbin.org/put")
    try:
        resp = await aiohttps.request(
            "PUT",
            "https://httpbin.org/put",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"action": "put_test"}),
        )
        data = await resp.json()
        ok = resp.status == 200 and data.get("json", {}).get("action") == "put_test"
        print("  [7/8] PASS" if ok else "  [7/8] FAIL")
    except Exception as e:
        print("  [7/8] ERROR:", e)

    # Test 8: HTTP (plain, non-HTTPS)
    print("[8/9] GET http://httpbin.org/get (plain HTTP)")
    try:
        resp = await aiohttps.get("http://httpbin.org/get")
        print("  status:", resp.status)
        data = await resp.json()
        print("  origin IP:", data.get("origin", "?"))
        print("  [8/9] PASS" if resp.status == 200 else "  [8/9] FAIL")
    except Exception as e:
        print("  [8/9] ERROR:", e)

    # Test 9: iter_lines() streaming SSE
    print("[9/9] GET https://httpbin.org/stream/3 -> iter_lines()")
    try:
        resp = await aiohttps.get("https://httpbin.org/stream/3")
        print("  status:", resp.status)
        count = 0
        async for line in resp.iter_lines():
            line = line.strip()
            if not line:
                # 跳过空行（HTTP 分隔行）
                continue
            count += 1
            print("  line {}: {} bytes".format(count, len(line)))
        print("  [9/9] PASS" if count >= 3 else "  [9/9] FAIL (expected >=3 lines, got {})".format(count))
    except Exception as e:
        print("  [9/9] ERROR:", e)

    print("--- aiohttps Test Done ---")


# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

time.sleep(3)
print("FreakStudio: aiohttps async HTTPS client test")

# ========================================  主程序  ===========================================

if __name__ == "__main__":
    asyncio.run(test_aiohttps())
