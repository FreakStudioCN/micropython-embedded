# MicroPython-PCF8575-OLED菜单控制系统

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
本项目基于MicroPython v1.23.0开发，通过PCF8575 I2C扩展芯片读取五向按键/5D摇杆的输入状态，结合SSD1306 OLED屏幕（128x64）实现可交互的多级菜单控制系统。项目封装了PCF8575、SSD1306硬件驱动，提供轻量化的OLED菜单库，支持菜单的选择、进入子菜单、返回上级、删除菜单等操作，并可通过回调函数扩展自定义业务逻辑（如LED控制、变量/参数显示与更新等），适用于嵌入式设备的人机交互场景。

## 主要功能
1. **PCF8575 I2C扩展驱动**：封装PCF8575类，支持I2C通信、端口/单个引脚的读写、引脚电平翻转、外部中断触发及回调处理；
2. **SSD1306 OLED屏幕驱动**：实现OLED屏幕初始化、显示开关、对比度调整、图形绘制、数据缓存更新等基础功能；
3. **多级菜单管理**：提供简易OLED菜单库，支持添加/删除菜单项、上下选择菜单项、进入子菜单、返回上级菜单、中心显示提示消息；
4. **五向按键交互**：通过PCF8575读取五向按键（UP/DOWN/LEFT/RIGHT/CENTER）状态，触发菜单的选择与操作；
5. **自定义回调逻辑**：菜单项支持绑定进入/退出回调函数，实现LED控制、变量/参数显示与更新等自定义业务；
6. **I2C设备自动扫描**：自动扫描I2C总线上的PCF8575和OLED设备地址，适配不同硬件部署场景；
7. **中断驱动响应**：PCF8575中断引脚配合下降沿触发，实现按键操作的异步响应，提升交互流畅性。

## 文件说明
| 文件名 | 功能描述 |
|--------|----------|
| pcf8575.py | 自定义PCF8575类，封装I2C通信、端口/引脚读写、翻转、中断处理等核心功能，实现对PCF8575芯片的完整控制 |
| SSD1306.py | 定义SSD1306类（继承framebuf.FrameBuffer）及I2C子类，实现OLED屏幕的初始化、显示控制、指令/数据发送等驱动逻辑 |
| menu.py | 实现MenuNode（菜单节点）和SimpleOLEDMenu（OLED菜单管理）类，提供多级菜单的添加、删除、选择、显示、回调等功能 |
| main.py | 项目主程序，初始化I2C设备、PCF8575、OLED屏幕和菜单系统，读取五向按键状态并绑定菜单操作，实现LED控制、变量/参数显示等业务逻辑 |

## 软件设计核心思想
1. **模块化解耦设计**：将硬件驱动（PCF8575、SSD1306）、菜单逻辑（menu）、业务逻辑（main）分层实现，各模块独立封装，降低耦合度，便于单独维护和扩展；
2. **面向对象封装**：核心硬件和功能均采用类封装（如PCF8575、SSD1306、SimpleOLEDMenu），隐藏底层通信和控制细节，对外提供简洁易用的接口；
3. **栈式菜单管理**：通过栈结构（menu_stack）管理菜单层级，实现子菜单的进入（入栈）与上级菜单的返回（出栈），逻辑清晰且易于扩展；
4. **中断驱动交互**：利用PCF8575的外部中断引脚，结合下降沿触发和回调函数，实现按键操作的异步响应，避免轮询占用CPU资源；
5. **回调扩展机制**：菜单项绑定自定义回调函数，将菜单显示与业务逻辑解耦，支持灵活扩展如LED控制、参数更新等自定义功能；
6. **鲁棒性设计**：添加引脚验证、菜单名称重复检查、长度限制、设备地址扫描等校验逻辑，提升程序容错性。

## 使用说明
### 环境依赖
- 软件环境：MicroPython v1.23.0（适配ESP32/ESP8266等支持I2C的MicroPython设备）；
- 硬件环境：PCF8575 I2C扩展芯片、SSD1306 OLED屏幕（128x64像素）、五向按键/5D摇杆、LED、杜邦线、开发板（如ESP32）；
- 硬件接线（示例）：
  - PCF8575：SDA→Pin6，SCL→Pin7，中断引脚→Pin8，五向按键接PCF8575的对应引脚；
  - SSD1306 OLED：SDA→Pin6，SCL→Pin7（与PCF8575共用I2C总线）；
  - LED：正极→Pin25，负极→GND（需串接限流电阻）。

### 安装步骤
1. 将项目文件（pcf8575.py、SSD1306.py、menu.py、main.py）上传至MicroPython设备（可通过Thonny、WebREPL等工具）；
2. 检查硬件接线是否正确，确保I2C总线、中断引脚、LED引脚连接无误；
3. 确认设备已烧录MicroPython v1.23.0固件，且支持I2C外设。

### 运行方式
1. 在MicroPython终端中执行：
   ```python
   import main
   ```
2. 或设置设备开机自启（将main.py重命名为main.py，设备上电后自动执行）。

## 示例程序
以下是核心功能的简化示例（基于main.py）：
```python
# 导入核心模块
from machine import I2C, Pin
import time
from pcf8575 import PCF8575
from SSD1306 import SSD1306_I2C
from menu import SimpleOLEDMenu

# 初始化I2C
i2c = I2C(id=1, sda=Pin(6), scl=Pin(7), freq=400000)

# 扫描并初始化PCF8575
pcf8575_addr = next((d for d in i2c.scan() if 0x20 <= d <= 0x27), 0x20)
pcf8575 = PCF8575(i2c, pcf8575_addr, interrupt_pin=Pin(8), callback=detect_interrupt)
pcf8575.port = 0x00FF

# 扫描并初始化OLED
oled_addr = next((d for d in i2c.scan() if 0x3C <= d <= 0x3D), 0x3C)
oled = SSD1306_I2C(i2c, oled_addr, 128, 64, False)

# 初始化菜单
menu = SimpleOLEDMenu(oled, "Main Menu", 0, 0, 128, 64)

# 添加菜单项及回调
def show_var():
    menu.show_message("Value: 10")

menu.add_menu("LED Control")
menu.add_menu("Show Variable", enter_callback=show_var)
menu.add_menu("Sub Menu", parent_name="LED Control")

# 显示菜单
menu.display_menu()
```

## 注意事项
1. **硬件接线**：I2C总线建议添加4.7KΩ上拉电阻，避免信号不稳定；中断引脚需配置为上拉输入，确保按键触发可靠；
2. **设备地址**：PCF8575默认地址范围0x20-0x27，OLED默认0x3C/0x3D，若扫描不到设备需检查硬件接线或地址跳线；
3. **菜单名称**：菜单项名称长度需≤16字符（适配128像素宽度，单字符8像素），过长会抛出ValueError；
4. **中断冲突**：若使用多个中断引脚，需避免中断触发优先级冲突，确保回调函数执行效率；
5. **版本兼容**：本项目基于MicroPython v1.23.0开发，低版本固件可能存在API差异，建议升级至对应版本；
6. **电源稳定性**：OLED屏幕和PCF8575需保证供电稳定，避免电压不足导致显示异常或通信失败。

## 联系方式
如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn
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