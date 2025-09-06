# OQQWall-Python 使用指南

## 快速开始

### 启动服务

```bash
# Linux/macOS
./start.sh

# Windows
start.bat

# 或直接运行
# 确保设置 DRIVER=~fastapi 以启用 NoneBot2 FastAPI 驱动
DRIVER=~fastapi python main.py
```

### 停止服务

按 `Ctrl+C` 停止服务

## 基本操作流程

### 1. 用户投稿

用户通过私聊机器人发送投稿：
- 文字投稿：直接发送文字
- 图片投稿：发送图片+文字描述
- 多条消息：在2分钟内发送的多条消息会合并为一个投稿

### 2. 自动处理

系统自动处理投稿：
1. 内容审核（AI安全检查）
2. 匿名检测（识别用户是否要求匿名）
3. 内容渲染（生成图片）
4. 发送到管理群审核

### 3. 人工审核

管理员在管理群中审核：
- `@机器人 <编号> 是` - 通过投稿
- `@机器人 <编号> 否` - 拒绝投稿
- `@机器人 <编号> 匿` - 切换匿名状态
- `@机器人 <编号> 等` - 暂缓处理
- `@机器人 <编号> 删` - 删除投稿
- `@机器人 <编号> 拉黑` - 拉黑用户
- `@机器人 <编号> 评论 <内容>` - 添加评论
- `@机器人 <编号> 立即` - 立即发送

### 4. 自动发布

通过审核的投稿会：
- 暂存到发送队列
- 根据配置的时间表自动发送
- 或达到批量阈值后自动发送

## CLI命令行工具

### 查看配置

```bash
python cli.py config
```

### 投稿管理

```bash
# 查看投稿列表
python cli.py list-submissions --status pending --limit 10

# 审核投稿
python cli.py audit 123 approve --comment "好投稿"
python cli.py audit 124 reject --comment "内容不合适"
```

### 黑名单管理

```bash
# 添加黑名单
python cli.py blacklist-add 1234567890 default --reason "违规内容"

# 查看黑名单
python cli.py blacklist-list

# 移除黑名单
python cli.py blacklist-remove 1234567890 default
```

### 数据库操作

```bash
# 初始化数据库
python cli.py db-init

# 测试数据库连接
python cli.py test-db
```

### 手动发送

```bash
# 立即发送暂存的投稿
python cli.py flush-posts --group default
```

## 高级功能

### 多账号协同

配置多个QQ账号协同工作：

```yaml
account_groups:
  campus:
    main_account:
      qq_id: "1234567890"
      http_port: 3000
    minor_accounts:
      - qq_id: "9876543210"
        http_port: 3001
      - qq_id: "5555555555"
        http_port: 3002
```

主账号用于接收投稿，所有账号都可以发送。

### 定时发送

配置固定时间发送投稿：

```yaml
publishers:
  qzone:
    send_schedule: ["09:00", "12:00", "18:00", "21:00"]
```

### 批量发送

配置批量发送阈值：

```yaml
account_groups:
  default:
    max_post_stack: 3  # 累积3个投稿后自动发送
```

### 快捷回复

配置常用回复模板：

```yaml
account_groups:
  default:
    quick_replies:
      "格式": "投稿格式：文字+图片即可"
      "时间": "每天9:00、12:00、18:00、21:00发送"
      "规则": "请遵守社区规范，文明投稿"
```

管理员使用：`@机器人 <编号> 格式`

### 水印设置

为发布的图片添加水印：

```yaml
account_groups:
  default:
    watermark_text: "校园墙 · 2024"
```

## 监控和日志

### 查看日志

日志文件位置：`data/logs/`

实时查看日志：
```bash
tail -f data/logs/oqqwall_$(date +%Y-%m-%d).log
```

### 健康检查

访问健康检查端点：
```bash
curl http://localhost:8082/health
```
（NoneBot2 会以 FastAPI 应用形式暴露 /health）

### 性能监控

查看系统状态：
```bash
# 查看进程
ps aux | grep oqqwall

# 查看端口
netstat -tlnp | grep 8082

# 查看资源使用
htop
```

## 备份和恢复

### 备份数据

```bash
# 备份数据库
cp data/oqqwall.db data/oqqwall.db.backup

# 备份所有数据
tar czf backup_$(date +%Y%m%d).tar.gz data/
```

### 恢复数据

```bash
# 恢复数据库
cp data/oqqwall.db.backup data/oqqwall.db

# 恢复所有数据
tar xzf backup_20240101.tar.gz
```

## 常见问题

### Q: 投稿没有收到？
A: 检查：
1. 机器人是否在线
2. 用户是否被拉黑
3. 查看日志是否有错误

### Q: 发送失败？
A: 检查：
1. QQ空间登录状态
2. 网络连接
3. API配额是否充足

### Q: 审核指令无效？
A: 确认：
1. 使用正确的格式：`@机器人 编号 指令`
2. 管理员权限
3. 编号是否正确

### Q: 如何修改已发送的内容？
A: 已发送的内容无法修改，只能在QQ空间手动编辑或删除。

## 开发和扩展

### 添加新的接收器

继承 `BaseReceiver` 类：

```python
from receivers.base import BaseReceiver

class WeChatReceiver(BaseReceiver):
    async def start(self):
        # 实现启动逻辑
        pass
        
    async def handle_message(self, message):
        # 实现消息处理
        pass
```

### 添加新的发送器

继承 `BasePublisher` 类：

```python
from publishers.base import BasePublisher

class BilibiliPublisher(BasePublisher):
    async def publish(self, content, images):
        # 实现发布逻辑
        pass
```

### 自定义处理器

实现处理管道阶段：

```python
from processors.base import BaseProcessor

class CustomProcessor(BaseProcessor):
    async def process(self, submission):
        # 自定义处理逻辑
        return submission
```

## 安全建议

1. **定期备份数据**
2. **使用强密码保护账号**
3. **限制管理群成员**
4. **定期更新依赖**
5. **监控异常行为**
6. **设置敏感词过滤**

## 更多帮助

- 查看完整文档：[GitHub Wiki](https://github.com/your-repo/wiki)
- 提交问题：[GitHub Issues](https://github.com/your-repo/issues)
- 加入社区：QQ群 123456789
