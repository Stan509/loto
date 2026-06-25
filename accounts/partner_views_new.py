"""
Partner views for managing the system with limited permissions.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST

from accounts.models import (
    User,
    UserRole,
    PartnerProfile,
    Subscription,
    AffiliateProfile,
    WithdrawalRequest,
    WithdrawalStatus,
    Borlette,
    Tirage,
    Resultat,
)


@login_required
def partner_dashboard(request: HttpRequest):
    """Complete dashboard for partners to manage the entire system."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    # Get or create partner profile
    partner_profile, created = PartnerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'can_submit_results': True,
            'can_confirm_affiliate_payments': True,
            'can_renew_subscriptions': True,
        }
    )
    
    # Get accessible borlettes (managed by this partner)
    if partner_profile.allowed_borlettes.exists():
        allowed_borlettes = partner_profile.allowed_borlettes.all()
    else:
        allowed_borlettes = Borlette.objects.all()
    
    # ===== STATISTICS =====
    today = timezone.now().date()
    
    # All admin users (directors) with subscriptions
    admin_users = User.objects.filter(
        role=UserRole.ADMIN,
        subscriptions__borlette__in=allowed_borlettes
    ).distinct().select_related()
    
    # All affiliate users
    affiliate_users = User.objects.filter(
        role=UserRole.AFFILIATE
    ).select_related()
    
    # Total stats
    total_admins = admin_users.count()
    total_affiliates = affiliate_users.count()
    
    # ===== SUBSCRIPTIONS MANAGEMENT =====
    # All subscriptions (active and inactive) for partner's borlettes
    all_subscriptions = Subscription.objects.filter(
        borlette__in=allowed_borlettes
    ).select_related('borlette', 'user').order_by('-end_date')
    
    # Add days_remaining and status color
    for sub in all_subscriptions:
        sub.days_remaining = (sub.end_date - today).days
        if sub.days_remaining <= 0:
            sub.status_color = 'red'
            sub.status_label = 'Expiré'
        elif sub.days_remaining <= 7:
            sub.status_color = 'amber'
            sub.status_label = 'Urgent'
        elif sub.days_remaining <= 30:
            sub.status_color = 'yellow'
            sub.status_label = 'Bientôt'
        else:
            sub.status_color = 'green'
            sub.status_label = 'Actif'
    
    # Separate active and expired
    active_subscriptions = [s for s in all_subscriptions if s.days_remaining > 0]
    expired_subscriptions = [s for s in all_subscriptions if s.days_remaining <= 0]
    urgent_subscriptions = [s for s in all_subscriptions if 0 < s.days_remaining <= 7]
    
    # ===== WITHDRAWALS MANAGEMENT =====
    # All pending withdrawals
    pending_withdrawals = WithdrawalRequest.objects.filter(
        status=WithdrawalStatus.PENDING,
        user__role=UserRole.AFFILIATE
    ).select_related('user').order_by('-created_at')
    
    # Recent completed withdrawals
    recent_paid_withdrawals = WithdrawalRequest.objects.filter(
        status=WithdrawalStatus.PAID
    ).select_related('user').order_by('-processed_at')[:10]
    
    total_pending_amount = sum(w.amount for w in pending_withdrawals)
    
    # ===== TIRAGES & RESULTS =====
    # All tirages (recent and upcoming)
    recent_tirages = Tirage.objects.filter(
        borlette__in=allowed_borlettes,
        heure_tirage__lte=timezone.now()
    ).order_by('-heure_tirage')[:10]
    
    # Tirages without results (need partner to submit)
    tirages_needing_results = Tirage.objects.filter(
        borlette__in=allowed_borlettes,
        heure_tirage__lte=timezone.now(),
        resultat__isnull=True
    ).order_by('-heure_tirage')[:20]
    
    # Upcoming tirages
    upcoming_tirages = Tirage.objects.filter(
        borlette__in=allowed_borlettes,
        heure_tirage__gt=timezone.now()
    ).order_by('heure_tirage')[:10]
    
    return render(request, "accounts/partner_dashboard.html", {
        "partner_profile": partner_profile,
        "allowed_borlettes": allowed_borlettes,
        
        # Stats
        "total_admins": total_admins,
        "total_affiliates": total_affiliates,
        "total_pending_amount": total_pending_amount,
        
        # Admins and Affiliates lists
        "admin_users": admin_users,
        "affiliate_users": affiliate_users,
        
        # Subscriptions
        "all_subscriptions": all_subscriptions,
        "active_subscriptions": active_subscriptions,
        "expired_subscriptions": expired_subscriptions,
        "urgent_subscriptions": urgent_subscriptions,
        "urgent_count": len(urgent_subscriptions),
        "expired_count": len(expired_subscriptions),
        
        # Withdrawals
        "pending_withdrawals": pending_withdrawals,
        "pending_withdrawals_count": len(pending_withdrawals),
        "recent_paid_withdrawals": recent_paid_withdrawals,
        
        # Tirages
        "recent_tirages": recent_tirages,
        "tirages_needing_results": tirages_needing_results,
        "tirages_needing_results_count": len(tirages_needing_results),
        "upcoming_tirages": upcoming_tirages,
    })


