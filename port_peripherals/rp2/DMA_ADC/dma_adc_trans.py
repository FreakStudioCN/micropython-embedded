# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/9/8 下午11:15   
# @Author  : 李清水            
# @File    : dma_adc_trans.py.py       
# @Description : 自定义ADC数据采集DMA传输类

# ======================================== 导入相关模块 =========================================

# 导入硬件相关模块
from machine import ADC
# 导入 addressof 函数，用于获取数据的内存地址
from uctypes import addressof
# 导入DMA相关模块
from rp2 import DMA
# 导入读写32位内存的模块
from machine import mem32

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 自定义ADC类，通过DMA进行数据传输
class DMA_ADC_Transfer:
    """
    DMA_ADC_Transfer 类，用于通过 DMA 进行高效的 ADC 数据传输。
    该类封装了 ADC 配置、DMA 传输、FIFO 控制等功能，实现高速采样并存入用户提供的缓冲区。

    该类支持自由采样模式，并可配置 ADC 采样率，同时提供阻塞和非阻塞模式进行 DMA 传输。

    Attributes:
        buf (bytearray): 用于存储 ADC 采样数据的缓冲区。
        sample_rate (int): 期望的 ADC 采样率 (Hz)。
        adc (ADC): ADC 实例对象，用于进行模数转换。
        dma (DMA): DMA 控制器实例对象。

    Constants:
        DREQ_ADC (int): ADC 的 DMA 触发信号 ID。
        ADC_BASE (int): ADC FIFO 寄存器的基地址。
        CS_REG (int): 控制寄存器 (CS) 的地址偏移。
        RESULT_REG (int): 结果寄存器 (RESULT) 的地址偏移。
        FCS_REG (int): FIFO 控制寄存器 (FCS) 的地址偏移。
        DIV_REG (int): 采样分频寄存器 (DIV) 的地址偏移。
        FIFO_REG (int): FIFO 数据寄存器 (FIFO) 的地址偏移。
        FIFO_THRESH (int): ADC FIFO 触发 DMA 传输的阈值。
        ADC_CLOCK_FREQ (int): ADC 时钟频率，假设为 48MHz。

    Methods:
        __init__(self, buf: bytearray, sample_rate: int = 1000, adc_id: int = 0):
            初始化 DMA_ADC_Transfer 类的实例，并配置 ADC 与 DMA。

        configure_adc_fifo(self) -> None:
            配置 ADC FIFO，使其能够配合 DMA 进行数据传输。

        start_adc_continuous(self) -> None:
            启动 ADC 自由采样模式，使其持续采集数据。

        configure_adc_sample_rate(self, sample_rate: int) -> None:
            配置 ADC 采样率，并设置相应的时钟分频。

        stop_dma_adc_fifo(self) -> None:
            停止 DMA 传输和 ADC 采样，确保采样过程安全结束。

        start_dma_transfer(self, wait_func: callable = None, complete_callback: callable = None, blocking: bool = True) -> None:
            启动 DMA 传输，并可选择是否阻塞等待完成或指定传输完成回调。

        close(self) -> None:
            关闭 DMA 传输，并释放 ADC 资源。
    """

    # ADC的DMA触发信号
    DREQ_ADC = 36

    # ADC FIFO寄存器的基地址
    ADC_BASE = 0x4004C000
    # CS 寄存器偏移量为0x00
    CS_REG = ADC_BASE + 0x00
    # RESULT 寄存器偏移量为0x04
    RESULT_REG = ADC_BASE + 0x04
    # FIFO 控制寄存器偏移量为0x08
    FCS_REG = ADC_BASE + 0x08
    # DIV 寄存器偏移量为0x10
    DIV_REG = ADC_BASE + 0x10
    # FIFO 寄存器偏移量为0x0C
    FIFO_REG = ADC_BASE + 0x0C

    # ADC的 FIFO 阈值
    FIFO_THRESH = 1

    # ADC 时钟频率，假设为48MHz
    ADC_CLOCK_FREQ = 48_000_000

    def __init__(self, buf: bytearray, sample_rate: int = 1000, adc_id: int = 0) -> None:
        """
        初始化DMA_ADC_Transfer类的实例。

        Args:
            buf (bytearray): 用户传入的数据缓冲区。
            sample_rate (int): 期望的采样率 (Hz)，默认为1000。
            adc_id (int): ADC的ID号（0、1或2），默认为0。

        Raises:
            TypeError: 如果buf不是bytearray类型。
            ValueError: 如果adc_id不是0、1或2，或者采样率超出范围。
        """
        # 判断buf是否为bytearray类型
        if not isinstance(buf, bytearray):
            raise TypeError("buf must be bytearray")

        # 判断adc_id是否为0、1或2
        if adc_id not in (0, 1, 2):
            raise ValueError("adc_id must be 0, 1 or 2")

        # 缓冲区：用户传入的缓冲区
        self.buf = buf
        # 采样率
        self.sample_rate = sample_rate
        # 创建ADC对象
        self.adc = ADC(adc_id)
        # 创建DMA通道对象
        self.dma = DMA()
        # 配置ADC的FIFO
        self.configure_adc_fifo()
        # 配置ADC采样率
        self.configure_adc_sample_rate(self.sample_rate)
        # 启动自由采样模式
        self.start_adc_continuous()

    def configure_adc_fifo(self) -> None:
        """
        配置ADC的FIFO，与DMA控制器相配合。
        默认FIFO右移4位，即ADC数据为8位，最大值为255。

        Returns:
            None
        """
        # 启用FIFO (FCS.EN), 启用DMA请求信号 (FCS.DREQ_EN), 设置FIFO右移 (FCS.SHIFT)
        fcs_value = mem32[DMA_ADC_Transfer.FCS_REG]
        mem32[DMA_ADC_Transfer.FCS_REG] = fcs_value | (1 << 0) | (1 << 3) | (1 << 1)
        # 设置FIFO阈值 (FCS.THRESH)
        mem32[DMA_ADC_Transfer.FCS_REG] |= (DMA_ADC_Transfer.FIFO_THRESH << 24)

    def start_adc_continuous(self) -> None:
        """
        启动自由采样模式，使能START_MANY数据位。
        ADC将自动以固定的间隔启动新的转换。

        Returns:
            None
        """
        # 读取 CS 寄存器的当前值
        cs_value = mem32[DMA_ADC_Transfer.CS_REG]
        # 设置 START_MANY 位为1
        mem32[DMA_ADC_Transfer.CS_REG] = cs_value | (1 << 3)

    def configure_adc_sample_rate(self, sample_rate: int) -> None:
        """
        配置ADC采样率。

        Args:
            sample_rate (int): 期望的采样率 (Hz)。

        Returns:
            None

        Raises:
            ValueError: 如果采样率超出范围。
        """
        # 确保采样率在合理范围内
        if sample_rate <= 0 or sample_rate > 48_000_000:
            raise ValueError("sample rate out of range")

        # 采样率在1000Hz以上时，才能充分发挥DMA的作用
        # 若采样率在1000Hz以下，使用普通软件定时器定时采样即可
        if sample_rate < 1000:
            raise ValueError("sample rate too low")

        # 计算分频器值
        total_period = 48_000_000 / sample_rate
        int_part = int(total_period) - 1
        frac_part = int((total_period - int_part - 1) * 256)

        # 写入采样周期到DIV寄存器
        mem32[DMA_ADC_Transfer.DIV_REG] = (int_part << 8) | frac_part

    def stop_dma_adc_fifo(self) -> None:
        """
        停止DMA传输和ADC转换。

        Returns:
            None
        """
        # 清除 CS 寄存器中的 START_MANY 位，以停止 ADC 转换
        # 读取 CS 寄存器
        adc_cs_value = mem32[DMA_ADC_Transfer.CS_REG]
        # 清除 START_MANY 位
        adc_cs_value &= ~(1 << 3)
        # 写回 CS 寄存器
        mem32[DMA_ADC_Transfer.CS_REG] = adc_cs_value

        # 轮询 READY 位，确保最后一次转换已完成
        while not ((mem32[DMA_ADC_Transfer.CS_REG]>>8) & 0x1):
            pass

    def start_dma_transfer(self, wait_func: callable = None, complete_callback: callable = None, blocking: bool = True) -> None:
        """
        启动DMA传输。

        Args:
            wait_func (callable): 等待DMA传输完成时调用的函数，可选。
            complete_callback (callable): DMA传输完成回调函数，可选。
            blocking (bool): 是否阻塞等待传输完成，默认为True。

        Returns:
            None

        Raises:
            ValueError: 如果非阻塞模式下传入了wait_func。
        """

        # 如果选择非阻塞模式，那么不应该传入wait_func
        if blocking == False and wait_func is not None:
            raise ValueError("wait_func must be None when blocking is False")

        # 若是 complete_callback 不为空，则执行用户自定义函数
        if complete_callback is not None:
            # 传输完成中断回调函数
            self.dma.irq(handler=complete_callback, hard=True)

        # 设置DMA控制寄存器
        ctrl = self.dma.pack_ctrl(
            enable=True,                         # 启用 DMA
            size=0,                              # 单次数据传输大小8-bit，单字节传输
            inc_read=False,                      # 读取地址不递增
            inc_write=True,                      # 写入地址递增
            treq_sel=DMA_ADC_Transfer.DREQ_ADC,  # 选择DMA触发源
            irq_quiet = False                    # 在每次传输结束时生成中断
        )

        # 配置DMA通道
        self.dma.config(
            read=self.FIFO_REG,         # 源地址，即ADC外设FIFO寄存器地址
            write=addressof(self.buf),  # 目标地址，即数据缓冲区地址
            count=len(self.buf),        # 数据传输总次数
            ctrl=ctrl,                  # DMA 控制寄存器配置
            trigger=False               # 不立即触发 DMA 传输
        )

        # 启动 DMA 传输
        self.dma.active(1)

        # 阻塞模式，等待 DMA 传输完成
        if blocking == True:
            # 等待DMA执行完毕
            while self.dma.active():
                # 若是 wait_func 不为空，则执行用户自定义函数
                if wait_func is not None:
                    # 执行用户自定义函数
                    wait_func()
        else:
            # 非阻塞模式，不等待DMA执行完毕
            return

    def close(self) -> None:
        """
        关闭DMA通道，并停止ADC。

        Returns:
            None
        """
        # 释放DMA通道占用
        self.dma.close()
        # 停止ADC转换
        self.stop_dma_adc_fifo()

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================