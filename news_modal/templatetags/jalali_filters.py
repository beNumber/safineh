import jdatetime

from django import template
from django.utils import timezone


register = template.Library()


PERSIAN_DIGITS = str.maketrans(
    "0123456789",
    "۰۱۲۳۴۵۶۷۸۹",
)


@register.filter
def to_jalali(value, date_format="%Y/%m/%d - %H:%M"):
    if not value:
        return ""

    try:
        if timezone.is_aware(value):
            value = timezone.localtime(value)

        jalali_date = jdatetime.datetime.fromgregorian(
            datetime=value
        )

        result = jalali_date.strftime(date_format)

        return result.translate(PERSIAN_DIGITS)

    except (TypeError, ValueError, AttributeError):
        return ""
