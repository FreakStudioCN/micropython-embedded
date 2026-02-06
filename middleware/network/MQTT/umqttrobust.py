# Python env   : MicroPython v1.23.0 on Wiznet W5500
# -*- coding: utf-8 -*-        
# @Time    : 2024/8/9 下午11:38   
# @Author  : 李清水            
# @File    : umqttrobust.py       
# @Description : 该模块用于解决umqttsimple模块在弱网或断网后可能出现死锁或无限递归等问题

# ======================================== 导入相关模块 ========================================

# 导入时间相关模块
import time
# 导入umqttsimple模块
import umqttsimple

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 继承自 umqttsimple.MQTTClient 类，用于解决umqttsimple模块在弱网或断网后可能出现死锁或无限递归等问题
class MQTTClient(umqttsimple.MQTTClient):
    """
    MQTTClient 类，继承自 umqttsimple.MQTTClient，用于增强 MQTT 客户端功能。

    该类在 umqttsimple.MQTTClient 的基础上增加了以下功能：
    - 支持调试模式，输出详细的错误日志。
    - 在网络不稳定或断网情况下，自动重连 MQTT 服务器。
    - 提供有限次数的消息检查和重试机制，避免无限阻塞。

    Attributes:
        client_id (int): 客户端 ID，用于标识客户端。
        server (str): MQTT 服务器地址。
        port (int): MQTT 服务器端口，默认为 0（自动选择默认端口）。
        user (str): 用户名，默认为 None。
        password (str): 密码，默认为 None。
        keepalive (int): 心跳时间，默认为 0。
        ssl (bool): 是否使用 SSL/TLS 加密连接，默认为 False。
        debug (bool): 是否输出调试信息，默认为 False。
        ssl_params (dict): SSL/TLS 参数，默认为空字典。
        sock (socket): 客户端与服务器通信的套接字。
        pid (int): 报文 ID，用于标识 MQTT 报文。
        cb (callable): 消息回调函数，用于处理接收到的消息。
        lw_topic (str): 遗嘱消息的主题，默认为 None。
        lw_msg (str): 遗嘱消息的内容，默认为 None。
        lw_qos (int): 遗嘱消息的 QoS 级别，默认为 0。
        lw_retain (bool): 遗嘱消息是否保留，默认为 False。

    Methods:
        __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0, ssl=False, debug=False, ssl_params={}):
            初始化 MQTTClient 类实例。

        log(self, in_reconnect, e):
            用于调试时输出错误信息。

        reconnect(self):
            在网络不稳定情况下重连 MQTT 服务器。

        publish(self, topic, msg, retain=False, qos=0):
            发布消息到指定主题，支持自动重连。

        wait_msg(self):
            等待并处理单个传入的 MQTT 消息，支持自动重连。

        check_msg(self, attempts=2):
            检查是否有来自服务器的挂起消息，提供有限次数的重试机制。
    """

    def __init__(self, client_id: int, server: str, port: int = 0, user: str = None, password: str = None, keepalive: int = 0, ssl: bool = False, debug: bool = False, ssl_params: dict = {}) -> None:
        '''
        初始化 MQTT 客户端类

        Args:
            client_id (int): 客户端 ID
            server (str): 服务器地址
            port (int): 服务器端口，默认为 0（自动选择默认端口）
            user (str): 用户名，默认为 None
            password (str): 密码，默认为 None
            keepalive (int): 心跳时间，默认为 0
            ssl (bool): 是否使用 SSL，默认为 False
            debug (bool): 是否输出调试信息，默认为 False
            ssl_params (dict): SSL 参数，默认为空字典

        Returns:
            None
        '''

        # 调用父类的初始化方法
        super().__init__(client_id, server, port, user, password, keepalive, ssl, ssl_params, )
        # 初始化 debug 属性，用于控制是否输出调试信息
        self.debug = debug

    def log(self, in_reconnect: bool, e: Exception) -> None:
        '''
        用于调试时输出错误信息

        Args:
            in_reconnect (bool): 是否在重连过程中出错
            e (Exception): 错误信息

        Returns:
            None
        '''

        # 只有在 debug 模式下（debug=True）才会打印日志
        if self.debug:
            # 判断是否在重连过程中出错，决定输出的日志内容
            if in_reconnect:
                print("mqtt reconnect: %r" % e)
            else:
                print("mqtt: %r" % e)

    def reconnect(self) -> None:
        '''
        用于在网络不稳定情况下重连 MQTT 服务器

        Returns:
            None
        '''

        # 初始化重试次数计数器 i
        i = 0

        # 无限循环，直到连接成功
        while True:
            # 尝试连接到 MQTT 服务器
            try:
                # 调用父类的 connect 方法进行连接。参数 False 表示不保持之前的会话
                return super().connect(False)
            # 如果捕获到 OSError 异常，说明连接失败
            except OSError as e:
                # 调用 log 方法记录重连错误信息
                self.log(True, e)
                # 增加重试计数器 i，用于控制下一次重连前的等待时间
                i += 1
                # 根据重试次数 i 进行等待，防止频繁重试
                time.sleep(i)

    def publish(self, topic: str, msg: str, retain: bool = False, qos: int = 0) -> None:
        '''
        定义一个发布消息的函数，处理在网络不稳定情况下可能的发布失败

        Args:
            topic (str): 主题
            msg (str): 消息
            retain (bool): 是否保留，默认为 False
            qos (int): QoS 质量，默认为 0

        Returns:
            None
        '''

        # 无限循环，直到成功发布消息
        while True:
            # 尝试发布消息
            try:
                # 调用父类的 publish 方法将消息发布到指定主题
                return super().publish(topic, msg, retain, qos)
            # 捕获发布消息时的 OSError 异常
            except OSError as e:
                # 调用 log 方法记录发布失败的错误信息
                self.log(False, e)
            # 如果发布失败，尝试重新连接 MQTT 服务器，并在下一次循环中再次尝试发布
            self.reconnect()

    def wait_msg(self) -> int:
        '''
        定义一个等待消息的函数，处理在网络不稳定情况下可能的等待失败
        阻塞式运行，直到接收消息才会返回

        Returns:
            int: 返回操作码
        '''

        # 无限循环，直到成功接收到消息
        while True:
            # 尝试接收消息
            try:
                # 调用父类的 wait_msg 方法等待并接收消息
                return super().wait_msg()
            # 捕获接收消息时的 OSError 异常
            except OSError as e:
                # 调用 log 方法记录接收失败的错误信息
                self.log(False, e)
            # 如果接收消息失败，尝试重新连接 MQTT 服务器，并在下一次循环中再次尝试接收消息
            self.reconnect()

    def check_msg(self, attempts: int = 2) -> int:
        '''
        定义一个检查消息的函数，处理在网络不稳定情况下可能的检查失败
        提供有限次数的消息检查和重试

        Args:
            attempts (int): 重试次数，默认为 2

        Returns:
            int or None: 返回操作码，如果没有收到消息则返回 None
        '''
        # 循环检查消息，最多尝试 attempts 次
        while attempts:
            # 将套接字设置为非阻塞模式，确保 wait_msg 方法不会阻塞等待消息
            self.sock.setblocking(False)

            # 尝试接收消息
            try:
                # 调用父类的 wait_msg 方法接收消息
                return super().wait_msg()
            #  捕获接收消息时的 OSError 异常
            except OSError as e:
                # 调用 log 方法记录接收消息失败的错误信息
                self.log(False, e)
            # 如果接收消息失败，尝试重新连接 MQTT 服务器
            self.reconnect()
            # 减少剩余尝试次数，如果尝试次数用尽，则退出循环
            attempts -= 1

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
