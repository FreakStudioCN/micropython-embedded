# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/14
# @Author  : leeqingsui
# @File    : xfyun_asr.py
# @Description : iFlytek online ASR (large model) driver over WebSocket for MicroPython
# @License : MIT

__version__  = "1.0.0"
__author__   = "leeqingsui"
__license__  = "MIT"
__platform__ = "MicroPython v1.23"

# ======================================== 导入相关模块 =========================================

import json
import time
import binascii
import hashlib
import asyncio
from async_websocketclient import AsyncWebsocketClient, URI

# ======================================== 全局变量 ============================================

# 讯飞中英识别大模型 WebSocket 接入点
_HOST    = "iat.xf-yun.com"
_PATH    = "/v1"
_WSS_URL = "wss://iat.xf-yun.com/v1"

# 每帧音频字节数（API 规范：16-bit PCM 每次发送 1280 字节）
_FRAME_SIZE = 1280

# RFC1123 日期格式所需的星期与月份名称表
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS   = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# ======================================== 功能函数 ============================================

def _rfc1123_now():
    """
    获取当前 UTC 时间的 RFC1123 格式字符串，调用前需通过 ntptime.settime() 同步时间。

    Returns:
        str: RFC1123 格式时间字符串，例如 "Thu, 10 Apr 2026 12:00:00 GMT"。

    ==========================================

    Return current UTC time in RFC1123 format. Requires ntptime.settime() before calling.

    Returns:
        str: RFC1123-formatted time string, e.g. "Thu, 10 Apr 2026 12:00:00 GMT".
    """
    # 获取当前 UTC 时间元组
    t = time.gmtime()
    # gmtime() -> (year, month, mday, hour, minute, second, weekday, yearday)
    # weekday: 0=Monday, 6=Sunday
    return "{wd}, {d:02d} {mon} {y} {h:02d}:{m:02d}:{s:02d} GMT".format(
        wd  = _WEEKDAYS[t[6]],
        d   = t[2],
        mon = _MONTHS[t[1] - 1],
        y   = t[0],
        h   = t[3],
        m   = t[4],
        s   = t[5],
    )


def _hmac_sha256(key, msg):
    """
    纯 MicroPython 实现 HMAC-SHA256，不依赖标准 hmac 模块。

    Args:
        key (bytes): HMAC 密钥。
        msg (bytes): 待签名消息。

    Returns:
        bytes: 32 字节 HMAC-SHA256 摘要。

    ==========================================

    Pure MicroPython HMAC-SHA256 without the standard hmac module.

    Args:
        key (bytes): HMAC key.
        msg (bytes): Message to sign.

    Returns:
        bytes: 32-byte HMAC-SHA256 digest.
    """
    block_size = 64
    # 若密钥超过块大小则先做哈希压缩
    if len(key) > block_size:
        key = hashlib.sha256(key).digest()
    # 补零至块大小
    key       = key + b'\x00' * (block_size - len(key))
    # 构造外层和内层填充
    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)
    # 两次 SHA256：先内层再外层
    inner     = hashlib.sha256(i_key_pad + msg).digest()
    return hashlib.sha256(o_key_pad + inner).digest()


def _url_encode(s):
    """
    URL 百分号编码，保留字母、数字及 -_.~ 字符，其余字节转义为 %XX。

    Args:
        s (str): 待编码的字符串。

    Returns:
        str: URL 编码后的字符串。

    ==========================================

    URL percent-encode a string, leaving letters, digits and -_.~ unescaped.

    Args:
        s (str): String to encode.

    Returns:
        str: URL-encoded string.
    """
    # RFC3986 非保留字符集，这些字符无需编码
    _safe = frozenset(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~'
    )
    out = []
    for ch in s:
        if ch in _safe:
            # 安全字符直接追加
            out.append(ch)
        else:
            # 非安全字符逐字节转义为 %XX
            for byte in ch.encode('utf-8'):
                out.append('%{:02X}'.format(byte))
    return ''.join(out)

# ======================================== 自定义类 ============================================

