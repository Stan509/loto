"""
Configuration des prix et commission pour le programme d'affiliation Gaboom.

Prix de base:
- Activation: 12,500 GDS pour 1 mois
- Agent enregistré: 1,250 GDS par agent

Programme d'affiliation:
- Directeur avec code promo affilié obtient:
  * Réduction de 2,500 GDS sur l'activation
  * Réduction de 50 GDS par agent enregistré
  
- Affilié obtient:
  * 2,000 GDS sur l'activation de chaque directeur
  * 200 GDS sur chaque agent de chaque directeur
  
- Bonus valable pendant 6 mois après l'inscription du directeur
"""

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

# ============================================================================
# PRIX DE BASE (en GDS)
# ============================================================================

BASE_PRICES = {
    'activation': Decimal('12500.00'),  # 12,500 GDS pour 1 mois
    'agent_monthly': Decimal('1250.00'),  # 1,250 GDS par agent par mois
}

# ============================================================================
# RÉDUCTIONS POUR DIRECTEURS AVEC CODE PROMO (en GDS)
# ============================================================================

DIRECTOR_DISCOUNTS = {
    'activation': Decimal('500.00'),   # Réduction de 500 GDS sur activation (12500 - 500 = 12000 GDS)
    'per_agent': Decimal('50.00'),     # Réduction de 50 GDS par agent (1250 - 50 = 1200 GDS)
}

# ============================================================================
# COMMISSIONS POUR AFFILIÉS (en GDS)
# ============================================================================

AFFILIATE_COMMISSIONS = {
    'activation': Decimal('2000.00'),  # 2,000 GDS sur activation du directeur
    'per_agent': Decimal('200.00'),    # 200 GDS par agent du directeur
}

# ============================================================================
# DURÉE DE VALIDITÉ DES BONUS (en mois)
# ============================================================================

BONUS_VALIDITY_MONTHS = 6

# ============================================================================
# FONCTIONS DE CALCUL
# ============================================================================


def calculate_director_price(agents_count: int, has_promo_code: bool = False, signup_date=None, current_date=None) -> dict:
    """
    Calcule le prix pour un directeur avec ou sans code promo.
    
    Args:
        agents_count: Nombre d'agents enregistrés
        has_promo_code: True si le directeur utilise un code promo affilié
        signup_date: Date d'inscription du directeur
        current_date: Date actuelle du calcul
        
    Returns:
        Dict avec les détails du prix:
        - base_activation: Prix de base de l'activation
        - base_agents: Prix de base pour les agents
        - discount_activation: Réduction sur l'activation
        - discount_agents: Réduction sur les agents
        - total_activation: Prix final de l'activation
        - total_agents: Prix final pour les agents
        - total: Prix total à payer
        - is_within_6_months: True si la réduction est encore valide
    """
    if current_date is None:
        current_date = timezone.now()
        
    is_within_6_months = True
    if has_promo_code and signup_date is not None:
        validity_end = signup_date + timedelta(days=30 * BONUS_VALIDITY_MONTHS)
        is_within_6_months = current_date <= validity_end

    base_activation = BASE_PRICES['activation']
    base_agents = BASE_PRICES['agent_monthly'] * agents_count
    
    if has_promo_code:
        discount_activation = DIRECTOR_DISCOUNTS['activation']
        if is_within_6_months:
            discount_agents = DIRECTOR_DISCOUNTS['per_agent'] * agents_count
        else:
            discount_agents = Decimal('0.00')
    else:
        discount_activation = Decimal('0.00')
        discount_agents = Decimal('0.00')
    
    total_activation = base_activation - discount_activation
    total_agents = base_agents - discount_agents
    
    return {
        'base_activation': base_activation,
        'base_agents': base_agents,
        'base_total': base_activation + base_agents,
        'discount_activation': discount_activation,
        'discount_agents': discount_agents,
        'total_discount': discount_activation + discount_agents,
        'total_activation': max(total_activation, Decimal('0.00')),
        'total_agents': max(total_agents, Decimal('0.00')),
        'total': max(total_activation + total_agents, Decimal('0.00')),
        'has_promo_code': has_promo_code,
        'is_within_6_months': is_within_6_months,
        'agents_count': agents_count,
    }


