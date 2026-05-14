# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/12
# @Author  : leeqingsui
# @File    : xfyun_tts.py
# @Description : iFlytek online TTS driver over WebSocket for MicroPython
# @License : MIT

# ======================================== 导入相关模块 =========================================

import json
import time
import binascii
import hashlib
import struct
import asyncio
from async_websocketclient import AsyncWebsocketClient, URI

# ======================================== 全局变量 ============================================

__version__ = "1.1.0"
__author__ = "leeqingsui"
__license__ = "MIT"
__platform__ = "MicroPython v1.23"

_HOST    = "tts-api.xfyun.cn"
_PATH    = "/v2/tts"
_WSS_URL = "wss://tts-api.xfyun.cn/v2/tts"

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
    t = time.gmtime()
    # gmtime() -> (year, month, mday, hour, minute, second, weekday, yearday)
    # weekday: 0 = Monday, 6 = Sunday
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
    if len(key) > block_size:
        key = hashlib.sha256(key).digest()
    key = key + b'\x00' * (block_size - len(key))
    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)
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
    _safe = frozenset(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~'
    )
    out = []
    for ch in s:
        if ch in _safe:
            out.append(ch)
        else:
            for byte in ch.encode('utf-8'):
                out.append('%{:02X}'.format(byte))
    return ''.join(out)


def _wav_header(sample_rate, channels, bits, data_size):
    """
    构造 44 字节的标准 WAV 文件头（PCM 格式，RIFF/WAVE/fmt/data）。

    Args:
        sample_rate (int): 采样率，如 8000。
        channels    (int): 声道数，1=单声道，2=立体声。
        bits        (int): 采样位深，如 16。
        data_size   (int): PCM 数据总字节数；写入占位头时传 0。

    Returns:
        bytes: 44 字节 WAV 文件头。

    ==========================================

    Build a 44-byte standard WAV file header (PCM, RIFF/WAVE/fmt/data).

    Args:
        sample_rate (int): Sample rate, e.g. 8000.
        channels    (int): Number of channels; 1=mono, 2=stereo.
        bits        (int): Bits per sample, e.g. 16.
        data_size   (int): Total PCM data bytes; pass 0 for a placeholder header.

    Returns:
        bytes: 44-byte WAV file header.
    """
    byte_rate   = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    return struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', data_size + 36,
        b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate,
        byte_rate, block_align, bits,
        b'data', data_size,
    )


# ======================================== 自定义类 ============================================


class _WsClient(AsyncWebsocketClient):
    """
    AsyncWebsocketClient 子类，用非递归字符串解析替换原正则解析。

    MicroPython 的 ure 正则引擎为递归实现，对超过 ~30 字符的路径段
    （如含鉴权参数的长 URL）会触发 "maximum recursion depth exceeded"。
    本子类仅覆盖 urlparse()，其余逻辑完全继承自父类。

    ==========================================

    Subclass of AsyncWebsocketClient that replaces regex-based URL parsing
    with iterative string operations.

    MicroPython's ure regex engine is recursive; paths longer than ~30 chars
    (e.g. auth query strings) exceed the stack limit and raise
    "maximum recursion depth exceeded". Only urlparse() is overridden here.
    """

    def urlparse(self, uri):
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
        if uri.startswith('wss://'):
            protocol     = 'wss'
            rest         = uri[6:]
            default_port = 443
        elif uri.startswith('ws://'):
            protocol     = 'ws'
            rest         = uri[5:]
            default_port = 80
        else:
            raise ValueError('Scheme not ws or wss')

        slash = rest.find('/')
        if slash == -1:
            hostpart = rest
            path     = '/'
        else:
            hostpart = rest[:slash]
            path     = rest[slash:]

        colon = hostpart.find(':')
        if colon == -1:
            hostname = hostpart
            port     = default_port
        else:
            hostname = hostpart[:colon]
            port     = int(hostpart[colon + 1:])

        return URI(protocol, hostname, port, path)


