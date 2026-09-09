from django import forms
from django.utils import timezone

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

    def clean(self):
        """اگر خبر منتشر می‌شود اما زمان انتشار ندارد، زمان حال را قرار بده"""
        cleaned = super().clean()
        status = cleaned.get("status")
        published_at = cleaned.get("published_at")

        if status == Article.Status.PUBLISHED and published_at is None:
            cleaned["published_at"] = timezone.now()

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
