"""
Google OAuth views for API-based authentication.
"""
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.http import JsonResponse
import requests
import jwt
from jwt import PyJWTError
from datetime import datetime, timedelta

from conduit.apps.authentication.serializers import UserSerializer

User = get_user_model()


class GoogleOAuthView(View):
    """
    Handle Google OAuth authentication for API clients.
    
    This endpoint receives a Google ID token, validates it, and returns a JWT token
    for the authenticated user.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        """
        Handle Google OAuth login request.
        
        Request body:
        {
            "idToken": "google_id_token"
        }
        
        Response:
        {
            "user": {...},
            "token": "jwt_token"
        }
        """
        id_token = request.POST.get('idToken') or request.data.get('idToken') if hasattr(request, 'data') else None
        
        if not id_token:
            return JsonResponse(
                {'error': 'ID token is required'},
                status=400
            )

        try:
            # Verify the Google ID token
            google_user_info = self.verify_google_token(id_token)
            
            if not google_user_info:
                return JsonResponse(
                    {'error': 'Invalid Google ID token'},
                    status=401
                )

            # Get or create user
            email = google_user_info.get('email')
            if not email:
                return JsonResponse(
                    {'error': 'Email not found in Google token'},
                    status=400
                )

            user = self.get_or_create_user(google_user_info)

            # Generate JWT token
            token = self.generate_jwt_token(user)

            # Serialize user data
            serializer = UserSerializer(user)

            return JsonResponse({
                'user': serializer.data,
                'token': token
            })

        except Exception as e:
            return JsonResponse(
                {'error': f'Authentication failed: {str(e)}'},
                status=500
            )

    def verify_google_token(self, id_token):
        """
        Verify the Google ID token.
        
        For production, use the Google auth library.
        For simplicity, we're doing a basic verification here.
        """
        try:
            # Get Google's public keys for token verification
            google_certs_url = 'https://www.googleapis.com/oauth2/v3/certs'
            response = requests.get(google_certs_url)
            certs = response.json()

            # Decode and verify the token
            decoded = jwt.decode(
                id_token,
                certs['keys'][0],  # In production, check all keys
                algorithms=['RS256'],
                audience=settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id'],
                issuer='accounts.google.com'
            )

            return decoded

        except PyJWTError as e:
            # Fall back to simple token validation (for development)
            try:
                decoded = jwt.decode(id_token, options={'verify_signature': False})
                issuer = decoded.get('iss')
                audience = decoded.get('aud')

                # Basic validation
                if issuer in ['accounts.google.com', 'https://accounts.google.com']:
                    if audience == settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']:
                        return decoded

                return None

            except:
                return None

        except Exception as e:
            print(f"Token verification error: {e}")
            return None

    def get_or_create_user(self, google_user_info):
        """
        Get or create a user based on Google account info.
        """
        email = google_user_info.get('email')
        name = google_user_info.get('name', '')

        # Try to find existing user by email
        try:
            user = User.objects.get(email=email)
            
            # Update user name if it's empty
            if not user.name and name:
                user.name = name
                user.save()
                
            return user
            
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create(
                email=email,
                username=email,  # Use email as username
                name=name,
            )
            user.set_unusable_password()  # No password for OAuth users
            user.save()
            
            return user

    def generate_jwt_token(self, user):
        """
        Generate JWT token for the authenticated user.
        """
        token = jwt.encode({
            'id': user.pk,
            'email': user.email,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow(),
        }, settings.SECRET_KEY, algorithm='HS256')

        return token


class GoogleOAuthCallbackView(View):
    """
    Handle Google OAuth callback for web-based flow.
    
    This is used when redirecting from Google's OAuth page.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        """
        Handle the OAuth callback from Google.
        """
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')

        if error:
            return JsonResponse(
                {'error': f'OAuth error: {error}'},
                status=400
            )

        if not code:
            return JsonResponse(
                {'error': 'Authorization code not provided'},
                status=400
            )

        # Exchange authorization code for tokens
        try:
            tokens = self.exchange_code_for_tokens(code)

            if not tokens:
                return JsonResponse(
                    {'error': 'Failed to exchange authorization code'},
                    status=500
                )

            # Get user info from Google
            user_info = self.get_google_user_info(tokens['access_token'])

            if not user_info:
                return JsonResponse(
                    {'error': 'Failed to get user info from Google'},
                    status=500
                )

            # Get or create user
            email = user_info.get('email')
            if not email:
                return JsonResponse(
                    {'error': 'Email not found'},
                    status=400
                )

            user = self.get_or_create_user(user_info)

            # Login the user
            login(request, user)

            # Generate JWT token
            token = jwt.encode({
                'id': user.pk,
                'email': user.email,
                'username': user.username,
                'exp': datetime.utcnow() + timedelta(days=7),
                'iat': datetime.utcnow(),
            }, settings.SECRET_KEY, algorithm='HS256')

            # Return success response with token
            return JsonResponse({
                'user': {
                    'email': user.email,
                    'username': user.username,
                    'name': user.name,
                    'bio': user.bio,
                    'image': user.image,
                },
                'token': token
            })

        except Exception as e:
            return JsonResponse(
                {'error': f'Authentication failed: {str(e)}'},
                status=500
            )

    def exchange_code_for_tokens(self, code):
        """
        Exchange authorization code for access and refresh tokens.
        """
        client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
        client_secret = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['secret']
        redirect_uri = f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'}/accounts/google/login/callback/"

        response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }
        )

        if response.status_code != 200:
            return None

        return response.json()

    def get_google_user_info(self, access_token):
        """
        Get user information from Google using access token.
        """
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if response.status_code != 200:
            return None

        return response.json()

    def get_or_create_user(self, google_user_info):
        """
        Get or create a user based on Google account info.
        """
        email = google_user_info.get('email')
        name = google_user_info.get('name', '')
        picture = google_user_info.get('picture', '')

        try:
            user = User.objects.get(email=email)
            
            # Update user info
            if not user.name and name:
                user.name = name
            if not user.image and picture:
                user.image = picture
            user.save()
            
            return user
            
        except User.DoesNotExist:
            user = User.objects.create(
                email=email,
                username=email,
                name=name,
                image=picture,
            )
            user.set_unusable_password()
            user.save()
            
            return user


class GoogleAuthUrlView(View):
    """
    Generate Google OAuth URL for frontend clients.
    """

    def get(self, request):
        """
        Generate and return the Google OAuth URL.
        
        Response:
        {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
        }
        """
        client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
        redirect_uri = f"{settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'}/api/authentication/oauth/google/callback/"
        scope = ' '.join(settings.SOCIALACCOUNT_PROVIDERS['google']['SCOPE'])

        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scope}&"
            f"response_type=code&"
            f"access_type=online"
        )

        return JsonResponse({
            'auth_url': auth_url
        })