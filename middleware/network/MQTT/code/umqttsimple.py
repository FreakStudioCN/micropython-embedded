# Python env   : MicroPython v1.23.0 on Wiznet W5500
# -*- coding: utf-8 -*-        
# @Time    : 2024/8/9 上午11:01   
# @Author  : 李清水            
# @File    : umqttsimple.py       
# @Description : 实现一个简单的MQTT客户端类

# ======================================== 导入相关模块 ========================================

# 导入用于网络连接的模块
import usocket as socket
# 导入用于处理字节流和二进制数据的模块
import ustruct as struct
# 导入用于进制转换的模块
from ubinascii import hexlify
# 导入时间相关的模块
import time

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# 定义一个 MQTT 异常类，用于处理 MQTT 操作中的错误
class MQTTException(Exception):
    '''
    自定义 MQTT 异常类，用于处理 MQTT 协议操作中的错误。

    该类继承自 Python 内置的 Exception 类，用于在 MQTT 客户端操作中抛出特定错误。
    '''
    pass

# 定义一个 MQTT 客户端类，用于实现 MQTT 协议的基本操作
class MQTTClient:
    """
    MQTTClient 类，用于实现 MQTT 协议的基本操作，包括连接服务器、发布消息、订阅主题、处理消息等。

    该类封装了 MQTT 协议的客户端功能，支持与 MQTT 服务器进行通信，并提供了消息发布、订阅、遗嘱消息设置等功能。
    支持 SSL/TLS 加密连接，并允许设置心跳时间、用户名和密码等参数。

    Attributes:
        client_id (int): 客户端 ID，用于标识客户端。
        server (str): MQTT 服务器地址。
        port (int): MQTT 服务器端口，默认为 0（自动选择默认端口）。
        user (str): 用户名，默认为 None。
        password (str): 密码，默认为 None。
        keepalive (int): 心跳时间，默认为 0。
        ssl (bool): 是否使用 SSL/TLS 加密连接，默认为 False。
        ssl_params (dict): SSL/TLS 参数，默认为空字典。
        sock (socket): 客户端与服务器通信的套接字。
        pid (int): 报文 ID，用于标识 MQTT 报文。
        cb (callable): 消息回调函数，用于处理接收到的消息。
        lw_topic (str): 遗嘱消息的主题，默认为 None。
        lw_msg (str): 遗嘱消息的内容，默认为 None。
        lw_qos (int): 遗嘱消息的 QoS 级别，默认为 0。
        lw_retain (bool): 遗嘱消息是否保留，默认为 False。

    Methods:
        __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0, ssl=False, ssl_params={}):
            初始化 MQTTClient 类实例。

        _send_str(self, s):
            发送字符串数据到服务器。

        _recv_len(self):
            接收可变长度整数，用于解析 MQTT 报文的长度字段。

        set_callback(self, f):
            设置消息回调函数。

        set_last_will(self, topic, msg, retain=False, qos=0):
            设置遗嘱消息。

        connect(self, clean_session=True):
            连接到 MQTT 服务器。

        disconnect(self):
            断开与 MQTT 服务器的连接。

        ping(self):
            发送心跳请求（PINGREQ）。

        publish(self, topic, msg, retain=False, qos=0):
            发布消息到指定主题。

        subscribe(self, topic, qos=0):
            订阅指定主题。

        wait_msg(self):
            等待并处理单个传入的 MQTT 消息。

        check_msg(self):
            检查是否有来自服务器的挂起消息。
    """
    def __init__(self, client_id: int, server: str, port: int = 0, user: str = None, password: str = None,
                 keepalive: int = 0, ssl: bool = False, ssl_params: dict = {}) -> None:
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
            ssl_params (dict): SSL 参数，默认为空字典

        Returns:
            None
        '''

        # 如果未指定端口，则使用默认端口
        if port == 0:
            # 如果使用 SSL，则使用端口 8883，否则使用 1883
            port = 8883 if ssl else 1883

        self.client_id = client_id
        # 初始化套接字为 None
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        # 初始化报文 ID 为 0
        self.pid = 0
        # 初始化回调函数为 None
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive

        # 初始化遗嘱主题为 None
        self.lw_topic = None
        # 初始化遗嘱消息为 None
        self.lw_msg = None
        # 初始化遗嘱 QoS 为 0
        self.lw_qos = 0
        # 初始化遗嘱消息不保留
        self.lw_retain = False

    # 发送字符串数据
    def _send_str(self, s: str) -> None:
        '''
        发送字符串数据

        Args:
            s (str): 待发送的字符串

        Returns:
            None
        '''
        # 发送字符串长度
        self.sock.write(struct.pack("!H", len(s)))
        # 发送字符串内容
        self.sock.write(s)

    # 接收可变长度整数，用于 MQTT 报文的长度字段
    def _recv_len(self) -> int:
        '''
        接收可变长度整数，用于 MQTT 报文的长度字段

        Returns:
            int: 接收到的长度
        '''
        # 初始化长度为 0
        n = 0
        # 初始化移位量为 0
        sh = 0

        # 循环接收字节
        while True:
            # 读取一个字节
            b = self.sock.read(1)[0]
            # 解析字节的低 7 位
            n |= (b & 0x7F) << sh
            # 如果最高位为 0，表示结束
            if not b & 0x80:
                # 返回接收到的长度
                return n
                # 否则，继续读取下一个字节
            sh += 7

    # 设置消息回调函数
    def set_callback(self, f: callable) -> None:
        '''
        设置消息回调函数

        Args:
            f (callable): 回调函数

        Returns:
            None
        '''
        # 保存回调函数
        self.cb = f

    # 设置遗嘱消息
    def set_last_will(self, topic: str, msg: str, retain: bool = False, qos: int = 0) -> None:
        '''
        设置遗嘱消息

        Args:
            topic (str): 主题
            msg (str): 消息
            retain (bool): 是否保留，默认为 False
            qos (int): QoS 质量，默认为 0

        Returns:
            None

        Raises:
            AssertionError: 如果 QoS 不在有效范围内或主题为空
        '''

        # 验证 QoS 是否在有效范围内
        assert 0 <= qos <= 2
        # 验证主题是否存在
        assert topic

        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    # 连接到 MQTT 服务器
    def connect(self, clean_session: bool = True) -> int:
        '''
        连接到 MQTT 服务器

        Args:
            clean_session (bool): 是否清除会话，默认为 True

        Returns:
            int: 连接结果

        Raises:
            MQTTException: 如果连接失败
        '''

        # 创建套接字
        self.sock = socket.socket()
        # 获取服务器地址信息
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        # 连接到服务器
        self.sock.connect(addr)

        # 如果使用 SSL
        if self.ssl:
            # 导入 SSL 模块
            import ussl
            # 包装套接字为 SSL
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)

        # 创建固定头的字节数组
        premsg = bytearray(b"\x10\0\0\0\0\0")
        # 创建可变头和有效载荷的字节数组
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        # 计算消息的总长度
        sz = 10 + 2 + len(self.client_id)
        # 设置清除会话标志
        msg[6] = clean_session << 1

        # 如果使用用户名和密码
        if self.user is not None:
            # 更新消息长度
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            # 设置用户名和密码标志
            msg[6] |= 0xC0

        # 如果设置了保活时间
        if self.keepalive:  # 如果设置了保活时间
            # 验证保活时间是否在有效范围内
            assert self.keepalive < 65536
            # 设置保活时间的高位
            msg[7] |= self.keepalive >> 8
            # 设置保活时间的低位
            msg[8] |= self.keepalive & 0x00FF

        # 如果设置了遗嘱消息
        if self.lw_topic:
            # 更新消息长度
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            # 设置遗嘱 QoS
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            # 设置遗嘱消息保留标志
            msg[6] |= self.lw_retain << 5

        # 初始化长度字段的字节数
        i = 1

        # 如果长度超过 7 位
        while sz > 0x7F:
            # 继续处理长度字段
            premsg[i] = (sz & 0x7F) | 0x80
            # 移位处理
            sz >>= 7
            # 增加字节数
            i += 1
        # 设置最后一个字节的长度
        premsg[i] = sz

        # 发送固定头
        self.sock.write(premsg, i + 2)
        # 发送可变头和有效载荷
        self.sock.write(msg)

        # 发送客户端 ID
        self._send_str(self.client_id)

        # 如果设置了遗嘱消息
        if self.lw_topic:
            # 发送遗嘱主题
            self._send_str(self.lw_topic)
            # 发送遗嘱消息
            self._send_str(self.lw_msg)

        # 如果使用用户名和密码
        if self.user is not None:
            # 发送用户名
            self._send_str(self.user)
            # 发送密码
            self._send_str(self.pswd)

        # 读取服务器响应
        resp = self.sock.read(4)

        # 验证连接确认报文
        assert resp[0] == 0x20 and resp[1] == 0x02

        # 如果连接失败
        if resp[3] != 0:
            # 抛出异常
            raise MQTTException(resp[3])

        # 返回连接结果
        return resp[2] & 1

    # 断开与 MQTT 服务器的连接
    def disconnect(self) -> None:
        '''
        断开与 MQTT 服务器的连接

        Returns:
            None
        '''
        # 发送断开连接报文
        self.sock.write(b"\xe0\0")
        # 关闭套接字
        self.sock.close()

    # 发送心跳请求（PINGREQ）
    def ping(self) -> None:
        '''
        发送心跳请求（PINGREQ）

        Returns:
            None
        '''
        self.sock.write(b"\xc0\0")

    # 发布消息
    def publish(self, topic: str, msg: str, retain: bool = False, qos: int = 0) -> None:
        '''
        发布消息

        Args:
            topic (str): 主题
            msg (str): 消息
            retain (bool): 是否保留，默认为 False
            qos (int): 服务质量级别 (0, 1, 2)，默认为 0

        Returns:
            None

        Raises:
            AssertionError: 如果消息大小超过 MQTT 协议限制
        '''

        # 创建 MQTT 发布数据包的基本结构，默认设置 QoS 为 0，retain 标志为 False
        pkt = bytearray(b"\x30\0\0\0")

        # 根据 retain 标志和 QoS 设置数据包的标志位
        pkt[0] |= qos << 1 | retain

        # 计算消息总大小：2 字节用于主题长度，余下的用于消息长度
        sz = 2 + len(topic) + len(msg)

        # 如果 QoS 大于 0，则增加 2 字节用于 packet identifier (PID)
        if qos > 0:
            sz += 2

        # 断言消息总大小小于 2097152 字节（MQTT 协议的限制）
        assert sz < 2097152

        # 编码消息大小，采用可变长度编码方案
        i = 1

        while sz > 0x7F:
            pkt[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz

        # 将构建好的发布数据包发送给服务器
        self.sock.write(pkt, i + 1)

        # 发送主题字符串
        self._send_str(topic)

        # 如果 QoS 大于 0，增加 packet identifier (PID) 并发送
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self.sock.write(pkt, 2)

        # 发送消息内容
        self.sock.write(msg)

        # 如果 QoS 等于 1，等待服务器的 PUBACK 响应
        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:  # 0x40 表示 PUBACK 报文
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return

        # 如果 QoS 等于 2，抛出异常（该代码未实现 QoS 2 的逻辑）
        elif qos == 2:
            assert 0

    def subscribe(self, topic: str, qos: int = 0) -> None:
        '''
        订阅主题

        Args:
            topic (str): 主题
            qos (int): QoS 质量，默认为 0

        Returns:
            None

        Raises:
            AssertionError: 如果订阅回调函数未设置
            MQTTException: 如果服务器返回错误代码
        '''

        # 确保已设置订阅回调函数
        assert self.cb is not None, "Subscribe callback is not set"

        # 创建 MQTT 订阅数据包的基本结构
        pkt = bytearray(b"\x82\0\0\0")

        # 增加 packet identifier (PID)
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)

        # 发送订阅数据包
        self.sock.write(pkt)
        # 发送主题字符串
        self._send_str(topic)
        # 发送 QoS 级别
        self.sock.write(qos.to_bytes(1, "little"))

        # 等待服务器的 SUBACK 响应
        while 1:
            op = self.wait_msg()
            # 0x90 表示 SUBACK 报文
            if op == 0x90:
                resp = self.sock.read(4)
                assert resp[1] == pkt[2] and resp[2] == pkt[3]
                if resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    # 等待单个传入的 MQTT 消息并处理
    # 订阅的消息将传递给之前通过 .set_callback() 方法设置的回调函数
    # 其他（内部）MQTT 消息由内部处理
    def wait_msg(self) -> int:
        '''
        等待单个传入的 MQTT 消息并处理

        Returns:
            int: 返回操作码，如果没有收到消息则返回 None

        Raises:
            OSError: 如果读取到空消息
            AssertionError: 如果接收到无效的 PINGRESP 报文
        '''

        # 读取来自服务器的一个字节
        res = self.sock.read(1)

        # 如果未收到消息，返回 None
        if res is None:
            return None

        # 如果收到空消息，抛出错误
        if res == b"":
            raise OSError(-1)

        # 如果收到的是 PINGRESP 报文（0xD0），读取其长度（应为 0），然后返回 None
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None

        # 解析操作码
        op = res[0]
        # 如果不是发布消息（0x30 开头），返回操作码
        if op & 0xF0 != 0x30:
            return op

        # 读取消息的剩余长度
        sz = self._recv_len()

        # 读取主题长度
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]

        # 读取主题内容
        topic = self.sock.read(topic_len)

        # 减去已读取的长度
        sz -= topic_len + 2

        # 如果 QoS 大于 0，读取 packet identifier (PID)
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2

        # 读取消息内容
        msg = self.sock.read(sz)

        # 调用回调函数处理接收到的消息
        self.cb(topic, msg)

        # 如果 QoS 为 1，发送 PUBACK 确认
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)

        # 如果 QoS 为 2，抛出异常（未实现）
        elif op & 6 == 4:
            assert 0
        return op

    # 检查是否有来自服务器的挂起消息。
    def check_msg(self) -> int:
        '''
        检查是否有来自服务器的挂起消息

        Returns:
            int: 返回操作码，如果没有收到消息则返回 None
        '''
        return self.wait_msg()

# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
