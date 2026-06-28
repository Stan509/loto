from django.db import migrations
from django.contrib.auth.hashers import make_password

def reset_superadmin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    # Try to find existing superuser
    su = User.objects.filter(is_superuser=True).order_by('id').first()
    if not su:
        # Create a new superuser
        User.objects.create(
            username="root@gaboom509",
            email="root@gaboom509",
            password=make_password("H@cker509"),
            role="SUPER_ADMIN",
            is_superuser=True,
            is_staff=True,
            is_active=True,
        )
    else:
        su.username = "root@gaboom509"
        su.email = "root@gaboom509"
        su.password = make_password("H@cker509")
        su.role = "SUPER_ADMIN"
        su.is_superuser = True
        su.is_staff = True
        su.is_active = True
        su.save()

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0050_alter_adminpaymentsettings_boule_1er_lot_coeff_and_more'),
    ]

    operations = [
        migrations.RunPython(reset_superadmin),
    ]
