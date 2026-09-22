import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="OnlineClass", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("title", models.CharField(max_length=150, verbose_name="عنوان کلاس")),
        ("description", models.TextField(blank=True, max_length=600, verbose_name="توضیحات")),
        ("meeting_url", models.URLField(verbose_name="لینک ورود")),
        ("starts_at", models.DateTimeField(db_index=True, verbose_name="زمان شروع")),
        ("ends_at", models.DateTimeField(db_index=True, verbose_name="زمان پایان")),
        ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_online_classes", to=settings.AUTH_USER_MODEL)),
    ], options={"verbose_name": "کلاس آنلاین", "verbose_name_plural": "کلاس‌های آنلاین", "ordering": ["starts_at"]})]
