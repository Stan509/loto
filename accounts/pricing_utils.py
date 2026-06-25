"""
Utilitaires pour l'intégration des prix et commissions dans le flux de transaction.

Ce module fournit des fonctions pour:
1. Calculer le prix lors de l'inscription d'une borlette
2. Calculer et enregistrer les commissions pour les affiliés
3. Mettre à jour les soldes des affiliés
"""

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction as db_transaction

from .models import (
    FinancialTransaction, FinancialTransactionType, FinancialSplit, 
    FinancialSplitRole, PromoCode, Referral, WithdrawalRequest, WithdrawalStatus
)
from .pricing_config import (
    calculate_director_price,
    calculate_affiliate_commission,
    BASE_PRICES,
    DIRECTOR_DISCOUNTS,
    AFFILIATE_COMMISSIONS,
    BONUS_VALIDITY_MONTHS,
)


def create_activation_transaction(borlette, months: int = 1, 
                                   promo_code=None, agents_count: int = 0) -> FinancialTransaction:
    """
    Crée une transaction d'activation avec le calcul des prix appliqué.
    
    Args:
        borlette: Instance Borlette
        months: Nombre de mois d'activation (default: 1)
        promo_code: Instance PromoCode si un code promo est utilisé
        agents_count: Nombre d'agents enregistrés
        
    Returns:
        FinancialTransaction créée
    """
    has_promo = promo_code is not None
    
    # Calculer le prix
    price_calc = calculate_director_price(agents_count, has_promo)
    
    # Créer la transaction
    with db_transaction.atomic():
        financial_tx = FinancialTransaction.objects.create(
            borlette=borlette,
            promo_code=promo_code,
            type=FinancialTransactionType.ACTIVATION,
            total_amount=price_calc['total'],
            months_active=months,
            agents_count=agents_count,
            eligible_agents=agents_count,
        )
        
        # Créer les splits financiers
        # 1. Split pour le propriétaire (montant après réductions)
        owner_amount = price_calc['total']
        FinancialSplit.objects.create(
            transaction=financial_tx,
            user=borlette.user,
            role=FinancialSplitRole.OWNER,
            amount=owner_amount,
        )
        
        # 2. Si code promo affilié, créer un split pour l'affilié
        if promo_code and promo_code.owner.role == 'AFFILIATE':
            # Calculer la commission de l'affilié
            commission_calc = calculate_affiliate_commission(
                timezone.now(),  # Date d'inscription = maintenant
                agents_count
            )
            
            affiliate_commission = commission_calc['total_commission']
            
            if affiliate_commission > 0:
                FinancialSplit.objects.create(
                    transaction=financial_tx,
                    user=promo_code.owner,
                    role=FinancialSplitRole.AFFILIATE,
                    amount=affiliate_commission,
                )
                
                # Mettre à jour le solde de l'affilié (à implémenter selon votre logique)
                # update_affiliate_balance(promo_code.owner, affiliate_commission)
        
        return financial_tx


def calculate_subscription_amount(borlette, months: int = 1, 
                                   agents_count: int = None) -> Decimal:
    """
    Calcule le montant d'un abonnement (renouvellement).
    
    Args:
        borlette: Instance Borlette
        months: Nombre de mois
        agents_count: Nombre d'agents (si None, utilise agents.count())
        
    Returns:
        Montant total de l'abonnement
    """
    if agents_count is None:
        agents_count = borlette.agents.count()
    
    # Vérifier si la borlette a utilisé un code promo lors de l'inscription
    first_transaction = FinancialTransaction.objects.filter(
        borlette=borlette,
        type=FinancialTransactionType.ACTIVATION
    ).first()
    
    has_promo = first_transaction and first_transaction.promo_code is not None
    signup_date = first_transaction.created_at if first_transaction else borlette.user.date_joined
    
    # Calculer le prix
    price_calc = calculate_director_price(agents_count, has_promo, signup_date=signup_date)
    
    # Multiplier par le nombre de mois
    return price_calc['total'] * months


