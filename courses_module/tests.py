from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_module.models import Student, UserRole
from users_module.models import FieldOfStudy, Grade, Province, School

from .forms import CourseResourceForm
from .models import ApprovalStatus, Course, CourseEnrollment, CourseRating, CourseResource, CourseView

User = get_user_model()


class CourseWorkflowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student", password="Pass123!", role=UserRole.STUDENT)
        self.consultant = User.objects.create_user(username="consultant", password="Pass123!", role=UserRole.CONSULTANT)
        self.trustee = User.objects.create_user(username="trustee", password="Pass123!", role=UserRole.PROVINCE_TRUSTEE)
        self.course = Course.objects.create(
            title="دوره آزمایشی",
            slug="test-course",
            author=self.consultant,
            description="توضیحات دوره",
            start_date=timezone.now() - timedelta(days=1),
            approval_status=ApprovalStatus.PENDING,
        )

    def test_pending_course_is_not_visible_to_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_list"))
        self.assertNotContains(response, self.course.title)
        detail = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(detail.status_code, 404)

    def test_only_consultant_can_open_create_page(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("courses_module:course_create")).status_code, 403)
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.get(reverse("courses_module:course_create")).status_code, 200)

    def test_admin_can_open_create_page(self):
        admin = User.objects.create_user(username="course-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("courses_module:course_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ایجاد و انتشار دوره")

    def test_admin_can_create_course_without_optional_filters(self):
        admin = User.objects.create_user(username="admin-create", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.post(reverse("courses_module:course_create"), {
            "title": "دوره جدید", "description": "دوره عمومی آزمایشی", "level": "ALL",
        })
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(title="دوره جدید")
        self.assertEqual(course.approval_status, ApprovalStatus.APPROVED)
        self.assertTrue(course.all_grades_allowed)

    def test_admin_can_restrict_and_restore_course_audience_when_editing(self):
        province = Province.objects.create(name="edit-province")
        school = School.objects.create(province=province, name="edit-school")
        grade = Grade.objects.create(school=school, title="دهم")
        field = FieldOfStudy.objects.create(grade=grade, title="ریاضی")
        admin = User.objects.create_user(username="edit-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        url = reverse("courses_module:course_edit", args=[self.course.pk])
        for selected, expected in ((True, False), (False, True)):
            data = {"title": self.course.title, "description": self.course.description, "level": "ALL"}
            if selected:
                data.update(allowed_grades=[grade.pk], allowed_fields=[field.pk])
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302, response.context["form"].errors if response.status_code == 200 else "")
            self.course.refresh_from_db()
            self.assertEqual(self.course.all_grades_allowed, expected)
            self.assertEqual(self.course.all_fields_allowed, expected)

    def test_course_is_visible_only_in_selected_provinces_and_cities(self):
        first_province = Province.objects.create(name="hormozgan")
        second_province = Province.objects.create(name="kerman")
        first_city = School.objects.create(province=first_province, name="شهر اول")
        excluded_city = School.objects.create(province=first_province, name="شهر دوم")
        second_city = School.objects.create(province=second_province, name="شهر سوم")
        students = []
        for index, city in enumerate((first_city, excluded_city, second_city)):
            grade = Grade.objects.create(school=city, title="دهم")
            field = FieldOfStudy.objects.create(grade=grade, title="ریاضی")
            student = User.objects.create_user(username=f"region-student-{index}", password="Pass123!", role=UserRole.STUDENT)
            Student.objects.create(user=student, field=field)
            students.append(student)

        admin = User.objects.create_user(username="region-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.post(reverse("courses_module:course_create"), {
            "title": "دوره مخصوص شهرها", "description": "برای دو شهر", "level": "ALL",
            "allowed_provinces": [first_province.pk, second_province.pk],
            "allowed_cities": [first_city.pk, second_city.pk],
        })
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(title="دوره مخصوص شهرها")
        self.assertFalse(course.all_provinces_allowed)
        self.assertEqual(set(course.allowed_cities.values_list("id", flat=True)), {first_city.pk, second_city.pk})

        for student, visible in zip(students, (True, False, True)):
            self.client.force_login(student)
            listing = self.client.get(reverse("courses_module:course_list"))
            self.assertEqual(course in listing.context["courses"], visible)
            detail = self.client.get(reverse("courses_module:course_detail", args=[course.slug]))
            self.assertEqual(detail.status_code, 200 if visible else 404)
            if not visible:
                enrollment = self.client.post(reverse("courses_module:course_enroll", args=[course.slug]))
                self.assertEqual(enrollment.status_code, 404)

    def test_city_must_belong_to_selected_province(self):
        first_province = Province.objects.create(name="hormozgan")
        other_province = Province.objects.create(name="kerman")
        other_city = School.objects.create(province=other_province, name="شهر خارج استان")
        admin = User.objects.create_user(username="region-validator", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.post(reverse("courses_module:course_create"), {
            "title": "دوره نامعتبر", "description": "محدوده نادرست", "level": "ALL",
            "allowed_provinces": [first_province.pk], "allowed_cities": [other_city.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("allowed_cities", response.context["form"].errors)

    def test_admin_course_management_renders(self):
        admin = User.objects.create_user(username="admin-catalog", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

    def test_course_counts_unique_viewers_without_enrollment(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.student)
        detail_url = reverse("courses_module:course_detail", args=[self.course.slug])
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(CourseView.objects.filter(course=self.course).count(), 1)
        self.assertFalse(CourseEnrollment.objects.filter(course=self.course, student=self.student).exists())
        admin = User.objects.create_user(username="viewer-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertEqual(response.context["courses"][0].admin_viewer_count, 1)

    def test_resource_accepts_either_file_or_url(self):
        url_form = CourseResourceForm(data={
            "title": "ویدیوی لینک‌شده", "resource_type": "video",
            "url": "https://youtu.be/abcdefghijk", "order": 1, "is_active": True,
        })
        self.assertTrue(url_form.is_valid(), url_form.errors)

        image = SimpleUploadedFile("lesson.png", b"image-bytes", content_type="image/png")
        file_form = CourseResourceForm(
            data={"title": "تصویر درس", "resource_type": "image", "order": 1, "is_active": True},
            files={"file": image},
        )
        self.assertTrue(file_form.is_valid(), file_form.errors)

        empty_form = CourseResourceForm(data={
            "title": "بدون منبع", "resource_type": "pdf", "order": 1, "is_active": True,
        })
        self.assertFalse(empty_form.is_valid())

    def test_linked_and_uploaded_resources_render_inside_course(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        CourseResource.objects.create(
            course=self.course, title="ویدیوی آموزشی", resource_type="video",
            url="https://youtu.be/abcdefghijk",
        )
        CourseResource.objects.create(
            course=self.course, title="جزوه", resource_type="pdf", url="https://example.com/lesson.pdf",
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertContains(response, "https://www.youtube.com/embed/abcdefghijk")
        self.assertContains(response, "https://example.com/lesson.pdf")

    def test_consultant_trustee_and_admin_can_edit_course(self):
        for user in (self.consultant, self.trustee):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("courses_module:course_edit", args=[self.course.pk])).status_code, 200)
        admin = User.objects.create_user(username="editor-admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("courses_module:course_edit", args=[self.course.pk])).status_code, 200)

    def test_trustee_queue_is_available_from_my_courses(self):
        self.client.force_login(self.trustee)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertContains(response, "دوره‌های تأییدنشده")
        self.assertContains(response, self.course.title)

    def test_trustee_can_approve_and_publish_course(self):
        self.client.force_login(self.trustee)
        response = self.client.post(reverse("courses_module:course_review", args=[self.course.pk]), {"action": "approve"})
        self.assertRedirects(response, reverse("courses_module:review_list"))
        self.course.refresh_from_db()
        self.assertEqual(self.course.approval_status, ApprovalStatus.APPROVED)
        self.assertEqual(self.course.reviewed_by, self.trustee)
        self.assertTrue(self.course.is_visible_now)

    def test_student_enrollment_and_rating_are_unique(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.student)
        enroll_url = reverse("courses_module:course_enroll", args=[self.course.slug])
        self.client.post(enroll_url)
        self.client.post(enroll_url)
        self.assertEqual(CourseEnrollment.objects.filter(course=self.course, student=self.student).count(), 1)
        rate_url = reverse("courses_module:course_rate", args=[self.course.slug])
        self.client.post(rate_url, {"rating": 4})
        self.client.post(rate_url, {"rating": 5})
        self.assertEqual(CourseRating.objects.get(course=self.course, student=self.student).value, 5)

    def test_my_courses_only_contains_enrolled_courses(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        other = Course.objects.create(
            title="دوره دیگر", slug="other", author=self.consultant, description="...",
            start_date=timezone.now() - timedelta(days=1), approval_status=ApprovalStatus.APPROVED,
        )
        CourseEnrollment.objects.create(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:my_courses"))
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, other.title)

    def test_approved_course_detail_renders_for_student(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

    def test_persian_slug_is_supported(self):
        self.course.slug = "دوره-آزمایشی-فارسی"
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["slug", "approval_status"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses_module:course_detail", args=[self.course.slug]))
        self.assertEqual(response.status_code, 200)

    def test_login_starts_at_dashboard(self):
        response = self.client.post(reverse("auth_module:login"), {"username": "consultant", "password": "Pass123!"})
        self.assertRedirects(response, reverse("dashboard"))

    def test_non_student_cannot_enroll(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.consultant)
        response = self.client.post(reverse("courses_module:course_enroll", args=[self.course.slug]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CourseEnrollment.objects.filter(course=self.course, student=self.consultant).exists())

    def test_only_admin_can_close_or_delete_course(self):
        self.course.approval_status = ApprovalStatus.APPROVED
        self.course.save(update_fields=["approval_status"])
        self.client.force_login(self.trustee)
        self.assertEqual(self.client.post(reverse("courses_module:course_close", args=[self.course.pk])).status_code, 403)
        admin = User.objects.create_user(username="admin", password="Pass123!", role=UserRole.ADMIN)
        self.client.force_login(admin)
        response = self.client.post(reverse("courses_module:course_close", args=[self.course.pk]))
        self.assertRedirects(response, reverse("courses_module:course_detail", args=[self.course.slug]))
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_active)
        self.client.post(reverse("courses_module:course_delete", args=[self.course.pk]))
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
