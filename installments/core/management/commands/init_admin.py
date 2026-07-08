from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create a default admin user if no users exist in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Username for the default admin (default: admin)",
        )
        parser.add_argument(
            "--password",
            default="admin123",
            help="Password for the default admin (default: admin123)",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        password = options["password"]

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING("يوجد مستخدم Admin بالفعل، لا حاجة لإنشاء حساب جديد.")
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"المستخدم '{username}' موجود بالفعل.")
            )
            return

        User.objects.create_superuser(username=username, password=password)
        self.stdout.write(
            self.style.SUCCESS(
                f"تم إنشاء حساب Admin بنجاح — اسم المستخدم: {username} | كلمة المرور: {password}\n"
                "يمكنك تغيير كلمة المرور من /admin/ في أي وقت."
            )
        )
