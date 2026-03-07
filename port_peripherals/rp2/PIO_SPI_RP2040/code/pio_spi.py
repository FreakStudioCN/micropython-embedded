# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/11/6 下午4:26   
# @Author  : 李清水            
# @File    : pio_spi.py       
# @Description : PIO类实验，在PIO程序中实现SPI协议通信
# 参考代码：https://github.com/raspberrypi/pico-micropython-examples/blob/master/pio/pio_spi.py

# ======================================== 导入相关模块 ========================================

# 导入硬件相关模块
from machine import Pin
# 导入RP2040相关的模块
from rp2 import PIO, StateMachine, asm_pio

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# 使用@asm_pio装饰器定义一个 PIO 程序
# OSR移位寄存器的方向为左移，使能自动推出和自动加载，移位计数阈值均为8
# 用于侧集操作的两个引脚初始化为低电平和高电平，用于输出的引脚初始化为低电平
@asm_pio(out_shiftdir=0, autopull=True, pull_thresh=8,
         autopush=True, push_thresh=8,
         sideset_init=(PIO.OUT_LOW, PIO.OUT_HIGH), out_init=PIO.OUT_LOW)
def spi_cpha0() -> None:
    """
    PIO 实现的 SPI 协议（CPHA=0\CPOL=0）

    该 PIO 程序实现了 SPI 协议的 CPHA=0\CPOL=0 模式，支持 8 位数据传输。
    通过侧集引脚控制 SCK 和 MOSI，同时读取 MISO 数据。

    Args:
        None

    Returns:
        None
    """
    # 设置寄存器 x 为 6，这里 x 寄存器用来控制每个字节的位数倒计数
    # 设置为 6 表示需要发送 7 次时钟循环，x的值从6递减到0
    set(x, 6)

    # 用于定义循环开始位置
    wrap_target()
    # 当OSR输出移位计数器达到其阈值时（即8个数据位），则从TX FIFO队列中提取一个字节数据到输出移位寄存器
    # 如果TX FIFO为空，则等待数据填充
    # 设置侧边位（side-set）的时钟线 SCK 为高电平，[1] 表示等待一个周期
    pull(ifempty)            .side(0x2)   [1]

    # 定义标签 bitloop，用于表示一个字节数据的位循环（发送和接收每一位）
    label("bitloop")
    # 从输出移位寄存器 OUT 中取出 1 位并通过 pins 输出，即数据输出到 MOSI 引脚
    # 设置 SCK 低电平，表明数据在时钟的下降沿输出
    out(pins, 1)             .side(0x0)   [1]
    # 从 MISO 引脚读取1位数据并存入输入ISR移位寄存器
    # 将 SCK 设置为高电平，在时钟的上升沿采样数据
    in_(pins, 1)             .side(0x1)
    # 判断x是否减至零，如果 x 未减到零，跳转到 bitloop 标签继续传输下一个位
    # 之后对 x 寄存器进行递减操作，同时保持时钟为高电平
    jmp(x_dec, "bitloop")    .side(0x1)
    # 再次输出 1 位数据到 MOSI 引脚，将 SCK 设置为低电平，确保数据发送完成
    # 总共进行8次数据收发，即一个字节数据传输完成
    out(pins, 1)             .side(0x0)
    # 重置 x 寄存器为 6，为下一字节传输做准备
    set(x, 6)                .side(0x0)
    # 从 MISO 引脚读取1位数据并存入输入ISR移位寄存器
    # 将 SCK 设置为高电平，在时钟的上升沿采样数据
    in_(pins, 1)             .side(0x1)

    # 如果 OSR 不为空（尚未达到其阈值），则跳转到 bitloop，继续传输下一个字节
    jmp(not_osre, "bitloop") .side(0x1)

    # 无操作同时设置 SCK 为低电平，形成CS结束的延迟，表示一字节数据传输结束
    nop()                    .side(0x0)   [1]
    # 用于定义循环结束位置
    wrap()

# ======================================== 自定义类 ============================================

