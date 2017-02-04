from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
	url(r'^', include('tubes.urls')),
    url(r'^api_auth/', include('rest_framework.urls')), # Support for frontend login page
    url(r'^get_token/', obtain_auth_token, name='get-token'), # Support for token authentication
]
