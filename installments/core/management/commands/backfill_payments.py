"""ترحيل دفعات الأقساط القديمة إلى جدول Payment (idempotent — آمن التكرار)."""
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Installment, Payment


class Command(BaseCommand):
    help = "ينشئ صف Payment واحد لكل قسط مدفوع وليس له صفوف دفعات بعد."

    def handle(self, *args, **options):
        installments = (
            Installment.objects.filter(paid_amount__gt=0)
            .select_related("receiver")
            .order_by("id")
        )
        created = 0
        skipped = 0
        for inst in installments.iterator():
            if Payment.objects.filter(installment=inst).exists():
                skipped += 1
                continue
            Payment.objects.create(
                account=inst.account,
                installment=inst,
                amount=inst.paid_amount,
                payment_method=inst.payment_method or "",
                paid_date=inst.paid_date,
                receiver=inst.receiver,
                received_by=inst.received_by or "",
                notes="ترحيل بيانات قديمة",
            )
            created += 1
        self.stdout.write(
            self.style.SUCCESS(f"تم إنشاء {created} صف دفعة (تخطي {skipped} له صفوف بالفعل).")
        )
