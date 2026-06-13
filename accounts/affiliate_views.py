from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.contrib import messages
from django.db import transaction

from accounts.models import PromoCode, UserRole, AffiliateProfile, Referral, Borlette, WithdrawalRequest, WithdrawalStatus
from accounts.pricing_config import (
    calculate_affiliate_commission,
    calculate_affiliate_total_earnings,
    AFFILIATE_COMMISSIONS,
    BONUS_VALIDITY_MONTHS,
)


@login_required
def affiliate_dashboard(request: HttpRequest):
    if request.user.is_superuser or request.user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AGENT):
        return redirect("/portal/dashboard/")

    if request.user.role != UserRole.AFFILIATE:
        return redirect("/portal/login/")

    # Get or create affiliate profile
    affiliate_profile, created = AffiliateProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'promo_code': f"GAB{request.user.username[:6].upper()}",
            'commission_percent': 20
        }
    )

    # Get referrals data
    referrals = Referral.objects.filter(promo__owner=request.user).select_related('new_user')
    total_referrals = referrals.count()
    active_referrals = referrals.filter(new_user__borlette__isnull=False).count()

    # Prepare referrals data for template with commission calculation
    referrals_data = []
    total_commission = 0
    active_commission = 0
    
    for ref in referrals:
        # Compter les agents du directeur
        try:
            director_borlette = ref.new_user.borlette
            agents_count = director_borlette.agents.count()
        except:
            agents_count = 0
        
        # Calculer la commission
        commission_calc = calculate_affiliate_commission(
            ref.created_at,
            agents_count
        )
        
        ref_data = {
            'username': ref.new_user.username,
            'email': ref.new_user.email,
            'created_at': ref.created_at,
            'has_borlette': hasattr(ref.new_user, 'borlette'),
            'agents_count': agents_count,
            'commission': commission_calc['total_commission'],
            'is_valid': commission_calc['is_valid'],
            'months_remaining': commission_calc['months_remaining'],
        }
        referrals_data.append(ref_data)
        
        total_commission += commission_calc['total_commission']
        if commission_calc['is_valid']:
            active_commission += commission_calc['total_commission']

    # Calculate totals
    total_commission = sum(r['commission'] for r in referrals_data)
    
    # Get user's promo code
    promo = PromoCode.objects.filter(owner=request.user).first()
    promo_code = promo.code if promo else "N/A"
    
    # Get withdrawal history (last 5)
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')[:5]
    total_withdrawn = sum(w.amount for w in WithdrawalRequest.objects.filter(
        user=request.user, 
        status=WithdrawalStatus.PAID
    ))
    pending_amount = sum(w.amount for w in WithdrawalRequest.objects.filter(
        user=request.user, 
        status=WithdrawalStatus.PENDING
    ))
    
    # Get affiliate profile
    affiliate_profile = request.user.affiliate_profile

    return render(
        request,
        "accounts/affiliate_dashboard.html",
        {
            "referrals": referrals_data,
            "total_referrals": len(referrals_data),
            "active_referrals": sum(1 for r in referrals_data if r['has_borlette']),
            "total_commission": total_commission,
            "commission_per_director": AFFILIATE_COMMISSIONS['activation'],
            "commission_per_agent": AFFILIATE_COMMISSIONS['per_agent'],
            "bonus_validity_months": BONUS_VALIDITY_MONTHS,
            "promo_code": promo_code,
            "active_commission": sum(r['commission'] for r in referrals_data if r['is_valid']),
            "withdrawals": withdrawals,
            "total_withdrawn": total_withdrawn,
            "pending_amount": pending_amount,
            "available_balance": affiliate_profile.available_balance,
        },
    )


@login_required
def affiliate_referrals_api(request: HttpRequest):
    """API endpoint pour récupérer les filleuls d'un affilié."""
    if request.user.role != UserRole.AFFILIATE:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    referrals = Referral.objects.filter(promo__owner=request.user).select_related('new_user')
    
    referrals_data = []
    for ref in referrals:
        referrals_data.append({
            'username': ref.new_user.username,
            'email': ref.new_user.email,
            'created_at': ref.created_at.isoformat(),
            'has_borlette': hasattr(ref.new_user, 'borlette')
        })

    return JsonResponse({
        'success': True,
        'referrals': referrals_data,
        'total_count': referrals.count(),
        'active_count': referrals.filter(new_user__borlette__isnull=False).count()
    })


