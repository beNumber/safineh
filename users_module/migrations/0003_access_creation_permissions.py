import django.db.models.deletion
from django.db import migrations, models


def migrate_question_bank_accesses(apps, schema_editor):
    Access = apps.get_model('users_module', 'Access')
    Access.objects.filter(name='bank').update(name='create_question')
    for code in ('create_question', 'create_chapter', 'create_subject'):
        Access.objects.get_or_create(name=code, subject=None)


class Migration(migrations.Migration):
    dependencies = [
        ('users_module', '0002_alter_access_options_alter_access_subject_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='access',
            name='unique_access_per_subject',
        ),
        migrations.AlterField(
            model_name='access',
            name='name',
            field=models.CharField(
                choices=[
                    ('create_question', 'ایجاد و مدیریت سؤال'),
                    ('create_chapter', 'ایجاد و مدیریت فصل'),
                    ('create_subject', 'ایجاد و مدیریت درس'),
                    ('ticket', 'تیکت'),
                    ('quiz', 'آزمون'),
                    ('course', 'دوره'),
                ],
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name='access',
            name='subject',
            field=models.ForeignKey(
                blank=True,
                help_text='خالی بودن درس یعنی دسترسی برای همه درس‌ها.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='users_module.subject',
            ),
        ),
        migrations.RunPython(
            migrate_question_bank_accesses,
            migrations.RunPython.noop,
        ),
    ]
