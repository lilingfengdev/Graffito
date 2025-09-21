# XWall 配置指南

> 💡 **配置文件位置**：`config/config.yaml`  
> 📝 **示例配置**：`config/config.example.yaml`

## 📂 配置文件结构

```
config/
├── config.yaml          # 主配置文件
└── config.example.yaml  # 示例配置文件（复制后修改）
```

## 🔧 主配置文件说明

### 🖥️ 系统配置 (system)

```yaml
system:
  debug: false              # 调试模式
  log_level: INFO          # 日志级别: DEBUG|INFO|WARNING|ERROR
  data_dir: ./data         # 数据目录
  cache_dir: ./data/cache  # 缓存目录
```

### 🌐 服务器配置 (server)

```yaml
server:
  host: "0.0.0.0"  # 监听地址
  port: 8082       # 监听端口
  workers: 4       # 工作进程数
```

### 🗄️ 数据库配置 (database)

```yaml
database:
  type: sqlite     # 数据库类型: sqlite|mysql
  url: sqlite+aiosqlite:///./data/xwall.db  # 数据库连接URL
  pool_size: 10    # 连接池大小
```

#### MySQL 配置示例
```yaml
database:
  type: mysql
  url: mysql+aiomysql://user:password@localhost:3306/xwall
  pool_size: 10
```

### 📦 Redis配置 (redis)

```yaml
redis:
  enabled: false      # 是否启用Redis
  host: localhost     # Redis主机
  port: 6379         # Redis端口
  db: 0              # Redis数据库编号
```

### ⚡ 队列配置 (queue)

```yaml
queue:
  backend: AsyncSQLiteQueue  # 队列后端: AsyncSQLiteQueue|AsyncQueue|MySQLQueue
  path: data/queues         # 队列数据目录（AsyncSQLiteQueue/AsyncQueue）
  mysql:                    # MySQL配置（MySQLQueue）
    host: 127.0.0.1
    port: 3306
    user: root
    password: ""
    database: xwallqueue
    table: xwall_tasks
```

### 🤖 LLM配置 (llm)

```yaml
llm:
  # OpenAI API 配置
  base_url: https://api.openai.com/v1     # API基础地址
  api_key: sk-your-api-key-here           # API密钥，支持环境变量 ${OPENAI_API_KEY}
  text_model: gpt-4o-mini                 # 文本模型
  vision_model: gpt-4o-mini               # 视觉模型
  timeout: 30                             # 请求超时（秒）
  max_retry: 3                            # 最大重试次数
```

推荐使用 Cerebras 的 Qwen,速度非常快,Sophnet 的 Deepseek 也可以

### ⚙️ 处理配置 (processing)

```yaml
processing:
  wait_time: 120        # 等待用户补充消息时间（秒）
  max_concurrent: 10    # 最大并发处理数
```

### 📱 QQ接收器配置 (receivers.qq)

```yaml
receivers:
  qq:
    enabled: true                    # 是否启用QQ接收器
    auto_accept_friend: true         # 自动接受好友请求
    friend_request_window: 300       # 好友请求窗口期（秒）
    friend_accept_delay_min: 180     # 接受好友请求最小延迟（秒）
    friend_accept_delay_max: 240     # 接受好友请求最大延迟（秒）
    access_token: ""                 # OneBot访问令牌（可选）
```

### 🔍 审核配置 (audit)

```yaml
audit:
  auto_approve: false              # 自动审核通过
  ai_safety_check: true            # 启用AI安全检查
  sensitive_words: []              # 敏感词列表
  skip_image_audit_over_mb: 0      # 跳过大图片AI审核的阈值（MB，0=不跳过）
```

## 📤 发布器配置

### 📺 QQ空间发布器 (publishers.qzone)

```yaml
publishers:
  qzone:
    enabled: true                    # 是否启用
    driver: aioqzone                 # 驱动: aioqzone|ooqzone
    max_attempts: 3                  # 最大重试次数
    batch_size: 30                   # 批处理大小
    max_images_per_post: 9           # 单条最大图片数
    send_schedule: []                # 发送时间表 ["09:00", "12:00", "18:00", "21:00"]
    
    # 发布控制
    publish_text: true               # 是否发布文本
    include_publish_id: true         # 是否包含发布编号
    include_at_sender: true          # 是否@投稿者
    image_source: rendered           # 图片来源: rendered|chat|both
    include_segments: true           # 是否包含聊天分段内容
```

