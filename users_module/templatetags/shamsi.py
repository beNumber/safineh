import jdatetime

from django import template
from django.utils import timezone


register = template.Library()

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _local_datetime(value):
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


@register.filter(name="shamsi")
def shamsi(value, date_format="%Y/%m/%d - %H:%M"):
    """تبدیل date/datetime میلادی جنگو به تاریخ شمسی با ارقام فارسی."""
    if not value:
        return ""

    try:
        value = _local_datetime(value)
        if hasattr(value, "hour"):
            converted = jdatetime.datetime.fromgregorian(datetime=value)
        else:
            converted = jdatetime.date.fromgregorian(date=value)
        return converted.strftime(date_format).translate(PERSIAN_DIGITS)
    except (TypeError, ValueError, AttributeError):
        return ""


@register.simple_tag(name="shamsi_now")
def shamsi_now(date_format="%Y/%m/%d"):
    """تاریخ و ساعت فعلی را بر اساس TIME_ZONE پروژه به‌صورت شمسی برمی‌گرداند."""
    value = timezone.localtime()
    return (
        jdatetime.datetime.fromgregorian(datetime=value)
        .strftime(date_format)
        .translate(PERSIAN_DIGITS)
    )
