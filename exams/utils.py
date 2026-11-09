"""
Utility functions for Exam Management System
- Seating allocation algorithm
- CSV/Excel import
- PDF generation
- CSV export
"""
import csv
import io
from django.http import HttpResponse
from django.db.models import Q
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor


# ─────────────────────────────────────────────
# SEATING ALLOCATION ALGORITHM (Core Logic)
# ─────────────────────────────────────────────

def room_capacity_available(exam, rooms):
    """Count free physical seats after all overlapping exams in the same rooms."""
    from .models import Exam, SeatingAllocation

    active_rooms = [room for room in rooms if room.is_active]
    room_ids = [room.pk for room in active_rooms]
    if not room_ids:
        return 0
    overlapping_ids = Exam.objects.filter(
        exam_date=exam.exam_date,
        start_time__lt=exam.end_time,
        end_time__gt=exam.start_time,
    ).values_list('pk', flat=True)
    occupied = {}
    allocations = SeatingAllocation.objects.filter(
        room_id__in=room_ids, exam_id__in=overlapping_ids
    ).values_list('room_id', 'seat_number')
    for room_id, seat_number in allocations:
        occupied.setdefault(room_id, set()).add(seat_number)
    return sum(max(room.capacity - len(occupied.get(room.pk, set())), 0) for room in active_rooms)



def allocate_seats(exam, rooms, students):
    """
    Build a seating plan using only unoccupied seats.

    Existing allocations for this exam are preserved. Students already
    allocated are skipped, and occupied seat numbers are never reused.
    """
    from .models import SeatingAllocation

    sorted_rooms = sorted(
        [room for room in rooms if room.is_active],
        key=lambda room: (room.building, room.room_number)
    )
    student_list = sorted(list(students), key=lambda student: student.roll_number)

    already_allocated_ids = set(
        SeatingAllocation.objects.filter(exam=exam)
        .values_list('student_id', flat=True)
    )
    pending_students = [
        student for student in student_list
        if student.pk not in already_allocated_ids
    ]

    from .models import Exam
    overlapping_exam_ids = Exam.objects.filter(
        exam_date=exam.exam_date,
        start_time__lt=exam.end_time,
        end_time__gt=exam.start_time,
    ).values_list('pk', flat=True)

    occupied_by_room = {}
    for room_id, seat_number in SeatingAllocation.objects.filter(
        exam_id__in=overlapping_exam_ids, room__in=sorted_rooms
    ).values_list('room_id', 'seat_number'):
        occupied_by_room.setdefault(room_id, set()).add(seat_number)

    available_capacity = sum(
        max(room.capacity - len(occupied_by_room.get(room.pk, set())), 0)
        for room in sorted_rooms
    )
    if len(pending_students) > available_capacity:
        raise ValueError(
            f"Insufficient free capacity: {len(pending_students)} students "
            f"need seats, but only {available_capacity} unoccupied seats are available."
        )

    allocations = []
    student_index = 0
    for room in sorted_rooms:
        occupied = occupied_by_room.get(room.pk, set())
        for seat_number in range(1, room.capacity + 1):
            if student_index >= len(pending_students):
                break
            if seat_number in occupied:
                continue
            allocations.append({
                'student': pending_students[student_index],
                'exam': exam,
                'room': room,
                'seat_number': seat_number,
            })
            student_index += 1
        if student_index >= len(pending_students):
            break

    return allocations


