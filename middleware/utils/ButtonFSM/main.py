# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/7/9 下午11:03   
# @Author  : 李清水            
# @File    : main.py       
# @Description : 定时器实验，使用定时器完成按键短按和长按检测功能

# ======================================== 导入相关模块 ========================================

# 导入硬件相关的模块
from machine import Pin, Timer
# 导入按键检测框架
from ButtonDetect import ButtonFSM
# 时间相关的模块
import time

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# 按键长按回调函数
def press_func(arg: int) -> None:
    """
    按键长按回调函数，当按键被长按时触发。

    Args:
        arg (int): 按键编号或其他标识信息。

    Returns:
        None: 该函数没有返回值，仅执行打印操作。
    """
    print('button %d is pressed' % arg)

# 按键短按回调函数
def click_func(arg: int) -> None:
    """
    按键短按回调函数，当按键被短按时触发。

    Args:
        arg (int): 按键编号或其他标识信息。

    Returns:
        None: 该函数没有返回值，仅执行打印操作。
    """
    print('button %d is clicked' % arg)

# 按键双击回调函数
def double_click_func(arg: int) -> None:
    """
    按键双击回调函数，当按键被双击时触发。

    Args:
        arg (int): 按键编号或其他标识信息。

    Returns:
        None: 该函数没有返回值，仅执行打印操作。
    """
    print('button %d is double clicked' % arg)

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 延时等待设备初始化
time.sleep(3)
# 打印调试信息
print("FreakStudio : Using ButtonFSM to detect the status of button")

# 定义按键引脚
button_1_pin = Pin(10)
button_2_pin = Pin(11)
button_3_pin = Pin(12)
button_4_pin = Pin(13)

# 定义定时器对象
timer_1 = Timer(-1)
timer_2 = Timer(-1)
timer_3 = Timer(-1)
timer_4 = Timer(-1)

# 创建4个按键实例
button_1 = ButtonFSM(button_1_pin, timer_1, ButtonFSM.LOW, press_func, click_func, double_click_func,1)
button_2 = ButtonFSM(button_2_pin, timer_2, ButtonFSM.LOW, press_func, click_func, double_click_func,2)
button_3 = ButtonFSM(button_3_pin, timer_3, ButtonFSM.LOW, press_func, click_func, double_click_func,3)
button_4 = ButtonFSM(button_4_pin, timer_4, ButtonFSM.LOW, press_func, click_func, double_click_func,4)

# ========================================  主程序  ============================================

while True:
    pass