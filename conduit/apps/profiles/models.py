from django.db import models

from conduit.apps.core.models import TimestampedModel
from rest_framework.exceptions import NotFound


class Profile(TimestampedModel):
    """
    User profile model extending the User model with additional information.
    
    Handles:
    - User profile information (bio, image)
    - Social following/followers
    - Magazine association (optional)
    """
    
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='profile'
    )

    bio = models.TextField(
        blank=True,
        max_length=1000,
        help_text='Tell other users something about yourself'
    )

    image = models.URLField(
        blank=True,
        help_text='Profile image URL'
    )

    # Follow relationships - a user can follow other users
    follows = models.ManyToManyField(
        'self',
        related_name='followed_by',
        symmetrical=False,
        blank=True,
        help_text='Users that this profile is following'
    )

    # Optional magazine association
    magazine = models.ForeignKey(
        'magazines.Magazine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authors',
        help_text='Magazine this profile is associated with (if any)'
    )

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"@{self.user.username}"

    def get_absolute_url(self):
        """Return the URL for this profile."""
        return f'/profiles/{self.user.username}/'

    # Class methods
    @classmethod
    def get_by_username(cls, username):
        """
        Get a profile by username with optimized queries.

        Args:
            username: Username to look up

        Returns:
            Profile instance

        Raises:
            NotFound: If profile with username doesn't exist
        """
        try:
            return cls.objects.select_related('user').get(user__username=username)
        except cls.DoesNotExist:
            raise NotFound('A profile with this username does not exist.')

    # Follow/Follower methods
    def follow(self, profile):
        """
        Follow a profile.

        Args:
            profile: Profile instance to follow

        Raises:
            ValueError: If trying to follow oneself
        """
        if self.pk == profile.pk:
            raise ValueError('You cannot follow yourself.')
        if not self.is_following(profile):
            self.follows.add(profile)

    def unfollow(self, profile):
        """
        Unfollow a profile.

        Args:
            profile: Profile instance to unfollow
        """
        if self.is_following(profile):
            self.follows.remove(profile)

    def is_following(self, profile):
        """
        Check if this profile is following another profile.

        Args:
            profile: Profile instance to check

        Returns:
            bool: True if following, False otherwise
        """
        return self.follows.filter(pk=profile.pk).exists()

    def is_followed_by(self, profile):
        """
        Check if this profile is followed by another profile.

        Args:
            profile: Profile instance to check

        Returns:
            bool: True if followed by, False otherwise
        """
        return self.followed_by.filter(pk=profile.pk).exists()

    # Article interaction methods (delegated to Article model)
    def favorite_article(self, article):
        """
        Favorite an article.
        
        Note: This is a convenience method that delegates to Article model.
        Consider using Article.favorite(profile) instead for better semantics.
        """
        from conduit.apps.articles.models import Article
        article.favorite(self)

    def unfavorite_article(self, article):
        """
        Unfavorite an article.
        
        Note: This is a convenience method that delegates to Article model.
        Consider using Article.unfavorite(profile) instead for better semantics.
        """
        from conduit.apps.articles.models import Article
        article.unfavorite(self)

    def has_favorited(self, article):
        """
        Check if this profile has favorited an article.

        Args:
            article: Article instance to check

        Returns:
            bool: True if favorited, False otherwise
        """
        return article.favorited_by.filter(pk=self.pk).exists()

    # Properties for computed data
    @property
    def followers_count(self):
        """Get the count of followers."""
        return self.followed_by.count()

    @property
    def following_count(self):
        """Get the count of profiles being followed."""
        return self.follows.count()

    @property
    def articles_count(self):
        """Get the count of articles written by this profile."""
        return self.articles.count()
