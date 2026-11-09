"""
Models for Exam Management System
Demonstrates Django ORM - Module 4, CO3
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings


class Student(models.Model):
    """Student model - stores student information"""
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]
    COURSE_CHOICES = [
        ('B.Tech CSE', 'B.Tech CSE'),
        ('B.Tech ECE', 'B.Tech ECE'),
        ('B.Tech ME', 'B.Tech ME'),
        ('B.Tech CE', 'B.Tech CE'),
        ('B.Tech EE', 'B.Tech EE'),
        ('BCA', 'BCA'),
        ('MCA', 'MCA'),
        ('M.Tech', 'M.Tech'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')
    roll_number = models.CharField(max_length=20, unique=True, verbose_name='Roll Number')
    name = models.CharField(max_length=100, verbose_name='Full Name')
    email = models.EmailField(unique=True, verbose_name='Email Address')
    course = models.CharField(max_length=50, choices=COURSE_CHOICES, default='B.Tech CSE')
    semester = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['roll_number']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return f"{self.roll_number} - {self.name}"


class Room(models.Model):
    """Room model - stores exam room information"""
    BUILDING_CHOICES = [
        ('Block A', 'Block A'),
        ('Block B', 'Block B'),
        ('Block C', 'Block C'),
        ('Block D', 'Block D'),
        ('Main Block', 'Main Block'),
        ('Lab Block', 'Lab Block'),
    ]

    room_number = models.CharField(max_length=20, unique=True, verbose_name='Room Number')
    building = models.CharField(max_length=50, choices=BUILDING_CHOICES, default='Block A')
    capacity = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Seating Capacity'
    )
    floor = models.IntegerField(default=0, verbose_name='Floor Number')
    is_active = models.BooleanField(default=True, verbose_name='Available for Exams')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['building', 'room_number']
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'

    def __str__(self):
        return f"{self.room_number} ({self.building}) - Cap: {self.capacity}"

    @property
    def full_name(self):
        return f"{self.building} - {self.room_number}"


class Exam(models.Model):
    """Exam model - stores examination details"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    subject = models.CharField(max_length=150, verbose_name='Subject Name')
    subject_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='Subject Code')
    exam_date = models.DateField(verbose_name='Exam Date')
    start_time = models.TimeField(verbose_name='Start Time')
    end_time = models.TimeField(verbose_name='End Time')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exam_date', 'subject']
        verbose_name = 'Exam'
        verbose_name_plural = 'Exams'

    def __str__(self):
        return f"{self.subject} - {self.exam_date}"

    @property
    def total_allocated(self):
        return self.seatingallocation_set.count()

    @property
    def total_capacity(self):
        rooms = Room.objects.filter(
            seatingallocation__exam=self
        ).distinct()
        return sum(r.capacity for r in rooms)


class SeatingAllocation(models.Model):
    """
    SeatingAllocation model - Many-to-Many through table
    Links Student, Exam, and Room with seat assignment
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='Student')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, verbose_name='Exam')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, verbose_name='Room')
    seat_number = models.IntegerField(verbose_name='Seat Number')
    allocated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate: same student in same exam
        unique_together = [
            ('student', 'exam'),
            ('exam', 'room', 'seat_number'),
        ]
        ordering = ['room', 'seat_number']
        verbose_name = 'Seating Allocation'
        verbose_name_plural = 'Seating Allocations'

    def __str__(self):
        return f"{self.student.roll_number} → {self.room.room_number} Seat {self.seat_number}"
