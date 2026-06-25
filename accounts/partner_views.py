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
    TirageStatus,
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
    
    # Get borlettes the partner can manage - show ALL borlettes by default
    managed_borlettes = Borlette.objects.all()
    # Show all subscriptions - no filter
    subscriptions_filter = {}
    
    # Subscriptions - Get subscriptions for borlettes managed by this partner
    all_subscriptions = (
        Subscription.objects.filter(**subscriptions_filter)
        .select_related("user", "borlette")
        .order_by("-end_date")
    )
    
    # Get subscriptions with payment proofs
    subscriptions_with_proofs = all_subscriptions.filter(payment_proof__isnull=False).order_by("-created_at")
    
    # Calculate days remaining for each subscription
    today = timezone.now().date()
    now = timezone.now()
    from datetime import datetime, time
    
    # Add days_remaining, hours_remaining, and status color
    for sub in all_subscriptions:
        sub.days_remaining = (sub.end_date - today).days
        
        # For trial subscriptions, calculate hours remaining (72h = 3 days)
        if sub.subscription_type == 'trial':
            # Convert end_date to datetime for precise calculation
            end_datetime = datetime.combine(sub.end_date, time.min)
            if timezone.is_aware(now):
                end_datetime = timezone.make_aware(end_datetime)
            sub.hours_remaining = ((end_datetime - now).total_seconds()) / 3600
            sub.is_trial = True
        else:
            sub.hours_remaining = None
            sub.is_trial = False
            
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
        borlette__in=managed_borlettes,
        heure_tirage__lte=timezone.now()
    ).order_by('-heure_tirage')[:10]
    
    # Tirages without results (need partner to submit)
    tirages_needing_results = Tirage.objects.filter(
        borlette__in=managed_borlettes,
        heure_tirage__lte=timezone.now()
    ).exclude(resultats__isnull=False).order_by('-heure_tirage')[:20]
    
    # Upcoming tirages
    upcoming_tirages = Tirage.objects.filter(
        borlette__in=managed_borlettes,
        heure_tirage__gt=timezone.now()
    ).order_by('heure_tirage')[:10]
    
    # ===== RESULTS HISTORY =====
    # Past tirages with results (for history display)
    past_results = Tirage.objects.filter(
        borlette__in=managed_borlettes,
        heure_tirage__lte=timezone.now(),
        resultats__isnull=False
    ).select_related('borlette').prefetch_related('resultats').order_by('-heure_tirage')[:30]
    
    # ===== ADMINS & AFFILIATES STATS =====
    # Admin users (directors of managed borlettes)
    admin_users = User.objects.filter(
        role=UserRole.ADMIN,
        borlette__in=managed_borlettes
    ).select_related('borlette').order_by('-date_joined')[:20]
    
    # Affiliate users
    affiliate_users = User.objects.filter(
        role=UserRole.AFFILIATE,
        is_active=True
    ).order_by('-date_joined')[:20]
    
    # Stats
    total_admins = User.objects.filter(role=UserRole.ADMIN).count()
    total_affiliates = User.objects.filter(role=UserRole.AFFILIATE, is_active=True).count()
    
    return render(request, "accounts/partner_dashboard.html", {
        "partner_profile": partner_profile,
        "allowed_borlettes": managed_borlettes,
        
        # Stats
        "total_admins": total_admins,
        "total_affiliates": total_affiliates,
        "total_pending_amount": total_pending_amount,
        
        # Admins and Affiliates lists
        "admin_users": admin_users,
        "affiliate_users": affiliate_users,
        
        # Subscriptions - convert QuerySet to list for counting after we annotated it
        "all_subscriptions": list(all_subscriptions),
        "active_subscriptions": active_subscriptions,
        "expired_subscriptions": expired_subscriptions,
        "urgent_subscriptions": urgent_subscriptions,
        "all_subscriptions_count": len(list(all_subscriptions)),
        "urgent_count": len(urgent_subscriptions),
        "expired_count": len(expired_subscriptions),
        
        # Payment proofs
        "subscriptions_with_proofs": list(subscriptions_with_proofs),
        "subscriptions_with_proofs_count": len(list(subscriptions_with_proofs)),
        
        # Withdrawals
        "pending_withdrawals": pending_withdrawals,
        "pending_withdrawals_count": len(pending_withdrawals),
        "recent_paid_withdrawals": recent_paid_withdrawals,
        
        # Tirages
        "recent_tirages": recent_tirages,
        "tirages_needing_results": tirages_needing_results,
        "tirages_needing_results_count": len(tirages_needing_results),
        "upcoming_tirages": upcoming_tirages,
        "past_results": past_results,
    })


