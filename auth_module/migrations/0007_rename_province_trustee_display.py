from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth_module", "0006_remove_consultant_auth_module_consult_8e451c_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("STUDENT", "دانش‌آموز"),
                    ("CONSULTANT", "مشاور"),
                    ("PROVINCE_TRUSTEE", "مسئول منطقه"),
                    ("CONTENT_MODERATOR", "ناظر محتوا"),
                    ("ADMIN", "مدیر سیستم"),
                ],
                default="STUDENT",
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name="provincetrustee",
            options={
                "verbose_name": "مسئول منطقه",
                "verbose_name_plural": "مسئولان مناطق",
            },
        ),
    ]
