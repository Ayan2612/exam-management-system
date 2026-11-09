"""Django Admin registration for Exam Management System"""
from django.contrib import admin
from .models import Student, Room, Exam, SeatingAllocation


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['roll_number', 'name', 'email', 'course', 'semester', 'created_at']
    list_filter = ['course', 'semester']
    search_fields = ['roll_number', 'name', 'email']
    ordering = ['roll_number']


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'building', 'capacity', 'floor', 'is_active']
    list_filter = ['building', 'is_active']
    search_fields = ['room_number', 'building']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['subject', 'subject_code', 'exam_date', 'start_time', 'end_time', 'status']
    list_filter = ['status', 'exam_date']
    search_fields = ['subject', 'subject_code']
    ordering = ['-exam_date']


@admin.register(SeatingAllocation)
class SeatingAllocationAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'room', 'seat_number', 'allocated_at']
    list_filter = ['exam', 'room']
    search_fields = ['student__roll_number', 'student__name']
    raw_id_fields = ['student', 'exam', 'room']


# Customize admin site
admin.site.site_header = "Exam Management System"
admin.site.site_title = "EMS Admin"
admin.site.index_title = "Administration Panel"
