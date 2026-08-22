from django import template
from django.utils import timezone
import jdatetime

register = template.Library()

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def jalali(value, fmt="%Y/%m/%d - %H:%M"):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    text = jdatetime.datetime.fromgregorian(datetime=value).strftime(fmt)
    return text.translate(FA_DIGITS)
