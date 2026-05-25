# FastAPI router with JWT auth — production pattern
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.shared.database import get_db
from src.shared.config import settings
from src.auth.schemas import Token, UserCreate, UserResponse
from src.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    if service.get_user_by_email(user_data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return service.create_user(user_data)

@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    token = service.create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token",
                            headers={"WWW-Authenticate": "Bearer"})
    return user
