"""
广联达 AI API Token 生成 — 共享基础组件

被智能问答系统和用例生成系统共同依赖，放在 core 层避免循环引用。
"""
import requests
import time
from random import choice
from hashlib import md5
from string import digits, ascii_letters


def generate_token(api_key: str, api_secret: str,
                   url: str = "https://copilot.glodon.com/api/auth/v1/access-token") -> str:
    """使用 api_key 和 api_secret 生成 Bearer token"""
    if not api_key or not api_secret:
        return ""

    timestamp = str(int(time.time() * 1000))
    noncestr = _generate_random_str(24)
    raw_token = f"{api_key}:{timestamp}:{noncestr}:{api_secret}"
    auth = md5(raw_token.encode('utf-8')).hexdigest()

    headers = {
        'X-AIOT-APIKEY': api_key,
        'X-AIOT-TIMESTAMP': timestamp,
        'X-AIOT-NONCESTR': noncestr,
        'Authorization': f"Basic {auth}"
    }
    try:
        response = requests.post(url, headers=headers, data={})
        if response.status_code == 200:
            res = response.json()
            if res["code"] != 200:
                raise Exception(res["message"])
            return f"Bearer {res['data']['accessToken']}"
        else:
            raise Exception(response.status_code)
    except Exception as err:
        return ""


def _generate_random_str(length: int = 24) -> str:
    return ''.join(choice(digits + ascii_letters) for _ in range(length))


def get_glodon_token() -> str:
    """获取广联达 AI API token（使用默认配置）"""
    api_key = "hxHkv8BS0a1MDlsL"
    api_secret = "1X51L2RULJuTGyY0x18uss1p"
    host = "https://copilot.glodon.com"
    return generate_token(api_key, api_secret, f"{host}/api/auth/v1/access-token")
