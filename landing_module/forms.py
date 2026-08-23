from django import forms
from .models import ConsultationRequest


class ConsultationModalForm(forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        fields = ['full_name', 'phone_number', 'target_field', 'message']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition',
                'placeholder': 'مثال: علی رضایی'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition',
                'placeholder': '۰۹۱۲۰۰۰۰۰۰۰'
            }),
            'target_field': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition',
                'placeholder': 'مثال: کنکور تجربی / ارشد کامپیوتر'
            }),
            'message': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none transition resize-none',
                'rows': 3,
                'placeholder': 'توضیحات تکمیلی یا سوالات تحصیلی خود را بنویسید...'
            }),
        }
