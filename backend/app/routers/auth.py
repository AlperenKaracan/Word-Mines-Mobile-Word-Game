from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from app.models.user import UserCreate, UserLogin
from app.db.database import db
from app.core.security import hash_password, verify_password
from app.core.jwt_handler import create_access_token, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=dict)
async def register(user: UserCreate):
    existing = await db.users.find_one({"username": user.username})
    if existing:
        raise HTTPException(status_code=400, detail="Kullanıcı adı mevcut.")
    pw = user.password
    if len(pw) < 8 or not any(c.isdigit() for c in pw) \
       or pw.lower() == pw or pw.upper() == pw:
        raise HTTPException(
            status_code=400,
            detail="Şifre 8+, büyük/küçük harf ve rakam içermeli."
        )
    data = user.dict()
    hashed = hash_password(data.pop("password"))
    data["hashed_password"] = hashed
    data["wins"] = 0
    data["total_games"] = 0
    await db.users.insert_one(data)
    return {"message": "Kayıt başarılı"}

@router.post("/login", response_model=dict)
async def login(user: UserLogin):
    dbu = await db.users.find_one({"username": user.username})
    if not dbu or not verify_password(user.password, dbu["hashed_password"]):
        raise HTTPException(status_code=400, detail="Geçersiz kullanıcı adı veya şifre")
    token = create_access_token({"sub": dbu["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": dbu["username"]
    }

async def get_current_user(
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token eksik veya hatalı.")
    token = authorization.split("Bearer ")[1]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token geçersiz veya süresi dolmuş.")
    return payload["sub"]
