"""Admin views for managing partners."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import UserRole, PartnerProfile, Borlette

User = get_user_model()


@staff_member_required
def admin_partner_list(request: HttpRequest):
    """Admin view to list all partners."""
    partners = PartnerProfile.objects.select_related('user').order_by('-created_at')
    
    return render(request, "admin_portal/partner_list.html", {
        "partners": partners,
    })


@staff_member_required
def admin_create_partner(request: HttpRequest):
    """Admin view to create a new partner."""
    borlettes = Borlette.objects.filter(is_active=True)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        # Permissions
        can_submit_results = request.POST.get('can_submit_results') == 'on'
        can_confirm_affiliate_payments = request.POST.get('can_confirm_affiliate_payments') == 'on'
        can_renew_subscriptions = request.POST.get('can_renew_subscriptions') == 'on'
        
        # Allowed borlettes
        allowed_borlette_ids = request.POST.getlist('allowed_borlettes')
        
        try:
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=UserRole.PARTNER,
                )
                
                # Create partner profile
                partner_profile = PartnerProfile.objects.create(
                    user=user,
                    can_submit_results=can_submit_results,
                    can_confirm_affiliate_payments=can_confirm_affiliate_payments,
                    can_renew_subscriptions=can_renew_subscriptions,
                )
                
                # Set allowed borlettes
                if allowed_borlette_ids:
                    partner_profile.allowed_borlettes.set(allowed_borlette_ids)
                
                messages.success(
                    request, 
                    f"Partenaire '{username}' créé avec succès. "
                    f"Permissions: Résultats={can_submit_results}, "
                    f"Paiements={can_confirm_affiliate_payments}, "
                    f"Renouvellements={can_renew_subscriptions}"
                )
                
                return redirect('admin_portal:partner_list')
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la création: {str(e)}")
    
    return render(request, "admin_portal/create_partner.html", {
        "borlettes": borlettes,
    })


@staff_member_required
def admin_edit_partner(request: HttpRequest, partner_id: int):
    """Admin view to edit a partner."""
    partner_profile = get_object_or_404(PartnerProfile, id=partner_id)
    borlettes = Borlette.objects.filter(is_active=True)
    
    if request.method == 'POST':
        # Update permissions
        partner_profile.can_submit_results = request.POST.get('can_submit_results') == 'on'
        partner_profile.can_confirm_affiliate_payments = request.POST.get('can_confirm_affiliate_payments') == 'on'
        partner_profile.can_renew_subscriptions = request.POST.get('can_renew_subscriptions') == 'on'
        partner_profile.is_active = request.POST.get('is_active') == 'on'
        
        # Update allowed borlettes
        allowed_borlette_ids = request.POST.getlist('allowed_borlettes')
        partner_profile.allowed_borlettes.set(allowed_borlette_ids)
        
        partner_profile.save()
        
        # Update user info
        user = partner_profile.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.is_active = partner_profile.is_active
        user.save()
        
        # Update password if provided
        new_password = request.POST.get('password', '')
        if new_password:
            user.set_password(new_password)
            user.save()
        
        messages.success(request, f"Partenaire '{user.username}' mis à jour avec succès.")
        return redirect('admin_portal:partner_list')
    
    return render(request, "admin_portal/edit_partner.html", {
        "partner": partner_profile,
        "borlettes": borlettes,
    })


@staff_member_required
def admin_toggle_partner(request: HttpRequest, partner_id: int):
    """Admin view to activate/deactivate a partner."""
    partner_profile = get_object_or_404(PartnerProfile, id=partner_id)
    
    partner_profile.is_active = not partner_profile.is_active
    partner_profile.save()
    
    partner_profile.user.is_active = partner_profile.is_active
    partner_profile.user.save()
    
    status = "activé" if partner_profile.is_active else "désactivé"
    messages.success(request, f"Partenaire '{partner_profile.user.username}' {status}.")
    
    return redirect('admin_portal:partner_list')


@staff_member_required
def admin_delete_partner(request: HttpRequest, partner_id: int):
    """Admin view to delete a partner."""
    partner_profile = get_object_or_404(PartnerProfile, id=partner_id)
    
    if request.method == 'POST':
        username = partner_profile.user.username
        partner_profile.user.delete()  # This will cascade delete the profile
        messages.success(request, f"Partenaire '{username}' supprimé.")
        return redirect('admin_portal:partner_list')
    
    return render(request, "admin_portal/delete_partner.html", {
        "partner": partner_profile,
    })
