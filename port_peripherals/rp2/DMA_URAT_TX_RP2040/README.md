# RP2040 DMA驱动ADC采集与UART发送
## 目录
- [简介](#简介)
- [主要功能](#主要功能)
- [文件说明](#文件说明)
- [软件设计核心思想](#软件设计核心思想)
- [使用说明](#使用说明)
- [示例程序](#示例程序)
- [注意事项](#注意事项)
- [联系方式](#联系方式)
- [许可协议](#许可协议)

## 简介

本项目基于MicroPython v1.23.0开发，面向树莓派Pico（RP2040）平台，实现了**DMA驱动的ADC高速数据采集**和**UART串口DMA数据发送**功能。通过直接操作硬件寄存器，完成外设到内存（ADC→内存缓冲区）、内存到外设（内存缓冲区→UART）的DMA（直接内存访问）传输，大幅降低CPU占用率，支持高速采样、双缓存不间断采集传输等特性，适用于需要高频数据采集与串口传输的场景。

## 主要功能

1. **ADC DMA高速采集**
   - 支持ADC 0/1/2通道配置，采样率可配置（≥1000Hz，最高适配48MHz ADC时钟）；
   - 启用ADC自由采样模式与FIFO缓冲区，配合DMA触发实现数据自动传输；
   - 支持阻塞/非阻塞传输模式，自定义传输等待函数、传输完成回调函数；
   - 精准控制ADC时钟分频，保证采样率准确性。

2. **UART DMA高效发送**
   - 支持UART0/UART1配置，兼容9600~921600bps标准波特率；
   - 直接操作UART寄存器，启用DMA发送功能，支持FIFO状态检测；
   - 兼容缓冲区协议对象（bytearray/bytes等），支持阻塞/非阻塞传输模式；
   - 低CPU占用，实现大批量数据高速串口发送。

3. **双缓存不间断采集传输**
   - 基于双缓冲区（buf1/buf2）实现ADC数据不间断采集；
   - 缓冲区交替完成“采集-发送”流程，避免数据丢失；
   - 中断调度机制确保回调函数安全执行，保证实时性。

4. **灵活的回调机制**
   - 支持传输过程中自定义等待函数（阻塞模式下）；
   - 传输完成回调函数支持中断级调度，适配实时性要求高的场景。

## 文件说明

| 文件名              | 功能说明                                                                 |
|---------------------|--------------------------------------------------------------------------|
| `dma_adc_trans.py`  | 自定义ADC DMA传输类（`DMA_ADC_Transfer`），封装ADC配置、FIFO控制、DMA传输、采样率配置、资源释放等核心功能。 |
| `dma_uart_tx.py`    | 自定义UART DMA发送类（`DMA_UART_Tx`），封装UART初始化、DMA使能、FIFO状态检测、DMA数据传输等功能。|
| `main.py`           | 主程序示例，演示单缓冲区ADC DMA采集+UART DMA发送、双缓存不间断采集传输的完整流程，包含回调函数、中断调度等逻辑。 |

## 软件设计核心思想

1. **硬件寄存器直接操作**：通过`mem32`模块读写RP2040的ADC/UART寄存器，精准配置FIFO阈值、DMA触发源、时钟分频等关键参数，实现底层硬件精准控制。
2. **DMA解耦CPU与外设**：利用DMA控制器接管“外设-内存”数据传输，CPU仅需初始化配置和处理传输回调，大幅降低CPU占用率，适配高速数据传输场景。
3. **模块化封装**：将ADC DMA、UART DMA功能分别封装为独立类，降低模块耦合性，提高代码复用性与可维护性。
4. **双缓存机制**：通过两个缓冲区交替执行“采集”和“发送”操作，实现ADC数据不间断采集，避免单缓冲区模式下的采集中断。
5. **安全的中断处理**：基于`micropython.schedule`实现中断回调调度，避免中断上下文执行复杂逻辑导致的系统异常。

## 使用说明

### 环境准备

- **硬件**：树莓派Pico（RP2040）开发板；
- **软件**：烧录MicroPython v1.23.0固件至Pico开发板；
- **依赖**：无第三方库依赖，仅使用MicroPython内置模块（`machine`/`rp2`/`uctypes`等）。

### 部署与运行

1. 将`dma_adc_trans.py`、`dma_uart_tx.py`、`main.py`上传至Pico开发板；
2. 通过串口终端（如Thonny、Putty）连接Pico，执行`main.py`；
3. 终端输出DMA传输耗时、状态等调试信息，观察ADC采集与UART发送流程。

### 自定义配置

- **ADC采样率**：初始化`DMA_ADC_Transfer`时修改`sample_rate`参数（≥1000Hz）；
- **UART参数**：初始化`DMA_UART_Tx`时修改`uart_num`（0/1）、`baudrate`（标准波特率）、`tx_pin`/`rx_pin`；
- **缓冲区大小**：修改`main.py`中`buf1`/`buf2`的`bytearray`长度，适配不同数据量需求。

## 示例程序

### 1. 单缓冲区ADC DMA采集 + UART DMA发送

```python
import time
from dma_adc_trans import DMA_ADC_Transfer
from dma_uart_tx import DMA_UART_Tx

# 初始化缓冲区
buf = bytearray(256)

# 初始化ADC DMA（采样率2000Hz，ADC0）
dma_adc = DMA_ADC_Transfer(buf=buf, sample_rate=2000, adc_id=0)
# 初始化UART DMA（UART0，921600bps，TX=0，RX=1）
dma_uart = DMA_UART_Tx(uart_num=0, baudrate=921600, tx_pin=0, rx_pin=1)

# 阻塞模式启动ADC DMA采集
start_time = time.ticks_us()
dma_adc.start_dma_transfer(blocking=True)
adc_time = time.ticks_diff(time.ticks_us(), start_time) / 1000
print(f"ADC DMA采集耗时：{adc_time:.2f} ms")

# 阻塞模式启动UART DMA发送
uart_time = dma_uart.dma_transmit(buf=buf, blocking=True) / 1000
print(f"UART DMA发送耗时：{uart_time:.2f} ms")

# 释放资源
dma_adc.close()
```

### 2. 双缓存不间断采集传输（核心逻辑）

```python
# 初始化双缓冲区
buf1 = bytearray(256)
buf2 = bytearray(256)

# 初始化两个ADC DMA实例
dma_adc_1 = DMA_ADC_Transfer(buf=buf1, sample_rate=45000, adc_id=0)
dma_adc_2 = DMA_ADC_Transfer(buf=buf2, sample_rate=45000, adc_id=0)

# 初始化UART DMA
dma_uart = DMA_UART_Tx(uart_num=0, baudrate=921600, tx_pin=0, rx_pin=1)

# 标记位初始化
dma_1_complete = False
dma_2_complete = True  # 初始启动dma_adc_1

# 双缓存轮询采集
while True:
    if dma_2_complete:
        # 启动buf1采集（非阻塞），完成后触发UART发送回调
        dma_adc_1.start_dma_transfer(blocking=False, complete_callback=uart_send_buf1)
        dma_2_complete = False
    if dma_1_complete:
        # 启动buf2采集（非阻塞），完成后触发UART发送回调
        dma_adc_2.start_dma_transfer(blocking=False, complete_callback=uart_send_buf2)
        dma_1_complete = False
```

## 注意事项

1. **采样率限制**：ADC采样率需≥1000Hz（低于该值会抛出异常），低采样率场景建议使用软件定时器替代DMA；
2. **硬件兼容性**：仅适配RP2040（树莓派Pico）平台，依赖RP2040的ADC/UART/DMA寄存器地址与DREQ触发号，不兼容其他MCU；
3. **缓冲区类型**：ADC DMA的缓冲区必须为`bytearray`类型，UART DMA支持所有符合缓冲区协议的对象（bytearray/bytes/array等）；
4. **波特率限制**：UART仅支持9600/19200/38400/57600/115200/230400/460800/921600bps标准波特率；
5. **资源释放**：ADC DMA使用完毕后需调用`close()`方法，释放DMA通道并停止ADC采样，避免硬件资源泄漏；
6. **中断安全**：回调函数需保证轻量化，复杂逻辑建议通过`micropython.schedule`调度至主线程执行。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

```
MIT License

Copyright (c) 2026 FreakStudio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