class _WsClient(AsyncWebsocketClient):
    """
    AsyncWebsocketClient 子类，用非递归字符串解析替换原正则解析。

    MicroPython 的 ure 正则引擎为递归实现，对超过约 30 字符的路径段
    （如含鉴权参数的长 URL）会触发 "maximum recursion depth exceeded"。
    本子类仅覆盖 urlparse()，其余逻辑完全继承自父类。

    ==========================================

    Subclass of AsyncWebsocketClient that replaces regex-based URL parsing
    with iterative string operations.

    MicroPython's ure regex engine is recursive; paths longer than ~30 chars
    (e.g. auth query strings) exceed the stack limit and raise
    "maximum recursion depth exceeded". Only urlparse() is overridden here.
    """

    def urlparse(self, uri: str):
        """
        解析 ws:// 或 wss:// URL，使用纯字符串操作，无递归风险。

        Args:
            uri (str): WebSocket URL，支持含查询字符串的长路径。

        Returns:
            URI: 包含 protocol、hostname、port、path 的具名元组。

        Raises:
            ValueError: 协议不是 ws 或 wss 时抛出。

        ==========================================

        Parse a ws:// or wss:// URL using plain string ops (no regex, no recursion).

        Args:
            uri (str): WebSocket URL, supports long paths with query strings.

        Returns:
            URI: Named tuple with protocol, hostname, port, path fields.

        Raises:
            ValueError: Raised when scheme is not ws or wss.
        """
        # 参数校验
        if uri is None:
            raise ValueError("uri cannot be None")
        if not isinstance(uri, str):
            raise TypeError("uri must be str, got {}".format(type(uri).__name__))

        # 判断协议并截取主机+路径部分
        if uri.startswith('wss://'):
            protocol, rest, default_port = 'wss', uri[6:], 443
        elif uri.startswith('ws://'):
            protocol, rest, default_port = 'ws', uri[5:], 80
        else:
            raise ValueError("Scheme not ws or wss")

        # 分离主机部分与路径部分
        slash = rest.find('/')
        if slash == -1:
            hostpart, path = rest, '/'
        else:
            hostpart, path = rest[:slash], rest[slash:]

        # 分离主机名与端口
        colon = hostpart.find(':')
        if colon == -1:
            hostname, port = hostpart, default_port
        else:
            hostname, port = hostpart[:colon], int(hostpart[colon + 1:])

        return URI(protocol, hostname, port, path)


