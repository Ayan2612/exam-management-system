"""
Views for Exam Management System
Demonstrates Django MVT - Modules 2-6, CO1-CO5
"""
import json
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from .models import Student, Room, Exam, SeatingAllocation
from .forms import (
    AdminLoginForm, StudentForm, RoomForm, ExamForm,
    CSVUploadForm, SeatingAllocationForm, StudentSearchForm, StudentRegistrationForm, StudentPortalLookupForm
)
from .utils import (
    allocate_seats, save_allocations,
    import_students_from_csv, import_students_from_excel,
    export_room_csv, export_exam_summary_csv,
    generate_admit_card_pdf, generate_room_pdf, generate_exam_summary_pdf
)


def staff_required(view_func):
    """Allow staff accounts only on administrative pages."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL + '?next=' + request.path)
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect('student_dashboard' if hasattr(request.user, 'student_profile') else 'student_login')
        return view_func(request, *args, **kwargs)
    return _wrapped


def student_required(view_func):
    """Allow only verified student accounts linked to a student record."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('student_login')
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        if not hasattr(request.user, 'student_profile'):
            logout(request)
            return redirect('student_login')
        return view_func(request, *args, **kwargs)
    return _wrapped
# ════════════════════════════════════════════════
# PUBLIC VIEWS
# ════════════════════════════════════════════════

def home(request):
    """Home / Landing page - Public"""
    stats = {
        'total_students': Student.objects.count(),
        'total_rooms': Room.objects.filter(is_active=True).count(),
        'total_exams': Exam.objects.count(),
        'total_allocations': SeatingAllocation.objects.count(),
    }
    recent_exams = Exam.objects.order_by('-exam_date')[:3]
    return render(request, 'exams/home.html', {'stats': stats, 'recent_exams': recent_exams})


@login_required(login_url='student_login')
def student_search(request):
    """Legacy seat lookup retained for signed-in staff; students use their dashboard."""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('student_dashboard')
    form = StudentSearchForm()
    return render(request, 'exams/student_search.html', {'form': form})


@login_required(login_url='student_login')
def ajax_search_seat(request):
    """
    AJAX endpoint - search seat by roll number
    Returns JSON: {found, student, room, seat_number, exam}
    CO5 - Asynchronous communication with AJAX
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        roll_number = request.GET.get('roll_number', '').strip()
        exam_id = request.GET.get('exam_id', '').strip()

        if not roll_number:
            return JsonResponse({'found': False, 'error': 'Please enter a roll number.'})
        if not (request.user.is_staff or request.user.is_superuser) and (not hasattr(request.user, 'student_profile') or request.user.student_profile.roll_number.lower() != roll_number.lower()):
            return JsonResponse({'found': False, 'error': 'You can only look up your own examination details.'}, status=403)

        try:
            student = Student.objects.get(roll_number__iexact=roll_number)
        except Student.DoesNotExist:
            return JsonResponse({'found': False, 'error': f'No student found with roll number "{roll_number}".'})

        query = SeatingAllocation.objects.filter(
            student=student
        ).select_related('exam', 'room', 'student')

        if exam_id:
            query = query.filter(exam_id=exam_id)

        allocations = query.all()

        if not allocations.exists():
            return JsonResponse({
                'found': False,
                'error': f'No seat allocation found for roll number "{roll_number}".'
            })

        data = []
        for alloc in allocations:
            data.append({
                'student_name': alloc.student.name,
                'roll_number': alloc.student.roll_number,
                'course': alloc.student.course,
                'semester': alloc.student.semester,
                'exam': alloc.exam.subject,
                'subject_code': alloc.exam.subject_code or '',
                'exam_date': alloc.exam.exam_date.strftime('%d %B %Y'),
                'exam_time': f"{alloc.exam.start_time.strftime('%I:%M %p')} - {alloc.exam.end_time.strftime('%I:%M %p')}",
                'room_number': alloc.room.room_number,
                'building': alloc.room.building,
                'seat_number': alloc.seat_number,
                'allocation_id': alloc.id,
            })

        return JsonResponse({'found': True, 'allocations': data})

    return JsonResponse({'found': False, 'error': 'Invalid request.'})


# ════════════════════════════════════════════════
# AUTHENTICATION VIEWS - Module 5, CO4
# ════════════════════════════════════════════════

def admin_login(request):
    """Admin login view"""
    if request.user.is_authenticated:
        return redirect('dashboard' if request.user.is_staff or request.user.is_superuser else 'student_dashboard')

    if request.method == 'POST':
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_staff or user.is_superuser:
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Access denied. Admin privileges required.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AdminLoginForm()

    return render(request, 'exams/login.html', {'form': form})


@staff_required
@require_POST
def admin_logout(request):
    """Admin logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


