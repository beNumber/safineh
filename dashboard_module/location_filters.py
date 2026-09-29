from auth_module.models import ProvinceTrustee, UserRole
from users_module.models import Province, School


def location_options(request, students=None):
    provinces = Province.objects.all()
    if students is not None:
        provinces = provinces.filter(schools__grades__fields__student__in=students).distinct()
    elif request.user.role == UserRole.PROVINCE_TRUSTEE and not request.user.is_superuser:
        provinces = provinces.filter(pk__in=ProvinceTrustee.objects.filter(user=request.user).values("province_id"))
    provinces = provinces.order_by("name")
    province_id = request.GET.get("province", "")
    school_id = request.GET.get("school", "")
    selected_province = int(province_id) if province_id.isdecimal() and provinces.filter(pk=province_id).exists() else None
    schools = School.objects.filter(province_id=selected_province).order_by("name") if selected_province else School.objects.none()
    selected_school = int(school_id) if school_id.isdecimal() and schools.filter(pk=school_id).exists() else None
    return {
        "filter_provinces": provinces,
        "filter_schools": schools,
        "selected_province": selected_province,
        "selected_school": selected_school,
    }
