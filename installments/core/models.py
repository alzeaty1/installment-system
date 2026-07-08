import calendar
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum


MAX_MONEY_AMOUNT = Decimal("100000.00")
MONEY_VALIDATORS = [
    MinValueValidator(Decimal("0.00")),
    MaxValueValidator(MAX_MONEY_AMOUNT),
]
DAY_OF_MONTH_VALIDATORS = [MinValueValidator(1), MaxValueValidator(31)]


def _add_months(source_date, months, due_day=1):
    """Add months to a date, clamping the day to the last day of the target month."""
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return source_date.replace(year=year, month=month, day=min(int(due_day), last_day))


class Account(models.Model):
    name = models.CharField(max_length=255, verbose_name="اسم الحساب")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "الحسابات"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Customer(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="الاسم")
    phone = models.CharField(max_length=50, verbose_name="رقم الهاتف")
    national_id = models.CharField(max_length=50, blank=True, verbose_name="الرقم القومي")
    address = models.TextField(blank=True, verbose_name="العنوان")
    whatsapp = models.CharField(max_length=50, blank=True, verbose_name="واتساب")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "عميل"
        verbose_name_plural = "العملاء"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class SupplierCategory(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="الاسم")

    class Meta:
        verbose_name = "فئة تاجر"
        verbose_name_plural = "فئات التجار"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="الاسم")
    phone = models.CharField(max_length=50, verbose_name="رقم الهاتف")
    address = models.TextField(blank=True, verbose_name="العنوان")
    category = models.ForeignKey(
        SupplierCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="الفئة",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "تاجر"
        verbose_name_plural = "التجار"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="الاسم")

    class Meta:
        verbose_name = "فئة منتج"
        verbose_name_plural = "فئات المنتجات"

    def __str__(self):
        return self.name


class ProductType(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="النوع")

    class Meta:
        verbose_name = "نوع منتج"
        verbose_name_plural = "أنواع المنتجات"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    name = models.CharField(max_length=255, verbose_name="الاسم")
    brand = models.CharField(max_length=255, blank=True, verbose_name="الماركة")
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="الفئة",
    )
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="النوع",
    )
    model_name = models.CharField(max_length=255, blank=True, verbose_name="الموديل")
    estimated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=MONEY_VALIDATORS,
        verbose_name="السعر التقديري",
    )
    image = models.ImageField(upload_to="products/", blank=True, verbose_name="صورة المنتج")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class SupplierPurchase(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="التاجر",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_purchases",
        verbose_name="العميل",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_records",
        verbose_name="المنتج",
    )
    contract = models.ForeignKey(
        "Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_records",
        verbose_name="العقد",
    )
    product_name = models.CharField(max_length=255, verbose_name="اسم المنتج")
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="سعر الشراء",
    )
    purchase_date = models.DateField(verbose_name="تاريخ الشراء")
    image = models.ImageField(upload_to="supplier_purchases/", blank=True, verbose_name="صورة الفاتورة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "عملية شراء منتج"
        verbose_name_plural = "سجل شراء المنتجات"
        ordering = ["-purchase_date"]

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
        (STATUS_ACTIVE, "نشط"),
        (STATUS_COMPLETED, "مكتمل"),
        (STATUS_OVERDUE, "متأخر"),
        (STATUS_CANCELLED, "ملغي"),
    ]

    contract_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name="رقم العقد")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="العميل")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="التاجر",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="المنتج",
    )
    product_name = models.CharField(max_length=255, verbose_name="اسم المنتج")
    actual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="التكلفة الفعلية",
    )
    customer_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="سعر العميل",
    )
    down_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=MONEY_VALIDATORS,
        verbose_name="مقدم",
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="المبلغ المتبقي",
    )
    interest_rate = models.DecimalField(max_digits=7, decimal_places=2, verbose_name="نسبة الفائدة")
    total_interest = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="إجمالي الفائدة",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="إجمالي المبلغ",
    )
    months_count = models.IntegerField(verbose_name="عدد الأشهر")
    installment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="قيمة القسط",
    )
    calculation_mode = models.CharField(
        max_length=1,
        choices=CALCULATION_MODE_CHOICES,
        verbose_name="نوع الحساب",
    )
    start_date = models.DateField(verbose_name="تاريخ البداية")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاريخ نهاية العقد")
    payment_due_day = models.IntegerField(
        default=1,
        validators=DAY_OF_MONTH_VALIDATORS,
        verbose_name="يوم الاستحقاق",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name="الحالة",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "عقد"
        verbose_name_plural = "العقود"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start_date"]),
        ]

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
        if not self.end_date and self.start_date and self.months_count:
            self.end_date = _add_months(self.start_date, self.months_count, self.payment_due_day)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.contract_number

    @property
    def total_paid(self):
        """Sum of all installment paid_amount for this contract."""
        return self.installments.aggregate(
            s=Sum("paid_amount", default=Decimal("0.00"))
        )["s"]

    @property
    def remaining_balance(self):
        """Total amount still owed on this contract."""
        return self.total_amount - self.total_paid

    @property
    def is_complete(self):
        """True when total paid covers total amount."""
        return self.total_paid >= self.total_amount

    @property
    def is_on_track(self):
        """True if total paid >= sum of base amounts of all due installments."""
        from datetime import date
        expected = self.installments.filter(
            due_date__lte=date.today()
        ).aggregate(
            s=Sum("amount", default=Decimal("0.00"))
        )["s"]
        return self.total_paid >= expected

    @property
    def progress_percentage(self):
        """Progress based on actual money paid vs total contract value."""
        if self.total_amount <= 0:
            return 0
        pct = (self.total_paid / self.total_amount) * 100
        return min(round(pct, 1), 100)


