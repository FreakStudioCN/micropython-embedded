# Freak嵌入式-MicroPython中间件开源仓库

Freak嵌入式工作室位以嵌入式电子套件及相关教程、成品电子模块开发、个人DIY电子作品为主要产品，致力于嵌入式教育📚和大学生创新创业比赛、电子计算机类比赛培训🧑‍💻。

**我们希望为电子DIY爱好者提供全面系统的教程和有趣的电子模块，帮助其快速完成项目相关知识学习和产品原型设计!**

![FreakStudio_Contact](docs/FreakStudio_Contact.png)

💡如有任何问题或需要帮助，请通过邮件📧： 10696531183@qq.com 联系 **李清水 / Freak** 。

# middleware 中间件模块
该目录是micropython-embedded项目的中间件模块集合，包含audio（音频）、display（显示）、input（输入）等常用功能组件，同时`port_peripherals`子目录放置了对于ESP32、STM32、RP2等不同硬件平台相关外设/内核的特定操作。

文件夹结构如下：
```
micropython-embedded/
├── middleware/          # 硬件无关的中间件层
│   ├── display/        # 显示框架（纯算法）
│   ├── input/          # 输入处理框架
│   ├── ui/             # 用户界面框架
│   ├── protocol/       # 通信协议处理
│   ├── audio/          # 音频处理（音效、合成器）
│   ├── storage/        # 存储抽象（文件、配置管理）
│   ├── network/        # 网络中间件（MQTT、WebSocket客户端）
│   ├── sensor/         # 传感器数据处理（滤波、校准）
│   └── utils/          # 通用工具库
├── port_peripherals/   # MCU特定的外设/内核等操作
│   ├── common/         # 通用抽象接口
│   ├── rp2/            # RP2040 特定外设
│   ├── stm32/          # STM32 特定外设
│   ├── esp32/          # ESP32 特定外设
│   ├── nrf/            # Nordic nRF52 系列
│   └── samd/           # SAMD21/51 系列
├── docs/               # 引用相关图片
```