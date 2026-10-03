from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard_module", "0001_moduleavailability"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name="PresencePeak", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("day", models.DateField(unique=True)),
            ("count", models.PositiveIntegerField(default=0)),
            ("recorded_at", models.DateTimeField()),
        ]),
        migrations.CreateModel(name="UserPresence", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("last_seen", models.DateTimeField(db_index=True)),
            ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="site_presence", to=settings.AUTH_USER_MODEL)),
        ]),
    ]
