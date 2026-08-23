from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dash_view(request):
    return render(request, "dashboard_module/dash.html")