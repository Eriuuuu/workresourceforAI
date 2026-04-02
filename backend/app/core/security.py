from datetime import datetime, timedelta,timezone
from typing import Any, Union, Optional
from jose import jwt, JWTError
import bcrypt
from app.core.config import get_settings
from loguru import logger

settings = get_settings()

# # 密码加密上下文
# pwd_context = CryptContext(
#     schemes=["bcrypt"], 
#     deprecated="auto",
#     bcrypt__rounds=4  # 加密轮数，提高安全性
# )

def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建JWT访问令牌
    
    JWT结构：
    - Header: 算法和令牌类型
    - Payload: 用户信息、过期时间、签发时间等
    - Signature: 使用密钥签名，防止篡改

    创建步骤 = {
        "1. 准备Payload": {
            "exp": "当前时间 + 30分钟",
            "sub": "用户ID", 
            "type": "access",
            "iat": "当前时间"
        },
        "2. 创建Header": {
            "alg": "HS256",
            "typ": "JWT"
        },
        "3. 编码数据": "Base64编码Header和Payload",
        "4. 生成签名": "HMAC-SHA256(编码后的数据, 密钥)",
        "5. 组合令牌": "Header.Payload.Signature"
    }
    
    参数：
        subject: 用户标识（通常是用户ID）
        expires_delta: 自定义过期时间
    
    返回：
        str: 编码后的JWT令牌
    """
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # JWT Payload
    to_encode = {
        "exp": expire,        # 过期时间 (expiration)
        "sub": str(subject),  # 用户标识 (subject)
        "type": "access",     # 令牌类型
        "iat": datetime.now(timezone.utc),  # 签发时间 (issued at)
    }
    
    # 使用HS256算法签名
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    bcrypt算法特点：
    1. 自动加盐，防止彩虹表攻击
    2. 计算密集型，防止暴力破解
    3. 相同密码每次哈希结果不同
    
    验证过程:
    {
    "1. 提取盐值": "从存储的哈希值中提取盐值",
    "2. 重新哈希": "使用相同盐值对输入密码进行哈希",
    "3. 比较结果": "比较新哈希值与存储的哈希值",
    "4. 返回结果": "匹配则返回True，否则False"
    }

    参数：
        plain_password: 明文密码
        hashed_password: 哈希后的密码
    
    返回：
        bool: 验证结果
    """
    plain_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)

def get_password_hash(password: str) -> str:
    """生成密码哈希
    
    参数：
        password: 明文密码
    
    返回：
        str: 哈希后的密码
    """
    pwd_bytes = password.encode('utf-8')
    # 生成盐
    salt = bcrypt.gensalt(rounds=4)
    # 哈希密码
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_token(token: str) -> Optional[str]:
    """验证JWT令牌并返回用户ID
    
    验证步骤：
    1. 解码JWT令牌
    2. 验证签名
    3. 检查过期时间
    4. 验证令牌类型
    
    参数：
        token: JWT令牌
    
    返回：
        Optional[str]: 用户ID或None
    """
    try:
        # 解码JWT
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        # 验证必要字段
        if user_id is None or token_type != "access":
            return None
            
        return user_id
        
    except JWTError as e:
        # 记录详细的JWT错误
        logger.warning(f"JWT verification failed: {e}")
        return None