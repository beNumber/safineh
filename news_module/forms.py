from django import forms
from django.utils import timezone

from users_module.models import Grade, Province, School

from .models import Article, Category, Tag


class ArticleForm(forms.ModelForm):
    """فرم ایجاد و ویرایش خبر"""

    class Meta:
        model = Article
        fields = [
            "title",
            "slug",
            "category",
            "tags",
            "target_provinces",
            "target_schools",
            "target_grades",
            "summary",
            "content",
            "image",
            "status",
            "is_featured",
            "published_at",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "عنوان خبر را وارد کنید",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "اگر خالی بماند، خودکار ساخته می‌شود",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                }
            ),
            "tags": forms.SelectMultiple(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                }
            ),
            "target_provinces": forms.SelectMultiple(
                attrs={"class": "audience-select", "data-audience": "province"}
            ),
            "target_schools": forms.SelectMultiple(
                attrs={"class": "audience-select", "data-audience": "school"}
            ),
            "target_grades": forms.SelectMultiple(
                attrs={"class": "audience-select", "data-audience": "grade"}
            ),
            "summary": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "rows": 3,
                    "placeholder": "خلاصه‌ای از خبر بنویسید",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "rows": 10,
                    "placeholder": "متن کامل خبر",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                }
            ),
            "is_featured": forms.CheckboxInput(
                attrs={
                    "class": "h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500",
                }
            ),
            "published_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                },
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_provinces"].queryset = Province.objects.order_by("name")
        self.fields["target_schools"].queryset = School.objects.select_related("province").order_by("province__name", "name")
        self.fields["target_grades"].queryset = Grade.objects.filter(is_active=True).select_related("school__province").order_by("school__province__name", "school__name", "title")
        self.fields["target_schools"].label_from_instance = lambda school: f"{school.name} — {school.province}"
        self.fields["target_grades"].label_from_instance = lambda grade: f"{grade.title} — {grade.school.name}"

    def clean(self):
        """اگر خبر منتشر می‌شود اما زمان انتشار ندارد، زمان حال را قرار بده"""
        cleaned = super().clean()
        status = cleaned.get("status")
        published_at = cleaned.get("published_at")

        if status == Article.Status.PUBLISHED and published_at is None:
            cleaned["published_at"] = timezone.now()

        provinces = cleaned.get("target_provinces") or Province.objects.none()
        schools = cleaned.get("target_schools") or School.objects.none()
        grades = cleaned.get("target_grades") or Grade.objects.none()
        if provinces.exists() and schools.exclude(province__in=provinces).exists():
            self.add_error("target_schools", "همه مدارس انتخاب‌شده باید متعلق به استان‌های مخاطب باشند.")
        if schools.exists() and grades.exclude(school__in=schools).exists():
            self.add_error("target_grades", "همه پایه‌های انتخاب‌شده باید متعلق به مدارس مخاطب باشند.")
        if provinces.exists() and grades.exclude(school__province__in=provinces).exists():
            self.add_error("target_grades", "همه پایه‌های انتخاب‌شده باید متعلق به استان‌های مخاطب باشند.")

        return cleaned


class CategoryForm(forms.ModelForm):
    """فرم ایجاد و ویرایش دسته‌بندی"""

    class Meta:
        model = Category
        fields = ["name", "slug", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "نام دسته‌بندی",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "اگر خالی بماند، خودکار ساخته می‌شود",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500",
                }
            ),
        }


class TagForm(forms.ModelForm):
    """فرم ایجاد و ویرایش تگ"""

    class Meta:
        model = Tag
        fields = ["name", "slug"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "نام تگ",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500",
                    "placeholder": "اگر خالی بماند، خودکار ساخته می‌شود",
                }
            ),
        }
