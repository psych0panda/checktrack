import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.main import app
from app.models import Invoice, Payment, Product, User
from app.tests.utils.utils import random_email

client = TestClient(app)


def test_read_invoices(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
):
    # Создаем тестового пользователя с уникальным email
    user = User(
        id=uuid.uuid4(),
        email=random_email(),
        hashed_password=get_password_hash("password"),
        is_superuser=False,
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Создаем тестовую накладную
    invoice = Invoice(
        id=uuid.uuid4(),
        serial_number="INV-001",
        user_id=user.id,
        total_amount=100.0,
        date_of_issue=datetime.now(),
    )
    db.add(invoice)
    db.commit()

    # Тестируем получение накладных
    response = client.get(
        f"{settings.API_V1_STR}/invoice/{invoice.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(invoice.id)
    assert response.json()["serial_number"] == invoice.serial_number
    assert response.json()["total_amount"] == invoice.total_amount

    # Удаляем связь накладной с пользователем
    db.delete(invoice)
    db.commit()
    db.delete(user)
    db.commit()


def test_read_invoice_unauthorized(client: TestClient, db: Session):
    # Создаем тестового пользователя с уникальным email
    user = User(
        id=uuid.uuid4(),
        email=random_email(),
        hashed_password=get_password_hash("password"),
        is_superuser=False,
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Создаем тестовую накладную
    invoice = Invoice(
        id=uuid.uuid4(),
        serial_number="INV-001",
        user_id=user.id,
        total_amount=100.0,
        date_of_issue=datetime.now(),
    )
    db.add(invoice)
    db.commit()

    # Тестируем получение накладной анонимным пользователем
    response = client.get(f"{settings.API_V1_STR}/invoice/{invoice.id}")
    assert (
        response.status_code == 401
    )  # Ожидаем, что анонимный пользователь получит ошибку 401 Unauthorized

    # Удаляем связь накладной с пользователем
    db.delete(invoice)
    db.commit()
    db.delete(user)
    db.commit()


def test_print_invoice(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
):
    # Создаем тестового пользователя с уникальным email
    user = User(
        id=uuid.uuid4(),
        email=random_email(),
        hashed_password=get_password_hash("password"),
    )
    db.add(user)
    db.commit()

    # Создаем тестовую накладную
    invoice = Invoice(
        id=uuid.uuid4(),
        serial_number="INV-001",
        user_id=user.id,
        total_amount=100.0,
        date_of_issue=datetime.now(),
    )
    db.add(invoice)
    db.commit()

    # Создаем тестовый продукт
    product = Product(
        id=uuid.uuid4(),
        title="Test Product",
        price=50.0,
        stock=2,
        invoice_id=invoice.id,
    )
    db.add(product)
    db.commit()

    # Создаем тестовый платеж
    payment = Payment(id=uuid.uuid4(), type="cash", amount=100.0, invoice_id=invoice.id)
    db.add(payment)
    db.commit()

    # Тестируем печать накладной
    response = client.get(
        f"{settings.API_V1_STR}/invoice/{invoice.id}/print",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200


def test_read_invoices_with_filters(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
):
    # Создаем тестового пользователя с уникальным email
    user = User(
        id=uuid.uuid4(),
        email=random_email(),
        hashed_password=get_password_hash("password"),
    )
    db.add(user)
    db.commit()

    # Создаем тестовую накладную
    invoice = Invoice(
        id=uuid.uuid4(),
        serial_number="INV-001",
        user_id=user.id,
        total_amount=100.0,
        date_of_issue=datetime.now(),
    )
    db.add(invoice)
    db.commit()

    # Тестируем получение накладных с фильтром по дате
    response = client.get(
        f"{settings.API_V1_STR}/invoice/",
        params={"from_date": datetime.now().isoformat()},
        headers=superuser_token_headers,
    )  # noqa
    assert response.status_code == 200
    assert response.json() == {"data": [], "count": 0}

    # Тестируем получение накладных с фильтром по общей сумме
    response = client.get(
        f"{settings.API_V1_STR}/invoice/",
        params={"min_total": 50.0},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    for inv in response.json()["data"]:
        assert inv["total_amount"] >= 50.0

    # Тестируем получение накладных с фильтром по типу оплаты
    response = client.get(
        f"{settings.API_V1_STR}/invoice/",
        params={"payment_type": "cash"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    for inv in response.json()["data"]:
        assert inv["payment_type"] == "cash"


def test_delete_invoice(db: Session):
    # Создаем тестового пользователя с уникальным email
    user = User(
        id=uuid.uuid4(),
        email=random_email(),
        hashed_password=get_password_hash("password"),
    )
    db.add(user)
    db.commit()

    # Создаем тестовую накладную
    invoice = Invoice(
        id=uuid.uuid4(),
        serial_number="INV-001",
        user_id=user.id,
        total_amount=100.0,
        date_of_issue=datetime.now(),
    )
    db.add(invoice)
    db.commit()

    # Создаем тестовый продукт
    product = Product(
        id=uuid.uuid4(),
        title="Test Product",
        price=50.0,
        stock=2,
        invoice_id=invoice.id,
    )
    db.add(product)
    db.commit()

    # Удаляем накладную
    db.delete(invoice)
    db.commit()

    # Проверяем, что накладная удалена
    result = db.execute(select(Invoice).filter(Invoice.id == invoice.id)).first()
    deleted_invoice = result[0] if result else None
    assert deleted_invoice is None

    # Удаляем пользователя
    db.delete(user)
    db.commit()
