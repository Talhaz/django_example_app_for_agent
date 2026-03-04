from rest_framework import serializers
from conduit.apps.reviews.models import Review
from conduit.apps.authentication.models import User
from conduit.apps.articles.models import Article


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for Review model.
    """
    author = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username'
    )
    article = serializers.SlugRelatedField(
        read_only=True,
        slug_field='slug'
    )

    class Meta:
        model = Review
        fields = (
            'id',
            'article',
            'author',
            'rating',
            'body',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = ('createdAt', 'updatedAt')


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a review.
    """
    class Meta:
        model = Review
        fields = (
            'article',
            'rating',
            'body',
        )

    def validate_rating(self, value):
        """Validate that rating is between 1 and 5."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, data):
        """
        Validate that the user hasn't already reviewed this article.
        """
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            article = data.get('article')
            if Review.objects.filter(article=article, author=request.user).exists():
                raise serializers.ValidationError(
                    "You have already reviewed this article."
                )
        return data