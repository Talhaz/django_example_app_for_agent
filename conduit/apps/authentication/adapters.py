"""
Custom adapters for django-allauth integration with our custom User model.
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter to handle User model specifics.
    """
    def save_user(self, request, user, form, commit=True):
        """
        Override to handle our custom User model fields.
        """
        # Save the base user data
        data = form.cleaned_data
        user.email = data.get('email')
        user.username = data.get('email')  # Use email as username for our User model
        user.name = data.get('name') if 'name' in data else ''

        if 'password' in data:
            user.set_password(data['password'])
        else:
            user.set_unusable_password()

        if commit:
            user.save()
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for Google OAuth.
    """
    def save_user(self, request, sociallogin, form=None):
        """
        Override to handle saving users from social accounts (Google OAuth).
        """
        user = super().save_user(request, sociallogin, form)

        # Set additional fields from social account data
        if sociallogin.account.provider == 'google':
            # Get user data from Google
            extra_data = sociallogin.account.extra_data

            # Set email
            user.email = extra_data.get('email', '')
            # Use email as username for our User model
            user.username = extra_data.get('email', '')

            # Set name (combine first and last name if available)
            first_name = extra_data.get('given_name', '')
            last_name = extra_data.get('family_name', '')
            if first_name and last_name:
                user.name = f"{first_name} {last_name}"
            elif first_name:
                user.name = first_name
            elif last_name:
                user.name = last_name
            else:
                # Use email prefix as fallback
                user.name = extra_data.get('email', '').split('@')[0]

            user.save()

        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Allow auto-signup for Google OAuth.
        """
        return True

    def pre_social_login(self, request, sociallogin):
        """
        Pre-login hook to handle linking social accounts to existing users.
        """
        # If this social account already exists, link it to the existing user
        if sociallogin.is_existing:
            return

        # Try to find an existing user with the same email
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return

        try:
            user = User.objects.get(email=email)
            # Link the social account to the existing user
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            # No existing user, let the auto-signup create a new one
            pass