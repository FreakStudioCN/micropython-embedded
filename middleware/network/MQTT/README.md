# MQTT客户端（Wiznet W5500 + MicroPython）

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

本项目基于MicroPython v1.23.0开发，适配Wiznet W5500以太网硬件模块，实现MQTT v3.1.1协议的客户端发布（Pub）与订阅（Sub）功能。针对原生`umqttsimple`模块在弱网/断网场景下易出现死锁、无限递归的问题，扩展实现`umqttrobust`增强模块，支持自动重连、有限次数消息重试等鲁棒性机制，可稳定运行于Raspberry Pi Pico等嵌入式设备，满足工业级弱网环境下的MQTT通信需求。

## 主要功能

1. **网络初始化**：支持Wiznet W5500以太网模块SPI初始化，优先通过DHCP动态获取IP，失败后自动降级为静态IP配置；
2. **MQTT核心通信**：实现MQTT客户端与服务器的连接、发布消息、订阅主题、断开连接、心跳保活（PINGREQ）等核心操作；
3. **鲁棒性增强**：`umqttrobust`模块重写核心方法，捕获弱网场景下的OSError异常，实现自动重连、有限次数消息重试，避免程序死锁；
4. **发布端功能**：循环发布JSON格式自定义消息，通过定时器周期性发送心跳包维持MQTT连接；
5. **订阅端功能**：订阅指定主题并通过回调函数处理消息，统计消息接收次数并向发布主题回传计数信息；
6. **灵活配置**：支持MQTT服务器地址、端口、客户端ID、QoS级别、发布/订阅主题等参数自定义；
7. **异常容错**：针对DHCP失败、MQTT连接/订阅/发布失败等场景提供异常捕获和自动重连逻辑，保证通信稳定性；
8. **心跳维护**：定时器驱动心跳包发送，避免MQTT服务器因超时断开客户端连接。

## 文件说明

| 文件名 | 功能说明 |
|--------|----------|
| `umqttsimple.py` | 轻量MQTT客户端核心实现，封装MQTT v3.1.1协议基础操作（连接、发布、订阅、心跳、遗嘱消息等） |
| `umqttrobust.py` | 增强型MQTT客户端，继承`umqttsimple.MQTTClient`，解决弱网下死锁问题，支持自动重连、有限次数消息重试、调试日志输出 |
| `MQTT_Pub.py` | MQTT发布客户端实现，初始化W5500网络后循环发布JSON格式消息，定时器维护心跳连接，异常时自动重连 |
| `MQTT_Sub.py` | MQTT订阅客户端实现，订阅指定主题并通过回调函数处理消息，统计接收次数并向发布主题回传计数信息 |

## 软件设计核心思想

1. **模块化设计**：将网络初始化（`w5x00_init`）、MQTT连接（`mqtt_connect`）、心跳维护（`timer_callback`）、消息处理（`sub_callback`）等功能拆分为独立函数，降低模块耦合度，便于维护和扩展；
2. **鲁棒性优先**：`umqttrobust`重写`publish`/`wait_msg`/`check_msg`/`reconnect`等方法，捕获OSError异常并触发自动重连，避免弱网下程序卡死；
3. **回调机制解耦**：订阅消息采用`sub_callback`回调函数异步处理，分离消息接收与业务逻辑（如计数、回传），提升代码灵活性；
4. **容错降级设计**：网络配置优先DHCP，失败后自动切换静态IP；MQTT连接/订阅/发布失败时触发重连逻辑，保证通信不中断；
5. **资源精细化管理**：定时器按需初始化/销毁，MQTT连接使用后主动断开，避免嵌入式设备资源泄漏；
6. **参数集中配置**：通过全局字典（`mqtt_params`）管理MQTT服务器、主题、QoS等参数，便于快速适配不同场景。

## 使用说明

### 软件环境

- MicroPython v1.23.0（需适配Wiznet W5500驱动）；
- 依赖模块：`machine`、`network`、`usocket`、`ustruct`、`ubinascii`、`json`（均为MicroPython内置模块）。

### 部署步骤

1. 将`umqttsimple.py`、`umqttrobust.py`、`MQTT_Pub.py`/`MQTT_Sub.py`上传至嵌入式设备文件系统；
2. 硬件接线：按“硬件要求”章节连接W5500模块与主控设备的SPI引脚、CS引脚、RST引脚；
3. 配置修改：根据实际网络环境，修改`MQTT_Pub.py`/`MQTT_Sub.py`中的静态IP（`ip`/`sn`/`gw`/`dns`）、MQTT服务器地址（`mqtt_params['url']`）、端口（`mqtt_params['port']`）、发布/订阅主题等参数；
4. 运行程序：发布端执行`MQTT_Pub.py`，订阅端执行`MQTT_Sub.py`。

## 示例程序

### 1. MQTT发布端运行

```python
# 直接运行发布端脚本
import MQTT_Pub
```

- 预期效果：设备初始化W5500网络（DHCP优先），连接MQTT服务器后循环10次发布JSON格式消息（每3秒1次），定时器每秒维护心跳，发布完成后断开连接；若过程中出现网络异常，自动触发重连逻辑。

### 2. MQTT订阅端运行

```python
# 直接运行订阅端脚本
import MQTT_Sub
```

- 预期效果：设备初始化网络后连接MQTT服务器，订阅指定主题并等待消息；每接收1条消息，计数+1并向发布主题回传计数信息；累计接收10条消息后断开连接，停止定时器。

## 注意事项

1. **网络参数适配**：静态IP（`netinfo`）需与局域网网段匹配，DHCP模式需保证局域网内有可用的DHCP服务器；
2. **MQTT服务器可达性**：确认`mqtt_params['url']`配置的服务器地址可访问，端口（默认1883）未被防火墙拦截；
3. **引脚适配**：若修改W5500的SPI引脚/CS引脚/RST引脚，需同步修改`w5x00_init`函数中的Pin配置；
4. **QoS限制**：`umqttsimple`暂未实现QoS 2完整逻辑，建议使用QoS 0/1；
5. **调试模式**：`umqttrobust.MQTTClient`支持`debug=True`开启调试日志，便于排查通信异常；
6. **心跳配置**：`keepalive`建议设置为60秒以内，定时器心跳周期（1秒）需与`keepalive`匹配，避免服务器主动断开连接；
7. **资源限制**：嵌入式设备内存有限，建议单条MQTT消息大小不超过2KB，避免内存溢出。

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
