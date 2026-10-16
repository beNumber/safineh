from django.db import migrations
from django.db.models import Q


def approve_private_text_messages(apps, schema_editor):
    ticket_model = apps.get_model('ticketing_module', 'Ticket')
    message_model = apps.get_model('ticketing_module', 'TicketMessage')
    database = schema_editor.connection.alias
    text_messages = message_model.objects.using(database).filter(
        ticket__is_private_consultation=True,
        is_internal=False,
    ).filter(Q(attachment='') | Q(attachment__isnull=True)).exclude(content='')
    text_messages.filter(moderation_status='PENDING').update(
        moderation_status='APPROVED', is_approved_by_moderator=True,
    )
    pending_tickets = message_model.objects.using(database).filter(
        moderation_status='PENDING',
    ).values('ticket_id')
    ticket_model.objects.using(database).filter(
        is_private_consultation=True,
        current_queue='MODERATOR',
        current_assignee_user__isnull=False,
        status='PENDING_APPROVAL',
        pk__in=text_messages.filter(moderation_status='APPROVED').values('ticket_id'),
    ).exclude(pk__in=pending_tickets).update(current_queue='CONSULTANT', status='OPEN')


class Migration(migrations.Migration):
    dependencies = [('ticketing_module', '0004_alter_ticket_current_queue_and_more')]

    operations = [migrations.RunPython(approve_private_text_messages, migrations.RunPython.noop)]
