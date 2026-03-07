# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/7/28 下午1:55   
# @Author  : 李清水            
# @File    : pio_uart_tx.py       
# @Description : PIO类实验，在PIO程序中实现UART发送

# ======================================== 导入相关模块 ========================================

# 导入时间相关的模块
import time
# 导入RP2040相关的模块
from rp2 import PIO, StateMachine, asm_pio
# 导入硬件相关的模块
from machine import Pin, UART

# ======================================== 全局变量 ============================================

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
# 侧集引脚初始化为高电平，OUT引脚初始化为高电平，输出数据方向为向右
@asm_pio(sideset_init=PIO.OUT_HIGH, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT)
def uart_tx() -> None:
    """
    PIO实现UART发送逻辑。

    Returns:
        None
    """
    # 从 TX FIFO 中取出一个字节,等待直到有数据可用
    pull()
    # 初始化位计数器x的值为7，同时将引脚置低电平 7 + 1 个周期，相当于发送一个起始位
    set(x, 7)  .side(0)       [7]
    # 定义了一个标签 "bitloop",用于后续跳转
    label("bitloop")
    # 将数据位从OSR移至pins，OUT指令执行需要一个周期，延时6个周期，总共花费 6+1 = 7个周期
    out(pins, 1)              [6]
    # 将x寄存器递减1，若x不为0，则跳转到bitloop标签处，继续数据发送循环
    # jmp指令执行花费一个周期，总共花费 7+1 = 8个周期，一次bitloop循环发送一个数据位
    jmp(x_dec, "bitloop")
    # 无操作侧集操作置高电平并延时6个周期，总共花费 6+1 = 7个周期
    # pull指令执行花费一个周期，总共花费 7+1 = 8个周期，发送一个停止位
    nop()      .side(1)       [6]

# pio_uart_print函数，用于通过PIO实现UART发送字符串
@timed_function
def pio_uart_print(sm: StateMachine, s: str) -> None:
    """
    通过PIO实现UART发送字符串。

    Args:
        sm (StateMachine): 使用的PIO状态机实例。
        s (str): 要发送的字符串。

    Returns:
        None
    """
    # 遍历字符串中的每个字符
    for c in s:
        # 将一个字推送到状态机的 TX FIFO
        sm.put(ord(c))

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
