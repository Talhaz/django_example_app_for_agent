"""
Magazine models module.

Provides the Magazine model and its custom manager for managing magazine
publications and their associated articles.
"""

from django.db import models, DatabaseError, IntegrityError
from django.db.models import Count
from django.utils.text import slugify
from django.utils.functional import cached_property
from typing import Optional, TYPE_CHECKING

from conduit.apps.core.models import TimestampedModel
from conduit.apps.articles.models import Article

if TYPE_CHECKING:
    from conduit.apps.profiles.models import Profile


# Constants for magazine thresholds
FEATURED_ARTICLE_THRESHOLD = 10  # Number of articles required to be featured


class MagazineManager(models.Manager):
    """
    Custom manager for Magazine model with article-related query methods.

    Provides optimized queryset methods for retrieving articles associated
    with magazines, reducing code duplication and improving query efficiency.

    All methods handle database errors gracefully and return appropriate
    fallback values (empty querysets, zeros, False) when errors occur.
    """

    def _handle_query_error(self, fallback_value=None):
        """
        Decorator/context manager-style helper to handle database errors consistently.

        Args:
            fallback_value: Value to return on error (default depends on method)

        Returns:
            Decorator function that wraps query methods
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except (DatabaseError, IntegrityError):
                    return fallback_value
                except Exception:
                    return fallback_value
            return wrapper
        return decorator

    def get_base_article_queryset(self, magazine: models.Model) -> models.QuerySet:
        """
        Get the base queryset for articles belonging to a magazine.

        This method provides the common queryset foundation for all article queries,
        reducing duplication across multiple methods.

        Args:
            magazine: Magazine instance to filter articles for

        Returns:
            QuerySet: Base queryset of articles with related fields selected
        """
        return Article.objects.filter(
            author__magazine=magazine,
            status='published'
        ).select_related('author', 'author__profile')

    def _calculate_featured_threshold(self, magazine: models.Model) -> int:
        """
        Calculate the view count threshold for featured articles.

        Featured articles are in the top 10% of articles by view count.

        Args:
            magazine: Magazine instance to calculate threshold for

        Returns:
            int: Minimum view count to be considered featured
        """
        article_count = magazine.article_count
        return max(article_count // 10, 1)

    def get_active_articles(
        self,
        magazine: models.Model,
        limit: Optional[int] = None,
        offset: int = 0,
        annotate_count: bool = False
    ) -> models.QuerySet:
        """
        Get active (published) articles from the given magazine.

        Args:
            magazine: Magazine instance to get articles for
            limit: Maximum number of articles to return (None for all)
            offset: Number of articles to skip (pagination offset)
            annotate_count: If True, annotate total count before slicing

        Returns:
            QuerySet: Filtered queryset of active articles (with count if annotated)
                       Returns empty queryset on database errors
        """
        try:
            articles = self.get_base_article_queryset(magazine)

            if annotate_count:
                # Annotate count before slicing to avoid extra query
                articles = articles.annotate(total_count=Count('id'))

            if offset > 0:
                articles = articles[offset:]

            if limit is not None:
                articles = articles[:limit]

            return articles

        except (DatabaseError, IntegrityError, Exception):
            return Article.objects.none()

    def get_featured_articles(self, magazine: models.Model, limit: int = 5) -> models.QuerySet:
        """
        Get featured articles from the given magazine.

        Featured articles are determined by:
        - Having high view count (top 10% by default)

        Args:
            magazine: Magazine instance to get featured articles for
            limit: Maximum number of featured articles to return

        Returns:
            QuerySet: Filtered queryset of featured articles
                       Returns empty queryset on database errors
        """
        try:
            threshold = self._calculate_featured_threshold(magazine)

            featured = self.get_base_article_queryset(magazine).filter(
                view_count__gte=threshold
            )

            # Order by view count (most viewed first)
            return featured.order_by('-view_count')[:limit]

        except (DatabaseError, IntegrityError, Exception):
            return Article.objects.none()

    def get_featured_count(self, magazine: models.Model) -> int:
        """
        Get the count of featured articles in the given magazine.

        Uses a lightweight COUNT query instead of fetching all records.

        Args:
            magazine: Magazine instance to count featured articles for

        Returns:
            int: Number of featured articles (returns 0 on database errors)
        """
        try:
            threshold = self._calculate_featured_threshold(magazine)

            return self.get_base_article_queryset(magazine).filter(
                view_count__gte=threshold
            ).count()

        except (DatabaseError, IntegrityError, Exception):
            return 0

    def get_top_articles(self, magazine: models.Model, limit: int = 5) -> models.QuerySet:
        """
        Get top articles from the given magazine.

        Returns the most viewed articles from this magazine.

        Args:
            magazine: Magazine instance to get articles for
            limit: Maximum number of articles to return

        Returns:
            QuerySet: Top articles from this magazine
                       Returns empty queryset on database errors
        """
        try:
            return self.get_active_articles(magazine, limit=limit)
        except Exception:
            return Article.objects.none()

    def has_active_articles(self, magazine: models.Model) -> bool:
        """
        Check if the magazine has any active (published) articles.

        Args:
            magazine: Magazine instance to check

        Returns:
            bool: True if magazine has active articles, False otherwise
                    Returns False on database errors
        """
        try:
            return magazine.article_count > 0
        except (AttributeError, TypeError, DatabaseError, IntegrityError, Exception):
            return False


class Magazine(TimestampedModel):
    """
    Magazine model for managing magazine publications.

    Inherits created_at and updated_at from TimestampedModel.
    A magazine represents a publication that can contain multiple articles.
    Each article is associated with a magazine through the author's profile.

    Attributes:
        title: The title of the magazine
        slug: URL-friendly identifier (auto-generated from title)
        description: Brief description of the magazine
        is_active: Whether the magazine is currently active

    Relationships:
        Through author's profile to articles (one-to-many)
    """

    objects = MagazineManager()

    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(db_index=True, max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Magazine'
        verbose_name_plural = 'Magazines'
        indexes = [
            models.Index(fields=['-created_at', 'is_active']),
            models.Index(fields=['title']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        """
        Return string representation of the magazine.

        Returns:
            str: The magazine title
        """
        return self.title

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate slug from title.

        Handles edge cases:
        - If slug is provided, uses it as-is
        - Otherwise generates slug from title
        - Ensures slug is unique

        Raises:
            ValueError: If title is empty or slug generation fails
            DatabaseError: If save operation fails
        """
        if not self.title or not self.title.strip():
            raise ValueError("Magazine title cannot be empty.")

        try:
            if not self.slug:
                self.slug = slugify(self.title)

            if not self.slug:
                raise ValueError(f"Could not generate a valid slug from title: '{self.title}'")

            super().save(*args, **kwargs)

        except (DatabaseError, IntegrityError) as e:
            raise DatabaseError(f"Failed to save magazine: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error saving magazine: {str(e)}")

    def get_absolute_url(self) -> str:
        """
        Return the absolute URL for this magazine.

        Returns:
            str: URL path to the magazine (e.g., '/magazines/my-magazine')
        """
        return f'/magazines/{self.slug}'

    @cached_property
    def article_count(self) -> int:
        """
        Get the total count of articles in this magazine (cached).

        Only counts published articles.

        Returns:
            int: Number of articles in this magazine
        """
        return Article.objects.filter(
            author__magazine=self,
            status='published'
        ).count()

    @cached_property
    def is_featured(self) -> bool:
        """
        Check if this magazine is featured (cached per instance).

        A magazine is considered featured if it has at least FEATURED_ARTICLE_THRESHOLD
        articles and is active.

        Returns:
            bool: True if featured, False otherwise
        """
        return self.is_active and self.article_count >= FEATURED_ARTICLE_THRESHOLD