from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import engine, Base, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriLink API")


def require_admin(current_user: models.User = Depends(auth.get_current_user)):
    """Reusable guard: only admins pass, everyone else gets 403."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------- HOME
@app.get("/")
def home():
    return {"message": "AgriLink API is running"}


# ---------------------------------------------------------------- AUTH
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(models.User).filter(models.User.phone == data.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    if data.role == "farmer" and data.farmer_type is None:
        raise HTTPException(status_code=400, detail="Farmers must choose a farmer type")
    if data.role == "buyer" and data.buyer_type is None:
        raise HTTPException(status_code=400, detail="Buyers must choose a buyer type")

    user = models.User(
        full_name=data.full_name,
        phone=data.phone,
        email=email,
        password_hash=auth.hash_password(data.password),
        role=data.role,
        farmer_type=data.farmer_type,
        buyer_type=data.buyer_type,
        district=data.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email.lower()).first()
    if user is None or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": auth.create_token(user), "token_type": "bearer", "user": user}


@app.get("/users/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ------------------------------------------------------------- PRODUCTS
@app.get("/products", response_model=list[schemas.ProductOut])
def list_products(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /products: any logged-in user can view the catalogue."""
    query = db.query(models.Product)
    if category:
        query = query.filter(models.Product.category == category)
    return query.order_by(models.Product.name).all()


@app.post("/products", response_model=schemas.ProductOut, status_code=201)
def create_product(
    data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """POST /products: add a product to the catalogue (admin only)."""
    existing = db.query(models.Product).filter(models.Product.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product with this name already exists")

    product = models.Product(name=data.name, category=data.category, unit=data.unit)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/products/{id}", response_model=schemas.ProductOut)
def update_product(
    id: int,
    data: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """PUT /products/{id}: edit a product (admin only)."""
    product = db.query(models.Product).filter(models.Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{id}")
def delete_product(
    id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """DELETE /products/{id}: delete a product (admin only)."""
    product = db.query(models.Product).filter(models.Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    in_use = db.query(models.ProduceListing).filter(models.ProduceListing.product_id == id).first()
    if in_use:
        raise HTTPException(status_code=400, detail="Product is used by existing listings")

    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}


# ------------------------------------------------------------- LISTINGS
@app.get("/listings", response_model=list[schemas.ListingOut])
def browse_listings(
    product_id: Optional[int] = None,
    location: Optional[str] = None,
    max_min_order: Optional[Decimal] = None,
    urgent: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /listings: browse available listings (urgent first)."""
    query = db.query(models.ProduceListing).filter(models.ProduceListing.status == "available")

    if product_id is not None:
        query = query.filter(models.ProduceListing.product_id == product_id)
    if location:
        query = query.filter(models.ProduceListing.location.ilike(f"%{location}%"))
    if max_min_order is not None:
        query = query.filter(models.ProduceListing.min_order_qty <= max_min_order)
    if urgent:
        query = query.filter(models.ProduceListing.is_urgent == True)  # noqa: E712

    return query.order_by(
        models.ProduceListing.is_urgent.desc(),
        models.ProduceListing.created_at.desc(),
    ).all()


# NOTE: /listings/mine must stay ABOVE /listings/{id}, or "mine" is read as an id.
@app.get("/listings/mine", response_model=list[schemas.ListingOut])
def my_listings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /listings/mine: the logged-in farmer's own listings."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can view their own listings")
    return (
        db.query(models.ProduceListing)
        .filter(models.ProduceListing.farmer_id == current_user.id)
        .order_by(models.ProduceListing.created_at.desc())
        .all()
    )


@app.get("/listings/{id}", response_model=schemas.ListingOut)
def get_listing(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /listings/{id}: single listing detail."""
    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@app.post("/listings", response_model=schemas.ListingOut, status_code=201)
def create_listing(
    data: schemas.ListingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """POST /listings: create a produce listing (farmer only)."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can create listings")

    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in catalogue")

    if data.min_order_qty > data.quantity:
        raise HTTPException(status_code=400, detail="Minimum order cannot exceed quantity")

    listing = models.ProduceListing(
        farmer_id=current_user.id,
        product_id=data.product_id,
        quantity=data.quantity,
        price_per_unit=data.price_per_unit,
        min_order_qty=data.min_order_qty,
        location=data.location,
        description=data.description,
        harvest_date=data.harvest_date,
        best_before=data.best_before,
        is_urgent=data.is_urgent,
        status="available",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@app.put("/listings/{id}", response_model=schemas.ListingOut)
def update_listing(
    id: int,
    data: schemas.ListingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """PUT /listings/{id}: edit own listing (farmer only)."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can edit listings")

    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listings")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(listing, key, value)

    db.commit()
    db.refresh(listing)
    return listing


@app.delete("/listings/{id}")
def delete_listing(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """DELETE /listings/{id}: delete own listing (farmer only)."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can delete listings")

    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own listings")

    db.delete(listing)
    db.commit()
    return {"message": "Listing deleted successfully"}