# ════════════════════════════════════════════════
# DASHBOARD - Protected
# ════════════════════════════════════════════════

@staff_required
def dashboard(request):
    """Admin dashboard with statistics"""
    stats = {
        'total_students': Student.objects.count(),
        'total_rooms': Room.objects.filter(is_active=True).count(),
        'total_exams': Exam.objects.count(),
        'total_allocations': SeatingAllocation.objects.count(),
        'scheduled_exams': Exam.objects.filter(status='scheduled').count(),
        'completed_exams': Exam.objects.filter(status='completed').count(),
        'total_capacity': sum(r.capacity for r in Room.objects.filter(is_active=True)),
    }
    recent_exams = Exam.objects.prefetch_related('seatingallocation_set').order_by('-created_at')[:5]
    recent_students = Student.objects.order_by('-created_at')[:5]
    return render(request, 'exams/dashboard.html', {
        'stats': stats,
        'recent_exams': recent_exams,
        'recent_students': recent_students,
    })


# ════════════════════════════════════════════════
# STUDENT VIEWS - Module 4, CO3
# ════════════════════════════════════════════════

@staff_required
def student_list(request):
    """List all students with search/filter"""
    q = request.GET.get('q', '').strip()
    course = request.GET.get('course', '').strip()
    semester = request.GET.get('semester', '').strip()

    students = Student.objects.all()

    if q:
        students = students.filter(
            Q(roll_number__icontains=q) |
            Q(name__icontains=q) |
            Q(email__icontains=q)
        )
    if course:
        students = students.filter(course=course)
    if semester:
        students = students.filter(semester=semester)

    paginator = Paginator(students, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    courses = Student.objects.values_list('course', flat=True).distinct()
    return render(request, 'exams/student_list.html', {
        'page_obj': page_obj,
        'q': q,
        'courses': courses,
        'selected_course': course,
        'selected_semester': semester,
        'total_count': students.count(),
    })


@staff_required
def student_create(request):
    """Create a new student"""
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            messages.success(request, f'Student {student.name} ({student.roll_number}) added successfully!')
            return redirect('student_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentForm()
    return render(request, 'exams/student_form.html', {'form': form, 'action': 'Add', 'title': 'Add New Student'})


@staff_required
def student_edit(request, pk):
    """Edit existing student"""
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f'Student {student.name} updated successfully!')
            return redirect('student_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentForm(instance=student)
    return render(request, 'exams/student_form.html', {'form': form, 'action': 'Edit', 'title': 'Edit Student', 'student': student})


@staff_required
def student_delete(request, pk):
    """Delete a student"""
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        name = student.name
        student.delete()
        messages.success(request, f'Student {name} deleted successfully.')
        return redirect('student_list')
    return render(request, 'exams/confirm_delete.html', {
        'object': student,
        'object_name': str(student),
        'cancel_url': 'student_list',
    })


@staff_required
def student_import(request):
    """Import students from CSV or Excel"""
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            filename = uploaded_file.name.lower()

            if filename.endswith('.csv'):
                success, errors = import_students_from_csv(uploaded_file)
            elif filename.endswith(('.xlsx', '.xls')):
                success, errors = import_students_from_excel(uploaded_file)
            else:
                messages.error(request, 'Only CSV or Excel files are supported.')
                return render(request, 'exams/student_import.html', {'form': form})

            if success:
                messages.success(request, f'Successfully imported/updated {success} students!')
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)
                if len(errors) > 5:
                    messages.warning(request, f'...and {len(errors) - 5} more errors.')

            return redirect('student_list')
    else:
        form = CSVUploadForm()
    return render(request, 'exams/student_import.html', {'form': form})


# ════════════════════════════════════════════════
# ROOM VIEWS - Module 4, CO3
# ════════════════════════════════════════════════

@staff_required
def room_list(request):
    """List all rooms"""
    rooms = Room.objects.annotate(
        alloc_count=Count('seatingallocation')
    ).order_by('building', 'room_number')
    return render(request, 'exams/room_list.html', {'rooms': rooms})


@staff_required
def room_create(request):
    """Create a new room"""
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            messages.success(request, f'Room {room.room_number} added successfully!')
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'exams/room_form.html', {'form': form, 'action': 'Add', 'title': 'Add New Room'})