def calculate_affiliate_commission(director_signup_date, agents_count: int, 
                                    current_date=None) -> dict:
    """
    Calcule la commission pour un affilié sur un directeur référé.
    
    Args:
        director_signup_date: Date d'inscription du directeur
        agents_count: Nombre d'agents actuels du directeur
        current_date: Date de calcul (default: aujourd'hui)
        
    Returns:
        Dict avec les détails de la commission:
        - activation_commission: Commission sur l'activation
        - agents_commission: Commission sur les agents
        - total_commission: Commission totale
        - is_valid: True si la période de bonus est encore valide
        - months_remaining: Mois restants dans la période de bonus
        - director_signup_date: Date d'inscription du directeur
    """
    if current_date is None:
        current_date = timezone.now()
    
    # Calculer la date de fin de validité
    validity_end = director_signup_date + timedelta(days=30 * BONUS_VALIDITY_MONTHS)
    
    # Vérifier si la période est encore valide
    is_valid = current_date <= validity_end
    
    # Calculer les mois restants
    if is_valid:
        days_remaining = (validity_end - current_date).days
        months_remaining = max(0, days_remaining // 30)
    else:
        months_remaining = 0
    
    if is_valid:
        activation_commission = AFFILIATE_COMMISSIONS['activation']
        agents_commission = AFFILIATE_COMMISSIONS['per_agent'] * agents_count
    else:
        activation_commission = Decimal('0.00')
        agents_commission = Decimal('0.00')
    
    return {
        'activation_commission': activation_commission,
        'agents_commission': agents_commission,
        'total_commission': activation_commission + agents_commission,
        'is_valid': is_valid,
        'months_remaining': months_remaining,
        'validity_end_date': validity_end,
        'director_signup_date': director_signup_date,
        'agents_count': agents_count,
    }


def calculate_affiliate_total_earnings(referred_directors: list) -> dict:
    """
    Calcule les gains totaux d'un affilié pour tous ses filleuls.
    
    Args:
        referred_directors: Liste de dicts avec 'signup_date' et 'agents_count'
        
    Returns:
        Dict avec:
        - total_activation_commissions: Total des commissions d'activation
        - total_agents_commissions: Total des commissions sur agents
        - total_earnings: Gains totaux
        - active_directors: Nombre de directeurs avec bonus encore valide
        - expired_directors: Nombre de directeurs avec bonus expiré
        - directors_details: Détails par directeur
    """
    total_activation = Decimal('0.00')
    total_agents = Decimal('0.00')
    active_count = 0
    expired_count = 0
    details = []
    
    for director in referred_directors:
        commission = calculate_affiliate_commission(
            director['signup_date'],
            director['agents_count']
        )
        
        total_activation += commission['activation_commission']
        total_agents += commission['agents_commission']
        
        if commission['is_valid']:
            active_count += 1
        else:
            expired_count += 1
        
        details.append({
            'director_id': director.get('id'),
            'director_name': director.get('name'),
            'commission': commission,
        })
    
    return {
        'total_activation_commissions': total_activation,
        'total_agents_commissions': total_agents,
        'total_earnings': total_activation + total_agents,
        'active_directors': active_count,
        'expired_directors': expired_count,
        'total_directors': len(referred_directors),
        'directors_details': details,
    }


# ============================================================================
# FONCTIONS POUR LE LANDING PAGE
# ============================================================================


def get_pricing_summary() -> dict:
    """
    Retourne un résumé des prix pour affichage sur le landing page.
    """
    return {
        'activation': {
            'amount': BASE_PRICES['activation'],
            'currency': 'GDS',
            'period': 'mois',
        },
        'agent': {
            'amount': BASE_PRICES['agent_monthly'],
            'currency': 'GDS',
            'period': 'mois',
        },
        'affiliate_discount': {
            'activation': DIRECTOR_DISCOUNTS['activation'],
            'per_agent': DIRECTOR_DISCOUNTS['per_agent'],
        },
        'affiliate_earnings': {
            'per_director': AFFILIATE_COMMISSIONS['activation'],
            'per_agent': AFFILIATE_COMMISSIONS['per_agent'],
            'validity_months': BONUS_VALIDITY_MONTHS,
        },
    }


def get_example_calculations() -> dict:
    """
    Retourne des exemples de calculs pour le landing page.
    """
    # Exemple 1: Directeur sans code promo, 10 agents
    example_no_promo = calculate_director_price(agents_count=10, has_promo_code=False)
    
    # Exemple 2: Directeur avec code promo, 10 agents
    example_with_promo = calculate_director_price(agents_count=10, has_promo_code=True)
    
    # Exemple 3: Gains de l'affilié pour ce directeur
    from datetime import datetime
    example_date = timezone.now() - timedelta(days=30)  # Inscrit il y a 1 mois
    example_affiliate = calculate_affiliate_commission(example_date, agents_count=10)
    
    return {
        'without_promo': example_no_promo,
        'with_promo': example_with_promo,
        'savings': {
            'activation': example_no_promo['total_activation'] - example_with_promo['total_activation'],
            'agents': example_no_promo['total_agents'] - example_with_promo['total_agents'],
            'total': example_no_promo['total'] - example_with_promo['total'],
        },
        'affiliate_earnings': example_affiliate,
    }
