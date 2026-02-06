# Python env   : MicroPython v1.23.0 on Wiznet W5500
# -*- coding: utf-8 -*-        
# @Time    : 2024/8/10 下午10:22   
# @Author  : 李清水            
# @File    : main.py       
# @Description : 实现MQTT客户端的Sub订阅功能

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
    'subtopic': '/FreakStudio/sub',    # 订阅的主题
    'pubqos': 0,                       # 发布的 QoS 等级
    'subqos': 0,                       # 订阅的 QoS 等级
    }

# 记录定时器运行次数
timer_count = 0
# MQTT 客户端实例
client = None
# MQTT接收计数值
msg_recv_count = 0

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

def sub_callback(topic: bytes, msg: bytes) -> None:
    '''
    订阅主题的回调函数，用于处理订阅主题的消息。

    Args:
        topic (bytes): 订阅的主题。
        msg (bytes): 接收到对应主题的消息。

    Returns:
        None
    '''
    # 声明全局变量：MQTT客户端实例 + 接收计数器
    global client, msg_recv_count

    # 将主题和消息（MQTT中以字节流传输）进行解码，转换为 UTF-8 字符串格式
    topic = topic.decode('utf-8')
    msg = msg.decode('utf-8')

    # 判断接收到的主题是否为配置的订阅主题
    if topic == mqtt_params['subtopic']:
        # 接收次数自增（每次收到目标主题消息，计数+1）
        msg_recv_count += 1

        # 打印接收到的主题、消息内容及当前接收次数
        print(f"\r\ntopic: {topic} \r\nrecv: {msg} \r\ncurrent receive count: {msg_recv_count}")

        # 发布消息时加入接收次数（关键修改：消息格式包含count）
        publish_msg = f'recv: {msg} | total receive count: {msg_recv_count}'
        client.publish(mqtt_params['pubtopic'], publish_msg, qos=mqtt_params['pubqos'])

        # 打印发送的主题、带次数的消息内容
        print(f'\r\ntopic: {mqtt_params["pubtopic"]} \r\nsend: {publish_msg}')

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 延时3s，等待设备上电
time.sleep(3)
# 打印调试信息
print("FreakStudio : Using WIZNET5K Ethernet Device to connect to MQTT Broker as a Subscriber")

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

# 设置回调函数，当收到订阅的主题消息时，调用 sub_callback 函数处理消息
client.set_callback(sub_callback)

# 无限循环，直到订阅成功跳出循环
while True:
    try:
        # 订阅指定的主题，并设置 QoS 等级，以便接收该主题的消息
        client.subscribe(mqtt_params['subtopic'],mqtt_params['subqos'])
        # 打印订阅成功的消息，显示订阅的主题
        print('subscribed to %s'%mqtt_params['subtopic'])
        # 订阅成功跳出循环
        break
    except OSError as e:
        # 打印异常相关信息，并获取异常的详细回溯信息
        print('raise exception : {}'.format(e))
        # 订阅失败时重新订阅和重置
        client.reconnect()

# 连续10次接收消息
while msg_recv_count<10:
    # 等待接收消息
    msg = client.wait_msg()

# 断开与 MQTT 服务器的连接
client.disconnect()
# 定时器停止
timer.deinit()