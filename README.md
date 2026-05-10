# Data Structures Learning Assistant

一个基于 FastAPI + 原生前端的学习助手项目。

## 项目结构

- `backend/`：后端服务（FastAPI）
- `frontend/`：前端页面（静态资源）
- `data/`：上传文件与向量库数据

## 环境要求

- Windows PowerShell
- Python 3.10+

## 启动后端

在终端 1 执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

后端健康检查：

```powershell
curl http://127.0.0.1:8000/api/health
```

## 启动前端

在终端 2 执行：

```powershell
cd frontend
python -m http.server 5500
```

浏览器打开：

```text
http://127.0.0.1:5500
```

## 使用说明

1. 打开前端页面后，在左侧输入并保存 DeepSeek API Key。
2. 上传学习资料（`.cpp`、`.h`、`.txt`、`.md`、`.pdf`、`.docx`）。
3. 在对话框中提问。

## 可选：提升 Hugging Face 下载速度

如果首次加载模型较慢，可在启动后端前设置：

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_ENABLE_HF_TRANSFER="1"
```

然后再启动 uvicorn。
