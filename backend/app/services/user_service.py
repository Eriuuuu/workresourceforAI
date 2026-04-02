from typing import List, Optional
from bson import ObjectId
from app.databases.mongodb import get_user_collection,get_database
from app.models.user_model import User, UserCreate, UserInDB, UserRole
from app.core.security import get_password_hash, verify_password,create_access_token
from loguru import logger
from datetime import datetime,timezone



class MongoRepository:
    """MongoDB 数据访问基类"""
    
    @staticmethod
    def to_model(data: dict, model_class):
        """将数据库数据转换为模型"""
        if data and "_id" in data:
            data["_id"] = str(data["_id"])
        return model_class(**data) if data else None
    
    @staticmethod
    def to_document(model) -> dict:
        """将模型转换为数据库文档"""
        data = model.dict(by_alias=True, exclude_unset=True)
        if "_id" in data and data["_id"]:
            data["_id"] = ObjectId(data["_id"])
        return data


class UserService(MongoRepository):
    """用户服务类"""
    # 分离数据访问和业务逻辑
    # 统一的错误处理
    # 事务性操作封装
    
    def __init__(self):
        self.user_collection = get_user_collection()
        self.datebase = get_database()
    
    async def create_user(self, user_create: UserCreate) -> User:
        """创建新用户"""
        # 检查邮箱是否已存在
        existing_user = await self.user_collection.find_one({"email": user_create.email})
        if existing_user:
            raise ValueError("Email already registered")
        
        # 检查用户名是否已存在
        existing_user = await self.user_collection.find_one({"username": user_create.username})
        if existing_user:
            raise ValueError("Username already taken")
        
        # 创建用户文档
        user_dict = user_create.model_dump(exclude={"password"})
        user_dict["hashed_password"] = get_password_hash(user_create.password)
        user_dict["created_at"] = user_dict["updated_at"] = datetime.now(timezone.utc)
        
        # 插入数据库
        result = await self.user_collection.insert_one(user_dict)
        
        # 获取创建的用户
        created_user = await self.user_collection.find_one({"_id": result.inserted_id})
        logger.info(f"User created: {user_create.email}")
        
        # 确保 _id 是字符串
        return self.to_model(created_user,User)
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        if not ObjectId.is_valid(user_id):
            return None
        
        user = await self.user_collection.find_one({"_id": ObjectId(user_id)})
        return self.to_model(user,User)
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """根据邮箱获取用户（包含密码哈希）"""
        user = await self.user_collection.find_one({"email": email})
        return self.to_model(user, UserInDB)
    
    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """获取用户列表"""
        cursor = self.user_collection.find().skip(skip).limit(limit)
        users = await cursor.to_list(length=limit)
        return [self.to_model(user,User) for user in users]
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """用户认证"""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if user.disabled:
            raise ValueError("User account is disabled")
        
        return User(**user.model_dump())
    
    async def update_user_role(self, user_id: str, role: UserRole) -> Optional[User]:
        """更新用户角色"""
        if not ObjectId.is_valid(user_id):
            return None
        
        result = await self.user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": role, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count == 0:
            return None
        
        updated_user = await self.user_collection.find_one({"_id": ObjectId(user_id)})
        return User(**updated_user)
    
    def create_user_tokens(self, user_id: str) -> dict:
        """创建用户令牌"""
        access_token = create_access_token(subject=user_id)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id
        }