from django.db import migrations

def add_resume_video(apps, schema_editor):
    DocumentationVideo = apps.get_model('accounts', 'DocumentationVideo')
    DocumentationVideo.objects.create(
        title="Résumé général",
        youtube_url="https://youtu.be/gxW4b3tqcNg",
        youtube_video_id="gxW4b3tqcNg",
        description="Résumé général et présentation globale des fonctionnalités et de la configuration de la plateforme Central Borlette.",
        category="Résumé",
        order=1,
        is_active=True
    )

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0052_seed_documentation_videos'),
    ]

    operations = [
        migrations.RunPython(add_resume_video),
    ]
