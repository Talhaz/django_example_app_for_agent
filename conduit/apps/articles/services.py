"""
Services for article-related business logic.

This module contains service classes that encapsulate complex business logic
that was previously embedded in views. This improves separation of concerns
and makes the code more testable and reusable.
"""

from django.db.models import Q, Count, F


class ArticleFilterService:
    """
    Service for filtering and sorting article querysets.
    
    This service encapsulates all the complex filtering logic that was
    previously in the ArticleViewSet.get_queryset() method.
    """
    
    def __init__(self, base_queryset):
        """
        Initialize with a base queryset.
        
        Args:
            base_queryset: The starting Article queryset (should be optimized)
        """
        self.queryset = base_queryset
    
    def apply_filters(self, filters):
        """
        Apply all filters to the queryset.
        
        Args:
            filters: Dictionary of filter parameters from request.query_params
            
        Returns:
            Filtered and sorted queryset
        """
        # Apply individual filters
        self._filter_by_author(filters.get('author'))
        self._filter_by_tag(filters.get('tag'))
        self._filter_by_multiple_tags(filters.get('tags'))
        self._filter_by_favorited_by(filters.get('favorited'))
        self._filter_by_category(filters.get('category'))
        self._filter_by_language(filters.get('language'))
        self._filter_by_search(filters.get('search'))

        # Handle date range with support for both parameter naming conventions
        # Priority: start_date/end_date > date_from/date_to (for backward compatibility)
        date_from = filters.get('start_date') or filters.get('date_from')
        date_to = filters.get('end_date') or filters.get('date_to')
        self._filter_by_date_range(date_from, date_to)
        self._filter_by_status(filters.get('status'))
        
        # Apply sorting
        self._apply_sorting(filters.get('sort'))
        
        return self.queryset
    
    def _filter_by_author(self, author):
        """Filter by author username."""
        if author:
            self.queryset = self.queryset.filter(author__user__username=author)
    
    def _filter_by_tag(self, tag):
        """Filter by single tag."""
        if tag:
            self.queryset = self.queryset.filter(tags__name=tag)
    
    def _filter_by_multiple_tags(self, tags):
        """Filter by multiple comma-separated tags."""
        if tags:
            tag_list = [t.strip() for t in tags.split(',')]
            for tag in tag_list:
                self.queryset = self.queryset.filter(tags__name=tag)
    
    def _filter_by_favorited_by(self, favorited_by):
        """Filter by favorited user."""
        if favorited_by:
            self.queryset = self.queryset.filter(
                favorited_by__user__username=favorited_by
            )
    
    def _filter_by_category(self, category):
        """Filter by category."""
        if category:
            self.queryset = self.queryset.filter(category=category)
    
    def _filter_by_search(self, search):
        """Search in title, description, or body."""
        if search:
            self.queryset = self.queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(body__icontains=search)
            )
    
    def _filter_by_date_range(self, date_from, date_to):
        """Filter by date range."""
        if date_from:
            self.queryset = self.queryset.filter(created_at__gte=date_from)
        if date_to:
            self.queryset = self.queryset.filter(created_at__lte=date_to)
    
    def _filter_by_status(self, status):
        """Filter by article status."""
        if status:
            self.queryset = self.queryset.filter(status=status)
    
    def _filter_by_language(self, language):
        """Filter by language."""
        if language:
            self.queryset = self.queryset.filter(language=language)
    
    def _apply_sorting(self, sort_by):
        """
        Apply sorting to the queryset.
        
        Args:
            sort_by: Sort parameter (e.g., 'date', '-date', 'popularity', etc.)
        """
        if not sort_by:
            return
        
        valid_sorts = {
            'date': '-created_at',
            '-date': 'created_at',
            'popularity': '-view_count',
            '-popularity': 'view_count',
            'favorites': '-favorited_by__count',
            '-favorites': 'favorited_by__count',
            'comments': '-comments__count',
            '-comments': 'comments__count',
        }
        
        # Annotate if sorting by favorites or comments
        if sort_by in ['favorites', '-favorites', 'comments', '-comments']:
            self.queryset = self.queryset.annotate(
                favorited_by_count=Count('favorited_by'),
                comments_count=Count('comments')
            )
        
        if sort_by in valid_sorts:
            self.queryset = self.queryset.order_by(valid_sorts[sort_by])


