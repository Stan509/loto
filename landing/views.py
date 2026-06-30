from django.http import HttpRequest
from django.shortcuts import render
from django.core.paginator import Paginator
from accounts.models import DocumentationVideo


def index(request: HttpRequest):
    from accounts.models import Tirage, Resultat, TirageStatus
    
    active_tirages = Tirage.objects.filter(statut=TirageStatus.ACTIF).order_by('ordre_affichage', 'nom')
    
    draw_results = []
    for tirage in active_tirages:
        results = Resultat.objects.filter(
            tirage=tirage
        ).order_by("-date", "-created_at")[:10]
        
        draw_results.append({
            "tirage": tirage,
            "results": results,
            "has_results": results.exists()
        })
        
    return render(request, "landing/index.html", {
        "draw_results": draw_results
    })


def documentation(request: HttpRequest):
    """Page de documentation avec vidéos YouTube intégrées par catégorie."""
    videos = DocumentationVideo.objects.filter(is_active=True).order_by('order', 'created_at')
    
    # Organiser les vidéos par catégorie
    intro_videos = videos.filter(category__iexact='Introduction')
    config_videos = videos.filter(category__iexact='Configuration')
    admin_videos = videos.filter(category__iexact='Admin Borlette') | videos.filter(category__iexact='Admin Borlettes')
    agents_videos = videos.filter(category__iexact='Agents')
    affiliate_videos = videos.filter(category__iexact='Affiliation') | videos.filter(category__iexact='Affiliés')
    resume_videos = videos.filter(category__iexact='Résumé') | videos.filter(category__iexact='Resume')
    
    return render(request, "landing/documentation.html", {
        'intro_videos': intro_videos.order_by('order', 'created_at'),
        'config_videos': config_videos.order_by('order', 'created_at'),
        'admin_videos': admin_videos.order_by('order', 'created_at'),
        'agents_videos': agents_videos.order_by('order', 'created_at'),
        'affiliate_videos': affiliate_videos.order_by('order', 'created_at'),
        'resume_videos': resume_videos.order_by('order', 'created_at'),
    })
