"""
Forms for Exam Management System
Demonstrates ModelForms - Module 4, CO3
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Student, Room, Exam, SeatingAllocation


class StyledFormMixin:
    """Mixin to add Bootstrap classes to all form fields"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})


class AdminLoginForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter password',
        })
    )


class StudentForm(StyledFormMixin, forms.ModelForm):
    """Form for creating/editing students"""
    class Meta:
        model = Student
        fields = ['roll_number', 'name', 'email', 'course', 'semester', 'phone']
        widgets = {
            'roll_number': forms.TextInput(attrs={'placeholder': 'e.g., 21B15CS001'}),
            'name': forms.TextInput(attrs={'placeholder': 'Full name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'student@college.edu'}),
            'phone': forms.TextInput(attrs={'placeholder': '10-digit mobile number'}),
        }


class RoomForm(StyledFormMixin, forms.ModelForm):
    """Form for creating/editing rooms"""
    class Meta:
        model = Room
        fields = ['room_number', 'building', 'capacity', 'floor', 'is_active']
        widgets = {
            'room_number': forms.TextInput(attrs={'placeholder': 'e.g., A101'}),
            'capacity': forms.NumberInput(attrs={'min': 1, 'placeholder': 'e.g., 30'}),
            'floor': forms.NumberInput(attrs={'min': 0}),
        }


class ExamForm(StyledFormMixin, forms.ModelForm):
    """Form for creating/editing exams"""
    class Meta:
        model = Exam
        fields = ['subject', 'subject_code', 'target_course', 'target_semester', 'exam_date', 'start_time', 'end_time', 'status', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'e.g., Data Structures & Algorithms'}),
            'subject_code': forms.TextInput(attrs={'placeholder': 'e.g., CS301'}),
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'placeholder': 'Optional exam notes...', 'rows': 3}),
        }


class CSVUploadForm(forms.Form):
    """Form for uploading CSV/Excel student data"""
    file = forms.FileField(
        label='Upload CSV or Excel File',
        help_text='Columns required: roll_number, name, email, course, semester',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
        })
    )


class SeatingAllocationForm(forms.Form):
    """Form for creating seating allocation for an exam"""
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(status='scheduled'),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label='Select Exam',
        empty_label='-- Select an Exam --',
    )
    rooms = forms.ModelMultipleChoiceField(
        queryset=Room.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'room-checkbox'}),
        label='Select Rooms',
        help_text='Select one or more rooms for the exam',
    )
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'student-checkbox'}),
        label='Select Students',
        help_text='Select students to allocate seats',
    )

    def clean(self):
        cleaned_data = super().clean()
        rooms = cleaned_data.get('rooms')
        students = cleaned_data.get('students')
        if rooms and students:
            total_capacity = sum(r.capacity for r in rooms)
            total_students = students.count()
            if total_students > total_capacity:
                raise forms.ValidationError(
                    f'Insufficient capacity! {total_students} students but only {total_capacity} seats available.'
                )
        return cleaned_data


class StudentSearchForm(forms.Form):
    """Form for AJAX student seat search"""
    roll_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your Roll Number (e.g., 21B15CS001)',
            'id': 'roll_number_input',
            'autocomplete': 'off',
        }),
        label='Roll Number'
    )
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'exam_select'}),
        label='Select Exam',
        empty_label='-- Select Exam --',
        required=False,
    )


class StudentRegistrationForm(forms.Form):
    """Verify a pre-enrolled student record before creating a portal account."""
    roll_number = forms.CharField(max_length=20, label='University roll number')
    email = forms.EmailField(label='Registered college email')
    password1 = forms.CharField(
        label='Create password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        self.fields['roll_number'].widget.attrs.update({
            'placeholder': 'Enter the roll number provided by the institute',
            'autocomplete': 'username',
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Use the email registered with the Examination Office',
            'autocomplete': 'email',
        })

    def clean(self):
        from django.contrib.auth import password_validation
        from django.contrib.auth.models import User
        from django.core.exceptions import ValidationError
        from django.db.models import Q

        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The passwords do not match.')

        roll_number = cleaned.get('roll_number', '').strip()
        email = cleaned.get('email', '').strip()
        if roll_number and email:
            try:
                student = Student.objects.get(
                    roll_number__iexact=roll_number,
                    email__iexact=email,
                )
            except Student.DoesNotExist:
                raise forms.ValidationError(
                    'We could not match that roll number and registered email. Please contact the Examination Office.'
                )
            if student.user_id and student.user.is_active:
                raise forms.ValidationError(
                    'A verified portal account already exists for this student. Please sign in instead.'
                )
            if User.objects.filter(Q(username__iexact=roll_number) & ~Q(pk=student.user_id)).exists():
                raise forms.ValidationError(
                    'This roll number is already linked to an account. Please contact the Examination Office.'
                )
            self.student_record = student
            if password1:
                candidate = User(username=student.roll_number, email=student.email)
                try:
                    password_validation.validate_password(password1, candidate)
                except ValidationError as exc:
                    self.add_error('password1', exc)
        return cleaned
