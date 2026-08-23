from django.contrib import admin
from .models import Category, Instructor, Course, FAQ, Testimonial, ConsultationRequest


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'icon')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialty')
    search_fields = ('name', 'specialty')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'instructor', 'level', 'price', 'is_featured')
    list_filter = ('level', 'is_featured', 'category')
    search_fields = ('title',)
    list_editable = ('is_featured', 'price')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order')
    list_editable = ('order',)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'major_or_rank', 'rating')
    list_filter = ('rating',)


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'target_field', 'created_at', 'is_called')
    list_filter = ('is_called', 'created_at')
    search_fields = ('full_name', 'phone_number', 'target_field')
    list_editable = ('is_called',)
