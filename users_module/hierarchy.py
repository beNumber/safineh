from .models import FieldOfStudy, Grade, School


def academic_hierarchy():
    return {
        "schools": [{"id": item.pk, "title": f"{item.name} · {item.province}"} for item in School.objects.select_related("province")],
        "grades": list(Grade.objects.filter(is_active=True).values("id", "title", "school_id")),
        "fields": list(FieldOfStudy.objects.filter(is_active=True, grade__is_active=True).values("id", "title", "grade_id")),
    }
