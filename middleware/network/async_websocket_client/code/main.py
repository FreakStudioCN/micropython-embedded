# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  : leeqingshui
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
WIFI_SSID = "Y/OURSPACE"
WIFI_PASSWORD = "qc123456789"

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
            time.sleep(1)  # 替换utime.sleep为time.sleep
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
