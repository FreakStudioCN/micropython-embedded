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

# 分配紧急异常缓冲区（必须位于所有中断代码之前）
micropython.alloc_emergency_exception_buf(100)

# 软件看门狗类
class SoftwareWatchdog:
    """
    软件看门狗类，使用MicroPython的Timer实现看门狗功能。
    该类封装了基于定时器的看门狗逻辑，支持超时检测、喂狗操作、状态记录、触发条件判断和恢复操作等功能。
    通过注册回调函数，用户可以自定义状态记录、触发条件和恢复操作逻辑。

    Attributes:
        timeout (int): 看门狗超时时间，单位为毫秒（默认4000ms）。
        debug (bool): 是否开启调试模式（默认开启）。
        max_failures (int): 连续喂狗失败的最大次数（默认1次）。
        reset_delay (int): 触发复位前的延迟时间，单位为毫秒（默认3000ms）。
        feed_successful (bool): 喂狗标志，表示是否成功喂狗。
        timer (Timer): 软件定时器实例，用于周期性检测喂狗状态。
        feed_count (int): 喂狗次数计数器。
        trigger_count (int): 看门狗触发次数计数器。
        failure_count (int): 连续喂狗失败次数计数器。
        _state_recorder (callable): 用户自定义状态记录回调函数。
        _trigger_condition (callable): 用户自定义触发条件回调函数。
        _recovery_handler (callable): 用户自定义恢复操作回调函数。

    Methods:
        __init__(self, timeout: int = 4000, debug: bool = True, max_failures: int = 1, reset_delay: int = 3000) -> None:
            初始化软件看门狗实例。

        _initialize_timer(self) -> None:
            初始化定时器并设置回调函数。

        register_state_recorder(self, recorder: callable[[], None]) -> None:
            注册状态记录回调函数。

        set_trigger_condition(self, condition: callable[[], bool]) -> None:
            设置触发条件回调函数。

        register_recovery_handler(self, handler: callable[[], bool]) -> None:
            注册恢复操作回调函数。

        _watchdog_callback(self, t: Timer) -> None:
            定时器回调函数，判断是否及时喂狗，同时具有状态记录和条件判断是否触发复位功能。

        feed(self) -> None:
            喂狗操作，重置喂狗标志。

        stop(self) -> None:
            停止看门狗定时器。

        __del__(self) -> None:
            析构函数，确保定时器资源释放。
    """
    def __init__(self, timeout: int = 4000, debug: bool = True, max_failures: int = 1, reset_delay: int = 3000) -> None:
        """
        初始化软件看门狗。

        Args:
            timeout (int): 看门狗超时时间，单位为毫秒（默认4000ms）。
            debug (bool): 是否开启调试模式（默认开启）。
            max_failures (int): 连续喂狗失败的最大次数（默认1次）。
            reset_delay (int): 触发复位前的延迟时间，单位为毫秒（默认3000ms）。

        Returns:
            None

        Raises:
            ValueError: 如果参数timeout、max_failures、reset_delay不是正整数或debug不是布尔值。
        """
        # 入口参数检查
        if not isinstance(reset_delay, int) or reset_delay <= 0:
            raise ValueError("reset_delay must be a positive integer")

        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")

        if not isinstance(max_failures, int) or max_failures <= 0:
            raise ValueError("max_failures must be a positive integer")

        if not isinstance(debug, bool):
            raise TypeError("debug must be a boolean value")

        # 设置超时时间
        self.timeout = timeout
        # 设置调试模式
        self.debug = debug
        # 设置最大失败次数
        self.max_failures = max_failures
        # 设置复位延迟时间
        self.reset_delay = reset_delay

        # 初始化喂狗标志为False
        self.feed_successful = False
        # 初始化软件定时器
        self.timer = Timer(-1)

        # 初始化喂狗次数
        self.feed_count = 0
        # 初始化看门狗触发次数
        self.trigger_count = 0
        # 初始化连续喂狗失败次数
        self.failure_count = 0

        # 初始化用户自定义状态记录函数为None
        self._state_recorder = None
        # 初始化用户自定义触发条件函数为None
        self._trigger_condition = None
        # 初始化恢复操作回调函数为None
        self._recovery_handler = None

        # 初始化定时器
        self._initialize_timer()

    def _initialize_timer(self) -> None:
        """
        初始化定时器并设置回调函数。

        Args:
            None

        Returns:
            None
        """
        # 初始化定时器，设置周期和回调函数
        self.timer.init(period=self.timeout, mode=Timer.PERIODIC, callback=lambda t: schedule(self._watchdog_callback, t))

    def register_state_recorder(self, recorder: callable[[], None]) -> None:
        """
        注册状态记录回调函数。

        Args:
            recorder (callable): 无参数无返回值的回调函数，用于记录状态

        Returns:
            None

        Raises:
            TypeError: 如果参数recorder不是callable类型。
        """
        # 检查recorder是否为可调用对象
        if not callable(recorder):
            raise TypeError("State recorder must be callable")

        # 设置状态记录回调函数
        self._state_recorder = recorder

    def set_trigger_condition(self, condition: callable[[], bool]) -> None:
        """
        设置触发条件回调函数。

        Args:
            condition (callable): 无参数返回bool的回调函数，返回为True表示允许触发重启。

        Returns:
            None

        Raises:
            TypeError: 如果参数condition不是callable类型。
        """
        # 检查condition是否为可调用对象
        if not callable(condition):
            raise TypeError("Trigger condition must be callable")

        # 设置触发条件回调函数
        self._trigger_condition = condition

    def register_recovery_handler(self, handler: callable[[], bool]) -> None:
        """
        注册恢复操作回调函数。

        Args:
            handler (callable): 无参数有返回值的回调函数，用于执行恢复操作，返回值为True表示恢复操作成功，False表示恢复操作失败。

        Returns:
            None

        Raises:
            TypeError: 如果参数handler不是callable类型。
        """
        # 检查handler是否为可调用对象
        if not callable(handler):
            raise TypeError("Recovery handler must be callable")

        # 设置恢复操作回调函数
        self._recovery_handler = handler

    # 使用@timed_function装饰器，SoftwareWatchdog._watchdog_callback方法运行时间
    @timed_function
    def _watchdog_callback(self, t: Timer) -> None:
        """
        定时器回调函数，判断是否及时喂狗，同时具有状态记录和条件判断是否触发复位功能。

        Args:
            t (Timer): 定时器对象（由Timer自动传入）。

        Returns:
            None

        Raises:
            Exception: 如果状态记录回调函数执行时发生错误。
            Exception: 如果恢复操作回调函数执行时发生错误。
            TypeError: 如果恢复操作回调函数的返回值不是布尔类型。
            Exception: 如果触发条件回调函数执行时发生错误。
        """

        # 原子读取喂狗标志
        irq_state = disable_irq()
        feed_flag = self.feed_successful
        enable_irq(irq_state)

        # 检查是否及时喂狗
        if not feed_flag:
            # 增加连续失败次数
            self.failure_count += 1
            # 增加触发次数
            self.trigger_count += 1

            # 如果调试模式开启，打印触发信息
            if self.debug:
                print("[Watchdog] Triggered ({} failures, {} total triggers)".format(
                    self.failure_count, self.trigger_count))

            # 执行状态记录（如果已注册）
            if self._state_recorder:
                try:
                    self._state_recorder()
                except Exception as e:
                    if self.debug:
                        print("[Error] Failed to record state:", str(e))

            # 检查连续失败次数是否达到最大值
            if self.failure_count >= self.max_failures:

                # 恢复操作是否成功的标志
                recovery_successful = False

                # 尝试恢复操作
                if self._recovery_handler:
                    try:
                        if self.debug:
                            print("[Watchdog] Attempting recovery...")
                        # 尝试恢复操作
                        recovery_successful = self._recovery_handler()
                        # 判断recovery_successful是否为bool变量
                        if not isinstance(recovery_successful, bool):
                            raise TypeError("Recovery handler must return a boolean value")
                    except Exception as e:
                        if self.debug:
                            print("[Error] Recovery handler failed:", str(e))

                # 检查恢复操作是否成功
                if recovery_successful:
                    # 重置连续失败次数
                    self.failure_count = 0
                    # 重置应该触发标注位
                    self.should_trigger = False
                    if self.debug:
                        print("[Watchdog] Recovery successful, resetting failure count...")
                else:
                    # 如果恢复失败，检查触发条件

                    # 默认触发
                    should_trigger = True
                    # 检查触发条件是否已注册
                    if self._trigger_condition:
                        try:
                            # 执行触发条件检查
                            should_trigger = self._trigger_condition()
                        except Exception as e:
                            if self.debug:
                                print("[Error] Trigger condition check failed:", str(e))
                            # 默认触发
                            should_trigger = True

                    # 如果满足触发条件，触发复位
                    if should_trigger:
                        if self.debug:
                            print("[Watchdog] Max failures reached, resetting system after %d ms..." %(self.reset_delay))
                        # 创建单次定时器，延迟指定时间后执行复位
                        self.reset_timer = Timer(-1)
                        self.reset_timer.init(period=self.reset_delay, mode=Timer.ONE_SHOT, callback=lambda t: reset())
        else:
            # 重置连续失败次数
            self.failure_count = 0

            # 原子重置
            irq_state = disable_irq()
            # 复位喂狗标志
            self.feed_successful = False
            enable_irq(irq_state)

    def feed(self) -> None:
        """
        喂狗操作，重置喂狗标志。

        Args:
            None

        Returns:
            None
        """
        irq_state = disable_irq()
        self.feed_successful = True
        # 增加喂狗次数
        self.feed_count += 1
        enable_irq(irq_state)

        # 如果调试模式开启，打印喂狗时间
        if self.debug:
            print("Watchdog fed at:", time.ticks_ms())

    def stop(self) -> None:
        """
        停止看门狗定时器。

        Args:
            None

        Returns:
            None
        """
        # 停止定时器
        self.timer.deinit()
        if self.debug:
            print("Watchdog stopped.")

    def __del__(self):
        """
        析构函数：确保定时器资源释放。

        Args:
            None

        Returns:
            None
        """
        self.timer.deinit()
        if self.debug:
            print("Watchdog resources released.")

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