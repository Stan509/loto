"""
API endpoints pour les calculs de prix et commissions.
"""

import json
from decimal import Decimal
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .pricing_config import (
    calculate_director_price,
    calculate_affiliate_commission,
    calculate_affiliate_total_earnings,
    get_pricing_summary,
    get_example_calculations,
)


class DecimalEncoder(json.JSONEncoder):
    """Encoder pour gérer les Decimal dans JSON."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def json_response(data, status=200):
    """Retourne une réponse JSON avec l'encoder Decimal."""
    return JsonResponse(data, encoder=DecimalEncoder, status=status)


@require_http_methods(["GET"])
def pricing_summary_api(request):
    """
    API pour obtenir le résumé des prix.
    
    GET /api/pricing/summary/
    
    Response:
    {
        "activation": {"amount": 12500.00, "currency": "GDS", "period": "mois"},
        "agent": {"amount": 1250.00, "currency": "GDS", "period": "mois"},
        "affiliate_discount": {"activation": 2500.00, "per_agent": 50.00},
        "affiliate_earnings": {"per_director": 2000.00, "per_agent": 200.00, "validity_months": 6}
    }
    """
    return json_response({
        "success": True,
        "data": get_pricing_summary()
    })


@require_http_methods(["GET"])
def calculate_price_api(request):
    """
    API pour calculer le prix pour un directeur.
    
    GET /api/pricing/calculate/?agents_count=10&has_promo_code=true
    
    Params:
        agents_count: Nombre d'agents (int)
        has_promo_code: True si code promo utilisé (bool)
        
    Response:
    {
        "success": true,
        "data": {
            "base_activation": 12500.00,
            "base_agents": 12500.00,
            "base_total": 25000.00,
            "discount_activation": 2500.00,
            "discount_agents": 500.00,
            "total_discount": 3000.00,
            "total_activation": 10000.00,
            "total_agents": 12000.00,
            "total": 22000.00,
            "has_promo_code": true,
            "agents_count": 10
        }
    }
    """
    try:
        agents_count = int(request.GET.get('agents_count', 0))
        has_promo_code = request.GET.get('has_promo_code', 'false').lower() == 'true'
        
        if agents_count < 0:
            return json_response({
                "success": False,
                "error": "agents_count doit être >= 0"
            }, status=400)
        
        result = calculate_director_price(agents_count, has_promo_code)
        
        return json_response({
            "success": True,
            "data": result
        })
        
    except ValueError as e:
        return json_response({
            "success": False,
            "error": f"Paramètre invalide: {str(e)}"
        }, status=400)


@require_http_methods(["GET"])
def example_calculations_api(request):
    """
    API pour obtenir des exemples de calculs.
    
    GET /api/pricing/examples/
    
    Response:
    {
        "success": true,
        "data": {
            "without_promo": {...},
            "with_promo": {...},
            "savings": {...},
            "affiliate_earnings": {...}
        }
    }
    """
    return json_response({
        "success": True,
        "data": get_example_calculations()
    })


@csrf_exempt
@require_http_methods(["POST"])
def calculate_affiliate_commission_api(request):
    """
    API pour calculer la commission d'un affilié.
    
    POST /api/pricing/affiliate-commission/
    
    Body:
    {
        "director_signup_date": "2026-01-15T10:30:00",
        "agents_count": 10
    }
    
    Response:
    {
        "success": true,
        "data": {
            "activation_commission": 2000.00,
            "agents_commission": 2000.00,
            "total_commission": 4000.00,
            "is_valid": true,
            "months_remaining": 5,
            "validity_end_date": "2026-07-15T10:30:00",
            "director_signup_date": "2026-01-15T10:30:00",
            "agents_count": 10
        }
    }
    """
    try:
        data = json.loads(request.body)
        
        director_signup_date = datetime.fromisoformat(data.get('director_signup_date'))
        agents_count = int(data.get('agents_count', 0))
        
        if agents_count < 0:
            return json_response({
                "success": False,
                "error": "agents_count doit être >= 0"
            }, status=400)
        
        result = calculate_affiliate_commission(director_signup_date, agents_count)
        
        return json_response({
            "success": True,
            "data": result
        })
        
    except (ValueError, TypeError) as e:
        return json_response({
            "success": False,
            "error": f"Paramètre invalide: {str(e)}"
        }, status=400)
    except json.JSONDecodeError:
        return json_response({
            "success": False,
            "error": "JSON invalide"
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def calculate_affiliate_total_api(request):
    """
    API pour calculer les gains totaux d'un affilié.
    
    POST /api/pricing/affiliate-total/
    
    Body:
    {
        "referred_directors": [
            {"id": 1, "signup_date": "2026-01-15T10:30:00", "agents_count": 10},
            {"id": 2, "signup_date": "2026-02-01T14:00:00", "agents_count": 5}
        ]
    }
    
    Response:
    {
        "success": true,
        "data": {
            "total_activation_commissions": 4000.00,
            "total_agents_commissions": 3000.00,
            "total_earnings": 7000.00,
            "active_directors": 2,
            "expired_directors": 0,
            "total_directors": 2,
            "directors_details": [...]
        }
    }
    """
    try:
        data = json.loads(request.body)
        referred_directors = data.get('referred_directors', [])
        
        # Convertir les dates string en datetime
        for director in referred_directors:
            if isinstance(director.get('signup_date'), str):
                director['signup_date'] = datetime.fromisoformat(director['signup_date'])
        
        result = calculate_affiliate_total_earnings(referred_directors)
        
        return json_response({
            "success": True,
            "data": result
        })
        
    except (ValueError, TypeError) as e:
        return json_response({
            "success": False,
            "error": f"Paramètre invalide: {str(e)}"
        }, status=400)
    except json.JSONDecodeError:
        return json_response({
            "success": False,
            "error": "JSON invalide"
        }, status=400)
