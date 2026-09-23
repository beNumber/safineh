from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from auth_module.models import UserRole
from users_module.models import Subject

from .models import Ticket, TicketMessage, TicketQueue, TicketStatus, TicketType


INPUT_CLASS = (
    "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm "
    "outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
)

CHECKBOX_CLASS = (
    "h-5 w-5 rounded border-slate-300 text-blue-600 transition focus:ring-blue-500"
)


class TicketCreateForm(forms.ModelForm):
    TECHNICAL_ISSUES = (
        ("", "انتخاب نوع مشکل فنی..."),
        ("video_download", "مشکل در دانلود یا پخش ویدیو / فایل آموزشی"),
        ("exam_platform", "اشکال در آزمون‌ها یا ثبت پاسخ‌برگ"),
        ("auth_profile", "مشکل ورود به پنل، پروفایل یا اطلاعات کاربری"),
        ("system_bug", "گزارش باگ یا خطای عمومی سامانه"),
        ("other_technical", "سایر موارد فنی"),
    )

    content = forms.CharField(
        label="متن پرسش یا شرح مشکل",
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASS,
                "rows": 6,
                "placeholder": "جزئیات پرسش یا مشکل خود را به صورت کامل شرح دهید...",
            }
        ),
    )
    attachment = forms.FileField(
        label="پیوست (تصویر، صوت یا سند)",
        required=False,
        widget=forms.FileInput(attrs={"class": INPUT_CLASS}),
    )
    technical_issue = forms.ChoiceField(
        label="نوع اشکال فنی",
        choices=TECHNICAL_ISSUES,
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS, "id": "id_technical_issue"}),
    )
    is_private_consultation = forms.BooleanField(
        label="گفت‌وگوی محرمانه و اختصاصی با مشاور ارشد",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS, "id": "id_is_private"}),
    )

    class Meta:
        model = Ticket
        fields = ["title", "ticket_type", "subject", "is_private_consultation"]
        labels = {
            "title": "عنوان تیکت",
            "ticket_type": "موضوع تیکت",
            "subject": "انتخاب درس",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "یک عنوان کوتاه و مشخص بنویسید...",
                }
            ),
            "ticket_type": forms.Select(
                attrs={"class": INPUT_CLASS, "id": "id_ticket_type"}
            ),
            "subject": forms.Select(
                attrs={"class": INPUT_CLASS, "id": "id_subject"}
            ),
        }

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        if student and getattr(student, "field_id", None):
            self.fields["subject"].queryset = Subject.objects.filter(
                field_id=student.field_id, is_active=True
            )
        else:
            self.fields["subject"].queryset = Subject.objects.none()

    def clean(self):
        cleaned = super().clean()
        ticket_type = cleaned.get("ticket_type")
        subject = cleaned.get("subject")
        technical_issue = cleaned.get("technical_issue")

        # ۱. اعتبارسنجی پرسش درسی
        if ticket_type == TicketType.LESSON:
            if not subject:
                self.add_error("subject", "برای پرسش‌های درسی، انتخاب درس الزامی است.")
        else:
            cleaned["subject"] = None

        # ۲. اعتبارسنجی اشکال فنی
        if ticket_type == TicketType.TECHNICAL:
            if not technical_issue:
                self.add_error("technical_issue", "لطفاً نوع مشکل فنی را مشخص فرمایید.")

        # ۳. اعتبارسنجی مشاوره خصوصی
        if ticket_type != TicketType.PSYCHOLOGY:
            cleaned["is_private_consultation"] = False

        return cleaned


class TicketMessageForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["content", "attachment"]
        labels = {"content": "متن پیام", "attachment": "پیوست"}
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": INPUT_CLASS,
                    "rows": 4,
                    "placeholder": "پاسخ یا پیام تکمیلی خود را اینجا بنویسید...",
                }
            ),
            "attachment": forms.FileInput(attrs={"class": INPUT_CLASS}),
        }


class ModerationForm(forms.Form):
    decision = forms.ChoiceField(
        label="نتیجه بررسی",
        choices=(("approve", "تأیید"), ("reject", "رد")),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    note = forms.CharField(
        label="توضیح ناظر",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASS,
                "rows": 3,
                "placeholder": "توضیح ناظر (در صورت رد، درج علت الزامی یا توصیه می‌شود)...",
            }
        ),
    )


