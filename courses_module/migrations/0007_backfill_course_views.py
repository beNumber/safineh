from django.db import migrations


def backfill_views(apps, schema_editor):
    Enrollment = apps.get_model("courses_module", "CourseEnrollment")
    View = apps.get_model("courses_module", "CourseView")
    for enrollment in Enrollment.objects.filter(first_viewed_at__isnull=False).iterator():
        View.objects.get_or_create(
            course_id=enrollment.course_id,
            user_id=enrollment.student_id,
            defaults={"first_viewed_at": enrollment.first_viewed_at},
        )


class Migration(migrations.Migration):
    dependencies = [("courses_module", "0006_course_view")]
    operations = [migrations.RunPython(backfill_views, migrations.RunPython.noop)]
