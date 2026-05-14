# Python env   : MicroPython v1.23.0
# -*- coding: utf-8 -*-
# @Time    : 2026/05/14
# @Author  : AI Assistant
# @File    : main.py
# @Description : 测试 VolcengineTTSV1WS 驱动类的代码
# @License : MIT

# ======================================== 导入相关模块 =========================================

import sys

sys.modules.pop("volcengine_tts_v1_ws", None)
import asyncio
import network
import time
from machine import I2S, Pin
from volcengine_tts_v1_ws import VolcengineTTSV1WS

# ======================================== 全局变量 ============================================

WIFI_SSID = "your_wifi_ssid"
WIFI_PASS = "your_wifi_password"
APP_ID = "your_app_id"
ACCESS_TOKEN = "your_access_token"

# ======================================== 功能函数 ============================================


def connect_wifi():
    """连接 WiFi 并打印 IP 地址。"""
    sta = network.WLAN(network.STA_IF)
    if not sta.isconnected():
        sta.active(True)
        sta.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(20):
            if sta.isconnected():
                break
            time.sleep(0.5)
    print("WiFi connected:", sta.ifconfig()[0])


async def run_tests(tts, audio_out, amp_sd):
    """执行全部 TTS 测试场景。"""
    V = VolcengineTTSV1WS

    tests = [
        # (描述, 文本, 语言, 是否流式, 参数)
        # ===== 新增：中文角色扮演 =====
        ("Chunzhen streaming", "嘿嘿，我是纯真少女，今天心情超好！", "zh", True, {"voice_type": V.VOICE_CHUNZHEN}),
        ("Xiaonaigou streaming", "哇，这个好好玩哦，我也想要！", "zh", True, {"voice_type": V.VOICE_XIAONAIGOU}),
        ("Jingling streaming", "欢迎来到魔法世界，我是你的精灵向导。", "zh", True, {"voice_type": V.VOICE_JINGLING}),
        ("Menyouping streaming", "嗯……还行吧，就这样。", "zh", True, {"voice_type": V.VOICE_MENYOUPING}),
        ("Neilian streaming", "这件事，我有一些不同的看法。", "zh", True, {"voice_type": V.VOICE_NEILIAN}),
        # ===== 新增：中文通用 =====
        ("Tianmeitaozi streaming", "桃子熟了，甜甜的，快来尝一口吧！", "zh", True, {"voice_type": V.VOICE_TIANMEITAOZI}),
        ("Kefunv streaming", "你好，有什么我可以帮助你的吗？", "zh", True, {"voice_type": V.VOICE_KEFUNV}),
        ("VV streaming", "哈哈，今天也是元气满满的一天！", "zh", True, {"voice_type": V.VOICE_VV}),
        ("Xiaohe streaming", "哇，這個真的超級好吃耶，你要不要試試看？", "zh", True, {"voice_type": V.VOICE_XIAOHE}),
        # ===== 新增：中文多情感（带 style）=====
        ("Guangzhoudege happy streaming", "哇，今日真系好开心啊，饮茶先！", "zh", True, {"voice_type": V.VOICE_GUANGZHOUDEGE, "style": "开心"}),
        ("Guangzhoudege angry streaming", "你搞咩啊！搞到我好嬲！", "zh", True, {"voice_type": V.VOICE_GUANGZHOUDEGE, "style": "愤怒"}),
        (
            "Jingqiangkanye happy streaming",
            "嘿，今儿个真高兴，咱哥儿几个好好乐呵乐呵！",
            "zh",
            True,
            {"voice_type": V.VOICE_JINGQIANGKANYE, "style": "开心"},
        ),
        ("Linjuayi care streaming", "孩子，吃了吗？来阿姨这儿，给你做好吃的。", "zh", True, {"voice_type": V.VOICE_LINJUAYI, "style": "开心"}),
        ("Beijingxiaoye happy streaming", "哟，这不是您嘛，稀客稀客，快请进！", "zh", True, {"voice_type": V.VOICE_BEIJINGXIAOYE, "style": "开心"}),
        ("Roumeinvyou coquettish streaming", "人家不嘛，你就陪我嘛……", "zh", True, {"voice_type": V.VOICE_ROUMEINVYOU, "style": "撒娇"}),
        ("Yangguang happy streaming", "加油！今天也是充满活力的一天！", "zh", True, {"voice_type": V.VOICE_YANGGUANG, "style": "开心"}),
        ("Meilinvyou coquettish streaming", "你怎么才来呀，人家等你好久了……", "zh", True, {"voice_type": V.VOICE_MEILINVYOU, "style": "撒娇"}),
        ("Shuangkuai happy streaming", "没问题！这事儿包在我身上，妥妥的！", "zh", True, {"voice_type": V.VOICE_SHUANGKUAI, "style": "开心"}),
        # ===== 原有：中文女声 =====
        ("Linxueying streaming", "我是甜美娇俏的声音，欢迎来到语音合成测试。", "zh", True, {"voice_type": V.VOICE_LINXUEYING}),
        ("Chengshu streaming", "岁月沉淀，温柔如初，这是成熟温柔的声音。", "zh", True, {"voice_type": V.VOICE_CHENGSHU}),
        ("Tianxin multi-emotion streaming", "今天天气真好，心情超级棒！", "zh", True, {"voice_type": V.VOICE_TIANXIN}),
        ("Gaolengyujie multi-emotion streaming", "哼，你以为你是谁？", "zh", True, {"voice_type": V.VOICE_GAOLENGYUJIE}),
        ("Yueyunv streaming", "你好，我系粤语小溏，欢迎嚟到广东话测试。", "zh", True, {"voice_type": V.VOICE_YUEYUNV}),
        # ===== 原有：中文男声 =====
        ("Aojiaobazong multi-emotion streaming", "本总裁的时间很宝贵，说重点。", "zh", True, {"voice_type": V.VOICE_AOJIAOBAZONG}),
        ("Yourougongzi multi-emotion streaming", "唉，这件事情嘛，我也不知道该怎么说……", "zh", True, {"voice_type": V.VOICE_YOUROUGONGZI}),
        # ===== 原有：语速测试（中文）=====
        ("Sophie speed 0.7 slow", "这是慢速语音合成测试，语速零点七倍。", "zh", False, {"voice_type": V.VOICE_SOPHIE, "speed": 0.7}),
        ("Sophie speed 1.5 fast", "这是快速语音合成测试，语速一点五倍。", "zh", False, {"voice_type": V.VOICE_SOPHIE, "speed": 1.5}),
        # ===== 原有：语调测试（中文）=====
        ("Qinqie pitch 0.7 low", "这是低音调测试，语调零点七倍。", "zh", False, {"voice_type": V.VOICE_QINQIE, "pitch": 0.7}),
        ("Qinqie pitch 1.4 high", "这是高音调测试，语调一点四倍！", "zh", False, {"voice_type": V.VOICE_QINQIE, "pitch": 1.4}),
        # ===== 原有：英语（美式）=====
        (
            "Serena American English streaming",
            "Hello! I'm Serena, an American English voice. Nice to meet you!",
            "en",
            True,
            {"voice_type": V.VOICE_EN_SERENA},
        ),
        (
            "Glen American English multi-emotion streaming",
            "Hey there! This is Glen speaking. How's it going today?",
            "en",
            True,
            {"voice_type": V.VOICE_EN_GLEN},
        ),
        # ===== 原有：英语（英式）=====
        (
            "Emily British English streaming",
            "Good day! I'm Emily, a British English voice. Lovely to speak with you.",
            "en",
            True,
            {"voice_type": V.VOICE_EN_EMILY},
        ),
        (
            "Corey British English multi-emotion",
            "Brilliant! This is Corey with a British accent. Quite splendid, isn't it?",
            "en",
            False,
            {"voice_type": V.VOICE_EN_COREY},
        ),
        # ===== 原有：日语 =====
        ("Hikaru Japanese streaming", "こんにちは！私はひかるです。音声合成のテストへようこそ。", "ja", True, {"voice_type": V.VOICE_JA_HIKARU}),
    ]

    for i, (desc, text, lang, streaming, kwargs) in enumerate(tests):
        print("\n=== Test {}: {} ===".format(i + 1, desc))
        if streaming:
            size = await tts.synthesize_and_play(text, audio_out, amp_sd, language=lang, **kwargs)
            print("Played {} bytes".format(size))
        else:
            path = "t{}.pcm".format(i + 1)
            size = await tts.synthesize(text, output_path=path, language=lang, **kwargs)
            print("Saved {} -> {} bytes".format(path, size))

    audio_out.deinit()
    print("\n=== All tests done ===")


# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

time.sleep(3)
print("FreakStudio: Using VolcengineTTSV1WS ...")

connect_wifi()

amp_sd = Pin(17, Pin.OUT, value=0)
audio_out = I2S(
    1,
    sck=Pin(14),
    ws=Pin(15),
    sd=Pin(16),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=16000,
    ibuf=40000,
)
tts = VolcengineTTSV1WS(
    app_id=APP_ID,
    access_token=ACCESS_TOKEN,
    voice_type=VolcengineTTSV1WS.VOICE_BV701_STREAMING,
    volume=0.5,
    debug=True,
)

# ========================================  主程序  ===========================================


async def main():
    """主入口，执行全部测试场景。"""
    try:
        await run_tests(tts, audio_out, amp_sd)
    except KeyboardInterrupt:
        print("Program interrupted by user")
    except OSError as e:
        print("Hardware communication error: %s" % str(e))
    except Exception as e:
        print("Unknown error: %s" % str(e))
    finally:
        print("Cleaning up resources...")
        audio_out.deinit()
        print("Program exited")


asyncio.run(main())