class ReferralForm(forms.Form):
    queue = forms.ChoiceField(
        label="ارجاع به",
        choices=TicketQueue.choices,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    assignee = forms.ModelChoiceField(
        label="کاربر مشخص",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )
    note = forms.CharField(
        label="علت ارجاع",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASS,
                "rows": 3,
                "placeholder": "توضیحات مربوط به دلیل ارجاع...",
            }
        ),
    )

    def __init__(self, *args, actor=None, ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.actor = actor
        self.ticket = ticket

        # استخراج ایمن شناسه استان تیکت
        province_id = None
        if ticket:
            if hasattr(ticket, "province") and ticket.province:
                province_id = getattr(ticket.province, "id", ticket.province)
            elif (
                getattr(ticket, "student", None)
                and getattr(ticket.student, "field", None)
                and getattr(ticket.student.field, "grade", None)
                and getattr(ticket.student.field.grade, "school", None)
            ):
                province_id = ticket.student.field.grade.school.province_id

        # ۱. محدود کردن صف‌ها (Queue) بر اساس سلسله‌مراتب
        if actor and not actor.is_superuser:
            if actor.role == UserRole.CONSULTANT:
                # مشاور فقط به معتمد استان ارجاع می‌دهد
                self.fields["queue"].choices = [(TicketQueue.TRUSTEE, "معتمد استان")]
            elif actor.role == UserRole.PROVINCE_TRUSTEE:
                # معتمد استان فقط به ادمین ارجاع می‌دهد
                self.fields["queue"].choices = [(TicketQueue.ADMIN, "مدیریت / ادمین")]
            else:
                self.fields["queue"].choices = TicketQueue.choices
        else:
            self.fields["queue"].choices = TicketQueue.choices

        # ۲. فیلتر کردن دقیق کاربران (Assignee) بر اساس نقش اقدام‌کننده
        if actor and not actor.is_superuser and actor.role == UserRole.CONSULTANT:
            # مشاور فقط معتمدین استان همان تیکت را می‌بیند
            q_trustee = Q(role=UserRole.PROVINCE_TRUSTEE)
            if province_id:
                q_trustee &= Q(trustee_provinces__province_id=province_id)
            assignee_qs = User.objects.filter(q_trustee, is_active=True)

        elif actor and not actor.is_superuser and actor.role == UserRole.PROVINCE_TRUSTEE:
            # معتمد استان فقط ادمین‌ها و سوپریوزرها را می‌بیند
            assignee_qs = User.objects.filter(
                Q(role=UserRole.ADMIN) | Q(is_superuser=True),
                is_active=True,
            )

        else:
            # ادمین / سوپریوزر / سایرین: امکان ارجاع به هر نقش ذی‌ربط
            eligible = Q(role__in=[UserRole.CONTENT_MODERATOR, UserRole.ADMIN]) | Q(
                is_superuser=True
            )
            if ticket:
                if province_id:
                    eligible |= Q(
                        role=UserRole.PROVINCE_TRUSTEE,
                        trustee_provinces__province_id=province_id,
                    )
                if ticket.ticket_type == TicketType.PSYCHOLOGY:
                    eligible |= Q(
                        role=UserRole.CONSULTANT,
                        scopes__can_answer_psychology=True,
                    )
                elif ticket.ticket_type == TicketType.LESSON and ticket.subject_id:
                    eligible |= Q(
                        role=UserRole.CONSULTANT,
                        scopes__accesses__name="ticket",
                        scopes__accesses__subject_id=ticket.subject_id,
                    )
            assignee_qs = User.objects.filter(eligible, is_active=True)

        self.fields["assignee"].queryset = assignee_qs.distinct()

    def clean(self):
        cleaned = super().clean()
        queue = cleaned.get("queue")
        assignee = cleaned.get("assignee")

        # اعتبارسنجی سلسله‌مراتب در سطح بک‌اند
        if self.actor and not self.actor.is_superuser:
            if self.actor.role == UserRole.CONSULTANT and queue != TicketQueue.TRUSTEE:
                self.add_error("queue", "مشاور تنها مجاز به ارجاع تیکت به معتمد استان است.")
            elif self.actor.role == UserRole.PROVINCE_TRUSTEE and queue != TicketQueue.ADMIN:
                self.add_error("queue", "معتمد استان تنها مجاز به ارجاع تیکت به ادمین است.")

        expected_roles = {
            TicketQueue.CONSULTANT: UserRole.CONSULTANT,
            TicketQueue.TRUSTEE: UserRole.PROVINCE_TRUSTEE,
            TicketQueue.MODERATOR: UserRole.CONTENT_MODERATOR,
            TicketQueue.ADMIN: UserRole.ADMIN,
        }

        if assignee and not (
            queue == TicketQueue.ADMIN and assignee.is_superuser
        ) and assignee.role != expected_roles.get(queue):
            self.add_error("assignee", "نقش کاربر انتخاب‌شده با مقصد ارجاع سازگار نیست.")

        return cleaned


class TicketEditForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["ticket_type", "subject", "status"]
        labels = {"ticket_type": "موضوع", "subject": "درس", "status": "وضعیت"}
        widgets = {
            "ticket_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "subject": forms.Select(attrs={"class": INPUT_CLASS}),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("ticket_type") == TicketType.LESSON and not cleaned.get("subject"):
            self.add_error("subject", "برای موضوع درسی، انتخاب درس الزامی است.")
        if cleaned.get("ticket_type") != TicketType.LESSON:
            cleaned["subject"] = None
        return cleaned
