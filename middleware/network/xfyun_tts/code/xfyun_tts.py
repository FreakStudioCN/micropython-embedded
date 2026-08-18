# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/14
# @Author  : leeqingsui
# @File    : xfyun_tts.py
# @Description : iFlytek 超拟人语音合成 (Super Smart TTS) driver over WebSocket for MicroPython
# @License : MIT

# ======================================== 导入相关模块 =========================================

import json
import time
import binascii
import hashlib
import struct
import asyncio
from async_websocketclient import AsyncWebsocketClient, URI
from fastb64 import b64encode_str, b64decode

# ======================================== 全局变量 ============================================

__version__ = "1.2.1"
__author__ = "leeqingsui"
__license__ = "MIT"
__platform__ = "MicroPython v1.23"

_HOST = "cbm01.cn-huabei-1.xf-yun.com"
_PATH = "/v1/private/mcd9m97e6"
_WSS_URL = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"

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
    获取当前 UTC 时间的 RFC1123 格式字符串，用于讯飞签名的 Date 头。

    这里走 timesync.utc_struct() 而不是 time.gmtime()：本 port 没有
    时区支持，gmtime() 和 localtime() 返回同一个值 —— RTC 里存什么就
    返回什么。项目 RTC 存东八区时间，直接用 gmtime() 会把 Date 头写
    成 8 小时后的时间，服务端判签名过期，返回 403 Forbidden。
    timesync 里的偏移是从 NTP 现算的，所以拿到的是真 UTC。

    Returns:
        str: RFC1123 格式时间字符串，例如 "Thu, 10 Apr 2026 12:00:00 GMT"。
    """
    try:
        import timesync

        t = timesync.utc_struct()
    except Exception:
        t = time.gmtime()  # timesync 不可用时退回原行为

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
    """
    block_size = 64
    if len(key) > block_size:
        key = hashlib.sha256(key).digest()
    key = key + b"\x00" * (block_size - len(key))
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
    """
    _safe = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")
    out = []
    for ch in s:
        if ch in _safe:
            out.append(ch)
        else:
            for byte in ch.encode("utf-8"):
                out.append("%{:02X}".format(byte))
    return "".join(out)


def _wav_header(sample_rate, channels, bits, data_size):
    """
    构造 44 字节的标准 WAV 文件头（PCM 格式，RIFF/WAVE/fmt/data）。

    Args:
        sample_rate (int): 采样率，如 16000。
        channels    (int): 声道数，1=单声道，2=立体声。
        bits        (int): 采样位深，如 16。
        data_size   (int): PCM 数据总字节数；写入占位头时传 0。

    Returns:
        bytes: 44 字节 WAV 文件头。
    """
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        data_size + 36,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )


# ======================================== 自定义类 ============================================


class _WsClient(AsyncWebsocketClient):
    """
    AsyncWebsocketClient 子类，用非递归字符串解析替换原正则解析。

    MicroPython 的 ure 正则引擎为递归实现，对超过 ~30 字符的路径段
    （如含鉴权参数的长 URL）会触发 "maximum recursion depth exceeded"。
    本子类仅覆盖 urlparse()，其余逻辑完全继承自父类。
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
        """
        if uri is None:
            raise ValueError("uri cannot be None")
        if uri.startswith("wss://"):
            protocol = "wss"
            rest = uri[6:]
            default_port = 443
        elif uri.startswith("ws://"):
            protocol = "ws"
            rest = uri[5:]
            default_port = 80
        else:
            raise ValueError("Scheme not ws or wss")

        slash = rest.find("/")
        if slash == -1:
            hostpart = rest
            path = "/"
        else:
            hostpart = rest[:slash]
            path = rest[slash:]

        colon = hostpart.find(":")
        if colon == -1:
            hostname = hostpart
            port = default_port
        else:
            hostname = hostpart[:colon]
            port = int(hostpart[colon + 1 :])

        return URI(protocol, hostname, port, path)


class XfyunTTS:
    """
    讯飞超拟人语音合成 (Super Smart TTS) 驱动，基于 WebSocket API，
    将文字合成为 PCM 音频（默认 raw PCM，16kHz，16-bit，单声道）。

    Attributes:
        _app_id     (str): 讯飞开放平台 APPID。
        _api_key    (str): API Key。
        _api_secret (str): API Secret（Base64 编码原文，由平台提供）。
        _vcn        (str): 默认发音人，如 "x6_lingfeiyi_pro"。
        _speed      (int): 语速 (0-100)，默认 50。
        _volume     (int): 音量 (0-100)，默认 50。
        _pitch      (int): 语调 (0-100)，默认 50。
        _bgs        (int): 背景音 (0/1)，默认 0。
        _reg        (int): 英文发音方式，默认 0。
        _rdn        (int): 数字发音方式，默认 0。
        _rhy        (int): 是否返回拼音标注，默认 0。
        _oral_level (str): 口语化等级 "high"/"mid"/"low"，默认 "mid"。
        _audio_cfg  (dict): 音频输出格式配置。
        _ws         (_WsClient): 内部 WebSocket 客户端实例。

    ==========================================

    iFlytek Super Smart TTS driver over WebSocket API.
    Converts text to PCM audio (default: raw PCM, 16kHz, 16-bit, mono).

    Attributes:
        _app_id     (str): iFlytek APPID.
        _api_key    (str): API Key.
        _api_secret (str): API Secret (Base64-encoded string).
        _vcn        (str): Default voice name, e.g. "x6_lingfeiyi_pro".
        _speed      (int): Speed (0-100), default 50.
        _volume     (int): Volume (0-100), default 50.
        _pitch      (int): Pitch (0-100), default 50.
        _bgs        (int): Background sound (0/1), default 0.
        _reg        (int): English pronunciation mode, default 0.
        _rdn        (int): Number pronunciation mode, default 0.
        _rhy        (int): Pinyin annotation flag, default 0.
        _oral_level (str): Colloquial level "high"/"mid"/"low", default "mid".
        _audio_cfg  (dict): Audio output format configuration.
        _ws         (_WsClient): Internal WebSocket client instance.
    """

    VOICE_XIAOYAN = "x4_xiaoyan"
    VOICE_YEZI = "x4_yezi"
    VOICE_JIUXU = "aisjiuxu"
    VOICE_JINGER = "aisjinger"
    VOICE_BABYXU = "aisbabyxu"
    VOICE_LINGFEIYI = "x6_lingfeiyi_pro"
    VOICE_LINGXIAOXUAN = "x6_lingxiaoxuan_pro"

    AUE_RAW = "raw"
    AUE_LAME = "lame"
    AUE_OPUS = "opus"
    AUE_OPUS_WB = "opus-wb"
    AUE_SPEEX = "speex;7"
    AUE_SPEEX_WB = "speex-wb;7"

    AUF_8K = "audio/L16;rate=8000"
    AUF_16K = "audio/L16;rate=16000"

    def __init__(
        self,
        app_id: str,
        api_key,
        api_secret,
        vcn="x6_lingfeiyi_pro",
        speed=50,
        volume=50,
        pitch=50,
        bgs=0,
        reg=0,
        rdn=0,
        rhy=0,
        oral_level="mid",
        audio_encoding="raw",
        audio_sample_rate=16000,
        audio_channels=1,
        audio_bit_depth=16,
        debug=False,
        cafile=None,
        cert_reqs=0,
        **kwargs
    ):
        """
        初始化超拟人 TTS 驱动，保存鉴权参数与合成配置。

        Args:
            app_id              (str): 讯飞开放平台 APPID。
            api_key             (str): API Key。
            api_secret          (str): API Secret。
            vcn                 (str): 默认发音人，参考控制台发音人列表。
            speed               (int): 语速 (0-100)，默认 50。
            volume              (int): 音量 (0-100)，默认 50。
            pitch               (int): 语调 (0-100)，默认 50。
            bgs                 (int): 背景音 0/1，默认 0。
            reg                 (int): 英文发音方式，默认 0。
            rdn                 (int): 数字发音方式，默认 0。
            rhy                 (int): 是否返回拼音标注，默认 0。
            oral_level          (str): 口语化等级 "high"/"mid"/"low"，默认 "mid"。
            audio_encoding      (str): 音频编码 "raw"/"lame"/"speex" 等，默认 "raw"。
            audio_sample_rate   (int): 音频采样率，默认 16000。
            audio_channels      (int): 声道数，默认 1。
            audio_bit_depth     (int): 位深，默认 16。

        ==========================================

        Initialize the Super Smart TTS driver with authentication and synthesis parameters.

        Args:
            app_id              (str): iFlytek APPID.
            api_key             (str): API Key.
            api_secret          (str): API Secret.
            vcn                 (str): Default voice name.
            speed               (int): Speed (0-100), default 50.
            volume              (int): Volume (0-100), default 50.
            pitch               (int): Pitch (0-100), default 50.
            bgs                 (int): Background sound, default 0.
            reg                 (int): English pronunciation mode, default 0.
            rdn                 (int): Number pronunciation mode, default 0.
            rhy                 (int): Pinyin annotation flag, default 0.
            oral_level          (str): Colloquial level, default "mid".
            audio_encoding      (str): Audio encoding, default "raw".
            audio_sample_rate   (int): Sample rate, default 16000.
            audio_channels      (int): Channels, default 1.
            audio_bit_depth     (int): Bit depth, default 16.
            cafile              (str): CA certificate file path; use with cert_reqs=2 to verify the WSS peer.
            cert_reqs           (int): TLS certificate verification mode, 0=none, 2=required. Default 0 for compatibility.
        """
        if app_id is None:
            raise ValueError("app_id cannot be None")
        if not isinstance(app_id, str):
            raise ValueError("app_id must be str, got %s" % type(app_id))
        if api_key is None:
            raise ValueError("api_key cannot be None")
        if not isinstance(api_key, str):
            raise ValueError("api_key must be str, got %s" % type(api_key))
        if api_secret is None:
            raise ValueError("api_secret cannot be None")
        if not isinstance(api_secret, str):
            raise ValueError("api_secret must be str, got %s" % type(api_secret))

        # Backward-compatible aliases from the classic TTS API.
        if "aue" in kwargs:
            audio_encoding = kwargs.get("aue")
        if "auf" in kwargs:
            auf = kwargs.get("auf")
            if isinstance(auf, str) and "rate=8000" in auf:
                audio_sample_rate = 8000
            elif isinstance(auf, str) and "rate=16000" in auf:
                audio_sample_rate = 16000

        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        # TTS 参数
        self._vcn = vcn
        self._speed = speed
        self._volume = volume
        self._pitch = pitch
        self._bgs = bgs
        self._reg = reg
        self._rdn = rdn
        self._rhy = rhy
        # 口语化参数
        self._oral_level = oral_level
        # 音频格式
        self._audio_cfg = {
            "encoding": audio_encoding,
            "sample_rate": audio_sample_rate,
            "channels": audio_channels,
            "bit_depth": audio_bit_depth,
            "frame_size": 0,
        }
        self._debug = debug
        self._cafile = cafile
        self._cert_reqs = cert_reqs
        self._ws = _WsClient(ms_delay_for_read=5)

    def set_voice(self, vcn) -> "XfyunTTS":
        if vcn is None:
            raise ValueError("vcn cannot be None")
        self._vcn = vcn
        return self

    def set_speed(self, speed) -> "XfyunTTS":
        if speed < 0 or speed > 100:
            raise ValueError("speed must be in [0, 100]")
        self._speed = speed
        return self

    def set_volume(self, volume) -> "XfyunTTS":
        if volume < 0 or volume > 100:
            raise ValueError("volume must be in [0, 100]")
        self._volume = volume
        return self

    def set_pitch(self, pitch) -> "XfyunTTS":
        if pitch < 0 or pitch > 100:
            raise ValueError("pitch must be in [0, 100]")
        self._pitch = pitch
        return self

    def set_background_sound(self, enabled) -> "XfyunTTS":
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self._bgs = 1 if enabled else 0
        return self

    def set_audio_encoding(self, aue, sfl=None) -> "XfyunTTS":
        if aue is None:
            raise ValueError("aue cannot be None")
        self._audio_cfg["encoding"] = aue
        if sfl is not None:
            self._audio_cfg["sfl"] = sfl
        elif "sfl" in self._audio_cfg:
            del self._audio_cfg["sfl"]
        return self

    def set_sample_rate(self, rate) -> "XfyunTTS":
        if rate not in (8000, 16000):
            raise ValueError("rate must be 8000 or 16000")
        self._audio_cfg["sample_rate"] = rate
        return self

    def set_text_encoding(self, tte) -> "XfyunTTS":
        if tte is None:
            raise ValueError("tte cannot be None")
        self._audio_cfg["text_encoding"] = tte
        return self

    def set_english_pronunciation(self, reg) -> "XfyunTTS":
        if str(reg) not in ("0", "1", "2"):
            raise ValueError("reg must be '0', '1', or '2'")
        self._reg = reg
        return self

    def set_digit_pronunciation(self, rdn) -> "XfyunTTS":
        if str(rdn) not in ("0", "1", "2", "3"):
            raise ValueError("rdn must be '0', '1', '2', or '3'")
        self._rdn = rdn
        return self

    def _log(self, msg):
        if msg is None:
            raise ValueError("msg cannot be None")
        if self._debug:
            print("[XfyunTTS]", msg)

    def _build_auth_url(self):
        """
        构造带 HMAC-SHA256 鉴权参数的讯飞超拟人 TTS WebSocket 请求 URL。

        Returns:
            str: 包含 authorization、date、host 查询参数的 WSS URL。
        """
        date = _rfc1123_now()

        # 签名原文：host + date + request-line
        sig_origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(_HOST, date, _PATH)

        secret_bytes = self._api_secret.encode("utf-8")
        sig_bytes = _hmac_sha256(secret_bytes, sig_origin.encode("utf-8"))
        sig_b64 = binascii.b2a_base64(sig_bytes).decode("utf-8").strip()

        auth_origin = ('api_key="{}", algorithm="hmac-sha256", ' 'headers="host date request-line", signature="{}"').format(self._api_key, sig_b64)
        auth_b64 = binascii.b2a_base64(auth_origin.encode("utf-8")).decode("utf-8").strip()

        return "{}?authorization={}&date={}&host={}".format(
            _WSS_URL,
            _url_encode(auth_b64),
            _url_encode(date),
            _url_encode(_HOST),
        )

    def _build_request(self, text, vcn=None, **kwargs):
        """
        构造超拟人 TTS API 的 JSON 请求字符串。

        支持在调用时覆盖 vcn、speed、volume、pitch 等参数。

        Args:
            text (str): 待合成的文本。
            vcn  (str, optional): 发音人，覆盖默认值。
            **kwargs: 可选覆盖 speed, volume, pitch, bgs, reg, rdn, rhy, oral_level。

        Returns:
            str: JSON 格式的请求字符串。
        """
        if text is None:
            raise ValueError("text cannot be None")
        # 合并 TTS 参数：实例默认值 + 调用时覆盖
        tts_params = {
            "vcn": vcn if vcn else self._vcn,
            "speed": self._speed,
            "volume": self._volume,
            "pitch": self._pitch,
            "bgs": self._bgs,
            "reg": self._reg,
            "rdn": self._rdn,
            "rhy": self._rhy,
            "audio": dict(self._audio_cfg),
        }
        # 调用时覆盖 speed/volume/pitch/bgs/reg/rdn/rhy
        for k in ("speed", "volume", "pitch", "bgs", "reg", "rdn", "rhy"):
            if k in kwargs:
                tts_params[k] = kwargs[k]
        # 调用时覆盖 audio 子参数
        for k in ("encoding", "sample_rate", "channels", "bit_depth", "frame_size"):
            if k in kwargs:
                tts_params["audio"][k] = kwargs[k]

        # 口语化参数
        oral_level = kwargs.get("oral_level", self._oral_level)

        # 文本需要 Base64 编码（API 要求）
        text_b64 = b64encode_str(text.encode("utf-8"))

        req = {
            "header": {
                "app_id": self._app_id,
                "status": 2,  # 一次性合成，直接传 2
            },
            "parameter": {
                "oral": {
                    "oral_level": oral_level,
                },
                "tts": tts_params,
            },
            "payload": {
                "text": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain",
                    "status": 2,
                    "seq": 0,
                    "text": text_b64,  # Base64 编码后发送
                },
            },
        }
        return json.dumps(req)

    async def synthesize(self, text, filepath=None, vcn=None, **kwargs):
        """
        连接超拟人 TTS 服务，发送合成请求，逐帧接收并流式写入文件（或内存）。

        Args:
            text     (str): 待合成的文字内容。
            filepath (str, optional): 目标文件路径。提供时每帧立即写入文件，
                                      内存中峰值仅为单帧大小；
                                      为 None 时在内存中积累并返回 bytes（仅适合极短文本）。
            vcn      (str, optional): 发音人，覆盖初始化时的默认值。例如 "x6_lingfeiyi_pro"。
            **kwargs: 可选覆盖 speed, volume, pitch, bgs, reg, rdn, rhy, oral_level,
                      audio_encoding, sample_rate 等。

        Returns:
            int:   filepath 不为 None 时，返回写入的总字节数；失败返回 0。
            bytes: filepath 为 None 时，返回完整 PCM 字节串；失败返回 b""。

        Example:
            # 使用默认发音人
            await tts.synthesize("你好世界", "tts.pcm")

            # 指定发音人
            await tts.synthesize("你好世界", "tts.pcm", vcn="x6_lingxiaoxuan_pro")

            # 指定发音人 + 语速
            await tts.synthesize("你好世界", "tts.pcm", vcn="x6_lingxiaoxuan_pro", speed=60)

        Notes:
            调用前需确保 WiFi 已连接，且已通过 ntptime.settime() 同步系统时间。
            服务端 header.status==2 表示最后一帧，收到后主动关闭连接。
        """
        url = self._build_auth_url()
        print("[TTS] Connecting to iFlytek Super Smart TTS...")

        # 每次 synthesize 重建 WebSocket
        try:
            await self._ws.close()
        except Exception:
            pass
        self._ws = _WsClient(ms_delay_for_read=5)
        try:
            await self._ws.handshake(url, cafile=self._cafile, cert_reqs=self._cert_reqs)
        except Exception as e:
            print("[TTS] Handshake failed:", e)
            return 0 if filepath else b""

        # 发送请求（vcn 和 kwargs 可在调用时覆盖）
        print("[TTS] Sending request (vcn=%s)..." % (vcn if vcn else self._vcn))
        await self._ws.send(self._build_request(text, vcn=vcn, **kwargs))

        # 是否保存为 WAV
        is_wav = filepath is not None and filepath.lower().endswith(".wav")
        sample_rate = self._audio_cfg.get("sample_rate", 16000)

        total_bytes = 0
        audio_chunks = [] if filepath is None else None
        f = open(filepath, "wb") if filepath else None
        if is_wav and f:
            f.write(_wav_header(sample_rate, 1, 16, 0))  # placeholder

        print("[TTS] Receiving audio chunks...")

        try:
            while await self._ws.open():
                msg = await asyncio.wait_for(self._ws.recv(), 10)
                if msg is None:
                    print("[TTS] Connection closed by server.")
                    break

                try:
                    resp = json.loads(msg)
                except Exception as e:
                    print("[TTS] JSON parse error:", e)
                    break

                code = resp.get("header", {}).get("code", -1)
                if code != 0:
                    print(
                        "[TTS] API error, code:",
                        code,
                        "msg:",
                        resp.get("header", {}).get("message", ""),
                    )
                    break

                # 提取音频数据
                payload = resp.get("payload", {})
                audio_section = payload.get("audio", {})
                audio_b64 = audio_section.get("audio", "")
                if audio_b64:
                    chunk = b64decode(audio_b64)
                    total_bytes += len(chunk)
                    if f:
                        f.write(chunk)
                    else:
                        audio_chunks.append(chunk)

                status = audio_section.get("status", 0)
                if status == 2:
                    print("[TTS] All audio received, total bytes:", total_bytes)
                    break
        finally:
            if is_wav and f:
                f.seek(0)
                f.write(_wav_header(sample_rate, 1, 16, total_bytes))
            if f:
                f.close()

        await self._ws.close()
        return total_bytes if filepath else b"".join(audio_chunks)

    async def synthesize_streaming(self, text, on_chunk, vcn=None, **kwargs):
        """
        流式合成：每收到一个音频块就立即调用 on_chunk(chunk) 回调，
        无需等待全部合成完毕即可开始播放，大幅降低首字延迟。

        Args:
            text     (str): 待合成的文字内容。
            on_chunk (callable): async callable(pcm_bytes)，
                                 每收到一个音频块就调用一次。
            vcn      (str, optional): 发音人，覆盖默认值。
            **kwargs: 可选覆盖 speed, volume, pitch, bgs, reg, rdn, rhy,
                      oral_level, audio_encoding, sample_rate 等。

        Returns:
            int: 接收到的总字节数；失败返回 0。

        Example:
            async def play(chunk):
                codec.write(chunk)

            total = await tts.synthesize_streaming("你好", play)
        """
        url = self._build_auth_url()
        print("[TTS] Connecting to iFlytek Super Smart TTS (streaming)...")

        # 每次重建 WebSocket
        try:
            await self._ws.close()
        except Exception:
            pass
        self._ws = _WsClient(ms_delay_for_read=5)
        try:
            await self._ws.handshake(url, cafile=self._cafile, cert_reqs=self._cert_reqs)
        except Exception as e:
            print("[TTS] Handshake failed:", e)
            return 0

        # 发送请求
        print("[TTS] Sending request (vcn=%s)..." % (vcn if vcn else self._vcn))
        await self._ws.send(self._build_request(text, vcn=vcn, **kwargs))

        total = 0
        print("[TTS] Streaming audio chunks...")

        try:
            while await self._ws.open():
                msg = await asyncio.wait_for(self._ws.recv(), 10)
                if msg is None:
                    print("[TTS] Connection closed by server.")
                    break

                try:
                    resp = json.loads(msg)
                except Exception as e:
                    print("[TTS] JSON parse error:", e)
                    break

                code = resp.get("header", {}).get("code", -1)
                if code != 0:
                    print(
                        "[TTS] API error, code:",
                        code,
                        "msg:",
                        resp.get("header", {}).get("message", ""),
                    )
                    break

                # 提取音频数据，立即回调
                payload = resp.get("payload", {})
                audio_section = payload.get("audio", {})
                audio_b64 = audio_section.get("audio", "")
                if audio_b64:
                    chunk = b64decode(audio_b64)
                    total += len(chunk)
                    await on_chunk(chunk)

                status = audio_section.get("status", 0)
                if status == 2:
                    print("[TTS] All audio received, total bytes:", total)
                    break
        finally:
            await self._ws.close()

        return total

    async def synthesize_and_play(self, text, audio_out, amp_sd, rate=16000, vcn=None, **kwargs):
        """
        流式合成并直接播放到 I2S（保留兼容，适用于 I2S 外设）。
        注意：当前项目使用 machine.AudioCodec，请使用 synthesize() 替代。

        Args:
            text      (str): 待合成文字。
            audio_out (I2S): 已初始化的 I2S TX 实例。
            amp_sd    (Pin): 功放 SD 引脚。
            rate      (int): 采样率，默认 16000。
            vcn       (str, optional): 发音人。
            **kwargs:  其他 TTS 参数。

        Returns:
            int: 实际写入 I2S 的总字节数；失败返回 0。
        """
        # 先合成到文件，再播放（兼容实现）
        tmp = "/tmp_tts.pcm"
        total = await self.synthesize(text, tmp, vcn=vcn, sample_rate=rate, **kwargs)
        if total <= 0:
            return 0

        amp_sd.value(1)
        frame = 640
        with open(tmp, "rb") as f:
            while True:
                chunk = f.read(frame)
                if not chunk:
                    break
                audio_out.write(chunk)

        # 等待缓冲区排空
        ibuf_ms = total * 1000 // (rate * 2)
        await asyncio.sleep_ms(ibuf_ms + 200)
        amp_sd.value(0)
        await asyncio.sleep_ms(300)

        try:
            import os

            os.remove(tmp)
        except Exception:
            pass
        return total

    def deinit(self) -> None:
        try:
            asyncio.run(self._ws.close())
        except Exception:
            pass
        self._log("Resources released")


# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ===========================================