@staff_required
def room_edit(request, pk):
    """Edit existing room"""
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, f'Room {room.room_number} updated!')
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'exams/room_form.html', {'form': form, 'action': 'Edit', 'title': 'Edit Room', 'room': room})


@staff_required
def room_delete(request, pk):
    """Delete a room"""
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        name = str(room)
        room.delete()
        messages.success(request, f'Room {name} deleted.')
        return redirect('room_list')
    return render(request, 'exams/confirm_delete.html', {
        'object': room,
        'object_name': str(room),
        'cancel_url': 'room_list',
    })


# ════════════════════════════════════════════════
# EXAM VIEWS - Core project logic
# ════════════════════════════════════════════════

@staff_required
def exam_list(request):
    """List all exams"""
    exams = Exam.objects.annotate(
        allocated_count=Count('seatingallocation')
    ).order_by('-exam_date')
    return render(request, 'exams/exam_list.html', {'exams': exams})


@staff_required
def exam_create(request):
    """Create a new exam"""
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save()
            messages.success(request, f'Exam "{exam.subject}" created successfully!')
            return redirect('exam_list')
    else:
        form = ExamForm()
    return render(request, 'exams/exam_form.html', {'form': form, 'action': 'Create', 'title': 'Create New Exam'})


@staff_required
def exam_edit(request, pk):
    """Edit existing exam"""
    exam = get_object_or_404(Exam, pk=pk)
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, f'Exam "{exam.subject}" updated!')
            return redirect('exam_list')
    else:
        form = ExamForm(instance=exam)
    return render(request, 'exams/exam_form.html', {'form': form, 'action': 'Edit', 'title': 'Edit Exam', 'exam': exam})


@staff_required
def exam_delete(request, pk):
    """Delete an exam"""
    exam = get_object_or_404(Exam, pk=pk)
    if request.method == 'POST':
        name = str(exam)
        exam.delete()
        messages.success(request, f'Exam "{name}" deleted.')
        return redirect('exam_list')
    return render(request, 'exams/confirm_delete.html', {
        'object': exam,
        'object_name': str(exam),
        'cancel_url': 'exam_list',
    })


# ════════════════════════════════════════════════
# SEATING ALLOCATION - Core Algorithm
# ════════════════════════════════════════════════

@staff_required
def seating_plan(request):
    """Create seating allocation for an exam"""
    if request.method == 'POST':
        form = SeatingAllocationForm(request.POST)
        if form.is_valid():
            exam = form.cleaned_data['exam']
            rooms = form.cleaned_data['rooms']
            students = form.cleaned_data['students']

            try:
                # Run the seating allocation algorithm
                allocations = allocate_seats(exam, rooms, students)
                created, skipped = save_allocations(allocations)

                messages.success(
                    request,
                    f'Seating plan generated! {created} seats allocated, {skipped} already existed.'
                )
                return redirect('seating_detail', exam_id=exam.id)

            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'Please correct the errors.')
    else:
        form = SeatingAllocationForm()

    # Build capacity info for real-time display
    rooms_data = [
        {'id': r.id, 'room_number': r.room_number, 'building': r.building, 'capacity': r.capacity}
        for r in Room.objects.filter(is_active=True)
    ]
    return render(request, 'exams/seating_plan.html', {
        'form': form,
        'rooms_data': json.dumps(rooms_data),
        'total_students': Student.objects.count(),
    })


