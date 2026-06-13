"""
URL configuration for centralborlette project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

from django.conf import settings
from django.conf.urls.static import static

from accounts import views as accounts_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('favicon.ico'), permanent=True)),
    path('', include('landing.urls')),
    path('admin/', accounts_views.admin_index_redirect),
    path('admin/', admin.site.urls),
    path('portal/', include('admin_portal.urls')),
    path('agent/', include('agent_portal.urls')),
    path('affiliate/', include('accounts.affiliate_urls')),
    path('partner/', include('accounts.partner_urls')),
    path('superadmin/dashboard/', accounts_views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/borlette/<int:borlette_id>/toggle-status/', accounts_views.superadmin_toggle_borlette_status, name='superadmin_toggle_borlette_status'),
    path('superadmin/api-config/', accounts_views.superadmin_api_config, name='superadmin_api_config'),
    path('superadmin/recovery/', accounts_views.superadmin_recovery_requests, name='superadmin_recovery_requests'),
    path('superadmin/recovery/<str:recovery_id>/resolve/', accounts_views.superadmin_resolve_recovery, name='superadmin_resolve_recovery'),
    path('account/recovery/', accounts_views.account_recovery, name='account_recovery'),
    path('account/force-password-change/', accounts_views.force_password_change, name='force_password_change'),
    path('api/', include('tickets.api_urls')),
    path('api/', include('accounts.api_urls')),
    path('api/agent/', include('agent_portal.api_urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
