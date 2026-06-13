"""Admin views for managing affiliate withdrawals."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from accounts.models import WithdrawalRequest, WithdrawalStatus, AffiliateProfile


@staff_member_required
def admin_affiliate_withdrawals(request: HttpRequest):
    """Admin view to manage all affiliate withdrawals."""
    # Get all withdrawals with pending status first, then by date
    withdrawals = WithdrawalRequest.objects.select_related('user', 'user__affiliate_profile').order_by(
        '-status', '-created_at'
    )
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)
    
    # Calculate stats
    pending_count = WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING).count()
    pending_amount = sum(
        w.amount for w in WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING)
    )
    
    total_paid = sum(
        w.amount for w in WithdrawalRequest.objects.filter(status=WithdrawalStatus.PAID)
    )
    
    # Check for overdue withdrawals (> 48h)
    overdue_withdrawals = WithdrawalRequest.objects.filter(
        status=WithdrawalStatus.PENDING,
        expected_by__lt=timezone.now()
    )
    overdue_count = overdue_withdrawals.count()
    
    return render(request, "admin_portal/affiliate_withdrawals.html", {
        "withdrawals": withdrawals,
        "status_filter": status_filter,
        "pending_count": pending_count,
        "pending_amount": pending_amount,
        "total_paid": total_paid,
        "overdue_count": overdue_count,
        "WithdrawalStatus": WithdrawalStatus,
    })


@staff_member_required
def admin_approve_withdrawal(request: HttpRequest, withdrawal_id: int):
    """Admin view to approve and process a withdrawal with proof upload."""
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        admin_notes = request.POST.get('admin_notes', '')
        
        if action == 'approve':
            # Handle proof screenshot upload
            proof_file = request.FILES.get('proof_screenshot')
            if proof_file:
                withdrawal.proof_screenshot = proof_file
            
            with transaction.atomic():
                withdrawal.status = WithdrawalStatus.PAID
                withdrawal.processed_at = timezone.now()
                withdrawal.processed_by = request.user
                withdrawal.admin_notes = admin_notes
                withdrawal.save()
                
                # Update affiliate profile
                affiliate_profile = withdrawal.user.affiliate_profile
                affiliate_profile.total_withdrawn += withdrawal.amount
                affiliate_profile.save()
                
                messages.success(
                    request, 
                    f"Retrait de {withdrawal.amount} GDS pour {withdrawal.user.username} approuvé et marqué comme payé."
                )
                
        elif action == 'reject':
            with transaction.atomic():
                # Refund the amount to available balance
                affiliate_profile = withdrawal.user.affiliate_profile
                affiliate_profile.available_balance += withdrawal.amount
                affiliate_profile.save()
                
                withdrawal.status = WithdrawalStatus.REJECTED
                withdrawal.processed_at = timezone.now()
                withdrawal.processed_by = request.user
                withdrawal.admin_notes = admin_notes
                withdrawal.save()
                
                messages.warning(
                    request,
                    f"Retrait de {withdrawal.amount} GDS pour {withdrawal.user.username} refusé. Le montant a été remboursé."
                )
        
        return redirect('admin_portal:affiliate_withdrawals')
    
    return render(request, "admin_portal/approve_withdrawal.html", {
        "withdrawal": withdrawal,
    })


@staff_member_required
def admin_affiliate_list(request: HttpRequest):
    """Admin view to list all affiliates with their stats."""
    affiliates = AffiliateProfile.objects.select_related('user').order_by('-total_earned')
    
    # Calculate totals
    total_affiliates = affiliates.count()
    total_earnings = sum(a.total_earned for a in affiliates)
    total_pending = sum(
        w.amount for w in WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING)
    )
    
    return render(request, "admin_portal/affiliate_list.html", {
        "affiliates": affiliates,
        "total_affiliates": total_affiliates,
        "total_earnings": total_earnings,
        "total_pending": total_pending,
    })
