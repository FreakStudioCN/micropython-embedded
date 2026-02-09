# Python env   : MicroPython v1.23.0 on Wiznet W5500
# -*- coding: utf-8 -*-
# @Time    : 2024/8/9 上午11:15
# @Author  : 李清水
# @File    : main.py
# @Description : 实现MQTT客户端的Pub发布功能

# ======================================== 导入相关模块 ========================================

# 导入硬件相关模块
from machine import Pin,SPI,reset,Timer
# 导入时间相关模块
import time
# 导入网络相关模块
import network
# 导入用于创建和管理网络连接的套接字模块
from usocket import socket
# 导入MQTT客户端
from umqttrobust import MQTTClient
# 导入json编码库
import json

# ======================================== 全局变量 ============================================

# 设备IP地址
ip = '192.168.1.20'
sn = '255.255.255.0'
gw = '192.168.1.1'
dns= '8.8.8.8'
# 用于网络连接的元组对象
netinfo=(ip, sn, gw, dns)

# MQTT 配置
mqtt_params = {
    'url': 'broker.emqx.io',           # MQTT 服务器地址
    'port': 1883,                      # MQTT 服务器端口
    'clientid': 'FreakStudioDevice',   # 本机的MQTT客户端ID
    'pubtopic': '/FreakStudio/pub',    # 发布的主题
    'pubqos': 0,                       # 发布的 QoS 等级
    }

# 要发布的消息内容
msg = { 'clientid' : 'FreakStudioDevice',
        'MQTT_Version' : 'v3.1.1',
        'Device' : 'raspberry pi pico',
        'Name' : 'FreakStudio MQTT Sub Test',
    }
# 对消息内容进行json编码
topic_msg = json.dumps(msg)

# 记录定时器运行次数
timer_count = 0

# MQTT 客户端实例
client = None

# ======================================== 功能函数 ============================================

def w5x00_init() -> network.WIZNET5K:
    '''
    初始化 network.WIZNET5K 实例，设置静态 IP 地址并进行连接。

    Returns:
        network.WIZNET5K: 初始化并连接成功的网络接口实例。
    '''

    # 声明全局变量
    global netinfo

    # 初始化SPI对象
    spi = SPI(0, 2_000_000, mosi=Pin(19), miso=Pin(16), sck=Pin(18))
    # 实例化network.WIZNET5K类，传入使用的片选引脚CS和复位引脚RST
    nic = network.WIZNET5K(spi, Pin(17), Pin(20))
    # 激活网络接口
    nic.active(True)

    try:
        print("\r\nConfiguring DHCP")
        # 尝试使用DHCP动态获取IP地址、子网掩码、网关和DNS服务器等网络配置
        nic.ifconfig('dhcp')
    except:
        print("\r\nDHCP fails, use static configuration")
        # 如果DHCP获取失败，使用静态IP地址配置
        nic.ifconfig(netinfo)

    # 若是没有连接网络，则循环执行
    while not nic.isconnected():
        time.sleep(1)
        # 输出寄存器信息
        print(nic.regs())

    # 打印设置的IP地址
    print('ip :', nic.ifconfig()[0])
    print('sn :', nic.ifconfig()[1])
    print('gw :', nic.ifconfig()[2])
    print('dns:', nic.ifconfig()[3])

    # 返回network.WIZNET5K实例
    return nic

def mqtt_connect() -> MQTTClient:
    '''
    连接到 MQTT 服务器。

    Returns:
        MQTTClient: 连接成功的 MQTT 客户端实例。
    '''
    global client_id, mqtt_server

    # 创建 MQTT 客户端实例,设置了连接的保持活跃时间为 60 秒
    client = MQTTClient(mqtt_params['clientid'], mqtt_params['url'], mqtt_params['port'],keepalive=60)
    # 连接到 MQTT 服务器
    client.connect()
    # 打印连接成功的消息
    print('Connected to %s MQTT Broker'%(mqtt_params['url']))
    # 返回 MQTT 客户端实例
    return client

def timer_callback(t: Timer) -> None:
    '''
    定时器回调函数，用于发送心跳包。

    Args:
        t (Timer): 定时器实例。

    Returns:
        None
    '''

    # 声明全局变量
    global timer_count, client

    # 定时器计数值加一
    timer_count = timer_count + 1

    # 如果定时器计数值大于等于 30
    if timer_count >= 30:
        # 重置定时器计数值
        timer_count = 0
        # 发送心跳包
        client.ping()

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 延时3s，等待设备上电
time.sleep(3)
# 打印调试信息
print("FreakStudio : Using WIZNET5K Ethernet Device to connect to MQTT Broker as a Publisher")

# 初始化w5500模块
nic = w5x00_init()

try:
    # 尝试连接到 MQTT 服务器
    client = mqtt_connect()
except OSError as e:
    # 打印异常相关信息，并获取异常的详细回溯信息
    print('raise exception : {}'.format(e))
    # 连接失败时重新连接和重置
    client.reconnect()

# 初始化定时器实例，定时发送MQTT心跳包
timer = Timer(-1)
# 定时器1s调用一次timer_callback函数
timer.init(freq=1, mode=Timer.PERIODIC, callback=timer_callback)

# ========================================  主程序  ===========================================

# 循环发布10次
for i in range(10):
    try:
        # 发布消息到指定主题
        client.publish(mqtt_params['pubtopic'],topic_msg,qos = mqtt_params['pubqos'])
        # 打印调试信息
        print('Message Published: %s' % topic_msg)
        # 等待 3 秒
        time.sleep(3)
    except Exception as e:
        # 打印异常相关信息，并获取异常的详细回溯信息
        print("Failed to publish message")
        print('raise exception : {}'.format(e))

# 断开与 MQTT 服务器的连接
client.disconnect()
# 定时器停止
timer.deinit()