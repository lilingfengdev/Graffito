Graffito Web 审核后台
=================

目录结构
--------

- `web/backend/app.py`: FastAPI 后端，提供认证、邀请注册、审核接口，并可挂载前端静态资源。
- `web/frontend/`: Vue 3 + Vite 前端（npm）。

后端启动
--------

1. 安装依赖（项目根目录）：
   - Windows PowerShell: `pip install -r requirements.txt`
2. main.py 联动启动后端：
   - 在 `config/config.yaml` 中配置：
     ```yaml
     web:
       enabled: true
       host: 0.0.0.0
       port: 8082
       jwt_secret_key: "change-this-secret"
     ```
   - 运行 `python main.py`，主程序将自动启动 FastAPI 网页服务。

前端启动（开发）
--------------

1. 进入前端目录：`cd web/frontend`
2. 安装依赖：`npm install`
3. 可选：设置后端 API 地址（默认 `http://localhost:8082`）：
   - 新建 `.env.local` 写入：
     ```ini
     VITE_API_BASE=http://localhost:8082
     ```
4. 启动开发服务器：`npm run dev`
   - 代理读取 `VITE_API_BASE` 指向后端。

前端构建与部署
--------------

1. 构建：`npm run build`
2. 构建产物位于 `web/frontend/dist`，后端会自动优先挂载该目录为静态网站。

首个用户初始化流程
------------------

1. 启动后端后访问前端（开发环境使用 Vite URL；构建后直接访问后端根路径）。
2. 若系统无超级管理员，先在登录页“初始化超级管理员”。
3. 使用超级管理员登录后，可创建“邀请链接”，新管理员可用该链接注册。


