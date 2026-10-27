from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=9, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Literal["farmer", "buyer"]
    farmer_type: Optional[Literal["smallholder", "urban", "commercial"]] = None
    buyer_type: Optional[Literal["trader", "business", "household"]] = None
    district: Optional[str] = None


class UserOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: EmailStr
    role: str
    farmer_type: Optional[str] = None
    buyer_type: Optional[str] = None
    district: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
