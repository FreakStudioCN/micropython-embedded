# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/7/10 上午10:19   
# @Author  : 李清水            
# @File    : ButtonDetect.py       
# @Description : 基于定时器的按键检测框架

# ======================================== 导入相关模块 ========================================

# 导入硬件相关模块
from machine import Timer, Signal, Timer, Pin

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 按键状态机框架
class ButtonFSM:
    """
    ButtonFSM类，用于实现按键状态机，检测按键的按下、释放、长按、双击等事件。

    该类封装了按键的状态机逻辑，支持按键的长按、单击、双击等操作的检测。通过定时器定期检测按键的状态变化，
    并根据按键的状态进行相应的事件处理。用户可以通过回调函数获取按键动作。

    Attributes:
        LOW (int): 按键的低电平状态，表示按键未按下。
        HIGH (int): 按键的高电平状态，表示按键被按下。
        BtnPressMinTime (int): 按键长按的最小时间（单位：毫秒），当按键按下时间超过该值时认为是长按。
        BtnDoubleClickMaxTime (int): 双击事件中两次点击的最大时间间隔（单位：毫秒）。
        RELEASE_EVENT (int): 按键释放事件。
        CLICK_EVENT (int): 按键点击事件。
        RELEASE_STATE (int): 按键释放状态。
        DEBOUNCE_STATE (int): 按键消抖状态。
        CLICK_STATE (int): 按键点击状态。
        WAIT_STATE (int): 按键等待第二次点击状态。
        DOUBLE_CLICK_STATE (int): 按键双击状态。
        PRESS_STATE (int): 按键长按状态。

    Methods:
        __init__(self, pin: Pin, timer: Timer, init_state: int,
                 press_callback: callable, click_callback: callable,
                 double_click_callback: callable, args: object = None) -> None:
            初始化ButtonFSM类实例，设置按键引脚、定时器和回调函数。

        detect(self, timer: Timer) -> None:
            按键状态检测函数，根据当前按键状态和信号判断按键动作，更新按键状态。

        get_action(self) -> None:
            获取当前按键动作（如点击或释放），并更新按键状态。
    """
    # 按键初始化状态，初始化情况下为低电平-0，按下时为高电平-1
    LOW, HIGH = (0, 1)
    # 按键长按最小确定时间：当短按时间大于该值时，认为按键被长按
    BtnPressMinTime = 1200
    # 双击中两次单击时间的最大间隔:当两次单击时间小于该值时，认为按键被双击
    BtnDoubleClickMaxTime = 500

    # 按键状态机相关定义
    # 按键事件:释放或按下
    RELEASE_EVENT,CLICK_EVENT = (0, 1)
    # 按键状态:释放、消抖、单击/继续按下、等待第二次按下、双击、长按
    RELEASE_STATE, DEBOUNCE_STATE, CLICK_STATE, WAIT_STATE, DOUBLE_CLICK_STATE, PRESS_STATE = (0, 1, 2, 3, 4, 5)

    def __init__(self, pin: Pin, timer: Timer, init_state: int,
                 press_callback: callable, click_callback: callable,
                 double_click_callback: callable, args: object = None) -> None:
        """
        初始化按键，设置按键的状态、引脚、回调函数及定时器。

        Args:
            pin (machine.Pin): 按键连接的引脚对象。
            timer (machine.Timer): 用于定时检测按键状态的定时器对象。
            init_state (int): 按键初始化状态（低电平或高电平），可选值为 ButtonFSM.LOW 或 ButtonFSM.HIGH。
            press_callback (callable): 长按触发时的回调函数。
            click_callback (callable): 单击触发时的回调函数。
            double_click_callback (callable): 双击触发时的回调函数。
            args (object, optional): 回调函数的额外参数，默认值为 None。

        Returns:
            None

        Description:
            此方法将按键初始化为低电平或高电平，设置定时器定期调用 `detect` 方法以检测按键状态。
        """

        self.pin = pin
        self.timer = timer
        self.init_state = init_state
        self.press_callback = press_callback
        self.click_callback = click_callback
        self.double_click_callback = double_click_callback

        # 初始化按键引脚
        # 按键初始化状态为低电平-0，按下时为高电平-1
        if self.init_state == ButtonFSM.LOW:
            self.pin.init(self.pin.IN, self.pin.PULL_DOWN)
            self.pin_signal = Signal(self.pin, invert=False)
        # 按键初始化状态为高电平-0，按下时为低电平-1
        elif self.init_state == ButtonFSM.HIGH:
            self.pin.init(self.pin.IN, self.pin.PULL_UP)
            self.pin_signal = Signal(self.pin, invert=True)

        # 按键长按计数：通过长按计数*定时器周期判断按键是否被长按
        self.press_count = 0

        # 按键事件
        self.event = ButtonFSM.RELEASE_EVENT
        # 按键状态
        self.state = ButtonFSM.RELEASE_STATE

        # 定时器连续运行，周期为20ms，到达设置时间调用detect方法检测按键状态
        self.run_period = 20
        self.timer.init(period=self.run_period, mode=Timer.PERIODIC, callback=self.detect)

        # 回调函数参数
        self.args = args

    def detect(self, timer: Timer) -> None:
        """
        按键按下状态检测函数，根据按键的当前状态和信号判断按键的动作。

        Args:
            timer (machine.Timer): 传入的定时器对象，用于定期调用检测函数。

        Returns:
            None: 该函数没有返回值，通过内部事件更新按键状态。
        """

        # 获取按键动作
        self.get_action()

        # 状态：无动作
        if self.state == ButtonFSM.RELEASE_STATE:
            # 按键按下，进入消抖状态
            if self.event == ButtonFSM.CLICK_EVENT:
                self.state = ButtonFSM.DEBOUNCE_STATE
            # 按键没有按下，进入释放状态
            else:
                self.state = ButtonFSM.RELEASE_STATE

        # 状态：消抖
        elif self.state == ButtonFSM.DEBOUNCE_STATE:
            # 按键按下，进入单击状态
            if self.event == ButtonFSM.CLICK_EVENT:
                self.state = ButtonFSM.CLICK_STATE
            # 按键没有按下，进入释放状态
            else:
                self.state = ButtonFSM.RELEASE_STATE

        # 状态：单击/继续按下
        elif self.state == ButtonFSM.CLICK_STATE:
            # 按键仍然处于按下状态并且超过BtnPressMinTime按键长按最小确定时间
            if self.event == ButtonFSM.CLICK_EVENT and self.press_count*self.run_period >= ButtonFSM.BtnPressMinTime:
                # 按键为长按状态
                self.state = ButtonFSM.PRESS_STATE
                self.press_count = 0
            # 按键仍然处于按下状态并且小于BtnPressMinTime按键长按最小确定时间
            elif self.event == ButtonFSM.CLICK_EVENT and self.press_count*self.run_period < ButtonFSM.BtnPressMinTime:
                # 继续计时
                self.press_count = self.press_count + 1
                # 保持单击状态
                self.state = ButtonFSM.CLICK_STATE

            # 短按后释放按键，进入等待第二次按下状态
            else:
                # 清除计数变量
                self.press_count = 0
                # 进入等待第二次按下状态
                self.state = ButtonFSM.WAIT_STATE

        # 状态：长按
        elif self.state == ButtonFSM.PRESS_STATE:
            # 仍然处于按下状态，等待按键释放后转换为长按事件
            if self.event == ButtonFSM.CLICK_EVENT:
                # 按键长按计数清零
                self.press_count = 0
                # 按键释放，进入释放状态
                self.state = ButtonFSM.PRESS_STATE
            else:
                self.press_count = 0
                self.state = ButtonFSM.RELEASE_STATE
                # 执行长按回调函数
                if self.press_callback is not None:
                    self.press_callback(self.args)

        # 状态：等待第二次按下
        elif self.state == ButtonFSM.WAIT_STATE:
            # 第一次短按,且释放时间大于BtnDoubleClickMaxTime双击中两次单击时间的最大间隔
            if self.event == ButtonFSM.RELEASE_EVENT and self.press_count*self.run_period >= ButtonFSM.BtnDoubleClickMaxTime:
                self.press_count = 0
                self.state = ButtonFSM.RELEASE_STATE
                # 执行单击回调函数
                if self.click_callback is not None:
                    self.click_callback(self.args)

            # 第一次短按，且释放时间小于BtnDoubleClickMaxTime双击中两次单击时间的最大间隔
            elif self.event == ButtonFSM.RELEASE_EVENT and self.press_count*self.run_period < ButtonFSM.BtnDoubleClickMaxTime:
                # 继续等待
                self.press_count = self.press_count + 1
                self.state = ButtonFSM.WAIT_STATE

            # 第一次短按，且还没到BtnDoubleClickMaxTime时间就第二次被按下
            else:
                self.press_count = 0
                # 进入双击状态
                self.state = ButtonFSM.DOUBLE_CLICK_STATE

        # 状态：双击
        elif self.state == ButtonFSM.DOUBLE_CLICK_STATE:
            # 第二次按的时间大于BtnPressMinTime按键长按最小确定时间
            if self.event == ButtonFSM.CLICK_EVENT and self.press_count*self.run_period >= ButtonFSM.BtnPressMinTime:
                # 按键长按状态
                self.state = ButtonFSM.PRESS_STATE
                # 按键长按计数清零
                self.press_count = 0

                if self.click_callback is not None:
                    self.click_callback(self.args)
            # 第二次按的时间小于BtnPressMinTime按键长按最小确定时间
            elif self.event == ButtonFSM.CLICK_EVENT and self.press_count*self.run_period < ButtonFSM.BtnPressMinTime:
                self.press_count = self.press_count + 1
                # 保持双击状态
                self.state = ButtonFSM.DOUBLE_CLICK_STATE

            # 第二次按键按下后在BtnPressMinTime按键长按最小确定时间内释放
            else :
                self.press_count = 0
                self.state = ButtonFSM.RELEASE_STATE
                # 执行双击回调函数
                if self.double_click_callback is not None:
                    self.double_click_callback(self.args)
        return

    def get_action(self) -> None:
        """
        获取按键动作并更新事件状态。

        Args:
            None

        Returns:
            None: 该函数没有返回值，仅更新内部事件状态。
        """

        # 若信号无效，按键没有被按下
        if self.pin_signal.value() == 0:
            self.event = ButtonFSM.RELEASE_EVENT
        # 信号有效，按键被按下
        elif self.pin_signal.value() == 1:
            self.event = ButtonFSM.CLICK_EVENT

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ============================================

