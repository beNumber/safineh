from django.db import migrations, models


def remove_legacy_lessons(apps, schema_editor):
    apps.get_model("dashboard_module", "ModuleAvailability").objects.filter(code="lessons").delete()


class Migration(migrations.Migration):
    dependencies = [("dashboard_module", "0002_presence")]

    operations = [
        migrations.RunPython(remove_legacy_lessons, migrations.RunPython.noop),
        migrations.AlterField(model_name="moduleavailability", name="code", field=models.CharField(
            choices=[("question_bank", "بانک سؤالات"), ("courses", "دوره‌ها و درس‌ها"), ("quizzes", "آزمون‌ها")],
            max_length=30, unique=True,
        )),
    ]
