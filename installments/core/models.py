from decimal import Decimal

from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, unique=True)
    national_id = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    whatsapp = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SupplierCategory(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    address = models.TextField(blank=True)
    category = models.ForeignKey(
        SupplierCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    estimated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to="products/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SupplierPurchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=255)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_date = models.DateField()
    image = models.ImageField(upload_to="supplier_purchases/", blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product_name


class Contract(models.Model):
    MODE_A = "A"
    MODE_B = "B"
    MODE_C = "C"

    CALCULATION_MODE_CHOICES = [
        (MODE_A, "A"),
        (MODE_B, "B"),
        (MODE_C, "C"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    contract_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=255)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2)
    customer_price = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=7, decimal_places=2)
    total_interest = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    months_count = models.IntegerField()
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    calculation_mode = models.CharField(
        max_length=1,
        choices=CALCULATION_MODE_CHOICES,
    )
    start_date = models.DateField()
    payment_due_day = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.contract_number:
            last_contract = (
                Contract.objects.exclude(contract_number="")
                .order_by("-id")
                .first()
            )
            next_id = (last_contract.id + 1) if last_contract else 1
            self.contract_number = f"CON-{next_id:06d}"
            while Contract.objects.filter(
                contract_number=self.contract_number
            ).exists():
                next_id += 1
                self.contract_number = f"CON-{next_id:06d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.contract_number


class Installment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_LATE = "late"
    STATUS_PARTIAL = "partial"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_LATE, "Late"),
        (STATUS_PARTIAL, "Partial"),
    ]

    PAYMENT_CASH = "cash"
    PAYMENT_WALLET = "wallet"
    PAYMENT_INSTAPAY = "instapay"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, "Cash"),
        (PAYMENT_WALLET, "Wallet"),
        (PAYMENT_INSTAPAY, "Instapay"),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.IntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.contract} - {self.installment_number}"


class Expense(models.Model):
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    category = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Notification(models.Model):
    TYPE_REMINDER = "reminder"
    TYPE_OVERDUE = "overdue"
    TYPE_INFO = "info"

    NOTIFICATION_TYPE_CHOICES = [
        (TYPE_REMINDER, "Reminder"),
        (TYPE_OVERDUE, "Overdue"),
        (TYPE_INFO, "Info"),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message[:50]


class Settings(models.Model):
    default_interest_rate = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("3.5"),
    )
    default_payment_due_day = models.IntegerField(default=1)
    business_name = models.CharField(
        max_length=255,
        default="نظام التقسيط",
    )
    whatsapp_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.business_name


