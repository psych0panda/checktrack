import io
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader
from sqlmodel import func, select
from weasyprint import HTML

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Invoice,
    InvoiceCreateRequest,
    InvoicePublic,
    InvoiceResponse,
    InvoicesPublic,
    Message,
    Payment,
    Product,
)
from app.utils import generate_invoice_serial_number

router = APIRouter(prefix="/invoice", tags=["invoice"])

template_dir = "app/templates"
file_loader = FileSystemLoader(template_dir)
env = Environment(loader=file_loader)


@router.get("/", response_model=InvoicesPublic)
def read_invoices(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    from_date: datetime | None = Query(
        None, description="Отфильтровать чеки, созданные не ранее указанной даты"
    ),
    min_total: float | None = Query(
        None, description="Показать чеки с суммой покупки не меньшей"
    ),
    payment_type: str | None = Query(
        None, description="Показать чеки с определённым типом оплаты (cash / cashless)"
    ),
) -> InvoicesPublic:
    """
    Получить список накладных.
    Ars:
        skip (int): пропустить указанное количество записей
        limit (int): количество записей для отображения
        from_date (datetime): фильтр по дате создания
        min_total (float): фильтр по общей сумме
        payment_type (str): фильтр по типу оплаты
    Returns:
        InvoicesPublic: список накладных

    """
    filters = []

    # Фильтр по дате создания (date_of_issue)
    if from_date:
        filters.append(Invoice.date_of_issue >= from_date)

    # Фильтр по общей сумме
    if min_total is not None:
        filters.append(Invoice.total_amount >= min_total)

    # Если пользователь не суперюзер – фильтруем по owner_id
    if not current_user.is_superuser:
        filters.append(Invoice.owner_id == current_user.id)

    # Если фильтр по типу оплаты задан, выполняем join с Payment
    if payment_type:
        statement = (
            select(Invoice)
            .join(Payment, isouter=True)
            .where(Payment.type == payment_type)
        )
        if filters:
            statement = statement.where(*filters)
    else:
        statement = select(Invoice)
        if filters:
            statement = statement.where(*filters)

    # Получаем общее количество записей (без offset/limit)
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    statement = statement.offset(skip).limit(limit)
    invoices = session.exec(statement).all()
    invoice_public_list = [InvoicePublic.from_orm(inv) for inv in invoices]
    return InvoicesPublic(data=invoice_public_list, count=count)


