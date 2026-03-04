from rest_framework import serializers

from conduit.apps.profiles.serializers import ProfileSerializer

from .models import Article, Comment, Tag
from .relations import TagRelatedField


class ArticleSerializer(serializers.ModelSerializer):
    author = ProfileSerializer(read_only=True)
    description = serializers.CharField(
        required=False,
        allow_blank=False,
        error_messages={'blank': 'Description cannot be blank if provided.'}
    )
    slug = serializers.SlugField(
        required=False,
        error_messages={'invalid': 'Slug must contain only letters, numbers, hyphens, and underscores.'}
    )
    title = serializers.CharField(
        error_messages={'required': 'Title is required.', 'blank': 'Title cannot be blank.'}
    )
    body = serializers.CharField(
        error_messages={'required': 'Article body is required.', 'blank': 'Article body cannot be blank.'}
    )
    status = serializers.CharField(
        required=False,
        error_messages={'invalid_choice': 'Invalid status. Must be draft, published, or archived.'}
    )

    favorited = serializers.SerializerMethodField()
    favoritesCount = serializers.SerializerMethodField(
        method_name='get_favorites_count'
    )

    liked = serializers.SerializerMethodField()
    likesCount = serializers.SerializerMethodField(
        method_name='get_likes_count'
    )

    disliked = serializers.SerializerMethodField()
    dislikesCount = serializers.SerializerMethodField(
        method_name='get_dislikes_count'
    )

    tagList = TagRelatedField(many=True, required=False, source='tags')

    # Django REST Framework makes it possible to create a read-only field that
    # gets it's value by calling a function. In this case, the client expects
    # `created_at` to be called `createdAt` and `updated_at` to be `updatedAt`.
    # `serializers.SerializerMethodField` is a good way to avoid having the
    # requirements of the client leak into our API.
    createdAt = serializers.SerializerMethodField(method_name='get_created_at')
    updatedAt = serializers.SerializerMethodField(method_name='get_updated_at')
    summary = serializers.SerializerMethodField()

    # Enhanced fields
    commentsCount = serializers.SerializerMethodField(
        method_name='get_comments_count'
    )
    viewCount = serializers.ReadOnlyField(source='view_count')
    readingTime = serializers.ReadOnlyField(source='reading_time')
    publishedAt = serializers.SerializerMethodField(
        method_name='get_published_at'
    )

    class Meta:
        model = Article
        fields = (
            'author',
            'body',
            'summary',
            'createdAt',
            'description',
            'favorited',
            'favoritesCount',
            'liked',
            'likesCount',
            'disliked',
            'dislikesCount',
            'slug',
            'tagList',
            'title',
            'updatedAt',
            'status',
            'category',
            'commentsCount',
            'viewCount',
            'readingTime',
            'publishedAt',
        )
        extra_kwargs = {
            'title': {'min_length': 1},
            'body': {'min_length': 1},
        }

    def create(self, validated_data):
        author = self.context.get('author', None)

        tags = validated_data.pop('tags', [])

        article = Article.objects.create(author=author, **validated_data)

        for tag in tags:
            article.tags.add(tag)

        return article

    def validate(self, attrs):
        """
        Cross-field validation for Article serializer.
        """
        title = attrs.get('title')
        body = attrs.get('body')
        description = attrs.get('description')
        slug = attrs.get('slug')
        status = attrs.get('status')

        # Validate title length (reasonable limits)
        if title and len(title) > 255:
            raise serializers.ValidationError({
                'title': 'Title cannot exceed 255 characters.'
            })

        # Validate body is not too long
        if body and len(body) > 100000:
            raise serializers.ValidationError({
                'body': 'Article body is too long. Maximum 100,000 characters.'
            })

        # Validate description length if provided
        if description and len(description) > 5000:
            raise serializers.ValidationError({
                'description': 'Description cannot exceed 5,000 characters.'
            })

        # Validate slug uniqueness if provided (for update scenarios)
        if slug and self.instance and slug != self.instance.slug:
            if Article.objects.filter(slug=slug).exists():
                raise serializers.ValidationError({
                    'slug': 'An article with this slug already exists.'
                })

        # If status is 'published', require both title and body
        if status == 'published':
            if not title:
                raise serializers.ValidationError({
                    'title': 'Title is required to publish an article.'
                })
            if not body:
                raise serializers.ValidationError({
                    'body': 'Article body is required to publish an article.'
                })

        return attrs

    def get_created_at(self, instance):
        return instance.created_at.isoformat()

    def get_favorited(self, instance):
        request = self.context.get('request', None)

        if request is None:
            return False

        if not request.user.is_authenticated:
            return False

        return request.user.profile.has_favorited(instance)

    def get_favorites_count(self, instance):
        return instance.favorited_by.count()

    def get_liked(self, instance):
        request = self.context.get('request', None)

        if request is None:
            return False

        if not request.user.is_authenticated:
            return False

        return request.user.profile.has_liked_article(instance)

    def get_likes_count(self, instance):
        return instance.likes.count()

    def get_disliked(self, instance):
        request = self.context.get('request', None)

        if request is None:
            return False

        if not request.user.is_authenticated:
            return False

        return request.user.profile in instance.dislikes.all()

    def get_dislikes_count(self, instance):
        return instance.dislikes.count()

    def get_updated_at(self, instance):
        return instance.updated_at.isoformat()

    def get_summary(self, instance):
        """Return a truncated summary of the article body (max 100 chars)."""
        body = getattr(instance, 'body', '')
        if len(body) > 100:
            return body[:100]
        return body

    def get_comments_count(self, instance):
        """Return the count of comments for this article."""
        return instance.comments.count()

    def get_published_at(self, instance):
        """Return the published_at timestamp if available."""
        if instance.published_at:
            return instance.published_at.isoformat()
        return None


