# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/7/11 上午9:43   
# @Author  : 李清水            
# @File    : main.py       
# @Description : 定时器类实验，使用定时器完成任务调度
# 代码参考：https://github.com/micropython-Chinese-Community/micropython-simple-scheduler/tree/main

# ======================================== 导入相关模块 ========================================

# 导入硬件相关的模块
from machine import Timer
# 导入任务调度器
from Scheduler import Scheduler, Task
# 导入时间模块
import time
# 垃圾回收的模块
import gc
# 导入系统相关的模块
import sys

# ======================================== 全局变量 ============================================

# 任务开始时间
time_start = time.ticks_us()
# 方法执行次数
RunCnt = 0

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

# 使用@timed_function装饰器，计算任务运行时间
@timed_function
def task_callback(task_id: int) -> None:
    """
    任务回调函数，用于打印任务信息并管理任务的状态。

    Args:
        task_id (int): 任务ID，用于标识当前任务。

    Returns:
        None
    """
    global time_start, RunCnt, sc, task1, task2
    # 计算从起始时间到现在的时间差
    time_now = (time.ticks_us() - time_start) / 1000

    # 输出任务运行次数、任务运行时间和任务ID
    print('{} - {:.2f} ms: task {} is running'.format(RunCnt, time_now, task_id))

    # 任务运行次数加1
    RunCnt = RunCnt + 1

    # 判断任务运行次数
    if RunCnt == 5 :
        # 任务2暂停
        sc.pause(task2)
        print('pause task 2')
        # 创建任务3，1000ms执行一次
        task3 = Task(task_callback, 3, interval=1000, state=Task.TASK_RUN)
        # 添加任务3
        sc.add(task3)
        print('add task 3')
        # 删除任务1
        sc.delete(task1)
        print('delete task 1')

    # 判断任务运行次数
    if RunCnt == 8:
        # 任务2恢复
        sc.resume(task2)

# 空闲任务回调函数
def task_idle_callback() -> None:
    """
    空闲任务回调函数，用于在内存不足时手动触发垃圾回收功能。

    Args:
        None

    Returns:
        None
    """
    # 当可用堆 RAM 的字节数小于 230000 时，手动触发垃圾回收功能
    if gc.mem_free() < 230000:
        # 手动触发垃圾回收功能
        gc.collect()

# 异常回调函数
def task_err_callback(e: Exception) -> None:
    """
    异常回调函数，用于打印异常信息并处理任务错误。

    Args:
        e (Exception): 捕获到的异常对象。

    Returns:
        None
    """
    while True:
        sys.print_exception(e)
        print('task run error')

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息
print("FreakStudio : Using Timer to implement a simple task scheduler")

# 创建任务1，500ms执行一次
task1 = Task(task_callback, 1, interval=500, state=Task.TASK_RUN)
# 创建任务2，1000ms执行一次
task2 = Task(task_callback, 2, interval=1000, state=Task.TASK_RUN)

# 创建任务调度器,定时周期为100ms
sc = Scheduler(Timer(-1), interval=100, task_idle=task_idle_callback, task_err=task_err_callback)

# 添加任务
sc.add(task1)
sc.add(task2)

# ========================================  主程序  ============================================

# 延时2s，等待烧录完成程序后打开终端
time.sleep(2)
# 开启调度
sc.scheduler()