@router.get("/{id}", response_model=InvoicePublic)
def read_invoice(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Получить накладную по ID.
    Args:
        id (uuid.UUID): ID накладной
    Returns:
        Invoice: накладная
    """
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not current_user.is_superuser and (invoice.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return invoice


@router.post("/", response_model=InvoiceResponse)
def create_invoice(
    session: SessionDep, current_user: CurrentUser, invoice_in: InvoiceCreateRequest
) -> Any:
    """
    Create new invoice.
    Args:
        invoice_in (InvoiceCreateRequest): данные для создания новой накладной
    Returns:
        Invoice: созданная накладная
    """
    user_id = current_user.id
    serial_number = generate_invoice_serial_number()

    # Создаем накладную базового уровня. Поля total и rest можно вычислить позже.
    invoice = Invoice(serial_number=serial_number, user_id=user_id, total_amount=0)
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    products = session.query(Product).filter(Product.invoice_id == invoice.id).all()
    # Обработка продуктов: создаем объекты Product для каждого элемента из invoice_in.products
    total = 0
    rest = 0
    products = []
    if rest > invoice_in.payment.amount:
        raise HTTPException(status_code=400, detail="Not enough payment amount")
    for prod in invoice_in.products:
        product_total = prod.price * prod.stock
        total += product_total
        rest += product_total - invoice_in.payment.amount
        product = Product(
            invoice_id=invoice.id,
            title=prod.name,
            price=prod.price,
            stock=prod.stock,
            total=product_total,  # Если поле total предусмотрено в модели Product
            summary=product_total,
        )
        session.add(product)
        products.append(product)

    # Обработка платежа: создаем объект Payment
    rest = (
        invoice_in.payment.amount - total if invoice_in.payment.amount >= total else 0
    )
    for _ in products:
        payment = Payment(
            invoice_id=invoice.id,
            type=invoice_in.payment.type,
            amount=invoice_in.payment.amount,
            rest=rest,
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)

    # Пересчитываем итоговые суммы, например, остаток (rest)
    invoice.total_amount = total
    invoice.rest = payment.rest
    invoice.payment_id = payment.id
    invoice.total_amount = invoice_in.payment.amount
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    return invoice


@router.delete("/{id}")
def delete_invoice(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Удалить накладную.
    Args:
        id (uuid.UUID): ID накладной
    Returns:
        Message: сообщение об успешном удалении
    """
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not current_user.is_superuser and (invoice.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(invoice)
    session.commit()
    return Message(message="Invoice deleted successfully")


def generate_receipt_text(invoice: Invoice, products: Product, width: int) -> str:
    """
    Генерация текста чека.
    Args:
        invoice (Invoice): накладная
        products (Product): список продуктов
        width (int): количество символов в строке
    Returns:
        str: текст чека
    """
    # Пример настройки заголовка, разделителей и форматирования.
    shop_name = "ФОП Джонсонюк Борис"
    divider = "=" * width
    sub_divider = "-" * width
    lines = []

    # Заголовок
    lines.append(shop_name.center(width))
    lines.append(divider)
    lines.append(f"ЧЕК №{invoice.serial_number}".center(width))
    lines.append(divider)

    # Проходим по списку продуктов, предполагая, что каждый продукт имеет:
    # - title: название,
    # - stock: количество (тип float),
    # - price: цену за единицу (float)
    # Вычисляем итог для каждой позиции: total = stock * price.
    total_products_amount = sum(product.price * product.stock for product in products)

    # Проверяем, хватает ли уплаченных средств
    if invoice.total_amount < total_products_amount:
        raise HTTPException(status_code=400, detail="Not enough payment amount")
    rest = invoice.total_amount - total_products_amount
    for prod in products:
        total_value = prod.price * prod.stock
        # Первая строка: количество x цена и итог по позиции (например: "3.00 x 298.00     894.00")
        line1 = f"{prod.stock:.2f} x {prod.price:.2f}"
        line1 = f"{line1:<{width-10}}{total_value:>10.2f}"
        # Вторая строка: название продукта и тот же итог, выровненный по правому краю.
        line2 = f"{prod.title:<{width-10}}{total_value:>10.2f}"
        lines.append(line1)
        lines.append(line2)
        lines.append(sub_divider)

    # Детали оплаты и чека
    lines.append(divider)
    lines.append("СУМА".ljust(width - 10) + f"{total_products_amount:>10.2f}")
    # Если имеется информация про оплату, выводим её тип и сумму
    if invoice.payment:
        lines.append(
            f"{invoice.payment.type}".ljust(width - 10)
            + f"{invoice.total_amount:>10.2f}"
        )
    lines.append("РЕШТА".ljust(width - 10) + f"{rest:>10.2f}")
    lines.append(divider)

    # Дата создания чека и сообщение
    date_line = invoice.date_of_issue.strftime("%d.%m.%Y %H:%M")
    lines.append(date_line.center(width))
    lines.append("Дякуємо за покупку!".center(width))
    return "\n".join(lines)


@router.get("/{id}/print", response_class=PlainTextResponse, response_model=None)
def print_invoice(
    id: uuid.UUID,
    session: SessionDep,
    width: int = Query(40, description="Кількість символів у рядку"),
) -> str:
    """
    Распечатка чек.
    Args:
        id (uuid.UUID): ID накладной
        width (int): количество символов в строке
    Returns:
        str: текст чека
    """
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    products = session.exec(
        select(Product).where(Product.invoice_id == invoice.id)
    ).all()

    total_products_amount = sum(product.price * product.stock for product in products)
    if invoice.total_amount < total_products_amount:
        raise HTTPException(status_code=400, detail="Not enough payment amount")
    rest = invoice.total_amount - total_products_amount

    # Загрузка шаблона
    template = env.get_template("receipt_template.txt")

    # Данные для шаблона
    data = {
        "shop_name": "ФОП Джонсонюк Борис",
        "divider": "=" * width,
        "sub_divider": "-" * width,
        "invoice": invoice,
        "products": products,
        "total_products_amount": total_products_amount,
        "rest": rest,
        "width": width,
    }

    # Рендеринг шаблона
    receipt_text = template.render(data)

    return receipt_text


@router.get("/{id}/print/pdf", response_class=StreamingResponse)
def print_invoice_pdf(
    id: uuid.UUID,
    session: SessionDep,
    width: int = Query(40, description="Кількість символів у рядку"),
) -> StreamingResponse:
    """
    Распечатка чек в формате PDF.
    Args:
        id (uuid.UUID): ID накладной
        width (int): количество символов в строке
    Returns:
        StreamingResponse: PDF файл чека
    """
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    products = session.exec(
        select(Product).where(Product.invoice_id == invoice.id)
    ).all()

    total_products_amount = sum(product.price * product.stock for product in products)
    if invoice.total_amount < total_products_amount:
        raise HTTPException(status_code=400, detail="Not enough payment amount")
    rest = invoice.total_amount - total_products_amount

    # Загрузка шаблона
    template = env.get_template("receipt_template.html")

    # Данные для шаблона
    data = {
        "shop_name": "ФОП Джонсонюк Борис",
        "divider": "=" * width,
        "sub_divider": "-" * width,
        "invoice": invoice,
        "products": products,
        "total_products_amount": total_products_amount,
        "rest": rest,
        "width": width,
    }

    # Рендеринг шаблона
    receipt_html = template.render(data)

    # Генерация PDF
    pdf = HTML(string=receipt_html).write_pdf()

    # Возвращаем PDF файл для скачивания
    headers = {
        "Content-Disposition": f'attachment; filename="invoice_{invoice.serial_number}.pdf"'
    }
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf", headers=headers
    )
