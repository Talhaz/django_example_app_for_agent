"""
Article Search Service.

Handles search query building for articles with support for
full-text search across multiple fields and optional filters.
"""

from django.db.models import Q


class ArticleSearchService:
    """Service for building article search queries."""

    def __init__(self, base_queryset=None):
        """Initialize with optional base queryset.

        Args:
            base_queryset: Starting queryset (defaults to Article.objects.all())
        """
        from .models import Article

        self.base_queryset = base_queryset or Article.objects.all()

    def build_search_query(
        self,
        search_query='',
        category=None,
        status_filter='published'
    ):
        """Build a filtered queryset based on search parameters.

        Args:
            search_query: Text to search across multiple fields
            category: Optional category filter
            status_filter: Article status filter (default: 'published')

        Returns:
            QuerySet: Filtered and ordered queryset
        """
        # Start with base queryset
        queryset = self.base_queryset.filter(status=status_filter)

        # Apply category filter if provided
        if category is not None:
            queryset = queryset.filter(category=category)

        # Apply search query if provided
        if search_query:
            # Search across multiple fields using Q objects for OR logic
            # Build search query: title, description, body, tags, or author username
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(body__icontains=search_query) |
                Q(tags__name__icontains=search_query) |
                Q(author__user__username__icontains=search_query)
            ).distinct()  # Remove duplicates from tag joins

        return queryset.order_by('-created_at', '-updated_at')