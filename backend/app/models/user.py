import re
from pydantic import BaseModel, EmailStr, Field, validator

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @validator('password')
    def password_complexity(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Şifre en az bir büyük harf içermelidir.')
        if not re.search(r'[a-z]', v):
            raise ValueError('Şifre en az bir küçük harf içermelidir.')
        if not re.search(r'[0-9]', v):
            raise ValueError('Şifre en az bir rakam içermelidir.')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserInDB(UserBase):
    hashed_password: str

class UserPublic(UserBase):
    wins: int = 0
    losses: int = 0
    success_rate: float = 0.0

class UserOut(UserBase):
    class Config:
        from_attributes = True