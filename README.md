# OQQWall-Python 重构版

## 架构设计

本项目采用插件化架构，支持多接收器和多发送器：

- **接收器插件**：支持从不同平台接收消息（QQ、微信等）
- **发送器插件**：支持发送到不同平台（QQ空间、B站等）
- **处理管道**：统一的消息处理流程

## 项目结构

```
OQQWall-Python/
├── config/              # 配置管理
├── core/                # 核心框架
├── receivers/           # 接收器插件
│   ├── base.py        # 接收器基类
│   └── qq/             # QQ接收器
├── processors/          # 处理器
│   ├── pipeline.py     # 处理管道
│   └── stages/         # 处理阶段
├── publishers/          # 发送器插件
│   ├── base.py        # 发送器基类
│   └── qzone/          # QQ空间发送器
├── services/           # 服务层
├── utils/              # 工具类
└── main.py            # 主程序
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑配置文件

# 运行
python main.py
```

## 功能特性

- ✅ 插件化架构，易于扩展
- ✅ 异步处理，高性能
- ✅ 支持多账号管理
- ✅ AI智能处理
- ✅ 自动审核和人工审核
- ✅ 定时发送
- ✅ 批量管理
