"""
API endpoints for Phase J - Mariage Risk Management
"""
import json
from itertools import permutations

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from accounts.models import (
    Tirage, 
    TirageNumeroStats, 
    MariageBlock,
    AuditAction,
)


def _get_blocked_boules(tirage_id: int) -> set:
    """Get set of blocked boules (both auto and admin blocked) for a tirage."""
    stats = TirageNumeroStats.objects.filter(
        tirage_id=tirage_id
    )
    return {
        s.numero for s in stats 
        if s.bloque_admin or s.bloque_auto
    }


def _get_auto_mariage_blocks(tirage_id: int) -> set:
    """
    Calculate auto-derived mariage blocks from blocked boules.
    Returns set of normalized tuples (a, b) where a < b.
    """
    blocked_boules = _get_blocked_boules(tirage_id)
    if len(blocked_boules) < 2:
        return set()
    
    # Generate all ordered pairs (permutations of 2)
    auto_blocks = set()
    for a, b in permutations(blocked_boules, 2):
        # Normalize: store with smaller first
        if int(a) < int(b):
            auto_blocks.add((a, b))
        else:
            auto_blocks.add((b, a))
    return auto_blocks


def _parse_combo(combo_str: str) -> tuple:
    """Parse '44x30' into ('44', '30') normalized."""
    parts = combo_str.lower().replace('x', '|').split('|')
    if len(parts) != 2:
        return None
    a, b = parts[0].strip(), parts[1].strip()
    # Validate format
    if not (a.isdigit() and b.isdigit() and len(a) <= 2 and len(b) <= 2):
        return None
    # Pad with zeros
    a = a.zfill(2)
    b = b.zfill(2)
    # Normalize order
    if int(a) > int(b):
        a, b = b, a
    return (a, b)


@login_required
@require_http_methods(["GET"])
def api_mariage_blocks_list(request, tirage_id: int):
    """
    GET /portal/api/tirages/<id>/mariage-blocks/
    
    Returns:
    {
        "manual": ["44x30", "33x12"],
        "auto": ["44x33", "33x44", "44x30", "30x44"],
        "all": [
            {"combo":"44x30","source":"BOTH"},
            {"combo":"33x44","source":"AUTO"}
        ]
    }
    """
    user = request.user
    if not hasattr(user, 'borlette'):
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
    
    # Verify tirage belongs to user's borlette
    try:
        tirage = Tirage.objects.get(id=tirage_id, borlette=user.borlette)
    except Tirage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Tirage not found"}, status=404)
    
    # Get manual blocks
    manual_blocks = MariageBlock.get_blocked_combos(tirage_id)
    manual_display = sorted([f"{a}x{b}" for a, b in manual_blocks])
    
    # Get auto blocks from blocked boules
    auto_blocks = _get_auto_mariage_blocks(tirage_id)
    auto_display = sorted([f"{a}x{b}" for a, b in auto_blocks])
    
    # Build combined list with source
    all_combos = {}
    
    # Add manual blocks
    for combo in manual_blocks:
        combo_str = f"{combo[0]}x{combo[1]}"
        all_combos[combo_str] = "MANUAL"
    
    # Add auto blocks (mark as BOTH if also manual)
    for combo in auto_blocks:
        combo_str = f"{combo[0]}x{combo[1]}"
        if combo_str in all_combos:
            all_combos[combo_str] = "BOTH"
        else:
            all_combos[combo_str] = "AUTO"
    
    # Sort combined list
    all_list = [
        {"combo": k, "source": v}
        for k, v in sorted(all_combos.items())
    ]
    
    return JsonResponse({
        "success": True,
        "tirage_id": tirage_id,
        "tirage_name": tirage.nom,
        "manual": manual_display,
        "auto": auto_display,
        "all": all_list,
    })


