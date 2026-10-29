from datetime import date
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------- USERS
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


# ------------------------------------------------------------- PRODUCTS
ProductCategory = Literal[
    "cereal", "legume", "vegetable", "fruit", "livestock",
    "apiculture", "rabbits", "fisheries", "farm_inputs",
]
ProductUnit = Literal["kg", "bunch", "litre", "tray", "bag", "piece", "jar"]


class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: ProductCategory
    unit: ProductUnit


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    category: Optional[ProductCategory] = None
    unit: Optional[ProductUnit] = None


class ProductOut(ProductBase):
    id: int

    model_config = {"from_attributes": True}


# ------------------------------------------------------------- LISTINGS
class ListingBase(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    price_per_unit: Decimal = Field(gt=0)
    min_order_qty: Decimal = Field(gt=0)
    location: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    harvest_date: Optional[date] = None
    best_before: Optional[date] = None
    is_urgent: bool = False


class ListingCreate(ListingBase):
    pass


class ListingUpdate(BaseModel):
    product_id: Optional[int] = None
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    price_per_unit: Optional[Decimal] = Field(default=None, gt=0)
    min_order_qty: Optional[Decimal] = Field(default=None, gt=0)
    location: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    harvest_date: Optional[date] = None
    best_before: Optional[date] = None
    is_urgent: Optional[bool] = None
    status: Optional[Literal["available", "sold_out"]] = None


class ListingOut(ListingBase):
    id: int
    farmer_id: int
    status: str

    model_config = {"from_attributes": True}
