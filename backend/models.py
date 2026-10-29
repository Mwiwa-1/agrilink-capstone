from sqlalchemy import (Column, Integer, String, Text, Numeric, Date,
                        DateTime, Boolean, ForeignKey)
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False)  # farmer, buyer, admin
    farmer_type = Column(String(15))           # smallholder, urban, commercial
    buyer_type = Column(String(15))            # trader, business, household
    district = Column(String(60))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    category = Column(String(30), nullable=False)
    unit = Column(String(20), nullable=False)


class ProduceListing(Base):
    __tablename__ = "produce_listings"
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    price_per_unit = Column(Numeric(12, 2), nullable=False)
    min_order_qty = Column(Numeric(10, 2), nullable=False)
    location = Column(String(100), nullable=False)
    description = Column(Text)
    harvest_date = Column(Date)
    best_before = Column(Date)
    is_urgent = Column(Boolean, nullable=False, default=False)
    status = Column(String(15), nullable=False, default="available")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("produce_listings.id"), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(14, 2), nullable=False)
    status = Column(String(15), nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("produce_listings.id"))
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Advisory(Base):
    __tablename__ = "advisory"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(150), nullable=False)
    category = Column(String(20), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
