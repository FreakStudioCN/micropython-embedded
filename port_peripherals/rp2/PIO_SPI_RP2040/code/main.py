# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2024/11/6 下午6:41   
# @Author  : 李清水            
# @File    : main.py       
# @Description : 使用PIO模拟的SPI协议进行数据收发回环测试

# ======================================== 导入相关模块 ========================================

# 导入时间相关模块
import time
# 导入PIO模拟SPI协议相关模块
from pio_spi import PIOSPI

# ======================================== 全局变量 ============================================

# 待发送的字节列表
tx_list = [0, 1, 2, 3, 4, 5, 6, 7]

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 延时等待设备初始化
time.sleep(3)
# 打印调试信息
print('FreakStudio : Using PIO to implement the SPI protocol')

# 初始化SPI类，设置波特率、极性、相位、时钟引脚、数据引脚
# 设置pin_mosi和pin_miso为GP10，pin_sck为GP11，pin_cs为GP12，CPHA为False，CPOL为False，波特率为1000000
# 设置MISO和MOSI引脚相同，进行收发回环测试
spi = PIOSPI(sm_id=0, pin_mosi=10, pin_sck=11, pin_miso=10, pin_cs = 12,cpha=False, cpol=False, freq=1000000)

# ========================================  主程序  ===========================================

# 使用PIO模拟SPI协议收发数据
while True:
    # 发送并读取数据
    data = spi.write_read(tx_list)
    # 打印调试信息
    print('FreakStudio : SPI data received : {}'.format(data))
    # 等待1秒
    time.sleep(1)