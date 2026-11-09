from django.test import TestCase
from django.urls import reverse

from .models import Exam, Student


class StudentPortalTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            roll_number='24B15CS001',
            name='Test Student',
            email='student@example.com',
            course='B.Tech CSE',
            semester=4,
        )

    def test_student_portal_opens_without_admin_or_student_login(self):
        response = self.client.get(reverse('student_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'University roll number')
        self.assertContains(response, 'View my portal')

    def test_roll_number_shows_only_matching_student_dashboard(self):
        response = self.client.post(reverse('student_portal'), {
            'roll_number': self.student.roll_number,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.name)
        self.assertContains(response, self.student.roll_number)
        self.assertNotContains(response, self.student.email)

    def test_unknown_roll_number_shows_validation_error(self):
        response = self.client.post(reverse('student_portal'), {
            'roll_number': 'NOT-A-REAL-ROLL',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No student record found')

    def test_student_portal_still_opens_while_admin_is_logged_in(self):
        from django.contrib.auth.models import User
        admin = User.objects.create_superuser(
            username='portaladmin',
            email='admin@example.com',
            password='TestAdmin!2026#',
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('student_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'University roll number')

    def test_exam_list_is_filtered_by_course_and_semester(self):
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
        response = self.client.post(reverse('student_portal'), {
            'roll_number': self.student.roll_number,
        })
        self.assertContains(response, 'CSE Semester Four')
        self.assertNotContains(response, 'ECE Semester Four')