@login_required
def partner_renew_subscription(request: HttpRequest, subscription_id: int):
    """Renew a subscription by 30 days."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    partner_profile = request.user.partner_profile
    
    # Check if partner can manage this subscription
    if subscription.borlette not in partner_profile.allowed_borlettes.all():
        if partner_profile.allowed_borlettes.exists():
            messages.error(request, "Vous ne pouvez pas gérer cette borlette.")
            return redirect("partner:dashboard")
    
    if request.method == "POST":
        # Extend by 30 days from today or from current end_date if not expired
        from datetime import timedelta
        today = timezone.now().date()
        
        if subscription.end_date < today:
            # Expired - start from today
            subscription.end_date = today + timedelta(days=30)
        else:
            # Active - extend from current end
            subscription.end_date = subscription.end_date + timedelta(days=30)
        
        subscription.is_active = True
        subscription.save()
        
        messages.success(
            request,
            f"Abonnement renouvelé jusqu'au {subscription.end_date.strftime('%d/%m/%Y')}"
        )
        return redirect("partner:dashboard")
    
    return render(request, "accounts/partner_renew_subscription.html", {
        "subscription": subscription,
    })


@login_required
def partner_confirm_withdrawal(request: HttpRequest, withdrawal_id: int):
    """Confirm an affiliate withdrawal with screenshot upload."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "confirm":
            # Save screenshot if provided
            if request.FILES.get("screenshot"):
                withdrawal.payment_proof = request.FILES["screenshot"]
            
            withdrawal.status = WithdrawalStatus.PAID
            withdrawal.processed_at = timezone.now()
            withdrawal.processed_by = request.user
            withdrawal.save()
            
            messages.success(request, "Paiement confirmé avec succès.")
            
        elif action == "reject":
            withdrawal.status = WithdrawalStatus.REJECTED
            withdrawal.processed_at = timezone.now()
            withdrawal.processed_by = request.user
            withdrawal.rejection_reason = request.POST.get("reason", "")
            withdrawal.save()
            
            messages.info(request, "Demande rejetée.")
        
        return redirect("partner:dashboard")
    
    return render(request, "accounts/partner_confirm_withdrawal.html", {
        "withdrawal": withdrawal,
    })


@login_required
def partner_submit_result(request: HttpRequest, tirage_id: int):
    """Submit results for a tirage."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    tirage = get_object_or_404(Tirage, id=tirage_id)
    
    if request.method == "POST":
        lot1 = request.POST.get("lot1")
        lot2 = request.POST.get("lot2")
        lot3 = request.POST.get("lot3")
        
        # Validate all lots are provided
        if lot1 and lot2 and lot3:
            Resultat.objects.update_or_create(
                tirage=tirage,
                session_key=tirage.session_key,
                defaults={
                    'lot1': lot1,
                    'lot2': lot2,
                    'lot3': lot3,
                    'date': timezone.now().date(),
                }
            )
            messages.success(request, "Résultats enregistrés avec succès.")
            return redirect("partner:dashboard")
        else:
            messages.error(request, "Veuillez saisir les 3 lots.")
    
    return render(request, "accounts/partner_submit_result.html", {
        "tirage": tirage,
    })


@login_required
@require_POST
def toggle_affiliate_status(request: HttpRequest, user_id: int):
    """Toggle affiliate active/inactive status."""
    if request.user.role != UserRole.PARTNER:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    try:
        affiliate = User.objects.get(id=user_id, role=UserRole.AFFILIATE)
        affiliate.is_active = not affiliate.is_active
        affiliate.save()
        
        return JsonResponse({
            "success": True,
            "is_active": affiliate.is_active,
            "message": f"Affilié {'activé' if affiliate.is_active else 'suspendu'}"
        })
    except User.DoesNotExist:
        return JsonResponse({"error": "Affilié non trouvé"}, status=404)
