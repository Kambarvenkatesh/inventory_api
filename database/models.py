from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Index, Integer, Numeric, String, Text, func,
)

from database.connection import Base


class Product(Base):

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("quantity >= 0", name="ck_products_quantity_non_negative"),
        Index("ix_products_category", "category"),
        Index("ix_products_name", "product_name"),
    )

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(String(50), unique=True, nullable=False)   # business key
    product_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)                        # long free text
    category = Column(String(100), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)                   # exact decimal, never FLOAT for money
    quantity = Column(Integer, nullable=False, default=0, server_default="0")
    supplier_name = Column(String(150), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
