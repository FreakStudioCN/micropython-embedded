# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/12/23 下午3:56   
# @Author  : 李清水            
# @File    : main.py       
# @Description : PIO类实验，实现UART串口接收

# ======================================== 导入相关模块 ========================================

import time
from rp2 import PIO, StateMachine, asm_pio
from machine import Pin, UART
import pio_uart_rx
# ======================================== 全局变量 ============================================

# 定义了 UART 的波特率为115200
UART_BAUD = 115200
# 定义了 PIO UART接收使用的引脚编号为1（GP1）
PIO_RX_PIN_NUM = 1
# 定义了串口接收字符串的终止符
UART_TERMINATOR = '\r'
# 定义了串口接收字符串的最大长度（防止缓冲区溢出）
UART_MAX_STR_LEN = 128

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 初始化PIO接收引脚（上拉输入，防止浮空）
pio_rx_pin = Pin(PIO_RX_PIN_NUM, Pin.IN, Pin.PULL_UP)

# 创建PIO状态机0，加载uart_rx程序，时钟频率为8*UART_BAUD（时序匹配的倍频）
# in_base: 输入引脚的起始编号，jmp_pin: 跳转判断使用的引脚（与输入引脚相同）
sm = StateMachine(
    0,
    pio_uart_rx.uart_rx,
    freq=8 * UART_BAUD,
    in_base=pio_rx_pin,
    jmp_pin=pio_rx_pin
)

# 绑定中断处理函数（接收错误时触发）
sm.irq(pio_uart_rx.uart_break_handler)
# 激活状态机（开始接收数据）
sm.active(1)

# ========================================  主程序  ===========================================

while True:
    # 读取字符串（直到换行符）并打印
    received_str = pio_uart_rx.pio_uart_read_string(sm)
    print("Received String: {}".format(received_str))