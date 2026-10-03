from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("courses_module", "0003_alter_course_allowed_fields_and_more")]
    operations = [
        migrations.AddField(model_name="courseenrollment", name="first_viewed_at", field=models.DateTimeField(blank=True, null=True, verbose_name="اولین مشاهده")),
        migrations.AddField(model_name="courseenrollment", name="last_viewed_at", field=models.DateTimeField(blank=True, null=True, verbose_name="آخرین مشاهده")),
        migrations.AddField(model_name="courseenrollment", name="view_count", field=models.PositiveIntegerField(default=0, verbose_name="تعداد مشاهده")),
    ]
