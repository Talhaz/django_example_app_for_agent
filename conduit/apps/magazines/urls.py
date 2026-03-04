from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MagazineViewSet

app_name = 'magazines'

router = DefaultRouter()
router.register(r'magazines', MagazineViewSet, basename='magazine')

urlpatterns = [
    path('', include(router.urls)),
]