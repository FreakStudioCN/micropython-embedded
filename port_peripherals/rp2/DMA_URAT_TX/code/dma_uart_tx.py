# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/9/7 下午11:56   
# @Author  : 李清水            
# @File    : dma_uart_tx.py       
# @Description : 自定义UART串口DMA传输

# ======================================== 导入相关模块 =========================================

# 从 rp2 库导入 DMA 控制器
from rp2 import DMA
# 导入时间相关的模块
import time
# 导入硬件相关的模块
from machine import UART
# 导入读写32位内存的模块
from machine import mem32
# 导入 addressof 函数，用于获取数据的内存地址
from uctypes import addressof

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 自定义DMA串口发送类：使用DMA传输数据到UART完成数据发送
class DMA_UART_Tx:
    """
    DMA_UART_Tx类，用于通过DMA（直接内存访问）将数据传输到UART完成数据发送。
    该类封装了DMA和UART的配置与操作，支持8个数据位、无校验位、1个停止位的传输模式。
    默认使用UART0，波特率115200，TX引脚0，RX引脚1。

    Attributes:
        uart_num (int): UART编号，0表示UART0，1表示UART1。
        baudrate (int): 波特率，默认为115200。
        tx_pin (int): TX引脚编号，默认为0。
        rx_pin (int): RX引脚编号，默认为1。
        uart (UART): UART实例，用于配置和操作UART。
        dma (DMA): DMA实例，用于配置和操作DMA。
        UART_BASE (int): UART寄存器基地址。
        UART_UARTDR (int): UART数据寄存器地址。
        UART_UARTFR (int): UART标志寄存器地址。
        UART_UARTDMACR (int): UART DMA控制寄存器地址。

    Methods:
        __init__(self, uart_num=0, baudrate=115200, tx_pin=0, rx_pin=1):
            初始化DMA UART类。
        is_transmit_fifo_full(self):
            检查UART传输FIFO是否已满。
        is_transmit_fifo_empty(self):
            检查UART传输FIFO是否为空。
        is_buffer_protocol(obj):
            判断对象是否为缓冲区协议对象。
        enable_uart_tx_dma(self):
            启用UART发送DMA功能。
        dma_transmit(self, buf, wait_func=None, callback=None, blocking=False):
            使用DMA传输数据到UART。
    """
    def __init__(self, uart_num: int = 0, baudrate: int = 115200, tx_pin: int = 0, rx_pin: int = 1) -> None:
        """
        初始化DMA UART类，暂时只支持8个数据位、无校验位、1个停止位的传输模式。
        默认使用UART0，波特率115200，TX引脚0，RX引脚1。

        Args:
            uart_num (int): 选择UART0或UART1，默认为0。
            baudrate (int): 波特率，默认为115200。
            tx_pin (int): TX引脚编号，默认为0。
            rx_pin (int): RX引脚编号，默认为1。

        Raises:
            ValueError: 如果UART编号或波特率不合法。
        """
        # 检测UART是否可用
        if uart_num not in (0, 1):
            raise ValueError("UART number must be 0 or 1")
        # 检查波特率是不是合法值
        if baudrate not in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            raise ValueError("Invalid baudrate")

        self.uart_num = uart_num
        self.baudrate = baudrate
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin

        # 初始化 UART
        self.uart = UART(self.uart_num, baudrate=self.baudrate, tx=self.tx_pin, rx=self.rx_pin)
        self.uart.init(baudrate=self.baudrate, bits=8, parity=None, stop=1, timeout=100)

        # 初始化 DMA
        self.dma = DMA()

        # 定义 UART 寄存器地址:若是UART0，那么地址为0x40034000，否则为0x40038000
        self.UART_BASE = 0x40034000 if self.uart_num == 0 else 0x40038000

        # UART外设中 UARTDR、UARTFR、UARTCR和UARTDMACR寄存器的相关地址信息
        self.UARTDR_OFFSET = 0x000
        self.UARTFR_OFFSET = 0x018
        self.UARTDMACR_OFFSET = 0x048

        self.UART_UARTDR = self.UART_BASE + self.UARTDR_OFFSET
        self.UART_UARTFR = self.UART_BASE + self.UARTFR_OFFSET
        self.UART_UARTDMACR = self.UART_BASE + self.UARTDMACR_OFFSET

        # 使能DMA传输功能
        self.enable_uart_tx_dma()

    def is_transmit_fifo_full(self) -> bool:
        """
        检查 UART 传输 FIFO 是否已满。

        Returns:
            bool: True 为满，False 为未满。
        """

        # 读取 UARTFR 寄存器的值
        reg_value = mem32[self.UART_UARTFR]
        # 提取 TXFF 位的值 (第 5 位)
        txff_bit = (reg_value >> 5) & 0x1

        # 判断 TXFF 位是否为 1（FIFO 是否已满）
        return txff_bit == 1

    def is_transmit_fifo_empty(self) -> bool:
        """
        检查 UART 传输 FIFO 是否为空。

        Returns:
            bool: True 为空，False 为不为空。
        """

        # 读取 UARTFR 寄存器的值
        reg_value = mem32[self.UART_UARTFR]
        # 提取 TXFE 位的值 (第 7 位)
        txfe_bit = (reg_value >> 7) & 0x1

        # 判断 TXFE 位是否为 1（FIFO 是否为空）
        return txfe_bit == 1

    @staticmethod
    def is_buffer_protocol(obj: object) -> bool:
        """
        判断对象是否为缓冲区协议对象。

        Args:
            obj (object): 传入对象。

        Returns:
            bool: 若为缓冲区协议对象，返回True，否则返回False。
        """
        try:
            # 尝试使用 memoryview 来创建对象的缓冲区视图
            memoryview(obj)
            return True
        except TypeError:
            return False

    def enable_uart_tx_dma(self) -> None:
        """
        启用 UART 发送 DMA 功能，设置 UARTDMACR 寄存器的 TXDMAE 位。
        """
        reg_value = mem32[self.UART_UARTDMACR]
        reg_value |= (1 << 1)
        mem32[self.UART_UARTDMACR] = reg_value

    def dma_transmit(self, buf: object, wait_func: callable = None, callback: callable = None,
                     blocking: bool = False) -> int:
        """
        使用DMA传输数据到UART。

        Args:
            buf (object): 待传输的字节数据，需要为缓冲区协议对象。
            wait_func (callable): 传输进行中时的回调函数，可选。
            callback (callable): 传输完成时的回调函数，可选。
            blocking (bool): 是否阻塞等待传输完成，可选，默认为 False。

        Returns:
            int: 耗时，单位为微秒。

        Raises:
            Exception: 如果非阻塞模式下传入了 wait_func，或者 buf 不是缓冲区协议对象。
        """

        # 如果选择非阻塞模式，那么不应该传入wait_func
        if blocking == False and wait_func is not None:
            raise Exception("Blocking mode should not have wait_func!")

        # 判断buf是否为缓冲区协议对象
        if DMA_UART_Tx.is_buffer_protocol(buf) == False:
            raise Exception("buf must be a buffer protocol object!")

        # 20为DREQ_UARTO_TX请求信号的编号,22为DREQ_UART1_TX请求信号的编号
        UART_DREQ = 20 if self.uart_num == 0 else 22

        # 设置DMA控制寄存器
        ctrl = self.dma.pack_ctrl(enable=True,          # 启用 DMA
                                  size=0,               # 单次数据传输大小8-bit (byte)
                                  inc_read=True,        # 读取地址递增
                                  inc_write=False,      # 写入地址不递增
                                  treq_sel=UART_DREQ    # 设置 DMA 触发信号
                                  )

        # 配置 DMA
        self.dma.config(read=addressof(buf),     # 源地址，即数据缓冲区的内存地址
                        write=self.UART_UARTDR,  # 目标地址，即 UART 数据寄存器的地址
                        count=len(buf),          # 数据传输的字节数
                        ctrl=ctrl,               # DMA 控制寄存器配置
                        trigger=True             # 立即触发 DMA 传输
                        )

        # 记录开始时间
        start_time = time.ticks_us()
        # 启动 DMA 传输
        self.dma.active(1)

        # 阻塞模式，等待 DMA 传输完成
        if blocking == True:
            # 等待 DMA 传输完成
            while self.dma.active():
                # 检查 UARTFR 寄存器的 TXFE 位是否置位
                if not self.is_transmit_fifo_empty():
                    # 如果 TXFE 位不为 1，说明 FIFO 不为空
                    if wait_func is not None:
                        # 执行用户自定义回调函数
                        wait_func()

        if callback is not None:
            # 等待DMA传输完毕，执行用户自定义回调callback
            callback()

        # 记录结束时间
        end_time = time.ticks_us()  # 记录结束时间
        # 返回耗时
        return time.ticks_diff(end_time, start_time)

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================