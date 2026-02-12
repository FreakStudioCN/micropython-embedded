# 数字电位器/DA芯片波形生成项目

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

本项目基于 MicroPython v1.23.0 开发，实现了对 DS3502 数字电位器芯片和 MCP4725 12位 DAC（数模转换）芯片的驱动，并提供通用波形发生器模块，可灵活生成正弦波、方波、三角波等任意波形。同时集成 ADC 定时采集、串口数据输出功能，适用于基于微控制器的波形生成与电压采集场景。

## 主要功能

1. **硬件驱动封装**：
   - 完整实现 DS3502 数字电位器 I2C 通信驱动，支持滑动寄存器读写、控制寄存器模式配置；
   - 实现 MCP4725 12位 DAC 芯片驱动，支持电压输出写入、电源模式配置、EEPROM 读写等；
2. **通用波形生成**：
   - 支持正弦波、方波、三角波生成，可自定义频率（0~10Hz）、幅度、直流偏移、参考电压；
   - 波形发生器解耦设计，适配任意分辨率 DAC/数字电位器，仅需配置分辨率和写入方法；
3. **数据采集与输出**：
   - 定时器驱动 ADC 定时采集电压（1ms 采样周期）；
   - 串口（UART）输出采集到的电压数据，格式化为两位小数；
4. **参数校验**：对输入参数（如电压、频率、DAC 分辨率等）进行严格校验，避免硬件操作越界。

## 文件说明

| 文件名                  | 功能说明                                                                 |
|-------------------------|--------------------------------------------------------------------------|
| `mcp4725.py`            | MCP4725 12位 DAC 芯片驱动模块，封装 I2C 通信、电压写入、电源模式配置等功能 |
| `ds3502.py`             | DS3502 数字电位器芯片驱动模块，封装滑动寄存器/控制寄存器读写、模式配置     |
| `dac_waveformgenerator.py` | 通用波形发生器类，支持任意分辨率 DAC，可生成正弦/方波/三角波             |
| `main.py`               | 主程序，演示 DS3502 生成波形、ADC 定时采集、串口输出采集数据             |

## 软件设计核心思想

1. **解耦与通用化**：
   - 波形发生器通过 `dac_resolution`（DAC 分辨率）和 `dac_write_method`（写入方法）参数适配不同 DAC/数字电位器，脱离硬件耦合；
   - 通用电压转 DAC 值方法 `_to_dac_value`，适配任意位数 DAC，自动限制数值范围避免越界；
2. **严格参数校验**：对频率、电压幅度/偏移、DAC 分辨率等参数做范围校验，抛出明确的错误提示，提升鲁棒性；
3. **硬件抽象封装**：将 I2C 通信、寄存器操作封装到硬件驱动类中，上层业务无需关注底层通信细节；
4. **定时器驱动**：采用软件定时器实现波形更新和 ADC 采集的定时触发，保证实时性；
5. **异常处理**：对无效 I2C 地址、非法参数、不存在的 DAC 方法等场景抛出异常，便于问题定位。

## 使用说明

### 环境准备

- 固件：MicroPython v1.23.0；
- 硬件：支持 I2C、ADC、UART 的 MicroPython 开发板（如 RP2040）；
- 外设：DS3502 数字电位器 / MCP4725 DAC 芯片、ADC 采样电路、串口调试工具。

### 硬件连接

1. **I2C 连接**：
   - DS3502/MCP4725 的 SDA/SCL 引脚连接开发板对应 I2C 引脚（示例中为 SDA=4、SCL=5）；
   - DS3502 地址范围 0x28~0x2B，MCP4725 地址范围 0x60~0x67；
2. **ADC 连接**：示例中使用 ADC0（GP26）采集电压；
3. **串口连接**：开发板 TX/RX 引脚连接串口工具（示例中 TX=0、RX=1，波特率 115200）。

### 核心参数配置

| 参数                | 说明                                                                 |
|---------------------|----------------------------------------------------------------------|
| `frequency`         | 波形频率，范围 0~10Hz                                                |
| `amplitude`         | 波形幅度，范围 0~参考电压（`vref`）                                  |
| `offset`            | 直流偏移，范围 0~参考电压（`vref`）                                  |
| `dac_resolution`    | DAC 最大分辨率（DS3502=127，MCP4725=4095），必传                     |
| `dac_write_method`  | DAC 写入方法名（DS3502='write_wiper'，MCP4725='write'），必传        |
| `vref`              | 参考电压（默认 3.3V，DS3502 示例中为 5V）                            |

## 示例程序

### 1. 初始化硬件（main.py 核心片段）

```python
from machine import ADC, Timer, Pin, I2C, UART
import time
from ds3502 import DS3502
from dac_waveformgenerator import WaveformGenerator

# 硬件初始化
time.sleep(3)  # 上电延时
i2c = I2C(id=0, sda=Pin(4), scl=Pin(5), freq=400000)  # I2C 400KHz
devices_list = i2c.scan()
DAC_ADDRESS = 0x28  # 或自动扫描获取
dac = DS3502(i2c, DAC_ADDRESS)
dac.set_mode(1)  # DS3502 快速模式

# 串口初始化
uart = UART(0, 115200, tx=0, rx=1, timeout=100)

# ADC 与定时器初始化
adc = ADC(0)
timer = Timer(-1)
timer.init(period=1, mode=Timer.PERIODIC, callback=timer_callback)
```

### 2. 生成正弦波

```python
# 初始化波形发生器（DS3502，5Hz，幅度1.5V，偏移1.5V，参考电压5V）
wave = WaveformGenerator(
    dac=dac,
    frequency=5,
    amplitude=1.5,
    offset=1.5,
    waveform='sine',
    vref=5,
    dac_resolution=127,
    dac_write_method='write_wiper'
)
wave.start()  # 启动波形生成
time.sleep(6) # 运行6秒
wave.stop()   # 停止波形生成
```

### 3. 生成三角波

```python
wave = WaveformGenerator(
    dac=dac,
    frequency=5,
    amplitude=1.5,
    offset=1.5,
    waveform='triangle',
    rise_ratio=0.8,  # 三角波上升比例
    vref=5,
    dac_resolution=127,
    dac_write_method='write_wiper'
)
wave.start()
time.sleep(6)
wave.stop()
```

## 注意事项

1. **I2C 地址校验**：DS3502 地址需在 0x28~0x2B 之间，MCP4725 地址需在 0x60~0x67 之间，否则初始化抛出异常；
2. **参数范围限制**：
   - 波形频率不超过 10Hz，避免定时器频率过高导致系统异常；
   - 幅度+偏移/偏移-幅度需在 0~参考电压范围内，防止 DAC 输出越界；
3. **DAC 配置必传项**：`dac_resolution` 和 `dac_write_method` 必须正确配置，否则抛出参数错误；
4. **上电延时**：主程序中需保留 3 秒上电延时，确保外设初始化完成；
5. **串口输出**：ADC 采集数据通过串口输出，需确保串口工具波特率（115200）与代码一致；
6. **模式配置**：DS3502 模式 0 写入速度慢（需 100ms 延时），模式 1 仅写入滑动寄存器，速度快。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

本项目采用 MIT 开源许可协议，您可以自由使用、修改、分发本项目代码，无需额外授权。  
MIT License 详情：  

```
Copyright (c) 2025 FreakStudio

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