class Installment(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_LATE = "late"
    STATUS_PARTIAL = "partial"
    STATUS_OVERPAID = "overpaid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "معلق"),
        (STATUS_PAID, "مدفوع"),
        (STATUS_LATE, "متأخر"),
        (STATUS_PARTIAL, "جزئي"),
        (STATUS_OVERPAID, "زيادة"),
    ]

    PAYMENT_CASH = "cash"
    PAYMENT_WALLET = "wallet"
    PAYMENT_INSTAPAY = "instapay"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, "نقدي"),
        (PAYMENT_WALLET, "محفظة"),
        (PAYMENT_INSTAPAY, "إنستاباي"),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name="العقد",
    )
    installment_number = models.IntegerField(verbose_name="رقم القسط")
    due_date = models.DateField(verbose_name="تاريخ الاستحقاق")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="المبلغ",
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=MONEY_VALIDATORS,
        verbose_name="المبلغ المدفوع",
    )
    paid_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الدفع")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="الحالة",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        verbose_name="طريقة الدفع",
    )
    transfer_sender_account = models.CharField(max_length=100, blank=True, verbose_name="رقم المحفظة/الحساب المرسل منه")
    transfer_sender_name = models.CharField(max_length=255, blank=True, verbose_name="اسم المرسل")
    transfer_image = models.ImageField(upload_to="transfers/", blank=True, verbose_name="صورة التحويل")
    received_by = models.CharField(max_length=255, blank=True, verbose_name="المستلم (كاش)")
    receiver = models.ForeignKey(
        "Receiver", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="installments",
        verbose_name="المستلم",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "قسط"
        verbose_name_plural = "الأقساط"
        ordering = ["installment_number"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return f"{self.contract} - {self.installment_number}"


class Expense(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    title = models.CharField(max_length=255, verbose_name="العنوان")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=MONEY_VALIDATORS,
        verbose_name="المبلغ",
    )
    expense_date = models.DateField(verbose_name="تاريخ المصروف")
    category = models.CharField(max_length=255, blank=True, verbose_name="الفئة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصروفات"
        ordering = ["-expense_date"]

    def __str__(self):
        return self.title


class Notification(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    TYPE_REMINDER = "reminder"
    TYPE_OVERDUE = "overdue"
    TYPE_INFO = "info"

    NOTIFICATION_TYPE_CHOICES = [
        (TYPE_REMINDER, "تذكير"),
        (TYPE_OVERDUE, "متأخر"),
        (TYPE_INFO, "معلومة"),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="العقد",
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="القسط",
    )
    message = models.TextField(verbose_name="الرسالة")
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        verbose_name="نوع التنبيه",
    )
    is_read = models.BooleanField(default=False, verbose_name="مقروء")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "تنبيه"
        verbose_name_plural = "التنبيهات"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:50]


class Settings(models.Model):
    default_interest_rate = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("3.5"),
        verbose_name="النسبة الشهرية الافتراضية %",
    )
    default_payment_due_day = models.IntegerField(
        default=1,
        validators=DAY_OF_MONTH_VALIDATORS,
        verbose_name="يوم الاستحقاق الافتراضي",
    )
    business_name = models.CharField(
        max_length=255,
        default="نظام التقسيط",
        verbose_name="اسم النشاط",
    )
    whatsapp_enabled = models.BooleanField(default=True, verbose_name="تفعيل واتساب")

    class Meta:
        verbose_name = "إعدادات"
        verbose_name_plural = "الإعدادات"

    def __str__(self):
        return self.business_name


class ActivityLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_PAYMENT = "payment"
    ACTION_RESET = "reset"
    ACTION_MARK_COMPLETED = "mark_completed"
    ACTION_OTHER = "other"

    ACTION_CHOICES = [
        (ACTION_CREATE, "إضافة"),
        (ACTION_UPDATE, "تعديل"),
        (ACTION_DELETE, "حذف"),
        (ACTION_PAYMENT, "دفع"),
        (ACTION_RESET, "إلغاء دفع"),
        (ACTION_MARK_COMPLETED, "تعليم مكتمل"),
        (ACTION_OTHER, "أخرى"),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب")
    user = models.CharField(max_length=150, blank=True, verbose_name="المستخدم")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="نوع الحركة")
    model_name = models.CharField(max_length=50, verbose_name="النموذج")
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="معرف الكائن")
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="وصف الكائن")
    description = models.TextField(verbose_name="الوصف")
    previous_value = models.JSONField(null=True, blank=True, verbose_name="القيمة السابقة")
    new_value = models.JSONField(null=True, blank=True, verbose_name="القيمة الجديدة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الحركة")

    class Meta:
        verbose_name = "سجل حركة"
        verbose_name_plural = "سجل الحركات"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.model_name} - {self.created_at}"


class Receiver(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE,
        related_name="receivers", verbose_name="الحساب"
    )
    name = models.CharField(max_length=100, verbose_name="الاسم")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")

    class Meta:
        unique_together = ("account", "name")
        ordering = ["name"]
        verbose_name = "مستلم"
        verbose_name_plural = "المستلمون"

    def __str__(self):
        return self.name