class XfyunASR:
    """
    讯飞中英识别大模型 ASR 驱动，基于 WebSocket API，将 PCM 音频文件识别为文字。
    支持中文、英文及 202 种方言。流式分帧发送，先发完所有帧再接收结果，
    内存峰值仅为单帧大小（1280 字节），与音频时长无关。

    Attributes:
        _app_id      (str): 讯飞开放平台 APPID。
        _api_key     (str): API Key。
        _api_secret  (str): API Secret（平台提供的原始字符串，勿 Base64 解码）。
        _sample_rate (int): 音频采样率，8000 或 16000。
        _accent      (str): 口音/方言，默认 "mandarin"。
        _eos         (int): 静音停止阈值（毫秒），默认 6000。
        _ws          (_WsClient): 内部 WebSocket 客户端实例。

    Methods:
        recognize(filepath): 识别指定 PCM 文件，返回识别文字字符串。

    Notes:
        - 调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
        - API Secret 直接以 UTF-8 字节作为 HMAC 密钥，不得对其 Base64 解码。
        - 音频格式要求：16-bit 有符号 PCM，单声道，采样率与初始化参数一致。

    ==========================================

    iFlytek Chinese-English large model ASR driver over WebSocket API.
    Supports Chinese, English and 202 dialects.
    Sends PCM audio in streaming frames then collects text; peak RAM is one frame (1280 bytes).

    Attributes:
        _app_id      (str): iFlytek APPID.
        _api_key     (str): API Key.
        _api_secret  (str): API Secret (raw string from platform; do NOT Base64-decode).
        _sample_rate (int): Audio sample rate, 8000 or 16000.
        _accent      (str): Accent/dialect, default "mandarin".
        _eos         (int): Silence-to-stop threshold in ms, default 6000.
        _ws          (_WsClient): Internal WebSocket client instance.

    Methods:
        recognize(filepath): Recognize a PCM file and return the transcribed text.

    Notes:
        - WiFi must be connected and system time NTP-synced before calling.
        - API Secret must be used as raw UTF-8 bytes for HMAC; do NOT Base64-decode it.
        - Audio format: 16-bit signed PCM, mono, sample rate matching init parameter.
    """

    def __init__(self, app_id: str, api_key: str, api_secret: str,
                 sample_rate: int = 16000, accent: str = "mandarin", eos: int = 6000) -> None:
        """
        初始化 ASR 驱动，保存鉴权参数与识别配置。

        Args:
            app_id      (str): 讯飞开放平台 APPID。
            api_key     (str): API Key。
            api_secret  (str): API Secret（平台提供的原始字符串）。
            sample_rate (int): 音频采样率，8000 或 16000，默认 16000。
            accent      (str): 口音/方言，默认 "mandarin"。
            eos         (int): 静音停止阈值（毫秒），默认 6000。

        Raises:
            ValueError: 任意字符串参数为空，或 sample_rate 不是 8000/16000，或 eos 不在合理范围。
            TypeError:  参数类型不符合要求。

        ==========================================

        Initialize the ASR driver with authentication and recognition parameters.

        Args:
            app_id      (str): iFlytek APPID.
            api_key     (str): API Key.
            api_secret  (str): API Secret (raw string from platform).
            sample_rate (int): Audio sample rate, 8000 or 16000, default 16000.
            accent      (str): Accent/dialect, default "mandarin".
            eos         (int): Silence-to-stop threshold in ms, default 6000.

        Raises:
            ValueError: Any string param is empty, sample_rate not 8000/16000, or eos out of range.
            TypeError:  Parameter type mismatch.
        """
        # 校验 app_id
        if app_id is None:
            raise ValueError("app_id cannot be None")
        if not isinstance(app_id, str):
            raise TypeError("app_id must be str, got {}".format(type(app_id).__name__))
        if len(app_id) == 0:
            raise ValueError("app_id cannot be empty")

        # 校验 api_key
        if api_key is None:
            raise ValueError("api_key cannot be None")
        if not isinstance(api_key, str):
            raise TypeError("api_key must be str, got {}".format(type(api_key).__name__))
        if len(api_key) == 0:
            raise ValueError("api_key cannot be empty")

        # 校验 api_secret
        if api_secret is None:
            raise ValueError("api_secret cannot be None")
        if not isinstance(api_secret, str):
            raise TypeError("api_secret must be str, got {}".format(type(api_secret).__name__))
        if len(api_secret) == 0:
            raise ValueError("api_secret cannot be empty")

        # 校验 sample_rate（仅支持 8000 和 16000）
        if not isinstance(sample_rate, int):
            raise TypeError("sample_rate must be int, got {}".format(type(sample_rate).__name__))
        if sample_rate not in (8000, 16000):
            raise ValueError("sample_rate must be 8000 or 16000, got {}".format(sample_rate))

        # 校验 accent
        if accent is None:
            raise ValueError("accent cannot be None")
        if not isinstance(accent, str):
            raise TypeError("accent must be str, got {}".format(type(accent).__name__))
        if len(accent) == 0:
            raise ValueError("accent cannot be empty")

        # 校验 eos（合理范围 500ms ~ 60000ms）
        if not isinstance(eos, int):
            raise TypeError("eos must be int, got {}".format(type(eos).__name__))
        if eos < 500 or eos > 60000:
            raise ValueError("eos must be between 500 and 60000, got {}".format(eos))

        # 保存鉴权参数
        self._app_id      = app_id
        self._api_key     = api_key
        self._api_secret  = api_secret
        # 保存识别配置
        self._sample_rate = sample_rate
        self._accent      = accent
        self._eos         = eos
        # 创建 WebSocket 客户端实例（每次 recognize 调用时重建，此处仅占位）
        self._ws          = _WsClient(ms_delay_for_read=5)

    def _build_auth_url(self) -> str:
        """
        构造带 HMAC-SHA256 鉴权参数的讯飞 ASR WebSocket 请求 URL。

        Returns:
            str: 包含 authorization、date、host 查询参数的 WSS URL。

        ==========================================

        Build the iFlytek ASR WebSocket URL with HMAC-SHA256 authentication query parameters.

        Returns:
            str: WSS URL containing authorization, date, and host query parameters.
        """
        # 获取当前 UTC 时间（RFC1123 格式），用于签名和 URL 参数
        date = _rfc1123_now()

        # 按讯飞规范拼接签名原文：host + date + request-line
        sig_origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(_HOST, date, _PATH)

        # API Secret 直接以 UTF-8 字节作为 HMAC 密钥（不得 Base64 解码）
        secret_bytes = self._api_secret.encode('utf-8')
        sig_bytes    = _hmac_sha256(secret_bytes, sig_origin.encode('utf-8'))
        # Base64 编码签名摘要
        sig_b64      = binascii.b2a_base64(sig_bytes).decode('utf-8').strip()

        # 拼接 authorization 原文并 Base64 编码
        auth_origin = (
            'api_key="{}", algorithm="hmac-sha256", '
            'headers="host date request-line", signature="{}"'
        ).format(self._api_key, sig_b64)
        auth_b64 = binascii.b2a_base64(auth_origin.encode('utf-8')).decode('utf-8').strip()

        # 拼接最终 WSS URL，三个参数均需 URL 百分号编码
        return "{}?authorization={}&date={}&host={}".format(
            _WSS_URL,
            _url_encode(auth_b64),
            _url_encode(date),
            _url_encode(_HOST),
        )

    async def recognize(self, filepath: str) -> str:
        """
        连接讯飞 ASR 服务，流式发送 PCM 音频文件，接收并拼接识别文字。

        发送策略：先将文件所有帧发完（status 0→1→2），再进入接收循环，
        规避 MicroPython 单线程 asyncio 无法真正并发收发的限制。
        内存中同时只存在单帧数据（1280 字节），与音频总时长无关。

        Args:
            filepath (str): PCM 音频文件路径（16-bit 有符号，单声道，采样率与初始化一致）。

        Returns:
            str: 识别结果文字；失败或无结果时返回 ""。

        Raises:
            ValueError: filepath 为 None 或空字符串。
            TypeError:  filepath 不是字符串类型。

        Notes:
            调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
            服务端 header.status==2 表示最后一帧结果，收到后主动关闭连接。

        ==========================================

        Connect to iFlytek ASR, stream PCM audio frames, then collect and return recognized text.

        Sends all frames first (status 0→1→2), then enters receive loop to avoid
        the need for true concurrency in MicroPython's single-threaded asyncio.
        Peak RAM usage is one frame (1280 bytes), independent of audio length.

        Args:
            filepath (str): PCM audio file path (16-bit signed, mono, matching init sample_rate).

        Returns:
            str: Recognized text; "" on failure or empty result.

        Raises:
            ValueError: filepath is None or empty string.
            TypeError:  filepath is not a string.

        Notes:
            WiFi must be connected and system time NTP-synced before calling.
            Server header.status==2 marks the final result frame; connection is closed afterward.
        """
        # 校验 filepath
        if filepath is None:
            raise ValueError("filepath cannot be None")
        if not isinstance(filepath, str):
            raise TypeError("filepath must be str, got {}".format(type(filepath).__name__))
        if len(filepath) == 0:
            raise ValueError("filepath cannot be empty")

        # 构造鉴权 URL
        url = self._build_auth_url()
        print("Connecting to iFlytek ASR...")

        # 每次 recognize 重建 WebSocket 实例，避免复用已关闭连接的脏状态
        self._ws = _WsClient(ms_delay_for_read=5)

        # WebSocket 握手
        try:
            await asyncio.wait_for(self._ws.handshake(url, cert_reqs=0), 10)
        except Exception as e:
            print("Handshake failed:", e)
            return ""

        print("Connected, sending audio frames...")

        # 构造首帧携带的识别参数
        iat_params = {
            "domain":   "slm",       # 固定值：中英识别大模型
            "language": "zh_cn",     # 固定值：中英文
            "accent":   self._accent,
            "eos":      self._eos,
            "result": {
                "encoding": "utf8",
                "compress": "raw",
                "format":   "json",
            },
        }

        # ---- 流式发送所有音频帧 ----
        seq = 0
        try:
            with open(filepath, "rb") as f:
                first = True
                while True:
                    # 每次读取 1280 字节
                    buf = f.read(_FRAME_SIZE)
                    # 读到少于 1280 字节说明已到文件末尾
                    eof = (len(buf) < _FRAME_SIZE)

                    # 判断帧状态：0=首帧，1=中间帧，2=末帧
                    if first and eof:
                        status = 2   # 极短音频：单帧即为首帧也是末帧
                    elif first:
                        status = 0
                    elif eof:
                        status = 2
                    else:
                        status = 1

                    # 音频数据 Base64 编码
                    audio_b64 = binascii.b2a_base64(buf).decode('utf-8').strip() if buf else ""

                    # 构造帧 JSON
                    frame = {
                        "header": {
                            "app_id": self._app_id,
                            "status": status,
                        },
                        "payload": {
                            "audio": {
                                "encoding":    "raw",
                                "sample_rate": self._sample_rate,
                                "channels":    1,
                                "bit_depth":   16,
                                "seq":         seq,
                                "status":      status,
                                "audio":       audio_b64,
                            },
                        },
                    }

                    # 仅首帧附带 parameter.iat 识别参数
                    if first:
                        frame["parameter"] = {"iat": iat_params}

                    # 发送帧
                    await self._ws.send(json.dumps(frame))
                    seq  += 1
                    first = False

                    # 按 API 规范每帧间隔 40ms，模拟实时发送节奏
                    await asyncio.sleep_ms(40)

                    # 末帧发送完毕后退出循环
                    if eof:
                        break

        except Exception as e:
            print("Send error:", e)
            await self._ws.close()
            return ""

        print("All frames sent ({}), receiving results...".format(seq))

        # ---- 接收并拼接识别结果 ----
        result = ""
        try:
            while await self._ws.open():
                msg = await asyncio.wait_for(self._ws.recv(), 10)
                # 服务端主动关闭连接
                if msg is None:
                    print("Connection closed by server.")
                    break

                # 解析服务端返回的 JSON
                try:
                    resp = json.loads(msg)
                except Exception as e:
                    print("JSON parse error:", e)
                    break

                # 检查返回码，非 0 表示业务错误
                code = resp.get("header", {}).get("code", -1)
                if code != 0:
                    print("ASR API error, code:", code,
                          "msg:", resp.get("header", {}).get("message", ""))
                    break

                # 提取识别文本（payload.result.text 为 Base64 编码的 JSON）
                payload = resp.get("payload")
                if payload:
                    text_b64 = payload.get("result", {}).get("text", "")
                    if text_b64:
                        try:
                            # 两层解码：Base64 → JSON → 遍历 ws[].cw[].w 拼接文字
                            text_json = json.loads(
                                binascii.a2b_base64(text_b64).decode('utf-8')
                            )
                            for ws_item in text_json.get("ws", []):
                                for cw in ws_item.get("cw", []):
                                    result += cw.get("w", "")
                        except Exception as e:
                            print("Text decode error:", e)

                # header.status==2 表示服务端识别完毕，退出接收循环
                if resp.get("header", {}).get("status") == 2:
                    print("Recognition complete.")
                    break

        finally:
            # 确保连接被关闭，无论是否发生异常
            await self._ws.close()

        return result

# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ===========================================
