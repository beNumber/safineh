from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("courses_module", "0005_course_content_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.CreateModel(name="CourseView", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("first_viewed_at", models.DateTimeField(default=django.utils.timezone.now)),
        ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="views", to="courses_module.course")),
        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="viewed_courses", to=settings.AUTH_USER_MODEL)),
    ], options={"constraints": [models.UniqueConstraint(fields=["course", "user"], name="unique_course_viewer")]})]
