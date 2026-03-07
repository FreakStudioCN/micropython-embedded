# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/9/8 上午11:04   
# @Author  : 李清水            
# @File    : main.py       
# @Description : DMA类实验，外设到内存传输，DMA从ADC外设的FIFO传输数据到内存

# ======================================== 导入相关模块 =========================================

# 导入时间相关模块
import time
# 导入自定义ADC DMA类
from dma_adc_trans import DMA_ADC_Transfer
# 导入自定义串口DMA传输类
from dma_uart_tx import DMA_UART_Tx
# 导入micropython相关的模块
import micropython
# 导入硬件相关模块
from machine import Timer

# ======================================== 全局变量 ============================================

# 数据缓冲区：256个元素，每个元素8位（1个字节）
buf1 = bytearray(256)
# 第二个ADC数据缓冲区
buf2 = bytearray(256)

# 串口使用DMA发送数据的运行时间
uart_dma_time = 0
# ADC使用DMA传输数据的运行时间
adc_dma_time = 0

# DMA_ADC_Transfer类实例1对应ADC的DMA和串口的DMA数据传输完毕的标志位
dma_1_adc_complete_flag = False
# DMA_ADC_Transfer类实例2对应ADC的DMA和串口的DMA数据传输完毕的标志位
dma_2_adc_complete_flag = False

# ======================================== 功能函数 ============================================

def adc_wait_dma_complete() -> None:
    """
    等待DMA传输ADC的FIFO中数据完成时调用的函数。

    Args:
        None

    Returns:
        None
    """

    # 打印调试信息
    print("DMA-ADC transmitting ADC data")

def adc_dma_complete_callback(d: object) -> None:
    """
    DMA传输ADC的FIFO中数据完成时调用的函数。

    Args:
        d (object): 使用的DMA通道实例。

    Returns:
        None
    """

    # 打印调试信息
    print("DMA-ADC transfer complete")

def uart_dma_trans_buf1_isr(d: object) -> None:
    """
    DMA传输ADC的FIFO中数据完成时的中断函数，尽快安排对应回调函数执行。

    Args:
        d (object): 使用的DMA通道实例。

    Returns:
        None
    """

    # 安排回调函数在稍后执行
    micropython.schedule(uart_dma_trans_buf1, d)

def uart_dma_trans_buf1(d: object) -> None:
    """
    DMA传输串口数据，读地址为buf1。

    Args:
        d (object): 使用的DMA通道实例。

    Returns:
        None
    """

    # 声明全局变量
    global dma_uart, buf1, dma_1_adc_complete_flag

    # 等待ADC的DMA传输彻底完毕
    while d.active():
        pass

    # 使用DMA传输串口数据，读地址为buf1
    dma_uart.dma_transmit(buf=buf1, blocking=False)
    # 标志位置位
    dma_1_adc_complete_flag = True

def uart_dma_trans_buf2_isr(d: object) -> None:
    """
    DMA传输ADC的FIFO中数据完成时的中断函数，尽快安排对应回调函数执行。

    Args:
        d (object): 使用的DMA通道实例。

    Returns:
        None
    """

    # 安排回调函数在稍后执行
    micropython.schedule(uart_dma_trans_buf2, d)

def uart_dma_trans_buf2(d: object) -> None:
    """
    DMA传输串口数据，读地址为buf2。

    Args:
        d (object): 使用的DMA通道实例。

    Returns:
        None
    """

    # 声明全局变量
    global dma_uart, buf2, dma_2_adc_complete_flag

    # 等待ADC的DMA传输彻底完毕
    while d.active():
        pass

    # 使用DMA传输串口数据，读地址为buf2
    dma_uart.dma_transmit(buf=buf2, blocking=False)
    # 标志位置位
    dma_2_adc_complete_flag = True

