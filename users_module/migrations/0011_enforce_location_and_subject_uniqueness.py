from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users_module", "0010_merge_location_and_subject_duplicates")]
    operations = [
        migrations.AlterField(
            model_name="province", name="name",
            field=models.CharField(max_length=100, unique=True, choices=[
                ("hormozgan", "هرمزگان"), ("kerman", "کرمان"), ("sistan", "سیستان و بلوچستان"),
            ]),
        ),
        migrations.AddConstraint(
            model_name="subject",
            constraint=models.UniqueConstraint(fields=("field", "title"), name="unique_subject_title_per_field"),
        ),
    ]
