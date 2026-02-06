# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-        
# @Time    : 2025/3/21 下午7:13   
# @Author  : 李清水            
# @File    : dac_waveformgenerator.py       
# @Description : 通用波形发生器类，支持任意位数DAC，手动配置分辨率/写入方法，生成正弦波、三角波、方波
# 这部分代码由 leeqingshui 开发，采用CC BY-NC 4.0许可协议

# ======================================== 导入相关模块 =========================================
import math
from machine import Timer

# ======================================== 自定义类 ============================================
class WaveformGenerator:
    # 新增dac_resolution、dac_write_method入参，加None默认值避免语法错误，仅支持手动配置
    def __init__(self, dac, frequency: float = 1, amplitude: float = 1.65, offset: float = 1.65,
                 waveform: str = 'sine', rise_ratio: float = 0.5, vref: float = 3.3,
                 dac_resolution: int = None, dac_write_method: str = None) -> None:
        """
        初始化通用波形发生器实例（手动配置DAC分辨率/写入方法，支持任意位数DAC）。

        Args:
            dac: 任意DAC/数字电位器实例（手动配置分辨率和写入方法适配）
            frequency (float, optional): 信号频率，默认1Hz，0 < 频率 ≤ 10Hz
            amplitude (float, optional): 信号幅度，默认1.65V，0 ≤ 幅度 ≤ vref
            offset (float, optional): 直流偏移，默认1.65V，0 ≤ 偏移 ≤ vref
            waveform (str, optional): 波形类型，支持'sine'/'square'/'triangle'，默认'sine'
            rise_ratio (float, optional): 三角波上升比例，默认0.5，0 ≤ 比例 ≤ 1
            vref (float, optional): 参考电压，默认3.3V，必须大于0
            dac_resolution (int): 【必传】DAC最大分辨率（如7位DS3502=127、12位MCP4725=4095）
            dac_write_method (str): 【必传】DAC写入方法名字符串（如DS3502='write_wiper'、MCP4725='write'）

        Returns:
            None

        Raises:
            ValueError: 基础参数超出范围/分辨率未传/分辨率非正整数
            AttributeError: DAC实例无指定的写入方法
            TypeError: 分辨率非整数/写入方法名非字符串
        """
        # 一、完善参数校验：基础参数校验+新增DAC参数强校验，优化错误提示为中文
        # 1. 原有电压相关参数校验，优化提示更明确
        if not (0 < frequency <= 10):
            raise ValueError(f"Frequency error: must be between 0-10Hz, current value {frequency}")
        if vref <= 0:
            raise ValueError(f"Reference voltage error: must be greater than 0, current value {vref}")
        if not (0 <= amplitude <= vref):
            raise ValueError(f"Amplitude error: must be between 0-{vref}V, current value {amplitude}")
        if not (0 <= offset <= vref):
            raise ValueError(f"DC offset error: must be between 0-{vref}V, current value {offset}")
        if not (0 <= amplitude + offset <= vref) or not (offset - amplitude >= 0):
            raise ValueError(f"Amplitude+offset/offset-amplitude error: must be between 0-{vref}V to prevent DAC output out-of-bounds")
        if waveform not in ['sine', 'square', 'triangle']:
            raise ValueError(f"Waveform type error: only 'sine'/'square'/'triangle' are supported, current value {waveform}")
        if not (0 <= rise_ratio <= 1):
            raise ValueError(f"Triangle wave rise ratio error: must be between 0-1, current value {rise_ratio}")
        
        # 2. 新增DAC参数专属校验（核心：分辨率+写入方法）
        if dac_resolution is None:
            raise ValueError("dac_resolution is a required parameter, please specify the maximum DAC resolution (e.g., DS3502=127, MCP4725=4095)")
        if dac_write_method is None:
            raise ValueError("dac_write_method is a required parameter, please specify the DAC write method name (e.g., DS3502='write_wiper', MCP4725='write')")
        if not isinstance(dac_resolution, int) or dac_resolution <= 0:
            raise TypeError(f"DAC resolution error: must be a positive integer, current type {type(dac_resolution)}, value {dac_resolution}")
        if not isinstance(dac_write_method, str):
            raise TypeError(f"DAC write method name error: must be a string, current type {type(dac_write_method)}")
        if not hasattr(dac, dac_write_method):
            raise AttributeError(f"DAC instance has no specified write method: {dac_write_method}, please check if the method name is correct")

        # 二、保存核心参数：基础参数+新增DAC参数
        self.dac = dac
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        self.waveform = waveform
        self.rise_ratio = rise_ratio
        self.vref = vref
        self.sample_rate = 50  # 固定50个采样点
        self.dac_resolution = dac_resolution  # 保存手动配置的DAC分辨率
        
        # 解耦DAC写入操作：从dac_write_method获取方法对象，赋值给dac_write_func供后续调用
        self.dac_write_func = getattr(dac, dac_write_method)

        # 初始化定时器和采样点索引
        self.timer = Timer(-1)
        self.index = 0
        # 生成适配当前DAC的采样点
        self.samples = self.generate_samples()

    # 二、通用电压转DAC值方法：新增_to_dac_value，公式适配任意DAC，自动限制0~分辨率范围
    def _to_dac_value(self, voltage: float) -> int:
        """
        通用电压转DAC数值方法，适配任意位数DAC
        核心公式：DAC值 = (目标电压 / 参考电压) × DAC最大分辨率
        自动限制数值在0~dac_resolution之间，避免越界写入DAC
        """
        dac_val = int(voltage / self.vref * self.dac_resolution)
        return max(0, min(dac_val, self.dac_resolution))  # 越界限制

    # 改造采样点生成：复用通用_to_dac_value方法，移除原DS3502专属硬编码
    def generate_samples(self) -> list[int]:
        """生成适配当前DAC的采样点列表，复用通用电压转值方法"""
        samples = []
        for i in range(self.sample_rate):
            if self.waveform == 'sine':
                angle = 2 * math.pi * i / self.sample_rate
                voltage = self.offset + self.amplitude * math.sin(angle)
            elif self.waveform == 'square':
                voltage = self.offset + self.amplitude if i < self.sample_rate // 2 else self.offset - self.amplitude
            elif self.waveform == 'triangle':
                if i < self.sample_rate * self.rise_ratio:
                    voltage = self.offset + 2 * self.amplitude * (i / (self.sample_rate * self.rise_ratio)) - self.amplitude
                else:
                    voltage = self.offset + 2 * self.amplitude * ((self.sample_rate - i) / (self.sample_rate * (1 - self.rise_ratio))) - self.amplitude
            # 调用通用转值方法，替代原硬编码的转值逻辑
            samples.append(self._to_dac_value(voltage))
        return samples

    # 三、解耦DAC写入操作：update回调中用dac_write_func写入，替代原硬编码的dac.write/write_wiper
    def update(self, t: Timer) -> None:
        """定时器回调函数，通用DAC写入，无硬件耦合"""
        self.dac_write_func(self.samples[self.index])  # 调用方法对象写入，适配任意DAC
        self.index = (self.index + 1) % self.sample_rate

    # 保留原启动/停止逻辑，无修改
    def start(self) -> None:
        """启动波形生成器，开启定时器"""
        self.timer.init(freq=self.frequency * self.sample_rate, mode=Timer.PERIODIC, callback=self.update)

    def stop(self) -> None:
        """停止波形生成器，关闭定时器"""
        self.timer.deinit()
        self.index = 0

# ======================================== 初始化配置 ==========================================
# ========================================  主程序  ===========================================