@login_required
def affiliate_submit_result(request: HttpRequest):
    """API endpoint pour permettre aux affiliés de soumettre les résultats des tirages par défaut."""
    if request.user.role != UserRole.AFFILIATE:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # Vérifier si l'affilié a la permission de soumettre les résultats
    try:
        affiliate_profile = request.user.affiliate_profile
        if not affiliate_profile.can_submit_results:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except AffiliateProfile.DoesNotExist:
        return JsonResponse({'error': 'Affiliate profile not found'}, status=404)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    import json
    from django.core.validators import RegexValidator
    from django.core.exceptions import ValidationError
    from accounts.models import Resultat, Tirage
    from datetime import date

    try:
        data = json.loads(request.body)
        
        tirage_id = data.get('tirage_id')
        lot1 = data.get('lot1')
        lot2 = data.get('lot2')
        lot3 = data.get('lot3')
        chiffre_loto3 = data.get('chiffre_loto3', '0')
        result_date = data.get('date', date.today().isoformat())

        # Validation des lots
        lot_validator = RegexValidator(r'^\d{2}$', message='Lot doit être au format 00-99')
        chiffre_validator = RegexValidator(r'^\d$', message='Chiffre doit être 0-9')

        for lot in [lot1, lot2, lot3]:
            lot_validator(lot)

        chiffre_validator(chiffre_loto3)

        # Récupérer le tirage (doit être un tirage par défaut)
        try:
            tirage = Tirage.objects.get(id=tirage_id, is_default=True)
        except Tirage.DoesNotExist:
            return JsonResponse({'error': 'Tirage non trouvé ou non autorisé'}, status=400)

        # Créer le résultat
        resultat = Resultat.objects.create(
            tirage=tirage,
            date=result_date,
            lot1=lot1,
            lot2=lot2,
            lot3=lot3,
            chiffre_loto3=chiffre_loto3,
            source='AFFILIATE',
            validated_by=request.user,
            validated_at=timezone.now(),
            statut='validated'
        )

        return JsonResponse({
            'success': True,
            'message': 'Résultat soumis avec succès',
            'result_id': resultat.id
        })

    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def affiliate_withdrawals(request: HttpRequest):
    """Page des retraits pour l'affilié."""
    if request.user.role != UserRole.AFFILIATE:
        return redirect("/portal/login/")

    affiliate_profile = request.user.affiliate_profile
    
    # Get withdrawal history
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate stats
    total_withdrawn = sum(w.amount for w in withdrawals if w.status == WithdrawalStatus.PAID)
    pending_amount = sum(w.amount for w in withdrawals if w.status == WithdrawalStatus.PENDING)
    
    # Handle withdrawal request
    if request.method == 'POST':
        amount_str = request.POST.get('amount', '')
        try:
            amount = float(amount_str)
            if amount <= 0:
                messages.error(request, "Le montant doit être positif.")
            elif amount > affiliate_profile.available_balance:
                messages.error(request, "Solde insuffisant pour ce retrait.")
            else:
                # Create withdrawal request
                with transaction.atomic():
                    withdrawal = WithdrawalRequest.objects.create(
                        user=request.user,
                        amount=amount,
                        status=WithdrawalStatus.PENDING,
                        payment_method=affiliate_profile.payment_method,
                        payment_phone=affiliate_profile.payment_phone,
                        payment_full_name=affiliate_profile.payment_full_name,
                        payment_location=affiliate_profile.payment_location,
                    )
                    # Deduct from available balance
                    affiliate_profile.available_balance -= amount
                    affiliate_profile.save()
                    messages.success(request, f"Demande de retrait de {amount} GDS soumise avec succès. Traitement sous 48h.")
                    return redirect('affiliate:withdrawals')
        except ValueError:
            messages.error(request, "Montant invalide.")
    
    return render(request, "accounts/affiliate_withdrawals.html", {
        "withdrawals": withdrawals,
        "total_withdrawn": total_withdrawn,
        "pending_amount": pending_amount,
        "available_balance": affiliate_profile.available_balance,
        "payment_method": affiliate_profile.payment_method,
        "payment_phone": affiliate_profile.payment_phone,
        "payment_full_name": affiliate_profile.payment_full_name,
        "payment_location": affiliate_profile.payment_location,
    })


@login_required
def affiliate_referrals_list(request: HttpRequest):
    """Page de la liste des filleuls pour l'affilié."""
    if request.user.role != UserRole.AFFILIATE:
        return redirect("/portal/login/")

    referrals = Referral.objects.filter(promo__owner=request.user).select_related('new_user')
    
    referrals_data = []
    total_commission = 0
    
    for ref in referrals:
        try:
            director_borlette = ref.new_user.borlette
            agents_count = director_borlette.agents.count()
        except:
            agents_count = 0
        
        commission_calc = calculate_affiliate_commission(ref.created_at, agents_count)
        
        ref_data = {
            'username': ref.new_user.username,
            'email': ref.new_user.email,
            'created_at': ref.created_at,
            'has_borlette': hasattr(ref.new_user, 'borlette'),
            'agents_count': agents_count,
            'commission': commission_calc['total_commission'],
            'is_valid': commission_calc['is_valid'],
            'months_remaining': commission_calc['months_remaining'],
        }
        referrals_data.append(ref_data)
        total_commission += commission_calc['total_commission']
    
    return render(request, "accounts/affiliate_referrals.html", {
        "referrals": referrals_data,
        "total_referrals": len(referrals_data),
        "active_referrals": sum(1 for r in referrals_data if r['has_borlette']),
        "total_commission": total_commission,
    })


@login_required
def affiliate_settings(request: HttpRequest):
    """Page des paramètres pour l'affilié."""
    if request.user.role != UserRole.AFFILIATE:
        return redirect("/portal/login/")

    affiliate_profile = request.user.affiliate_profile
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', '')
        payment_phone = request.POST.get('payment_phone', '')
        payment_full_name = request.POST.get('payment_full_name', '')
        payment_location = request.POST.get('payment_location', '')
        
        affiliate_profile.payment_method = payment_method if payment_method else None
        affiliate_profile.payment_phone = payment_phone
        affiliate_profile.payment_full_name = payment_full_name
        affiliate_profile.payment_location = payment_location
        affiliate_profile.save()
        
        messages.success(request, "Informations de paiement mises à jour avec succès.")
        return redirect('affiliate:settings')
    
    return render(request, "accounts/affiliate_settings.html", {
        "profile": affiliate_profile,
        "promo_code": affiliate_profile.promo_code,
    })
