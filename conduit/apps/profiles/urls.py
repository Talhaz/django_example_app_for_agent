from django.urls import path

from .views import ProfileRetrieveAPIView, ProfileFollowAPIView

app_name = 'profiles'

urlpatterns = [
    path('profiles/<str:username>/', ProfileRetrieveAPIView.as_view(), name='retrieve'),
    path('profiles/<str:username>/follow/', ProfileFollowAPIView.as_view(), name='follow'),
]
