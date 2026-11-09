from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0002_student_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='target_course',
            field=models.CharField(blank=True, choices=[('B.Tech CSE', 'B.Tech CSE'), ('B.Tech ECE', 'B.Tech ECE'), ('B.Tech ME', 'B.Tech ME'), ('B.Tech CE', 'B.Tech CE'), ('B.Tech EE', 'B.Tech EE'), ('BCA', 'BCA'), ('MCA', 'MCA'), ('M.Tech', 'M.Tech')], default='', max_length=50, verbose_name='Applicable Course'),
        ),
        migrations.AddField(
            model_name='exam',
            name='target_semester',
            field=models.IntegerField(blank=True, choices=[(1, 'Semester 1'), (2, 'Semester 2'), (3, 'Semester 3'), (4, 'Semester 4'), (5, 'Semester 5'), (6, 'Semester 6'), (7, 'Semester 7'), (8, 'Semester 8')], null=True, verbose_name='Applicable Semester'),
        ),
    ]
