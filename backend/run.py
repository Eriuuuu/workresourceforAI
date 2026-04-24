"""
开发服务器启动脚本

使用 watchfiles 替代默认 reloader，排除运行时生成目录避免误触发 reload。
用法: python run.py
"""
import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        reload_excludes=[
            "chroma_db/*",
            "prometheus_data/*",
            "logs/*",
            "*.bin",
            "*.sqlite3",
            "*.pyc",
            "__pycache__/*",
            ".git/*",
        ],
        log_level="info",
    )
