import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr
from sqlmodel import Field, Relationship, SQLModel


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


class InvoicePublic(SQLModel):
    id: UUID
    serial_number: str
    user_id: UUID
    total_amount: float
    date_of_issue: datetime
    payment_id: UUID | None

    class Config:
        orm_mode = True


class InvoicesPublic(SQLModel):
    data: list[InvoicePublic]
    count: int


class InvoiceProducts(SQLModel, table=True):
    invoice_id: UUID = Field(foreign_key="invoice.id", primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", primary_key=True)


class InvoiceBase(SQLModel, table=False):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=255)
    owner_id: UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="invoice")


class InvoiceUpdate(InvoiceBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


class Payment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: str = Field(max_length=255)
    amount: float = Field(default=0)
    rest: float = Field(default=0)
    status: str = Field(max_length=255, default="pending")
    product_id: UUID | None = Field(default=None, foreign_key="product.id")
    product: Optional["Product"] = Relationship(back_populates="payments")
    invoice: Optional["Invoice"] = Relationship(back_populates="payment")


class Product(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=255)
    price: float = Field(default=0)
    stock: int = Field(default=0)
    summary: str | None = Field(max_length=255)
    # Прямая связь с Invoice (один к многим)
    invoice_id: UUID | None = Field(
        default=None, foreign_key="invoice.id", nullable=True, ondelete="CASCADE"
    )
    # Связь с платежами:
    payments: list[Payment] = Relationship(back_populates="product")


class Invoice(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    serial_number: str = Field(max_length=255)
    user_id: UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    total_amount: float = Field(default=0)
    rest: float = Field(default=0)
    date_of_issue: datetime = Field(default_factory=datetime.now)
    payment_id: UUID | None = Field(default=None, foreign_key="payment.id")
    payment: Payment | None = Relationship(back_populates="invoice")
    # Если требуется связь "Invoice → Product" через промежуточную таблицу:
    products: list[Product] = Relationship(link_model=InvoiceProducts)
    created_at: datetime = Field(default_factory=datetime.now)


class ProductCreateRequest(BaseModel):
    name: str
    price: Decimal
    stock: int


class PaymentCreateRequest(BaseModel):
    type: Literal["cash", "cashless"]
    amount: Decimal


class InvoiceCreateRequest(BaseModel):
    products: list[ProductCreateRequest]
    payment: PaymentCreateRequest


class ProductResponse(BaseModel):
    name: str
    price: Decimal
    stock: int
    total: Decimal
    rest: Decimal

    class Config:
        orm_mode = True


class PaymentResponse(BaseModel):
    type: Literal["cash", "cashless"]
    amount: Decimal

    class Config:
        orm_mode = True


class InvoiceResponse(BaseModel):
    id: UUID
    products: list[ProductResponse]
    payment: PaymentResponse | None  # Сделать поле опциональным
    total_amount: Decimal  # Общая сумма накладной
    rest: Decimal  # Остаток (например, сдача)
    created_at: datetime

    class Config:
        orm_mode = True
