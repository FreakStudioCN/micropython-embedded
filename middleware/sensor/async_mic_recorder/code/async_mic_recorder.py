# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/04/20
# @Author  : leeqingsui
# @File    : async_mic_recorder.py
# @Description : Async VAD microphone recorder for MicroPython using I2S StreamReader
# @License : MIT

__version__  = "1.0.0"
__author__   = "leeqingsui"
__license__  = "MIT"
__platform__ = "MicroPython v1.23"

# ======================================== 导入相关模块 =========================================

import asyncio
import struct
import math
import gc

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

class AsyncMicRecorder:
    """
    基于 asyncio.StreamReader 的异步 VAD 麦克风录音类。
    通过能量阈值检测语音起止，将完整一句话写入 PCM 文件。
    支持预热丢帧、最大录音时长、能量回调和事件回调。

    Attributes:
        _i2s         (I2S): machine.I2S 实例，mode=RX。
        _rate        (int): 采样率，Hz。
        _threshold   (int): VAD 能量阈值，越大越不灵敏。
        _sil_frames  (int): 连续静音帧数触发停止。
        _min_frames  (int): 最短有效语音帧数，过短则忽略。
        _frame_bytes (int): 每帧字节数。
        _max_bytes   (int): PSRAM 预分配最大字节数。
        _warmup      (int): 预热丢弃帧数。
        _on_energy   (callable): 每帧能量回调 fn(energy)，None 则静默。
        _on_event    (callable): 状态事件回调 fn(msg)，None 则静默。

    Methods:
        start(): 预热麦克风，丢弃初始噪声帧。
        listen(output_file): 阻塞直到检测到完整一句话，写入文件，返回路径。
        stop(): 释放 I2S 资源。

    Notes:
        - 事件字符串：'ready', 'voice_start', 'too_short', 'saved:path:size'
        - listen() 使用 PSRAM 预分配 + memoryview 实现零拷贝写入，避免 GC 停顿。

    ==========================================

    Async VAD microphone recorder using asyncio.StreamReader over I2S.
    Detects speech start/end by RMS energy threshold and writes one utterance to a PCM file.

    Attributes:
        _i2s         (I2S): machine.I2S instance, mode=RX.
        _rate        (int): Sample rate in Hz.
        _threshold   (int): VAD energy threshold; higher = less sensitive.
        _sil_frames  (int): Consecutive silence frames to trigger stop.
        _min_frames  (int): Minimum voice frames; shorter utterances are discarded.
        _frame_bytes (int): Bytes per frame.
        _max_bytes   (int): Pre-allocated PSRAM buffer size in bytes.
        _warmup      (int): Warm-up frames to discard on start.
        _on_energy   (callable): Per-frame energy callback fn(energy), None = silent.
        _on_event    (callable): State event callback fn(msg), None = silent.

    Methods:
        start(): Warm up the microphone, discarding initial noise frames.
        listen(output_file): Block until a complete utterance is detected, write to file, return path.
        stop(): Release I2S resources.

    Notes:
        - Event strings: 'ready', 'voice_start', 'too_short', 'saved:path:size'
        - listen() uses pre-allocated PSRAM + memoryview for zero-copy writes to avoid GC pauses.
    """

    def __init__(self,
                 i2s,
                 rate: int = 16000,
                 threshold: int = 600,
                 silence_frames: int = 40,
                 min_voice_frames: int = 5,
                 frame_bytes: int = 2048,
                 max_seconds: int = 30,
                 warmup_frames: int = 15,
                 on_energy=None,
                 on_event=None) -> None:
        """
        初始化录音器，校验参数并预计算内部状态。

        Args:
            i2s              : machine.I2S 实例（mode=RX，bits=16，format=MONO）。
            rate         (int): 采样率，Hz，必须 > 0，默认 16000。
            threshold    (int): VAD 能量阈值，必须 >= 0，默认 600。
            silence_frames(int): 连续静音帧数触发停止，必须 > 0，默认 40。
            min_voice_frames(int): 最短有效语音帧数，必须 > 0，默认 5。
            frame_bytes  (int): 每帧字节数，必须 > 0 且为偶数，默认 2048。
            max_seconds  (int): 最大录音时长（秒），必须 > 0，默认 30。
            warmup_frames(int): 预热丢弃帧数，必须 >= 0，默认 15。
            on_energy        : 每帧能量回调 fn(energy)，可为 None。
            on_event         : 状态事件回调 fn(msg)，可为 None。

        Raises:
            ValueError: 任意数值参数不在合法范围内。
            TypeError:  数值参数类型不是 int，或回调不可调用。

        ==========================================

        Initialize the recorder, validate parameters and pre-compute internal state.

        Args:
            i2s              : machine.I2S instance (mode=RX, bits=16, format=MONO).
            rate         (int): Sample rate in Hz, must be > 0, default 16000.
            threshold    (int): VAD energy threshold, must be >= 0, default 600.
            silence_frames(int): Consecutive silence frames to stop, must be > 0, default 40.
            min_voice_frames(int): Minimum voice frames, must be > 0, default 5.
            frame_bytes  (int): Bytes per frame, must be > 0 and even, default 2048.
            max_seconds  (int): Max recording duration in seconds, must be > 0, default 30.
            warmup_frames(int): Warm-up frames to discard, must be >= 0, default 15.
            on_energy        : Per-frame energy callback fn(energy), may be None.
            on_event         : State event callback fn(msg), may be None.

        Raises:
            ValueError: Any numeric parameter is out of valid range.
            TypeError:  Numeric parameter is not int, or callback is not callable.
        """
        # 校验 i2s（鸭子类型：检查 readinto 接口）
        if not hasattr(i2s, "readinto"):
            raise TypeError("i2s must be a machine.I2S instance with readinto()")

        # 校验 rate
        if not isinstance(rate, int):
            raise TypeError("rate must be int, got {}".format(type(rate).__name__))
        if rate <= 0:
            raise ValueError("rate must be > 0, got {}".format(rate))

        # 校验 threshold
        if not isinstance(threshold, int):
            raise TypeError("threshold must be int, got {}".format(type(threshold).__name__))
        if threshold < 0:
            raise ValueError("threshold must be >= 0, got {}".format(threshold))

        # 校验 silence_frames
        if not isinstance(silence_frames, int):
            raise TypeError("silence_frames must be int, got {}".format(type(silence_frames).__name__))
        if silence_frames <= 0:
            raise ValueError("silence_frames must be > 0, got {}".format(silence_frames))

        # 校验 min_voice_frames
        if not isinstance(min_voice_frames, int):
            raise TypeError("min_voice_frames must be int, got {}".format(type(min_voice_frames).__name__))
        if min_voice_frames <= 0:
            raise ValueError("min_voice_frames must be > 0, got ".format(min_voice_frames))

        # 校验 frame_bytes
        if not isinstance(frame_bytes, int):
            raise TypeError("frame_bytes must be int, got {}".format(type(frame_bytes).__name__))
        if frame_bytes <= 0 or frame_bytes % 2 != 0:
            raise ValueError("frame_bytes must be a positive even integer, got {}".format(frame_bytes))

        # 校验 max_seconds
        if not isinstance(max_seconds, int):
            raise TypeError("max_seconds must be int, got {}".format(type(max_seconds).__name__))
        if max_seconds <= 0:
            raise ValueError("max_seconds must be > 0, got {}".format(max_seconds))

        # 校验 warmup_frames
        if not isinstance(warmup_frames, int):
            raise TypeError("warmup_frames must be int, got {}".format(type(warmup_frames).__name__))
        if warmup_frames < 0:
            raise ValueError("warmup_frames must be >= 0, got {}".format(warmup_frames))

        # 校验回调（可为 None，非 None 时必须可调用）
        if on_energy is not None and not callable(on_energy):
            raise TypeError("on_energy must be callable or None")
        if on_event is not None and not callable(on_event):
            raise TypeError("on_event must be callable or None")

        # 保存参数
        self._i2s         = i2s
        self._rate        = rate
        self._threshold   = threshold
        self._sil_frames  = silence_frames
        self._min_frames  = min_voice_frames
        self._frame_bytes = frame_bytes
        self._max_bytes   = rate * 2 * max_seconds
        self._warmup      = warmup_frames
        self._on_energy   = on_energy
        self._on_event    = on_event

    def _emit(self, msg: str) -> None:
        """
        触发事件回调（内部方法）。

        Args:
            msg (str): 事件字符串。

        ==========================================

        Fire the event callback (internal method).

        Args:
            msg (str): Event string.
        """
        if msg is None:
            raise ValueError("msg cannot be None")
        if not isinstance(msg, str):
            raise TypeError("msg must be str, got {}".format(type(msg).__name__))
        if self._on_event:
            self._on_event(msg)

    async def start(self) -> None:
        """
        预热麦克风，丢弃初始噪声帧，完成后触发 'ready' 事件。

        Notes:
            必须在 listen() 之前调用一次。

        ==========================================

        Warm up the microphone by discarding initial noise frames, then fires 'ready' event.

        Notes:
            Must be called once before listen().
        """
        # 创建 asyncio StreamReader 包装 I2S
        sreader = asyncio.StreamReader(self._i2s)
        self._sreader = sreader
        buf = bytearray(self._frame_bytes)
        # 丢弃预热帧，消除 I2S 启动噪声
        for _ in range(self._warmup):
            await sreader.readinto(buf)
        self._emit("ready")

    async def listen(self, output_file: str = "mic.pcm") -> str:
        """
        阻塞直到检测到完整一句话，将 PCM 数据写入文件，返回文件路径。

        Args:
            output_file (str): 输出 PCM 文件路径，默认 "mic.pcm"。

        Returns:
            str: 写入成功的文件路径。

        Raises:
            ValueError: output_file 为 None 或空字符串。
            TypeError:  output_file 不是字符串。

        Notes:
            使用 PSRAM 预分配缓冲区 + memoryview 实现零拷贝写入，避免 GC 停顿。
            事件序列：voice_start → (too_short | saved:path:size)

        ==========================================

        Block until a complete utterance is detected, write PCM to file, return file path.

        Args:
            output_file (str): Output PCM file path, default "mic.pcm".

        Returns:
            str: Path of the written file.

        Raises:
            ValueError: output_file is None or empty string.
            TypeError:  output_file is not a string.

        Notes:
            Uses pre-allocated PSRAM buffer + memoryview for zero-copy writes to avoid GC pauses.
            Event sequence: voice_start -> (too_short | saved:path:size)
        """
        # 校验 output_file
        if output_file is None:
            raise ValueError("output_file cannot be None")
        if not isinstance(output_file, str):
            raise TypeError("output_file must be str, got {}".format(type(output_file).__name__))
        if len(output_file) == 0:
            raise ValueError("output_file cannot be empty")

        sreader  = self._sreader
        frame_b  = self._frame_bytes
        read_buf = bytearray(frame_b)

        # 预分配 PSRAM 缓冲区，避免录音过程中动态分配
        gc.collect()
        pcm_buf = bytearray(self._max_bytes)
        mv      = memoryview(pcm_buf)

        recording   = False
        silence_cnt = 0
        voice_cnt   = 0
        write_pos   = 0

        while True:
            await sreader.readinto(read_buf)
            energy = self._rms(read_buf)

            # 仅在非录音状态下触发能量回调（避免录音时频繁回调影响性能）
            if not recording and self._on_energy:
                self._on_energy(energy)

            if energy > self._threshold:
                if not recording:
                    # 检测到语音，进入录音状态
                    self._emit("voice_start")
                    recording   = True
                    silence_cnt = 0
                    voice_cnt   = 0
                    write_pos   = 0
                voice_cnt  += 1
                silence_cnt = 0
                end = write_pos + frame_b
                if end <= self._max_bytes:
                    mv[write_pos:end] = read_buf
                    write_pos = end

            elif recording:
                # 录音中遇到静音帧，继续写入（保留尾部静音）
                silence_cnt += 1
                end = write_pos + frame_b
                if end <= self._max_bytes:
                    mv[write_pos:end] = read_buf
                    write_pos = end

                if silence_cnt >= self._sil_frames:
                    if voice_cnt >= self._min_frames:
                        # 有效语音，写入文件
                        with open(output_file, "wb") as f:
                            f.write(mv[:write_pos])
                        self._emit("saved:{}:{}".format(output_file, write_pos))
                        return output_file
                    else:
                        # 语音过短，重置状态继续监听
                        self._emit("too_short")
                        recording = False
                        write_pos = 0

    def stop(self) -> None:
        """
        释放 I2S 硬件资源。

        Notes:
            调用后不可再使用 start()/listen()。

        ==========================================

        Release I2S hardware resources.

        Notes:
            Do not call start()/listen() after this.
        """
        self._i2s.deinit()

    @staticmethod
    def _rms(buf: bytearray) -> int:
        """
        计算缓冲区的 RMS 能量（每隔4个样本采样以降低 CPU 占用）。

        Args:
            buf (bytearray): 16-bit 有符号小端 PCM 数据。

        Returns:
            int: RMS 能量值。

        ==========================================

        Compute RMS energy of the buffer (sampled every 4th sample to reduce CPU load).

        Args:
            buf (bytearray): 16-bit signed little-endian PCM data.

        Returns:
            int: RMS energy value.
        """
        if not isinstance(buf, (bytearray, bytes, memoryview)):
            raise TypeError("buf must be bytearray/bytes/memoryview")
        n = len(buf) // 2
        if n == 0:
            return 0
        samples = struct.unpack('<' + 'h' * n, buf)
        sq_sum  = sum(samples[i] * samples[i] for i in range(0, n, 4))
        return int(math.sqrt(sq_sum / (n // 4)))

# ======================================== 初始化配置 ===========================================

# ========================================  主程序  ===========================================
