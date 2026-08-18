# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/14
# @Author  : leeqingsui
# @File    : xfyun_asr.py
# @Description : iFlytek online ASR (large model) driver over WebSocket for MicroPython
# @License : MIT

__version__ = "1.0.2"
__author__ = "leeqingsui"
__license__ = "MIT"
__platform__ = "MicroPython v1.23"

# ======================================== 导入相关模块 =========================================

import json
import time
import binascii
import hashlib
import asyncio
from async_websocketclient import AsyncWebsocketClient, URI
from fastb64 import b64encode_str, b64decode

# ======================================== 全局变量 ============================================

# 讯飞大模型多语种语音识别 WebSocket 接入点
_HOST = "iat.cn-huabei-1.xf-yun.com"
_PATH = "/v1"
_WSS_URL = "wss://iat.cn-huabei-1.xf-yun.com/v1"

# 每帧音频字节数（API 规范：16-bit PCM 每次发送 1280 字节 = 40ms@16k）
_FRAME_SIZE = 1280
# 麦克风单次 read() 返回的字节数（20ms@16k），两帧凑一个 _FRAME_SIZE
_MIC_CHUNK = 640

# 本地 VAD 能量阈值下限（16-bit 平均绝对幅度）
_VAD_ENERGY_THRESHOLD = 80
# 连续多少帧静音后主动发 EOS 关流（35 帧 × 20ms = 700ms）。
# 原来是 20 帧（400ms），实测说话中间正常换气就被切断，句子只收到前半截。
_VAD_SILENCE_FRAMES = 35
# 判定"开始说话"所需的连续有声帧数（3 帧 = 120ms，滤掉咔哒声）
_VAD_SPEECH_FRAMES = 3
# 用前 N 帧估计底噪（8 帧 = 320ms）
_VAD_NOISE_FRAMES = 8
# 自适应阈值 = max(下限, 底噪 × 该倍数)
_VAD_NOISE_MULT = 3
# 能量计算的采样步长：每 4 个采样点取 1 个。全扫 1280B 要 5.6ms，
# 步长 4 只要 1.5ms，两者算出的能量值实测差 <0.5%。
_VAD_STRIDE = 4

# 默认 EOS 降为 800ms（原 6000ms），配合本地 VAD 快速关流
_DEFAULT_EOS = 800

