# MicroPython 简单任务调度器
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
本项目基于 MicroPython v1.23.0 实现了轻量级的任务调度器，用于在嵌入式设备中管理定时任务的执行。核心包含 `Task` 任务类和 `Scheduler` 调度类，支持任务的动态添加、删除、暂停、恢复，同时提供任务空闲回调和异常回调机制，可灵活适配各类周期性任务场景。

## 主要功能
### Task 任务类
- 封装任务的回调函数、参数、执行间隔和运行状态；
- 支持任务的暂停（`pause`）和恢复（`resume`）操作；
- 提供任务执行入口（`run` 方法），自动传递参数至回调函数。

### Scheduler 调度类
- 基于 `machine.Timer` 定时器实现任务的周期性调度；
- 支持批量管理任务（添加、删除、清空任务列表）；
- 内置任务空闲回调（内存不足时触发垃圾回收）和异常回调（捕获任务执行错误）；
- 按时间片轮询任务状态，仅执行到达间隔的运行态任务；
- 支持任务的手动触发执行（`run` 方法）。

## 文件说明
| 文件名 | 功能说明 |
|--------|----------|
| `Scheduler.py` | 核心模块，定义 `Task` 任务类和 `Scheduler` 调度类，实现任务的封装与调度逻辑 |
| `main.py` | 示例程序，演示调度器的初始化、任务创建/添加/暂停/恢复/删除，以及回调函数的使用 |

## 软件设计核心思想
1. **任务封装**：`Task` 类将任务的回调函数、参数、执行间隔、运行状态等属性封装，通过 `_cnt`（任务间隔与调度器定时器间隔的比值）和 `_rt`（运行计数）控制任务执行时机；
2. **定时器驱动**：`Scheduler` 初始化时绑定定时器，定时器中断中更新任务的运行计数（`_rt`），主循环（`scheduler` 方法）轮询检测计数是否达到阈值，达到则执行任务；
3. **状态管理**：通过 `TASK_RUN`/`TASK_STOP` 状态标识控制任务是否可执行，支持动态暂停/恢复；
4. **异常与空闲处理**：空闲时触发垃圾回收优化内存，任务执行异常时通过回调函数捕获并打印错误信息，保证调度器稳定性。

## 使用说明
### 环境要求
- MicroPython v1.23.0 及以上版本；
- 支持 `machine.Timer` 模块的嵌入式设备（如 ESP32、ESP8266 等）。

### 基本步骤
1. **导入模块**：
   ```python
   from machine import Timer
   from Scheduler import Scheduler, Task
   ```
2. **定义任务回调函数**：
   ```python
   def my_task(task_id):
       print(f"Task {task_id} is running")
   ```
3. **创建任务实例**：
   ```python
   # 创建每500ms执行一次的运行态任务
   task = Task(my_task, 1, interval=500, state=Task.TASK_RUN)
   ```
4. **初始化调度器**：
   ```python
   # 初始化调度器，定时器间隔100ms，绑定空闲/异常回调
   sc = Scheduler(Timer(-1), interval=100, task_idle=task_idle_callback, task_err=task_err_callback)
   ```
5. **添加任务并启动调度**：
   ```python
   sc.add(task)
   sc.scheduler()  # 启动调度主循环
   ```
6. **任务管理操作**：
   ```python
   sc.pause(task)   # 暂停任务
   sc.resume(task)  # 恢复任务
   sc.delete(task)  # 删除任务
   sc.clear()       # 清空所有任务
   ```

## 示例程序
`main.py` 演示了完整的调度器使用流程：
1. 定义带计时装饰器的任务回调函数 `task_callback`，打印任务执行信息并统计运行次数；
2. 初始化时创建任务1（500ms执行一次）、任务2（1000ms执行一次）；
3. 调度器启动后，任务运行至第5次时：暂停任务2、添加任务3（1000ms执行一次）、删除任务1；
4. 任务运行至第8次时，恢复任务2的执行；
5. 空闲回调函数 `task_idle_callback` 检测内存，不足时触发垃圾回收；
6. 异常回调函数 `task_err_callback` 捕获并打印任务执行错误。

运行示例程序后，终端会输出任务执行次数、时间及状态变更日志，可直观看到任务的调度过程。

## 注意事项
1. 任务执行间隔（`interval`）需为调度器定时器间隔（`Scheduler` 的 `interval` 参数）的整数倍，否则会因整除取整导致实际间隔偏差；
2. 调度器主循环（`scheduler` 方法）为死循环，需确保无阻塞操作，避免影响任务调度精度；
3. 定时器建议使用虚拟定时器（`Timer(-1)`），避免占用硬件定时器资源；
4. 任务回调函数应尽量轻量化，长时间阻塞会导致其他任务延迟执行；
5. 垃圾回收、异常处理等回调函数需根据实际场景调整，避免过度占用系统资源。

## 联系方式
如有任何问题或需要帮助，请通过以下方式联系开发者：  
📧 **邮箱**：liqinghsui@freakstudio.cn  
💻 **GitHub**：[https://github.com/FreakStudioCN](https://github.com/FreakStudioCN)

## 许可协议
本项目采用 MIT 开源许可协议，您可以自由使用、修改和分发本项目代码，具体协议内容如下：

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