class XfyunTTS:
    """
    讯飞在线语音合成（TTS）驱动，基于 WebSocket API，将文字合成为 PCM 音频。
    支持动态配置发音人、语速、音量、音高等参数。

    Attributes:
        _app_id     (str): 讯飞开放平台 APPID。
        _api_key    (str): API Key。
        _api_secret (str): API Secret（Base64 编码原文，由平台提供）。
        _vcn        (str): 发音人。
        _aue        (str): 音频编码格式。
        _auf        (str): 音频采样规格。
        _speed      (int): 语速 [0-100]。
        _volume     (int): 音量 [0-100]。
        _pitch      (int): 音高 [0-100]。
        _bgs        (int): 背景音 0/1。
        _tte        (str): 文本编码格式。
        _reg        (str): 英文发音方式 [0-2]。
        _rdn        (str): 数字发音方式 [0-3]。
        _sfl        (int): 流式返回 mp3（配合 aue=lame）。
        _ws         (AsyncWebsocketClient): 内部 WebSocket 客户端实例。

    ==========================================

    iFlytek online TTS driver over WebSocket API, converting text to PCM audio.
    Supports dynamic configuration of voice, speed, volume, pitch, and more.

    Attributes:
        _app_id     (str): iFlytek Open Platform APPID.
        _api_key    (str): API Key.
        _api_secret (str): API Secret (Base64-encoded string as provided by the platform).
        _vcn        (str): Voice name.
        _aue        (str): Audio encoding.
        _auf        (str): Audio format.
        _speed      (int): Speech speed [0-100].
        _volume     (int): Volume [0-100].
        _pitch      (int): Pitch [0-100].
        _bgs        (int): Background sound 0/1.
        _tte        (str): Text encoding format.
        _reg        (str): English pronunciation mode [0-2].
        _rdn        (str): Digit pronunciation mode [0-3].
        _sfl        (int): Stream mp3 (with aue=lame).
        _ws         (AsyncWebsocketClient): Internal WebSocket client instance.
    """

    # 发音人常量 / Voice constants
    VOICE_XIAOYAN = "x4_xiaoyan"      # 讯飞小燕
    VOICE_YEZI = "x4_yezi"            # 讯飞小露
    VOICE_JIUXU = "aisjiuxu"          # 讯飞许久
    VOICE_JINGER = "aisjinger"        # 讯飞小婧
    VOICE_BABYXU = "aisbabyxu"        # 讯飞许小宝

    # 音频编码常量 / Audio encoding constants
    AUE_RAW = "raw"                   # 原始 PCM
    AUE_LAME = "lame"                 # MP3
    AUE_OPUS = "opus"                 # Opus 8k
    AUE_OPUS_WB = "opus-wb"           # Opus 16k
    AUE_SPEEX = "speex;7"             # 讯飞定制 Speex 8k
    AUE_SPEEX_WB = "speex-wb;7"       # 讯飞定制 Speex 16k

    # 采样率常量 / Sample rate constants
    AUF_8K = "audio/L16;rate=8000"
    AUF_16K = "audio/L16;rate=16000"

    # 默认值常量 / Default value constants
    DEFAULT_SPEED = 50
    DEFAULT_VOLUME = 50
    DEFAULT_PITCH = 50

    def __init__(self, app_id, api_key, api_secret,
                 vcn="x4_xiaoyan", aue="raw", auf="audio/L16;rate=8000",
                 speed=50, volume=50, pitch=50, **kwargs):
        """
        初始化 TTS 驱动，保存鉴权参数与音频配置。

        Args:
            app_id     (str): 讯飞开放平台 APPID。
            api_key    (str): API Key。
            api_secret (str): API Secret（Base64 编码原文）。
            vcn        (str): 发音人，默认 "x4_xiaoyan"。
            aue        (str): 音频编码，默认 "raw"（PCM）。
            auf        (str): 音频格式，默认 "audio/L16;rate=8000"。
            speed      (int): 语速 [0-100]，默认 50。
            volume     (int): 音量 [0-100]，默认 50。
            pitch      (int): 音高 [0-100]，默认 50。
            **kwargs: 高级参数
                bgs (int): 背景音 0/1，默认 0。
                tte (str): 文本编码，默认 "UTF8"。
                reg (str): 英文发音方式 [0-2]，默认 "0"。
                rdn (str): 数字发音方式 [0-3]，默认 "0"。
                sfl (int): 流式返回 mp3（配合 aue=lame），默认 None。

        ==========================================

        Initialize the TTS driver with authentication and audio parameters.

        Args:
            app_id     (str): iFlytek APPID.
            api_key    (str): API Key.
            api_secret (str): API Secret (Base64-encoded string).
            vcn        (str): Voice name, default "x4_xiaoyan".
            aue        (str): Audio encoding, default "raw" (PCM).
            auf        (str): Audio format, default "audio/L16;rate=8000".
            speed      (int): Speech speed [0-100], default 50.
            volume     (int): Volume [0-100], default 50.
            pitch      (int): Pitch [0-100], default 50.
            **kwargs: Advanced parameters
                bgs (int): Background sound 0/1, default 0.
                tte (str): Text encoding, default "UTF8".
                reg (str): English pronunciation [0-2], default "0".
                rdn (str): Digit pronunciation [0-3], default "0".
                sfl (int): Stream mp3 (with aue=lame), default None.
        """
        # 必需参数 / Required parameters
        self._app_id     = app_id
        self._api_key    = api_key
        self._api_secret = api_secret

        # 常用参数 / Common parameters
        self._vcn    = vcn
        self._aue    = aue
        self._auf    = auf
        self._speed  = speed
        self._volume = volume
        self._pitch  = pitch

        # 高级参数 / Advanced parameters
        self._bgs = kwargs.get('bgs', 0)
        self._tte = kwargs.get('tte', "UTF8")
        self._reg = kwargs.get('reg', "0")
        self._rdn = kwargs.get('rdn', "0")
        self._sfl = kwargs.get('sfl', None)

        # WebSocket 客户端 / WebSocket client
        self._ws = _WsClient(ms_delay_for_read=5)

    # ========== 动态设置方法 / Dynamic configuration methods ==========

    def set_voice(self, vcn):
        """
        设置发音人，下次合成时生效。

        Args:
            vcn (str): 发音人参数值，如 "x4_xiaoyan"。

        Returns:
            self: 支持链式调用。

        ==========================================

        Set voice name, takes effect on next synthesis.

        Args:
            vcn (str): Voice parameter, e.g. "x4_xiaoyan".

        Returns:
            self: Supports method chaining.
        """
        self._vcn = vcn
        return self

    def set_speed(self, speed):
        """
        设置语速 [0-100]，下次合成时生效。

        Args:
            speed (int): 语速值，范围 [0-100]。

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数超出范围时抛出。

        ==========================================

        Set speech speed [0-100], takes effect on next synthesis.

        Args:
            speed (int): Speed value in range [0-100].

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when parameter is out of range.
        """
        if not 0 <= speed <= 100:
            raise ValueError("speed must be in [0, 100]")
        self._speed = speed
        return self

    def set_volume(self, volume):
        """
        设置音量 [0-100]，下次合成时生效。

        Args:
            volume (int): 音量值，范围 [0-100]。

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数超出范围时抛出。

        ==========================================

        Set volume [0-100], takes effect on next synthesis.

        Args:
            volume (int): Volume value in range [0-100].

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when parameter is out of range.
        """
        if not 0 <= volume <= 100:
            raise ValueError("volume must be in [0, 100]")
        self._volume = volume
        return self

    def set_pitch(self, pitch):
        """
        设置音高 [0-100]，下次合成时生效。

        Args:
            pitch (int): 音高值，范围 [0-100]。

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数超出范围时抛出。

        ==========================================

        Set pitch [0-100], takes effect on next synthesis.

        Args:
            pitch (int): Pitch value in range [0-100].

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when parameter is out of range.
        """
        if not 0 <= pitch <= 100:
            raise ValueError("pitch must be in [0, 100]")
        self._pitch = pitch
        return self

    def set_background_sound(self, enabled):
        """
        设置背景音，下次合成时生效。

        Args:
            enabled (bool): True 开启背景音，False 关闭背景音。

        Returns:
            self: 支持链式调用。

        ==========================================

        Set background sound, takes effect on next synthesis.

        Args:
            enabled (bool): True to enable, False to disable.

        Returns:
            self: Supports method chaining.
        """
        self._bgs = 1 if enabled else 0
        return self

    def set_audio_encoding(self, aue, sfl=None):
        """
        设置音频编码格式，下次合成时生效。

        Args:
            aue (str): 音频编码，如 "raw"、"lame"、"opus" 等。
            sfl (int, optional): 流式返回 mp3，仅在 aue="lame" 时有效。

        Returns:
            self: 支持链式调用。

        ==========================================

        Set audio encoding format, takes effect on next synthesis.

        Args:
            aue (str): Audio encoding, e.g. "raw", "lame", "opus".
            sfl (int, optional): Stream mp3, only valid when aue="lame".

        Returns:
            self: Supports method chaining.
        """
        self._aue = aue
        self._sfl = sfl if aue == "lame" else None
        return self

    def set_sample_rate(self, rate):
        """
        设置采样率，下次合成时生效。

        Args:
            rate (int): 采样率，支持 8000 或 16000。

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数不是 8000 或 16000 时抛出。

        ==========================================

        Set sample rate, takes effect on next synthesis.

        Args:
            rate (int): Sample rate, 8000 or 16000.

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when rate is not 8000 or 16000.
        """
        if rate == 8000:
            self._auf = self.AUF_8K
        elif rate == 16000:
            self._auf = self.AUF_16K
        else:
            raise ValueError("rate must be 8000 or 16000")
        return self

    def set_text_encoding(self, tte):
        """
        设置文本编码格式，下次合成时生效。

        Args:
            tte (str): 文本编码，如 "UTF8"、"GBK"、"GB2312" 等。

        Returns:
            self: 支持链式调用。

        ==========================================

        Set text encoding format, takes effect on next synthesis.

        Args:
            tte (str): Text encoding, e.g. "UTF8", "GBK", "GB2312".

        Returns:
            self: Supports method chaining.
        """
        self._tte = tte
        return self

    def set_english_pronunciation(self, reg):
        """
        设置英文发音方式，下次合成时生效。

        Args:
            reg (str): 英文发音方式
                "0": 自动判断，不确定按单词发音（默认）
                "1": 所有英文按字母发音
                "2": 自动判断，不确定按字母发音

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数不是 "0"、"1" 或 "2" 时抛出。

        ==========================================

        Set English pronunciation mode, takes effect on next synthesis.

        Args:
            reg (str): English pronunciation mode
                "0": Auto, default to word pronunciation
                "1": All English as letters
                "2": Auto, default to letter pronunciation

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when reg is not "0", "1", or "2".
        """
        if reg not in ("0", "1", "2"):
            raise ValueError("reg must be '0', '1', or '2'")
        self._reg = reg
        return self

    def set_digit_pronunciation(self, rdn):
        """
        设置数字发音方式，下次合成时生效。

        Args:
            rdn (str): 数字发音方式
                "0": 自动判断（默认）
                "1": 完全数值
                "2": 完全字符串
                "3": 字符串优先

        Returns:
            self: 支持链式调用。

        Raises:
            ValueError: 参数不是 "0"、"1"、"2" 或 "3" 时抛出。

        ==========================================

        Set digit pronunciation mode, takes effect on next synthesis.

        Args:
            rdn (str): Digit pronunciation mode
                "0": Auto (default)
                "1": Complete numeric
                "2": Complete string
                "3": String priority

        Returns:
            self: Supports method chaining.

        Raises:
            ValueError: Raised when rdn is not "0", "1", "2", or "3".
        """
        if rdn not in ("0", "1", "2", "3"):
            raise ValueError("rdn must be '0', '1', '2', or '3'")
        self._rdn = rdn
        return self

    # ========== 内部方法 / Internal methods ==========

    def _build_auth_url(self):
        """
        构造带 HMAC-SHA256 鉴权参数的讯飞 TTS WebSocket 请求 URL。

        Returns:
            str: 包含 authorization、date、host 查询参数的 WSS URL。

        ==========================================

        Build the iFlytek TTS WebSocket URL with HMAC-SHA256 authentication query parameters.

        Returns:
            str: WSS URL containing authorization, date, and host query parameters.
        """
        date = _rfc1123_now()

        # Signature origin string per iFlytek docs
        sig_origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(_HOST, date, _PATH)

        # Decode API Secret from Base64, then HMAC-SHA256 sign
        secret_bytes = self._api_secret.encode('utf-8')
        sig_bytes    = _hmac_sha256(secret_bytes, sig_origin.encode('utf-8'))
        sig_b64      = binascii.b2a_base64(sig_bytes).decode('utf-8').strip()

        # Build authorization string and Base64-encode it
        auth_origin = (
            'api_key="{}", algorithm="hmac-sha256", '
            'headers="host date request-line", signature="{}"'
        ).format(self._api_key, sig_b64)
        auth_b64 = binascii.b2a_base64(auth_origin.encode('utf-8')).decode('utf-8').strip()

        url = "{}?authorization={}&date={}&host={}".format(
            _WSS_URL,
            _url_encode(auth_b64),
            _url_encode(date),
            _url_encode(_HOST),
        )
        return url

    def _build_request(self, text):
        """
        构造讯飞 TTS API 的 JSON 请求字符串，文字内容以 Base64 编码传输。

        Args:
            text (str): 待合成的文本。

        Returns:
            str: JSON 格式的请求字符串。

        ==========================================

        Build the iFlytek TTS API JSON request string; text is Base64-encoded.

        Args:
            text (str): Text to synthesize.

        Returns:
            str: JSON-formatted request string.
        """
        text_b64 = binascii.b2a_base64(text.encode('utf-8')).decode('utf-8').strip()
        req = {
            "common": {
                "app_id": self._app_id,
            },
            "business": {
                "aue": self._aue,
                "auf": self._auf,
                "vcn": self._vcn,
                "speed": self._speed,
                "volume": self._volume,
                "pitch": self._pitch,
                "bgs": self._bgs,
                "tte": self._tte,
                "reg": self._reg,
                "rdn": self._rdn,
            },
            "data": {
                "text":   text_b64,
                "status": 2,
            },
        }
        # sfl 仅在 aue=lame 时添加 / Add sfl only when aue=lame
        if self._sfl is not None:
            req["business"]["sfl"] = self._sfl
        return json.dumps(req)

    async def synthesize(self, text, filepath=None):
        """
        连接讯飞 TTS 服务，发送合成请求，逐帧接收并流式写入文件（或内存），避免大块内存分配。

        Args:
            text     (str): 待合成的文字内容。
            filepath (str, optional): 目标文件路径。提供时每帧立即写入文件，
                                      内存中峰值仅为单帧大小（约 1~4 KB）；
                                      为 None 时在内存中积累并返回 bytes（仅适合极短文本）。

        Returns:
            int:   filepath 不为 None 时，返回写入的总字节数；失败返回 0。
            bytes: filepath 为 None 时，返回完整 PCM 字节串；失败返回 b""。

        Notes:
            调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
            服务端 status==2 表示最后一帧，收到后主动关闭连接。

        ==========================================

        Connect to iFlytek TTS and stream audio chunks directly to a file to avoid
        large contiguous memory allocation on RAM-constrained devices.

        Args:
            text     (str): Text to synthesize.
            filepath (str, optional): Destination file path. When provided, each chunk is
                                      written immediately; peak RAM usage is one chunk (~1-4 KB).
                                      When None, chunks are accumulated in memory (short text only).

        Returns:
            int:   Total bytes written when filepath is given; 0 on failure.
            bytes: Complete PCM bytes when filepath is None; b"" on failure.

        Notes:
            WiFi must be connected and system time NTP-synced before calling.
            Server status==2 marks the final chunk; connection is closed afterward.
        """
        url = self._build_auth_url()
        print("Connecting to iFlytek TTS...")

        try:
            await self._ws.close()
        except Exception:
            pass
        self._ws = _WsClient(ms_delay_for_read=5)
        try:
            await self._ws.handshake(url, cert_reqs=0)
        except Exception as e:
            print("Handshake failed:", e)
            return 0 if filepath else b""

        print("Connected, sending request...")
        await self._ws.send(self._build_request(text))

        is_wav       = filepath is not None and filepath.lower().endswith('.wav')
        total_bytes  = 0
        audio_chunks = [] if filepath is None else None
        f            = open(filepath, "wb") if filepath else None
        if is_wav:
            try:
                sample_rate = int(self._auf.split('rate=')[1])
            except Exception:
                sample_rate = 8000
            f.write(_wav_header(sample_rate, 1, 16, 0))  # placeholder, fixed after streaming
        print("Receiving audio chunks...")

        try:
            while await self._ws.open():
                msg = await asyncio.wait_for(self._ws.recv(), 10)
                if msg is None:
                    print("Connection closed by server.")
                    break

                try:
                    resp = json.loads(msg)
                except Exception as e:
                    print("JSON parse error:", e)
                    break

                code = resp.get("code", -1)
                if code != 0:
                    print("TTS API error, code:", code, "msg:", resp.get("message", ""))
                    break

                audio_section = resp.get("data", {})
                audio_b64     = audio_section.get("audio", "")
                if audio_b64:
                    chunk = binascii.a2b_base64(audio_b64)
                    total_bytes += len(chunk)
                    if f:
                        f.write(chunk)
                    else:
                        audio_chunks.append(chunk)
                    print("Chunk received, bytes:", len(chunk))

                status = audio_section.get("status", 0)
                if status == 2:
                    print("All audio received, total bytes:", total_bytes)
                    break
        finally:
            if is_wav and f:
                f.seek(0)
                f.write(_wav_header(sample_rate, 1, 16, total_bytes))
            if f:
                f.close()

        await self._ws.close()
        return total_bytes if filepath else b"".join(audio_chunks)

    async def synthesize_and_play(self, text, audio_out, amp_sd, rate=16000):
        """
        连接讯飞 TTS，收到每个音频 chunk 立即写入 I2S，无需等待全部合成完成。
        相比 synthesize()+play_pcm() 可减少约 1~2 秒首字节延迟。

        Args:
            text      (str): 待合成文字。
            audio_out (I2S): 已初始化的 I2S TX 实例。
            amp_sd    (Pin): 功放 SD 引脚，合成前置高，播完后置低。
            rate      (int): 采样率，默认 16000，用于计算尾部等待时长。

        Returns:
            int: 实际写入 I2S 的总字节数；失败返回 0。
        """
        url = self._build_auth_url()
        print("[TTS] Connecting...")

        # 确保旧连接彻底关闭再新建，避免 socket 资源耗尽
        try:
            await self._ws.close()
        except Exception:
            pass
        self._ws = _WsClient(ms_delay_for_read=5)
        try:
            await asyncio.wait_for(self._ws.handshake(url, cert_reqs=0), 10)
        except Exception as e:
            print("[TTS] Handshake failed:", e)
            return 0

        await self._ws.send(self._build_request(text))

        amp_sd.value(1)
        total_bytes = 0
        swriter = asyncio.StreamWriter(audio_out)
        print("[TTS] Streaming audio...")

        try:
            while await self._ws.open():
                msg = await asyncio.wait_for(self._ws.recv(), 10)
                if msg is None:
                    break

                try:
                    resp = json.loads(msg)
                except Exception:
                    break

                code = resp.get("code", -1)
                if code != 0:
                    print("[TTS] API error:", code, resp.get("message", ""))
                    break

                audio_section = resp.get("data", {})
                audio_b64     = audio_section.get("audio", "")
                if audio_b64:
                    chunk = binascii.a2b_base64(audio_b64)
                    swriter.write(chunk)
                    await swriter.drain()
                    total_bytes += len(chunk)

                if audio_section.get("status", 0) == 2:
                    break
        finally:
            pass

        await self._ws.close()

        # 等待 I2S 缓冲区中剩余数据播完
        ibuf_ms = total_bytes * 1000 // (rate * 2)
        await asyncio.sleep_ms(ibuf_ms + 200)
        amp_sd.value(0)
        await asyncio.sleep_ms(300)
        print("[TTS] Done, {} bytes".format(total_bytes))
        return total_bytes

# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ===========================================
