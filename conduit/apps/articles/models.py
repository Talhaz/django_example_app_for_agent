from django.db import models
from django.db.models import Count, F
from django.utils import timezone

from conduit.apps.core.models import TimestampedModel


class Article(TimestampedModel):
    slug = models.SlugField(db_index=True, max_length=255, unique=True)
    title = models.CharField(db_index=True, max_length=255)

    description = models.TextField()
    body = models.TextField()


    # Every article must have an author. This will answer questions like "Who
    # gets credit for writing this article?" and "Who can edit this article?".
    # Unlike the `User` <-> `Profile` relationship, this is a simple foreign
    # key (or one-to-many) relationship. In this case, one `Profile` can have
    # many `Article`s.
    author = models.ForeignKey(
        'profiles.Profile', on_delete=models.CASCADE, related_name='articles'
    )

    tags = models.ManyToManyField(
        'articles.Tag', related_name='articles'
    )

    # Publication status of the article.
    # Removed redundant 'published' boolean field - use 'status' instead
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)

    # Category field for article categorization
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('technology', 'Technology'),
        ('science', 'Science'),
        ('health', 'Health'),
        ('entertainment', 'Entertainment'),
        ('business', 'Business'),
        ('sports', 'Sports'),
        ('education', 'Education'),
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', db_index=True)

    # Enhanced fields
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Like/Dislike fields
    likes = models.ManyToManyField(
        'profiles.Profile', related_name='liked_articles', blank=True
    )
    dislikes = models.ManyToManyField(
        'profiles.Profile', related_name='disliked_articles', blank=True
    )

    # Favorites field - articles that profiles have favorited
    favorited_by = models.ManyToManyField(
        'profiles.Profile', related_name='favorited_articles', blank=True
    )

    # Reverse relationship to track individual article views
    view_history = models.ManyToManyField(
        'profiles.Profile', through='ArticleView', related_name='viewed_articles', blank=True
    )

    # Soft delete field
    is_deleted = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.title

    @property
    def reading_time(self):
        """
        Calculate estimated reading time in minutes.
        Average reading speed: ~200-250 words per minute.
        """
        if not self.body:
            return 0
        word_count = len(self.body.split())
        minutes = word_count // 200
        return max(1, minutes)  # Minimum 1 minute

    @property
    def trending_score(self):
        """
        Calculate trending score for an article based on engagement metrics.

        Scoring algorithm:
        - Each favorite counts as 3 points
        - Each comment counts as 2 points
        - Each view counts as 1 point

        This method can be used with annotation for batch queries:
            Article.objects.annotate(
                trending_score=Count('favorited_by') * 3 +
                               Count('comments') * 2 +
                               F('view_count')
            )

        Returns:
            int: The trending score for this individual article
        """
        return (self.favorited_by.count() * 3 +
                self.comments.count() * 2 +
                self.view_count)

    def toggle_like(self, profile):
        """Toggle like status for a profile.

        If profile has disliked the article, remove from dislikes.
        Then toggle like status: add if not liked, remove if already liked.

        Args:
            profile: Profile instance liking/unliking the article

        Returns:
            Article: The updated article instance
        """
        # Remove from dislikes if user previously disliked
        if profile in self.dislikes.all():
            self.dislikes.remove(profile)

        # Add to likes if not already liked, otherwise remove (toggle)
        if profile not in self.likes.all():
            self.likes.add(profile)
        else:
            self.likes.remove(profile)

        return self

    def favorite(self, profile):
        """
        Add this article to a profile's favorites.

        Args:
            profile: Profile instance favoriting the article
        """
        if not self.favorited_by.filter(pk=profile.pk).exists():
            self.favorited_by.add(profile)

    def unfavorite(self, profile):
        """
        Remove this article from a profile's favorites.

        Args:
            profile: Profile instance unfavoriting the article
        """
        if self.favorited_by.filter(pk=profile.pk).exists():
            self.favorited_by.remove(profile)


class ArticleView(TimestampedModel):
    """Model for tracking individual article views with metadata."""
    
    article = models.ForeignKey(
        'articles.Article', 
        related_name='article_views', 
        on_delete=models.CASCADE
    )
    
    user = models.ForeignKey(
        'profiles.Profile',
        related_name='article_views',
        on_delete=models.CASCADE
    )
    
    # Track additional view metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        # Ensure a user can only view an article once
        unique_together = ('article', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['article', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.user.user.username} viewed {self.article.title}'


class Tag(TimestampedModel):
    """Model for article tags."""
    
    name = models.CharField(db_index=True, max_length=255, unique=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name


class Comment(TimestampedModel):
    """Model for article comments with author and content."""
    
    article = models.ForeignKey(
        'articles.Article',
        related_name='comments',
        on_delete=models.CASCADE
    )
    
    author = models.ForeignKey(
        'profiles.Profile',
        related_name='comments',
        on_delete=models.CASCADE
    )
    
    body = models.TextField()
    
    # Soft delete field
    is_deleted = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['article', 'created_at']),
        ]
    
    def __str__(self):
        return f'Comment by {self.author.user.username} on {self.article.title}'
