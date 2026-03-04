from django.urls import re_path

app_name = 'authentication'

from .views import (
    LoginAPIView, RegistrationAPIView, UserRetrieveUpdateAPIView
)
from .oauth import (
    GoogleOAuthView, GoogleOAuthCallbackView, GoogleAuthUrlView
)

urlpatterns = [
    re_path(r'^user/?$', UserRetrieveUpdateAPIView.as_view()),
    re_path(r'^users/?$', RegistrationAPIView.as_view()),
    re_path(r'^users/login/?$', LoginAPIView.as_view()),
    
    # Google OAuth URLs
    re_path(r'^oauth/google/$', GoogleOAuthView.as_view(), name='google_oauth_login'),
    re_path(r'^oauth/google/callback/$', GoogleOAuthCallbackView.as_view(), name='google_oauth_callback'),
    re_path(r'^oauth/google/url/$', GoogleAuthUrlView.as_view(), name='google_oauth_url'),
]
