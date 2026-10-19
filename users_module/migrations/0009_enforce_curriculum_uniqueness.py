from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users_module", "0008_unique_grade_field_titles")]
    operations = [
        migrations.AddConstraint(
            model_name="grade",
            constraint=models.UniqueConstraint(fields=("school", "title"), name="unique_grade_title_per_school"),
        ),
        migrations.AddConstraint(
            model_name="fieldofstudy",
            constraint=models.UniqueConstraint(fields=("grade", "title"), name="unique_field_title_per_grade"),
        ),
    ]