def get_affiliate_commission_summary(affiliate_user) -> dict:
    """
    Calcule le résumé des commissions pour un affilié.
    
    Args:
        affiliate_user: Instance User avec role AFFILIATE
        
    Returns:
        Dict avec les statistiques de commissions
    """
    # Récupérer tous les filleuls (directeurs qui ont utilisé le code promo de l'affilié)
    from .models import PromoCode, Referral
    
    # Récupérer le code promo de l'affilié
    try:
        promo_code = PromoCode.objects.get(owner=affiliate_user, is_active=True)
    except PromoCode.DoesNotExist:
        return {
            'total_referrals': 0,
            'total_commission': Decimal('0.00'),
            'active_commissions': Decimal('0.00'),
            'expired_commissions': Decimal('0.00'),
            'referrals': [],
        }
    
    # Récupérer tous les filleuls
    referrals = Referral.objects.filter(promo=promo_code).select_related('new_user')
    
    referred_directors = []
    for referral in referrals:
        # Compter les agents du directeur
        try:
            director_borlette = referral.new_user.borlette
            agents_count = director_borlette.agents.count()
        except:
            agents_count = 0
        
        referred_directors.append({
            'id': referral.new_user.id,
            'name': referral.new_user.username,
            'signup_date': referral.created_at,
            'agents_count': agents_count,
        })
    
    # Calculer les gains totaux
    from .pricing_config import calculate_affiliate_total_earnings
    result = calculate_affiliate_total_earnings(referred_directors)
    
    return {
        'total_referrals': result['total_directors'],
        'total_commission': result['total_earnings'],
        'active_commissions': result['total_earnings'],  # Commission en cours
        'expired_commissions': Decimal('0.00'),  # Commission expirée
        'active_directors': result['active_directors'],
        'expired_directors': result['expired_directors'],
        'referrals': result['directors_details'],
    }


def get_director_savings_info(borlette) -> dict:
    """
    Retourne les informations de réduction pour un directeur.
    
    Args:
        borlette: Instance Borlette
        
    Returns:
        Dict avec les informations de réduction
    """
    # Vérifier si le directeur a utilisé un code promo
    first_transaction = FinancialTransaction.objects.filter(
        borlette=borlette,
        type=FinancialTransactionType.ACTIVATION
    ).first()
    
    has_promo = first_transaction and first_transaction.promo_code is not None
    signup_date = first_transaction.created_at if first_transaction else borlette.user.date_joined
    
    agents_count = borlette.agents.count()
    
    # Calculer le prix avec et sans promo
    price_without_promo = calculate_director_price(agents_count, False)
    price_with_promo = calculate_director_price(agents_count, True, signup_date=signup_date)
    
    is_within_6_months = price_with_promo['is_within_6_months']
    
    return {
        'has_promo_code': has_promo,
        'is_within_6_months': is_within_6_months,
        'agents_count': agents_count,
        'base_price': price_without_promo['total'],
        'discounted_price': price_with_promo['total'] if has_promo else price_without_promo['total'],
        'total_savings': price_without_promo['total'] - price_with_promo['total'] if has_promo else Decimal('0.00'),
        'activation_savings': DIRECTOR_DISCOUNTS['activation'] if has_promo else Decimal('0.00'),
        'per_agent_savings': DIRECTOR_DISCOUNTS['per_agent'] if (has_promo and is_within_6_months) else Decimal('0.00'),
        'total_agent_savings': (DIRECTOR_DISCOUNTS['per_agent'] * agents_count) if (has_promo and is_within_6_months) else Decimal('0.00'),
    }


# ============================================================================
# FONCTIONS POUR LE LANDING PAGE
# ============================================================================


def get_pricing_context_for_template() -> dict:
    """
    Retourne le contexte pour les templates (landing page, etc.)
    
    Returns:
        Dict avec toutes les informations de prix formatées
    """
    from .pricing_config import get_pricing_summary, get_example_calculations
    
    pricing = get_pricing_summary()
    examples = get_example_calculations()
    
    return {
        'pricing': pricing,
        'examples': examples,
        'activation_price': pricing['activation']['amount'],
        'agent_price': pricing['agent']['amount'],
        'affiliate_discount_activation': pricing['affiliate_discount']['activation'],
        'affiliate_discount_per_agent': pricing['affiliate_discount']['per_agent'],
        'affiliate_earning_per_director': pricing['affiliate_earnings']['per_director'],
        'affiliate_earning_per_agent': pricing['affiliate_earnings']['per_agent'],
        'bonus_validity_months': pricing['affiliate_earnings']['validity_months'],
    }
