# XWall 安装部署指南

## 📋 环境要求

| 要求                | 版本           | 说明               |
|-------------------|--------------|------------------|
| 🐍 **Python**     | 3.8+         | 推荐使用 Python 3.9+ |
| 🗄️ **数据库**       | SQLite/MySQL | SQLite 为默认选项     |
| 🎭 **Playwright** | 最新版          | 用于 HTML 渲染       |
| 🤖 **LLM API**    | OpenAI 兼容    | GPT/Claude/国产大模型 |

## ⚡ 快速安装

### Windows 用户

```bash
# 直接运行启动脚本
start.bat
```

### Linux/Mac 用户

```bash
# 克隆项目
git clone https://github.com/lilingfengdev/XWall.git
cd XWall

# 安装依赖
pip install -r requirements.txt --extra-index-url https://aioqzone.github.io/aioqzone-index/simple
playwright install chromium

# 配置系统
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml 文件

# 启动服务
python main.py
```

## 🔧 详细配置

详细的配置说明请参考 [配置指南](configuration.md)。