@staff_required
def seating_detail(request, exam_id):
    """View complete seating allocation for an exam"""
    exam = get_object_or_404(Exam, pk=exam_id)
    allocations = SeatingAllocation.objects.filter(
        exam=exam
    ).select_related('student', 'room').order_by('room__room_number', 'seat_number')

    # Group by room
    rooms_data = {}
    for alloc in allocations:
        room_key = alloc.room.room_number
        if room_key not in rooms_data:
            rooms_data[room_key] = {
                'room': alloc.room,
                'allocations': [],
                'count': 0,
            }
        rooms_data[room_key]['allocations'].append(alloc)
        rooms_data[room_key]['count'] += 1

    return render(request, 'exams/seating_detail.html', {
        'exam': exam,
        'rooms_data': rooms_data,
        'total_allocated': allocations.count(),
    })


@staff_required
def clear_seating(request, exam_id):
    """Clear all seating allocations for an exam"""
    exam = get_object_or_404(Exam, pk=exam_id)
    if request.method == 'POST':
        count, _ = SeatingAllocation.objects.filter(exam=exam).delete()
        messages.success(request, f'Cleared {count} seat allocations for "{exam.subject}".')
        return redirect('seating_detail', exam_id=exam.id)
    return render(request, 'exams/confirm_delete.html', {
        'object': exam,
        'object_name': f'All seating allocations for: {exam.subject}',
        'cancel_url': 'exam_list',
        'custom_cancel': f'/seating/{exam.id}/',
    })


# ════════════════════════════════════════════════
# ADMIT CARD & REPORTS - Module 6, CO5
# ════════════════════════════════════════════════

def _admit_card_allocation(request, allocation_id):
    """Resolve a staff request or a short-lived signed student roll-lookup token."""
    allocation = get_object_or_404(SeatingAllocation, pk=allocation_id)
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return allocation
    token = request.GET.get('token', '')
    try:
        payload = signing.loads(token, salt='exams.student.admit-card', max_age=15 * 60)
    except (signing.BadSignature, signing.SignatureExpired):
        raise PermissionDenied('Please look up your roll number again to access this admit card.')
    if payload.get('allocation_id') != allocation.pk or payload.get('student_id') != allocation.student_id:
        raise PermissionDenied('This admit-card link is not valid for this student.')
    return allocation


def view_admit_card(request, allocation_id):
    """Render the admit card using a short-lived signed lookup token."""
    allocation = _admit_card_allocation(request, allocation_id)
    return render(request, 'exams/admit_card.html', {'allocation': allocation})


def download_admit_card(request, allocation_id):
    """Download the admit card using a short-lived signed lookup token."""
    allocation = _admit_card_allocation(request, allocation_id)

    buffer = generate_admit_card_pdf(allocation)

    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"admit_card_{allocation.student.roll_number}_{allocation.exam.subject.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_required
def download_room_pdf(request, exam_id, room_id):
    """Download room-wise seating PDF"""
    exam = get_object_or_404(Exam, pk=exam_id)
    room = get_object_or_404(Room, pk=room_id)

    buffer = generate_room_pdf(exam, room)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"seating_{exam.subject.replace(' ', '_')}_{room.room_number}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_required
def download_room_csv_view(request, exam_id, room_id):
    """Download room-wise seating CSV"""
    exam = get_object_or_404(Exam, pk=exam_id)
    room = get_object_or_404(Room, pk=room_id)
    return export_room_csv(exam, room)


@staff_required
def download_exam_pdf(request, exam_id):
    """Download full exam summary PDF"""
    exam = get_object_or_404(Exam, pk=exam_id)
    buffer = generate_exam_summary_pdf(exam)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"exam_summary_{exam.subject.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_required
def download_exam_csv(request, exam_id):
    """Download full exam summary CSV"""
    exam = get_object_or_404(Exam, pk=exam_id)
    return export_exam_summary_csv(exam)


# ════════════════════════════════════════════════
# SAMPLE CSV TEMPLATE DOWNLOAD
# ════════════════════════════════════════════════

