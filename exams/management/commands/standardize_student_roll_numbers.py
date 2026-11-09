"""
Repair legacy and accidentally duplicated student roll numbers.

Run without --apply first to inspect the exact mapping:
    python manage.py standardize_student_roll_numbers

Apply after checking the preview:
    python manage.py standardize_student_roll_numbers --apply
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exams.models import Student

CANONICAL_ROLL = re.compile(r"^992[3-6][0-9]{8}$")
EMBEDDED_CANONICAL_ROLL = re.compile(r"992[3-6][0-9]{8}")


def batch_for_semester(semester):
    if semester in (1, 2):
        return 2026
    if semester in (3, 4):
        return 2025
    if semester in (5, 6):
        return 2024
    if semester in (7, 8):
        return 2023
    raise ValueError(f"Unsupported semester: {semester}")


def make_roll_number(batch, sequence):
    # 12 digits total: 9924 + 0103 + 0018, for example.
    return f"99{str(batch)[-2:]}0103{sequence:04d}"


class Command(BaseCommand):
    help = "Preview or repair existing student roll numbers in place."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist changes after preview.")

    def handle(self, *args, **options):
        all_students = list(Student.objects.all().order_by("pk"))
        students = [s for s in all_students if not CANONICAL_ROLL.fullmatch(s.roll_number or "")]
        if not students:
            self.stdout.write(self.style.SUCCESS("All student roll numbers already use the 12-digit format."))
            return

        # Keep valid roll numbers reserved so the repair cannot overwrite them.
        reserved = {
            s.roll_number for s in all_students
            if CANONICAL_ROLL.fullmatch(s.roll_number or "")
        }
        planned = []
        planned_numbers = set()
        errors = []

        for student in students:
            try:
                batch = batch_for_semester(student.semester)
            except ValueError as exc:
                errors.append(f"{student.roll_number}: {exc}")
                continue

            old_roll = student.roll_number or ""
            embedded = EMBEDDED_CANONICAL_ROLL.findall(old_roll)
            if embedded:
                # If an earlier run accidentally prefixed a valid roll number
                # to itself, recover the original 12-digit value's last 4 digits.
                sequence = int(embedded[-1][-4:])
            else:
                trailing_digits = re.search(r"(\d+)$", old_roll)
                sequence = int(trailing_digits.group(1)[-4:]) if trailing_digits else 0

            if sequence < 1:
                sequence = student.pk
            candidate = make_roll_number(batch, sequence)

            if candidate in reserved or candidate in planned_numbers:
                errors.append(
                    f"{old_roll}: target {candidate} already belongs to another student; "
                    "no records will be changed. Resolve this collision manually."
                )
                continue

            planned.append((student, old_roll, candidate))
            planned_numbers.add(candidate)

        if errors:
            raise CommandError("Preflight failed; no records changed:\n" + "\n".join(errors))

        self.stdout.write(f"Students to repair: {len(planned)}")
        for student, old, new in planned:
            self.stdout.write(f"  {old}  ->  {new}  ({student.name}, semester {student.semester})")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "DRY RUN ONLY. No database writes were made. Review the mapping, then rerun with --apply."
            ))
            return

        with transaction.atomic():
            # Recheck collisions immediately before saving.
            targets = [new for _, _, new in planned]
            if Student.objects.filter(roll_number__in=targets).exclude(
                pk__in=[s.pk for s, _, _ in planned]
            ).exists():
                raise CommandError("A target roll number now exists. No records changed.")
            for student, _, new in planned:
                student.roll_number = new
                student.save(update_fields=["roll_number", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"Repaired {len(planned)} student records in place. Student IDs and linked seating allocations are preserved."
        ))
