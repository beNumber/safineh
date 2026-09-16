import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth_module", "0006_remove_consultant_auth_module_consult_8e451c_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentConsultantAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.CharField(blank=True, max_length=300, verbose_name="یادداشت داخلی")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان شروع")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")),
                ("assigned_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_counseling_assignments", to=settings.AUTH_USER_MODEL, verbose_name="تخصیص‌دهنده")),
                ("consultant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="counseling_assignments", to=settings.AUTH_USER_MODEL, verbose_name="مشاور")),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="consultant_assignment", to="auth_module.student", verbose_name="دانش‌آموز")),
            ],
            options={
                "verbose_name": "تخصیص دانش‌آموز به مشاور",
                "verbose_name_plural": "تخصیص دانش‌آموزان به مشاوران",
                "ordering": ["student__user__last_name", "student__user__first_name"],
            },
        ),
        migrations.AddIndex(
            model_name="studentconsultantassignment",
            index=models.Index(fields=["consultant", "updated_at"], name="counseling__consult_a76c76_idx"),
        ),
    ]
