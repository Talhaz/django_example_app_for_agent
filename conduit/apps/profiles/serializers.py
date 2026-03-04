from rest_framework import serializers
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Profile

# Default profile image
DEFAULT_PROFILE_IMAGE = 'https://static.productionready.io/images/smiley-cyrus.jpg'


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile model."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    bio = serializers.CharField(
        allow_blank=True,
        required=False,
        max_length=1000,
        help_text='Tell others about yourself (max 1000 characters)',
        error_messages={
            'max_length': 'Bio cannot exceed 1,000 characters.'
        }
    )
    image = serializers.URLField(
        allow_blank=True,
        required=False,
        help_text='Profile image URL',
        error_messages={
            'invalid': 'Please provide a valid image URL.'
        }
    )
    following = serializers.SerializerMethodField()
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    articles_count = serializers.ReadOnlyField()

    class Meta:
        model = Profile
        fields = (
            'username',
            'bio',
            'image',
            'following',
            'followers_count',
            'following_count',
            'articles_count',
        )
        read_only_fields = ('username',)

    def get_image(self, obj):
        """Return profile image or default if not set."""
        return obj.image if obj.image else DEFAULT_PROFILE_IMAGE

    def get_following(self, instance):
        """
        Check if the authenticated user is following this profile.
        
        Returns:
            bool: True if following, False otherwise
        """
        request = self.context.get('request')
        
        if not request or not request.user.is_authenticated:
            return False
        
        try:
            follower = request.user.profile
            return follower.is_following(instance)
        except Profile.DoesNotExist:
            return False
