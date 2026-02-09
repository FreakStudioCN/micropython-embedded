# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/8/16 上午10:51   
# @Author  : 李清水            
# @File    : main.py       
# @Description : WDT看门狗定时器类实验，使用Pico软件定时器实现

# ======================================== 导入相关模块 ========================================

# 导入硬件相关模块
from machine import Timer, reset, disable_irq, enable_irq
# 导入时间相关模块
import time
# 导入scheduler方法
from micropython import schedule
# 导入micropython相关模块
import micropython

from SoftwareWatchdog import SoftwareWatchdog

# ======================================== 全局变量 ============================================

# 设置触发条件的阈值
threshold = 10
# 假设当前的值是0
current_value = 12
# 声明看门狗对象
watchdog = None

# ======================================== 功能函数 ============================================

# 用户自定义状态记录函数
def user_log_critical_time() -> None:
    """
    用户自定义状态记录函数，用于将当前时间戳、当前值、看门狗触发次数、连续喂狗失败次数写入日志文件。
    当日志文件行数超过 50 条时，自动创建新的日志文件。

    Args:
        None

    Returns:
        None

    Raises:
        Exception: 如果写入日志文件时发生错误。
    """
    # 声明全局变量
    global watchdog, current_value

    # 获取当前时间戳
    timestamp = time.ticks_ms()

    # 日志文件的基础名称
    log_base_name = "/log"
    log_extension = ".txt"
    log_index = 0
    log_file = f"{log_base_name}{log_index}{log_extension}"

    # 查找最新的日志文件
    while True:
        try:
            # 尝试打开文件以检查是否存在
            with open(log_file, "r") as f:
                lines = f.readlines()
                # 如果文件行数小于 10，继续使用当前文件
                if len(lines) < 10:
                    break
        except OSError:
            # 如果文件不存在，使用当前文件
            break
        # 如果文件行数超过 10，递增索引，尝试下一个文件
        log_index += 1
        log_file = f"{log_base_name}{log_index}{log_extension}"

    # 将时间戳、当前值、看门狗触发次数、连续喂狗失败次数写入日志文件
    try:
        with open(log_file, "a") as f:
            # 使用 % 格式化字符串
            log_entry = "Timestamp: %d ms, Current Value: %d, Triggers: %d, Failures: %d\n" % (
                timestamp, current_value, watchdog.trigger_count, watchdog.failure_count
            )
            f.write(log_entry)
            # 确保数据写入存储设备
            f.flush()
    except Exception as e:
        print("[Error] Failed to write log:", str(e))

# 用户自定义触发条件函数
@micropython.native
def user_check_threshold() -> bool:
    """
    用户自定义触发条件函数，用于判断是否达到阈值。

    Args:
        None

    Returns:
        bool: True表示达到阈值，False表示未达到阈值

    Raises:
        None
    """
    # 声明全局变量
    global current_value, threshold

    # 检查是否达到阈值
    if current_value >= threshold:
        # 到达触发阈值，返回True并打印信息
        print("[Trigger] Threshold reached, triggering watchdog...")
        return True

    # 没有达到阈值，返回False并打印信息
    print("[Info] Current value is below threshold, no need to trigger watchdog...")
    return False

# 自定义恢复操作函数
@micropython.native
def user_recovery_handler() -> bool:
    """
    用户自定义恢复操作函数，用于执行恢复操作。

    Args:
        None

    Returns:
        bool: True表示恢复操作成功，False表示恢复操作失败

    Raises:
        Exception: 如果恢复操作执行过程中发生错误。
    """
    # 声明全局变量
    global watchdog

    # 打印恢复操作信息
    print("[Recovery] Attempting to recover system...")

    # 模拟恢复操作
    try:
        # 用户可以在这里执行恢复操作，例如重启系统、重新连接网络等。
        pass
    except Exception as e:
        print("[Error] Failed to recover system:", str(e))
        # 返回False表示恢复操作失败
        return False

    # 打印恢复操作成功信息
    print("[Recovery] Recovery operation completed successfully.")

    # 返回True表示恢复操作成功
    return True

# 计时装饰器，用于计算函数运行时间
@micropython.native
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

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息
print("FreakStudio : Implement Watchdog Timer using a software timer Test")

# 初始化软件看门狗，设置超时时间为4秒，最大连续失败次数为3次，复位延迟时间为1秒
watchdog = SoftwareWatchdog(timeout=4000, debug=True, max_failures=3, reset_delay=1000)
# 注册状态记录回调函数
watchdog.register_state_recorder(user_log_critical_time)
# 设置触发条件回调函数
watchdog.set_trigger_condition(user_check_threshold)
# # 注册恢复操作回调函数
# watchdog.register_recovery_handler(user_recovery_handler)

# ========================================  主程序  ===========================================

# 在超时时间内喂狗十次，看门狗定时器不触发复位
for i in range(2):
    # 喂狗
    watchdog.feed()
    # 延时2秒
    time.sleep(2)
