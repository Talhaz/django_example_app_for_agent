from django.db import models
from conduit.apps.core.models import TimestampedModel
from conduit.apps.authentication.models import User
from conduit.apps.articles.models import Article


class Review(TimestampedModel):
    """
    Review model for articles.
    Allows users to rate and review articles.
    """
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]

    article = models.ForeignKey(
        Article,
        related_name='reviews',
        on_delete=models.CASCADE,
        help_text='The article being reviewed'
    )
    author = models.ForeignKey(
        User,
        related_name='reviews',
        on_delete=models.CASCADE,
        help_text='The user who wrote the review'
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        help_text='Rating from 1 to 5'
    )
    body = models.TextField(
        help_text='Review content'
    )

    class Meta:
        ordering = ['-created_at']
        unique_together = ('article', 'author')  # One review per user per article

    def __str__(self):
        return f'{self.author.username} - {self.article.slug}: {self.rating}/5'