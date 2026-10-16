import io
import zipfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_module.models import ProvinceTrustee, Student, User, UserRole
from auth_module.user_management import build_user_template_xlsx, import_users, normalize_code
from courses_module.forms import CourseCreateForm
from courses_module.models import Course
from questions_module.models import Chapter, Question, Topic
from quiz_module.forms import QuizForm
from quiz_module.models import Quiz
from quiz_module.permissions import student_quizzes
from .academic_imports import import_curriculum
from .models import FieldOfStudy, Grade, Province, School, Subject
from .spreadsheets import build_spreadsheet, read_spreadsheet


def spreadsheet(headers, rows, name="data.xlsx"):
    return SimpleUploadedFile(name, build_spreadsheet(headers, rows).getvalue())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AcademicImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province, _ = Province.objects.get_or_create(name="hormozgan")
        cls.school = School.objects.create(province=cls.province, name="مدرسه ورودی اول")
        cls.other_school = School.objects.create(province=cls.province, name="مدرسه ورودی دوم")
        cls.grade = Grade.objects.create(school=cls.school, title="دهم")
        cls.other_grade = Grade.objects.create(school=cls.other_school, title="دهم")
        cls.field = FieldOfStudy.objects.create(grade=cls.grade, title="ریاضی")
        cls.other_field = FieldOfStudy.objects.create(grade=cls.other_grade, title="ریاضی")
        cls.subject = Subject.objects.create(field=cls.field, title="حسابان")
        cls.other_subject = Subject.objects.create(field=cls.other_field, title="حسابان")
        cls.admin = User.objects.create_user(username="import-admin", role=UserRole.ADMIN)

    def defaults(self):
        return {"default_school": self.school, "default_province": self.province,
                "default_grade": "دهم", "default_field": "ریاضی"}

    def course_data(self):
        return {"title": "دوره جدید", "description": "شرح دوره", "level": "ALL",
                "allowed_grades": [str(self.grade.pk)], "allowed_fields": [str(self.field.pk)],
                "subjects": [str(self.subject.pk)], "start_date": "۱۴۰۵/۰۷/۲۴ ۱۸:۳۰"}

    def test_course_choices_display_each_title_only_once(self):
        form = CourseCreateForm(user=self.admin)
        for name in ["allowed_grades", "allowed_fields", "subjects"]:
            labels = [str(label) for value, label in form.fields[name].choices]
            self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual([str(label) for value, label in form.fields["allowed_grades"].choices].count("دهم"), 1)

    def test_course_selections_expand_across_schools_instead_of_losing_targets(self):
        form = CourseCreateForm(self.course_data(), user=self.admin)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn(self.grade, form.cleaned_data["allowed_grades"])
        self.assertIn(self.other_grade, form.cleaned_data["allowed_grades"])
        self.assertIn(self.other_field, form.cleaned_data["allowed_fields"])
        self.assertIn(self.other_subject, form.cleaned_data["subjects"])

    def test_grouped_course_choices_reject_forged_ids(self):
        data = self.course_data()
        data["allowed_grades"] = ["99999999"]
        form = CourseCreateForm(data, user=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn("allowed_grades", form.errors)

    def test_course_edit_marks_representative_for_nonrepresentative_initial_value(self):
        course = Course.objects.create(title="ویرایش", slug="unique-edit", author=self.admin, description="شرح")
        course.allowed_grades.add(self.other_grade)
        form = CourseCreateForm(instance=course, user=self.admin)
        values = form["allowed_grades"].value()
        selected_titles = set(Grade.objects.filter(pk__in=values).values_list("title", flat=True))
        self.assertEqual(selected_titles, {"دهم"})
        selected = [choice for choice in form["allowed_grades"] if choice.data["selected"]]
        self.assertEqual(len(selected), 1)

    def test_jalali_datetime_and_local_time_round_trip(self):
        with timezone.override("Asia/Tehran"):
            form = CourseCreateForm(self.course_data(), user=self.admin)
            self.assertTrue(form.is_valid(), form.errors)
            value = timezone.localtime(form.cleaned_data["start_date"])
            self.assertEqual((value.year, value.month, value.day, value.hour, value.minute), (2026, 10, 16, 18, 30))
            form.instance.start_date = form.cleaned_data["start_date"]
            rendered = CourseCreateForm(instance=form.instance, user=self.admin)
            self.assertEqual(rendered.initial["start_date"], "1405/07/24 18:30")

    def test_course_dates_reject_impossible_or_reversed_dates(self):
        for changes in [{"start_date": "۱۴۰۵/۱۳/۰۱ ۱۲:۰۰"},
                        {"end_date": "۱۴۰۵/۰۷/۲۳ ۱۲:۰۰"},
                        {"start_date": "۱۴۰۵/۰۷/۲۴ ۲۵:۰۰"}]:
            data = dict(self.course_data(), **changes)
            self.assertFalse(CourseCreateForm(data, user=self.admin).is_valid())

    def test_course_schedule_has_ltr_inputs_and_correct_datepicker_options(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("courses_module:course_create"))
        self.assertContains(response, "css/course-schedule.css")
        self.assertContains(response, "js/course-schedule.js")
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, 'class="schedule-control"')

    def test_member_excel_handles_numeric_grade_field_alias_and_scientific_code(self):
        rows = [["علی", "رضایی", "هرمزگان", self.school.name, "۱۰", "ریاضی فیزیک",
                 "1.23456789E+8", "StrongPass123!", "دانش‌آموز", ""]]
        upload = SimpleUploadedFile("members.xlsx", build_user_template_xlsx(rows).getvalue())
        results = import_users(upload)
        self.assertTrue(results[0]["ok"], results)
        user = User.objects.get(username="0123456789")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertEqual(user.student_profiles.get().field_id, self.field.pk)

    def test_member_import_uses_default_school_grade_field_and_role(self):
        upload = spreadsheet(["نام", "نام‌خانوادگی", "کدملی", "رمز"],
                             [["مریم", "محمدی", "۱۲۳۴۵۶۷۸۹۰", "StrongPass123!"]])
        results = import_users(upload, self.defaults())
        self.assertTrue(results[0]["ok"], results)
        user = User.objects.get(username="1234567890")
        self.assertEqual(user.role, UserRole.STUDENT)
        self.assertEqual(user.student_profiles.get().field_id, self.field.pk)

    def test_lower_grade_infers_its_single_general_field(self):
        grade = Grade.objects.create(school=self.school, title="ششم")
        field = FieldOfStudy.objects.create(grade=grade, title="عمومی")
        upload = spreadsheet(["نام", "فامیل", "کد ملی", "رمز عبور", "کلاس"],
                             [["حسن", "امیری", "1234567891", "StrongPass123!", "۶"]])
        results = import_users(upload, {"default_school": self.school})
        self.assertTrue(results[0]["ok"], results)
        self.assertEqual(Student.objects.get(user__username="1234567891").field_id, field.pk)

    def test_missing_or_ambiguous_field_does_not_create_partial_user(self):
        FieldOfStudy.objects.create(grade=self.grade, title="تجربی")
        upload = spreadsheet(["نام", "فامیل", "کد ملی", "رمز عبور", "پایه"],
                             [["حسن", "امیری", "1234567891", "StrongPass123!", "۱۰"]])
        result = import_users(upload, {"default_school": self.school})[0]
        self.assertFalse(result["ok"])
        self.assertFalse(User.objects.filter(username="1234567891").exists())

    def test_member_duplicate_import_does_not_change_existing_account(self):
        for repeat in range(2):
            upload = spreadsheet(["نام", "فامیل", "کد ملی", "رمز عبور"],
                                 [["حسن", "امیری", "1234567892", "StrongPass123!"]])
            result = import_users(upload, self.defaults())[0]
            self.assertEqual(result["ok"], repeat == 0)
        self.assertEqual(User.objects.filter(username="1234567892").count(), 1)

    def test_defaults_are_used_by_upload_endpoint(self):
        self.client.force_login(self.admin)
        upload = spreadsheet(["نام", "فامیل", "کد ملی", "رمز عبور"],
                             [["حسن", "امیری", "1234567893", "StrongPass123!"]])
        response = self.client.post(reverse("auth_module:user-import"), {
            "file": upload, "default_school": self.school.pk, "default_grade": "دهم", "default_field": "ریاضی",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="1234567893").exists())

    def test_each_curriculum_kind_imports_idempotently(self):
        for kind, title, defaults in [
            ("grade", "یازدهم", {"default_school": self.school}),
            ("field", "تجربی", dict(self.defaults(), default_grade="دهم")),
            ("subject", "فیزیک", self.defaults()),
        ]:
            for repeat in range(2):
                result = import_curriculum(spreadsheet(["عنوان"], [[title]]), kind, defaults)[0]
                self.assertTrue(result["ok"], result)
        self.assertEqual(Grade.objects.filter(school=self.school, title="یازدهم").count(), 1)
        self.assertEqual(FieldOfStudy.objects.filter(grade=self.grade, title="تجربی").count(), 1)
        self.assertEqual(Subject.objects.filter(field=self.field, title="فیزیک").count(), 1)

    def test_curriculum_global_import_expands_without_duplicate_titles_in_choices(self):
        results = import_curriculum(spreadsheet(["پایه"], [["پایه هشتم"]]), "grade",
                                    {"default_province": self.province, "apply_to_all": True})
        self.assertTrue(results[0]["ok"], results)
        self.assertTrue(Grade.objects.filter(school=self.school, title="هشتم").exists())
        self.assertTrue(Grade.objects.filter(school=self.other_school, title="هشتم").exists())
        form = CourseCreateForm(user=self.admin)
        self.assertEqual([str(label) for value, label in form.fields["allowed_grades"].choices].count("هشتم"), 1)

    def test_curriculum_requires_explicit_scope_and_only_admin_can_upload(self):
        result = import_curriculum(spreadsheet(["پایه"], [["هشتم"]]), "grade")[0]
        self.assertFalse(result["ok"])
        student = User.objects.create_user(username="no-import", role=UserRole.STUDENT)
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("users_module:curriculum_import")).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("users_module:curriculum_import"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["import_forms"]), 3)

    def test_curriculum_template_and_post_endpoint(self):
        self.client.force_login(self.admin)
        for kind in ["grade", "field", "subject"]:
            self.assertEqual(self.client.get(reverse("users_module:curriculum_template", args=[kind])).status_code, 200)
        response = self.client.post(reverse("users_module:curriculum_import_kind", args=["subject"]), {
            "file": spreadsheet(["درس"], [["درس جدید"]]), "default_school": self.school.pk,
            "default_grade": "دهم", "default_field": "ریاضی",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subject.objects.filter(field=self.field, title="درس جدید").exists())

    def test_province_school_subject_normalization_enforces_uniqueness(self):
        for model, values in [
            (Province, {"name": " هرمزگان "}),
            (School, {"name": "  مدرسه ورودی اول ", "province": self.province}),
            (Subject, {"title": " حسابان ", "field": self.field}),
        ]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**values)

    def test_quiz_choices_and_audience_use_unique_titles_across_schools(self):
        form = QuizForm(user=self.admin)
        for name in ["grade", "field"]:
            labels = [str(label) for value, label in form.fields[name].choices if value]
            self.assertEqual(len(labels), len(set(labels)))
        student = User.objects.create_user(username="other-school-quiz", role=UserRole.STUDENT)
        Student.objects.create(user=student, field=self.other_field)
        quiz = Quiz.objects.create(title="آزمون دهم", grade=self.grade, field=self.field,
                                   opens_at=timezone.now(), closes_at=timezone.now() + timezone.timedelta(hours=1),
                                   status=Quiz.Status.APPROVED, province=self.province)
        self.assertIn(quiz, student_quizzes(student))

    def test_bad_spreadsheet_and_excessive_national_code_are_reported(self):
        result = import_users(SimpleUploadedFile("bad.xlsx", b"not an xlsx"))[0]
        self.assertFalse(result["ok"])
        self.assertNotEqual(normalize_code("1E+99999999"), "0000000001")
        with self.assertRaises(ValueError):
            read_spreadsheet(spreadsheet(["نام", "نام"], [["الف", "ب"]]), {})

    def test_real_excel_numeric_cells_rich_strings_and_physical_rows(self):
        source = build_spreadsheet(["نام", "کد ملی"])
        output = io.BytesIO()
        namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as archive:
            for item in original.infolist():
                data = original.read(item.filename)
                if item.filename == "xl/worksheets/sheet1.xml":
                    data = data.decode().replace("</sheetData>", '<row r="7"><c r="A7" t="s"><v>0</v></c><c r="B7"><v>1.23456789E+8</v></c></row></sheetData>').encode()
                archive.writestr(item, data)
            archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}"><si><r><t>علی</t></r><r><t>رضا</t></r></si></sst>')
        rows = read_spreadsheet(SimpleUploadedFile("real.xlsx", output.getvalue()), {"نام": "name", "کد ملی": "code"})
        self.assertEqual(rows, [{"name": "علیرضا", "code": "1.23456789E+8", "_row_number": 7}])

    def test_course_summary_hides_repeated_scoped_titles(self):
        from users_module.templatetags.academic_titles import unique_titles

        self.assertEqual(len(unique_titles([self.grade, self.other_grade])), 1)
        self.assertEqual(len(unique_titles([self.field, self.other_field])), 1)