# 使用RP2040的PIO（可编程I/O）系统实现的自定义SPI驱动类
class PIOSPI:
    """
    PIOSPI 类，用于通过 PIO 实现 SPI 通信。

    该类封装了基于 RP2040 PIO 的 SPI 通信功能，支持阻塞式读写操作。
    通过 PIO 状态机实现 SPI 协议，适用于需要高效、低延迟的 SPI 通信场景。

    Attributes:
        _sm (StateMachine): PIO 状态机实例，用于实现 SPI 协议。
        _cs (Pin): CS 引脚实例，用于控制 SPI 设备的片选信号。

    Methods:
        __init__(self, sm_id, pin_mosi, pin_sck, pin_miso=None, pin_cs=None, cpha=False, cpol=False, freq=1000000):
            初始化 PIOSPI 类实例。

        write(self, wdata: list[int]) -> None:
            阻塞式写入数据到 SPI 设备。

        read(self, n: int) -> list[int]:
            阻塞式从 SPI 设备读取数据。

        write_read(self, wdata: list[int]) -> list[int]:
            阻塞式写入并读取 SPI 设备数据。
    """
    def __init__(self, sm_id: int, pin_mosi: int, pin_sck: int, pin_miso: int = None, pin_cs: int = None, cpha: bool = False, cpol: bool = False, freq: int = 1000000):
        """
        初始化 PIOSPI 类实例。

        Args:
            sm_id (int): 状态机编号。
            pin_mosi (int): MOSI 引脚编号。
            pin_sck (int): SCK 引脚编号。
            pin_miso (int): MISO 引脚编号，可选。
            pin_cs (int): CS 引脚编号，可选。
            cpha (bool): 时钟相位，默认为 False。
            cpol (bool): 时钟极性，默认为 False。
            freq (int): 时钟频率，默认为 1000000 Hz。

        Raises:
            AssertionError: 如果 cpol 或 cpha 不为 False。
        """
        # 确保仅使用 CPHA=0 和 CPOL=0（不支持反相时钟信号或其他相位）
        assert(not(cpol or cpha))

        # 判断pin_mosi编号和pin_sck编号是否相邻，并且pin_mosi编号小于pin_sck编号
        if not (pin_mosi == pin_sck - 1 or pin_mosi == pin_sck + 1):
            raise AssertionError('pin_mosi must be adjacent to pin_sck')

        # 创建了一个状态机对象 _sm,并将其激活，状态机程序为 spi_cpha0,频率为 4*freq
        self._sm = StateMachine(sm_id, spi_cpha0, freq=4*freq, sideset_base=Pin(pin_sck), out_base=Pin(pin_mosi), in_base=Pin(pin_miso))

        # 初始化 CS 引脚（如果提供）
        self._cs = Pin(pin_cs, Pin.OUT) if pin_cs is not None else None
        if self._cs:
            # 初始状态为高电平（未选中）
            self._cs.value(1)

        # 激活状态机
        self._sm.active(1)

    def write(self, wdata: list[int]) -> None:
        """
        阻塞式写入数据到 SPI 设备。

        Args:
            wdata (list[int]): 要写入的数据列表，每个元素为 8 位数据。

        Returns:
            None
        """
        # 拉低 CS 引脚
        if self._cs:
            self._cs.value(0)

        # 将每个字节左移 24 位后放入状态机的输出 FIFO
        for b in wdata:
            self._sm.put(b << 24)

        # 拉高 CS 引脚
        if self._cs:
            self._cs.value(1)

    def read(self, n: int) -> list[int]:
        """
        阻塞式从 SPI 设备读取数据。

        Args:
            n (int): 需要读取的数据字节数。

        Returns:
            list[int]: 读取的数据列表，每个元素为 8 位数据。
        """
        # 拉低 CS 引脚
        if self._cs:
            self._cs.value(0)
        data = []

        # 清空RX FIFO
        self._sm.restart()

        for i in range(n):
            # 取数据的前16位
            data.append(self._sm.get() & 0xff)

        # 拉高 CS 引脚
        if self._cs:
            self._cs.value(1)

        return data

    def write_read(self, wdata: list[int]) -> list[int]:
        """
        阻塞式写入并读取 SPI 设备数据。

        Args:
            wdata (list[int]): 要写入的数据列表，每个元素为 8 位数据。

        Returns:
            list[int]: 读取的数据列表，每个元素为 8 位数据。
        """
        # 拉低 CS 引脚
        if self._cs:
            self._cs.value(0)
        rdata = []

        # 清空RX FIFO
        self._sm.restart()

        for b in wdata:
            # 将每个字节左移 24 位后放入状态机的输出 FIFO
            self._sm.put(b << 24)
            # 取数据的前16位
            rdata.append(self._sm.get() & 0xff)

        # 拉高 CS 引脚
        if self._cs:
            self._cs.value(1)

        return rdata

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================