from functools import wraps
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ParseError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Q, OuterRef, Subquery
from django.db import DatabaseError, IntegrityError
from .models import Magazine, FEATURED_ARTICLE_THRESHOLD
from .serializers import MagazineSerializer


def handle_database_errors(action_name=None):
    """
    Decorator to handle database errors consistently across view methods.

    Args:
        action_name: Name of the action for error messages (defaults to 'operation')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            action_text = action_name or func.__name__.replace('_', ' ')
            try:
                return func(self, *args, **kwargs)
            except (DatabaseError, IntegrityError) as e:
                raise ParseError(f'Database error while {action_text}: {str(e)}')
            except (ValueError, TypeError):
                raise ParseError(f'Invalid input for {action_text}')
            except Magazine.DoesNotExist:
                raise NotFound('Magazine not found.')
            except Exception as e:
                raise ParseError(f'Error {action_text}: {str(e)}')
        return wrapper
    return decorator


class MagazineViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Magazine model with full CRUD operations.

    Actions:
        - list: List all magazines (with filtering, search, ordering)
        - retrieve: Get a specific magazine by ID
        - create: Create a new magazine
        - update: Update a magazine (full update)
        - partial_update: Partially update a magazine
        - destroy: Delete a magazine
        - active: Custom action to list only active magazines
        - featured: Custom action to list featured magazines
    """
    queryset = Magazine.objects.all()
    serializer_class = MagazineSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def _get_article_count_subquery(self):
        """
        Generate subquery for counting articles per magazine.

        Returns:
            Subquery: Subquery expression for article count annotation
        """
        from conduit.apps.articles.models import Article

        return Subquery(
            Article.objects.filter(
                author__magazine=OuterRef('pk'),
                status='published'
            ).values('author__magazine').annotate(
                count=Count('id')
            ).values('count')[:1]
        )

    def get_queryset(self):
        """
        Optionally filter queryset to show only active magazines.
        Use ?include_inactive=true to include inactive magazines.

        Optimizes queries by prefetching related profiles and their articles.

        Raises:
            ParseError: If there's an error parsing query parameters
            DatabaseError: If there's a database error during query execution
        """
        try:
            queryset = super().get_queryset()
            include_inactive = self.request.query_params.get('include_inactive', 'false').lower() == 'true'

            if not include_inactive:
                queryset = queryset.filter(is_active=True)

            # Annotate with article count using helper method
            queryset = queryset.annotate(article_count=self._get_article_count_subquery())

            # Prefetch profiles and their published articles to avoid N+1 queries
            return queryset.prefetch_related(
                'profiles__articles'
            ).select_related()

        except (DatabaseError, IntegrityError) as e:
            raise ParseError(
                detail=f"Database error while retrieving magazines: {str(e)}"
            )
        except Exception as e:
            raise ParseError(
                detail=f"Error processing magazine query: {str(e)}"
            )

    def _paginate_and_respond(self, queryset):
        """
        Handle pagination for a queryset and return appropriate response.

        Args:
            queryset: QuerySet to paginate

        Returns:
            Response: Paginated response if pagination is enabled, else direct response
        """
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _validate_pagination_params(self, request):
        """
        Validate pagination parameters from request.

        Args:
            request: The HTTP request object

        Returns:
            tuple: (limit, offset) validated values

        Raises:
            ParseError: If parameters are invalid
        """
        try:
            limit = int(request.query_params.get('limit', 10))
            offset = int(request.query_params.get('offset', 0))

            if limit < 1 or limit > 100:
                raise ParseError('Limit must be between 1 and 100.')

            if offset < 0:
                raise ParseError('Offset must be a non-negative integer.')

            return limit, offset

        except (ValueError, TypeError):
            raise ParseError('Invalid limit or offset value. Must be an integer.')

    @action(detail=False, methods=['get'])
    @handle_database_errors(action_name='retrieving active magazines')
    def active(self, request):
        """
        Custom action to get only active magazines.

        GET /magazines/active/
        """
        # get_queryset() already filters is_active=True by default
        active_magazines = self.get_queryset()
        return self._paginate_and_respond(active_magazines)

    @action(detail=False, methods=['get'])
    @handle_database_errors(action_name='retrieving featured magazines')
    def featured(self, request):
        """
        Custom action to get featured magazines.
        Featured magazines have at least FEATURED_ARTICLE_THRESHOLD articles and are active.

        GET /magazines/featured/
        """
        # Annotate with article count and filter by threshold
        featured_magazines = (
            self.get_queryset()
            .annotate(article_count=self._get_article_count_subquery())
            .filter(article_count__gte=self.FEATURED_ARTICLE_THRESHOLD)
        )

        return self._paginate_and_respond(featured_magazines)

    @action(detail=True, methods=['get'])
    @handle_database_errors(action_name='retrieving articles for magazine')
    def articles(self, request, pk=None):
        """
        Custom action to get articles for a specific magazine.

        GET /magazines/{id}/articles/
        """
        magazine = self.get_object()
        limit, offset = self._validate_pagination_params(request)

        # Get articles with annotated count to avoid extra query
        articles = magazine.get_active_articles(limit=limit, offset=offset, annotate_count=True)

        # Get total count from annotation (first article has the count)
        article_count = articles.first().total_count if articles.exists() else 0

        # Return basic article information
        articles_data = [
            {
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'description': article.description,
                'created_at': article.created_at,
                'author': article.author.username
            }
            for article in articles
        ]

        return Response({
            'magazine': magazine.title,
            'article_count': article_count,
            'articles': articles_data
        })

    @action(detail=True, methods=['post'])
    @handle_database_errors(action_name='activating magazine')
    def activate(self, request, pk=None):
        """
        Custom action to activate a magazine.

        POST /magazines/{id}/activate/
        """
        return self._set_active_status(pk, active=True)

    @action(detail=True, methods=['post'])
    @handle_database_errors(action_name='deactivating magazine')
    def deactivate(self, request, pk=None):
        """
        Custom action to deactivate a magazine.

        POST /magazines/{id}/deactivate/
        """
        return self._set_active_status(pk, active=False)

    def _set_active_status(self, pk, active):
        """
        Helper method to set magazine active status.

        Args:
            pk: Primary key of the magazine
            active: Boolean indicating active status

        Returns:
            Response: Success response with magazine data

        Raises:
            NotFound: If the magazine does not exist
            ParseError: If there's an error saving the magazine
        """
        magazine = self.get_object()
        magazine.is_active = active
        magazine.save(update_fields=['is_active'])

        serializer = self.get_serializer(magazine)
        status_text = 'activated' if active else 'deactivated'
        return Response({
            'message': f'Magazine {status_text} successfully',
            'magazine': serializer.data
        })