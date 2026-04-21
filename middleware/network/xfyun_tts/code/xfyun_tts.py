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

__version__ = "1.0.0"
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
    默认输出 aue=raw（原始 PCM），采样率 8000 Hz（auf=audio/L16;rate=8000）。

    Attributes:
        _app_id     (str): 讯飞开放平台 APPID。
        _api_key    (str): API Key。
        _api_secret (str): API Secret（Base64 编码原文，由平台提供）。
        _vcn        (str): 发音人，默认 "x4_xiaoyan"。
        _aue        (str): 音频编码格式，默认 "raw"（原始 PCM）。
        _auf        (str): 音频采样规格，默认 "audio/L16;rate=8000"。
        _ws         (AsyncWebsocketClient): 内部 WebSocket 客户端实例。

    ==========================================

    iFlytek online TTS driver over WebSocket API, converting text to PCM audio.
    Default output: aue=raw (raw PCM) at 8000 Hz (auf=audio/L16;rate=8000).

    Attributes:
        _app_id     (str): iFlytek Open Platform APPID.
        _api_key    (str): API Key.
        _api_secret (str): API Secret (Base64-encoded string as provided by the platform).
        _vcn        (str): Voice name, default "x4_xiaoyan".
        _aue        (str): Audio encoding, default "raw" (raw PCM).
        _auf        (str): Audio format, default "audio/L16;rate=8000".
        _ws         (AsyncWebsocketClient): Internal WebSocket client instance.
    """

    def __init__(self, app_id, api_key, api_secret,
                 vcn="x4_xiaoyan", aue="raw", auf="audio/L16;rate=8000"):
        """
        初始化 TTS 驱动，保存鉴权参数与音频配置。

        Args:
            app_id     (str): 讯飞开放平台 APPID。
            api_key    (str): API Key。
            api_secret (str): API Secret（Base64 编码原文）。
            vcn        (str): 发音人，默认 "x4_xiaoyan"。
            aue        (str): 音频编码，默认 "raw"（PCM）。
            auf        (str): 音频格式，默认 "audio/L16;rate=8000"。

        ==========================================

        Initialize the TTS driver with authentication and audio parameters.

        Args:
            app_id     (str): iFlytek APPID.
            api_key    (str): API Key.
            api_secret (str): API Secret (Base64-encoded string).
            vcn        (str): Voice name, default "x4_xiaoyan".
            aue        (str): Audio encoding, default "raw" (PCM).
            auf        (str): Audio format, default "audio/L16;rate=8000".
        """
        self._app_id     = app_id
        self._api_key    = api_key
        self._api_secret = api_secret
        self._vcn        = vcn
        self._aue        = aue
        self._auf        = auf
        self._ws         = _WsClient(ms_delay_for_read=5)

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
                "tte": "UTF8",
            },
            "data": {
                "text":   text_b64,
                "status": 2,
            },
        }
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