# def dma_timer_check(timer: Timer) -> None:
#     """
#     DMA数据传输检查定时器中断函数，检查DMA传输是否完成，
#     如果完成则启动另一个缓冲区的DMA传输。
#
#     Args:
#         timer (machine.Timer): 触发中断的定时器实例。
#
#     Returns:
#         None
#     """
#     global dma_adc_1, dma_adc_2, dma_1_adc_complete_flag, dma_2_adc_complete_flag
#
#     if dma_2_adc_complete_flag:
#         dma_adc_1.start_dma_transfer(blocking=False, complete_callback=uart_dma_trans_buf1_isr)
#         dma_2_adc_complete_flag = False
#
#     if dma_1_adc_complete_flag:
#         dma_adc_2.start_dma_transfer(blocking=False, complete_callback=uart_dma_trans_buf2_isr)
#         dma_1_adc_complete_flag = False

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息，表示开始主程序
print("FreakStudio: DMA Peripheral to Memory Test")

# 初始化DMA_ADC_Transfer类实例，并传入数据缓冲区
dma_adc = DMA_ADC_Transfer(buf = buf1, sample_rate = 2000, adc_id = 0)
# 实例化 DMA_UART_Tx 类，假设使用 UART0，波特率115200，TX引脚为0，RX引脚为1
dma_uart = DMA_UART_Tx(uart_num=0, baudrate=921600, tx_pin=0, rx_pin=1)

# ========================================  主程序  ===========================================

# 记录开始时间
start_time = time.ticks_us()
# 启动DMA传输:阻塞模式，传输未完成时会打印调试信息，传输完成后也会打印调试信息
dma_adc.start_dma_transfer(wait_func = adc_wait_dma_complete,
                           complete_callback = adc_dma_complete_callback,
                           blocking = True)
# 记录结束时间
end_time = time.ticks_us()

# 关闭DMA通道并停止ADC
dma_adc.close()

# 计算DMA数据传输时间
adc_dma_time = time.ticks_diff(end_time, start_time) / 1000

# 打印DMA数据传输时间
print("DMA run time: {:.2f} ms".format(adc_dma_time))

# 打印调试信息
print("FreakStudio: Start DMA UART transmit")

# 串口传输数据，使用DMA
# 传输数据，使用阻塞模式，记录运行时间
uart_dma_time = dma_uart.dma_transmit(buf=buf1,blocking=True) / 1000

# 打印调试数据，表示传输完成
print("DMA UART Finished,run time: {:.2f} ms".format(uart_dma_time))

# 初始化DMA_ADC_Transfer类实例1，并传入数据缓冲区buf1
dma_adc_1 = DMA_ADC_Transfer(buf=buf1, sample_rate=45000, adc_id=0)
# 初始化DMA_ADC_Transfer类实例2，并传入数据缓冲区buf2
dma_adc_2 = DMA_ADC_Transfer(buf=buf2, sample_rate=45000, adc_id=0)

# 首先启动dma_adc_1的DMA传输:非阻塞模式
dma_adc_1.start_dma_transfer(blocking=False,complete_callback = uart_dma_trans_buf1_isr)

# # 初始化软件定时器
# dma_check_timer = Timer(-1)
# # 使用定时器每10ms检查一次DMA传输标志
# dma_check_timer.init(period=10, mode=Timer.PERIODIC, callback=dma_timer_check)

# 轮询开启双缓存不间断数据采集和传输
while True:
    # 记录开始时间
    start_time = time.ticks_us()

    # 判断DMA_ADC_Transfer类实例2的DMA传输是否完成
    if dma_2_adc_complete_flag == True:
        # 启动DMA传输:非阻塞模式
        dma_adc_1.start_dma_transfer(blocking=False,complete_callback = uart_dma_trans_buf1_isr)
        # 标志位不置位
        dma_2_adc_complete_flag = False

    # 判断DMA_ADC_Transfer类实例1的DMA传输是否完成
    if dma_1_adc_complete_flag == True:
        # 启动DMA传输:非阻塞模式
        dma_adc_2.start_dma_transfer(blocking=False,complete_callback = uart_dma_trans_buf2_isr)
        # 标志位不置位
        dma_1_adc_complete_flag = False

    # 记录结束时间
    end_time = time.ticks_us()
    # 计算两次DMA数据传输花费时间
    dma_time = time.ticks_diff(end_time, start_time) / 1000
    # 打印调试数据
    print("DMA ADC run time: {:.2f} ms".format(dma_time))