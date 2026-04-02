import os
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from loguru import logger
import asyncio

settings = get_settings()

class MongoDB:
    """MongoDB连接管理类
    
    使用Motor实现异步MongoDB操作
    提供连接池管理，提高性能
    实现健康检查机制，确保连接可用性
    """
    
    client: AsyncIOMotorClient = None
    database = None

# 创建全局数据库实例
mongodb = MongoDB()

async def connect_to_mongo():
    """连接MongoDB数据库
    
    功能：
    1. 创建Motor客户端连接
    2. 选择指定数据库
    3. 执行ping命令测试连接
    4. 记录连接状态日志
    """
    try:
        # 创建异步MongoDB客户端
        mongodb.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=100,  # 最大连接池大小
            minPoolSize=10,   # 最小连接池大小
            retryWrites=True  # 启用重试写入
        )
        
        # 选择数据库
        mongodb.database = mongodb.client[settings.DATABASE_NAME]
        
        # 测试连接 - 执行ping命令
        await mongodb.client.admin.command('ping')
        collections =await mongodb.database.list_collection_names()
        
        logger.info("✅ Successfully connected to MongoDB")
        logger.info(f"📊 Database: {settings.DATABASE_NAME}")
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        # 在生产环境中，这里可以添加重试逻辑或告警
        raise

async def close_mongo_connection():
    """关闭MongoDB连接
    
    清理连接池资源，避免资源泄漏
    """
    if mongodb.client:
        mongodb.client.close()
        logger.info("✅ MongoDB connection closed")

def get_database():
    """获取数据库实例
    
    返回：
        AsyncIOMotorDatabase: 数据库实例
    
    异常：
        RuntimeError: 如果数据库未连接
    """
    if mongodb.database is None:
        raise RuntimeError("Database not connected. Call connect_to_mongo first.")
    return mongodb.database

def get_user_collection():
    """获取用户集合
    
    返回：
        AsyncIOMotorCollection: 用户集合实例
    """
    return get_database().users

def get_collection(collection_name: str):
    """通用方法：获取指定集合
    
    参数：
        collection_name: 集合名称
    
    返回：
        AsyncIOMotorCollection: 集合实例
    """
    return get_database()[collection_name]


# # 正确运行异步函数
# async def main():
#     await connect_to_mongo()
    
#     # 测试获取数据库
#     db = get_database()  # ✅ 注意：get_database() 是同步函数，不需要 await
#     print(f"📊 数据库: {db}")
    
#     # 测试获取集合
#     users_collection = get_user_collection()
#     print(f"📁 用户集合: {users_collection}")
    
#     await close_mongo_connection()


# if __name__ == "__main__":
#     asyncio.run(main())