from django.db import transaction

from .models import FieldOfStudy, Grade, Province, School, Subject, normalize_curriculum_title
from .spreadsheets import read_spreadsheet


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
GRADE_TITLES = dict(enumerate(["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم"], 1))
ALIASES = {"استان": "province", "مدرسه": "city", "شهر": "city", "نام مدرسه": "city",
           "پایه": "grade", "پایه تحصیلی": "grade", "کلاس": "grade", "نام کلاس": "grade",
           "رشته": "field", "رشته تحصیلی": "field", "درس": "subject", "نام درس": "subject"}
KINDS = {"grade": ("پایه‌ها", Grade), "field": ("رشته‌ها", FieldOfStudy), "subject": ("درس‌ها", Subject)}


def grade_title(value):
    text = normalize_curriculum_title(str(value or "")).translate(DIGITS)
    text = text.removeprefix("پایه ").strip()
    number = text.removesuffix(".0")
    return GRADE_TITLES.get(int(number), text) if number.isdigit() else text


def field_title(value):
    text = normalize_curriculum_title(str(value or ""))
    return {"ریاضی فیزیک": "ریاضی", "ریاضی و فیزیک": "ریاضی", "علوم تجربی": "تجربی",
            "علوم انسانی": "انسانی", "بدون رشته": "عمومی", "general": "عمومی"}.get(text, text)


def resolve_province(value):
    text = normalize_curriculum_title(str(value)).casefold()
    matches = [item for item in Province.objects.order_by("pk")
               if text in {normalize_curriculum_title(item.name).casefold(),
                           normalize_curriculum_title(item.get_name_display()).casefold()}]
    if not matches:
        raise ValueError("استان در سامانه تعریف نشده است.")
    return matches[0]


def resolve_school(province, value):
    title = normalize_curriculum_title(str(value))
    title = {"hadi": "هادی", "borhan": "برهان"}.get(title.casefold(), title)
    matches = [item for item in School.objects.filter(province=province).order_by("pk")
               if normalize_curriculum_title(item.name).casefold() == title.casefold()]
    if not matches:
        raise ValueError("مدرسه در استان انتخاب‌شده پیدا نشد.")
    return matches[0]


def resolve_student_field(school, grade_value, field_value):
    title = grade_title(grade_value)
    fields = FieldOfStudy.objects.filter(grade__school=school, grade__is_active=True, is_active=True).select_related("grade")
    matches = [item for item in fields if grade_title(item.grade.title) == title]
    if field_value:
        matches = [item for item in matches if field_title(item.title) == field_title(field_value)]
    if not matches:
        raise ValueError("ترکیب مدرسه، پایه و رشته پیدا نشد؛ از مقادیر مجاز یا پیش‌فرض‌های فرم استفاده کنید.")
    titles = {field_title(item.title) for item in matches}
    if len(titles) != 1:
        raise ValueError("این پایه چند رشته دارد؛ رشته را در Excel یا پیش‌فرض فرم مشخص کنید.")
    return min(matches, key=lambda item: item.pk)


def row_location(row, defaults):
    province_value = row.get("province") or defaults.get("default_province")
    province = province_value if isinstance(province_value, Province) else resolve_province(province_value) if province_value else None
    school_value = row.get("city") or defaults.get("default_school")
    if isinstance(school_value, School):
        school = school_value
        if province and school.province_id != province.pk:
            raise ValueError("مدرسه پیش‌فرض متعلق به استان این ردیف نیست.")
        province = province or school.province
    elif school_value:
        if not province:
            raise ValueError("برای انتخاب مدرسه، استان را هم مشخص کنید.")
        school = resolve_school(province, school_value)
    else:
        school = None
    return province, school


def import_curriculum(upload, kind, defaults=None):
    if kind not in KINDS:
        raise ValueError("نوع اطلاعات آموزشی معتبر نیست.")
    defaults = defaults or {}
    aliases = dict(ALIASES, title=kind)
    aliases.update({"عنوان": kind, "نام": kind})
    try:
        rows = read_spreadsheet(upload, aliases, required=[kind])
    except Exception as error:
        return [{"row": 1, "ok": False, "message": f"فایل قابل خواندن نیست: {error}"}]
    results = []
    for row in rows:
        try:
            with transaction.atomic():
                province, school = row_location(row, defaults)
                if not school and not defaults.get("apply_to_all"):
                    raise ValueError("مدرسه را مشخص کنید یا گزینه اعمال در همه مدارس را فعال کنید.")
                schools = School.objects.filter(pk=school.pk) if school else School.objects.all()
                if province:
                    schools = schools.filter(province=province)
                grade_value = row.get("grade") or defaults.get("default_grade")
                field_value = row.get("field") or defaults.get("default_field")
                title = normalize_curriculum_title(row.get(kind, ""))
                if not title:
                    raise ValueError("عنوان نمی‌تواند خالی باشد.")
                if len(title) > 100:
                    raise ValueError("عنوان حداکثر ۱۰۰ نویسه است.")
                if kind == "grade":
                    parents, parent_key, title = schools, "school", grade_title(title)
                elif kind == "field":
                    parents = Grade.objects.filter(school__in=schools, is_active=True)
                    if grade_value:
                        parents = parents.filter(title=grade_title(grade_value))
                    elif not defaults.get("apply_to_all"):
                        raise ValueError("پایه رشته را مشخص کنید.")
                    parent_key, title = "grade", field_title(title)
                else:
                    parents = FieldOfStudy.objects.filter(grade__school__in=schools, grade__is_active=True, is_active=True)
                    if grade_value:
                        parents = parents.filter(grade__title=grade_title(grade_value))
                    if field_value:
                        parents = parents.filter(title=field_title(field_value))
                    elif not defaults.get("apply_to_all"):
                        raise ValueError("رشته درس را مشخص کنید.")
                    parent_key = "field"
                parents = list(parents.order_by("pk"))
                if not parents:
                    raise ValueError("مسیر آموزشی مشخص‌شده پیدا نشد؛ ابتدا مدرسه، پایه و رشته را تعریف کنید.")
                created_count = 0
                for parent in parents:
                    item, created = KINDS[kind][1].objects.get_or_create(**{parent_key: parent, "title": title})
                    if not item.is_active:
                        item.is_active = True
                        item.save(update_fields=["is_active"])
                    created_count += created
            results.append({"row": row["_row_number"], "ok": True,
                            "message": f"{title}: {created_count} مورد جدید؛ {len(parents) - created_count} مورد از قبل موجود."})
        except Exception as error:
            results.append({"row": row["_row_number"], "ok": False, "message": str(error)})
    return results or [{"row": 2, "ok": False, "message": "فایل ردیف داده ندارد."}]
