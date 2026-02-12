# 基于MicroPython的按键检测框架
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

本项目是基于 MicroPython v1.23.0 开发的按键检测框架，通过定时器实现按键状态的周期性检测，结合有限状态机（FSM）设计思想，能够精准识别按键的单击、双击、长按等动作，并支持自定义回调函数处理不同按键事件。该框架适用于嵌入式微控制器（如ESP32、ESP8266等）的按键交互场景，具备轻量、易扩展、高可靠性的特点。

## 主要功能

1. 内置按键消抖逻辑，避免机械按键抖动导致的误触发；
2. 支持按键单击、双击、长按三种核心事件的检测；
3. 可自定义长按最小判定时间（默认1200ms）、双击最大时间间隔（默认500ms）；
4. 支持多按键独立检测，每个按键可配置独立的回调函数；
5. 兼容按键高低电平初始化（支持上拉/下拉电阻配置）；
6. 基于定时器周期性检测，非阻塞式设计，不占用主程序执行流程。

## 文件说明

| 文件名 | 功能说明 |
|--------|----------|
| ButtonDetect.py | 核心文件，实现`ButtonFSM`按键状态机类，封装按键检测的核心逻辑，包括状态转换、事件判定、回调函数触发等 |
| main.py | 示例程序，演示如何使用`ButtonFSM`类初始化多个按键，定义单击/双击/长按回调函数，并完成按键检测的完整流程 |

## 软件设计核心思想

本框架的核心是**有限状态机（FSM）** 设计，通过定时器以20ms为周期检测按键电平状态，结合时间阈值判断按键动作，核心状态转换逻辑如下：

1. **状态定义**：释放态、消抖态、单击/持续按下态、等待双击态、双击态、长按态；
2. **消抖处理**：按键按下后先进入消抖态，确认电平稳定后再进入后续状态；
3. **长按判定**：按键按下时间超过`BtnPressMinTime`（1200ms）时，判定为长按事件；
4. **双击判定**：两次单击的时间间隔小于`BtnDoubleClickMaxTime`（500ms）时，判定为双击事件；
5. **事件触发**：不同状态转换完成后，触发对应的回调函数（单击/双击/长按），完成事件响应。

定时器的周期性检测保证了按键状态的实时性，状态机的设计则确保了不同按键动作的精准区分，避免误判。

## 使用说明

### 环境要求

- 固件版本：MicroPython v1.23.0；
- 硬件：支持MicroPython的嵌入式微控制器（如ESP32、ESP8266）。

### 硬件连接

1. 将按键一端连接到微控制器的GPIO引脚，另一端根据初始化电平配置连接：
   - 若初始化状态为`ButtonFSM.LOW`：按键另一端接GND，引脚启用下拉电阻；
   - 若初始化状态为`ButtonFSM.HIGH`：按键另一端接VCC，引脚启用上拉电阻。

### 基本使用步骤

1. 导入核心模块：

   ```python
   from machine import Pin, Timer
   from ButtonDetect import ButtonFSM
   ```

2. 定义按键事件的回调函数（单击/双击/长按）：

   ```python
   def press_func(arg):
       print(f"按键{arg}长按触发")
   def click_func(arg):
       print(f"按键{arg}单击触发")
   def double_click_func(arg):
       print(f"按键{arg}双击触发")
   ```

3. 初始化按键引脚和定时器：

   ```python
   button_pin = Pin(10)  # 按键连接的GPIO引脚
   timer = Timer(-1)     # 创建定时器对象（-1表示虚拟定时器）
   ```

4. 实例化`ButtonFSM`类，配置按键参数：

   ```python
   button = ButtonFSM(
       pin=button_pin,
       timer=timer,
       init_state=ButtonFSM.LOW,  # 按键初始化电平为低
       press_callback=press_func,
       click_callback=click_func,
       double_click_callback=double_click_func,
       args=1  # 回调函数的额外参数（如按键编号）
   )
   ```

5. 主程序保持运行：

   ```python
   while True:
       pass
   ```

## 示例程序

以下是`main.py`中的核心示例代码，演示4个独立按键的检测配置：

```python
# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
from machine import Pin, Timer
from ButtonDetect import ButtonFSM
import time

# 按键长按回调函数
def press_func(arg: int) -> None:
    print('button %d is pressed' % arg)

# 按键短按回调函数
def click_func(arg: int) -> None:
    print('button %d is clicked' % arg)

# 按键双击回调函数
def double_click_func(arg: int) -> None:
    print('button %d is double clicked' % arg)

# 延时等待设备初始化
time.sleep(3)
print("FreakStudio : Using ButtonFSM to detect the status of button")

# 定义按键引脚和定时器
button_1_pin = Pin(10)
button_2_pin = Pin(11)
button_3_pin = Pin(12)
button_4_pin = Pin(13)

timer_1 = Timer(-1)
timer_2 = Timer(-1)
timer_3 = Timer(-1)
timer_4 = Timer(-1)

# 创建4个按键实例
button_1 = ButtonFSM(button_1_pin, timer_1, ButtonFSM.LOW, press_func, click_func, double_click_func,1)
button_2 = ButtonFSM(button_2_pin, timer_2, ButtonFSM.LOW, press_func, click_func, double_click_func,2)
button_3 = ButtonFSM(button_3_pin, timer_3, ButtonFSM.LOW, press_func, click_func, double_click_func,3)
button_4 = ButtonFSM(button_4_pin, timer_4, ButtonFSM.LOW, press_func, click_func, double_click_func,4)

# 主循环
while True:
    pass
```

## 注意事项

1. 定时器周期：框架默认定时器检测周期为20ms，若需调整需修改`ButtonFSM`类中的`run_period`参数，建议不小于10ms（避免过度占用CPU）；
2. 电平配置：初始化状态`LOW/HIGH`需与硬件连接匹配，否则会导致按键状态检测异常；
3. 回调函数：回调函数应尽量简洁，避免执行耗时操作（如长时间延时），否则会影响按键检测的实时性；
4. 多按键资源：每个按键需独立的定时器对象，避免多个按键共享定时器导致状态混乱；
5. 时间阈值：可通过修改`ButtonFSM.BtnPressMinTime`（长按阈值）、`ButtonFSM.BtnDoubleClickMaxTime`（双击间隔阈值）适配不同场景的按键特性。

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
