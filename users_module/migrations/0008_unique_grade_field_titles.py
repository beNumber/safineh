from django.db import migrations


def normalize_title(value):
    return " ".join(value.replace("ي", "ی").replace("ك", "ک").split())


def merge_curriculum_duplicates(apps, schema_editor):
    database = schema_editor.connection.alias
    tables = set(schema_editor.connection.introspection.table_names())

    def remap_references(target_model, duplicate_id, canonical_id):
        for related_model in apps.get_models(include_auto_created=True):
            if related_model._meta.db_table not in tables:
                continue
            for field in related_model._meta.local_fields:
                if not field.is_relation or field.remote_field.model != target_model:
                    continue
                rows = related_model.objects.using(database).filter(**{field.attname: duplicate_id})
                if related_model._meta.auto_created:
                    for row in rows:
                        values = {column.attname: getattr(row, column.attname)
                                  for column in related_model._meta.local_fields if not column.primary_key}
                        values[field.attname] = canonical_id
                        related_model.objects.using(database).get_or_create(**values)
                    rows.delete()
                else:
                    rows.update(**{field.attname: canonical_id})

    for model_name, parent_name in [("Grade", "school_id"), ("FieldOfStudy", "grade_id")]:
        model = apps.get_model("users_module", model_name)
        canonical = {}
        for item in list(model.objects.using(database).order_by("pk")):
            title = normalize_title(item.title)
            key = (getattr(item, parent_name), title)
            if key not in canonical:
                canonical[key] = item
                model.objects.using(database).filter(pk=item.pk).update(title=title)
                continue
            survivor = canonical[key]
            remap_references(model, item.pk, survivor.pk)
            if item.is_active and not survivor.is_active:
                model.objects.using(database).filter(pk=survivor.pk).update(is_active=True)
                survivor.is_active = True
            model.objects.using(database).filter(pk=item.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users_module", "0007_deactivate_legacy_school_values"),
        ("auth_module", "0008_consultant_ticket_student_gender_and_more"),
        ("courses_module", "0001_initial"),
        ("quiz_module", "0003_quizevent_alter_quiz_options_and_more"),
    ]
    operations = [
        migrations.RunPython(merge_curriculum_duplicates, migrations.RunPython.noop),
    ]
