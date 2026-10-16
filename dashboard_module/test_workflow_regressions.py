from datetime import timedelta
from importlib import import_module
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_module.models import ProvinceTrustee, Student, User, UserRole
from blog_module.models import Category, Post
from classroom_module.models import OnlineClass
from counseling_module.models import StudentConsultantAssignment
from courses_module.models import ApprovalStatus, Course, CourseEnrollment, CourseEpisode, CourseRating, CourseSection
from questions_module.models import Chapter, ExamAnswer, ExamSession, PracticeAnswer, PracticeSession, Question
from quiz_module.models import Quiz
from ticketing_module.models import ModerationStatus, Ticket, TicketMessage, TicketQueue, TicketStatus, TicketType
from users_module.models import FieldOfStudy, Grade, Province, School, Subject

from .models import NotificationReceipt


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkflowRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.province = Province.objects.get_or_create(name='hormozgan')[0]
        cls.other_province = Province.objects.get_or_create(name='kerman')[0]
        school = School.objects.create(name='شهر تست', province=cls.province)
        grade = Grade.objects.create(title='دهم', school=school)
        cls.field = FieldOfStudy.objects.create(title='ریاضی', grade=grade)
        cls.student = User.objects.create_user(username='reg-student', role=UserRole.STUDENT)
        cls.profile = Student.objects.create(user=cls.student, field=cls.field)
        cls.consultant = User.objects.create_user(username='reg-consultant', role=UserRole.CONSULTANT)
        cls.trustee = User.objects.create_user(username='reg-trustee', role=UserRole.PROVINCE_TRUSTEE)
        cls.admin = User.objects.create_user(username='reg-admin', role=UserRole.ADMIN)
        cls.moderator = User.objects.create_user(username='reg-moderator', role=UserRole.CONTENT_MODERATOR)
        ProvinceTrustee.objects.create(user=cls.trustee, province=cls.province)
        StudentConsultantAssignment.objects.create(student=cls.profile, consultant=cls.consultant)
        cls.course = Course.objects.create(
            title='دوره تست', slug='دوره-تست', author=cls.consultant, description='توضیح',
            approval_status=ApprovalStatus.APPROVED, all_fields_allowed=True, all_grades_allowed=True,
            start_date=timezone.now() - timedelta(days=1),
        )
        section = CourseSection.objects.create(course=cls.course, title='بخش اول')
        cls.episode = CourseEpisode.objects.create(section=section, title='جلسه اول', url='https://example.com/lesson')

    def test_enrollment_persian_url_is_idempotent_and_content_opens(self):
        self.client.force_login(self.student)
        url = reverse('courses_module:course_enroll', args=[self.course.slug])
        for attempt in range(2):
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(CourseEnrollment.objects.filter(course=self.course, student=self.student).count(), 1)
        response = self.client.get(reverse('courses_module:course_detail', args=[self.course.slug]))
        self.assertTrue(response.context['can_access_content'])
        self.assertEqual(self.client.get(reverse('courses_module:episode_download', args=[self.episode.pk])).status_code, 302)

    def test_full_course_does_not_enroll_student(self):
        Course.objects.filter(pk=self.course.pk).update(capacity=0)
        self.client.force_login(self.student)
        self.client.post(reverse('courses_module:course_enroll', args=[self.course.slug]))
        self.assertFalse(CourseEnrollment.objects.exists())

    def test_staff_preview_does_not_require_enrollment(self):
        for user in (self.admin, self.trustee, self.consultant):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('courses_module:course_detail', args=[self.course.slug]))
                self.assertTrue(response.context['can_access_content'])
                self.assertNotContains(response, 'تست شرکت در دوره')
                self.assertRedirects(self.client.get(reverse('courses_module:episode_download', args=[self.episode.pk])), self.episode.url, fetch_redirect_response=False)
        self.assertFalse(CourseEnrollment.objects.exists())

    def test_trustee_can_review_from_detail_and_publish(self):
        Course.objects.filter(pk=self.course.pk).update(approval_status=ApprovalStatus.PENDING, is_active=False)
        self.client.force_login(self.trustee)
        detail = self.client.get(reverse('courses_module:course_detail', args=[self.course.slug]))
        self.assertTrue(detail.context['can_review'])
        response = self.client.post(reverse('courses_module:course_review', args=[self.course.pk]), {'action': 'approve'})
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_visible_now)
        self.assertEqual(self.course.reviewed_by, self.trustee)

    def test_trustee_cannot_review_other_province(self):
        Course.objects.filter(pk=self.course.pk).update(approval_status=ApprovalStatus.PENDING, all_provinces_allowed=False)
        self.course.allowed_provinces.add(self.other_province)
        self.client.force_login(self.trustee)
        response = self.client.post(reverse('courses_module:course_review', args=[self.course.pk]), {'action': 'approve'})
        self.assertEqual(response.status_code, 404)

    def test_course_province_filter_and_fractional_stars(self):
        Course.objects.filter(pk=self.course.pk).update(all_provinces_allowed=False)
        self.course.allowed_provinces.add(self.province)
        CourseRating.objects.create(course=self.course, student=self.student, value=3)
        CourseRating.objects.create(course=self.course, student=self.admin, value=4)
        self.client.force_login(self.admin)
        url = reverse('courses_module:course_list')
        response = self.client.get(url, {'province': self.province.pk})
        self.assertContains(response, 'width:70%')
        self.assertContains(response, 'name="province"')
        self.assertNotContains(self.client.get(url, {'province': self.other_province.pk}), self.course.title)

    def test_consultant_question_status_handles_missing_relations(self):
        Question.objects.create(creator=self.consultant, text='سؤال خودم', approval_status=Question.ApprovalStatus.PENDING)
        Question.objects.create(creator=self.admin, text='سؤال مدیر')
        self.client.force_login(self.consultant)
        response = self.client.get(reverse('questions_module:choose_mode'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'سؤال خودم')
        self.assertNotContains(response, 'سؤال مدیر')

    def test_question_performance_uses_bounded_queries_and_counts_booleans(self):
        from questions_module.views import _performance_data

        for number in range(3):
            subject = Subject.objects.create(title=f'درس {number}', field=self.field)
            chapter = Chapter.objects.create(name='فصل', subject=subject)
            question = Question.objects.create(chapter=chapter, text='سؤال')
            practice = PracticeSession.objects.create(user=self.consultant, status=PracticeSession.Status.DONE)
            exam = ExamSession.objects.create(user=self.consultant, status=ExamSession.Status.DONE)
            PracticeAnswer.objects.create(session=practice, question=question, is_correct=True)
            ExamAnswer.objects.create(session=exam, question=question, is_correct=False)
        with self.assertNumQueries(3):
            result = _performance_data(self.consultant)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item['percent'] == 50.0 and item['total'] == 2 for item in result))

    def test_assigned_consultant_can_create_quiz_for_student(self):
        self.client.force_login(self.consultant)
        url = reverse('quiz_module:quiz_create')
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {
            'title': 'آزمون دانش‌آموز من', 'assigned_students': [self.student.pk],
            'duration_minutes': 30, 'max_attempts': 1, 'negative_ratio': '0.33',
            'opens_date': '1405/08/01', 'opens_time': '08:00',
            'closes_date': '1405/08/01', 'closes_time': '09:00',
        })
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code == 200 else '')
        self.assertTrue(Quiz.objects.get(creator=self.consultant).assigned_students.filter(pk=self.student.pk).exists())

    def test_consultant_cannot_target_unassigned_student_without_general_access(self):
        other_student = User.objects.create_user(username='unassigned', role=UserRole.STUDENT)
        Student.objects.create(user=other_student, field=self.field)
        self.client.force_login(self.consultant)
        response = self.client.get(reverse('quiz_module:filter_students'))
        self.assertEqual([item['id'] for item in response.json()['results']], [self.student.pk])
        response = self.client.post(reverse('quiz_module:quiz_create'), {
            'title': 'آزمون غیرمجاز', 'assigned_students': [other_student.pk],
            'duration_minutes': 30, 'max_attempts': 1, 'negative_ratio': '0.33',
            'opens_date': '1405/08/01', 'opens_time': '08:00',
            'closes_date': '1405/08/01', 'closes_time': '09:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('assigned_students', response.context['form'].errors)
        self.assertFalse(Quiz.objects.exists())

    def test_unseen_notification_is_not_marked_by_an_older_panel(self):
        category = Category.objects.create(name='مطالب', slug='reg-notification-batch')
        self.client.force_login(self.student)
        for number in range(7):
            Post.objects.create(title=f'مطلب {number}', slug=f'notice-{number}', body='متن', category=category, author=self.admin, status='published', published_at=timezone.now())
        response = self.client.get(reverse('dashboard'))
        token = response.context['fanous_notification_token']
        self.assertEqual(len(response.context['fanous_notifications']), 6)
        Post.objects.create(title='تازه‌تر', slug='notice-later', body='متن', category=category, author=self.admin, status='published', published_at=timezone.now())
        self.client.post(reverse('notifications_read'), {'token': token})
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['fanous_unread_count'], 2)
        self.assertIn('تازه‌تر', [item['title'] for item in response.context['fanous_notifications']])

    def test_notification_token_cannot_mark_another_users_notifications(self):
        self.client.force_login(self.student)
        token = self.client.get(reverse('dashboard')).context['fanous_notification_token']
        self.client.force_login(self.consultant)
        self.assertEqual(self.client.post(reverse('notifications_read'), {'token': token}).status_code, 403)
        self.assertFalse(NotificationReceipt.objects.exists())

    def test_private_text_goes_directly_to_consultant(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('counseling:private_ticket'), {'title': 'مشاوره', 'content': 'پیام متنی'})
        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.current_queue, TicketQueue.CONSULTANT)
        self.assertEqual(ticket.messages.get().moderation_status, ModerationStatus.APPROVED)
        self.client.force_login(self.consultant)
        self.assertContains(self.client.get(reverse('ticketing:detail', args=[ticket.pk])), 'پیام متنی')
        self.client.post(reverse('ticketing:add_message', args=[ticket.pk]), {'content': 'پاسخ مستقیم'})
        self.assertEqual(ticket.messages.get(sender=self.consultant).moderation_status, ModerationStatus.APPROVED)

    def test_legacy_private_text_migration_keeps_attachments_pending(self):
        text_ticket = Ticket.objects.create(title='متن قدیمی', student=self.profile, ticket_type=TicketType.PSYCHOLOGY, is_private_consultation=True, current_assignee_user=self.consultant)
        attachment_ticket = Ticket.objects.create(title='فایل قدیمی', student=self.profile, ticket_type=TicketType.PSYCHOLOGY, is_private_consultation=True, current_assignee_user=self.consultant)
        text = TicketMessage.objects.create(ticket=text_ticket, sender=self.student, content='متن')
        attachment = TicketMessage.objects.create(ticket=attachment_ticket, sender=self.student, content='فایل', attachment='existing.txt')
        migration = import_module('ticketing_module.migrations.0005_approve_private_text_messages')
        migration.approve_private_text_messages(apps, SimpleNamespace(connection=connection))
        text.refresh_from_db()
        attachment.refresh_from_db()
        text_ticket.refresh_from_db()
        attachment_ticket.refresh_from_db()
        self.assertEqual(text.moderation_status, ModerationStatus.APPROVED)
        self.assertEqual(text_ticket.current_queue, TicketQueue.CONSULTANT)
        self.assertEqual(text_ticket.status, TicketStatus.OPEN)
        self.assertEqual(attachment.moderation_status, ModerationStatus.PENDING)
        self.assertEqual(attachment_ticket.current_queue, TicketQueue.MODERATOR)

    def test_private_attachment_only_reply_is_moderated(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            self.client.force_login(self.student)
            self.client.post(reverse('counseling:private_ticket'), {
                'title': 'پیوست خصوصی', 'content': 'متن اولیه',
                'attachment': SimpleUploadedFile('test.txt', b'private attachment'),
            })
            ticket = Ticket.objects.get()
            message = ticket.messages.get()
            self.assertEqual(ticket.current_queue, TicketQueue.MODERATOR)
            self.assertEqual(message.moderation_status, ModerationStatus.PENDING)
            self.client.force_login(self.moderator)
            self.client.post(reverse('ticketing:moderate_message', args=[message.pk]), {'decision': 'approve'})
            ticket.refresh_from_db()
            self.assertEqual(ticket.current_queue, TicketQueue.CONSULTANT)
            self.client.force_login(self.student)
            self.client.post(reverse('ticketing:add_message', args=[ticket.pk]), {'attachment': SimpleUploadedFile('reply.txt', b'reply')})
            self.assertEqual(ticket.messages.count(), 2)
            self.assertEqual(ticket.messages.order_by('-pk').first().moderation_status, ModerationStatus.PENDING)

    def test_seen_notifications_stay_read_after_new_login(self):
        category = Category.objects.create(name='خبر', slug='reg-category')
        Post.objects.create(title='خبر جدید', slug='reg-post', body='متن', category=category, author=self.admin, status='published', published_at=timezone.now())
        OnlineClass.objects.create(title='کلاس جدید', meeting_url='https://example.com/class', starts_at=timezone.now() + timedelta(hours=1), ends_at=timezone.now() + timedelta(hours=2))
        self.client.force_login(self.student)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['fanous_unread_count'], 2)
        token = response.context['fanous_notification_token']
        for attempt in range(2):
            self.assertEqual(self.client.post(reverse('notifications_read'), {'token': token}).status_code, 200)
        self.assertEqual(NotificationReceipt.objects.filter(user=self.student).count(), 2)
        self.client.logout()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('dashboard')).context['fanous_unread_count'], 0)

    def test_invalid_notification_token_is_rejected(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse('notifications_read'), {'token': 'invalid'}).status_code, 400)
        self.assertFalse(NotificationReceipt.objects.exists())