@login_required
@require_http_methods(["POST"])
def api_mariage_block_add(request, tirage_id: int):
    """
    POST /portal/api/tirages/<id>/mariage-blocks/
    
    Body: {"combo": "44x30"}
    
    Adds a manual mariage block.
    """
    user = request.user
    if not hasattr(user, 'borlette'):
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
    
    # Verify tirage
    try:
        tirage = Tirage.objects.get(id=tirage_id, borlette=user.borlette)
    except Tirage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Tirage not found"}, status=404)
    
    # Parse request body
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    
    combo_str = payload.get("combo", "").strip()
    if not combo_str:
        return JsonResponse({"success": False, "error": "Missing combo"}, status=400)
    
    # Parse and validate combo
    parsed = _parse_combo(combo_str)
    if not parsed:
        return JsonResponse({"success": False, "error": "Invalid combo format"}, status=400)
    
    a, b = parsed
    
    # Check if already blocked manually
    if MariageBlock.is_blocked(tirage_id, a, b):
        return JsonResponse({
            "success": False, 
            "error": "Combo already blocked manually",
            "combo": f"{a}x{b}"
        }, status=409)
    
    # Create block
    block = MariageBlock.objects.create(
        tirage=tirage,
        boule_a=int(a),
        boule_b=int(b),
        created_by=user
    )
    
    # Log audit
    from accounts.audit import log_audit
    log_audit(
        action=AuditAction.RISK_BLOCK_ADD,
        entity_type="MariageBlock",
        entity_id=str(block.id),
        borlette=user.borlette,
        actor_user=user,
        request=request,
        meta={
            "tirage_id": tirage_id,
            "tirage_name": tirage.nom,
            "combo": f"{a}x{b}",
            "boule_a": a,
            "boule_b": b,
            "source": "MANUAL"
        },
    )
    
    return JsonResponse({
        "success": True,
        "combo": f"{a}x{b}",
        "message": f"Mariage {a}x{b} bloqué manuellement"
    })


@login_required
@require_http_methods(["DELETE"])
def api_mariage_block_remove(request, tirage_id: int):
    """
    DELETE /portal/api/tirages/<id>/mariage-blocks/?combo=44x30
    
    Removes a manual mariage block.
    """
    user = request.user
    if not hasattr(user, 'borlette'):
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
    
    # Verify tirage
    try:
        tirage = Tirage.objects.get(id=tirage_id, borlette=user.borlette)
    except Tirage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Tirage not found"}, status=404)
    
    # Get combo from query params
    combo_str = request.GET.get("combo", "").strip()
    if not combo_str:
        return JsonResponse({"success": False, "error": "Missing combo parameter"}, status=400)
    
    # Parse combo
    parsed = _parse_combo(combo_str)
    if not parsed:
        return JsonResponse({"success": False, "error": "Invalid combo format"}, status=400)
    
    a, b = parsed
    
    # Find and delete block
    try:
        block = MariageBlock.objects.get(
            tirage=tirage,
            boule_a=int(a),
            boule_b=int(b)
        )
        block.delete()
        
        # Log audit
        from accounts.audit import log_audit
        log_audit(
            action=AuditAction.RISK_BLOCK_REMOVE,
            entity_type="MariageBlock",
            entity_id=f"{tirage_id}:{a}x{b}",
            borlette=user.borlette,
            actor_user=user,
            request=request,
            meta={
                "tirage_id": tirage_id,
                "tirage_name": tirage.nom,
                "combo": f"{a}x{b}",
                "boule_a": a,
                "boule_b": b,
            },
        )
        
        return JsonResponse({
            "success": True,
            "combo": f"{a}x{b}",
            "message": f"Blocage manuel {a}x{b} supprimé"
        })
        
    except MariageBlock.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Manual block not found",
            "combo": f"{a}x{b}"
        }, status=404)


def is_mariage_blocked(tirage_id: int, combo_str: str) -> tuple:
    """
    Check if a mariage combo is blocked (for ticket validation).
    
    Returns: (is_blocked: bool, source: str)
    source can be: "MANUAL", "AUTO", "BOTH", or None
    """
    parsed = _parse_combo(combo_str)
    if not parsed:
        return (False, None)
    
    a, b = parsed
    
    # Check manual block
    is_manual = MariageBlock.is_blocked(tirage_id, a, b)
    
    # Check auto block (derived from blocked boules)
    auto_blocks = _get_auto_mariage_blocks(tirage_id)
    is_auto = (a, b) in auto_blocks
    
    if is_manual and is_auto:
        return (True, "BOTH")
    elif is_manual:
        return (True, "MANUAL")
    elif is_auto:
        return (True, "AUTO")
    else:
        return (False, None)
