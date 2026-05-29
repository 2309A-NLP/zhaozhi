# 前端分离说明

当前项目默认前端已经切换为 `frontend/` 目录下的静态页面。

## 1. 当前默认前端

目录：`frontend/`

特点：
- 纯 `HTML + CSS + Vue + JS`
- 不包含 Python 前端代码
- 通过 `fetch + HTTP JSON` 调用后端接口
- 访问地址为 `http://127.0.0.1:8000/`

运行方式：
- `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- 或执行 `run_local.ps1`

## 2. Streamlit 代码状态

目录：
- `app/streamlit_app.py`
- `app/pages/1_Workspace.py`

说明：
- 这两个文件仍然保留，作为旧版兼容页面
- 但项目默认运行不再依赖这两个 `.py` 前端文件
- 用户访问根路径 `/` 时，实际打开的是 `frontend/index.html`

## 3. 关于“前端 py 改成 html”

如果直接把 Streamlit 页面从 `.py` 改成 `.html`，Streamlit 将无法执行，项目会直接失效。

因此本次调整采用兼容方案：
- 保留旧 `.py` 文件，避免影响历史代码和兼容入口
- 将项目默认前端切换为 `frontend/index.html`
- 保证运行时实际使用的是 HTML 前端，而不是 Python 前端
