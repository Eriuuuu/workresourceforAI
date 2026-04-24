"""
QA 系统实例管理器 — 解耦 qa_agent.py 对 aiagent_api.py 的循环引用

QA 系统实例的生命周期：
1. 应用启动时 _qa_system_instance = None
2. 前端调用 /initialize 接口 → aiagent_api 调用 init_qa_system() 设置实例
3. qa_agent 通过 get_qa_system() 获取实例
"""
from typing import Optional
from loguru import logger

_qa_system_instance = None


def init_qa_system(instance) -> None:
    """设置全局 QA 系统实例（由 aiagent_api 在初始化完成后调用）"""
    global _qa_system_instance
    _qa_system_instance = instance
    logger.info("[QAManager] QA 系统实例已注册")


def get_qa_system():
    """获取全局 QA 系统实例"""
    return _qa_system_instance


def clear_qa_system() -> None:
    """清除全局 QA 系统实例"""
    global _qa_system_instance
    _qa_system_instance = None
    logger.info("[QAManager] QA 系统实例已清除")
