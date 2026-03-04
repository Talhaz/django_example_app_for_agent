from django.urls import path, re_path
from rest_framework.routers import DefaultRouter
from conduit.apps.reviews.views import ReviewViewSet

app_name = 'reviews'

router = DefaultRouter(trailing_slash=False)
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = router.urls