class CommentSerializer(serializers.ModelSerializer):
    author = ProfileSerializer(required=False)
    body = serializers.CharField(
        error_messages={
            'required': 'Comment body is required.',
            'blank': 'Comment body cannot be blank.'
        }
    )

    createdAt = serializers.SerializerMethodField(method_name='get_created_at')
    updatedAt = serializers.SerializerMethodField(method_name='get_updated_at')

    class Meta:
        model = Comment
        fields = (
            'id',
            'author',
            'body',
            'createdAt',
            'updatedAt',
        )
        extra_kwargs = {
            'body': {'min_length': 1},
        }

    def create(self, validated_data):
        article = self.context['article']
        author = self.context['author']

        return Comment.objects.create(
            author=author, article=article, **validated_data
        )

    def validate(self, attrs):
        """
        Cross-field validation for Comment serializer.
        """
        body = attrs.get('body')

        # Validate body length
        if body and len(body) > 10000:
            raise serializers.ValidationError({
                'body': 'Comment is too long. Maximum 10,000 characters.'
            })

        # Strip leading/trailing whitespace
        if body:
            attrs['body'] = body.strip()

        return attrs

    def get_created_at(self, instance):
        return instance.created_at.isoformat()

    def get_updated_at(self, instance):
        return instance.updated_at.isoformat()


class TagSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        error_messages={
            'required': 'Tag name is required.',
            'blank': 'Tag name cannot be blank.'
        }
    )

    class Meta:
        model = Tag
        fields = ('name',)

    def validate(self, attrs):
        """
        Validate tag name.
        """
        name = attrs.get('name')

        if name:
            # Normalize tag name
            name = name.lower().strip()
            attrs['name'] = name

            # Validate length
            if len(name) > 50:
                raise serializers.ValidationError({
                    'name': 'Tag name cannot exceed 50 characters.'
                })

            # Validate characters (alphanumeric and hyphens/underscores)
            if not name.replace('-', '').replace('_', '').isalnum():
                raise serializers.ValidationError({
                    'name': 'Tag name can only contain letters, numbers, hyphens, and underscores.'
                })

        return attrs

    def to_representation(self, obj):
        return obj.name
