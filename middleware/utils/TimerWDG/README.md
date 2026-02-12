# 软件看门狗定时器（Pico/MicroPython）

基于MicroPython在Raspberry Pi Pico上实现的软件看门狗（WDT）定时器，通过软件定时器模拟硬件看门狗功能，支持自定义触发条件、状态记录、恢复操作等灵活扩展能力。

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

本项目基于MicroPython v1.23.0开发，针对Raspberry Pi Pico（或其他支持MicroPython的开发板）实现**软件看门狗定时器**功能。相较于硬件看门狗，本实现支持自定义触发条件、状态日志记录、系统恢复操作等扩展能力，可灵活适配不同业务场景的系统监控需求，当系统喂狗超时、连续失败次数达到阈值时，可执行恢复操作或触发系统复位。

## 主要功能

1. **核心看门狗能力**：基于MicroPython Timer实现周期性喂狗检测，支持自定义超时时间（默认4000ms）；
2. **灵活的触发机制**：支持注册自定义触发条件函数（如阈值检测），仅满足条件时触发复位；
3. **状态记录**：可注册自定义日志记录函数，自动将时间戳、系统状态、看门狗触发次数等写入日志文件（自动分文件，避免单文件过大）；
4. **系统恢复机制**：支持注册自定义恢复操作函数，复位前优先执行自救逻辑，恢复成功则重置失败计数；
5. **失败次数限制**：可配置最大连续喂狗失败次数，达到阈值后触发复位流程；
6. **中断安全**：通过禁用/启用中断保证喂狗标志的原子操作，避免竞态条件；
7. **调试与性能分析**：内置调试模式（打印关键流程信息）、计时装饰器（统计函数运行时间）；
8. **资源管理**：析构函数与stop方法确保定时器资源释放，避免内存泄漏。

## 文件说明

| 文件名                | 功能说明                                                                 |
|-----------------------|--------------------------------------------------------------------------|
| `main.py`             | 主程序文件，包含自定义回调函数（阈值检查、日志记录、恢复操作）、看门狗初始化及喂狗测试逻辑 |
| `SoftwareWatchdog.py` | 软件看门狗核心类实现，封装定时器管理、喂狗、回调注册、复位触发等核心逻辑               |

## 软件设计核心思想

1. **模块化封装**：将看门狗核心逻辑封装为`SoftwareWatchdog`类，解耦核心功能与业务逻辑，便于复用和扩展；
2. **回调解耦**：通过注册自定义回调函数（状态记录、触发条件、恢复操作），让业务逻辑与看门狗核心逻辑分离，提升灵活性；
3. **中断安全**：对喂狗标志的读写采用`disable_irq/enable_irq`实现原子操作，避免中断上下文与主程序的竞态问题；
4. **分层处理流程**：连续喂狗失败后，先执行恢复操作 → 恢复失败则检查触发条件 → 满足条件则延迟复位，保证系统有自救机会；
5. **调试与性能优化**：调试模式打印关键流程信息，`@micropython.native`装饰器提升回调函数执行效率，计时装饰器辅助性能分析；
6. **资源安全**：析构函数自动释放定时器资源，避免开发板长期运行导致的资源泄漏。

## 使用说明

### 1. 环境准备

- 硬件：Raspberry Pi Pico（或其他支持MicroPython的开发板）；
- 软件：MicroPython v1.23.0（适配代码版本，其他版本需适配API）；
- 工具：Thonny/VSCode（用于将代码上传到开发板）。

### 2. 文件部署

将`main.py`和`SoftwareWatchdog.py`上传到开发板根目录。

### 3. 核心配置与使用

#### 初始化看门狗

```python
from SoftwareWatchdog import SoftwareWatchdog

# 初始化：超时4000ms，开启调试，最大连续失败3次，复位延迟1000ms
watchdog = SoftwareWatchdog(timeout=4000, debug=True, max_failures=3, reset_delay=1000)
```

#### 注册自定义回调

```python
# 1. 注册状态记录函数（如日志写入）
watchdog.register_state_recorder(user_log_critical_time)

# 2. 设置触发条件函数（返回bool，True表示触发复位）
watchdog.set_trigger_condition(user_check_threshold)

# 3. 注册恢复操作函数（返回bool，True表示恢复成功）
watchdog.register_recovery_handler(user_recovery_handler)
```

#### 喂狗操作

需在超时时间内调用`feed()`方法，否则累计失败次数：

```python
watchdog.feed()  # 喂狗，重置喂狗标志
```

#### 停止看门狗

```python
watchdog.stop()  # 释放定时器资源
```

## 示例程序

以下是简化的核心示例（完整代码见`main.py`）：

```python
# 导入模块
from SoftwareWatchdog import SoftwareWatchdog
import time

# 自定义触发条件函数
def user_check_threshold() -> bool:
    global current_value, threshold
    return current_value >= threshold  # 阈值检测

# 自定义状态记录函数
def user_log_critical_time() -> None:
    timestamp = time.ticks_ms()
    with open("/log0.txt", "a") as f:
        f.write(f"Timestamp: {timestamp}ms, Triggers: {watchdog.trigger_count}\n")

# 自定义恢复操作函数
def user_recovery_handler() -> bool:
    try:
        # 执行恢复逻辑（如重置变量、重启服务）
        global current_value
        current_value = 0
        return True
    except Exception as e:
        print(f"Recovery failed: {e}")
        return False

# 初始化配置
threshold = 10
current_value = 12  # 初始值超过阈值，触发条件为True

# 初始化看门狗
watchdog = SoftwareWatchdog(timeout=4000, debug=True, max_failures=3, reset_delay=1000)
watchdog.register_state_recorder(user_log_critical_time)
watchdog.set_trigger_condition(user_check_threshold)
watchdog.register_recovery_handler(user_recovery_handler)

# 喂狗测试（仅喂狗2次，后续超时触发看门狗）
for i in range(2):
    watchdog.feed()
    time.sleep(2)
```

## 注意事项

1. **喂狗时效性**：`feed()`需在超时时间内调用，否则累计失败次数，达到`max_failures`后触发复位流程；
2. **回调函数优化**：自定义回调函数建议添加`@micropython.native`装饰器，提升执行效率，避免定时器回调阻塞；
3. **日志写入**：确保开发板文件系统有写入权限，日志文件自动分文件（超过10行新建），需预留足够存储空间；
4. **中断安全**：`disable_irq/enable_irq`代码块需尽可能短，避免影响系统中断响应（如定时器、串口等）；
5. **复位风险**：`reset()`会重启开发板，复位前需确保关键数据已写入存储（如日志flush）；
6. **异常缓冲区**：`micropython.alloc_emergency_exception_buf(100)`需在中断代码前调用，否则中断中异常无法打印。

## 联系方式

如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：<liqinghsui@freakstudio.cn>  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议

本项目采用MIT开源许可协议，您可以自由使用、修改、分发本代码，无需授权（需保留版权声明）。

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
