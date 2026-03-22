# Python env   : MicroPython v1.27.0
# -*- coding: utf-8 -*-
# @Time    : 2026/3/22 下午3:25
# @Author  : 李清水
# @File    : microMLP.py
# @Description : 轻量级多层感知器(MLP)神经网络实现，支持多种激活函数、反向传播训练、QLearning及模型持久化
# @License : MIT comment

__version__ = "0.1.0"
__author__ = "Jean-Christophe Bos"
__license__ = "MIT"
__platform__ = "MicroPython v1.27"

# ======================================== 导入相关模块 =========================================

from math import exp, log
from json import load, dumps
from time import time

try:
    from machine import rng
except:
    from random import random

# ======================================== 全局变量 ============================================

# ======================================== 功能函数 ============================================

# ======================================== 自定义类 ============================================


class MicroMLP:
    """
    轻量级多层感知器(MLP)神经网络核心类，适配MicroPython/标准Python双环境，支持多种激活函数、反向传播训练、QLearning强化学习及模型序列化，专为资源受限的嵌入式场景设计。

    Attributes:
        ACTFUNC_HEAVISIDE (str): Heaviside激活函数名称常量。
        ACTFUNC_SIGMOID (str): Sigmoid激活函数名称常量。
        ACTFUNC_TANH (str): TanH激活函数名称常量。
        ACTFUNC_SOFTPLUS (str): SoftPlus激活函数名称常量。
        ACTFUNC_RELU (str): ReLU激活函数名称常量。
        ACTFUNC_GAUSSIAN (str): Gaussian激活函数名称常量。
        Eta (float): 学习率，控制权重更新步长，默认0.30。
        Alpha (float): 动量系数，抑制权重更新震荡，默认0.75。
        Gain (float): 激活函数增益系数，默认0.99。
        CorrectLearnedMAE (float): 训练完成的MAE阈值，默认0.02。
        _layers (list): 网络层列表，存储InputLayer/Layer/OutputLayer实例。
        _examples (list): 训练样本列表，存储输入-目标值对。

    Methods:
        __init__():
            初始化MLP实例，清空网络层和训练样本列表。
        Create(neuronsByLayers: list, activationFuncName: str, layersAutoConnectFunction=None, useBiasValue=1.0) -> MicroMLP:
            静态方法，创建MLP网络实例，初始化各层神经元并建立连接。
        RandomFloat() -> float:
            静态方法，生成0-1范围内的随机浮点数（适配MicroPython/标准Python）。
        RandomNetworkWeight() -> float:
            静态方法，生成-0.35~0.35范围内的随机权重值。
        HeavisideActivation(x: float, derivative=False) -> float:
            静态方法，Heaviside激活函数，可选返回导数。
        SigmoidActivation(x: float, derivative=False) -> float:
            静态方法，Sigmoid激活函数，可选返回导数。
        TanHActivation(x: float, derivative=False) -> float:
            静态方法，TanH激活函数，可选返回导数。
        SoftPlusActivation(x: float, derivative=False) -> float:
            静态方法，SoftPlus激活函数，可选返回导数。
        ReLUActivation(x: float, derivative=False) -> float:
            静态方法，ReLU激活函数，可选返回导数。
        GaussianActivation(x: float, derivative=False) -> float:
            静态方法，Gaussian激活函数，可选返回导数。
        LayersFullConnect(layerSrc: Layer, layerDst: Layer) -> None:
            静态方法，建立两层神经元间的全连接。
        GetActivationFunction(actFuncName: str) -> function:
            静态方法，根据名称返回对应的激活函数（含导数支持）。
        LoadFromFile(filename: str) -> MicroMLP:
            静态方法，从JSON文件加载预训练的MLP模型。
        GetLayer(layerIndex: int) -> Layer:
            获取指定索引的网络层实例，索引无效返回None。
        GetLayerIndex(layer: Layer) -> int:
            获取指定网络层的索引，层不存在抛出ValueError。
        AddLayer(layer: Layer) -> None:
            向网络添加一层神经元。
        RemoveLayer(layer: Layer) -> None:
            从网络移除指定层，层不存在抛出ValueError。
        ClearAll() -> None:
            清空网络所有层及关联资源。
        GetInputLayer() -> InputLayer:
            获取网络输入层实例，无输入层返回None。
        GetOutputLayer() -> OutputLayer:
            获取网络输出层实例，无输出层返回None。
        Learn(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            单次反向传播训练，返回训练是否成功。
        Test(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            测试模型预测效果，返回测试是否成功。
        Predict(inputVectorNNValues: list) -> list:
            模型预测，返回标准化的输出向量（NNValue列表），预测失败返回None。
        QLearningLearnForChosenAction(stateVectorNNValues: list, rewardNNValue: NNValue, pastStateVectorNNValues: list, chosenActionIndex: int, terminalState=True, discountFactorNNValue=None) -> bool:
            QLearning强化学习训练，返回训练是否成功。
        QLearningPredictBestActionIndex(stateVectorNNValues: list) -> int:
            QLearning预测最优动作索引，预测失败返回None。
        SaveToFile(filename: str) -> bool:
            将模型序列化为JSON文件保存，返回保存是否成功。
        AddExample(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            添加训练样本到样本列表，返回添加是否成功。
        ClearExamples() -> None:
            清空训练样本列表。
        LearnExamples(maxSeconds=30, maxCount=None, stopWhenLearned=True, printMAEAverage=True) -> int:
            批量训练样本，返回实际训练步数，训练失败返回0。

    Notes:
        - 轻量化设计，无第三方依赖，适配嵌入式MicroPython环境。
        - 激活函数导数仅在反向传播时使用，正向传播无需计算。
        - 训练终止条件可通过CorrectLearnedMAE调整，值越小训练精度越高。
        - 模型序列化仅保存权重/配置，不保存训练样本。

    ==========================================

    Lightweight Multi-Layer Perceptron (MLP) neural network core class, compatible with both MicroPython and standard Python. Supports multiple activation functions, backpropagation training, QLearning reinforcement learning, and model serialization, designed for resource-constrained embedded scenarios.

    Attributes:
        ACTFUNC_HEAVISIDE (str): Constant for Heaviside activation function name.
        ACTFUNC_SIGMOID (str): Constant for Sigmoid activation function name.
        ACTFUNC_TANH (str): Constant for TanH activation function name.
        ACTFUNC_SOFTPLUS (str): Constant for SoftPlus activation function name.
        ACTFUNC_RELU (str): Constant for ReLU activation function name.
        ACTFUNC_GAUSSIAN (str): Constant for Gaussian activation function name.
        Eta (float): Learning rate, controls weight update step size, default 0.30.
        Alpha (float): Momentum coefficient, suppresses weight update oscillation, default 0.75.
        Gain (float): Activation function gain coefficient, default 0.99.
        CorrectLearnedMAE (float): MAE threshold for training completion, default 0.02.
        _layers (list): List of network layers, stores InputLayer/Layer/OutputLayer instances.
        _examples (list): List of training samples, stores input-target value pairs.

    Methods:
        __init__():
            Initialize MLP instance, clear network layers and training sample list.
        Create(neuronsByLayers: list, activationFuncName: str, layersAutoConnectFunction=None, useBiasValue=1.0) -> MicroMLP:
            Static method, create MLP network instance, initialize neurons of each layer and establish connections.
        RandomFloat() -> float:
            Static method, generate random float in 0-1 range (compatible with MicroPython/standard Python).
        RandomNetworkWeight() -> float:
            Static method, generate random weight in -0.35~0.35 range.
        HeavisideActivation(x: float, derivative=False) -> float:
            Static method, Heaviside activation function, optionally return derivative.
        SigmoidActivation(x: float, derivative=False) -> float:
            Static method, Sigmoid activation function, optionally return derivative.
        TanHActivation(x: float, derivative=False) -> float:
            Static method, TanH activation function, optionally return derivative.
        SoftPlusActivation(x: float, derivative=False) -> float:
            Static method, SoftPlus activation function, optionally return derivative.
        ReLUActivation(x: float, derivative=False) -> float:
            Static method, ReLU activation function, optionally return derivative.
        GaussianActivation(x: float, derivative=False) -> float:
            Static method, Gaussian activation function, optionally return derivative.
        LayersFullConnect(layerSrc: Layer, layerDst: Layer) -> None:
            Static method, establish full connection between neurons of two layers.
        GetActivationFunction(actFuncName: str) -> function:
            Static method, return corresponding activation function (with derivative support) by name.
        LoadFromFile(filename: str) -> MicroMLP:
            Static method, load pre-trained MLP model from JSON file.
        GetLayer(layerIndex: int) -> Layer:
            Get network layer instance by index, return None if index is invalid.
        GetLayerIndex(layer: Layer) -> int:
            Get index of specified network layer, raise ValueError if layer does not exist.
        AddLayer(layer: Layer) -> None:
            Add a layer of neurons to the network.
        RemoveLayer(layer: Layer) -> None:
            Remove specified layer from network, raise ValueError if layer does not exist.
        ClearAll() -> None:
            Clear all layers and associated resources of the network.
        GetInputLayer() -> InputLayer:
            Get input layer instance of the network, return None if no input layer.
        GetOutputLayer() -> OutputLayer:
            Get output layer instance of the network, return None if no output layer.
        Learn(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            Single backpropagation training, return whether training is successful.
        Test(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            Test model prediction effect, return whether test is successful.
        Predict(inputVectorNNValues: list) -> list:
            Model prediction, return standardized output vector (NNValue list), return None if prediction fails.
        QLearningLearnForChosenAction(stateVectorNNValues: list, rewardNNValue: NNValue, pastStateVectorNNValues: list, chosenActionIndex: int, terminalState=True, discountFactorNNValue=None) -> bool:
            QLearning reinforcement learning training, return whether training is successful.
        QLearningPredictBestActionIndex(stateVectorNNValues: list) -> int:
            QLearning predict optimal action index, return None if prediction fails.
        SaveToFile(filename: str) -> bool:
            Serialize model to JSON file for saving, return whether saving is successful.
        AddExample(inputVectorNNValues: list, targetVectorNNValues: list) -> bool:
            Add training sample to sample list, return whether addition is successful.
        ClearExamples() -> None:
            Clear training sample list.
        LearnExamples(maxSeconds=30, maxCount=None, stopWhenLearned=True, printMAEAverage=True) -> int:
            Batch train samples, return actual training steps, return 0 if training fails.

    Notes:
        - Lightweight design with no third-party dependencies, compatible with embedded MicroPython environment.
        - Activation function derivatives are only used in backpropagation, no need to calculate in forward propagation.
        - Training termination condition can be adjusted via CorrectLearnedMAE, smaller value means higher training accuracy.
        - Model serialization only saves weights/configurations, not training samples.
    """

    ACTFUNC_HEAVISIDE = "Heaviside"
    ACTFUNC_SIGMOID = "Sigmoid"
    ACTFUNC_TANH = "TanH"
    ACTFUNC_SOFTPLUS = "SoftPlus"
    ACTFUNC_RELU = "ReLU"
    ACTFUNC_GAUSSIAN = "Gaussian"

    Eta = 0.30
    Alpha = 0.75
    Gain = 0.99

    CorrectLearnedMAE = 0.02

    # -------------------------------------------------------------------------
    # --( Class : NNValue )----------------------------------------------------
    # -------------------------------------------------------------------------

    class NNValue:
        """
        神经网络数值标准化处理类，将任意范围的数值线性映射到0-1区间，支持百分比、字节、布尔、浮点、模拟信号等多类型的双向转换，适配神经网络输入输出规范。

        Attributes:
            _minValue (float/int): 数值原始最小值（映射到0）。
            _maxValue (float/int): 数值原始最大值（映射到1）。
            _value (float): 标准化后的数值（0-1区间）。
            AsFloat (float): 只读属性，返回反标准化的浮点数值。
            AsInt (int): 只读属性，返回反标准化的整数值（四舍五入）。
            AsPercent (float): 只读属性，返回百分比形式的数值（0-100）。
            AsByte (str): 只读属性，返回字节形式的字符（0-255对应ASCII）。
            AsBool (bool): 只读属性，返回布尔值（>=0.5为True，否则False）。
            AsAnalogSignal (float): 只读属性，返回标准化的模拟信号值（0-1）。

        Methods:
            __init__(minValue: float/int, maxValue: float/int, value: float/int):
                初始化数值标准化实例，数值超出范围自动截断到0/1。
            FromPercent(value: float/int) -> NNValue:
                静态方法，创建百分比数值的标准化实例（0-100映射到0-1）。
            NewPercent() -> NNValue:
                静态方法，创建初始值为0%的标准化实例。
            FromByte(value: str/int) -> NNValue:
                静态方法，创建字节数值的标准化实例（0-255映射到0-1）。
            NewByte() -> NNValue:
                静态方法，创建初始值为0x00的标准化实例。
            FromBool(value: bool) -> NNValue:
                静态方法，创建布尔值的标准化实例（False=0，True=1）。
            NewBool() -> NNValue:
                静态方法，创建初始值为False的标准化实例。
            FromAnalogSignal(value: float/int) -> NNValue:
                静态方法，创建模拟信号的标准化实例（0-1直接赋值）。
            NewAnalogSignal() -> NNValue:
                静态方法，创建初始值为0的模拟信号实例。
            _setScaledValue(minValue: float/int, maxValue: float/int, value: float/int) -> None:
                私有方法，执行数值标准化计算。

        Notes:
            - 初始化时若maxValue <= minValue会抛出Exception异常。
            - 所有属性setter会自动重新标准化数值，保证_value始终在0-1区间。
            - AsByte返回的是字符类型，需通过ord()转换为数值。

        ==========================================

        Neural network value normalization class, linearly maps values of any range to 0-1 interval, supports bidirectional conversion of percentage, byte, boolean, float, analog signal and other types, adapts to neural network input/output specifications.

        Attributes:
            _minValue (float/int): Original minimum value of the number (mapped to 0).
            _maxValue (float/int): Original maximum value of the number (mapped to 1).
            _value (float): Normalized value (0-1 interval).
            AsFloat (float): Read-only property, returns denormalized float value.
            AsInt (int): Read-only property, returns denormalized integer value (rounded).
            AsPercent (float): Read-only property, returns value in percentage form (0-100).
            AsByte (str): Read-only property, returns character in byte form (0-255 corresponding to ASCII).
            AsBool (bool): Read-only property, returns boolean value (True if >=0.5, else False).
            AsAnalogSignal (float): Read-only property, returns normalized analog signal value (0-1).

        Methods:
            __init__(minValue: float/int, maxValue: float/int, value: float/int):
                Initialize value normalization instance, values out of range are automatically truncated to 0/1.
            FromPercent(value: float/int) -> NNValue:
                Static method, create normalized instance of percentage value (0-100 mapped to 0-1).
            NewPercent() -> NNValue:
                Static method, create normalized instance with initial value of 0%.
            FromByte(value: str/int) -> NNValue:
                Static method, create normalized instance of byte value (0-255 mapped to 0-1).
            NewByte() -> NNValue:
                Static method, create normalized instance with initial value of 0x00.
            FromBool(value: bool) -> NNValue:
                Static method, create normalized instance of boolean value (False=0, True=1).
            NewBool() -> NNValue:
                Static method, create normalized instance with initial value of False.
            FromAnalogSignal(value: float/int) -> NNValue:
                Static method, create normalized instance of analog signal (0-1 direct assignment).
            NewAnalogSignal() -> NNValue:
                Static method, create analog signal instance with initial value of 0.
            _setScaledValue(minValue: float/int, maxValue: float/int, value: float/int) -> None:
                Private method, perform value normalization calculation.

        Notes:
            - Exception is raised if maxValue <= minValue during initialization.
            - All property setters automatically re-normalize values to ensure _value is always in 0-1 interval.
            - AsByte returns character type, need to convert to numeric value via ord().
        """

        # -[ Static functions ]---------------------------------

        @staticmethod
        def FromPercent(value):
            return MicroMLP.NNValue(0, 100, value)

        @staticmethod
        def NewPercent():
            return MicroMLP.NNValue.FromPercent(0)

        @staticmethod
        def FromByte(value):
            return MicroMLP.NNValue(0, 255, ord(value))

        @staticmethod
        def NewByte():
            return MicroMLP.NNValue.FromByte(b"\x00")

        @staticmethod
        def FromBool(value):
            return MicroMLP.NNValue(0, 1, 1 if value else 0)

        @staticmethod
        def NewBool():
            return MicroMLP.NNValue.FromBool(False)

        @staticmethod
        def FromAnalogSignal(value):
            return MicroMLP.NNValue(0, 1, value)

        @staticmethod
        def NewAnalogSignal():
            return MicroMLP.NNValue.FromAnalogSignal(0)

        # -[ Constructor ]--------------------------------------

        def __init__(self, minValue, maxValue, value):
            if maxValue - minValue <= 0:
                raise Exception('MicroMLP.NNValue : "maxValue" must be greater than "minValue".')
            self._minValue = minValue
            self._maxValue = maxValue
            self._value = 0.0
            self._setScaledValue(minValue, maxValue, value)

        # -[ Private functions ]--------------------------------

        def _setScaledValue(self, minValue, maxValue, value):
            if value <= minValue:
                self._value = 0.0
            elif value >= maxValue:
                self._value = 1.0
            else:
                self._value = float(value - minValue) / (maxValue - minValue)

        # -[ Properties ]---------------------------------------

        @property
        def AsFloat(self):
            return self._minValue + (self._value * (self._maxValue - self._minValue))

        @AsFloat.setter
        def AsFloat(self, value):
            self._setScaledValue(self._minValue, self._maxValue, value)

        @property
        def AsInt(self):
            return int(round(self.AsFloat))

        @AsInt.setter
        def AsInt(self, value):
            self._setScaledValue(self._minValue, self._maxValue, value)

        @property
        def AsPercent(self):
            return self._value * 100

        @AsPercent.setter
        def AsPercent(self, value):
            self._setScaledValue(0, 100, value)

        @property
        def AsByte(self):
            return chr(int(round(self._value * 255)))

        @AsByte.setter
        def AsByte(self, value):
            self._setScaledValue(0, 255, ord(value))

        @property
        def AsBool(self):
            return self._value >= 0.5

        @AsBool.setter
        def AsBool(self, value):
            self._setScaledValue(0, 1, 1 if value else 0)

        @property
        def AsAnalogSignal(self):
            return self._value

        @AsAnalogSignal.setter
        def AsAnalogSignal(self, value):
            self._setScaledValue(0, 1, value)

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : Connection )-------------------------------------------------
    # -------------------------------------------------------------------------

    class Connection:
        """
        神经元连接类，维护源神经元与目标神经元间的连接权重，实现反向传播中的权重更新（含动量项），并支持连接的安全移除与关联清理。

        Attributes:
            _neuronSrc (MicroMLP.Neuron): 输出信号的源神经元实例。
            _neuronDst (MicroMLP.Neuron): 接收信号的目标神经元实例。
            _weight (float): 连接权重值（默认-0.35~0.35随机生成）。
            _momentumDeltaWeight (float): 动量项权重增量，默认0.0。
            NeuronSrc (MicroMLP.Neuron): 只读属性，返回源神经元实例。
            NeuronDst (MicroMLP.Neuron): 只读属性，返回目标神经元实例。
            Weight (float): 只读属性，返回当前连接权重值。

        Methods:
            __init__(neuronSrc: MicroMLP.Neuron, neuronDst: MicroMLP.Neuron, weight=None):
                初始化神经元连接，自动注册到源/目标神经元的连接列表。
            UpdateWeight(eta: float, alpha: float) -> None:
                根据反向传播误差更新连接权重，包含动量项计算。
            Remove() -> None:
                安全移除连接，清理与源/目标神经元的双向关联。

        Notes:
            - 权重更新公式：new_weight = weight + eta*dst_error*src_output + alpha*momentumDeltaWeight。
            - Remove方法会将_neuronSrc/_neuronDst置为None，防止悬空引用。
            - 初始化时若未指定weight，将调用RandomNetworkWeight()生成随机值。

        ==========================================

        Neuron connection class, maintains connection weight between source neuron and target neuron, implements weight update (including momentum term) in backpropagation, and supports safe removal and association cleanup of connections.

        Attributes:
            _neuronSrc (MicroMLP.Neuron): Source neuron instance that outputs signals.
            _neuronDst (MicroMLP.Neuron): Target neuron instance that receives signals.
            _weight (float): Connection weight value (randomly generated between -0.35~0.35 by default).
            _momentumDeltaWeight (float): Momentum term weight increment, default 0.0.
            NeuronSrc (MicroMLP.Neuron): Read-only property, returns source neuron instance.
            NeuronDst (MicroMLP.Neuron): Read-only property, returns target neuron instance.
            Weight (float): Read-only property, returns current connection weight value.

        Methods:
            __init__(neuronSrc: MicroMLP.Neuron, neuronDst: MicroMLP.Neuron, weight=None):
                Initialize neuron connection, automatically register to connection lists of source/target neurons.
            UpdateWeight(eta: float, alpha: float) -> None:
                Update connection weight according to backpropagation error, including momentum term calculation.
            Remove() -> None:
                Safely remove connection, clean up bidirectional association with source/target neurons.

        Notes:
            - Weight update formula: new_weight = weight + eta*dst_error*src_output + alpha*momentumDeltaWeight.
            - Remove method sets _neuronSrc/_neuronDst to None to prevent dangling references.
            - If weight is not specified during initialization, RandomNetworkWeight() is called to generate random value.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, neuronSrc, neuronDst, weight=None):
            neuronSrc.AddOutputConnection(self)
            neuronDst.AddInputConnection(self)
            self._neuronSrc = neuronSrc
            self._neuronDst = neuronDst
            self._weight = weight if weight else MicroMLP.RandomNetworkWeight()
            self._momentumDeltaWeight = 0.0

        # -[ Public functions ]---------------------------------

        def UpdateWeight(self, eta, alpha):
            deltaWeight = eta * self._neuronSrc.ComputedOutput * self._neuronDst.ComputedSignalError
            self._weight += deltaWeight + (alpha * self._momentumDeltaWeight)
            self._momentumDeltaWeight = deltaWeight

        def Remove(self):
            if self._neuronSrc and self._neuronDst:
                nSrc = self._neuronSrc
                nDst = self._neuronDst
                self._neuronSrc = None
                self._neuronDst = None
                nSrc.RemoveOutputConnection(self)
                nDst.RemoveInputConnection(self)

        # -[ Properties ]---------------------------------------

        @property
        def NeuronSrc(self):
            return self._neuronSrc

        @property
        def NeuronDst(self):
            return self._neuronDst

        @property
        def Weight(self):
            return self._weight

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : Neuron )-----------------------------------------------------
    # -------------------------------------------------------------------------

    class Neuron:
        """
        神经网络神经元核心类，管理输入/输出连接列表与偏置项，实现输入加权和计算、激活函数输出、误差反向传播计算，支持神经元的安全移除与资源清理。

        Attributes:
            _parentLayer (MicroMLP.Layer): 神经元所属的网络层实例。
            _inputConnections (list): 输入连接列表（Connection实例）。
            _outputConnections (list): 输出连接列表（Connection实例）。
            _inputBias (MicroMLP.Bias): 神经元偏置项实例，默认None。
            _computedInput (float): 输入加权和（含偏置），默认0.0。
            _computedOutput (float): 激活函数输出值，默认0.0。
            _computedDeltaError (float): 预测误差值，默认0.0。
            _computedSignalError (float): 信号误差值（用于权重更新），默认0.0。
            ParentLayer (MicroMLP.Layer): 只读属性，返回所属网络层实例。
            ComputedOutput (float): 只读属性，返回当前输出值。
            ComputedDeltaError (float): 只读属性，返回当前预测误差值。
            ComputedSignalError (float): 只读属性，返回当前信号误差值。

        Methods:
            __init__(parentLayer: MicroMLP.Layer):
                初始化神经元实例，自动注册到所属网络层的神经元列表。
            GetNeuronIndex() -> int:
                获取神经元在所属层中的索引。
            GetInputConnections() -> list:
                返回输入连接列表的副本，防止外部修改。
            GetOutputConnections() -> list:
                返回输出连接列表的副本，防止外部修改。
            AddInputConnection(connection: Connection) -> None:
                添加输入连接到列表。
            AddOutputConnection(connection: Connection) -> None:
                添加输出连接到列表。
            RemoveInputConnection(connection: Connection) -> None:
                从输入连接列表移除指定连接。
            RemoveOutputConnection(connection: Connection) -> None:
                从输出连接列表移除指定连接。
            SetBias(bias: MicroMLP.Bias) -> None:
                设置神经元偏置项。
            GetBias() -> MicroMLP.Bias:
                返回当前偏置项实例，无偏置返回None。
            SetOutputNNValue(nnvalue: NNValue) -> None:
                直接设置神经元输出值（用于输入层）。
            _computeInput() -> None:
                私有方法，计算输入加权和（含偏置项）。
            ComputeOutput() -> None:
                计算激活函数输出值，更新_computedOutput。
            ComputeError(targetNNValue=None) -> None:
                计算预测误差和信号误差，更新_deltaError/_signalError。
            Remove() -> None:
                安全移除神经元，清理所有连接、偏置及与层的关联。

        Notes:
            - _computeInput会遍历所有输入连接计算加权和，若有偏置则加上bias.value*bias.weight。
            - ComputeError在有targetNNValue时计算预测误差，无则累加下游神经元的信号误差。
            - Remove方法会递归清理所有关联连接和偏置，防止内存泄漏。

        ==========================================

        Neural network neuron core class, manages input/output connection lists and bias term, implements input weighted sum calculation, activation function output, error backpropagation calculation, and supports safe removal and resource cleanup of neurons.

        Attributes:
            _parentLayer (MicroMLP.Layer): Network layer instance to which the neuron belongs.
            _inputConnections (list): Input connection list (Connection instances).
            _outputConnections (list): Output connection list (Connection instances).
            _inputBias (MicroMLP.Bias): Neuron bias term instance, default None.
            _computedInput (float): Input weighted sum (including bias), default 0.0.
            _computedOutput (float): Activation function output value, default 0.0.
            _computedDeltaError (float): Prediction error value, default 0.0.
            _computedSignalError (float): Signal error value (used for weight update), default 0.0.
            ParentLayer (MicroMLP.Layer): Read-only property, returns the affiliated network layer instance.
            ComputedOutput (float): Read-only property, returns current output value.
            ComputedDeltaError (float): Read-only property, returns current prediction error value.
            ComputedSignalError (float): Read-only property, returns current signal error value.

        Methods:
            __init__(parentLayer: MicroMLP.Layer):
                Initialize neuron instance, automatically register to neuron list of the affiliated network layer.
            GetNeuronIndex() -> int:
                Get index of the neuron in its affiliated layer.
            GetInputConnections() -> list:
                Return a copy of input connection list to prevent external modification.
            GetOutputConnections() -> list:
                Return a copy of output connection list to prevent external modification.
            AddInputConnection(connection: Connection) -> None:
                Add input connection to the list.
            AddOutputConnection(connection: Connection) -> None:
                Add output connection to the list.
            RemoveInputConnection(connection: Connection) -> None:
                Remove specified connection from input connection list.
            RemoveOutputConnection(connection: Connection) -> None:
                Remove specified connection from output connection list.
            SetBias(bias: MicroMLP.Bias) -> None:
                Set neuron bias term.
            GetBias() -> MicroMLP.Bias:
                Return current bias term instance, return None if no bias.
            SetOutputNNValue(nnvalue: NNValue) -> None:
                Directly set neuron output value (used for input layer).
            _computeInput() -> None:
                Private method, calculate input weighted sum (including bias term).
            ComputeOutput() -> None:
                Calculate activation function output value, update _computedOutput.
            ComputeError(targetNNValue=None) -> None:
                Calculate prediction error and signal error, update _deltaError/_signalError.
            Remove() -> None:
                Safely remove neuron, clean up all connections, biases and association with layer.

        Notes:
            - _computeInput iterates all input connections to calculate weighted sum, adds bias.value*bias.weight if bias exists.
            - ComputeError calculates prediction error when targetNNValue is provided, otherwise accumulates signal errors of downstream neurons.
            - Remove method recursively cleans up all associated connections and biases to prevent memory leaks.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, parentLayer):
            parentLayer.AddNeuron(self)
            self._parentLayer = parentLayer
            self._inputConnections = []
            self._outputConnections = []
            self._inputBias = None
            self._computedInput = 0.0
            self._computedOutput = 0.0
            self._computedDeltaError = 0.0
            self._computedSignalError = 0.0

        # -[ Public functions ]---------------------------------

        def GetNeuronIndex(self):
            return self._parentLayer.GetNeuronIndex(self)

        def GetInputConnections(self):
            return self._inputConnections

        def GetOutputConnections(self):
            return self._outputConnections

        def AddInputConnection(self, connection):
            self._inputConnections.append(connection)

        def AddOutputConnection(self, connection):
            self._outputConnections.append(connection)

        def RemoveInputConnection(self, connection):
            self._inputConnections.remove(connection)

        def RemoveOutputConnection(self, connection):
            self._outputConnections.remove(connection)

        def SetBias(self, bias):
            self._inputBias = bias

        def GetBias(self):
            return self._inputBias

        def SetOutputNNValue(self, nnvalue):
            self._computedOutput = nnvalue.AsAnalogSignal

        def _computeInput(self):
            sum = 0.0
            for conn in self._inputConnections:
                sum += conn.NeuronSrc.ComputedOutput * conn.Weight
            if self._inputBias:
                sum += self._inputBias.Value * self._inputBias.Weight
            self._computedInput = sum

        def ComputeOutput(self):
            self._computeInput()
            if self._parentLayer._actFunc:
                self._computedOutput = self._parentLayer._actFunc(self._computedInput * self._parentLayer.ParentMicroMLP.Gain)

        def ComputeError(self, targetNNValue=None):
            if targetNNValue:
                self._computedDeltaError = targetNNValue.AsAnalogSignal - self.ComputedOutput
            else:
                self._computedDeltaError = 0.0
                for conn in self._outputConnections:
                    self._computedDeltaError += conn.NeuronDst.ComputedSignalError * conn.Weight
            if self._parentLayer._actFunc:
                self._computedSignalError = (
                    self._computedDeltaError
                    * self._parentLayer.ParentMicroMLP.Gain
                    * self._parentLayer._actFunc(self._computedInput, derivative=True)
                )

        def Remove(self):
            for conn in self._inputConnections:
                conn.NeuronSrc.RemoveOutputConnection(conn)
            for conn in self._outputConnections:
                conn.NeuronDst.RemoveInputConnection(conn)
            l = self._parentLayer
            self._parentLayer = None
            l.RemoveNeuron(self)

        # -[ Properties ]---------------------------------------

        @property
        def ParentLayer(self):
            return self._parentLayer

        @property
        def ComputedOutput(self):
            return self._computedOutput

        @property
        def ComputedDeltaError(self):
            return self._computedDeltaError

        @property
        def ComputedSignalError(self):
            return self._computedSignalError

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : Bias )-------------------------------------------------------
    # -------------------------------------------------------------------------

    class Bias:
        """
        神经元偏置项类，为神经元添加固定偏置值并维护偏置权重，实现反向传播中的偏置权重更新（含动量项），支持偏置项的安全移除与关联清理。

        Attributes:
            _neuronDst (MicroMLP.Neuron): 关联的目标神经元实例。
            _value (float): 偏置固定值，默认1.0。
            _weight (float): 偏置权重值（默认-0.35~0.35随机生成）。
            _momentumDeltaWeight (float): 动量项权重增量，默认0.0。
            NeuronDst (MicroMLP.Neuron): 只读属性，返回目标神经元实例。
            Value (float): 只读属性，返回偏置固定值。
            Weight (float): 只读属性，返回当前偏置权重值。

        Methods:
            __init__(neuronDst: MicroMLP.Neuron, value=1.0, weight=None):
                初始化偏置项，自动注册到目标神经元的偏置属性。
            UpdateWeight(eta: float, alpha: float) -> None:
                根据反向传播误差更新偏置权重，包含动量项计算。
            Remove() -> None:
                安全移除偏置项，清理与目标神经元的关联。

        Notes:
            - 偏置权重更新规则与Connection完全一致，仅输入固定为_value（默认1.0）。
            - Remove方法会调用目标神经元的SetBias(None)，解除双向关联。
            - 初始化时若未指定weight，将调用RandomNetworkWeight()生成随机值。

        ==========================================

        Neuron bias term class, adds fixed bias value to neuron and maintains bias weight, implements bias weight update (including momentum term) in backpropagation, and supports safe removal and association cleanup of bias term.

        Attributes:
            _neuronDst (MicroMLP.Neuron): Associated target neuron instance.
            _value (float): Fixed bias value, default 1.0.
            _weight (float): Bias weight value (randomly generated between -0.35~0.35 by default).
            _momentumDeltaWeight (float): Momentum term weight increment, default 0.0.
            NeuronDst (MicroMLP.Neuron): Read-only property, returns target neuron instance.
            Value (float): Read-only property, returns fixed bias value.
            Weight (float): Read-only property, returns current bias weight value.

        Methods:
            __init__(neuronDst: MicroMLP.Neuron, value=1.0, weight=None):
                Initialize bias term, automatically register to bias property of target neuron.
            UpdateWeight(eta: float, alpha: float) -> None:
                Update bias weight according to backpropagation error, including momentum term calculation.
            Remove() -> None:
                Safely remove bias term, clean up association with target neuron.

        Notes:
            - Bias weight update rule is exactly the same as Connection, only input is fixed to _value (1.0 by default).
            - Remove method calls SetBias(None) of target neuron to release bidirectional association.
            - If weight is not specified during initialization, RandomNetworkWeight() is called to generate random value.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, neuronDst, value=1.0, weight=None):
            neuronDst.SetBias(self)
            self._neuronDst = neuronDst
            self._value = value
            self._weight = weight if weight else MicroMLP.RandomNetworkWeight()
            self._momentumDeltaWeight = 0.0

        # -[ Public functions ]---------------------------------

        def UpdateWeight(self, eta, alpha):
            deltaWeight = eta * self._value * self._neuronDst.ComputedSignalError
            self._weight += deltaWeight + (alpha * self._momentumDeltaWeight)
            self._momentumDeltaWeight = deltaWeight

        def Remove(self):
            self._neuronDst.SetBias(None)

        # -[ Properties ]---------------------------------------

        @property
        def NeuronDst(self):
            return self._neuronDst

        @property
        def Value(self):
            return self._value

        @property
        def Weight(self):
            return self._weight

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : Layer )------------------------------------------------------
    # -------------------------------------------------------------------------

    class Layer:
        """
        神经网络层基类，管理层内神经元集合，提供神经元增删、索引查询、数量统计功能，支持层级均方误差(MSE)、平均绝对误差(MAE)计算及层的安全移除。

        Attributes:
            _parentMicroMLP (MicroMLP): 所属的MLP主实例。
            _actFuncName (str): 激活函数名称，默认None（无激活）。
            _actFunc (function): 激活函数实例（含导数支持），默认None。
            _neurons (list): 层内神经元列表（Neuron实例）。
            ParentMicroMLP (MicroMLP): 只读属性，返回所属MLP主实例。
            ActivationFuncName (str): 只读属性，返回激活函数名称。
            Neurons (list): 只读属性，返回神经元列表的副本。
            NeuronsCount (int): 只读属性，返回层内神经元数量。

        Methods:
            __init__(parentMicroMLP: MicroMLP, activationFuncName=None, neuronsCount=0):
                初始化网络层，自动创建指定数量的神经元并注册到MLP。
            GetLayerIndex() -> int:
                获取当前层在MLP中的索引。
            GetNeuron(neuronIndex: int) -> MicroMLP.Neuron:
                获取指定索引的神经元实例，索引无效返回None。
            GetNeuronIndex(neuron: MicroMLP.Neuron) -> int:
                获取指定神经元在层中的索引，神经元不存在抛出ValueError。
            AddNeuron(neuron: MicroMLP.Neuron) -> None:
                向层中添加神经元实例。
            RemoveNeuron(neuron: MicroMLP.Neuron) -> None:
                从层中移除指定神经元实例。
            GetMeanSquareError() -> float:
                计算层内所有神经元的均方误差(MSE)，无神经元返回0。
            GetMeanAbsoluteError() -> float:
                计算层内所有神经元的平均绝对误差(MAE)，无神经元返回0。
            GetMeanSquareErrorAsPercent() -> float:
                返回百分比形式的MSE（保留三位小数）。
            GetMeanAbsoluteErrorAsPercent() -> float:
                返回百分比形式的MAE（保留三位小数）。
            Remove() -> None:
                安全移除网络层，递归清理所有神经元及关联资源。

        Notes:
            - 无激活函数时，ComputeOutput直接将_computedInput赋值给_computedOutput。
            - 误差计算基于神经元的_computedDeltaError，仅在反向传播后有效。
            - Remove方法会将_parentMicroMLP置为None，防止悬空引用。

        ==========================================

        Neural network layer base class, manages neuron set in the layer, provides neuron add/delete, index query, quantity statistics functions, supports layer-level Mean Squared Error (MSE), Mean Absolute Error (MAE) calculation and safe removal of the layer.

        Attributes:
            _parentMicroMLP (MicroMLP): Affiliated MLP main instance.
            _actFuncName (str): Activation function name, default None (no activation).
            _actFunc (function): Activation function instance (with derivative support), default None.
            _neurons (list): List of neurons in the layer (Neuron instances).
            ParentMicroMLP (MicroMLP): Read-only property, returns affiliated MLP main instance.
            ActivationFuncName (str): Read-only property, returns activation function name.
            Neurons (list): Read-only property, returns a copy of neuron list.
            NeuronsCount (int): Read-only property, returns number of neurons in the layer.

        Methods:
            __init__(parentMicroMLP: MicroMLP, activationFuncName=None, neuronsCount=0):
                Initialize network layer, automatically create specified number of neurons and register to MLP.
            GetLayerIndex() -> int:
                Get index of current layer in MLP.
            GetNeuron(neuronIndex: int) -> MicroMLP.Neuron:
                Get neuron instance by index, return None if index is invalid.
            GetNeuronIndex(neuron: MicroMLP.Neuron) -> int:
                Get index of specified neuron in the layer, raise ValueError if neuron does not exist.
            AddNeuron(neuron: MicroMLP.Neuron) -> None:
                Add neuron instance to the layer.
            RemoveNeuron(neuron: MicroMLP.Neuron) -> None:
                Remove specified neuron instance from the layer.
            GetMeanSquareError() -> float:
                Calculate Mean Squared Error (MSE) of all neurons in the layer, return 0 if no neurons.
            GetMeanAbsoluteError() -> float:
                Calculate Mean Absolute Error (MAE) of all neurons in the layer, return 0 if no neurons.
            GetMeanSquareErrorAsPercent() -> float:
                Return MSE in percentage form (keep three decimal places).
            GetMeanAbsoluteErrorAsPercent() -> float:
                Return MAE in percentage form (keep three decimal places).
            Remove() -> None:
                Safely remove network layer, recursively clean up all neurons and associated resources.

        Notes:
            - When no activation function is set, ComputeOutput directly assigns _computedInput to _computedOutput.
            - Error calculation is based on _computedDeltaError of neurons, only valid after backpropagation.
            - Remove method sets _parentMicroMLP to None to prevent dangling references.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, parentMicroMLP, activationFuncName=None, neuronsCount=0):
            self._parentMicroMLP = parentMicroMLP
            self._actFuncName = activationFuncName
            self._actFunc = MicroMLP.GetActivationFunction(activationFuncName)
            self._neurons = []
            self._parentMicroMLP.AddLayer(self)
            for i in range(neuronsCount):
                MicroMLP.Neuron(self)

        # -[ Public functions ]---------------------------------

        def GetLayerIndex(self):
            return self._parentMicroMLP.GetLayerIndex(self)

        def GetNeuron(self, neuronIndex):
            if neuronIndex >= 0 and neuronIndex < len(self._neurons):
                return self._neurons[neuronIndex]
            return None

        def GetNeuronIndex(self, neuron):
            return self._neurons.index(neuron)

        def AddNeuron(self, neuron):
            self._neurons.append(neuron)

        def RemoveNeuron(self, neuron):
            self._neurons.remove(neuron)

        def GetMeanSquareError(self):
            if len(self._neurons) == 0:
                return 0
            mse = 0.0
            for n in self._neurons:
                mse += n.ComputedDeltaError**2
            return mse / len(self._neurons)

        def GetMeanAbsoluteError(self):
            if len(self._neurons) == 0:
                return 0
            mae = 0.0
            for n in self._neurons:
                mae += abs(n.ComputedDeltaError)
            return mae / len(self._neurons)

        def GetMeanSquareErrorAsPercent(self):
            return round(self.GetMeanSquareError() * 100 * 1000) / 1000

        def GetMeanAbsoluteErrorAsPercent(self):
            return round(self.GetMeanAbsoluteError() * 100 * 1000) / 1000

        def Remove(self):
            while len(self._neurons) > 0:
                self._neurons[0].Remove()
            mlp = self._parentMicroMLP
            self._parentMicroMLP = None
            mlp.RemoveLayer(self)

        # -[ Properties ]---------------------------------------

        @property
        def ParentMicroMLP(self):
            return self._parentMicroMLP

        @property
        def ActivationFuncName(self):
            return self._actFuncName

        @property
        def Neurons(self):
            return self._neurons

        @property
        def NeuronsCount(self):
            return len(self._neurons)

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : InputLayer )-------------------------------------------------
    # -------------------------------------------------------------------------

    class InputLayer(Layer):
        """
        神经网络输入层类（继承Layer），无激活函数，专用于接收并分发输入数据到后续网络层，提供输入向量校验与设置接口。

        Attributes:
            继承Layer类的所有属性，无额外属性。

        Methods:
            __init__(parentMicroMLP: MicroMLP, neuronsCount=0):
                初始化输入层，激活函数固定为None，创建指定数量的输入神经元。
            SetInputVectorNNValues(inputVectorNNValues: list) -> bool:
                设置输入向量，将标准化数值分配到对应神经元，返回设置是否成功。

        Notes:
            - 输入神经元数量必须与输入特征维度一致，否则SetInputVectorNNValues返回False。
            - 输入层神经元的输出值通过SetOutputNNValue直接设置，无需计算。
            - 继承自Layer的Remove方法已适配输入层的资源清理逻辑。

        ==========================================

        Neural network input layer class (inherits Layer), no activation function, dedicated to receiving and distributing input data to subsequent network layers, provides input vector verification and setting interface.

        Attributes:
            Inherits all attributes of Layer class, no additional attributes.

        Methods:
            __init__(parentMicroMLP: MicroMLP, neuronsCount=0):
                Initialize input layer, activation function is fixed to None, create specified number of input neurons.
            SetInputVectorNNValues(inputVectorNNValues: list) -> bool:
                Set input vector, assign normalized values to corresponding neurons, return whether setting is successful.

        Notes:
            - The number of input neurons must match the input feature dimension, otherwise SetInputVectorNNValues returns False.
            - Output values of input layer neurons are directly set via SetOutputNNValue without calculation.
            - The Remove method inherited from Layer has adapted to the resource cleanup logic of input layer.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, parentMicroMLP, neuronsCount=0):
            super().__init__(parentMicroMLP, None, neuronsCount)

        # -[ Public functions ]---------------------------------

        def SetInputVectorNNValues(self, inputVectorNNValues):
            if len(inputVectorNNValues) == self.NeuronsCount:
                for i in range(self.NeuronsCount):
                    self._neurons[i].SetOutputNNValue(inputVectorNNValues[i])
                return True
            return False

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # --( Class : OutputLayer )------------------------------------------------
    # -------------------------------------------------------------------------

    class OutputLayer(Layer):
        """
        神经网络输出层类（继承Layer），配置激活函数生成预测结果，计算预测值与目标值的误差，提供标准化输出向量的获取接口。

        Attributes:
            继承Layer类的所有属性，无额外属性。

        Methods:
            __init__(parentMicroMLP: MicroMLP, activationFuncName: str, neuronsCount=0):
                初始化输出层，指定激活函数并创建指定数量的输出神经元。
            GetOutputVectorNNValues() -> list:
                获取输出向量，返回各神经元输出值的标准化实例（NNValue列表）。
            ComputeTargetLayerError(targetVectorNNValues: list) -> bool:
                计算输出层误差，分配目标值到对应神经元并计算DeltaError，返回计算是否成功。

        Notes:
            - 激活函数名称必须匹配MicroMLP的激活函数常量，否则无激活效果。
            - 输出神经元数量必须与预测目标维度一致，否则ComputeTargetLayerError返回False。
            - GetOutputVectorNNValues返回的是标准化数值，需通过AsFloat/AsInt等属性还原实际值。

        ==========================================

        Neural network output layer class (inherits Layer), configures activation function to generate prediction results, calculates error between predicted and target values, provides interface to get standardized output vector.

        Attributes:
            Inherits all attributes of Layer class, no additional attributes.

        Methods:
            __init__(parentMicroMLP: MicroMLP, activationFuncName: str, neuronsCount=0):
                Initialize output layer, specify activation function and create specified number of output neurons.
            GetOutputVectorNNValues() -> list:
                Get output vector, return normalized instances of output values of each neuron (NNValue list).
            ComputeTargetLayerError(targetVectorNNValues: list) -> bool:
                Calculate output layer error, assign target values to corresponding neurons and calculate DeltaError, return whether calculation is successful.

        Notes:
            - Activation function name must match the activation function constants of MicroMLP, otherwise no activation effect.
            - The number of output neurons must match the prediction target dimension, otherwise ComputeTargetLayerError returns False.
            - Values returned by GetOutputVectorNNValues are normalized, need to restore actual values via AsFloat/AsInt and other properties.
        """

        # -[ Constructor ]--------------------------------------

        def __init__(self, parentMicroMLP, activationFuncName, neuronsCount=0):
            super().__init__(parentMicroMLP, activationFuncName, neuronsCount)

        # -[ Public functions ]---------------------------------

        def GetOutputVectorNNValues(self):
            nnvalues = []
            for n in self._neurons:
                nnvalues.append(MicroMLP.NNValue.FromAnalogSignal(n.ComputedOutput))
            return nnvalues

        def ComputeTargetLayerError(self, targetVectorNNValues):
            if len(targetVectorNNValues) == self.NeuronsCount:
                for i in range(self.NeuronsCount):
                    self._neurons[i].ComputeError(targetVectorNNValues[i])
                return True
            return False

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    # -[ Constructor ]--------------------------------------

    def __init__(self):
        self._layers = []
        self._examples = []

    # -[ Static functions ]-------------------------------------

    @staticmethod
    def Create(neuronsByLayers, activationFuncName, layersAutoConnectFunction=None, useBiasValue=1.0):
        if not neuronsByLayers or len(neuronsByLayers) < 2:
            raise Exception('MicroMLP.Create : Incorrect "neuronsByLayers" parameter.')
        for x in neuronsByLayers:
            if x < 1:
                raise Exception('MicroMLP.Create : Incorrect count in "neuronsByLayers".')
        if not MicroMLP.GetActivationFunction(activationFuncName):
            raise Exception('MicroMLP : Unknow activationFuncName "%s".' % activationFuncName)
        mlp = MicroMLP()
        for i in range(len(neuronsByLayers)):
            if i == 0:
                layer = MicroMLP.InputLayer(mlp, neuronsByLayers[i])
            else:
                if i == len(neuronsByLayers) - 1:
                    layer = MicroMLP.OutputLayer(mlp, activationFuncName, neuronsByLayers[i])
                else:
                    layer = MicroMLP.Layer(mlp, activationFuncName, neuronsByLayers[i])
                if layersAutoConnectFunction:
                    layersAutoConnectFunction(mlp.GetLayer(i - 1), layer)
                if useBiasValue:
                    for n in layer.Neurons:
                        MicroMLP.Bias(n, useBiasValue)
        return mlp

    @staticmethod
    def RandomFloat():
        if "rng" in globals():
            return rng() / (2**24)
        return random()

    @staticmethod
    def RandomNetworkWeight():
        return (MicroMLP.RandomFloat() - 0.5) * 0.7

    @staticmethod
    def HeavisideActivation(x, derivative=False):
        if derivative:
            return 1.0
        return 1.0 if x >= 0 else 0.0

    @staticmethod
    def SigmoidActivation(x, derivative=False):
        f = 1.0 / (1.0 + exp(-x))
        if derivative:
            return f * (1.0 - f)
        return f

    @staticmethod
    def TanHActivation(x, derivative=False):
        f = (2.0 / (1.0 + exp(-2.0 * x))) - 1.0
        if derivative:
            return 1.0 - (f**2)
        return f

    @staticmethod
    def SoftPlusActivation(x, derivative=False):
        if derivative:
            return 1 / (1 + exp(-x))
        return log(1 + exp(x))

    @staticmethod
    def ReLUActivation(x, derivative=False):
        if derivative:
            return 1.0 if x >= 0 else 0.0
        return max(0.0, x)

    @staticmethod
    def GaussianActivation(x, derivative=False):
        f = exp(-(x**2))
        if derivative:
            return -2 * x * f
        return f

    @staticmethod
    def LayersFullConnect(layerSrc, layerDst):
        if layerSrc and layerDst and layerSrc != layerDst:
            for nSrc in layerSrc.Neurons:
                for nDst in layerDst.Neurons:
                    MicroMLP.Connection(nSrc, nDst)

    @staticmethod
    def GetActivationFunction(actFuncName):
        if actFuncName:
            funcs = {
                MicroMLP.ACTFUNC_HEAVISIDE: MicroMLP.HeavisideActivation,
                MicroMLP.ACTFUNC_SIGMOID: MicroMLP.SigmoidActivation,
                MicroMLP.ACTFUNC_TANH: MicroMLP.TanHActivation,
                MicroMLP.ACTFUNC_SOFTPLUS: MicroMLP.SoftPlusActivation,
                MicroMLP.ACTFUNC_RELU: MicroMLP.ReLUActivation,
                MicroMLP.ACTFUNC_GAUSSIAN: MicroMLP.GaussianActivation,
            }
            if actFuncName in funcs:
                return funcs[actFuncName]
        return None

    @staticmethod
    def LoadFromFile(filename):
        with open(filename, "r") as jsonFile:
            o = load(jsonFile)
        mlp = MicroMLP()
        mlp.Eta = o["Eta"]
        mlp.Alpha = o["Alpha"]
        mlp.Gain = o["Gain"]
        oLayers = o["Layers"]
        for i in range(len(oLayers)):
            oLayer = oLayers[i]
            activationFuncName = oLayer["Func"]
            oNeurons = oLayer["Neurons"]
            if i == 0:
                layer = MicroMLP.InputLayer(mlp, len(oNeurons))
            else:
                if i == len(oLayers) - 1:
                    layer = MicroMLP.OutputLayer(mlp, activationFuncName, len(oNeurons))
                else:
                    layer = MicroMLP.Layer(mlp, activationFuncName, len(oNeurons))
            for neuron in layer.Neurons:
                oNeuron = oNeurons[neuron.GetNeuronIndex()]
                oBias = oNeuron["Bias"]
                if oBias:
                    MicroMLP.Bias(neuron, oBias["Val"], oBias["Wght"])
                for oConn in oNeuron["Conn"]:
                    nSrc = mlp.GetLayer(oConn["LSrc"]).GetNeuron(oConn["NSrc"])
                    MicroMLP.Connection(nSrc, neuron, oConn["Wght"])
        return mlp

    # -[ Public functions ]---------------------------------

    def GetLayer(self, layerIndex):
        if layerIndex >= 0 and layerIndex < len(self._layers):
            return self._layers[layerIndex]
        return None

    def GetLayerIndex(self, layer):
        return self._layers.index(layer)

    def AddLayer(self, layer):
        self._layers.append(layer)

    def RemoveLayer(self, layer):
        self._layers.remove(layer)

    def ClearAll(self):
        while len(self._layers) > 0:
            self._layers[0].Remove()

    def GetInputLayer(self):
        if self.LayersCount > 0:
            l = self._layers[0]
            if type(l) is MicroMLP.InputLayer:
                return l
        return None

    def GetOutputLayer(self):
        if self.LayersCount > 0:
            l = self._layers[self.LayersCount - 1]
            if type(l) is MicroMLP.OutputLayer:
                return l
        return None

    def Learn(self, inputVectorNNValues, targetVectorNNValues):
        if targetVectorNNValues:
            return self._simulate(inputVectorNNValues, targetVectorNNValues, True)
        return False

    def Test(self, inputVectorNNValues, targetVectorNNValues):
        if targetVectorNNValues:
            return self._simulate(inputVectorNNValues, targetVectorNNValues)
        return False

    def Predict(self, inputVectorNNValues):
        if self._simulate(inputVectorNNValues):
            return self.GetOutputLayer().GetOutputVectorNNValues()
        return None

    def QLearningLearnForChosenAction(
        self, stateVectorNNValues, rewardNNValue, pastStateVectorNNValues, chosenActionIndex, terminalState=True, discountFactorNNValue=None
    ):
        if chosenActionIndex >= 0 and chosenActionIndex < self.GetOutputLayer().NeuronsCount:
            if not terminalState:
                if not discountFactorNNValue or not self._simulate(stateVectorNNValues):
                    return False
                bestActVal = 0
                for nnVal in self.GetOutputLayer().GetOutputVectorNNValues():
                    if nnVal.AsAnalogSignal > bestActVal:
                        bestActVal = nnVal.AsAnalogSignal
            if self._simulate(pastStateVectorNNValues):
                targetVectorNNValues = self.GetOutputLayer().GetOutputVectorNNValues()
                targetActVal = rewardNNValue.AsAnalogSignal
                if not terminalState:
                    targetActVal += discountFactorNNValue.AsAnalogSignal * bestActVal
                targetVectorNNValues[chosenActionIndex].AsAnalogSignal = targetActVal
                return self._simulate(pastStateVectorNNValues, targetVectorNNValues, True)
        return False

    def QLearningPredictBestActionIndex(self, stateVectorNNValues):
        bestActIdx = None
        if self._simulate(stateVectorNNValues):
            maxVal = 0
            idx = 0
            for nnVal in self.GetOutputLayer().GetOutputVectorNNValues():
                if nnVal.AsAnalogSignal > maxVal:
                    maxVal = nnVal.AsAnalogSignal
                    bestActIdx = idx
                idx += 1
        return bestActIdx

    def SaveToFile(self, filename):
        o = {"Eta": self.Eta, "Alpha": self.Alpha, "Gain": self.Gain, "Layers": []}
        for layer in self.Layers:
            oLayer = {"Func": layer.ActivationFuncName, "Neurons": []}
            for neuron in layer.Neurons:
                bias = neuron.GetBias()
                if bias:
                    oBias = {"Val": bias.Value, "Wght": bias.Weight}
                else:
                    oBias = None
                oNeuron = {"Bias": oBias, "Conn": []}
                for conn in neuron.GetInputConnections():
                    oNeuron["Conn"].append(
                        {"LSrc": conn.NeuronSrc.ParentLayer.GetLayerIndex(), "NSrc": conn.NeuronSrc.GetNeuronIndex(), "Wght": conn.Weight}
                    )
                oLayer["Neurons"].append(oNeuron)
            o["Layers"].append(oLayer)
        try:
            jsonStr = dumps(o)
            jsonFile = open(filename, "wt")
            jsonFile.write(jsonStr)
            jsonFile.close()
        except:
            return False
        return True

    def AddExample(self, inputVectorNNValues, targetVectorNNValues):
        if (
            self.IsNetworkComplete
            and inputVectorNNValues
            and targetVectorNNValues
            and len(inputVectorNNValues) == self.GetInputLayer().NeuronsCount
            and len(targetVectorNNValues) == self.GetOutputLayer().NeuronsCount
        ):
            self._examples.append({"Input": inputVectorNNValues, "Target": targetVectorNNValues})
            return True
        return False

    def ClearExamples(self):
        self._examples.clear()

    def LearnExamples(self, maxSeconds=30, maxCount=None, stopWhenLearned=True, printMAEAverage=True):
        if self.ExamplesCount > 0 and maxSeconds > 0:
            count = 0
            endTime = time() + maxSeconds
            while time() < endTime and (maxCount is None or count < maxCount):
                idx = int(MicroMLP.RandomFloat() * self.ExamplesCount)
                if not self.Learn(self._examples[idx]["Input"], self._examples[idx]["Target"]):
                    return 0
                count += 1
                if (stopWhenLearned or printMAEAverage) and count % 10 == 0:
                    maeAvg = 0.0
                    for ex in self._examples:
                        self.Test(ex["Input"], ex["Target"])
                        maeAvg += self.MAE
                    maeAvg /= self.ExamplesCount
                    if printMAEAverage:
                        print("[ STEP : %s / ERROR : %s%% ]" % (count, round(maeAvg * 100 * 1000) / 1000))
                    if stopWhenLearned and maeAvg <= self.CorrectLearnedMAE:
                        break
            return count
        return 0

    # -[ Properties ]---------------------------------------

    @property
    def Layers(self):
        return self._layers

    @property
    def LayersCount(self):
        return len(self._layers)

    @property
    def IsNetworkComplete(self):
        return self.GetInputLayer() is not None and self.GetOutputLayer() is not None

    @property
    def MSE(self):
        if self.IsNetworkComplete:
            return self.GetOutputLayer().GetMeanSquareError()
        return 0.0

    @property
    def MAE(self):
        if self.IsNetworkComplete:
            return self.GetOutputLayer().GetMeanAbsoluteError()
        return 0.0

    @property
    def MSEPercent(self):
        if self.IsNetworkComplete:
            return self.GetOutputLayer().GetMeanSquareErrorAsPercent()
        return 0.0

    @property
    def MAEPercent(self):
        if self.IsNetworkComplete:
            return self.GetOutputLayer().GetMeanAbsoluteErrorAsPercent()
        return 0.0

    @property
    def ExamplesCount(self):
        return len(self._examples)

    # -[ Private functions ]------------------------------------

    def _propagateSignal(self):
        if self.IsNetworkComplete:
            idx = 1
            while idx < self.LayersCount:
                for n in self.GetLayer(idx).Neurons:
                    n.ComputeOutput()
                idx += 1
            return True
        return False

    def _backPropagateError(self):
        if self.IsNetworkComplete:
            idx = self.LayersCount - 1
            while idx >= 0:
                for n in self.GetLayer(idx).Neurons:
                    if idx < self.LayersCount - 1:
                        if idx > 0:
                            n.ComputeError()
                        for conn in n.GetOutputConnections():
                            conn.UpdateWeight(self.Eta, self.Alpha)
                    bias = n.GetBias()
                    if bias:
                        bias.UpdateWeight(self.Eta, self.Alpha)
                idx -= 1
            return True
        return False

    def _simulate(self, inputVectorNNValues, targetVectorNNValues=None, training=False):
        if self.IsNetworkComplete and self.GetInputLayer().SetInputVectorNNValues(inputVectorNNValues):
            self._propagateSignal()
            if not targetVectorNNValues:
                return not training
            if self.GetOutputLayer().ComputeTargetLayerError(targetVectorNNValues):
                if not training:
                    return True
                return self._backPropagateError()
        return False


# ======================================== 初始化配置 ==========================================

# ========================================  主程序  ===========================================
