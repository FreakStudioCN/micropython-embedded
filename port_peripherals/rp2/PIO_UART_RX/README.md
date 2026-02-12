# PIO实现UART串口接收（RP2040 MicroPython）
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

本项目基于RP2040芯片（如树莓派Pico/Pico W）的MicroPython环境，利用RP2040独有的PIO（可编程I/O）模块实现UART串口异步接收功能。相比传统硬件UART，PIO实现的UART具备更灵活的时序控制能力，可精准匹配UART通信协议（8位数据位、1位起始位、1位停止位），适用于对串口接收时序有定制化需求的场景。

## 主要功能

1. 基于PIO状态机实现UART串口接收，兼容标准UART异步通信协议；
2. 支持串口帧错误/停止位错误检测，并通过中断机制触发错误处理；
3. 提供单字节读取接口，集成计时装饰器可监控函数运行时间；
4. 提供字符串读取接口，支持自定义终止符和最大长度限制，防止缓冲区溢出；
5. 模块化设计，核心功能与主程序解耦，便于扩展和维护。

## 文件说明

| 文件名          | 功能说明                                                                 |
|-----------------|--------------------------------------------------------------------------|
| `pio_uart_rx.py` | 核心功能实现文件，包含：<br> - 计时装饰器（统计函数运行时间）<br> - PIO UART接收程序（状态机逻辑）<br> - 中断处理函数（帧错误/停止位错误）<br> - 单字节/字符串读取函数 |
| `main.py`       | 主程序文件，包含：<br> - 引脚、波特率等参数配置<br> - PIO状态机初始化与激活<br> - 循环读取串口字符串并打印 |

## 软件设计核心思想

1. **PIO时序精准控制**：将PIO状态机时钟频率设为8倍UART波特率，通过PIO指令精准匹配UART异步接收时序（等待起始位→循环读取8位数据→校验停止位），保证数据接收的准确性；
2. **分层设计思想**：底层实现单字节读取（带计时），上层封装字符串读取逻辑（支持终止符和长度限制），适配不同场景的接收需求；
3. **鲁棒性设计**：通过中断处理帧错误/停止位错误，防止无效数据干扰；设置最大字符串长度，避免无限阻塞；接收引脚配置上拉输入，防止浮空误触发；
4. **性能监控**：集成计时装饰器，可统计关键函数（如单字节读取）的运行时间，便于后续性能调优。

## 使用说明

### 硬件环境

- 主控芯片：RP2040（树莓派Pico/Pico W等）
- 外设：外部UART发送设备（需与RP2040电平匹配，建议3.3V）
- 引脚连接：外部UART发送端（TX）连接到RP2040的GP1引脚

### 软件环境

- MicroPython版本：v1.23.0及以上
- 开发工具：支持RP2040 MicroPython的编辑器（如Thonny、VSCode+PyMakr）

### 部署步骤

1. 将`pio_uart_rx.py`和`main.py`上传到RP2040设备；
2. 确认外部UART设备的波特率为115200（或修改`main.py`中`UART_BAUD`常量适配）；
3. 运行`main.py`，RP2040将开始监听GP1引脚的UART数据。

## 示例程序

以下为核心示例代码（对应`main.py`），实现PIO UART初始化及循环读取字符串：

```python
import time
from rp2 import PIO, StateMachine, asm_pio
from machine import Pin, UART
import pio_uart_rx

# 配置参数
UART_BAUD = 115200
PIO_RX_PIN_NUM = 1
UART_TERMINATOR = '\r'
UART_MAX_STR_LEN = 128

# 初始化引脚
pio_rx_pin = Pin(PIO_RX_PIN_NUM, Pin.IN, Pin.PULL_UP)

# 创建并激活PIO状态机
sm = StateMachine(
    0,
    pio_uart_rx.uart_rx,
    freq=8 * UART_BAUD,
    in_base=pio_rx_pin,
    jmp_pin=pio_rx_pin
)
sm.irq(pio_uart_rx.uart_break_handler)
sm.active(1)

# 循环读取并打印串口数据
while True:
    received_str = pio_uart_rx.pio_uart_read_string(sm)
    print("Received String: {}".format(received_str))
```

运行后，RP2040会持续读取GP1引脚的UART数据，直到接收到终止符`\r`，并打印完整字符串。

## 注意事项

1. **波特率匹配**：PIO状态机频率必须设为8倍UART波特率，否则会导致时序错误，无法正确接收数据；
2. **引脚配置**：接收引脚必须配置为上拉输入（`Pin.PULL_UP`），避免引脚浮空导致的误触发；
3. **终止符与长度**：默认终止符为`\r`（回车）、最大字符串长度为128字节，可根据实际需求修改`UART_TERMINATOR`和`UART_MAX_STR_LEN`常量；
4. **电平匹配**：RP2040为3.3V电平，与5V串口设备通信时需增加电平转换模块，避免芯片损坏；
5. **错误处理**：若终端打印`Recv Break/Frame Error`，需检查串口通信时序、波特率或硬件连接。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

本项目采用MIT开源许可协议，您可以自由使用、修改和分发本项目代码，具体协议如下：

```
MIT License

Copyright (c) 2025 FreakStudioCN

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
