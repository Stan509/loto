#!/usr/bin/env python
import os
import sys
import django
from django.utils import timezone

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaboom.settings')
django.setup()

from admin_portal.models import Agent, AgentDevice

# Create a test agent
agent = Agent.objects.create(
    first_name="Test",
    last_name="Agent",
    phone="50912345678",
    email="test@gaboom.com",
    is_active=True,
    created_at=timezone.now(),
    updated_at=timezone.now()
)

# Create device credentials for the agent
device = AgentDevice.objects.create(
    agent=agent,
    device_id="test_device_001",
    device_secret="test_secret_key_123456789",
    device_name="Test Device",
    is_active=True,
    created_at=timezone.now(),
    updated_at=timezone.now()
)

print(f"✅ Agent créé: {agent.first_name} {agent.last_name} (ID: {agent.id})")
print(f"📱 Device ID: {device.device_id}")
print(f"🔑 Device Secret: {device.device_secret}")
print(f"📧 Email: {agent.email}")
print(f"📞 Téléphone: {agent.phone}")

# Display connection info for app
print("\n📋 Informations pour l'app:")
print(f"Device ID: {device.device_id}")
print(f"Device Secret: {device.device_secret}")
print(f"Device Name: {device.device_name}")
