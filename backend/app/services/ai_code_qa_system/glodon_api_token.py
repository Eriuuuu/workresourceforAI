"""
兼容导入 — 保持旧路径可用，实际逻辑已迁移到 core.glodon_api_token
"""
from app.core.glodon_api_token import generate_token, get_glodon_token, _generate_random_str  # noqa
