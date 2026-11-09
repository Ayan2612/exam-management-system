from django.test import TestCase
from django.urls import reverse

from .models import Exam, Student


class StudentPortalTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            roll_number='992401030018',
            name='Test Student',
            email='student@example.com',
            course='B.Tech CSE',
            semester=1,
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
            subject='CSE Semester Five',
            exam_date='2099-01-10',
            start_time='09:00',
            end_time='12:00',
            target_course='B.Tech CSE',
            target_semester=5,
        )
        Exam.objects.create(
            subject='ECE Semester Five',
            exam_date='2099-01-11',
            start_time='09:00',
            end_time='12:00',
            target_course='B.Tech ECE',
            target_semester=5,
        )
        response = self.client.post(reverse('student_portal'), {
            'roll_number': self.student.roll_number,
        })
        self.assertContains(response, 'CSE Semester Five')
        self.assertNotContains(response, 'ECE Semester Five')


class JIITRollNumberSemesterTests(TestCase):
    def test_2024_batch_maps_to_semester_five_in_november_2026(self):
        from unittest.mock import patch
        from datetime import date
        from django.utils import timezone
        from .views import _jiit_semester_from_roll_number
        with patch('exams.views.timezone.localdate', return_value=date(2026, 11, 9)):
            self.assertEqual(_jiit_semester_from_roll_number('992401030018', 1), (5, 2024))

    def test_2025_batch_maps_to_semester_three_in_november_2026(self):
        from unittest.mock import patch
        from datetime import date
        from .views import _jiit_semester_from_roll_number
        with patch('exams.views.timezone.localdate', return_value=date(2026, 11, 9)):
            self.assertEqual(_jiit_semester_from_roll_number('992501030018', 1), (3, 2025))

    def test_2026_batch_maps_to_semester_one_in_november_2026(self):
        from unittest.mock import patch
        from datetime import date
        from .views import _jiit_semester_from_roll_number
        with patch('exams.views.timezone.localdate', return_value=date(2026, 11, 9)):
            self.assertEqual(_jiit_semester_from_roll_number('992601030018', 1), (1, 2026))


class ExamAllocationCriteriaTests(TestCase):
    def setUp(self):
        from datetime import date, time
        from .models import Room
        self.exam = Exam.objects.create(
            subject='Full Stack Lab', exam_date=date(2026, 12, 1),
            start_time=time(10), end_time=time(13),
            target_course='B.Tech CSE', target_semester=5,
        )
        self.room = Room.objects.create(
            room_number='A101', building='Block A', capacity=10,
        )
        self.eligible = [
            Student.objects.create(
                roll_number=f'9924010300{i:02d}', name=f'Eligible {i}',
                email=f'eligible{i}@example.com', course='B.Tech CSE', semester=5,
            ) for i in range(1, 6)
        ]
        self.wrong_semester = Student.objects.create(
            roll_number='992401030099', name='Wrong semester',
            email='wrongsemester@example.com', course='B.Tech CSE', semester=3,
        )

    def test_form_rejects_students_outside_exam_semester(self):
        from .forms import SeatingAllocationForm
        form = SeatingAllocationForm(data={
            'exam': self.exam.pk, 'rooms': [self.room.pk],
            'students': [student.pk for student in self.eligible] + [self.wrong_semester.pk],
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(any('course/semester criteria' in str(error) for error in form.non_field_errors()))

    def test_different_subjects_can_share_room_in_same_slot_with_distinct_seats(self):
        from datetime import time
        from .models import SeatingAllocation
        from .utils import allocate_seats, save_allocations
        dsa = Exam.objects.create(
            subject='DSA', exam_date=self.exam.exam_date,
            start_time=time(10), end_time=time(13),
            target_course='B.Tech CSE', target_semester=3,
        )
        dsa_students = [
            Student.objects.create(
                roll_number=f'9925010300{i:02d}', name=f'DSA {i}',
                email=f'dsa{i}@example.com', course='B.Tech CSE', semester=3,
            ) for i in range(1, 6)
        ]
        self.assertEqual(save_allocations(allocate_seats(dsa, [self.room], dsa_students))[0], 5)
        self.assertEqual(save_allocations(allocate_seats(self.exam, [self.room], self.eligible))[0], 5)
        seats = list(SeatingAllocation.objects.filter(room=self.room).values_list('seat_number', flat=True))
        self.assertEqual(len(seats), 10)
        self.assertEqual(len(set(seats)), 10)

    def test_overlapping_exams_cannot_exceed_shared_room_capacity(self):
        from datetime import time
        from .utils import allocate_seats, save_allocations
        dsa = Exam.objects.create(
            subject='DSA', exam_date=self.exam.exam_date,
            start_time=time(10), end_time=time(13),
            target_course='B.Tech CSE', target_semester=3,
        )
        dsa_students = [
            Student.objects.create(
                roll_number=f'9925010400{i:02d}', name=f'DSA Extra {i}',
                email=f'dsaextra{i}@example.com', course='B.Tech CSE', semester=3,
            ) for i in range(1, 6)
        ]
        save_allocations(allocate_seats(dsa, [self.room], dsa_students))
        extra = Student.objects.create(
            roll_number='992401040099', name='Extra',
            email='extra@example.com', course='B.Tech CSE', semester=5,
        )
        with self.assertRaisesMessage(ValueError, 'Insufficient free capacity'):
            allocate_seats(self.exam, [self.room], self.eligible + [extra])