@login_required
def partner_renew_subscription(request: HttpRequest, subscription_id: int):
    """Renew a subscription by 30 days - requires existing payment proof and countdown < 7 days."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    partner_profile = request.user.partner_profile
    
    # Check if partner can manage this subscription
    if subscription.borlette not in partner_profile.allowed_borlettes.all():
        if partner_profile.allowed_borlettes.exists():
            messages.error(request, "Vous ne pouvez pas gérer cette borlette.")
            return redirect("partner:dashboard")
    
    # Vérifier qu'il y a une preuve de paiement (uploadée par l'admin)
    if not subscription.payment_proof:
        messages.error(request, "Aucune preuve de paiement trouvée. L'admin doit uploader la preuve avant le renouvellement.")
        return redirect("partner:dashboard")
    
    # Vérifier que le compte à rebours est inférieur à 7 jours
    today = timezone.now().date()
    days_remaining = (subscription.end_date - today).days
    if days_remaining > 7:
        messages.error(request, f"Le renouvellement n'est disponible que 7 jours avant l'expiration. Jours restants: {days_remaining}")
        return redirect("partner:dashboard")
    
    if request.method == "POST":
        # Get months from form (default 1 month)
        months = int(request.POST.get('months', 1))
        
        # Extend subscription
        from datetime import timedelta
        today = timezone.now().date()
        days_to_add = months * 30
        
        if subscription.end_date < today:
            # Expired - start from today
            subscription.end_date = today + timedelta(days=days_to_add)
        else:
            # Active - extend from current end
            subscription.end_date = subscription.end_date + timedelta(days=days_to_add)
        
        # Clear payment proof after renewal (admin will upload new one for next renewal)
        subscription.payment_proof = None
        subscription.payment_proof_uploaded_at = None
        subscription.is_active = True
        subscription.save()
        
        messages.success(
            request,
            f"Abonnement renouvelé jusqu'au {subscription.end_date.strftime('%d/%m/%Y')}. Preuve de paiement enregistrée."
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
    """Submit results for a tirage - applied to ALL borlettes with the same tirage code."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    tirage = get_object_or_404(Tirage, id=tirage_id)
    
    if request.method == "POST":
        # Lot principal (3 lots)
        lot1 = request.POST.get("lot1")
        lot2 = request.POST.get("lot2")
        lot3 = request.POST.get("lot3")
        
        # Loto3
        loto3 = request.POST.get("loto3")
        
        # Loto4 - 3 options
        loto4_1 = request.POST.get("loto4_1")
        loto4_2 = request.POST.get("loto4_2")
        loto4_3 = request.POST.get("loto4_3")
        
        # Loto5 - 2 options
        loto5_1 = request.POST.get("loto5_1")
        loto5_2 = request.POST.get("loto5_2")
        
        # Validate at least the main 3 lots are provided
        if lot1 and lot2 and lot3:
            # Find ALL tirages with the same code (across all borlettes)
            tirage_code = tirage.code
            all_tirages_with_code = Tirage.objects.filter(
                code=tirage_code,
                statut=TirageStatus.ACTIF
            ).select_related('borlette')
            
            created_count = 0
            updated_count = 0
            
            for t in all_tirages_with_code:
                defaults = {
                    'lot1': lot1,
                    'lot2': lot2,
                    'lot3': lot3,
                    'date': timezone.now().date(),
                    'chiffre_loto3': loto3 if loto3 else '',
                    'source': 'PARTNER',
                    'statut': 'pending',
                }
                
                obj, created = Resultat.objects.update_or_create(
                    tirage=t,
                    session_key=t.session_key,
                    defaults=defaults
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            messages.success(
                request, 
                f"Résultats enregistrés pour {all_tirages_with_code.count()} borlette(s) "
                f"(créés: {created_count}, mis à jour: {updated_count})"
            )
            return redirect("partner:dashboard")
        else:
            messages.error(request, "Veuillez saisir les 3 lots principaux (Lot1, Lot2, Lot3).")
    
    return render(request, "accounts/partner_submit_result.html", {
        "tirage": tirage,
    })


@login_required
def partner_borlettes(request: HttpRequest):
    """Borlettes management page."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    partner_profile = request.user.partner_profile
    
    # Get borlettes
    if partner_profile.allowed_borlettes.exists():
        borlettes = partner_profile.allowed_borlettes.all().select_related('user')
    else:
        borlettes = Borlette.objects.all().select_related('user')
    
    # Annotate with subscription info
    for borlette in borlettes:
        borlette.active_subscription = Subscription.objects.filter(
            borlette=borlette,
            end_date__gte=timezone.now().date()
        ).first()
        if borlette.active_subscription:
            borlette.active_subscription.days_remaining = (
                borlette.active_subscription.end_date - timezone.now().date()
            ).days
    
    total_admins = User.objects.filter(role=UserRole.ADMIN).count()
    
    return render(request, "accounts/partner_borlettes.html", {
        "borlettes": borlettes,
        "total_borlettes": borlettes.count(),
        "borlettes_with_subscriptions": borlettes.filter(subscriptions__end_date__gte=timezone.now().date()).distinct().count(),
        "total_admins": total_admins,
    })


@login_required
def partner_subscriptions(request: HttpRequest):
    """Subscriptions management page."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    partner_profile = request.user.partner_profile
    
    # Get borlettes filter
    if partner_profile.allowed_borlettes.exists():
        allowed_borlettes = partner_profile.allowed_borlettes.all()
    else:
        allowed_borlettes = Borlette.objects.all()
    
    # Get all subscriptions
    all_subscriptions = Subscription.objects.filter(
        borlette__in=allowed_borlettes
    ).select_related('borlette', 'user').order_by('-end_date')
    
    # Calculate days remaining
    today = timezone.now().date()
    for sub in all_subscriptions:
        sub.days_remaining = (sub.end_date - today).days
    
    # Categorize
    active_subscriptions = [s for s in all_subscriptions if s.days_remaining > 0]
    expired_subscriptions = [s for s in all_subscriptions if s.days_remaining <= 0]
    urgent_subscriptions = [s for s in all_subscriptions if 0 < s.days_remaining <= 7]
    
    # Filter by status
    current_filter = request.GET.get('filter', 'all')
    if current_filter == 'active':
        filtered_subscriptions = active_subscriptions
    elif current_filter == 'urgent':
        filtered_subscriptions = urgent_subscriptions
    elif current_filter == 'expired':
        filtered_subscriptions = expired_subscriptions
    elif current_filter == 'trial':
        filtered_subscriptions = [s for s in all_subscriptions if s.subscription_type == 'trial']
    else:
        filtered_subscriptions = list(all_subscriptions)
    
    return render(request, "accounts/partner_subscriptions.html", {
        "all_subscriptions": all_subscriptions,
        "active_subscriptions": active_subscriptions,
        "expired_subscriptions": expired_subscriptions,
        "urgent_subscriptions": urgent_subscriptions,
        "filtered_subscriptions": filtered_subscriptions,
        "current_filter": current_filter,
        "urgent_count": len(urgent_subscriptions),
        "expired_count": len(expired_subscriptions),
    })


@login_required
def partner_tirages(request: HttpRequest):
    """Tirages management page - grouped by code (unique tirages only)."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    partner_profile = request.user.partner_profile
    
    # Get borlettes
    if partner_profile.allowed_borlettes.exists():
        allowed_borlettes = partner_profile.allowed_borlettes.all()
    else:
        allowed_borlettes = Borlette.objects.all()
    
    # Get all tirages from allowed borlettes
    all_tirages = Tirage.objects.filter(
        borlette__in=allowed_borlettes
    ).select_related('borlette').prefetch_related('resultats')
    
    # Group by tirage code - pick one representative per code (first one)
    seen_codes = {}
    grouped_tirages = []
    
    for t in all_tirages.order_by('ordre_affichage', 'nom'):
        if t.code and t.code not in seen_codes:
            seen_codes[t.code] = t
            # Count how many borlettes have this tirage code
            t.borlettes_count = Tirage.objects.filter(
                code=t.code,
                borlette__in=allowed_borlettes
            ).values('borlette').distinct().count()
            # Check if any borlette has a result for this tirage code today
            t.has_any_result = Resultat.objects.filter(
                tirage__code=t.code,
                date=timezone.now().date()
            ).exists()
            grouped_tirages.append(t)
    
    # Sort by display order
    grouped_tirages.sort(key=lambda x: (x.ordre_affichage, x.nom))
    
    now = timezone.now()
    
    # Calculate stats
    total_unique_tirages = len(grouped_tirages)
    tirages_with_results = sum(1 for t in grouped_tirages if t.has_any_result)
    tirages_needing_results = [t for t in grouped_tirages if not t.has_any_result]
    
    # Filter by tab
    current_tab = request.GET.get('tab', 'all')
    if current_tab == 'pending':
        tirages = tirages_needing_results
    elif current_tab == 'upcoming':
        # All unique tirages are considered as upcoming
        tirages = grouped_tirages
    else:
        tirages = grouped_tirages
    
    return render(request, "accounts/partner_tirages.html", {
        "tirages": tirages,
        "total_tirages": total_unique_tirages,
        "tirages_with_results": tirages_with_results,
        "tirages_needing_results": len(tirages_needing_results),
        "upcoming_tirages": total_unique_tirages,
        "current_tab": current_tab,
        "now": now,
    })


@login_required
def partner_results(request: HttpRequest):
    """Results history page - grouped by tirage code to avoid duplicates."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    partner_profile = request.user.partner_profile
    
    # Get borlettes
    if partner_profile.allowed_borlettes.exists():
        allowed_borlettes = partner_profile.allowed_borlettes.all()
    else:
        allowed_borlettes = Borlette.objects.all()
    
    # Get results - but group by tirage code to avoid duplicates
    # Use distinct tirage codes with their latest result
    from django.db.models import Max, Count
    
    # Get all unique (date, tirage_code) combinations with their latest result
    resultats_raw = Resultat.objects.filter(
        tirage__borlette__in=allowed_borlettes
    ).select_related('tirage').order_by('-date', '-created_at')
    
    # Filter by date
    date_filter = request.GET.get('date')
    if date_filter:
        resultats_raw = resultats_raw.filter(date=date_filter)
    
    # Filter by tirage code
    tirage_code = request.GET.get('tirage_code')
    if tirage_code:
        resultats_raw = resultats_raw.filter(tirage__code=tirage_code)
    
    # Group by (date, tirage_code) to avoid duplicates
    seen = {}
    grouped_results = []
    for r in resultats_raw[:200]:  # Check more to get unique ones
        key = (r.date, r.tirage.code)
        if key not in seen:
            seen[key] = r
            # Count how many borlettes have this result
            r.borlettes_count = Resultat.objects.filter(
                date=r.date,
                tirage__code=r.tirage.code,
                tirage__borlette__in=allowed_borlettes
            ).values('tirage__borlette').distinct().count()
            grouped_results.append(r)
        if len(grouped_results) >= 50:
            break
    
    # Get unique tirage codes for filter dropdown
    tirage_codes = Tirage.objects.filter(
        borlette__in=allowed_borlettes
    ).values_list('code', flat=True).distinct()
    
    return render(request, "accounts/partner_results.html", {
        "resultats": grouped_results,
        "borlettes": allowed_borlettes,
        "tirage_codes": tirage_codes,
        "date_filter": date_filter,
        "tirage_code_filter": tirage_code,
    })


@login_required
def partner_affiliates(request: HttpRequest):
    """Affiliates management page."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    # Get all affiliates
    affiliates = AffiliateProfile.objects.select_related('user').all()
    
    # Calculate stats
    active_affiliates = affiliates.filter(user__is_active=True)
    
    # Filter by status
    current_status = request.GET.get('status', 'all')
    if current_status == 'active':
        affiliates = active_affiliates
    elif current_status == 'inactive':
        affiliates = affiliates.filter(user__is_active=False)
    elif current_status == 'suspended':
        affiliates = affiliates.filter(user__is_active=False)
    
    return render(request, "accounts/partner_affiliates.html", {
        "affiliates": affiliates,
        "total_affiliates": AffiliateProfile.objects.count(),
        "active_affiliates": active_affiliates.count(),
        "current_status": current_status,
    })


@login_required
def partner_withdrawals(request: HttpRequest):
    """Withdrawals management page."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    # Get all withdrawals
    all_withdrawals = WithdrawalRequest.objects.select_related('user', 'processed_by').order_by('-created_at')
    
    # Calculate stats (last 30 days)
    from datetime import timedelta
    last_30_days = timezone.now() - timedelta(days=30)
    
    pending_count = all_withdrawals.filter(status=WithdrawalStatus.PENDING).count()
    paid_count = all_withdrawals.filter(status=WithdrawalStatus.PAID, processed_at__gte=last_30_days).count()
    rejected_count = all_withdrawals.filter(status=WithdrawalStatus.REJECTED, processed_at__gte=last_30_days).count()
    
    pending_withdrawals = all_withdrawals.filter(status=WithdrawalStatus.PENDING)
    total_pending_amount = sum(w.amount for w in pending_withdrawals)
    
    # Filter by status
    current_status = request.GET.get('status', 'pending')
    if current_status == 'pending':
        withdrawals = pending_withdrawals
    elif current_status == 'paid':
        withdrawals = all_withdrawals.filter(status=WithdrawalStatus.PAID)
    elif current_status == 'rejected':
        withdrawals = all_withdrawals.filter(status=WithdrawalStatus.REJECTED)
    else:
        withdrawals = all_withdrawals[:50]
    
    return render(request, "accounts/partner_withdrawals.html", {
        "withdrawals": withdrawals,
        "pending_count": pending_count,
        "paid_count": paid_count,
        "rejected_count": rejected_count,
        "total_pending_amount": total_pending_amount,
        "current_status": current_status,
    })


@login_required
@require_POST
def bulk_renew_subscriptions(request: HttpRequest):
    """Bulk renew selected subscriptions."""
    if request.user.role != UserRole.PARTNER:
        return redirect("/portal/login/")
    
    subscription_ids = request.POST.get('subscription_ids', '')
    if subscription_ids:
        from datetime import timedelta
        today = timezone.now().date()
        
        ids = [int(id) for id in subscription_ids.split(',') if id.isdigit()]
        renewed_count = 0
        
        for sub_id in ids:
            try:
                sub = Subscription.objects.get(id=sub_id)
                if sub.end_date < today:
                    sub.end_date = today + timedelta(days=30)
                else:
                    sub.end_date = sub.end_date + timedelta(days=30)
                sub.is_active = True
                sub.save()
                renewed_count += 1
            except Subscription.DoesNotExist:
                continue
        
        messages.success(request, f"{renewed_count} abonnement(s) renouvelé(s) avec succès.")
    
    return redirect("partner:subscriptions")


@login_required
def toggle_affiliate_status(request: HttpRequest, user_id: int):
    """Toggle affiliate active/inactive status."""
    if request.user.role != UserRole.PARTNER:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"error": "Unauthorized"}, status=403)
        return redirect("/portal/login/")
    
    try:
        affiliate = User.objects.get(id=user_id, role=UserRole.AFFILIATE)
        affiliate.is_active = not affiliate.is_active
        affiliate.save()
        
        messages.success(request, f"Affilié {affiliate.username} {'activé' if affiliate.is_active else 'suspendu'}.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "is_active": affiliate.is_active,
                "message": f"Affilié {'activé' if affiliate.is_active else 'suspendu'}"
            })
    except User.DoesNotExist:
        messages.error(request, "Affilié non trouvé.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"error": "Affilié non trouvé"}, status=404)
    
    return redirect("partner:affiliates")