### 🎬 哔哩哔哩发布器 (publishers.bilibili)

```yaml
publishers:
  bilibili:
    enabled: false                   # 是否启用
    max_attempts: 3                  # 最大重试次数
    batch_size: 30                   # 批处理大小
    max_images_per_post: 9           # 单条最大图片数
    send_schedule: []                # 发送时间表
    
    # 发布控制
    publish_text: true               # 是否发布文本
    include_publish_id: true         # 是否包含发布编号
    include_at_sender: false         # 是否@投稿者
    image_source: rendered           # 图片来源
    include_segments: false          # 是否包含聊天分段
    
    # 账号配置
    accounts: {}                     # 账号Cookie配置
    # 示例：
    # accounts:
    #   account1:
    #     cookie_file: data/cookies/bilibili_account1.json
```

### 📱 小红书发布器 (publishers.rednote)

```yaml
publishers:
  rednote:
    enabled: false                   # 是否启用
    max_attempts: 3                  # 最大重试次数
    batch_size: 20                   # 批处理大小
    max_images_per_post: 9           # 单条最大图片数
    send_schedule: []                # 发送时间表
    
    # 发布控制
    publish_text: true               # 是否发布文本
    include_publish_id: false        # 是否包含发布编号
    include_at_sender: false         # 是否@投稿者
    image_source: rendered           # 图片来源
    include_segments: false          # 是否包含聊天分段
    
    # 账号配置
    accounts: {}                     # 账号Cookie配置
    
    # Playwright配置
    headless: true                   # 无头模式
    slow_mo_ms: 0                    # 操作延迟（毫秒）
    user_agent: ""                   # 自定义UA
```

## 👥 账号组配置 (account_groups)

```yaml
account_groups:
  default:                          # 账号组名称
    name: "默认组"                   # 显示名称
    manage_group_id: "123456789"     # 管理群ID
    
    # 主账号配置
    main_account:
      qq_id: "1234567890"           # 主账号QQ号
      http_port: 3000               # NapCat HTTP端口
      http_token: ""                # HTTP访问令牌
    
    # 副账号列表
    minor_accounts: []
    # - qq_id: "9876543210"
    #   http_port: 3001
    #   http_token: ""
    
    # 投稿配置
    max_post_stack: 1               # 最大投稿堆栈
    max_images_per_post: 30         # 单条投稿最大图片数
    send_schedule: []               # 发送时间表
    
    # 水印配置
    watermark_text: ""              # 水印文本
    wall_mark: "XWall"              # 墙标识
    
    # 交互配置
    friend_add_message: "你好，欢迎投稿"  # 好友申请通过消息
    allow_anonymous_comment: true    # 允许匿名评论
    
    # 快捷回复
    quick_replies:
      "格式": "投稿格式：直接发送文字+图片即可"
      "时间": "我们会在每天9:00、12:00、18:00、21:00发送投稿"
```

## 🔐 环境变量支持

配置文件支持环境变量替换，格式为 `${变量名}`：

```yaml
llm:
  api_key: ${OPENAI_API_KEY}      # 从环境变量读取
  base_url: ${OPENAI_BASE_URL}    # 从环境变量读取
```

### 常用环境变量
```bash
# 创建 .env 文件
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
```

## 📋 配置验证

XWall 使用 Pydantic 进行配置验证，启动时会自动检查配置的正确性：

- **类型检查**：确保配置项类型正确
- **值验证**：检查取值范围和格式
- **依赖检查**：验证配置项之间的依赖关系

如果配置有误，启动时会显示详细的错误信息。

## 🚀 快速配置

1. **复制示例配置**
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. **配置 LLM API**
   ```yaml
   llm:
     api_key: your-api-key-here
   ```

3. **配置账号组**
   ```yaml
   account_groups:
     default:
       manage_group_id: "your-manage-group-id"
       main_account:
         qq_id: "your-bot-qq"
   ```

4. **启用发布器**
   ```yaml
   publishers:
     qzone:
       enabled: true
   ```

更多高级配置选项，请参考代码中的注释和 `config/config.example.yaml` 文件。