class LocationMergeMigrationTests(TransactionTestCase):
    def test_location_merge_preserves_nested_questions_students_and_course_memberships(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("users_module", "0009_enforce_curriculum_uniqueness")])
            province, _ = Province.objects.get_or_create(name="hormozgan")
            duplicate_province = Province.objects.create(name="legacy-province")
            Province.objects.filter(pk=duplicate_province.pk).update(name=" هرمزگان ")
            school = School.objects.create(province=province, name="ادغام مدرسه")
            duplicate_school = School.objects.create(province=duplicate_province, name="ادغام مدرسه")
            grade = Grade.objects.create(school=school, title="دهم")
            duplicate_grade = Grade.objects.create(school=duplicate_school, title="دهم")
            field = FieldOfStudy.objects.create(grade=grade, title="ریاضی")
            duplicate_field = FieldOfStudy.objects.create(grade=duplicate_grade, title="ریاضی")
            subject = Subject.objects.create(field=field, title="حسابان")
            duplicate_subject = Subject.objects.create(field=duplicate_field, title="حسابان")
            chapter = Chapter.objects.create(subject=subject, name="فصل مشترک")
            duplicate_chapter = Chapter.objects.create(subject=duplicate_subject, name="فصل مشترک")
            topic = Topic.objects.create(chapter=chapter, name="مبحث مشترک")
            duplicate_topic = Topic.objects.create(chapter=duplicate_chapter, name="مبحث مشترک")
            user = User.objects.create_user(username="location-merge", role=UserRole.STUDENT)
            trustee = User.objects.create_user(username="location-trustee", role=UserRole.PROVINCE_TRUSTEE)
            ProvinceTrustee.objects.create(user=trustee, province=province)
            ProvinceTrustee.objects.create(user=trustee, province=duplicate_province)
            profile = Student.objects.create(user=user, field=duplicate_field)
            question = Question.objects.create(chapter=duplicate_chapter, topic=duplicate_topic, text="سؤال محفوظ")
            course = Course.objects.create(title="دوره ادغام", slug="merge-locations", author=user, description="شرح")
            course.allowed_provinces.add(province, duplicate_province)
            course.allowed_cities.add(school, duplicate_school)
            course.allowed_grades.add(grade, duplicate_grade)
            course.allowed_fields.add(field, duplicate_field)
            course.subjects.add(subject, duplicate_subject)
            MigrationExecutor(connection).migrate(latest)
            profile.refresh_from_db()
            question.refresh_from_db()
            self.assertEqual(profile.field_id, field.pk)
            self.assertEqual(question.chapter_id, chapter.pk)
            self.assertEqual(question.topic_id, topic.pk)
            for name, item in [("allowed_provinces", province), ("allowed_cities", school),
                               ("allowed_grades", grade), ("allowed_fields", field), ("subjects", subject)]:
                self.assertQuerySetEqual(getattr(course, name).all(), [item])
            self.assertFalse(Province.objects.filter(pk=duplicate_province.pk).exists())
            self.assertEqual(ProvinceTrustee.objects.filter(user=trustee, province=province).count(), 1)
        finally:
            MigrationExecutor(connection).migrate(latest)
