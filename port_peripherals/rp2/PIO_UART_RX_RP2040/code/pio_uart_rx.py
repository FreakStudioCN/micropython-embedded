# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/12/23 下午3:56   
# @Author  : 李清水            
# @File    : pio_uart_rx.py      
# @Description : PIO类实验，实现UART串口接收

# ======================================== 导入相关模块 ========================================

import time
from rp2 import PIO, StateMachine, asm_pio
from machine import Pin, UART

# ======================================== 全局变量 ============================================

# 定义了串口接收字符串的终止符
UART_TERMINATOR = '\r'
# 定义了串口接收字符串的最大长度（防止缓冲区溢出）
UART_MAX_STR_LEN = 128

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

# 使用@asm_pio装饰器定义一个 PIO 程序
# 输入数据方向为向右移位
@asm_pio(in_shiftdir=PIO.SHIFT_RIGHT)
def uart_rx() -> None:
    """
    PIO实现UART接收逻辑（8位数据位，1位起始位，1位停止位）。

    Returns:
        None
    """
    label("start")
    # 等待起始位（低电平）
    wait(0, pin, 0)
    # 设置数据计数器x为7（共8位数据），延时到第一个数据位中间（10个周期）
    set(x, 7)                 [10]
    # 循环读取8位数据
    label("bitloop")
    in_(pins, 1)
    jmp(x_dec, "bitloop")     [6]
    # 检查停止位（高电平为正常）
    jmp(pin, "good_stop")
    # 停止位错误：触发中断，等待引脚空闲，放弃数据
    irq(block, 4)
    wait(1, pin, 0)
    jmp("start")
    # 停止位正常：推送数据到FIFO（block表示阻塞直到FIFO有空间）
    label("good_stop")
    push(block)

def uart_break_handler(sm: StateMachine) -> None:
    """
    PIO检测到串口帧错误/停止位错误时的中断处理函数。

    Args:
        sm (StateMachine): 触发中断的PIO状态机实例

    Returns:
        None
    """
    print("Recv Break/Frame Error at: {}ms".format(time.ticks_ms()))

@timed_function
def pio_uart_read_byte(sm: StateMachine) -> int:
    """
    从PIO状态机读取一个UART接收的字节（带计时装饰器）。

    Args:
        sm (StateMachine): 使用的PIO状态机实例

    Returns:
        int: 接收的8位字节数据（0-255）
    """
    # 从PIO FIFO读取32位数据，右移24位提取有效8位（因右移位存储在高8位）
    received_data = sm.get()
    received_byte = received_data >> 24
    return received_byte

def pio_uart_read_string(sm: StateMachine, max_length: int = UART_MAX_STR_LEN, terminator: str = UART_TERMINATOR) -> str:
    """
    从PIO状态机读取UART接收的字符串（直到终止符或最大长度）。

    Args:
        sm (StateMachine): 使用的PIO状态机实例
        max_length (int, optional): 最大读取长度，防止无限阻塞。默认值为UART_MAX_STR_LEN
        terminator (str, optional): 字符串终止符（如换行符）。默认值为UART_TERMINATOR

    Returns:
        str: 接收的字符串
    """
    received_chars = []
    current_length = 0
    # 循环读取字节直到达到最大长度或遇到终止符
    while current_length < max_length:
        byte = pio_uart_read_byte(sm)
        char = chr(byte)
        received_chars.append(char)
        current_length += 1
        # 遇到终止符则停止读取
        if char == terminator:
            break
    # 拼接字符为字符串并返回
    return ''.join(received_chars)

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
