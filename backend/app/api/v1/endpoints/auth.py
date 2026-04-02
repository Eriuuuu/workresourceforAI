from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.user_service import UserService
from app.core.security import create_access_token
from app.models.user_model import User ,UserCreate
from datetime import timedelta

router = APIRouter(tags=["登录注册操作"])

@router.post("/login", response_model=dict, response_description= "用户登录执行")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends()
):
    """用户登录"""
    user = await user_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token = create_access_token(subject=str(user.id),expires_delta=timedelta(hours=1))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/register", response_model=User, response_description= "用户注册执行")
async def register(
    user_create: UserCreate,
    user_service: UserService = Depends()
):
    """用户注册"""
    try:
        user = await user_service.create_user(user_create)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )