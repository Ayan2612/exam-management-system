"""
URL Configuration for exams app
Demonstrates URL routing - Module 2, CO2
"""
from django.urls import path
from . import views

urlpatterns = [
    # ── Public URLs ──────────────────────────────
    path('', views.home, name='home'),
    path('search/', views.student_search, name='student_search'),
    path('student/register/', views.student_register, name='student_register'),
    path('student/verify/<str:token>/', views.student_verify_email, name='student_verify_email'),
    path('student/login/', views.student_login, name='student_login'),
    path('student/portal/', views.student_portal, name='student_portal'),
    path('student-portal/', views.student_portal, name='student_portal_short'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/logout/', views.student_logout, name='student_logout'),
    path('ajax/search-seat/', views.ajax_search_seat, name='ajax_search_seat'),
    path('admit-card/<int:allocation_id>/', views.download_admit_card, name='download_admit_card'),
    path('admit-card/<int:allocation_id>/view/', views.view_admit_card, name='view_admit_card'),
    path('download/template/', views.download_csv_template, name='download_csv_template'),

    # ── Authentication ────────────────────────────
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-logout/', views.admin_logout, name='admin_logout'),

    # ── Dashboard ─────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Student Management ─────────────────────────
    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_create, name='student_create'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('students/import/', views.student_import, name='student_import'),

    # ── Room Management ────────────────────────────
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/add/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', views.room_delete, name='room_delete'),

    # ── Exam Management ────────────────────────────
    path('exams/', views.exam_list, name='exam_list'),
    path('exams/create/', views.exam_create, name='exam_create'),
    path('exams/<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    path('exams/<int:pk>/delete/', views.exam_delete, name='exam_delete'),

    # ── Seating Allocation ─────────────────────────
    path('seating/', views.seating_plan, name='seating_plan'),
    path('seating/<int:exam_id>/', views.seating_detail, name='seating_detail'),
    path('seating/<int:exam_id>/clear/', views.clear_seating, name='clear_seating'),

    # ── Reports & Downloads ────────────────────────
    path('reports/exam/<int:exam_id>/pdf/', views.download_exam_pdf, name='download_exam_pdf'),
    path('reports/exam/<int:exam_id>/csv/', views.download_exam_csv, name='download_exam_csv'),
    path('reports/room/<int:exam_id>/<int:room_id>/pdf/', views.download_room_pdf, name='download_room_pdf'),
    path('reports/room/<int:exam_id>/<int:room_id>/csv/', views.download_room_csv_view, name='download_room_csv'),
]
