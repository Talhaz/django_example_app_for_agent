from rest_framework import serializers
from .models import Magazine
from .magazine_utils import safe_method_return


class MagazineSerializer(serializers.ModelSerializer):
    """
    Serializer for the Magazine model.

    Handles serialization and deserialization with proper error handling
    for database-related operations.
    """

    article_count = serializers.SerializerMethodField()
    has_active_articles = serializers.SerializerMethodField()
    featured_count = serializers.SerializerMethodField()

    class Meta:
        model = Magazine
        fields = (
            'id', 'title', 'slug', 'description', 'is_active',
            'created_at', 'updated_at',
            'article_count', 'has_active_articles', 'featured_count'
        )
        read_only_fields = ('slug', 'created_at', 'updated_at')

    @safe_method_return(0)
    def get_article_count(self, obj):
        """
        Get the count of articles in this magazine.
        """
        return obj.article_count

    @safe_method_return(False)
    def get_has_active_articles(self, obj):
        """
        Check if the magazine has active articles.
        """
        return obj.has_active_articles()

    @safe_method_return(0)
    def get_featured_count(self, obj):
        """
        Get the count of featured articles in this magazine.
        """
        return obj.get_featured_count()