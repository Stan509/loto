from django.db import migrations

def seed_documentation_videos(apps, schema_editor):
    DocumentationVideo = apps.get_model('accounts', 'DocumentationVideo')
    
    # Clean up existing default videos to avoid duplicates
    DocumentationVideo.objects.all().delete()
    
    videos = [
        # Section 1: Introduction
        {
            "title": "Inscription sur ordinateur et tablette",
            "youtube_url": "https://youtu.be/QQob922IHDU",
            "youtube_video_id": "QQob922IHDU",
            "description": "Apprenez à vous inscrire facilement sur la plateforme Central Borlette en utilisant votre ordinateur ou votre tablette.",
            "category": "Introduction",
            "order": 1,
            "is_active": True
        },
        {
            "title": "Inscription sur mobile",
            "youtube_url": "https://youtu.be/I0kUzVDbwzA",
            "youtube_video_id": "I0kUzVDbwzA",
            "description": "Découvrez le guide complet d'inscription adapté spécialement aux téléphones et appareils mobiles.",
            "category": "Introduction",
            "order": 2,
            "is_active": True
        },
        
        # Section 2: Configuration
        {
            "title": "Configuration",
            "youtube_url": "https://youtu.be/X0lUS2znHJE",
            "youtube_video_id": "X0lUS2znHJE",
            "description": "Guide complet sur la configuration initiale de votre borlette, y compris les taux de lot, les banques et les options système.",
            "category": "Configuration",
            "order": 1,
            "is_active": True
        },
        
        # Section 3: Admin Borlette
        {
            "title": "Gestion de tirages et de risque",
            "youtube_url": "https://youtu.be/CyDR_gsf8M4",
            "youtube_video_id": "CyDR_gsf8M4",
            "description": "Maîtrisez la gestion des tirages en cours et la configuration avancée du contrôle des risques (limites et blocages de boules).",
            "category": "Admin Borlette",
            "order": 2,
            "is_active": True
        },
        {
            "title": "Création et gestion des équipes avec permissions",
            "youtube_url": "https://youtu.be/NsaZiTtXeBM",
            "youtube_video_id": "NsaZiTtXeBM",
            "description": "Apprenez à ajouter des collaborateurs dans votre équipe administrative et à configurer précisément leurs droits d'accès.",
            "category": "Admin Borlette",
            "order": 3,
            "is_active": True
        },
        
        # Section 4: Agents
        {
            "title": "Création d'agents depuis le dashboard par le directeur",
            "youtube_url": "https://youtu.be/Iduo3-o48vc",
            "youtube_video_id": "Iduo3-o48vc",
            "description": "Procédure pas-à-pas pour créer, configurer et activer un nouvel agent de vente depuis le tableau de bord directeur.",
            "category": "Agents",
            "order": 1,
            "is_active": True
        },
        {
            "title": "Gestion des agents de vente",
            "youtube_url": "https://youtu.be/z58k476R_sg",
            "youtube_video_id": "z58k476R_sg",
            "description": "Suivi des caisses, ajustement des commissions, dépôts et retraits d'espèces pour le contrôle financier de vos agents.",
            "category": "Agents",
            "order": 2,
            "is_active": True
        },
        {
            "title": "Installation des postes de ventes, configuration et comment vendre avec le POS",
            "youtube_url": "https://youtu.be/YN602--VzdU",
            "youtube_video_id": "YN602--VzdU",
            "description": "Guide d'installation de l'application POS mobile, couplage de l'imprimante Bluetooth, et tutoriel complet sur la vente de tickets.",
            "category": "Agents",
            "order": 3,
            "is_active": True
        },
        
        # Section 5: Affiliation
        {
            "title": "Affiliation et Parrainage",
            "youtube_url": "https://youtu.be/wN6p1ArKa-c",
            "youtube_video_id": "wN6p1ArKa-c",
            "description": "Comprendre le programme d'affiliation : génération de code promo, suivi des filleuls et gains de commissions passives.",
            "category": "Affiliation",
            "order": 1,
            "is_active": True
        }
    ]
    
    for video_data in videos:
        DocumentationVideo.objects.create(**video_data)

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0051_reset_superadmin'),
    ]

    operations = [
        migrations.RunPython(seed_documentation_videos),
    ]
