"""
Convert legacy student roll numbers to the 12-digit JIIT-style format.

Run a dry-run first:
    python manage.py standardize_student_roll_numbers

Apply only after reviewing the preview:
    python manage.py standardize_student_roll_numbers --apply
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exams.models import Student


def batch_for_semester(semester):
    """Map current odd/even semester pairs to their expected admission batch."""
    if semester in (1, 2):
        return 2026
    if semester in (3, 4):
        return 2025
    if semester in (5, 6):
        return 2024
    if semester in (7, 8):
        return 2023
    raise ValueError(f"Unsupported semester: {semester}")


def make_roll_number(student, sequence):
    batch = batch_for_semester(student.semester)
    # The sample JIIT-style pattern supplied for this project uses 0103
    # as the programme segment. Keep the generated structure consistent.
    return f"992{str(batch)[-2:]}0103{sequence:04d}"


class Command(BaseCommand):
    help = "Preview or apply legacy student roll-number standardization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist the changes. Without this flag, only preview them.",
        )

    def handle(self, *args, **options):
        students = list(Student.objects.exclude(roll_number__regex=r"^992[0-9]{8}$").order_by("pk"))
        if not students:
            self.stdout.write(self.style.SUCCESS("No legacy roll numbers found. Nothing to do."))
            return

        existing = set(
            Student.objects.exclude(pk__in=[s.pk for s in students])
            .values_list("roll_number", flat=True)
        )
        planned = []
        counters = {}
        errors = []

        for student in students:
            try:
                batch = batch_for_semester(student.semester)
            except ValueError as exc:
                errors.append(f"{student.roll_number}: {exc}")
                continue

            # Preserve the numeric suffix where possible; otherwise allocate
            # the next available serial within the admission batch.
            match = re.search(r"(\d+)$", student.roll_number)
            serial = int(match.group(1)) if match else 0
            key = batch
            serial = max(serial, counters.get(key, 0) + 1)
            candidate = make_roll_number(student, serial)
            while candidate in existing or any(item[2] == candidate for item in planned):
                serial += 1
                candidate = make_roll_number(student, serial)
            counters[key] = serial
            planned.append((student, student.roll_number, candidate))

        if errors:
            raise CommandError("Preflight failed; no records changed:\n" + "\n".join(errors))

        self.stdout.write(f"Students to update: {len(planned)}")
        for student, old, new in planned:
            self.stdout.write(f"  {old}  ->  {new}  ({student.name}, semester {student.semester})")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "DRY RUN ONLY. Review the mapping, then rerun with --apply to save changes."
            ))
            return

        with transaction.atomic():
            # Check all target values again inside the transaction before writing.
            targets = [new for _, _, new in planned]
            if Student.objects.filter(roll_number__in=targets).exists():
                raise CommandError("A target roll number already exists. No records changed.")
            for student, _, new in planned:
                student.roll_number = new
                student.save(update_fields=["roll_number", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"Successfully updated {len(planned)} student records. Related seating allocations were preserved."
        ))
