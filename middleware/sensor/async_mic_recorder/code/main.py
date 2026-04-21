# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/20
# @Author  : leeqingsui
# @File    : main.py
# @Description : AsyncMicRecorder test file 异步VAD录音器测试主程序

# ======================================== 导入相关模块 =========================================

# 导入硬件I2S、引脚控制模块
from machine import I2S, Pin
# 导入异步协程核心库
import asyncio
# 导入延时模块
import time
# 导入自定义异步录音器类
from async_mic_recorder import AsyncMicRecorder

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# 实时音量能量回调函数：打印当前麦克风采集的音量值
def on_energy(e):
    print("energy:", e, end="\r")

# 录音器状态事件回调函数：处理录音器发出的各类状态通知
def on_event(msg):
    if msg == "ready":
        print("AsyncMicRecorder ready")
    elif msg == "voice_start":
        print("\nVoice detected, recording...")
    elif msg == "too_short":
        print("\nVoice too short, listening...")
    elif msg.startswith("saved:"):
        _, path, size = msg.split(":")
        print("Saved -> {} ({} bytes)".format(path, size))

# 主异步任务：初始化录音器并启动录音流程
async def main():
    # 实例化异步VAD录音器，传入I2S对象和录音参数
    recorder = AsyncMicRecorder(
        audio_in,
        rate=16000,         # 采样率16kHz
        threshold=600,      # VAD音量阈值
        silence_frames=40,  # 静音帧数阈值（触发停止）
        min_voice_frames=5, # 最小有效语音帧数
        frame_bytes=2048,   # 单帧数据字节数
        max_seconds=30,     # 最大录音时长30秒
        warmup_frames=15,   # 预热丢帧数
        on_energy=on_energy,
        on_event=on_event,
    )
    # 启动录音器（预热，丢弃初始噪声）
    await recorder.start()
    # 开始监听语音，保存为mic.pcm文件
    path = await recorder.listen("mic.pcm")
    # 打印录音完成路径
    print("Recording saved:", path)
    # 停止录音器，释放I2S硬件资源
    recorder.stop()

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ===========================================

# 等待硬件稳定
time.sleep(3)
print("FreakStudio: test AsyncMicRecorder now")

# 初始化I2S麦克风输入
audio_in = I2S(
    0,                  # I2S单元编号
    sck=Pin(5), ws=Pin(4), sd=Pin(6),   # 时钟/声道/数据引脚
    mode=I2S.RX,        # 接收模式（麦克风输入）
    bits=16,            # 16位采样精度
    format=I2S.MONO,    # 单声道
    rate=16000,         # 采样率16kHz
    ibuf=40000,         # I2S内部缓冲区大小
)

# ========================================  主程序  ===========================================

# 运行异步主任务
asyncio.run(main())