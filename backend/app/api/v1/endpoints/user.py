from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from app.services.user_service import UserService
from app.models.user_model import User, UserRole
from app.api.dependencies.auth import get_current_active_user

router = APIRouter(tags=["获取用户信息操作"])

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user

@router.get("/", response_model=List[User])
async def read_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_service: UserService = Depends(),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户列表（需要认证）"""
    users = await user_service.get_users(skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: str,
    user_service: UserService = Depends(),
    current_user: User = Depends(get_current_active_user)
):
    """根据ID获取用户"""
    user = await user_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user