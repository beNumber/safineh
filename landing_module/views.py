from django.shortcuts import render
from django.utils import timezone

from blog_module.models import Post
from news_module.models import Article

def landing_home_view(request):
    """
    نمایش صفحه اصلی سامانه آموزشی مدرسه
    """
    # تعریف ساختار پایه‌های تحصیلی مدرسه
    educational_stages = [
        {
            'title': 'دوره دوم ابتدایی',
            'desc': 'آموزش مفاهیم پایه، تقویت خلاقیت و مهارت‌های حل مسئله',
            'grades': [
                {'name': 'پایه پنجم دبستان', 'icon': 'fa-child-reaching', 'color': 'from-amber-500 to-orange-500'},
                {'name': 'پایه ششم دبستان', 'icon': 'fa-graduation-cap', 'color': 'from-orange-500 to-amber-600'},
            ]
        },
        {
            'title': 'دوره اول متوسطه',
            'desc': 'تقویت دروس علوم پایه، ریاضیات و آمادگی برای انتخاب رشته',
            'grades': [
                {'name': 'پایه هفتم', 'icon': 'fa-book-bookmark', 'color': 'from-emerald-500 to-teal-600'},
                {'name': 'پایه هشتم', 'icon': 'fa-shapes', 'color': 'from-teal-500 to-cyan-600'},
                {'name': 'پایه نهم (هدایت تحصیلی)', 'icon': 'fa-compass', 'color': 'from-cyan-500 to-blue-600'},
            ]
        },
        {
            'title': 'دوره دوم متوسطه (پایه‌های دهم، یازدهم و دوازدهم)',
            'desc': 'آموزش تخصصی رشته‌ها، آمادگی امتحانات نهایی و کنکور سراسری',
            'branches': [
                {
                    'name': 'رشته علوم تجربی',
                    'icon': 'fa-flask-vial',
                    'color': 'from-emerald-600 to-green-700',
                    'grades': ['دهم تجربی', 'یازدهم تجربی', 'دوازدهم تجربی']
                },
                {
                    'name': 'رشته ریاضی و فیزیک',
                    'icon': 'fa-square-root-variable',
                    'color': 'from-blue-600 to-indigo-700',
                    'grades': ['دهم ریاضی', 'یازدهم ریاضی', 'دوازدهم ریاضی']
                },
                {
                    'name': 'رشته علوم انسانی',
                    'icon': 'fa-scale-balanced',
                    'color': 'from-purple-600 to-violet-700',
                    'grades': ['دهم انسانی', 'یازدهم انسانی', 'دوازدهم انسانی']
                },
            ]
        }
    ]

    published_posts = Post.published.select_related('category', 'author').prefetch_related('tags')
    published_news = Article.objects.filter(
        status=Article.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    ).select_related('category', 'author').prefetch_related('tags')

    # سوالات متداول سامانه
    school_faqs = [
        {
            'question': 'چگونه می‌توانم به جزوات و آزمون‌های کلاسی دسترسی پیدا کنم؟',
            'answer': 'دانش‌آموزان می‌توانند پس از ورود به حساب کاربری خود، از بخش پایه‌های تحصیلی و میز کار شخصی به کلیه محتواها، فیلم‌ها و آزمون‌ها دسترسی داشته باشند.'
        },
        {
            'question': 'آیا برای ورود به سامانه نیاز به ثبت‌نام جداگانه است؟',
            'answer': 'خیر، اطلاعات ورود برای کلیه دانش‌آموزان توسط واحد فناوری مدرسه صادر و از طریق پنل ورود در دسترس است.'
        },
        {
            'question': 'امتحانات آنلاین و تکالیف چگونه بارگذاری می‌شوند؟',
            'answer': 'از طریق بخش داشبورد دانش‌آموزی، بخش تکالیف و سامانه آزمون اختصاصی مدرسه قابل دریافت و ارسال است.'
        },
        {
            'question': 'آیا مقالات و اخبار مدرسه برای عموم در دسترس است؟',
            'answer': 'بله، بخش اخبار مدرسه و مقالات آموزشی جهت ارتقای سطح علمی دانش‌آموزان و اولیا به صورت آزاد قابل مطالعه است.'
        }
    ]

    context = {
        'stages': educational_stages,
        'news': published_news[:3],
        'articles': published_posts[:3],
        'faqs': school_faqs,
    }
    return render(request, 'landing_module/index.html', context)
