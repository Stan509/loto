#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaboom.settings')
django.setup()

from admin_portal.models import Agent, AgentDevice
from django.utils import timezone

def create_test_agent():
    """Create a test agent with device credentials"""
    
    # Check if agent already exists
    existing_agent = Agent.objects.filter(email="test@gaboom.com").first()
    if existing_agent:
        print(f"⚠️  Agent existe déjà: {existing_agent.first_name} {existing_agent.last_name}")
        device = AgentDevice.objects.filter(agent=existing_agent).first()
        if device:
            print(f"📱 Device ID: {device.device_id}")
            print(f"🔑 Device Secret: {device.device_secret}")
            return device
        else:
            print("❌ Aucun device trouvé pour cet agent")
    
    # Create new agent
    agent = Agent.objects.create(
        first_name="Test",
        last_name="Agent",
        phone="50912345678",
        email="test@gaboom.com",
        is_active=True,
        created_at=timezone.now(),
        updated_at=timezone.now()
    )
    
    # Create device credentials
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
    
    return device

if __name__ == "__main__":
    create_test_agent()
