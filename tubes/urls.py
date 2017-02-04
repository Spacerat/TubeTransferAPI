from django.conf.urls import url, include
from tubes import views
from rest_framework.routers import DefaultRouter

# Hook up the URLs for the /containers/ endpoint.
router = DefaultRouter()
router.register(r'containers', views.ContainerViewSet)

urlpatterns = [
	url(r'^', include(router.urls)),
]