def download_csv_template(request):
    """Download sample CSV template for student import"""
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['roll_number', 'name', 'email', 'course', 'semester', 'phone'])
    writer.writerow(['21B15CS001', 'Rahul Sharma', 'rahul@college.edu', 'B.Tech CSE', '5', '9876543210'])
    writer.writerow(['21B15CS002', 'Priya Singh', 'priya@college.edu', 'B.Tech CSE', '5', '9876543211'])
    writer.writerow(['21B15ECE001', 'Amit Kumar', 'amit@college.edu', 'B.Tech ECE', '3', '9876543212'])
    return response

# ════════════════════════════════════════════════
# STUDENT PORTAL - Self-service and verified accounts
# ════════════════════════════════════════════════

def student_register(request):
    """Legacy registration route now opens the roll-number-only portal."""
    return redirect('student_portal')


def student_verify_email(request, token):
    """Verify a time-limited signed email token and activate the account."""
    try:
        payload = signing.loads(token, salt='exams.student.email-verification', max_age=60 * 60 * 24)
        student = Student.objects.select_related('user').get(pk=payload['student_id'], user_id=payload['user_id'])
    except (signing.BadSignature, signing.SignatureExpired, Student.DoesNotExist, KeyError, TypeError):
        return render(request, 'exams/student_verification_result.html', {'verified': False, 'message': 'This verification link is invalid or has expired. Please register again to request a fresh link.'})
    user = student.user
    if user.is_active:
        return render(request, 'exams/student_verification_result.html', {'verified': True, 'message': 'Your email address is already verified. You can sign in to your student portal.'})
    user.is_active = True
    user.save(update_fields=['is_active'])
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return render(request, 'exams/student_verification_result.html', {'verified': True, 'message': 'Your email has been verified. Your Student Examination Portal is ready.', 'continue_to_portal': True})


def student_login(request):
    """Legacy login URL now opens the roll-number-only student portal."""
    return redirect('student_portal')


def student_dashboard(request):
    """Compatibility route for old links; open the roll-number portal."""
    return redirect('student_portal')


def student_portal(request):
    """Look up a student's examination details using their university roll number."""
    form = StudentPortalLookupForm(request.POST or None)
    context = {'form': form, 'student': None, 'upcoming_rows': [], 'history_rows': []}
    if request.method == 'POST' and form.is_valid():
        roll_number = form.cleaned_data['roll_number'].strip()
        student = Student.objects.filter(roll_number__iexact=roll_number).first()
        if not student:
            form.add_error('roll_number', 'No student record found. Please check your roll number.')
        else:
            today = timezone.localdate()
            allocations = SeatingAllocation.objects.filter(student=student).select_related('exam', 'room').order_by('exam__exam_date', 'exam__start_time')
            allocation_by_exam = {item.exam_id: item for item in allocations}
            upcoming = Exam.objects.filter(exam_date__gte=today, status__in=['scheduled', 'ongoing']).filter(Q(target_course='') | Q(target_course=student.course)).filter(Q(target_semester__isnull=True) | Q(target_semester=student.semester)).order_by('exam_date', 'start_time')
            history = Exam.objects.filter(Q(exam_date__lt=today) | Q(status='completed')).filter(Q(target_course='') | Q(target_course=student.course)).filter(Q(target_semester__isnull=True) | Q(target_semester=student.semester)).order_by('-exam_date', '-start_time')[:10]
            upcoming_rows = [{'exam': exam, 'allocation': allocation_by_exam.get(exam.pk), 'admit_token': signing.dumps({'allocation_id': allocation_by_exam[exam.pk].pk, 'student_id': student.pk}, salt='exams.student.admit-card') if allocation_by_exam.get(exam.pk) else ''} for exam in upcoming]
            history_rows = [{'exam': exam, 'allocation': allocation_by_exam.get(exam.pk)} for exam in history]
            context.update({
                'student': student, 'upcoming_rows': upcoming_rows, 'history_rows': history_rows,
                'upcoming_count': len(upcoming_rows), 'allocated_count': allocations.count(),
                'admit_card_count': allocations.count(),
            })
    return render(request, 'exams/student_dashboard.html', context)


@student_required
@require_POST
def student_logout(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('student_login')
