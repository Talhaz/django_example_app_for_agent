from django.contrib import admin
from conduit.apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('article', 'author', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('article__title', 'author__username', 'body')
    readonly_fields = ('created_at', 'updated_at')