def save_allocations(allocations):
    """Persist a complete plan atomically; never leave a partial seating plan."""
    from django.db import transaction
    from .models import SeatingAllocation

    created_count = 0
    skipped_count = 0

    with transaction.atomic():
        for alloc in allocations:
            _, created = SeatingAllocation.objects.get_or_create(
                student=alloc['student'],
                exam=alloc['exam'],
                defaults={
                    'room': alloc['room'],
                    'seat_number': alloc['seat_number'],
                }
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

    return created_count, skipped_count


# ─────────────────────────────────────────────
# CSV / EXCEL IMPORT
# ─────────────────────────────────────────────

def _upsert_imported_student(roll, name, email, course, semester, phone):
    """Update an existing student by roll number or email, preserving related records."""
    from .models import Student
    from django.utils import timezone

    # Derive the current semester from the JIIT-style admission-year prefix.
    if roll.startswith('992') and len(roll) >= 5 and roll[3:5].isdigit():
        admission_year = 2000 + int(roll[3:5])
        today = timezone.localdate()
        semester = 2 * (today.year - admission_year) + (
            1 if today.month >= 8 or today.month <= 2 else 2
        )
        semester = min(max(semester, 1), 6 if course == 'BCA' else 8)

    defaults = {
        'roll_number': roll,
        'name': name,
        'email': email,
        'course': course,
        'semester': semester,
        'phone': phone or None,
    }
    student = Student.objects.filter(roll_number__iexact=roll).first()
    if student is None:
        # Email is the stable matching key when an existing student's roll number changes.
        student = Student.objects.filter(email__iexact=email).first()
    if student is not None:
        for field, value in defaults.items():
            setattr(student, field, value)
        student.save()
        return student, False
    return Student.objects.create(**defaults), True


def _validate_import_row(roll, name, email, course, semester, phone):
    """Validate the six mandatory student import fields before writing anything."""
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    from .models import Student

    if not all(str(value).strip() for value in (roll, name, email, course, semester, phone)):
        raise ValueError("all six fields are mandatory")
    if not (len(roll) == 12 and roll.isdigit() and roll.startswith('992')):
        raise ValueError("roll_number must be a 12-digit JIIT-style number beginning with 992")
    try:
        validate_email(email)
    except ValidationError:
        raise ValueError("email is not a valid email address")
    valid_courses = {value for value, _ in Student.COURSE_CHOICES}
    if course not in valid_courses:
        raise ValueError(f"course must be one of: {', '.join(sorted(valid_courses))}")
    try:
        semester_number = int(semester)
    except (TypeError, ValueError):
        raise ValueError("semester must be a whole number from 1 to 8")
    max_semester = 6 if course == 'BCA' else 8
    if not 1 <= semester_number <= max_semester:
        raise ValueError(f"semester for {course} must be between 1 and {max_semester}")
    if not (phone.isdigit() and len(phone) == 10):
        raise ValueError("phone must contain exactly 10 digits")
    return semester_number


def import_students_from_csv(file):
    """Import validated CSV rows; return (success_count, errors_list)."""
    success_count = 0
    errors = []
    try:
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        required_cols = ['roll_number', 'name', 'email', 'course', 'semester', 'phone']
        headers = [header.strip() for header in (reader.fieldnames or [])]
        if not set(required_cols).issubset(set(headers)):
            missing = [column for column in required_cols if column not in headers]
            return 0, [f"Missing required columns: {', '.join(missing)}"]
        reader.fieldnames = headers
        for row_num, row in enumerate(reader, start=2):
            try:
                roll = (row.get('roll_number') or '').strip()
                name = (row.get('name') or '').strip()
                email = (row.get('email') or '').strip()
                course = (row.get('course') or '').strip()
                semester_raw = (row.get('semester') or '').strip()
                phone = (row.get('phone') or '').strip()
                semester = _validate_import_row(roll, name, email, course, semester_raw, phone)
                _upsert_imported_student(roll, name, email, course, semester, phone)
                success_count += 1
            except Exception as exc:
                errors.append(f"Row {row_num}: {exc}")
    except Exception as exc:
        errors.append(f"File read error: {exc}")
    return success_count, errors


def import_students_from_excel(file):
    """Import validated .xlsx rows; return (success_count, errors_list)."""
    import openpyxl
    success_count = 0
    errors = []
    try:
        workbook = openpyxl.load_workbook(file, read_only=True, data_only=True)
        sheet = workbook.active
        headers = [str(cell.value).strip().lower() if cell.value is not None else '' for cell in sheet[1]]
        required = ['roll_number', 'name', 'email', 'course', 'semester', 'phone']
        missing = [column for column in required if column not in headers]
        if missing:
            return 0, [f"Missing required columns: {', '.join(missing)}"]
        indexes = {header: headers.index(header) for header in required}
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            try:
                values = [row[indexes[column]] if indexes[column] < len(row) else None for column in required]
                roll, name, email, course, semester_raw, phone = [
                    str(value).strip() if value is not None else '' for value in values
                ]
                semester = _validate_import_row(roll, name, email, course, semester_raw, phone)
                _upsert_imported_student(roll, name, email, course, semester, phone)
                success_count += 1
            except Exception as exc:
                errors.append(f"Row {row_num}: {exc}")
        workbook.close()
    except Exception as exc:
        errors.append(f"Excel file error: {exc}")
    return success_count, errors


# ─────────────────────────────────────────────
# CSV EXPORT
# ─────────────────────────────────────────────

def export_room_csv(exam, room):
    """Generate CSV report for a room's seating plan."""
    from .models import SeatingAllocation

    response = HttpResponse(content_type='text/csv')
    filename = f"seating_{exam.subject.replace(' ', '_')}_{room.room_number}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Seat No.', 'Roll Number', 'Student Name', 'Course', 'Semester', 'Room', 'Exam', 'Date'])

    allocations = SeatingAllocation.objects.filter(
        exam=exam, room=room
    ).select_related('student').order_by('seat_number')

    for alloc in allocations:
        writer.writerow([
            alloc.seat_number,
            alloc.student.roll_number,
            alloc.student.name,
            alloc.student.course,
            alloc.student.semester,
            room.room_number,
            exam.subject,
            exam.exam_date,
        ])

    return response


def export_exam_summary_csv(exam):
    """Generate full exam summary CSV."""
    from .models import SeatingAllocation

    response = HttpResponse(content_type='text/csv')
    filename = f"exam_summary_{exam.subject.replace(' ', '_')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['#', 'Roll Number', 'Student Name', 'Course', 'Semester', 'Room', 'Seat No.', 'Exam', 'Date'])

    allocations = SeatingAllocation.objects.filter(
        exam=exam
    ).select_related('student', 'room').order_by('room__room_number', 'seat_number')

    for idx, alloc in enumerate(allocations, start=1):
        writer.writerow([
            idx,
            alloc.student.roll_number,
            alloc.student.name,
            alloc.student.course,
            alloc.student.semester,
            alloc.room.room_number,
            alloc.seat_number,
            exam.subject,
            exam.exam_date,
        ])

    return response


# ─────────────────────────────────────────────
# PDF GENERATION (ReportLab)
# ─────────────────────────────────────────────

from reportlab.graphics.barcode import createBarcodeDrawing

BRAND_PURPLE = HexColor('#4338ca')
BRAND_DARK = HexColor('#0f172a')
BRAND_LIGHT = HexColor('#f8fafc')
BRAND_BORDER = HexColor('#cbd5e1')
BRAND_SEAT_BG = HexColor('#eef2ff')
BRAND_SEAT_BORDER = HexColor('#6366f1')


def generate_admit_card_pdf(allocation):
    """
    Generate professional, official admit card PDF matching the web template.
    Includes:
    - University Header & Document Title Badge
    - Scannable Code39 Barcode Drawing
    - Candidate Passport Photograph Box
    - Structured Student & Candidate Details Table
    - Examination Schedule & Venue Details Table
    - Highlighted Confirmed Seat Allocation Box (Room, Seat #, Status)
    - Important Examination Instructions
    - Candidate, Invigilator, and Controller Signature lines with Official Seal
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm
    )
    styles = getSampleStyleSheet()
    story = []

    # 1. Header
    title_style = ParagraphStyle(
        'DocTitle', fontName='Helvetica-Bold', fontSize=15,
        leading=18, alignment=TA_CENTER, textColor=BRAND_DARK
    )
    sub_style = ParagraphStyle(
        'DocSub', fontName='Helvetica', fontSize=8,
        leading=11, alignment=TA_CENTER, textColor=HexColor('#64748b')
    )
    badge_style = ParagraphStyle(
        'DocBadge', fontName='Helvetica-Bold', fontSize=8.5,
        leading=11, alignment=TA_CENTER, textColor=colors.white
    )

    story.append(Paragraph("EXAMINATION MANAGEMENT SYSTEM", title_style))
    story.append(Paragraph("Office of the Controller of Examinations · Academic Session 2026", sub_style))
    story.append(Spacer(1, 4))

    badge_table = Table([[Paragraph("OFFICIAL HALL TICKET / ADMIT CARD", badge_style)]], colWidths=[8.5*cm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_DARK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 8))

    # 2. Barcode + Passport Photo Box Row
    barcode_drawing = createBarcodeDrawing(
        'Standard39', value=allocation.student.roll_number,
        width=160, height=32, humanReadable=True
    )

    photo_para = Paragraph(
        "Affix Passport<br/>Photograph<br/>Here",
        ParagraphStyle('PBox', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER, textColor=HexColor('#94a3b8'))
    )
    photo_cell = Table([[photo_para]], colWidths=[2.6*cm], rowHeights=[3.1*cm])
    photo_cell.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafc')),
    ]))

    top_row = Table([[barcode_drawing, photo_cell]], colWidths=[14.4*cm, 3.6*cm])
    top_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 6))

    # 3. Student Details Table
    lbl_style = ParagraphStyle('Lbl', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=HexColor('#475569'))
    val_style = ParagraphStyle('Val', fontName='Helvetica', fontSize=8, leading=10, textColor=BRAND_DARK)
    val_bold = ParagraphStyle('ValB', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=BRAND_DARK)

    student_data = [
        [Paragraph("Candidate Name:", lbl_style), Paragraph(allocation.student.name, val_bold),
         Paragraph("Roll Number:", lbl_style), Paragraph(allocation.student.roll_number, ParagraphStyle('RN', fontName='Helvetica-Bold', fontSize=8.5, textColor=BRAND_PURPLE))],
        [Paragraph("Course / Programme:", lbl_style), Paragraph(allocation.student.course, val_style),
         Paragraph("Semester:", lbl_style), Paragraph(f"Semester {allocation.student.semester}", val_style)],
        [Paragraph("Email Address:", lbl_style), Paragraph(allocation.student.email, val_style),
         Paragraph("Mobile / Phone:", lbl_style), Paragraph(allocation.student.phone or 'N/A', val_style)],
    ]
    t_student = Table(student_data, colWidths=[3.8*cm, 5.2*cm, 3.8*cm, 5.2*cm])
    t_student.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), BRAND_LIGHT),
        ('BACKGROUND', (2, 0), (2, -1), BRAND_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_student)
    story.append(Spacer(1, 6))

    # 4. Exam Schedule & Venue Table
    exam_data = [
        [Paragraph("EXAMINATION SCHEDULE & VENUE DETAILS", ParagraphStyle('ESection', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=BRAND_DARK)), '', '', ''],
        [Paragraph("Exam Subject:", lbl_style), Paragraph(allocation.exam.subject, val_bold),
         Paragraph("Subject Code:", lbl_style), Paragraph(allocation.exam.subject_code or 'N/A', val_style)],
        [Paragraph("Exam Date:", lbl_style), Paragraph(allocation.exam.exam_date.strftime('%A, %d %B %Y'), val_bold),
         Paragraph("Reporting Time:", lbl_style), Paragraph("30 mins before start", ParagraphStyle('RT', fontName='Helvetica-Bold', fontSize=8, textColor=HexColor('#b45309')))],
        [Paragraph("Exam Timings:", lbl_style), Paragraph(f"{allocation.exam.start_time.strftime('%I:%M %p')} – {allocation.exam.end_time.strftime('%I:%M %p')}", val_bold),
         Paragraph("Building / Block:", lbl_style), Paragraph(f"{allocation.room.building} (Floor {allocation.room.floor})", val_style)],
    ]
    t_exam = Table(exam_data, colWidths=[3.8*cm, 5.2*cm, 3.8*cm, 5.2*cm])
    t_exam.setStyle(TableStyle([
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 1), (0, -1), BRAND_LIGHT),
        ('BACKGROUND', (2, 1), (2, -1), BRAND_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_exam)
    story.append(Spacer(1, 6))

    # 5. Highlighted Seat Box
    seat_box_data = [
        [
            Paragraph(f'ALLOCATED ROOM<br/><font size="12" color="#4338ca"><b>Room {allocation.room.room_number}</b></font><br/><font size="7" color="#64748b">{allocation.room.building}</font>', ParagraphStyle('S1', fontName='Helvetica', fontSize=7.5, alignment=TA_CENTER)),
            Paragraph(f'ASSIGNED SEAT NUMBER<br/><font size="14" color="#059669"><b>SEAT #{allocation.seat_number}</b></font><br/><font size="7" color="#059669">✓ Confirmed Allocation</font>', ParagraphStyle('S2', fontName='Helvetica', fontSize=7.5, alignment=TA_CENTER)),
            Paragraph('VERIFICATION STATUS<br/><font size="11" color="#0f172a"><b>ELIGIBLE</b></font><br/><font size="7" color="#64748b">Admit Card Validated</font>', ParagraphStyle('S3', fontName='Helvetica', fontSize=7.5, alignment=TA_CENTER)),
        ]
    ]
    t_seat = Table(seat_box_data, colWidths=[6*cm, 6*cm, 6*cm])
    t_seat.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SEAT_BG),
        ('BOX', (0, 0), (-1, -1), 1.5, BRAND_SEAT_BORDER),
        ('LINEBEFORE', (1, 0), (1, -1), 1, HexColor('#c7d2fe')),
        ('LINEBEFORE', (2, 0), (2, -1), 1, HexColor('#c7d2fe')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_seat)
    story.append(Spacer(1, 6))

    # 6. Candidate Instructions
    inst_header = Paragraph("<b>IMPORTANT INSTRUCTIONS FOR CANDIDATES:</b>", ParagraphStyle('IH', fontName='Helvetica', fontSize=7.5, leading=9, textColor=BRAND_DARK))
    inst_text = (
        "1. Candidates must carry this printed Admit Card along with their valid College Photo ID to the exam hall.<br/>"
        "2. Reach the examination venue at least 30 minutes prior to the scheduled start time.<br/>"
        "3. Mobile phones, smartwatches, programmable calculators, or any electronic items are strictly prohibited.<br/>"
        "4. Candidates must sit strictly at their assigned Room and Seat Number shown above.<br/>"
        "5. This hall ticket is system-generated and valid solely for the mentioned exam."
    )
    inst_p = Paragraph(inst_text, ParagraphStyle('IT', fontName='Helvetica', fontSize=6.5, leading=9, textColor=HexColor('#475569')))
    inst_table = Table([[inst_header], [inst_p]], colWidths=[18*cm])
    inst_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, BRAND_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(inst_table)
    story.append(Spacer(1, 12))

    # 7. Signatures Row
    sign_data = [
        [
            Paragraph("<br/><br/>____________________________<br/><b>Candidate's Signature</b>", ParagraphStyle('SG1', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER)),
            Paragraph("<br/><br/>____________________________<br/><b>Invigilator's Signature</b>", ParagraphStyle('SG2', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER)),
            Paragraph("<font color=\"#4338ca\"><b>[OFFICIAL SEAL]</b></font><br/>____________________________<br/><b>Controller of Examinations</b>", ParagraphStyle('SG3', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER)),
        ]
    ]
    t_sign = Table(sign_data, colWidths=[6*cm, 6*cm, 6*cm])
    t_sign.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_sign)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_room_pdf(exam, room):
    """Generate room-wise seating plan PDF."""
    from .models import SeatingAllocation

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Title'],
        fontSize=18, textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=4)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
        fontSize=11, textColor=BRAND_PURPLE, alignment=TA_CENTER, spaceAfter=20)

    story.append(Paragraph("EXAM MANAGEMENT SYSTEM", title_style))
    story.append(Paragraph(
        f"Room: {room.room_number} ({room.building}) | "
        f"Exam: {exam.subject} | Date: {exam.exam_date.strftime('%d %B %Y')} | "
        f"Time: {exam.start_time.strftime('%I:%M %p')} - {exam.end_time.strftime('%I:%M %p')}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_PURPLE, spaceAfter=15))

    allocations = SeatingAllocation.objects.filter(
        exam=exam, room=room
    ).select_related('student').order_by('seat_number')

    headers = ['Seat No.', 'Roll Number', 'Student Name', 'Course', 'Semester', 'Signature']
    table_data = [headers]
    for alloc in allocations:
        table_data.append([
            str(alloc.seat_number),
            alloc.student.roll_number,
            alloc.student.name,
            alloc.student.course,
            f"Sem {alloc.student.semester}",
            '',
        ])

    t = Table(table_data, colWidths=[2*cm, 4*cm, 7*cm, 5*cm, 2.5*cm, 5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#c7d2fe')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_exam_summary_pdf(exam):
    """Generate full exam summary PDF."""
    from .models import SeatingAllocation

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Title'],
        fontSize=20, textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=4)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
        fontSize=11, textColor=BRAND_PURPLE, alignment=TA_CENTER, spaceAfter=20)

    story.append(Paragraph("EXAM MANAGEMENT SYSTEM", title_style))
    story.append(Paragraph(
        f"Complete Seating Plan | {exam.subject} | {exam.exam_date.strftime('%d %B %Y')}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_PURPLE, spaceAfter=15))

    allocations = SeatingAllocation.objects.filter(
        exam=exam
    ).select_related('student', 'room').order_by('room__room_number', 'seat_number')

    headers = ['#', 'Roll Number', 'Student Name', 'Course', 'Sem', 'Room', 'Seat No.']
    table_data = [headers]
    for idx, alloc in enumerate(allocations, start=1):
        table_data.append([
            str(idx),
            alloc.student.roll_number,
            alloc.student.name,
            alloc.student.course,
            str(alloc.student.semester),
            alloc.room.room_number,
            str(alloc.seat_number),
        ])

    t = Table(table_data, colWidths=[1.5*cm, 4*cm, 8*cm, 5*cm, 1.8*cm, 3*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#c7d2fe')),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer
