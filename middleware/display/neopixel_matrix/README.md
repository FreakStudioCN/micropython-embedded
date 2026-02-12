# WS2812矩阵驱动库（MicroPython）
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
本项目是基于 **MicroPython v1.23.0** 开发的WS2812 LED矩阵驱动库，提供了简洁、高效的API接口，支持WS2812矩阵的像素控制、动画播放、文字滚动、图像渲染等功能。驱动库封装了底层硬件操作，适配不同的WS2812排列布局（行优先/蛇形）、RGB颜色顺序、画面翻转/旋转等场景，同时支持Gamma校正、亮度调节、局部刷新等优化特性，可快速实现各类LED矩阵显示效果。

## 主要功能

1. **基础显示控制**：支持像素点/线/面绘制、全屏填充、局部区域刷新；
2. **颜色处理**：内置RGB565常用颜色常量，支持RGB565与RGB888格式互转、Gamma校正、亮度调节（0~1）；
3. **布局适配**：支持行优先（LAYOUT_ROW）、蛇形（LAYOUT_SNAKE）两种矩阵排列方式，支持画面水平/垂直翻转、90/180/270°旋转；
4. **动画特效**：提供颜色填充、滚动线条、循环动画等预制特效，支持自定义帧率的动画播放；
5. **图像渲染**：支持加载JSON格式的RGB565图像数据（文件/字符串/字典），支持多帧动画循环播放；
6. **文字滚动**：支持上下左右四个方向的文字滚动，可自定义文字/背景颜色、滚动速度和次数；
7. **工程化扩展**：支持通过UART串口发送RGB888格式的像素数据，便于外接主控/显示设备；
8. **性能优化**：基于`micropython.native`装饰器优化核心方法，支持循环滚动（wrap）和普通滚动两种模式。

## 文件说明

| 文件名 | 功能说明 |
|--------|----------|
| `neopixel_matrix.py` | WS2812矩阵核心驱动类，封装了FrameBuffer、Neopixel底层操作，提供颜色转换、图像渲染、滚动、刷新等核心API； |
| `main.py` | 测试示例代码，包含颜色填充、滚动线条、JSON图像动画、文字滚动、UART数据发送等功能的演示； |

## 软件设计核心思想

1. **封装与抽象**：基于`framebuf.FrameBuffer`封装`NeopixelMatrix`类，屏蔽底层硬件差异，对外提供统一的显示控制接口；
2. **兼容性适配**：支持自定义RGB颜色顺序（RGB/GRB/BGR等6种）、矩阵布局、画面翻转/旋转，适配不同硬件规格的WS2812矩阵；
3. **标准化数据格式**：定义JSON格式的RGB565图像数据规范，支持文件加载、字符串/字典解析，便于图像数据的复用和扩展；
4. **性能优先**：核心方法（如`_pos2index`、`rgb565_to_rgb888`、`show`）使用`micropython.native`装饰器编译为原生代码，提升执行效率；
5. **灵活的滚动机制**：区分循环滚动（wrap=True，无残留）和普通滚动（清除残留区域），满足不同动画场景需求；
6. **工程化扩展**：提供`send_pixels_via_uart`方法，支持将像素数据通过UART发送，便于与其他设备通信；
7. **鲁棒性设计**：关键参数（坐标、布局、颜色顺序、亮度等）增加合法性校验，异常场景提供明确的错误提示。

## 使用说明

### 环境要求

- 固件：MicroPython v1.23.0；
- 硬件：支持MicroPython的主控板（如RP2040/ESP32等）、WS2812 LED矩阵；
- 依赖：内置`neopixel`、`framebuf`、`machine`模块，无需额外安装。

### 硬件连接
1. 将WS2812矩阵的数据引脚连接到主控板指定GPIO（示例中为Pin(6)）；
2. 若使用UART发送功能，需连接主控板UART_TX引脚（示例中为Pin(16)）到外接设备的UART_RX引脚。

### 快速开始

