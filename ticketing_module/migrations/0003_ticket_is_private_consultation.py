from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ticketing_module", "0002_alter_ticket_options_alter_ticketauditlog_options_and_more")]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="is_private_consultation",
            field=models.BooleanField(
                db_index=True,
                default=False,
                verbose_name="گفت‌وگوی خصوصی با مشاور اختصاصی",
            ),
        )
    ]
