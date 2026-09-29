from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses_module", "0007_backfill_course_views"),
        ("users_module", "0005_alter_access_options_remove_fieldofstudy_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="allowed_cities",
            field=models.ManyToManyField(blank=True, related_name="courses_allowed_cities", to="users_module.school", verbose_name="شهرهای مجاز"),
        ),
    ]
