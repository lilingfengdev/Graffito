<div align="center">
  <img src="logo.png" alt="Graffito Logo" width="200" height="200">
  
  # Graffito - 校园墙自动运营系统
  
  ![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white)
  ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
  ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=flat-square)
  
  基于 AI 的全自动校园墙系统，从投稿接收到多平台发布一站式解决
  
</div>

---

## ✨ 核心功能

### 📱 投稿接收
- QQ 私聊接收投稿，自动接受好友
- 智能合并多条消息，AI 判断内容完整性
- 自动识别扩列内容

### 🛡️ 智能审核
- AI 内容安全检测（文字 + 图片）
- 自动匿名判断
- 敏感词过滤

### 🎨 内容渲染
- 精美 HTML 模板渲染成高清图片
- 支持本地/独立服务/Cloudflare 渲染
- 自定义水印、字体、墙标识

### 👨‍💼 审核管理

**管理群指令**：
- `是` - 通过投稿
- `否` - 拒绝投稿
- `匿` - 切换匿名
- `删` - 删除投稿
- `拒 [原因]` - 拒绝并通知
- `立即` - 立即发布
- `重渲染` - 重新渲染图片
- `评论 [内容]` - 添加评论
- `回复 [内容]` - 回复投稿者
- `拉黑` - 拉黑用户

**Web 管理面板**：
- 在线审核投稿
- 用户权限管理
- 数据统计

### 📤 多平台发布
- **QQ 空间**：说说 + 图片批量发布
- **哔哩哔哩**：动态发布
- **小红书**：图文笔记发布

**发布功能**：
- 定时发布（可配置多个时段）
- 批量发布
- 图片来源可选（渲染图/聊天图/混合）
- 每平台独立配置发布格式

### 🔔 通知系统
- 投稿确认、审核结果、发布成功全程通知
- 举报处理结果通知

---

## 🚀 工作流程

```
投稿 → AI审核 → 内容渲染 → 人工审核 → 定时发布 → 多平台同步 → 通知投稿者
```

---

## Chisel - 智能举报审核系统

<div align="center">
  <img src="chisel.png" alt="Graffito Logo" width="200" height="200">
</div>

Chisel 是内置的举报处理系统，提供 AI + 人工的双重审核机制，保障校园墙安全。

### 核心特性
- **举报接收**：用户可举报已发布的违规内容
- **AI 风险评级**：自动分析举报内容，评估风险等级
  - `safe` - 安全内容，无需处理
  - `warning` - 疑似违规，需人工复核
  - `danger` - 危险内容，建议删除
- **智能决策**：
  - 危险内容可自动删除并通知相关方
  - 安全内容自动通过无需干预
  - 疑似内容进入管理群人工审核
- **评论分析**：可抓取平台评论，AI 综合分析舆情
- **完整通知**：自动通知举报者、投稿者和管理员处理结果

---

## 📁 项目结构

```
├── main.py              # 主程序入口
├── config/              # 配置文件
├── core/                # 数据模型、数据库、缓存
├── processors/          # LLM处理、HTML渲染、图片生成
├── receivers/           # QQ接收器
├── publishers/          # QQ空间、B站、小红书发布器
├── services/            # 审核、投稿、举报、通知服务
├── web/                 # Web管理界面（后端+前端）
└── render_service/      # 独立渲染服务
```

---

## 🙏 致谢

- [gfhdhytghd/OQQWall](https://github.com/gfhdhytghd/OQQWall/)
- [aioqzone/aioqzone](https://github.com/aioqzone/aioqzone/)
- [nemo2011/bilibili-api](https://github.com/nemo2011/bilibili-api)
- [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)
- [idoknow/Campux](https://github.com/idoknow/Campux)

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源

<div align="center">
Made with ❤️ by lilingfeng
</div>
