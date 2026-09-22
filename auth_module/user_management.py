import csv
import io
import re
import zipfile
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.db import transaction

from users_module.models import FieldOfStudy, Grade, Province, School
from .models import Consultant, ProvinceTrustee, Student, UserRole


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
ROLE_MAP = {
    "دانش آموز": UserRole.STUDENT, "دانش‌آموز": UserRole.STUDENT, "student": UserRole.STUDENT,
    "مشاور": UserRole.CONSULTANT, "consultant": UserRole.CONSULTANT,
    "معتمد": UserRole.PROVINCE_TRUSTEE, "معتمد استان": UserRole.PROVINCE_TRUSTEE, "province_trustee": UserRole.PROVINCE_TRUSTEE,
    "ناظر": UserRole.CONTENT_MODERATOR, "ناظر محتوا": UserRole.CONTENT_MODERATOR, "content_moderator": UserRole.CONTENT_MODERATOR,
    "ادمین": UserRole.ADMIN, "مدیر": UserRole.ADMIN, "مدیر سیستم": UserRole.ADMIN, "admin": UserRole.ADMIN,
}
HEADERS = {
    "اسم": "first_name", "نام": "first_name", "فامیل": "last_name", "نام خانوادگی": "last_name",
    "شهر": "city", "استان": "province", "رشته": "field", "پایه": "grade", "پایه (اختیاری)": "grade",
    "کد ملی": "national_code", "کدملی": "national_code", "رمز عبور": "password",
    "نقش": "role", "نام کاربری": "username",
}


def clean_text(value):
    return str(value or "").strip().replace("ي", "ی").replace("ك", "ک")


def normalize_code(value):
    value = clean_text(value).translate(DIGITS)
    if value.endswith(".0"):
        value = value[:-2]
    return value.zfill(10) if value.isdigit() and len(value) < 10 else value


def _xlsx_rows(upload):
    with zipfile.ZipFile(upload) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        sheet = next(node for node in workbook.iter() if node.tag.endswith("}sheet"))
        relation_id = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
        target = targets[relation_id].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ElementTree.fromstring(archive.read(target))
        for row in (node for node in root.iter() if node.tag.endswith("}row")):
            values, current = [], 0
            for cell in (node for node in row if node.tag.endswith("}c")):
                ref = cell.attrib.get("r", "A1")
                letters = re.match(r"[A-Z]+", ref).group()
                column = 0
                for letter in letters:
                    column = column * 26 + ord(letter) - 64
                while current < column - 1:
                    values.append(""); current += 1
                value_node = next((node for node in cell.iter() if node.tag.endswith("}v")), None)
                inline = next((node for node in cell.iter() if node.tag.endswith("}t")), None)
                value = inline.text if inline is not None else (value_node.text if value_node is not None else "")
                if cell.attrib.get("t") == "s" and value != "":
                    value = shared[int(value)]
                values.append(value or ""); current += 1
            yield values


def spreadsheet_rows(upload):
    name = upload.name.lower()
    if name.endswith(".csv"):
        text = upload.read().decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
    elif name.endswith(".xlsx"):
        rows = list(_xlsx_rows(upload))
    else:
        raise ValueError("فقط فایل‌های xlsx و csv قابل قبول هستند.")
    if not rows:
        return []
    headers = [HEADERS.get(clean_text(value), clean_text(value).lower()) for value in rows[0]]
    return [{headers[index]: clean_text(value) for index, value in enumerate(row) if index < len(headers)} for row in rows[1:] if any(clean_text(value) for value in row)]


def _province(value):
    value = clean_text(value).lower()
    for item in Province.objects.all():
        if value in {clean_text(item.name).lower(), clean_text(item.get_name_display()).lower()}:
            return item
    raise ValueError("استان در سامانه تعریف نشده است.")


def _role(value):
    role = ROLE_MAP.get(clean_text(value).lower())
    if not role:
        raise ValueError("نقش معتبر نیست.")
    return role


def import_users(upload):
    rows = spreadsheet_rows(upload)
    results = []
    required = {"first_name", "last_name", "province", "city", "national_code", "password", "role"}
    User = get_user_model()
    for number, row in enumerate(rows, start=2):
        try:
            missing = [HEADERS.get(key, key) for key in required if not row.get(key)]
            if missing:
                raise ValueError("ستون‌های ضروری این ردیف کامل نیستند.")
            code = normalize_code(row["national_code"])
            if not (code.isdigit() and len(code) == 10):
                raise ValueError("کد ملی باید ۱۰ رقم باشد.")
            role = _role(row["role"])
            province = _province(row["province"])
            school = School.objects.filter(province=province, name__iexact=row["city"]).first()
            if not school:
                raise ValueError("شهر موردنظر در این استان تعریف نشده است.")
            with transaction.atomic():
                user, created = User.objects.get_or_create(username=code, defaults={"first_name": row["first_name"], "last_name": row["last_name"], "role": role})
                if not created:
                    raise ValueError("کاربری با این کد ملی قبلاً وجود دارد.")
                user.first_name, user.last_name, user.role = row["first_name"], row["last_name"], role
                user.is_staff = role == UserRole.ADMIN
                user.set_password(row["password"])
                user.save()
                if role == UserRole.STUDENT:
                    if not row.get("field"):
                        raise ValueError("رشته برای دانش‌آموز الزامی است.")
                    fields = FieldOfStudy.objects.filter(grade__school=school, title__iexact=row["field"])
                    if row.get("grade"):
                        fields = fields.filter(grade__title__iexact=row["grade"])
                    if fields.count() != 1:
                        raise ValueError("رشته/پایه مبهم یا تعریف‌نشده است؛ در صورت نیاز ستون پایه را تکمیل کنید.")
                    Student.objects.create(user=user, field=fields.first())
                elif role == UserRole.CONSULTANT:
                    Consultant.objects.get_or_create(consultant=user)
                elif role == UserRole.PROVINCE_TRUSTEE:
                    ProvinceTrustee.objects.create(user=user, province=province)
            results.append({"row": number, "ok": True, "message": f"{row['first_name']} {row['last_name']} ساخته شد."})
        except Exception as error:
            results.append({"row": number, "ok": False, "message": str(error)})
    return results


def shift_student_grade(student, direction):
    current = student.field.grade
    rank_words = {"اول": 1, "دوم": 2, "سوم": 3, "چهارم": 4, "پنجم": 5, "ششم": 6, "هفتم": 7, "هشتم": 8, "نهم": 9, "دهم": 10, "یازدهم": 11, "دوازدهم": 12}
    def grade_rank(grade):
        title = clean_text(grade.title).translate(DIGITS)
        match = re.search(r"\d+", title)
        if match:
            return int(match.group())
        return next((rank for word, rank in rank_words.items() if word in title), grade.pk)
    grades = sorted(Grade.objects.filter(school=current.school, is_active=True), key=grade_rank)
    index = next((i for i, grade in enumerate(grades) if grade.pk == current.pk), None)
    target_index = index + direction if index is not None else -1
    if target_index < 0 or target_index >= len(grades):
        return False
    target_field = FieldOfStudy.objects.filter(grade=grades[target_index], title__iexact=student.field.title, is_active=True).first()
    if not target_field:
        return False
    student.field = target_field
    student.save(update_fields=["field"])
    return True
