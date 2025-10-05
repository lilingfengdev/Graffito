#!/bin/bash

# Graffito 启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║             Graffito 启动脚本           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"

# 检查Python版本
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo -e "${RED}错误: Python版本必须 >= 3.9，当前版本: $python_version${NC}"
    exit 1
fi

# 创建虚拟环境并安装依赖（仅首次）
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source venv/bin/activate
    echo -e "${YELLOW}首次创建，安装依赖...${NC}"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt --extra-index-url https://aioqzone.github.io/aioqzone-index/simple
    playwright install-deps
    playwright install chromium
else
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source venv/bin/activate
    echo -e "${YELLOW}虚拟环境已存在，跳过依赖安装${NC}"
fi

# 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo -e "${YELLOW}配置文件不存在，创建默认配置...${NC}"
    cp config/config.example.yaml config/config.yaml 2>/dev/null || true
    echo -e "${RED}请编辑 config/config.yaml 配置文件后重新启动${NC}"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}环境变量文件不存在${NC}"
    echo -e "${YELLOW}如需配置环境变量，请创建 .env 文件${NC}"
fi

# 创建必要的目录
mkdir -p data data/cache data/logs data/cookies

# 启动参数处理
case "$1" in
    -d|--debug)
        echo -e "${YELLOW}以调试模式启动...${NC}"
        export DEBUG=true
        export LOG_LEVEL=DEBUG
        ;;
    -h|--help)
        echo "用法: $0 [选项]"
        echo "选项:"
        echo "  -d, --debug    调试模式"
        echo "  -i, --init-db  强制初始化数据库"
        echo "  -h, --help     显示帮助"
        exit 0
        ;;
esac

# 初始化数据库：仅在不存在或通过 --init-db/-i 强制时执行
if [ "$1" = "--init-db" ] || [ "$1" = "-i" ]; then
    echo -e "${YELLOW}强制初始化数据库...${NC}"
    python3 cli.py db-init
elif [ ! -f "data/graffito.db" ]; then
    echo -e "${YELLOW}初始化数据库...${NC}"
    python3 cli.py db-init
else
    echo -e "${YELLOW}检测到数据库已存在，跳过初始化${NC}"
fi

# 启动主程序
echo -e "${GREEN}启动 Graffito...${NC}"
export DRIVER=~fastapi
python3 main.py
