from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pydantic_core import core_schema
from bson import ObjectId
from datetime import datetime, timedelta,timezone


class UserRole(str, Enum):
    """用户角色枚举"""

    USER = "user"
    MODERATOR = "moderator"    # 版主/审核员
    ADMIN = "admin"

# class PyObjectId:
#     """简化版 ObjectId 处理器"""
    
#     @classmethod
#     def validate(cls, v):
#         """验证并转换为 ObjectId"""
#         if isinstance(v, ObjectId):
#             return v
#         if isinstance(v, str) and ObjectId.is_valid(v):
#             return ObjectId(v)
#         raise ValueError(f"Invalid ObjectId: {v}")
    
#     @classmethod
#     def serialize(cls, v):
#         """序列化为字符串"""
#         return str(v)
    
#     @classmethod
#     def __get_pydantic_core_schema__(cls, source_type, handler):
#         return core_schema.general_after_validator_function(
#             cls.validate,
#             core_schema.any_schema(),
#             serialization=core_schema.plain_serializer_function_ser_schema(cls.serialize),
#         )

class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, example="johndoe")
    email: EmailStr = Field(..., example="john@example.com")
    full_name: Optional[str] = Field(None, example="John Doe")
    role: UserRole = Field(default=UserRole.USER)

class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=6, example="securepassword123")

class UserInDB(UserBase):
    """数据库中的用户模型"""
    # 自定义ObjectId处理
    # 时间戳自动管理
    # 数据验证和序列化
    id: str = Field(..., alias="_id")
    hashed_password: str
    disabled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,   #允许在模型中使用任意 Python 类型(包括自定义的)，而不仅仅是 Pydantic 内置支持的类型
        populate_by_name=True,          #允许通过字段名和别名两种方式创建和访问模型实例。
        # 移除了 json_encoders，因为序列化已在 PyObjectId 中处理
    )      

class User(UserBase):
    """用户响应模型"""
    id: str = Field(..., alias="_id")
    disabled: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        populate_by_name=True
    ) 