# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/9/7 上午11:26   
# @Author  : 李清水            
# @File    : main.py       
# @Description : DMA类实验，内存到外设传输：DMA从内存写入数据到UART

# ======================================== 导入相关模块 =========================================

# 导入数学计算相关模块
import math
# 导入时间相关模块
import time
# 导入自定义串口DMA传输类
from dma_uart_tx import DMA_UART_Tx
# 导入硬件相关模块
from machine import UART

# ======================================== 全局变量 ============================================

# 数据缓冲区，待发送的数据：为一个正弦波数据
# 配置正弦波参数
amplitude = 127     # 幅度，正弦波最大值(0-255)，127 对应无符号8位范围的一半，峰值
offset = 128        # 偏移量，保证波形在 0 到 255 之间
num_samples = 1000  # 正弦波采样点数
frequency = 1       # 频率，可以自行调整

# 生成正弦波数据，并将其放入 bytearray
sin_wave = bytearray(num_samples)

for i in range(num_samples):
    # 计算当前采样点的角度
    angle = 2 * math.pi * frequency * (i / num_samples)
    # 生成对应的正弦波值，放大并加上偏移量以适应 bytearray (0-255) 范围
    sine_value = int(amplitude * math.sin(angle) + offset)
    # 将正弦值放入 bytearray 缓冲区
    sin_wave[i] = sine_value

# 串口使用DMA发送数据的运行时间
uart_dma_time = 0
# 串口不使用DMA发送数据的运行时间
uart_non_dma_time = 0

# ======================================== 功能函数 ============================================

# DMA传输等待回调函数
def uart_dma_tx_wait_func() -> None:
    """
    DMA传输等待回调函数。

    Returns:
        None
    """
    print("wait dma transmit complete")

# DMA传输完成回调函数
def uart_dma_tx_complete_callback() -> None:
    """
    DMA传输完成回调函数。

    Returns:
        None
    """
    print("uart dma transmit complete")

# 在 bytearray 每个元素后添加换行符 '\r\n'
def add_newline_after_each_byte(buf: bytearray) -> bytearray:
    """
    在 bytearray 每个元素后添加换行符 '\r\n'。

    Args:
        buf (bytearray): 输入的 bytearray。

    Returns:
        bytearray: 返回一个新的包含 '\r\n' 的 bytearray。

    Raises:
        TypeError: 如果输入参数不是 bytearray 类型。
    """

    # 检查输入参数是否为 bytearray
    if not isinstance(buf, bytearray):
        raise TypeError("buf must be a bytearray")

    # 新建一个新的 bytearray 用于存放结果
    expanded_buf = bytearray()

    # 遍历输入缓冲区的每个字节
    for byte in buf:
        # 添加原始数据字节
        expanded_buf.append(byte)
        # 追加 '\r' 的 ASCII 值 (13)
        expanded_buf.append(13)
        # 追加 '\n' 的 ASCII 值 (10)
        expanded_buf.append(10)

    return expanded_buf

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息，表示开始主程序
print("FreakStudio: DMA Memory to Peripheral Test ")

# 实例化 DMA_UART_Tx 类，假设使用 UART0，波特率115200，TX引脚为0，RX引脚为1
dma_uart = DMA_UART_Tx(uart_num=0, baudrate=115200, tx_pin=0, rx_pin=1)

# 创建串口对象，设置波特率为115200
uart = UART(1, 115200)
# 初始化uart对象，波特率为115200，数据位为8，无校验位，停止位为1
# 设置接收引脚为GPIO5，发送引脚为GPIO4
# 设置串口超时时间为100ms
uart.init(baudrate  = 115200,
          bits      = 8,
          parity    = None,
          stop      = 1,
          tx        = 4,
          rx        = 5,
          timeout   = 100)

# ========================================  主程序  ===========================================

# 串口传输数据，使用DMA
# 传输数据，使用阻塞模式
dma_uart.dma_transmit(buf=sin_wave, wait_func=uart_dma_tx_wait_func, callback=uart_dma_tx_complete_callback, blocking=True)
# 传输数据，使用非阻塞模式，记录运行时间
uart_dma_time = dma_uart.dma_transmit(buf=sin_wave, blocking=False)

# 传输数据，不使用DMA
# 记录开始时间点
start_time = time.ticks_us()
# 传输数据
uart.write(sin_wave)
# 记录结束时间点
end_time = time.ticks_us()
# 计算运行时间
uart_non_dma_time = time.ticks_diff(end_time, start_time)

# 打印调试数据，表示传输完成
print("DMA Finished,run time: %d us" % uart_dma_time)
print("Non-DMA Finished,run time: %d us" % uart_non_dma_time)