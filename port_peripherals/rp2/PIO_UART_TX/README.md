# RP2040 PIO 实现 UART 串口通信实验
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
本项目基于 MicroPython v1.23.0 开发，针对树莓派 RP2040 芯片，实现了**PIO（Programmable I/O）自定义程序模拟 UART 串口发送**功能，并与 RP2040 硬件 UART 外设的发送功能进行对比。通过该实验可深入理解 PIO 状态机的工作原理，以及 UART 串口通信的底层时序实现逻辑。

## 主要功能
1. 基于 PIO 状态机实现 UART 串口发送（TX）功能，严格遵循 UART 通信时序（起始位、8 位数据位、1 位停止位）；
2. 基于 RP2040 硬件 UART 外设实现串口发送功能；
3. 提供计时装饰器，精准统计 PIO 串口发送和硬件 UART 发送函数的运行时间；
4. 主程序周期性（1 秒）发送指定字符串，对比两种串口发送方式的执行效率。

## 文件说明
| 文件名 | 功能说明 |
|--------|----------|
| `main.py` | 项目主程序，包含全局变量定义、计时装饰器、硬件 UART 初始化/发送函数、PIO 状态机初始化，以及主循环（周期性触发两种串口发送逻辑） |
| `pio_uart_tx.py` | PIO 串口发送核心实现，包含 `uart_tx` PIO 汇编程序（定义 UART 发送时序）、`pio_uart_print` 函数（封装 PIO 发送字符串逻辑），以及复用的计时装饰器 |

## 软件设计核心思想
### 1. PIO 实现 UART TX 核心逻辑
通过 `@asm_pio` 装饰器编写 PIO 汇编程序 `uart_tx`，模拟 UART 发送时序：
- **起始位**：拉低引脚电平，持续 1 个波特率周期；
- **数据位**：循环 8 次，逐位将字符数据从 OSR（输出移位寄存器）输出到引脚，每次输出后延时匹配波特率时序；
- **停止位**：拉高引脚电平，持续 1 个波特率周期；
- 状态机频率配置为 `8 * UART_BAUD`，通过指令周期延时（如 `[7]` `[6]`）匹配 UART 波特率时序。

### 2. 计时装饰器设计
通用计时装饰器 `timed_function`，通过 `time.ticks_us()` 记录函数执行前后的时间戳，计算时间差并打印，用于对比 PIO 串口和硬件 UART 的发送耗时。

### 3. 程序架构
- 初始化阶段：创建并启动 PIO 状态机、初始化硬件 UART 外设；
- 主循环阶段：每秒触发一次 PIO 串口发送和硬件 UART 发送，通过计时装饰器输出各自耗时，直观对比两种方式的效率。

## 使用说明
### 硬件要求
- 树莓派 RP2040 开发板（如 Raspberry Pi Pico/Pico W）；
- 串口调试工具（如 USB-TTL 模块），用于接收串口数据（硬件 UART 接 TX0/引脚0，PIO UART 接引脚4）。

### 环境要求
- MicroPython v1.23.0 固件（烧录至 RP2040 开发板）。

### 操作步骤
1. 将 `main.py` 和 `pio_uart_tx.py` 上传至 RP2040 开发板；
2. 硬件接线：
   - 硬件 UART TX：RP2040 引脚 0 → USB-TTL 模块 RX；
   - PIO UART TX：RP2040 引脚 4 → USB-TTL 模块 RX；
   - USB-TTL 模块与电脑连接，打开串口调试工具（波特率 115200、8 位数据位、无校验、1 位停止位）；
3. 运行 `main.py`，串口调试工具将每秒接收到两行 `UART TX DATA`（分别来自 PIO 串口和硬件 UART），开发板串口终端会打印两个发送函数的运行时间。

## 示例程序
### 核心代码片段（main.py 主逻辑）
```python
# 初始化PIO状态机
sm = StateMachine(0, pio_uart_tx.uart_tx, freq=8 * UART_BAUD, sideset_base=Pin(PIN_BASE), out_base=Pin(PIN_BASE))
sm.active(1)

# 初始化硬件UART
uart = UART(0, UART_BAUD)
uart.init(baudrate=UART_BAUD, bits=8, parity=None, stop=1, tx=0, rx=1, timeout=100)

# 主循环
while True:
    time.sleep(1)
    # PIO UART发送
    pio_uart_tx.pio_uart_print(sm, "UART TX DATA\r\n")
    # 硬件UART发送
    hardware_uart_print(uart, "UART TX DATA\r\n")
```

### 运行效果
串口终端会周期性输出类似以下内容（显示函数运行时间）：
```
Function pio_uart_print Time =  0.120ms
Function hardware_uart_print Time =  0.080ms
```
串口调试工具每秒接收两行 `UART TX DATA`。

## 注意事项
1. **MicroPython 版本**：项目基于 MicroPython v1.23.0 开发，低版本可能存在 PIO 指令或 UART API 兼容问题；
2. **引脚冲突**：硬件 UART 使用引脚 0（TX）/1（RX），PIO UART 使用引脚 4，需确保这些引脚未被其他外设占用；
3. **状态机频率**：PIO 状态机频率必须配置为 `8 * UART_BAUD`，否则会导致 UART 时序错误；
4. **波特率限制**：当前配置为 115200 波特率，修改波特率时需同步调整 PIO 状态机频率和指令延时；
5. **串口阻塞**：硬件 UART 发送后通过 `uart.txdone()` 阻塞等待发送完成，确保数据完整发送。

## 联系方式
如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议
本项目采用 MIT 开源许可协议，您可以自由使用、修改、分发本项目代码，具体协议内容如下：

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