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


class AdditionalValidationTests(TestCase):
    def setUp(self):
        from datetime import date, time
        from .models import Room
        self.date = date(2026, 12, 10)
        self.room = Room.objects.create(room_number='T101', building='Block A', capacity=10)
        self.exam = Exam.objects.create(
            subject='Networks', exam_date=self.date, start_time=time(10),
            end_time=time(12), target_course='B.Tech CSE', target_semester=5,
        )
        self.students = [
            Student.objects.create(
                roll_number=f'9924010500{i:02d}', name=f'Candidate {i}',
                email=f'candidate{i}@example.com', course='B.Tech CSE', semester=5,
            ) for i in range(1, 4)
        ]

    def test_exam_form_rejects_end_time_before_start_time(self):
        from .forms import ExamForm
        form = ExamForm(data={
            'subject': 'Invalid timing', 'subject_code': 'CS1',
            'target_course': 'B.Tech CSE', 'target_semester': 5,
            'exam_date': '2026-12-10', 'start_time': '13:00',
            'end_time': '12:00', 'status': 'scheduled', 'description': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('end_time', form.errors)

    def test_exam_form_rejects_equal_start_and_end_time(self):
        from .forms import ExamForm
        form = ExamForm(data={
            'subject': 'Zero duration', 'subject_code': 'CS2',
            'target_course': 'B.Tech CSE', 'target_semester': 5,
            'exam_date': '2026-12-10', 'start_time': '10:00',
            'end_time': '10:00', 'status': 'scheduled', 'description': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('end_time', form.errors)

    def test_partial_overlap_uses_different_physical_seats(self):
        from datetime import time
        from .models import SeatingAllocation
        from .utils import allocate_seats, save_allocations
        first_students = self.students
        second_students = [
            Student.objects.create(
                roll_number=f'9925010500{i:02d}', name=f'Other {i}',
                email=f'other{i}@example.com', course='B.Tech CSE', semester=3,
            ) for i in range(1, 4)
        ]
        save_allocations(allocate_seats(self.exam, [self.room], first_students))
        overlapping = Exam.objects.create(
            subject='Cloud Computing', exam_date=self.date, start_time=time(11),
            end_time=time(13), target_course='B.Tech CSE', target_semester=3,
        )
        save_allocations(allocate_seats(overlapping, [self.room], second_students))
        seats = list(SeatingAllocation.objects.filter(room=self.room).values_list('seat_number', flat=True))
        self.assertEqual(len(seats), 6)
        self.assertEqual(len(seats), len(set(seats)))

    def test_back_to_back_exams_can_reuse_same_seats(self):
        from datetime import time
        from .models import SeatingAllocation
        from .utils import allocate_seats, save_allocations
        save_allocations(allocate_seats(self.exam, [self.room], self.students))
        next_exam = Exam.objects.create(
            subject='Operating Systems', exam_date=self.date, start_time=time(12),
            end_time=time(14), target_course='B.Tech CSE', target_semester=5,
        )
        next_students = [
            Student.objects.create(
                roll_number=f'9924010600{i:02d}', name=f'Next {i}',
                email=f'next{i}@example.com', course='B.Tech CSE', semester=5,
            ) for i in range(1, 4)
        ]
        save_allocations(allocate_seats(next_exam, [self.room], next_students))
        first_seats = set(SeatingAllocation.objects.filter(exam=self.exam).values_list('seat_number', flat=True))
        next_seats = set(SeatingAllocation.objects.filter(exam=next_exam).values_list('seat_number', flat=True))
        self.assertEqual(first_seats, next_seats)

    def test_student_cannot_be_allocated_to_overlapping_exams(self):
        from datetime import time
        from .forms import SeatingAllocationForm
        from .utils import allocate_seats, save_allocations
        from .models import SeatingAllocation
        save_allocations(allocate_seats(self.exam, [self.room], [self.students[0]]))
        overlapping = Exam.objects.create(
            subject='Data Structures', exam_date=self.date, start_time=time(11),
            end_time=time(13), target_course='B.Tech CSE', target_semester=5,
        )
        form = SeatingAllocationForm(data={
            'exam': overlapping.pk, 'rooms': [self.room.pk],
            'students': [self.students[0].pk],
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(any('overlapping time slot' in str(error) for error in form.non_field_errors()))
        with self.assertRaisesMessage(ValueError, 'overlapping time slot'):
            allocate_seats(overlapping, [self.room], [self.students[0]])

    def test_csv_import_rejects_invalid_roll_course_semester_and_phone(self):
        from io import BytesIO
        from .utils import import_students_from_csv
        csv_data = (
            'roll_number,name,email,course,semester,phone\\n'
            '123,Invalid Roll,bad@example.com,B.Tech CSE,5,9876543210\\n'
            '992401030099,Invalid Course,course@example.com,Unknown,5,9876543210\\n'
            '992401030098,Invalid Semester,semester@example.com,B.Tech CSE,9,9876543210\\n'
            '992401030097,Invalid Phone,phone@example.com,B.Tech CSE,5,12345\\n'
        )
        success, errors = import_students_from_csv(BytesIO(csv_data.encode('utf-8')))
        self.assertEqual(success, 0)
        self.assertEqual(len(errors), 4)
        self.assertEqual(Student.objects.count(), 3)

    def test_csv_import_rejects_blank_mandatory_field(self):
        from io import BytesIO
        from .utils import import_students_from_csv
        csv_data = (
            'roll_number,name,email,course,semester,phone\\n'
            '992401030099,Blank Phone,blank@example.com,B.Tech CSE,5,\\n'
        )
        success, errors = import_students_from_csv(BytesIO(csv_data.encode('utf-8')))
        self.assertEqual(success, 0)
        self.assertTrue(any('mandatory' in error for error in errors))
