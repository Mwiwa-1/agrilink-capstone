import os
import uuid
from decimal import Decimal
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import engine, Base, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriLink API")
# Folder for listing photos, 
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads",StaticFiles(directory="uploads"),  name="uploads")

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
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended. Contact the admin")    
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


# --------------------------------------------------------------- ORDERS
def get_pending_order_for_farmer(order_id: int, db: Session, current_user: models.User):
    """Shared checks for accept/reject: farmer, own listing, order still pending."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can do this")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == order.listing_id).first()
    if listing is None or listing.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="This order is not on your listing")

    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Order is no longer pending")
    return order, listing


@app.post("/orders", response_model=schemas.OrderOut, status_code=201)
def place_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """POST /orders: a buyer orders a quantity from a listing."""
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can place orders")

    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == data.listing_id).first()
    if not listing or listing.status != "available":
        raise HTTPException(status_code=404, detail="Listing not found or sold out")

    if data.quantity < listing.min_order_qty:
        raise HTTPException(status_code=400, detail=f"Minimum order is {listing.min_order_qty}")
    if data.quantity > listing.quantity:
        raise HTTPException(status_code=400, detail=f"Only {listing.quantity} available")

    order = models.Order(
        buyer_id=current_user.id,
        listing_id=listing.id,
        quantity=data.quantity,
        total_price=data.quantity * listing.price_per_unit,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# NOTE: /orders/mine and /orders/received are fixed paths, kept above any /orders/{id} route.
@app.get("/orders/mine", response_model=list[schemas.OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /orders/mine: the logged-in buyer's own orders."""
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers have orders placed")
    return (
        db.query(models.Order)
        .filter(models.Order.buyer_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@app.get("/orders/received", response_model=list[schemas.OrderOut])
def received_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /orders/received: orders placed on the logged-in farmer's listings."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers receive orders")
    return (
        db.query(models.Order)
        .join(models.ProduceListing, models.Order.listing_id == models.ProduceListing.id)
        .filter(models.ProduceListing.farmer_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@app.put("/orders/{id}/cancel", response_model=schemas.OrderOut)
def cancel_order(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """PUT /orders/{id}/cancel: a buyer cancels their own pending order."""
    order = db.query(models.Order).filter(models.Order.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your own orders")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending orders can be cancelled")

    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


@app.put("/orders/{id}/accept", response_model=schemas.OrderOut)
def accept_order(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """PUT /orders/{id}/accept: farmer accepts; listing quantity goes down."""
    order, listing = get_pending_order_for_farmer(id, db, current_user)

    if order.quantity > listing.quantity:
        raise HTTPException(status_code=400, detail="Not enough quantity left on the listing")

    listing.quantity = listing.quantity - order.quantity
    if listing.quantity <= 0:
        listing.status = "sold_out"
    order.status = "accepted"

    db.commit()
    db.refresh(order)
    return order


@app.put("/orders/{id}/reject", response_model=schemas.OrderOut)
def reject_order(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """PUT /orders/{id}/reject: farmer rejects a pending order."""
    order, listing = get_pending_order_for_farmer(id, db, current_user)

    order.status = "rejected"
    db.commit()
    db.refresh(order)
    return order


# ------------------------------------------------------------- MESSAGES
@app.post("/messages", response_model=schemas.MessageOut, status_code=201)
def send_message(
    data: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """POST /messages: send a message to another user (optionally about a listing)."""
    if data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot message yourself")

    receiver = db.query(models.User).filter(models.User.id == data.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    if data.listing_id is not None:
        listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == data.listing_id).first()
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

    message = models.Message(
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        listing_id=data.listing_id,
        body=data.body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@app.get("/messages/inbox", response_model=list[schemas.MessageOut])
def inbox(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /messages/inbox: messages sent to the logged-in user, newest first."""
    return (
        db.query(models.Message)
        .filter(models.Message.receiver_id == current_user.id)
        .order_by(models.Message.created_at.desc(), models.Message.id.desc())
        .all()
    )


@app.get("/messages/with/{user_id}", response_model=list[schemas.MessageOut])
def conversation(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /messages/with/{user_id}: the full conversation with one person, oldest first."""
    me = current_user.id
    return (
        db.query(models.Message)
        .filter(
            ((models.Message.sender_id == me) & (models.Message.receiver_id == user_id))
            | ((models.Message.sender_id == user_id) & (models.Message.receiver_id == me))
        )
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
        .all()
    )


# ------------------------------------------------------------- ADVISORY
@app.get("/advisory", response_model=list[schemas.AdvisoryOut])
def list_advisory(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /advisory: any logged-in user can read advice (newest first)."""
    query = db.query(models.Advisory)
    if category:
        query = query.filter(models.Advisory.category == category)
    return query.order_by(models.Advisory.created_at.desc(), models.Advisory.id.desc()).all()


@app.get("/advisory/{id}", response_model=schemas.AdvisoryOut)
def get_advisory(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """GET /advisory/{id}: one advisory article."""
    article = db.query(models.Advisory).filter(models.Advisory.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Advisory article not found")
    return article


@app.post("/advisory", response_model=schemas.AdvisoryOut, status_code=201)
def create_advisory(
    data: schemas.AdvisoryCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """POST /advisory: publish advice (admin only)."""
    article = models.Advisory(
        author_id=admin.id,
        title=data.title,
        category=data.category,
        body=data.body,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@app.put("/advisory/{id}", response_model=schemas.AdvisoryOut)
def update_advisory(
    id: int,
    data: schemas.AdvisoryUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """PUT /advisory/{id}: edit advice (admin only)."""
    article = db.query(models.Advisory).filter(models.Advisory.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Advisory article not found")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(article, key, value)

    db.commit()
    db.refresh(article)
    return article


@app.delete("/advisory/{id}")
def delete_advisory(
    id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """DELETE /advisory/{id}: remove advice (admin only)."""
    article = db.query(models.Advisory).filter(models.Advisory.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Advisory article not found")

    db.delete(article)
    db.commit()
    return {"message": "Advisory article deleted successfully"}

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


@app.post("/listings/{id}/image", response_model=schemas.ListingOut)
def upload_listing_image(
    id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """POST /listings/{id}/image: a farmer adds a photo to their own listing."""
    if current_user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmers can upload photos")

    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only add photos to your own listings")

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP images are allowed")

    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large (max 5 MB)")

    filename = f"{uuid.uuid4().hex}{extension}"
    with open(os.path.join("uploads", filename), "wb") as out:
        out.write(content)

    listing.image_url = f"/uploads/{filename}"
    db.commit()
    db.refresh(listing)
    return listing


# ---------------------------------------------------------------- ADMIN
@app.get("/admin/users", response_model=list[schemas.UserOut])
def admin_list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """GET /admin/users: every user in the system (admin only)."""
    return db.query(models.User).order_by(models.User.id).all()


@app.put("/admin/users/{id}/suspend", response_model=schemas.UserOut)
def admin_suspend_user(
    id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """PUT /admin/users/{id}/suspend: block a user from logging in (admin only)."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Admins cannot be suspended")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@app.put("/admin/users/{id}/activate", response_model=schemas.UserOut)
def admin_activate_user(
    id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """PUT /admin/users/{id}/activate: let a suspended user log in again (admin only)."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@app.put("/admin/listings/{id}/remove", response_model=schemas.ListingOut)
def admin_remove_listing(
    id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """PUT /admin/listings/{id}/remove: hide a fraudulent listing from browsing (admin only)."""
    listing = db.query(models.ProduceListing).filter(models.ProduceListing.id == id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.status = "removed"
    db.commit()
    db.refresh(listing)
    return listing


@app.get("/admin/orders", response_model=list[schemas.OrderOut])
def admin_list_orders(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """GET /admin/orders: every order in the system (admin only)."""
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()
