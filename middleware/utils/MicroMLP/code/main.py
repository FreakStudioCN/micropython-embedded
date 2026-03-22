# Python env   : MicroPython v1.27.0
# -*- coding: utf-8 -*-
# @Time    : 2026/3/22 下午3:26
# @Author  : 李清水
# @File    : main.py
# @Description : microMLP驱动库相关测试代码

# ======================================== 导入相关模块 =========================================

from microMLP import MicroMLP
import time

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================

# ======================================== 初始化配置 ==========================================

# 上电延时3s
time.sleep(3)
# 打印调试信息
print("FreakStudio : MicroMLP test start")

mlp = MicroMLP.Create(neuronsByLayers=[2, 2, 1], activationFuncName=MicroMLP.ACTFUNC_GAUSSIAN, layersAutoConnectFunction=MicroMLP.LayersFullConnect)

nnFalse = MicroMLP.NNValue.FromBool(False)
nnTrue = MicroMLP.NNValue.FromBool(True)

mlp.AddExample([nnFalse, nnFalse], [nnFalse])
mlp.AddExample([nnFalse, nnTrue], [nnTrue])
mlp.AddExample([nnTrue, nnTrue], [nnFalse])
mlp.AddExample([nnTrue, nnFalse], [nnTrue])

learnCount = mlp.LearnExamples()

# ========================================  主程序  ===========================================

print("LEARNED :")
print("  - False xor False = %s" % mlp.Predict([nnFalse, nnFalse])[0].AsBool)
print("  - False xor True  = %s" % mlp.Predict([nnFalse, nnTrue])[0].AsBool)
print("  - True  xor True  = %s" % mlp.Predict([nnTrue, nnTrue])[0].AsBool)
print("  - True  xor False = %s" % mlp.Predict([nnTrue, nnFalse])[0].AsBool)