# RFC1123 日期格式所需的星期与月份名称表
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

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

    Note:
        走 timesync.utc_struct() 而不是 time.gmtime()。本 port 没有时区
        支持，gmtime() 等于 localtime()，RTC 里存什么就返回什么。项目
        RTC 存东八区时间，直接用会让 Date 头偏 8 小时，服务端判签名过期
        返回 403 Forbidden。timesync 的偏移是从 NTP 现算的，是真 UTC。
    """
    try:
        import timesync

        t = timesync.utc_struct()
    except Exception:
        t = time.gmtime()  # timesync 不可用时退回原行为
    # gmtime() -> (year, month, mday, hour, minute, second, weekday, yearday)
    # weekday: 0=Monday, 6=Sunday
    return "{wd}, {d:02d} {mon} {y} {h:02d}:{m:02d}:{s:02d} GMT".format(
        wd=_WEEKDAYS[t[6]],
        d=t[2],
        mon=_MONTHS[t[1] - 1],
        y=t[0],
        h=t[3],
        m=t[4],
        s=t[5],
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
    key = key + b"\x00" * (block_size - len(key))
    # 构造外层和内层填充
    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)
    # 两次 SHA256：先内层再外层
    inner = hashlib.sha256(i_key_pad + msg).digest()
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
    _safe = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")
    out = []
    for ch in s:
        if ch in _safe:
            # 安全字符直接追加
            out.append(ch)
        else:
            # 非安全字符逐字节转义为 %XX
            for byte in ch.encode("utf-8"):
                out.append("%{:02X}".format(byte))
    return "".join(out)


def _extract_w_fields(json_str):
    """
    从 JSON 字符串中手动提取所有 "w" 字段值，拼接为完整文本。
    完全避开 MicroPython json.loads() 对 false/true/null 关键字的解析 bug。

    Args:
        json_str (str): 从 ASR 响应解码的 JSON 字符串。

    Returns:
        str: 所有 "w" 字段值连接后的完整识别文本。
    """
    result = []
    marker = '"w":"'
    start = 0
    while True:
        pos = json_str.find(marker, start)
        if pos == -1:
            break
        val_start = pos + len(marker)
        # 寻找闭合引号，同时处理 \" 转义
        val_end = val_start
        while val_end < len(json_str):
            if json_str[val_end] == "\\":
                val_end += 2  # 跳过转义序列
            elif json_str[val_end] == '"':
                break
            else:
                val_end += 1
        result.append(json_str[val_start:val_end])
        start = val_end + 1
    # 解码 Unicode 转义序列（如 \u4f60 → 你）
    out = []
    for chunk in result:
        i = 0
        while i < len(chunk):
            if chunk[i : i + 2] == "\\u" and i + 6 <= len(chunk):
                code = int(chunk[i + 2 : i + 6], 16)
                out.append(chr(code))
                i += 6
            else:
                out.append(chunk[i])
                i += 1
    return "".join(out)


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
        if uri.startswith("wss://"):
            protocol, rest, default_port = "wss", uri[6:], 443
        elif uri.startswith("ws://"):
            protocol, rest, default_port = "ws", uri[5:], 80
        else:
            raise ValueError("Scheme not ws or wss")

        # 分离主机部分与路径部分
        slash = rest.find("/")
        if slash == -1:
            hostpart, path = rest, "/"
        else:
            hostpart, path = rest[:slash], rest[slash:]

        # 分离主机名与端口
        colon = hostpart.find(":")
        if colon == -1:
            hostname, port = hostpart, default_port
        else:
            hostname, port = hostpart[:colon], int(hostpart[colon + 1 :])

        return URI(protocol, hostname, port, path)


def _frame_energy(pcm_chunk):
    """
    计算 PCM chunk 的平均绝对幅度，按 _VAD_STRIDE 抽样以控制 CPU 开销。

    Args:
        pcm_chunk (bytes): 16-bit 有符号小端 PCM 原始数据。

    Returns:
        int: 平均绝对幅度（0~32768）；数据不足时返回 0。

    ==========================================

    Mean absolute amplitude of a PCM chunk, subsampled by _VAD_STRIDE to bound
    CPU cost (1.5ms per 1280-byte frame instead of 5.6ms for a full scan).

    Args:
        pcm_chunk (bytes): Raw 16-bit signed little-endian PCM.

    Returns:
        int: Mean absolute amplitude (0-32768); 0 when there is too little data.
    """
    n = len(pcm_chunk)
    if n < 2:
        return 0
    energy = 0
    count = 0
    # 每 _VAD_STRIDE 个采样点取一个，即字节步长 = 2 × stride
    step = 2 * _VAD_STRIDE
    for i in range(0, n - 1, step):
        val = pcm_chunk[i] | (pcm_chunk[i + 1] << 8)
        if val >= 32768:
            val -= 65536  # 有符号转换
        energy += val if val >= 0 else -val
        count += 1
    if count == 0:
        return 0
    return energy // count


def _is_silence(pcm_chunk, threshold=_VAD_ENERGY_THRESHOLD):
    """
    能量法 VAD：平均绝对幅度低于阈值视为静音。

    Args:
        pcm_chunk (bytes): 16-bit 有符号 PCM 原始数据。
        threshold (int): 能量阈值。

    Returns:
        bool: True 表示静音，False 表示有声。

    ==========================================

    Energy-based VAD: returns True when mean absolute amplitude < threshold.
    """
    if len(pcm_chunk) < 2:
        return True
    return _frame_energy(pcm_chunk) < threshold


def _mic_tls_is_verified(cafile, cert_reqs) -> bool:
    return cert_reqs == 2 and cafile is not None and cafile != ""


class XfyunASR:
    """
    讯飞大模型多语种语音识别 ASR 驱动，基于 WebSocket API，将 PCM 音频文件识别为文字。
    支持中文、英文及 46 种语种。流式分帧发送，先发完所有帧再接收结果，
    内存峰值仅为单帧大小（1280 字节），与音频时长无关。

    Attributes:
        _app_id      (str): 讯飞开放平台 APPID。
        _api_key     (str): API Key。
        _api_secret  (str): API Secret（平台提供的原始字符串，勿 Base64 解码）。
        _sample_rate (int): 音频采样率，8000 或 16000。
        _accent      (str): 口音，默认 "mandarin"。
        _eos         (int): 静音停止阈值（毫秒），默认 6000。
        _ln          (str): 指定语种范围，如 "zh|en"，None 为自动识别。
        _ws          (_WsClient): 内部 WebSocket 客户端实例。

    Methods:
        recognize(filepath): 识别指定 PCM 文件，返回识别文字字符串。

    Notes:
        - 调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
        - API Secret 直接以 UTF-8 字节作为 HMAC 密钥，不得对其 Base64 解码。
        - 音频格式要求：16-bit 有符号 PCM，单声道，采样率与初始化参数一致。

    ==========================================

    iFlytek multilingual large model ASR driver over WebSocket API.
    Supports 46 languages (Chinese, English, Japanese, Korean, etc.).
    Sends PCM audio in streaming frames then collects text; peak RAM is one frame (1280 bytes).

    Attributes:
        _app_id      (str): iFlytek APPID.
        _api_key     (str): API Key.
        _api_secret  (str): API Secret (raw string from platform; do NOT Base64-decode).
        _sample_rate (int): Audio sample rate, 8000 or 16000.
        _accent      (str): Accent, default "mandarin".
        _eos         (int): Silence-to-stop threshold in ms, default 800.
        _ln          (str): Language range, e.g. "zh|en", None for auto-detect.
        _ws          (_WsClient): Internal WebSocket client instance.

    Methods:
        recognize(filepath): Recognize a PCM file and return the transcribed text.

    Notes:
        - WiFi must be connected and system time NTP-synced before calling.
        - API Secret must be used as raw UTF-8 bytes for HMAC; do NOT Base64-decode it.
        - Audio format: 16-bit signed PCM, mono, sample rate matching init parameter.
    """

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        sample_rate: int = 16000,
        accent: str = "mandarin",
        eos: int = _DEFAULT_EOS,
        ln: str = None,
        cafile: str = None,
        cert_reqs: int = 0,
    ) -> None:
        """
        初始化 ASR 驱动，保存鉴权参数与识别配置。

        Args:
            app_id      (str): 讯飞开放平台 APPID。
            api_key     (str): API Key。
            api_secret  (str): API Secret（平台提供的原始字符串）。
            sample_rate (int): 音频采样率，8000 或 16000，默认 16000。
            accent      (str): 口音，默认 "mandarin"。
            eos         (int): 静音停止阈值（毫秒），默认 6000。
            ln          (str): 指定语种范围，如 "zh|en"，None 为自动识别（免切模式）。

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
            accent      (str): Accent, default "mandarin".
            eos         (int): Silence-to-stop threshold in ms, default 800.
            ln          (str): Language range, e.g. "zh|en", None for auto-detect.
            cafile      (str): CA certificate file path; use with cert_reqs=2 to verify the WSS peer.
            cert_reqs   (int): TLS certificate verification mode, 0=none, 2=required. Default 0 for compatibility.

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

        # 校验 eos（合理范围 300ms ~ 60000ms）
        if not isinstance(eos, int):
            raise TypeError("eos must be int, got {}".format(type(eos).__name__))
        if eos < 300 or eos > 60000:
            raise ValueError("eos must be between 300 and 60000, got {}".format(eos))

        # 保存鉴权参数
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        # 保存识别配置
        self._sample_rate = sample_rate
        self._accent = accent
        self._eos = eos
        self._ln = ln  # None = auto-detect
        self._cafile = cafile
        self._cert_reqs = cert_reqs
        # 创建 WebSocket 客户端实例（每次 recognize 调用时重建，此处仅占位）
        self._ws = _WsClient(ms_delay_for_read=5)
        # 接收任务的共享状态
        self._result = ""  # 已拼接的识别文本
        self._final = False  # 服务端是否已返回 status==2
        self._err = None  # 接收侧的业务错误信息
        self._connected = False  # connect() 是否已完成握手
        self._conn_cafile = None
        self._conn_cert_reqs = 0

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
        secret_bytes = self._api_secret.encode("utf-8")
        sig_bytes = _hmac_sha256(secret_bytes, sig_origin.encode("utf-8"))
        # Base64 编码签名摘要
        sig_b64 = binascii.b2a_base64(sig_bytes).decode("utf-8").strip()

        # 拼接 authorization 原文并 Base64 编码
        auth_origin = ('api_key="{}", algorithm="hmac-sha256", ' 'headers="host date request-line", signature="{}"').format(self._api_key, sig_b64)
        auth_b64 = binascii.b2a_base64(auth_origin.encode("utf-8")).decode("utf-8").strip()

        # 拼接最终 WSS URL，三个参数均需 URL 百分号编码
        return "{}?authorization={}&date={}&host={}".format(
            _WSS_URL,
            _url_encode(auth_b64),
            _url_encode(date),
            _url_encode(_HOST),
        )

    def _iat_params(self) -> dict:
        """
        构造首帧携带的 parameter.iat 识别参数。

        Returns:
            dict: 识别参数字典。

        ==========================================

        Build the parameter.iat recognition options carried by the first frame.

        Returns:
            dict: Recognition parameter dictionary.
        """
        params = {
            "domain": "slm",  # 固定值：大模型多语种语音识别
            "language": "mul_cn",  # 固定值：多语种
            "accent": self._accent,
            "eos": self._eos,
            "result": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "json",
            },
        }
        # 如果指定了语种范围，加入 ln 参数（如 "zh|en|ja"）
        if self._ln is not None:
            params["ln"] = self._ln
        return params

    def _first_frame(self, pcm: bytes, status: int) -> str:
        """
        构造首帧 JSON（携带识别参数与完整音频描述字段）。

        Args:
            pcm    (bytes): 该帧的原始 PCM 数据，可为空。
            status (int):   帧状态，0=首帧，2=首帧即末帧。

        Returns:
            str: 可直接发送的 JSON 字符串。

        ==========================================

        Build the first frame JSON, carrying recognition params and the full
        audio descriptor fields.

        Args:
            pcm    (bytes): Raw PCM for this frame; may be empty.
            status (int):   Frame status, 0 = first, 2 = first and last.

        Returns:
            str: JSON string ready to send.
        """
        if status not in (0, 2):
            raise ValueError("status must be 0 or 2")
        return json.dumps(
            {
                "header": {
                    "app_id": self._app_id,
                    "status": status,
                },
                "parameter": {"iat": self._iat_params()},
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": self._sample_rate,
                        "channels": 1,
                        "bit_depth": 16,
                        "seq": 1,
                        "status": status,
                        "audio": b64encode_str(pcm) if pcm else "",
                    },
                },
            }
        )

    def _next_frame(self, pcm: bytes, status: int) -> str:
        """
        构造中间帧或末帧 JSON，用字符串拼接代替 json.dumps 以省 CPU。

        严格按文档：中间帧不含 channels/bit_depth/seq。
        实测 json.dumps 约 4.0ms/帧，直接拼接约 2.8ms/帧。

        Args:
            pcm    (bytes): 该帧的原始 PCM 数据，可为空（末帧允许空载荷）。
            status (int):   帧状态，1=中间帧，2=末帧。

        Returns:
            str: 可直接发送的 JSON 字符串。

        ==========================================

        Build a middle/last frame JSON via string concatenation instead of
        json.dumps to save CPU (2.8ms vs 4.0ms per frame, measured).

        Per the API docs, middle frames omit channels/bit_depth/seq.

        Args:
            pcm    (bytes): Raw PCM for this frame; may be empty on the last frame.
            status (int):   Frame status, 1 = middle, 2 = last.

        Returns:
            str: JSON string ready to send.
        """
        if status not in (1, 2):
            raise ValueError("status must be 1 or 2")
        return (
            '{"header":{"app_id":"'
            + self._app_id
            + '","status":'
            + str(status)
            + '},"payload":{"audio":{"encoding":"raw","sample_rate":'
            + str(self._sample_rate)
            + ',"status":'
            + str(status)
            + ',"audio":"'
            + (b64encode_str(pcm) if pcm else "")
            + '"}}}'
        )

    async def connect(self, timeout: int = 10, cafile: str = None, cert_reqs: int = None) -> bool:
        """
        提前完成 WebSocket 握手，把 TLS 建连开销挪出识别时段。

        典型用法：在播放提示音之前调用本方法，用户听提示音的时间正好
        覆盖 TLS 握手（实测 1~2s），录音一开始就能立即发帧。

        Args:
            timeout (int): 握手超时秒数，默认 10。

        Returns:
            bool: 握手成功返回 True，失败返回 False。

        ==========================================

        Perform the WebSocket handshake ahead of time so TLS setup happens
        outside the recognition window.

        Typical use: call this before playing a prompt tone; the prompt covers
        the 1-2s TLS handshake, so the first audio frame can go out immediately
        once recording starts.

        Args:
            timeout   (int): Handshake timeout in seconds, default 10.
            cafile    (str): CA certificate path for this connection; None uses the instance setting.
            cert_reqs (int): TLS verification mode for this connection; None uses the instance setting.

        Returns:
            bool: True on success, False on failure.
        """
        # 复位上一轮的共享状态
        self._result = ""
        self._final = False
        self._err = None
        self._connected = False
        self._conn_cafile = None
        self._conn_cert_reqs = 0

        url = self._build_auth_url()
        self._ws = _WsClient(ms_delay_for_read=5)
        if cert_reqs is None:
            cert_reqs = self._cert_reqs
        if cafile is None:
            cafile = self._cafile
        try:
            await asyncio.wait_for(
                self._ws.handshake(url, cafile=cafile, cert_reqs=cert_reqs),
                timeout,
            )
        except Exception as e:
            print("[ASR] Handshake failed:", e)
            try:
                await self._ws.close()
            except Exception:
                pass
            return False
        self._connected = True
        self._conn_cafile = cafile
        self._conn_cert_reqs = cert_reqs
        return True

    def _handle_message(self, msg) -> bool:
        """
        解析一条服务端消息，累加识别文本。

        Args:
            msg (str): 服务端返回的 JSON 文本。

        Returns:
            bool: True 表示识别已结束（status==2 或出错），应停止接收。

        ==========================================

        Parse one server message and accumulate recognized text.

        Args:
            msg (str): JSON text returned by the server.

        Returns:
            bool: True when recognition is finished (status==2 or error).
        """
        if msg is None:
            raise ValueError("msg cannot be None")
        # MicroPython 的 json.loads 对 true/false/null 处理有缺陷，先替换为数字
        safe = msg.replace(":true", ":1").replace(":false", ":0").replace(":null", ":0")
        try:
            resp = json.loads(safe)
        except Exception:
            print("[ASR] json parse error, raw:", msg[:120])
            return False

        header = resp.get("header", {})
        code = header.get("code", -1)
        if code != 0:
            self._err = "code=%s msg=%s" % (code, header.get("message", ""))
            print("[ASR] API error,", self._err)
            return True

        # 提取识别文本（payload.result.text 是 Base64 编码的 JSON）
        payload = resp.get("payload")
        if payload:
            text_b64 = payload.get("result", {}).get("text", "")
            if text_b64:
                try:
                    decoded = b64decode(text_b64).decode("utf-8")
                    self._result += _extract_w_fields(decoded)
                except Exception as e:
                    print("[ASR] decode error:", e, "b64[:40]:", text_b64[:40])

        if header.get("status") == 2:
            self._final = True
            return True
        return False

    async def _recv_loop(self):
        """
        后台接收任务：持续收包直到服务端返回 status==2、报错或连接关闭。

        本任务从不在读帧中途被取消——这是关键。用 asyncio.wait_for 包住
        recv() 会在 WebSocket 帧读到一半时抛出取消异常，帧解析器就此失步，
        之后每次读到的都是错位的垃圾字节，只能干等超时。

        ==========================================

        Background receive task: keeps reading until the server returns
        status==2, reports an error, or closes the connection.

        This task is never cancelled mid-frame, which is the whole point.
        Wrapping recv() in asyncio.wait_for aborts halfway through a WebSocket
        frame, desyncing the frame parser so every later read returns misaligned
        garbage and the caller can only wait for a timeout.
        """
        try:
            while not self._final and self._err is None:
                msg = await self._ws.recv()
                if msg is None:
                    # 服务端关闭连接
                    break
                if self._handle_message(msg):
                    break
        except Exception as e:
            if self._err is None:
                self._err = "recv: %s" % e

    async def _await_final(self, recv_task, timeout_ms: int) -> None:
        """
        等待接收任务结束，超时后取消它（此时已无失步风险）。

        Args:
            recv_task: _recv_loop 创建的任务对象。
            timeout_ms (int): 最长等待毫秒数。

        ==========================================

        Wait for the receive task to finish, cancelling it on timeout (at which
        point a desync no longer matters because the connection is being closed).

        Args:
            recv_task: Task object created from _recv_loop.
            timeout_ms (int): Maximum wait in milliseconds.
        """
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while not recv_task.done() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            await asyncio.sleep_ms(10)
        if not recv_task.done():
            print("[ASR] timeout waiting for final result")
            recv_task.cancel()
            try:
                await recv_task
            except Exception:
                pass

    async def _send_file(self, filepath: str, pace_ms: int) -> int:
        """
        按帧读取 PCM 文件并发送，可选墙钟节流。

        Args:
            filepath (str): PCM 文件路径。
            pace_ms  (int): 每帧目标间隔毫秒；<=0 表示不节流，尽快发完。

        Returns:
            int: 实际发送的帧数。

        ==========================================

        Read a PCM file frame by frame and send it, optionally wall-clock paced.

        Args:
            filepath (str): PCM file path.
            pace_ms  (int): Target per-frame interval in ms; <=0 sends as fast as possible.

        Returns:
            int: Number of frames actually sent.
        """
        sent = 0
        first = True
        next_send = time.ticks_ms()

        with open(filepath, "rb") as f:
            while True:
                buf = f.read(_FRAME_SIZE)
                eof = len(buf) < _FRAME_SIZE

                if first:
                    status = 2 if eof else 0
                    await self._ws.send(self._first_frame(buf, status))
                else:
                    status = 2 if eof else 1
                    await self._ws.send(self._next_frame(buf, status))
                sent += 1
                first = False

                if eof:
                    break

                # ── 墙钟节流：用累计时刻推进，避免 sleep 误差累积 ──
                if pace_ms > 0:
                    next_send = time.ticks_add(next_send, pace_ms)
                    wait = time.ticks_diff(next_send, time.ticks_ms())
                    if wait > 0:
                        await asyncio.sleep_ms(wait)
                    else:
                        # 已落后于墙钟，让出一次 CPU 后继续追赶
                        await asyncio.sleep_ms(0)
                else:
                    await asyncio.sleep_ms(0)

        return sent

    async def recognize(self, filepath: str, pace_ms: int = 0, timeout_ms: int = 15000) -> str:
        """
        识别 PCM 音频文件，返回识别文字。发送与接收并发进行。

        对已录好的文件不需要按 40ms/帧节流——服务端按音频内容而非到达时间
        计时长，全速发送反而更快。默认 pace_ms=0 即全速。

        Args:
            filepath   (str): PCM 音频文件路径（16-bit 有符号，单声道，采样率与初始化一致）。
            pace_ms    (int): 每帧发送间隔毫秒，0 表示全速发送（默认）。
            timeout_ms (int): 发完后等待最终结果的最长毫秒数，默认 15000。

        Returns:
            str: 识别结果文字；失败或无结果时返回 ""。

        Raises:
            ValueError: filepath 为 None 或空字符串。
            TypeError:  filepath 不是字符串类型。

        Notes:
            调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
            若已调用过 connect()，本方法复用该连接，不再重新握手。

        ==========================================

        Recognize a PCM audio file and return the transcribed text. Sending and
        receiving run concurrently.

        Pre-recorded files do not need 40ms-per-frame pacing: the server measures
        duration from the audio itself, not from arrival times, so sending at full
        speed is simply faster. pace_ms defaults to 0 (full speed).

        Args:
            filepath   (str): PCM file path (16-bit signed, mono, matching init sample_rate).
            pace_ms    (int): Per-frame send interval in ms; 0 means full speed (default).
            timeout_ms (int): Max wait for the final result after sending, default 15000.

        Returns:
            str: Recognized text; "" on failure or empty result.

        Raises:
            ValueError: filepath is None or empty.
            TypeError:  filepath is not a string.

        Notes:
            WiFi must be connected and system time NTP-synced before calling.
            Reuses an existing connect() session instead of re-handshaking.
        """
        # 校验 filepath
        if filepath is None:
            raise ValueError("filepath cannot be None")
        if not isinstance(filepath, str):
            raise TypeError("filepath must be str, got {}".format(type(filepath).__name__))
        if len(filepath) == 0:
            raise ValueError("filepath cannot be empty")

        # 未预先握手则现场建连
        if not self._connected:
            if not await self.connect():
                return ""

        t0 = time.ticks_ms()
        recv_task = asyncio.create_task(self._recv_loop())
        try:
            sent = await self._send_file(filepath, pace_ms)
            print("[ASR] sent %d frames in %d ms" % (sent, time.ticks_diff(time.ticks_ms(), t0)))
            await self._await_final(recv_task, timeout_ms)
        except Exception as e:
            print("[ASR] send error:", e)
            recv_task.cancel()
        finally:
            self._connected = False
            self._conn_cafile = None
            self._conn_cert_reqs = 0
            await self._ws.close()

        print("[ASR] total %d ms" % time.ticks_diff(time.ticks_ms(), t0))
        return self._result

    async def recognize_streaming(self, filepath: str) -> str:
        """
        识别 PCM 文件（兼容旧接口），等价于 recognize(filepath)。

        Args:
            filepath (str): PCM 音频文件路径。

        Returns:
            str: 识别结果文字；失败或无结果时返回 ""。

        ==========================================

        Recognize a PCM file; kept for backwards compatibility. Equivalent to
        recognize(filepath).

        Args:
            filepath (str): PCM audio file path.

        Returns:
            str: Recognized text; "" on failure or empty result.
        """
        return await self.recognize(filepath)

    async def recognize_mic(
        self,
        codec,
        max_ms: int = 15000,
        start_timeout_ms: int = 6000,
        timeout_ms: int = 8000,
        on_state=None,
    ) -> str:
        """
        边录边识别：直接从麦克风流式送帧，用户一停口就出结果。

        这是延迟最低的用法。传统"录满 N 秒 → 存文件 → 读文件发送 → 等结果"
        是串行的，总耗时 = N + 发送 + 服务端；本方法把三者重叠，总耗时 ≈
        用户实际说话时长 + 约 0.3s 收尾。

        流程：
          1. 先攒 _VAD_NOISE_FRAMES 帧估底噪，自适应确定能量阈值；
          2. 检测到连续有声帧才开始发送，并补发 200ms 前置缓冲（避免吃掉首字）；
          3. 说话期间实时送帧（麦克风本身就是 20ms 一块，天然是实时节奏）；
          4. 连续 _VAD_SILENCE_FRAMES 帧静音 → 立即发 status=2 关流。

        Args:
            codec:                  machine.AudioCodec 实例，需已 start()。
            max_ms           (int): 最长录音毫秒数，默认 15000。
            start_timeout_ms (int): 等待用户开口的最长毫秒数，默认 6000；超时返回 ""。
            timeout_ms       (int): 关流后等待最终结果的最长毫秒数，默认 8000。
            on_state:               可选回调 on_state(state)，state 取
                                    "listening" / "speaking" / "done"，用于刷新显示。

        Returns:
            str: 识别结果文字；用户未开口或失败时返回 ""。

        Notes:
            若已调用过 connect()，复用该连接；否则现场握手（会多花 1~2s）。

        ==========================================

        Recognize straight from the microphone: frames stream out while the user
        is still talking, so the result lands right after they stop.

        This is the lowest-latency entry point. The classic "record N seconds ->
        write file -> read and send -> wait" pipeline is serial, costing
        N + send + server. This overlaps all three, costing roughly the user's
        actual speaking time plus ~0.3s of tail.

        Flow:
          1. Collect _VAD_NOISE_FRAMES frames to estimate the noise floor and
             derive an adaptive energy threshold.
          2. Start sending only after consecutive voiced frames, replaying a
             200ms pre-roll so the first syllable is not clipped.
          3. Stream frames live while the user talks (the mic emits 20ms chunks,
             which is already real-time pacing by construction).
          4. After _VAD_SILENCE_FRAMES silent frames, send status=2 immediately.

        Args:
            codec:                  machine.AudioCodec instance, already start()ed.
            max_ms           (int): Max recording time in ms, default 15000.
            start_timeout_ms (int): Max wait for speech onset in ms, default 6000.
            timeout_ms       (int): Max wait for the final result in ms, default 8000.
            on_state:               Optional on_state(state) callback with
                                    "listening" / "speaking" / "done".

        Returns:
            str: Recognized text; "" if the user never spoke or on failure.

        Notes:
            Reuses an existing connect() session; otherwise handshakes inline
            (costing an extra 1-2s).
        """
        if codec is None:
            raise ValueError("codec cannot be None")

        if self._connected:
            if not _mic_tls_is_verified(self._conn_cafile, self._conn_cert_reqs):
                raise ValueError("recognize_mic requires TLS peer verification; " "configure cafile and cert_reqs=2")
        elif not _mic_tls_is_verified(self._cafile, self._cert_reqs):
            raise ValueError("recognize_mic requires TLS peer verification; " "configure cafile and cert_reqs=2")

        # 未预先握手则现场建连
        if not self._connected:
            if not await self.connect():
                return ""
            if not _mic_tls_is_verified(self._conn_cafile, self._conn_cert_reqs):
                raise ValueError("recognize_mic requires TLS peer verification; " "configure cafile and cert_reqs=2")

        # 丢掉麦克风里的积压帧。调用方通常刚放完 TTS，那段播音会经
        # AEC 残留漏进 mic 缓冲；不丢的话前 8 帧底噪估计就被它污染，
        # 阈值被抬到真人说话都够不着，表现是一直等到 start_timeout
        # 然后报 no speech detected。
        try:
            codec.clear()
        except Exception:
            pass

        if on_state:
            on_state("listening")

        t_start = time.ticks_ms()
        recv_task = asyncio.create_task(self._recv_loop())

        # ── 状态机变量 ──
        pending = []  # 累积到 _FRAME_SIZE 的待发缓冲
        pending_n = 0
        preroll = []  # 开口前的前置缓冲（滚动保留）
        preroll_n = 0
        preroll_max = self._sample_rate * 2 * 200 // 1000  # 200ms
        noise_sum = 0
        noise_cnt = 0
        threshold = _VAD_ENERGY_THRESHOLD
        voiced = 0  # 连续有声帧计数
        silence = 0  # 连续静音帧计数
        speaking = False  # 是否已确认开口
        first = True  # 下一帧是否为首帧
        sent = 0
        t_speech = 0  # 开口时刻

        try:
            while True:
                now = time.ticks_ms()
                # 总时长上限
                if speaking and time.ticks_diff(now, t_speech) > max_ms:
                    print("[ASR] max_ms reached")
                    break
                # 一直没开口
                if not speaking and time.ticks_diff(now, t_start) > start_timeout_ms:
                    print("[ASR] no speech detected")
                    break

                if not codec.any():
                    await asyncio.sleep_ms(5)
                    continue

                chunk = codec.read()
                if not chunk:
                    await asyncio.sleep_ms(5)
                    continue

                energy = _frame_energy(chunk)

                if not speaking:
                    # ── 阶段一：估底噪 + 等开口 ──
                    if noise_cnt < _VAD_NOISE_FRAMES:
                        noise_sum += energy
                        noise_cnt += 1
                        if noise_cnt == _VAD_NOISE_FRAMES:
                            floor = noise_sum // _VAD_NOISE_FRAMES
                            threshold = max(_VAD_ENERGY_THRESHOLD, floor * _VAD_NOISE_MULT)
                            print("[ASR] noise floor=%d threshold=%d" % (floor, threshold))
                    else:
                        if energy >= threshold:
                            voiced += 1
                        else:
                            voiced = 0
                        if voiced >= _VAD_SPEECH_FRAMES:
                            speaking = True
                            t_speech = time.ticks_ms()
                            print("[ASR] speech onset (energy=%d)" % energy)
                            if on_state:
                                on_state("speaking")
                            # 前置缓冲入队，避免首字被吃
                            for p in preroll:
                                pending.append(p)
                                pending_n += len(p)
                            preroll = []
                            preroll_n = 0

                    # 滚动保留最近 200ms 作为前置缓冲
                    if not speaking:
                        preroll.append(chunk)
                        preroll_n += len(chunk)
                        while preroll_n > preroll_max and preroll:
                            preroll_n -= len(preroll.pop(0))
                        continue

                # ── 阶段二：说话中，实时送帧 ──
                pending.append(chunk)
                pending_n += len(chunk)

                if energy < threshold:
                    silence += 1
                else:
                    silence = 0

                # 攒够一帧就发
                while pending_n >= _FRAME_SIZE:
                    blob = b"".join(pending)
                    frame, rest = blob[:_FRAME_SIZE], blob[_FRAME_SIZE:]
                    pending = [rest] if rest else []
                    pending_n = len(rest)
                    if first:
                        await self._ws.send(self._first_frame(frame, 0))
                        first = False
                    else:
                        await self._ws.send(self._next_frame(frame, 1))
                    sent += 1

                # 尾部静音够长 → 收口
                if silence >= _VAD_SILENCE_FRAMES:
                    print("[ASR] silence detected, closing stream")
                    break

                if self._final or self._err is not None:
                    break

            # ── 发末帧（带上残留数据）──
            tail = b"".join(pending) if pending else b""
            if first:
                # 从未发过帧：用户没说话
                if not speaking:
                    recv_task.cancel()
                    if on_state:
                        on_state("done")
                    return ""
                await self._ws.send(self._first_frame(tail, 2))
            else:
                await self._ws.send(self._next_frame(tail, 2))
            sent += 1

            t_eos = time.ticks_ms()
            print("[ASR] EOS after %d frames, speech %d ms" % (sent, time.ticks_diff(t_eos, t_speech) if t_speech else 0))
            await self._await_final(recv_task, timeout_ms)
            print("[ASR] EOS -> result: %d ms" % time.ticks_diff(time.ticks_ms(), t_eos))

        except Exception as e:
            print("[ASR] mic stream error:", e)
            recv_task.cancel()
        finally:
            self._connected = False
            self._conn_cafile = None
            self._conn_cert_reqs = 0
            await self._ws.close()
            if on_state:
                on_state("done")

        return self._result


# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ===========================================
