from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import (
    AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly, BasePermission
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from django.http import HttpResponse
from django.db.models import Q, Count, F, Case, When, IntegerField
from django.utils import timezone
from datetime import datetime
import csv
from io import StringIO
import json

from .models import Article, Comment, Tag
from .renderers import ArticleJSONRenderer, CommentJSONRenderer
from .serializers import ArticleSerializer, CommentSerializer, TagSerializer
from .services import (
    ArticleFilterService,
    ArticleExportService,
    ArticleStatsService,
    ArticleSearchService
)


# ============== Custom Permissions ==============

class IsAuthorOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an article to edit or delete it.
    Allows read-only access to any authenticated user.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        # Write permissions are only allowed to the author of the article.
        return obj.author == request.user.profile


class IsCommentAuthorOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of a comment to delete it.
    Allows read-only access to any authenticated user.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user.
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        # Write permissions (DELETE) are only allowed to the comment author.
        return obj.author == request.user.profile


class IsArticleAuthor(BasePermission):
    """
    Custom permission to only allow the article author to access the view.
    """

    def has_object_permission(self, request, view, obj):
        return obj.author == request.user.profile


# ============== Mixins for Common Functionality ==============

class ArticleQueryMixin:
    """Mixin providing common article queryset optimizations."""

    def get_base_queryset(self):
        """
        Return article queryset with common select_related optimizations.
        This eliminates N+1 query problems for author relationships.
        """
        return Article.objects.select_related('author', 'author__user')


class ArticleLookupMixin:
    """Mixin providing common article retrieval by slug logic."""

    def get_article_by_slug(self, slug):
        """
        Retrieve article by slug with NotFound exception handling.
        Centralizes article lookup logic to eliminate duplication.

        Args:
            slug: Article slug to look up

        Returns:
            Article instance

        Raises:
            NotFound: If article doesn't exist
        """
        try:
            return self.get_base_queryset().get(slug=slug)
        except Article.DoesNotExist:
            raise NotFound('An article with this slug does not exist.')


# ============== ViewSets ==============

class ArticleViewSet(ArticleQueryMixin,
                     ArticleLookupMixin,
                     mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):

    lookup_field = 'slug'
    queryset = Article.objects.select_related('author', 'author__user')
    permission_classes = (IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """Get optimized queryset with optional filtering."""
        # Start with optimized base queryset
        queryset = self.get_base_queryset()

        # Use service to apply all filters and sorting
        filter_service = ArticleFilterService(queryset)
        queryset = filter_service.apply_filters(self.request.query_params)

        return queryset

    def create(self, request):
        serializer_context = {
            'author': request.user.profile,
            'request': request
        }
        serializer_data = request.data.get('article', {})

        serializer = self.serializer_class(
        data=serializer_data, context=serializer_context
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request):
        serializer_context = {'request': request}
        page = self.paginate_queryset(self.get_queryset())

        serializer = self.serializer_class(
            page,
            context=serializer_context,
            many=True
        )

        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, slug):
        """Retrieve single article using mixin."""
        serializer_context = {'request': request}
        article = self.get_article_by_slug(slug)

        # Increment view count using F() to avoid race condition
        # Direct update is more efficient than save()
        Article.objects.filter(pk=article.pk).update(
            view_count=F('view_count') + 1
        )

        serializer = self.serializer_class(
            article,
            context=serializer_context
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, slug):
        """Update article using mixin for retrieval."""
        serializer_context = {'request': request}
        serializer_instance = self.get_article_by_slug(slug)
        serializer_data = request.data.get('article', {})

        serializer = self.serializer_class(
            serializer_instance,
            context=serializer_context,
            data=serializer_data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def view(self, request, slug=None):
        """Increment view count for an article."""
        article = self.get_article_by_slug(slug)
        article.view_count = F('view_count') + 1
        article.save(update_fields=['view_count'])
        article.refresh_from_db()

        serializer = self.serializer_class(
            article, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending articles based on views, favorites, and comments.

        Uses the same scoring algorithm as Article.trending_score:
        - Each favorite counts as 3 points
        - Each comment counts as 2 points
        - Each view counts as 1 point
        """
        queryset = self.get_queryset().annotate(
            trending_score=Count('favorited_by') * 3 +
                          Count('comments') * 2 +
                          F('view_count')
        ).order_by('-trending_score')[:20]

        serializer_context = {'request': request}
        serializer = self.serializer_class(
            queryset, context=serializer_context, many=True
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most viewed articles."""
        queryset = self.get_queryset().order_by('-view_count')[:20]

        serializer_context = {'request': request}
        serializer = self.serializer_class(
            queryset, context=serializer_context, many=True
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def reading_list(self, request):
        """Get articles bookmarked/liked by the current user."""
        profile = request.user.profile
        queryset = self.get_queryset().filter(
            favorited_by=profile
        ).order_by('-created_at')

        serializer_context = {'request': request}
        page = self.paginate_queryset(queryset)
        serializer = self.serializer_class(
            page, context=serializer_context, many=True
        )
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export articles to CSV or JSON format."""
        format_type = request.query_params.get('format', 'json').lower()
        # Limit export to prevent memory issues with large datasets
        queryset = self.get_queryset()[:1000]

        # Use service to handle export logic
        export_service = ArticleExportService(queryset, self.serializer_class)

        if format_type == 'csv':
            return export_service.to_csv()

        # Default to JSON
        return export_service.to_json(request)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get article statistics."""
        stats_service = ArticleStatsService()
        stats = stats_service.get_all_stats()

        return Response(stats, status=status.HTTP_200_OK)


class CommentsListCreateAPIView(ArticleQueryMixin,
                                ArticleLookupMixin,
                                generics.ListCreateAPIView):
    """List and create comments for an article."""
    lookup_field = 'article__slug'
    lookup_url_kwarg = 'article_slug'
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = Comment.objects.select_related(
        'article', 'article__author', 'article__author__user',
        'author', 'author__user'
    )
    renderer_classes = (CommentJSONRenderer,)
    serializer_class = CommentSerializer

    def filter_queryset(self, queryset):
        """Filter comments by article slug and exclude soft-deleted comments."""
        filters = {self.lookup_field: self.kwargs[self.lookup_url_kwarg]}
        return queryset.filter(**filters, is_deleted=False)

    def create(self, request, article_slug=None):
        """Create a comment for the specified article."""
        data = request.data.get('comment', {})
        context = {
            'author': request.user.profile,
            'article': self.get_article_by_slug(article_slug)
        }

        serializer = self.serializer_class(data=data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentsDestroyAPIView(generics.DestroyAPIView):
    """Delete a comment by ID."""
    lookup_url_kwarg = 'comment_pk'
    permission_classes = (IsAuthenticated,)
    queryset = Comment.objects.all()

    def destroy(self, request, article_slug=None, comment_pk=None):
        """Soft delete the specified comment."""
        try:
            comment = Comment.objects.get(pk=comment_pk)
        except Comment.DoesNotExist:
            raise NotFound('A comment with this ID does not exist.')

        # Soft delete: mark as deleted instead of actually deleting
        comment.is_deleted = True
        comment.save(update_fields=['is_deleted'])
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class ArticlesFavoriteAPIView(ArticleLookupMixin, APIView):
    """Favorite/unfavorite an article."""
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def delete(self, request, article_slug=None):
        """Unfavorite an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.unfavorite(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, article_slug=None):
        """Favorite an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.favorite(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ArticlesLikeAPIView(ArticleLookupMixin, APIView):
    """Like/unlike an article (separate from favorites)."""
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def delete(self, request, article_slug=None):
        """Unlike an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.unlike_article(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, article_slug=None):
        """Like an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.like_article(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TagListAPIView(generics.ListAPIView):
    """List all available tags."""
    queryset = Tag.objects.all()
    pagination_class = None
    permission_classes = (AllowAny,)
    serializer_class = TagSerializer

    def list(self, request):
        """Return list of all tags."""
        serializer_data = self.get_queryset()
        serializer = self.serializer_class(serializer_data, many=True)

        return Response({
            'tags': serializer.data
        }, status=status.HTTP_200_OK)


class ArticlesByCategoryAPIView(ArticleQueryMixin, generics.ListAPIView):
    """List all articles in a given category.

    Example request: ``/api/articles/category/?category=technology``
    Returns published articles filtered by the category query parameter.
    Requires a category parameter; returns empty list if not provided.
    Articles are ordered by newest first (created_at descending).
    """
    serializer_class = ArticleSerializer
    permission_classes = (AllowAny,)
    renderer_classes = (ArticleJSONRenderer,)

    def get_queryset(self):
        """Filter articles by category parameter using ArticleFilterService."""
        from .services import ArticleFilterService

        category = self.request.query_params.get('category', None)
        if category is None:
            return Article.objects.none()

        # Use ArticleFilterService for consistent filtering
        base_queryset = self.get_base_queryset().filter(status='published')
        filter_service = ArticleFilterService(base_queryset)

        # Build filters dict
        filters = {'category': category, 'sort': '-date'}

        # Apply filters and return
        return filter_service.apply_filters(filters)

    def list(self, request, *args, **kwargs):
        """Return paginated list of articles in the specified category."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ArticlesFeedAPIView(ArticleQueryMixin, generics.ListAPIView):
    """Return a feed of articles from followed users using ArticleFeedService."""
    permission_classes = (IsAuthenticated,)
    queryset = Article.objects.all()
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """Get feed articles using ArticleFeedService."""
        from .services import ArticleFeedService

        base_queryset = self.get_base_queryset()
        feed_service = ArticleFeedService(base_queryset, self.request.user)

        # Get feed with default filters (published, newest first)
        return feed_service.get_feed_with_defaults()

    def list(self, request):
        """Return paginated feed of articles."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        serializer_context = {'request': request}
        serializer = self.serializer_class(
            page, context=serializer_context, many=True
        )

        return self.get_paginated_response(serializer.data)


class ArticleSearchAPIView(ArticleQueryMixin, generics.ListAPIView):
    """Search articles by full-text search across multiple fields.

    Query Parameters:
        - q: Search term to search in title, description, body, tags, and author username
        - category: Filter by category (optional)
        - status: Filter by status (default: 'published')

    Example request: ``/api/articles/search/?q=python&category=technology``
    Returns paginated list of articles matching the search criteria.
    Articles are ordered by relevance (created_at descending for results).
    """
    permission_classes = (AllowAny,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """Filter articles based on search query and optional filters."""
        search_query = self.request.query_params.get('q', '').strip()
        category = self.request.query_params.get('category', None)
        status_filter = self.request.query_params.get('status', 'published')

        search_service = ArticleSearchService(
            base_queryset=self.get_base_queryset()
        )

        return search_service.build_search_query(
            search_query=search_query,
            category=category,
            status_filter=status_filter
        )

    def list(self, request, *args, **kwargs):
        """Return paginated search results."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ArticlesDislikeAPIView(ArticleLookupMixin, APIView):
    """Dislike/undislike an article (separate from favorites and likes)."""
    permission_classes = (IsAuthenticated,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def delete(self, request, article_slug=None):
        """Undislike an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.undislike_article(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, article_slug=None):
        """Dislike an article."""
        profile = self.request.user.profile
        article = self.get_article_by_slug(article_slug)
        serializer_context = {'request': request}

        profile.dislike_article(article)
        serializer = self.serializer_class(article, context=serializer_context)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
class ArticlesByDateRangeAPIView(ArticleQueryMixin, generics.ListAPIView):
    """List articles filtered by date range.

    Query Parameters:
        - start_date: Start date in format YYYY-MM-DD (required)
        - end_date: End date in format YYYY-MM-DD (required)
        - status: Filter by status (default: 'published')

    Supported date formats:
        - YYYY-MM-DD (ISO date)
        - YYYY-MM-DDTHH:MM:SS (ISO datetime)
        - YYYY-MM-DD HH:MM:SS (SQL datetime)

    Example request: ``/api/articles/date-range/?start_date=2024-01-01&end_date=2024-12-31``
    Returns paginated list of articles created within the specified date range.
    Articles are ordered by newest first (created_at descending).
    """
    permission_classes = (AllowAny,)
    renderer_classes = (ArticleJSONRenderer,)
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """Filter articles by date range parameters using ArticleFilterService."""
        from .services import ArticleFilterService

        start_date_str = self.request.query_params.get('start_date', None)
        end_date_str = self.request.query_params.get('end_date', None)
        status_filter = self.request.query_params.get('status', 'published')

        # Validate that both dates are provided
        if not start_date_str or not end_date_str:
            return Article.objects.none()

        # Use ArticleFilterService for consistent filtering with proper date parsing
        base_queryset = self.get_base_queryset()
        filter_service = ArticleFilterService(base_queryset)

        # Build filters dict
        filters = {
            'start_date': start_date_str,
            'end_date': end_date_str,
            'status': status_filter,
            'sort': '-date'
        }

        # Apply filters and return
        return filter_service.apply_filters(filters)

    def list(self, request, *args, **kwargs):
        """Return paginated list of articles in the specified date range."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)