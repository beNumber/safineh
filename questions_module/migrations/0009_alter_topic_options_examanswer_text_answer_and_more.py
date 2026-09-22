from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("questions_module", "0008_examsession_question_type_and_more"),
    ]

    # شاخه موازی قبلی همان ساختار مسیر 0010 را دوباره می‌ساخت و روی
    # دیتابیس تازه باعث ایجاد جدول تکراری می‌شد. عملیات نهایی در 0010 است.
    operations = []
