from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from conduit.apps.reviews.models import Review
from conduit.apps.reviews.serializers import ReviewSerializer, ReviewCreateSerializer
from conduit.apps.articles.models import Article


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reviews.
    - List all reviews for an article
    - Create a review for an article (authenticated)
    - Retrieve, update, delete own reviews
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filter reviews by article if article_slug is provided in query params.
        """
        queryset = Review.objects.select_related('author', 'article').all()
        article_slug = self.request.query_params.get('article_slug')
        if article_slug:
            queryset = queryset.filter(article__slug=article_slug)
        return queryset

    def get_serializer_class(self):
        """
        Use ReviewCreateSerializer for creating reviews,
        ReviewSerializer for other operations.
        """
        if self.action == 'create':
            return ReviewCreateSerializer
        return ReviewSerializer

    def perform_create(self, serializer):
        """
        Set the author to the current user when creating a review.
        """
        serializer.save(author=self.request.user)

    def get_permissions(self):
        """
        Custom permission handling:
        - Only the review owner can update or delete
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """
        Get all reviews by the current user.
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        reviews = Review.objects.filter(author=request.user).select_related('article')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='article/(?P<article_slug>[^/.]+)')
    def by_article(self, request, article_slug=None):
        """
        Get all reviews for a specific article by slug.
        """
        try:
            article = Article.objects.get(slug=article_slug)
            reviews = Review.objects.filter(article=article).select_related('author')
            serializer = ReviewSerializer(reviews, many=True)
            return Response(serializer.data)
        except Article.DoesNotExist:
            return Response(
                {'error': 'Article not found'},
                status=status.HTTP_404_NOT_FOUND
            )