from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("courses_module", "0004_courseenrollment_view_tracking")]

    operations = [
        migrations.AddField(model_name="coursesection", name="description", field=models.TextField(blank=True, null=True)),
        migrations.AddField(model_name="coursesection", name="is_active", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="courseepisode", name="description", field=models.TextField(blank=True, null=True)),
        migrations.AddField(model_name="courseepisode", name="is_active", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="courseepisode", name="url", field=models.URLField(blank=True, max_length=1000, null=True)),
        migrations.AddField(model_name="courseepisode", name="created_at", field=models.DateTimeField(auto_now_add=True, null=True)),
        migrations.CreateModel(name="CourseResource", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=255)),
            ("resource_type", models.CharField(choices=[("video", "ویدیو"), ("image", "تصویر"), ("pdf", "PDF")], max_length=10)),
            ("file", models.FileField(blank=True, null=True, upload_to="courses/resources/")),
            ("url", models.URLField(blank=True, max_length=1000)),
            ("order", models.PositiveIntegerField(default=1)),
            ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resources", to="courses_module.course")),
        ], options={"ordering": ["order", "created_at"]}),
    ]