```python
# 1. 导入驱动类
from neopixel_matrix import NeopixelMatrix
from machine import Pin

# 2. 初始化矩阵（4x1 WS2812矩阵，数据引脚Pin(6)，蛇形布局，亮度0.1，RGB顺序，水平翻转）
matrix = NeopixelMatrix(
    width=4, 
    height=1, 
    pin=Pin(6), 
    layout=NeopixelMatrix.LAYOUT_SNAKE, 
    brightness=0.1, 
    order=NeopixelMatrix.ORDER_RGB, 
    flip_h=True
)

# 3. 基础操作
matrix.fill(NeopixelMatrix.COLOR_RED)  # 全屏填充红色
matrix.show()  # 刷新显示
```

### 核心API使用

- **图像显示**：加载JSON图像文件并显示

  ```python
  matrix.load_rgb565_image("test_image.json", offset_x=0, offset_y=0)
  matrix.show()
  ```

- **文字滚动**：向左滚动显示"welcome"，白色文字、蓝色背景，滚动3次

  ```python
  matrix.scroll_text("welcome", 'left', 
                     text_color=NeopixelMatrix.COLOR_WHITE, 
                     bg_color=NeopixelMatrix.COLOR_BLUE, 
                     delay=0.1, 
                     scroll_count=3)
  ```

- **动画播放**：加载30帧动画并以30FPS播放

  ```python
  frames = load_animation_frames()  # 加载帧数据
  play_animation(matrix, frames, fps=30)  # 播放动画
  ```

- **UART发送像素数据**：

  ```python
  from machine import UART
  uart0 = UART(0, baudrate=115200, tx=Pin(16), rx=Pin(17))
  matrix.send_pixels_via_uart(uart=uart0, start_x=0, start_y=0, end_x=3)
  ```

## 示例程序

### 1. 颜色填充特效

```python
def color_wipe(color, delay=0.1):
    matrix.fill(0)
    for i in range(8):
        for j in range(8):
            matrix.pixel(i, j, color)
            matrix.show()
            time.sleep(delay)
    matrix.fill(0)

# 调用示例：填充红色，延迟0.1秒
color_wipe(NeopixelMatrix.COLOR_RED, 0.1)
```

### 2. 滚动线条动画

```python
optimized_scrolling_lines()  # 蓝横线下降→红竖线右移动画
```

### 3. JSON图像动画播放

```python
animation_frames = [json_img1, json_img2, json_img3]  # 定义帧数据
animate_images(matrix, animation_frames, delay=0.5)  # 循环播放动画
```

### 4. 多方向文字滚动

```python
# 向左滚动
scroll_text(matrix, "welcome", 'left', NeopixelMatrix.COLOR_WHITE, NeopixelMatrix.COLOR_BLUE, 0.1, 3)
# 向上滚动
scroll_text(matrix, "world", 'up', NeopixelMatrix.COLOR_GREEN, NeopixelMatrix.COLOR_RED, 0.2, 1)
```

### 5. UART发送像素数据

```python
for i in range(0, 7):
    matrix.fill(color[i])
    matrix.send_pixels_via_uart(uart=uart0,start_x=0, start_y=0,end_x=3)
    time.sleep_ms(500)
```

## 注意事项

1. **参数合法性**：初始化矩阵时，宽度/高度需≥1，布局仅支持`LAYOUT_ROW`/`LAYOUT_SNAKE`，旋转角度仅支持0/90/180/270°；
2. **亮度范围**：亮度值需在0~1之间，超出范围会抛出`ValueError`；
3. **滚动限制**：`scroll`方法不支持同时设置水平和垂直滚动步数（xstep/ystep不能同时非零）；
4. **JSON图像格式**：图像数据需符合规范，`pixels`数组元素需为0~65535的RGB565值，`width`需为正整数且`len(pixels)`能被`width`整除；
5. **局部刷新**：调用`show(x1, y1, x2, y2)`时，需保证`x1≤x2`且`y1≤y2`，且坐标不超出矩阵范围；
6. **UART配置**：使用`send_pixels_via_uart`前需确保UART已正确初始化，波特率与外接设备匹配；
7. **性能考量**：在低性能主控上，建议降低动画帧率（如15~20FPS），避免卡顿；
8. **引脚冲突**：需确认矩阵数据引脚、UART引脚未与主控板其他功能（如内置LED、按键）冲突。

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
