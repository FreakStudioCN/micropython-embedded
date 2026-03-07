# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/7/28 下午1:55   
# @Author  : 李清水            
# @File    : main.py       
# @Description : PIO类实验，在PIO程序中实现UART串口通信

# ======================================== 导入相关模块 ========================================

# 导入时间相关的模块
import time
# 导入RP2040相关的模块
from rp2 import PIO, StateMachine, asm_pio
# 导入硬件相关的模块
from machine import Pin, UART

import pio_uart_tx

# ======================================== 全局变量 ============================================

# 定义了 UART 的波特率为115200
UART_BAUD = 115200
# 定义了 PIO 使用的起始引脚编号为 4
PIN_BASE = 4
# 串口发送计数
UART_TX_COUNT = 0

# ======================================== 功能函数 ============================================

# 计时装饰器，用于计算函数运行时间
def timed_function(f: callable, *args: tuple, **kwargs: dict) -> callable:
    """
    计时装饰器，用于计算并打印函数/方法运行时间。

    Args:
        f (callable): 需要传入的函数/方法
        args (tuple): 函数/方法 f 传入的任意数量的位置参数
        kwargs (dict): 函数/方法 f 传入的任意数量的关键字参数

    Returns:
        callable: 返回计时后的函数
    """
    myname = str(f).split(' ')[1]

    def new_func(*args: tuple, **kwargs: dict) -> any:
        t: int = time.ticks_us()
        result = f(*args, **kwargs)
        delta: int = time.ticks_diff(time.ticks_us(), t)
        print('Function {} Time = {:6.3f}ms'.format(myname, delta / 1000))
        return result

    return new_func


# 硬件UART外设发送数据
@timed_function
def hardware_uart_print(uart_obj: UART, s: str) -> None:
    """
    硬件UART外设发送数据。

    Args:
        uart_obj (UART): 使用的UART硬件串口外设实例。
        s (str): 要发送的字符串。

    Returns:
        None
    """
    uart_obj.write(s)
    # 阻塞直到发送完成
    while not uart.txdone():
        pass

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 创建一个状态机0，写入PIO程序uart_tx，时钟周期为8 * UART_BAUD，使用引脚4作为侧集引脚和输出引脚
sm = StateMachine(0, pio_uart_tx.uart_tx, freq=8 * UART_BAUD, sideset_base=Pin(PIN_BASE), out_base=Pin(PIN_BASE))
# 启动状态机
sm.active(1)

# 创建一个串口实例
uart = UART(0, UART_BAUD)
# 串口外设初始化
uart.init(baudrate  = UART_BAUD,
          bits      = 8,
          parity    = None,
          stop      = 1,
          tx        = 0,
          rx        = 1,
          timeout   = 100)

# ========================================  主程序  ===========================================

while True:
    # 延时1秒
    time.sleep(1)
    # PIO实现UART发送字符串
    pio_uart_tx.pio_uart_print(sm, "UART TX DATA\r\n")
    # 硬件UART外设发送字符串
    hardware_uart_print(uart, "UART TX DATA\r\n")