from django import forms
from django.contrib.auth import get_user_model

from auth_module.models import UserRole

from .models import StudentConsultantAssignment


GLASS_FIELD = (
    "w-full rounded-2xl border border-white/70 bg-white/70 px-4 py-3 text-sm text-slate-700 "
    "shadow-sm outline-none backdrop-blur-xl transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
)


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentConsultantAssignment
        fields = ["consultant", "note"]
        widgets = {
            "consultant": forms.Select(attrs={"class": GLASS_FIELD}),
            "note": forms.TextInput(
                attrs={"class": GLASS_FIELD, "placeholder": "مثلاً: پیگیری هفتگی آزمون‌ها"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["consultant"].queryset = get_user_model().objects.filter(
            role=UserRole.CONSULTANT, is_active=True
        ).order_by("last_name", "first_name", "username")
        self.fields["consultant"].label_from_instance = lambda user: (
            user.get_full_name().strip() or user.username
        )


class PrivateCounselingTicketForm(forms.Form):
    title = forms.CharField(
        label="موضوع گفت‌وگو",
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": GLASS_FIELD, "placeholder": "مثلاً: برنامه‌ریزی برای آزمون هفته آینده"}
        ),
    )
    content = forms.CharField(
        label="پیام شما",
        widget=forms.Textarea(
            attrs={"class": GLASS_FIELD, "rows": 6, "placeholder": "هر چیزی که لازم است مشاورت بداند..."}
        ),
    )
    attachment = forms.FileField(
        label="پیوست (اختیاری)", required=False, widget=forms.FileInput(attrs={"class": GLASS_FIELD})
    )
