"""KLA WasteNet Pro — Support Ticket Views"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from apps.support.models import SupportTicket, TicketMessage
from apps.accounts.views import role_required


@login_required
def support_tickets(request):
    if request.user.is_admin():
        tickets = SupportTicket.objects.select_related('user', 'assigned_to').order_by('-created_at')
    else:
        tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support/tickets.html', {'tickets': tickets[:20]})


@login_required
def new_ticket(request):
    if request.method == 'POST':
        ticket = SupportTicket.objects.create(
            user=request.user,
            category=request.POST.get('category'),
            priority=request.POST.get('priority', 'medium'),
            subject=request.POST.get('subject'),
            description=request.POST.get('description'),
        )
        if 'attachment' in request.FILES:
            ticket.attachment = request.FILES['attachment']
            ticket.save(update_fields=['attachment'])

        messages.success(request, f'Ticket {ticket.ticket_number} submitted. We will respond within 24 hours.')
        return redirect('ticket_detail', pk=ticket.pk)

    return render(request, 'support/new_ticket.html', {
        'CATEGORY_CHOICES': SupportTicket.CATEGORY_CHOICES,
        'PRIORITY_CHOICES': SupportTicket.PRIORITY_CHOICES,
    })


@login_required
def ticket_detail(request, pk):
    if request.user.is_admin():
        ticket = get_object_or_404(SupportTicket, pk=pk)
    else:
        ticket = get_object_or_404(SupportTicket, pk=pk, user=request.user)

    messages_qs = ticket.messages.select_related('sender')
    if not request.user.is_admin():
        messages_qs = messages_qs.filter(is_internal=False)

    if request.method == 'POST':
        msg_text = request.POST.get('message', '').strip()
        if msg_text:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=msg_text,
            )
            if ticket.status == 'waiting_customer' and not request.user.is_admin():
                ticket.status = 'in_progress'
                ticket.save(update_fields=['status'])
            messages.success(request, 'Message sent.')
            return redirect('ticket_detail', pk=pk)

    return render(request, 'support/ticket_detail.html', {
        'ticket': ticket,
        'ticket_messages': messages_qs,
    })


@role_required('admin', 'super_admin', 'kcca_official')
def admin_tickets(request):
    status_filter = request.GET.get('status', '')
    tickets = SupportTicket.objects.select_related('user', 'assigned_to').order_by('-created_at')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    return render(request, 'support/admin_tickets.html', {
        'tickets': tickets[:50],
        'status_filter': status_filter,
        'STATUS_CHOICES': SupportTicket.STATUS_CHOICES,
    })


@role_required('admin', 'super_admin')
def assign_ticket(request, pk):
    from apps.accounts.models import User
    ticket = get_object_or_404(SupportTicket, pk=pk)
    if request.method == 'POST':
        agent_id = request.POST.get('agent')
        agent = get_object_or_404(User, pk=agent_id)
        ticket.assigned_to = agent
        ticket.status = 'in_progress'
        ticket.save(update_fields=['assigned_to', 'status'])
        messages.success(request, f'Ticket assigned to {agent.get_display_name()}')
        return redirect('admin_tickets')
    agents = User.objects.filter(role__in=['admin', 'super_admin'], is_active=True)
    return render(request, 'support/assign_ticket.html', {'ticket': ticket, 'agents': agents})
