from rest_framework import status, generics
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile
from .renderers import ProfileJSONRenderer
from .serializers import ProfileSerializer


class BaseProfileView:
    """Base view with common profile serializer logic."""
    
    serializer_class = ProfileSerializer
    renderer_classes = (ProfileJSONRenderer,)
    
    def get_serializer_context(self):
        """Add request to serializer context."""
        context = super().get_serializer_context() if hasattr(super(), 'get_serializer_context') else {}
        context['request'] = self.request
        return context
    
    def serialize_profile(self, profile):
        """Serialize a profile instance with context."""
        return self.serializer_class(
            profile,
            context=self.get_serializer_context()
        ).data


class ProfileRetrieveAPIView(BaseProfileView, RetrieveAPIView):
    """
    Retrieve a user's profile by username.
    
    GET /profiles/{username}/
    """
    permission_classes = (AllowAny,)
    lookup_field = 'username'
    
    def get_object(self):
        """Get profile by username from URL."""
        username = self.kwargs.get('username')
        return Profile.get_by_username(username)
    
    def retrieve(self, request, username, *args, **kwargs):
        """Return the requested profile."""
        profile = self.get_object()
        return Response(
            self.serialize_profile(profile),
            status=status.HTTP_200_OK
        )


class ProfileFollowAPIView(BaseProfileView, APIView):
    """
    Follow or unfollow a user profile.

    POST /profiles/{username}/follow - Follow a user
    DELETE /profiles/{username}/follow - Unfollow a user
    """
    permission_classes = (IsAuthenticated,)

    def _get_profiles(self, username):
        """
        Get follower (current user) and followee (target profile).

        Args:
            username: Username of profile to follow/unfollow

        Returns:
            tuple: (follower_profile, followee_profile)
        """
        follower = self.request.user.profile
        followee = Profile.get_by_username(username)
        return follower, followee

    def delete(self, request, username):
        """Unfollow a user profile."""
        follower, followee = self._get_profiles(username)
        follower.unfollow(followee)

        # Re-fetch the profile to get updated counts
        updated_profile = Profile.get_by_username(username)

        return Response(
            self.serialize_profile(updated_profile),
            status=status.HTTP_200_OK
        )

    def post(self, request, username):
        """Follow a user profile."""
        follower, followee = self._get_profiles(username)
        follower.follow(followee)

        # Re-fetch the profile to get updated counts
        updated_profile = Profile.get_by_username(username)

        return Response(
            self.serialize_profile(updated_profile),
            status=status.HTTP_201_CREATED
        )