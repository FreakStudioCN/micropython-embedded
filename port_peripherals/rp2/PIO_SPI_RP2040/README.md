# PIO实现SPI协议通信
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

本项目基于RP2040微控制器的可编程I/O（PIO）模块，采用MicroPython v1.23.0实现SPI串行通信协议，重点实现了CPHA=0、CPOL=0模式下的8位数据传输。项目封装了通用的PIOSPI类，支持阻塞式的SPI写、读、写读操作，并提供了数据收发回环测试的示例程序，适用于需要高效、低延迟SPI通信的场景。

## 主要功能

1. 基于RP2040 PIO状态机实现SPI协议（CPHA=0、CPOL=0），支持8位字节数据传输；
2. 封装PIOSPI类，提供简洁的SPI通信接口，包括`write`（仅写）、`read`（仅读）、`write_read`（写读）阻塞式操作；
3. 支持自定义SPI时钟频率、片选（CS）引脚、MOSI/SCK/MISO引脚；
4. 提供SPI数据收发回环测试示例，验证通信功能的正确性。

## 文件说明

| 文件名      | 功能说明                                                                 |
|-------------|--------------------------------------------------------------------------|
| pio_spi.py  | 核心实现文件，包含SPI协议的PIO汇编程序（`spi_cpha0`）、PIOSPI类的封装，实现SPI底层通信逻辑 |
| main.py     | 测试示例文件，初始化PIOSPI类并执行SPI数据收发回环测试，循环打印接收数据       |

## 软件设计核心思想

1. **PIO程序设计**：通过`@asm_pio`装饰器编写汇编级PIO程序，配置自动拉取（autopull）、自动推送（autopush）、移位阈值为8位，适配8位字节传输；利用侧集（sideset）引脚控制SCK时钟电平，通过`out`指令输出MOSI数据、`in_`指令读取MISO数据，结合寄存器x实现8位数据的循环传输；
2. **类封装思想**：PIOSPI类封装PIO状态机的初始化、激活、数据收发逻辑，对外暴露简洁的读写接口，屏蔽底层PIO操作细节；
3. **时序匹配**：严格遵循CPHA=0、CPOL=0的SPI时序规则，在时钟下降沿输出MOSI数据，上升沿采样MISO数据，保证数据传输的准确性。

## 使用说明

### 环境要求

- 硬件：RP2040开发板（如Raspberry Pi Pico）；
- 软件：MicroPython v1.23.0固件。

### 硬件接线

- 回环测试：将MOSI引脚（示例为GP10）与MISO引脚（示例为GP10）短接（同一引脚）；
- 常规使用：根据需求连接MOSI、SCK、MISO、CS引脚到外设，确保MOSI与SCK引脚相邻；
- 示例接线：MOSI(GP10)、SCK(GP11)、CS(GP12)，MISO与MOSI短接（回环测试）。

### 部署与运行

1. 将`pio_spi.py`和`main.py`上传到RP2040开发板；
2. 复位开发板或直接执行`main.py`；
3. 查看串口输出，验证SPI数据收发结果。

## 示例程序

以下是核心的回环测试示例（对应`main.py`）：

```python
# 导入依赖模块
import time
from pio_spi import PIOSPI

# 待发送的测试数据
tx_list = [0, 1, 2, 3, 4, 5, 6, 7]

# 延时等待设备初始化
time.sleep(3)
print('FreakStudio : Using PIO to implement the SPI protocol')

# 初始化PIOSPI类（回环测试配置）
spi = PIOSPI(
    sm_id=0, 
    pin_mosi=10, 
    pin_sck=11, 
    pin_miso=10, 
    pin_cs=12,
    cpha=False, 
    cpol=False, 
    freq=1000000
)

# 循环执行SPI写读操作
while True:
    data = spi.write_read(tx_list)
    print('FreakStudio : SPI data received : {}'.format(data))
    time.sleep(1)
```

## 注意事项

1. 仅支持CPHA=0、CPOL=0模式，传入其他参数会触发断言错误；
2. MOSI引脚必须与SCK引脚相邻（MOSI = SCK ±1），否则会触发断言错误；
3. 数据传输单位为8位字节，输入的待发送数据需为8位整数列表；
4. 状态机编号（sm_id）需选择未被占用的编号，避免冲突；
5. 片选引脚（CS）初始状态为高电平，数据传输时拉低，传输完成后拉高。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

本项目采用MIT开源许可协议，具体条款如下：

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
