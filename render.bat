@echo off
REM 启动独立的 HTML 渲染服务器 (Windows)
REM 默认监听端口 8084

echo Starting HTML Render Service...
python -m render_service.server

