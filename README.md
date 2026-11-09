# 🎓 Examination Management System (EMS)

A comprehensive, production-grade Mini Full-Stack Web Application built with **Django, SQLite, Bootstrap 5, AJAX, and ReportLab**. 

Developed in alignment with the **Full Stack Development Lab (Course Code: 24B15CS314)** syllabus and approved project synopsis, addressing all five Course Outcomes (**CO1–CO5**).

---

## 🌟 Key Features

### 1. 🛡️ Staff & Administration Portal
- **Secure Authentication**: Protected dashboard accessible only by authorized staff and examination controllers.
- **Student Data Management**: Complete CRUD operations, multi-parameter search (Roll number, Name, Course, Semester).
- **Bulk CSV / Excel Ingestion**: Upload student rosters using `.csv`, `.xlsx`, or `.xls` with duplicate roll number validation.
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
