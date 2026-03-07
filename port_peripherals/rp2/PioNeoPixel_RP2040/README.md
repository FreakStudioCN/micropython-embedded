# RP2040 PIO 控制 WS2812 灯带

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

本项目基于 RP2040 芯片的 MicroPython 环境（v1.23.0）开发，利用 RP2040 独有的 PIO 模块实现对 WS2812 LED 灯带的精准时序控制，无需依赖硬件 PWM，可高效、稳定地驱动灯带完成 16 种颜色的循环闪烁效果。

## 主要功能

1. 基于 PIO 汇编指令实现 WS2812 灯带的底层驱动，兼容 800kHz 通信频率；
2. 预设 16 种低亮度配色方案，避免灯带过亮烧毁，涵盖红、橙、黄、绿、蓝、紫等主流颜色；
3. 实现灯带颜色的循环左移切换，每 200ms 切换一次颜色，视觉效果流畅；
4. 代码模块化设计，驱动逻辑与业务逻辑分离，便于扩展和维护。

## 文件说明

| 文件名 | 功能说明 |
|--------|----------|
| `main.py` | 主程序文件，负责全局变量定义、状态机初始化、颜色数据循环输出等核心业务逻辑 |
| `ws2812_driver.py` | WS2812 驱动文件，通过 `rp2.asm_pio` 定义 PIO 汇编程序，实现 WS2812 通信时序的底层控制 |

## 软件设计核心思想

### 1. PIO 驱动核心

WS2812 采用单线通信协议，对时序要求严格（高电平/低电平的时长决定数据位 0/1）。本项目通过 `rp2.asm_pio` 编写汇编级 PIO 程序：

- 启用 `autopull` 自动拉取数据，设置 `pull_thresh=24` 匹配 WS2812 的 24 位 GRB 颜色数据；
- 通过 `side-set` 引脚（Pin16）输出高低电平，精准控制通信时序；
- 利用 PIO 状态机的硬件并行特性，脱离 CPU 干预，保证时序稳定性。

### 2. 颜色数据处理

WS2812 采用 GRB 颜色格式（而非常规 RGB），程序中通过位运算将 RGB 转换为 24 位 GRB 数据：

```python
value = (g << 16) | (r << 8) | b  # 转换为 GRB 格式
```

通过列表左移操作（`colors = colors[1:] + [colors[0]]`）实现颜色循环切换。

### 3. 状态机配置

将 PIO 状态机频率设置为 8MHz（WS2812 通信频率 800kHz × 10），保证 1 个 WS2812 时钟周期对应 10 个 PIO 执行周期，精准匹配通信时序：

```python
sm = rp2.StateMachine(0, ws2812_driver.ws2812, freq=8000000, sideset_base=Pin(16))
```

## 使用说明

### 硬件准备

1. RP2040 开发板（如树莓派 Pico）；
2. WS2812 LED 灯带（任意长度，测试用 16 灯珠）；
3. 杜邦线：将 RP2040 的 Pin16 连接到 WS2812 的 DIN 引脚，WS2812 接 5V 电源和 GND。

### 软件环境

- MicroPython v1.23.0（适配 RP2040 版本）；
- 开发工具：Thonny、VSCode + PyMakr 等（支持 MicroPython 代码上传）。

### 部署步骤

1. 将 `main.py` 和 `ws2812_driver.py` 上传到 RP2040 开发板；
2. 给开发板上电，程序自动运行（上电延时 3s 保证初始化稳定）；
3. 观察灯带效果：16 种颜色循环闪烁，每 200ms 切换一次。

## 示例程序

核心示例代码（`main.py` 关键逻辑）：

```python
import rp2
import time
from machine import Pin
import ws2812_driver

# 预设16种低亮度颜色
colors = [
    (128, 0, 0), (128, 82, 0), (128, 128, 0), (0, 128, 0),
    (0, 128, 128), (0, 0, 128), (38, 0, 65), (119, 65, 119),
    (128, 53, 90), (128, 10, 74), (128, 128, 128), (96, 96, 96),
    (0, 0, 0), (64, 64, 64), (128, 0, 128), (128, 128, 128)
]

# 初始化PIO状态机
sm = rp2.StateMachine(0, ws2812_driver.ws2812, freq=8000000, sideset_base=Pin(16))
sm.active(1)

# 颜色循环输出
while True:
    for r, g, b in colors:
        value = (g << 16) | (r << 8) | b
        sm.put(value, 8)
    colors = colors[1:] + [colors[0]]
    time.sleep_ms(200)
```

## 注意事项

1. **引脚匹配**：程序默认使用 Pin16 作为数据输出引脚，若修改引脚需同步修改 `sideset_base=Pin(XX)`；
2. **电压兼容**：WS2812 通常为 5V 供电，RP2040 的 GPIO 输出为 3.3V，若灯带不亮需增加 3.3V→5V 电平转换模块；
3. **亮度控制**：代码中颜色值均降低至 128 以下（最大 255），避免高亮度导致灯带发热烧毁；
4. **状态机冲突**：程序使用 PIO 状态机 0，若同时使用其他 PIO 功能需修改状态机编号；
5. **版本兼容**：确保 RP2040 的 MicroPython 版本为 v1.23.0，避免 `rp2.asm_pio` 语法兼容问题。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

本项目采用 MIT 开源许可协议，您可以自由使用、修改、分发本项目代码，具体协议如下：

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
