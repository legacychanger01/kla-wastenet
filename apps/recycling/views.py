"""KLA WasteNet Pro — Recycling Views"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect
from apps.recycling.models import RecyclingRequest, RewardPoints, EnvironmentalCampaign
from apps.accounts.views import role_required


@login_required
def recycling_request(request):
    if request.method == 'POST':
        rec = RecyclingRequest.objects.create(
            user=request.user,
            material_type=request.POST.get('material_type'),
            estimated_weight_kg=request.POST.get('estimated_weight_kg', 1),
            description=request.POST.get('description', ''),
            address=request.POST.get('address', request.user.address),
            division=request.POST.get('division', request.user.division),
            preferred_date=request.POST.get('preferred_date') or None,
        )
        if 'image' in request.FILES:
            rec.image = request.FILES['image']
            rec.save(update_fields=['image'])

        messages.success(request, f'Recycling request submitted! You will earn reward points upon collection.')
        return redirect('my_rewards')

    active_campaigns = EnvironmentalCampaign.objects.filter(status='active')
    return render(request, 'recycling/request.html', {
        'MATERIAL_CHOICES': RecyclingRequest.MATERIAL_CHOICES,
        'DIVISIONS': request.user.DIVISION_CHOICES,
        'campaigns': active_campaigns,
    })


@login_required
def my_rewards(request):
    transactions = RewardPoints.objects.filter(user=request.user).order_by('-created_at')
    total = transactions.aggregate(total=Sum('points'))['total'] or 0
    recycling_history = RecyclingRequest.objects.filter(user=request.user).order_by('-created_at')[:10]

    # Environmental impact
    total_kg = RecyclingRequest.objects.filter(
        user=request.user, status__in=('collected', 'processed', 'rewarded')
    ).aggregate(total=Sum('actual_weight_kg'))['total'] or 0

    carbon_saved = RecyclingRequest.objects.filter(
        user=request.user
    ).aggregate(total=Sum('carbon_saved_kg'))['total'] or 0

    return render(request, 'recycling/my_rewards.html', {
        'transactions': transactions[:10],
        'total_points': total,
        'recycling_history': recycling_history,
        'total_recycled_kg': total_kg,
        'carbon_saved_kg': carbon_saved,
    })


@login_required
def campaigns(request):
    active = EnvironmentalCampaign.objects.filter(status='active')
    upcoming = EnvironmentalCampaign.objects.filter(status='draft')
    past = EnvironmentalCampaign.objects.filter(status='ended')[:5]
    return render(request, 'recycling/campaigns.html', {
        'active_campaigns': active,
        'upcoming': upcoming,
        'past': past,
    })


@role_required('admin', 'super_admin', 'kcca_official', 'recycler')
def admin_recycling(request):
    requests_qs = RecyclingRequest.objects.select_related('user').order_by('-created_at')
    return render(request, 'recycling/admin.html', {'requests': requests_qs[:50]})
