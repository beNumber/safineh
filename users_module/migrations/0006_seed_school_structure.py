from django.db import migrations


PROVINCES = {
    "hormozgan": "هرمزگان",
    "sistan": "سیستان و بلوچستان",
    "kerman": "کرمان",
}

SCHOOLS = {
    "hormozgan": ("هادی", "برهان"),
    "sistan": ("سیستان",),
    "kerman": ("کرمان",),
}

GRADES = ("پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم")
GENERAL_GRADES = {"پنجم", "ششم", "هفتم", "هشتم", "نهم"}
FIELDS = ("ریاضی", "تجربی", "انسانی")


def seed_school_structure(apps, schema_editor):
    Province = apps.get_model("users_module", "Province")
    School = apps.get_model("users_module", "School")
    Grade = apps.get_model("users_module", "Grade")
    FieldOfStudy = apps.get_model("users_module", "FieldOfStudy")

    provinces = {}
    for code in PROVINCES:
        province, _ = Province.objects.get_or_create(name=code)
        provinces[code] = province

    legacy_hadi = School.objects.filter(
        province=provinces["hormozgan"], name__iexact="hadi"
    ).first()
    if legacy_hadi and not School.objects.filter(
        province=provinces["hormozgan"], name="هادی"
    ).exists():
        legacy_hadi.name = "هادی"
        legacy_hadi.save(update_fields=["name"])

    for province_code, school_names in SCHOOLS.items():
        province = provinces[province_code]
        for school_name in school_names:
            school, _ = School.objects.get_or_create(
                province=province,
                name=school_name,
            )
            for grade_title in GRADES:
                grade, _ = Grade.objects.get_or_create(
                    school=school,
                    title=grade_title,
                    defaults={"is_active": True},
                )
                if not grade.is_active:
                    grade.is_active = True
                    grade.save(update_fields=["is_active"])

                field_titles = ("عمومی",) if grade_title in GENERAL_GRADES else FIELDS
                for field_title in field_titles:
                    field, _ = FieldOfStudy.objects.get_or_create(
                        grade=grade,
                        title=field_title,
                        defaults={"is_active": True},
                    )
                    if not field.is_active:
                        field.is_active = True
                        field.save(update_fields=["is_active"])


class Migration(migrations.Migration):
    dependencies = [
        ("users_module", "0005_alter_access_options_remove_fieldofstudy_code_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="school",
            options={
                "verbose_name": "مدرسه",
                "verbose_name_plural": "مدارس",
            },
        ),
        migrations.RunPython(seed_school_structure, migrations.RunPython.noop),
    ]
