# 🎓 Examination Management System (EMS)

A comprehensive, production-grade Mini Full-Stack Web Application built with **Django, SQLite, Bootstrap 5, AJAX, and ReportLab**. 

Developed in alignment with the **Full Stack Development Lab (Course Code: 24B15CS314)** syllabus and approved project synopsis, addressing all five Course Outcomes (**CO1–CO5**).

---

## 🌟 Key Features

### 1. 🛡️ Staff & Administration Portal
- **Secure Authentication**: Protected dashboard accessible only by authorized staff and examination controllers.
- **Student Data Management**: Complete CRUD operations, multi-parameter search (Roll number, Name, Course, Semester).
- **Bulk CSV / Excel Ingestion**: Upload student rosters using `.csv`, `.xlsx`, or `.xls`; use 12-digit JIIT-style roll numbers (9923/9924/9925/9926 for 2023/2024/2025/2026 batches).
- **Room & Capacity Management**: Add and configure exam rooms, building blocks, floors, and strict capacity limits.
- **Exam Scheduling**: Create and schedule examinations with subject codes, dates, and session timings.

### 2. ⚡ Automated Seating Allocation Engine
- **Deterministic Sequential Allocation**: Distributes eligible students across selected rooms according to capacities.
- **Capacity Overflow Safeguard**: Real-time validation preventing room overbooking or duplicate seat allocations.
- **Room-wise Breakdown**: Visualizes seat plans per room with occupancy percentages.

### 3. 🔍 Candidate Portal & Live AJAX Seat Search
- **Asynchronous Lookup**: Students enter their roll number to verify their assigned exam hall and seat number in real-time with zero page reloads.
- **Official Hall Ticket / Admit Card**:
  - **Interactive Web Preview**: Clean university printable template with candidate photo box, rules, and signatures.
  - **Dynamic ReportLab PDF**: Official downloadable binary PDF with scannable Code39 barcode and verification seals.

### 4. 📊 Downloadable Reports & Data Export
- **Room-wise Attendance Sheets**: PDF and CSV formats for room invigilators.
- **Complete Exam Summary**: Exportable full seating manifests.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| **Backend Framework** | Python 3 · Django 6 |
| **Database & ORM** | SQLite3 · Django ORM |
| **Frontend Presentation** | HTML5 · CSS3 · Bootstrap 5 · JavaScript |
| **Asynchronous Requests** | AJAX (Vanilla JS Fetch API) |
| **PDF Generation** | ReportLab (A4 Canvas & Flowables) |
| **Data Ingestion/Export** | OpenPyXL (Excel) · Python CSV Library |

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/Ayan2612/exam-management-system.git
cd exam-management-system
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations & Start Server
```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

---

## 🔐 Create an Administrator Account

Create your own administrator account locally after running migrations:

```bash
python manage.py createsuperuser
```

- **Admin Portal**: `http://127.0.0.1:8000/admin-login/`
- **Student Search**: `http://127.0.0.1:8000/search/`

Do not commit real credentials or secret keys to the repository.

---

## 📁 Project Architecture

```
exam_management/
│
├── manage.py
├── requirements.txt
├── README.md
├── sample_students.csv
├── sample_students.xlsx
│
├── exam_management/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── exams/
│   ├── models.py          # Student, Room, Exam, SeatingAllocation
│   ├── views.py           # Business Logic, MVT Views, Reports
│   ├── urls.py            # URL Routing
│   ├── forms.py           # ModelForms, StyledFormMixin
│   ├── utils.py           # Seating Algorithm, ReportLab PDF, CSV Ingest
│   └── admin.py           # Django Admin Customization
│
├── static/
│   ├── css/main.css       # University Academic Theme Stylesheet
│   └── js/main.js         # AJAX Search, Toast, Capacity Logic
│
└── templates/exams/
    ├── base.html
    ├── admin_base.html
    ├── home.html
    ├── login.html
    ├── dashboard.html
    ├── student_search.html
    ├── admit_card.html     # Official Printable Hall Ticket
    ├── student_list.html
    ├── student_form.html
    ├── student_import.html
    ├── room_list.html
    ├── room_form.html
    ├── exam_list.html
    ├── exam_form.html
    ├── seating_plan.html
    ├── seating_detail.html
    └── confirm_delete.html
```

---

## 🎓 Course Outcomes (CO) Mapping

- **CO1 (Module 1)**: Python & Django fundamentals, virtual environment, and MVT pattern.
- **CO2 (Modules 2 & 3)**: URL routing, view dispatching, template inheritance, and responsive UI design.
- **CO3 (Module 4)**: Django ORM relationships (1-to-many, many-to-many through model), ModelForms, and CRUD.
- **CO4 (Module 5)**: Authentication, authorization, access restrictions, and form validation.
- **CO5 (Module 6)**: Asynchronous AJAX communication, dynamic PDF generation with ReportLab, and CSV export.


## Student Portal (Roll Number Lookup)

Open `/student/portal/` from the home page and enter the student's university roll number. The portal displays the matching student's profile basics, course/semester-specific upcoming examination schedule, seating allocation, admit-card links and examination history.

No student registration, password or email verification is required. Administrators must first add/import the student's record and keep their roll number accurate. Use the 12-digit JIIT-style format: `9923…` (2023), `9924…` (2024), `9925…` (2025), or `9926…` (2026). During CSV/Excel import, an existing student is matched by exact roll number first and registered email second; this lets an updated roll number replace the old one while preserving the same student record and its seating allocations. The current semester is inferred from the admission year for these roll numbers (B.Tech up to semester 8; BCA up to semester 6).

Admit-card links are signed and expire after 15 minutes. The roll-number-only lookup is intended for a classroom/demo project: a roll number is an identifier, not a secret, so anyone who knows a student's roll number may be able to view the portal details. Do not expose sensitive personal information or use this approach for confidential student records in a real deployment.

Administrators can optionally target an exam to a course and semester. Leave either audience field blank to make that dimension open to all students. Seating allocation validates selected students against the configured audience.

### Django security settings

Set `DJANGO_SECRET_KEY` to a long random secret and set `DJANGO_DEBUG=False` plus `DJANGO_ALLOWED_HOSTS` to your real hostnames before any public deployment. The fallback key in settings is for local development only. Do not commit `.env` or real credentials.

## Simple roll-number Student Portal

Open `/student/portal/` (or use the Student Portal link on the home page), enter the university roll number and view that student's course/semester-specific exam schedule, seating allocation, admit-card links and examination history. No student registration, password or email verification is required.

**Demo limitation:** a roll number is an identifier, not a secret. Anyone who knows a student's roll number may be able to look up the public portal details. Do not expose sensitive personal data on this page or use roll-number-only access for confidential records in a real deployment. Admit-card links are signed and expire after 15 minutes.

### Standardize existing legacy student roll numbers

Back up your local database before applying this operation. The command maps the existing semester to a batch (Sem 7/8 → 2023, Sem 5/6 → 2024, Sem 3/4 → 2025, Sem 1/2 → 2026) and updates each existing Student row in place, preserving its primary key and related seating allocations.

Preview the exact changes first (no database writes):

```bash
python manage.py standardize_student_roll_numbers
```

After reviewing the proposed roll-number mapping, apply it:

```bash
python manage.py standardize_student_roll_numbers --apply
```

The generated demo format is `99YY0103NNNN` (for example, `992401030018` for 2024 and `992501030018` for 2025); the final four digits are based on the old roll number's numeric suffix where possible. This is a project demo convention, not a claim that the programme segment is an official institute-issued code. The command refuses to proceed if it encounters unsupported semesters or a target-roll collision.