class ArticleExportService:
    """
    Service for exporting articles to various formats.
    """
    
    def __init__(self, queryset, serializer_class):
        """
        Initialize with queryset and serializer.
        
        Args:
            queryset: Article queryset to export
            serializer_class: DRF serializer class for articles
        """
        self.queryset = queryset
        self.serializer_class = serializer_class
    
    def to_csv(self):
        """
        Export articles to CSV format.
        
        Returns:
            HttpResponse with CSV content
        """
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="articles.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'slug', 'title', 'description', 'author',
            'created_at', 'view_count', 'status', 'category'
        ])
        
        for article in self.queryset:
            writer.writerow([
                article.slug,
                article.title,
                article.description,
                article.author.user.username,
                article.created_at.isoformat(),
                article.view_count,
                article.status,
                article.category or '',
            ])
        
        return response
    
    def to_json(self, request):
        """
        Export articles to JSON format.
        
        Args:
            request: HTTP request object for serializer context
            
        Returns:
            HttpResponse with JSON content
        """
        from django.http import HttpResponse
        import json
        
        serializer = self.serializer_class(
            self.queryset, context={'request': request}, many=True
        )
        response = HttpResponse(
            json.dumps(serializer.data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="articles.json"'
        return response


class ArticleStatsService:
    """
    Service for calculating article statistics.
    """
    
    def __init__(self):
        """
        Initialize stats service.
        """
        from .models import Article, Comment
        self.Article = Article
        self.Comment = Comment
    
    def get_all_stats(self):
        """
        Calculate comprehensive article statistics.
        
        Returns:
            Dictionary with various statistics
        """
        from django.db.models import Sum, Avg
        
        queryset = self.Article.objects.all()
        
        stats = {
            'total_articles': queryset.count(),
            'total_views': queryset.aggregate(total=Sum('view_count'))['total'] or 0,
            'avg_views': queryset.aggregate(avg=Avg('view_count'))['avg'] or 0,
            'most_viewed': self._get_most_viewed(queryset),
            'total_comments': self.Comment.objects.count(),
            'articles_by_status': self._get_articles_by_status(queryset),
            'recent_articles': self._get_recent_articles(queryset),
        }
        
        return stats
    
    def _get_most_viewed(self, queryset):
        """Get the most viewed article."""
        most_viewed = queryset.order_by('-view_count').first()
        if most_viewed:
            return {
                'slug': most_viewed.slug,
                'title': most_viewed.title,
                'view_count': most_viewed.view_count,
            }
        return None
    
    def _get_articles_by_status(self, queryset):
        """Get count of articles by status."""
        return {
            status: queryset.filter(status=status).count()
            for status, _ in self.Article.STATUS_CHOICES
        }
    
    def _get_recent_articles(self, queryset):
        """Get recent articles."""
        return list(
            queryset.order_by('-created_at')[:5]
            .values('slug', 'title', 'created_at')
        )


class ArticleSearchService:
    """
    Service for searching articles.
    """
    
    def __init__(self, base_queryset):
        """
        Initialize with base queryset.
        
        Args:
            base_queryset: The starting Article queryset (should be optimized)
        """
        self.queryset = base_queryset
    
    def search(self, search_query, category=None, status_filter='published'):
        """
        Search articles across multiple fields.
        
        Args:
            search_query: Search term
            category: Optional category filter
            status_filter: Status to filter by (default: 'published')
            
        Returns:
            Filtered queryset ordered by relevance (date descending)
        """
        # Start with base queryset filtered by status
        self.queryset = self.queryset.filter(status=status_filter)
        
        # Apply category filter if provided
        if category is not None:
            self.queryset = self.queryset.filter(category=category)
        
        # Apply search query if provided
        if search_query and search_query.strip():
            self.queryset = self._apply_search_query(search_query.strip())
        
        return self.queryset.order_by('-created_at', '-updated_at')
    
    def _apply_search_query(self, search_query):
        """
        Apply full-text search across multiple fields.
        
        Args:
            search_query: The cleaned search term
            
        Returns:
            Filtered queryset
        """
        from django.db.models import Q
        
        # Search across multiple fields using Q objects for OR logic
        return self.queryset.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(body__icontains=search_query) |
            Q(tags__name__icontains=search_query) |
            Q(author__user__username__icontains=search_query)
        ).distinct()  # Remove duplicates from tag joins


class ArticleFeedService:
    """
    Service for retrieving personalized article feeds based on followed users.
    
    This service encapsulates the logic for generating a feed of articles
    from users that the current user follows, with optional filtering capabilities.
    """
    
    def __init__(self, base_queryset, user):
        """
        Initialize with base queryset and user.
        
        Args:
            base_queryset: The starting Article queryset (should be optimized)
            user: The user for whom to generate the feed
        """
        self.queryset = base_queryset
        self.user = user
    
    def get_feed(self, filters=None):
        """
        Get a feed of articles from followed users.

        Args:
            filters: Optional dictionary of filters to apply (same as ArticleFilterService)
                    Supported keys: category, tag, tags, search, date_from, date_to, sort, status

        Returns:
            Queryset of articles from followed users, optionally filtered and sorted
        """
        # Filter articles by followed users
        followed_profiles = self.user.profile.follows.all()
        self.queryset = self.queryset.filter(author__in=followed_profiles)

        # Apply additional filters if provided
        if filters:
            filter_service = ArticleFilterService(self.queryset)
            self.queryset = filter_service.apply_filters(filters)

        return self.queryset
    
    def get_feed_with_defaults(self):
        """
        Get feed with default filters (published articles, newest first).
        
        Returns:
            Queryset of published articles from followed users, ordered by newest first
        """
        default_filters = {
            'status': 'published',
            'sort': '-date'
        }
        return self.get_feed(default_filters)