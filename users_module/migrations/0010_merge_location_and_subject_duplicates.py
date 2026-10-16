from django.db import migrations


def merge_duplicates(apps, schema_editor):
    database = schema_editor.connection.alias
    tables = set(schema_editor.connection.introspection.table_names())
    tree = {
        "users_module.province": ("users_module", "School", "province_id", "name"),
        "users_module.school": ("users_module", "Grade", "school_id", "title"),
        "users_module.grade": ("users_module", "FieldOfStudy", "grade_id", "title"),
        "users_module.fieldofstudy": ("users_module", "Subject", "field_id", "title"),
        "users_module.subject": ("questions_module", "Chapter", "subject_id", "name"),
        "questions_module.chapter": ("questions_module", "Topic", "chapter_id", "name"),
    }

    def normalized(value, province=False):
        text = " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").split())
        if province:
            text = {"هرمزگان": "hormozgan", "کرمان": "kerman", "سیستان": "sistan",
                    "سیستان و بلوچستان": "sistan"}.get(text.casefold(), text.casefold())
        return text

    def remap(model, duplicate, canonical):
        for related in apps.get_models(include_auto_created=True):
            if related._meta.db_table not in tables:
                continue
            for field in related._meta.local_fields:
                if not field.is_relation or field.remote_field.model != model:
                    continue
                rows = related.objects.using(database).filter(**{field.attname: duplicate.pk})
                if related._meta.label_lower == "auth_module.provincetrustee":
                    existing_users = related.objects.using(database).filter(province_id=canonical.pk).values("user_id")
                    rows.filter(user_id__in=existing_users).delete()
                if related._meta.auto_created:
                    for row in list(rows):
                        values = {column.attname: getattr(row, column.attname)
                                  for column in related._meta.local_fields if not column.primary_key}
                        values[field.attname] = canonical.pk
                        related.objects.using(database).get_or_create(**values)
                    rows.delete()
                else:
                    rows.update(**{field.attname: canonical.pk})

    def merge(model, duplicate, canonical):
        child_spec = tree.get(model._meta.label_lower)
        if child_spec:
            app_name, child_name, parent_key, title_key = child_spec
            child = apps.get_model(app_name, child_name)
            for item in list(child.objects.using(database).filter(**{parent_key: duplicate.pk}).order_by("pk")):
                targets = child.objects.using(database).filter(**{parent_key: canonical.pk}).order_by("pk")
                target = next((candidate for candidate in targets
                               if normalized(getattr(candidate, title_key)) == normalized(getattr(item, title_key))), None)
                if target:
                    merge(child, item, target)
                else:
                    child.objects.using(database).filter(pk=item.pk).update(**{parent_key: canonical.pk})
        remap(model, duplicate, canonical)
        if hasattr(duplicate, "is_active") and duplicate.is_active and not canonical.is_active:
            model.objects.using(database).filter(pk=canonical.pk).update(is_active=True)
            canonical.is_active = True
        model.objects.using(database).filter(pk=duplicate.pk).delete()

    for model_name, parent_key, title_key in [
        ("Province", None, "name"), ("School", "province_id", "name"),
        ("Grade", "school_id", "title"), ("FieldOfStudy", "grade_id", "title"),
        ("Subject", "field_id", "title"),
    ]:
        model = apps.get_model("users_module", model_name)
        groups = {}
        for item in model.objects.using(database).order_by("pk"):
            title = normalized(getattr(item, title_key), province=model_name == "Province")
            groups.setdefault((getattr(item, parent_key) if parent_key else None, title), []).append(item)
        for (_, title), members in groups.items():
            canonical = members[0]
            for duplicate in members[1:]:
                merge(model, duplicate, canonical)
            model.objects.using(database).filter(pk=canonical.pk).update(**{title_key: title})


class Migration(migrations.Migration):
    dependencies = [
        ("users_module", "0009_enforce_curriculum_uniqueness"),
        ("questions_module", "0009_alter_topic_options_examanswer_text_answer_and_more"),
    ]
    operations = [migrations.RunPython(merge_duplicates, migrations.RunPython.noop)]
