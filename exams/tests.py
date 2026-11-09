import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Exam, Room, SeatingAllocation, Student


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StudentPortalTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            roll_number='24B15CS001',
            name='Test Student',
            email='student@example.com',
            course='B.Tech CSE',
            semester=4,
        )

    def test_registration_requires_existing_roll_and_email_pair(self):
        response = self.client.post(reverse('student_register'), {
            'roll_number': self.student.roll_number,
            'email': 'wrong@example.com',
            'password1': 'ExamPortal!2026#Secure',
            'password2': 'ExamPortal!2026#Secure',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username=self.student.roll_number).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_registration_sends_verification_and_activates_account(self):
        response = self.client.post(reverse('student_register'), {
            'roll_number': self.student.roll_number,
            'email': self.student.email,
            'password1': 'ExamPortal!2026#Secure',
            'password2': 'ExamPortal!2026#Secure',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(username=self.student.roll_number)
        self.assertFalse(user.is_active)
        match = re.search(r'http://testserver(/student/verify/[^\s]+)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        verified = self.client.get(match.group(1))
        self.assertEqual(verified.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(Student.objects.get(pk=self.student.pk).user_id, user.pk)
        dashboard = self.client.get(reverse('student_dashboard'))
        self.assertEqual(dashboard.status_code, 200)

    def test_dashboard_only_shows_matching_course_and_semester(self):
        user = User.objects.create_user(
            username=self.student.roll_number,
            email=self.student.email,
            password='ExamPortal!2026#Secure',
        )
        self.student.user = user
        self.student.save(update_fields=['user'])
        self.client.force_login(user)
        Exam.objects.create(
            subject='CSE Semester Four',
            exam_date='2099-01-10',
            start_time='09:00',
            end_time='12:00',
            target_course='B.Tech CSE',
            target_semester=4,
        )
        Exam.objects.create(
            subject='ECE Semester Four',
            exam_date='2099-01-11',
            start_time='09:00',
            end_time='12:00',
            target_course='B.Tech ECE',
            target_semester=4,
        )
        response = self.client.get(reverse('student_dashboard'))
        self.assertContains(response, 'CSE Semester Four')
        self.assertNotContains(response, 'ECE Semester Four')

    def test_student_cannot_view_another_students_admit_card(self):
        user = User.objects.create_user(
            username=self.student.roll_number,
            email=self.student.email,
            password='ExamPortal!2026#Secure',
        )
        self.student.user = user
        self.student.save(update_fields=['user'])
        other = Student.objects.create(
            roll_number='24B15CS002',
            name='Other Student',
            email='other@example.com',
            course='B.Tech CSE',
            semester=4,
        )
        exam = Exam.objects.create(
            subject='Secure Exam',
            exam_date='2099-01-10',
            start_time='09:00',
            end_time='12:00',
        )
        room = Room.objects.create(room_number='T101', capacity=20)
        allocation = SeatingAllocation.objects.create(
            student=other, exam=exam, room=room, seat_number=1,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('view_admit_card', args=[allocation.pk]))
        self.assertEqual(response.status_code, 403)
