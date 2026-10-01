from django.db import migrations


VALID_GRADES = {"پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم"}
GENERAL_GRADES = {"پنجم", "ششم", "هفتم", "هشتم", "نهم"}
ACADEMIC_FIELDS = {"ریاضی", "تجربی", "انسانی"}
TARGET_SCHOOLS = {"هادی", "برهان", "سیستان", "کرمان"}


def deactivate_legacy_values(apps, schema_editor):
    Grade = apps.get_model("users_module", "Grade")
    FieldOfStudy = apps.get_model("users_module", "FieldOfStudy")

    target_grades = Grade.objects.filter(school__name__in=TARGET_SCHOOLS)
    target_grades.exclude(title__in=VALID_GRADES).update(is_active=False)

    for grade in target_grades.filter(title__in=VALID_GRADES):
        valid_fields = {"عمومی"} if grade.title in GENERAL_GRADES else ACADEMIC_FIELDS
        FieldOfStudy.objects.filter(grade=grade).exclude(
            title__in=valid_fields
        ).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("users_module", "0006_seed_school_structure"),
    ]

    operations = [
        migrations.RunPython(deactivate_legacy_values, migrations.RunPython.noop),
    ]
