from django.urls import include, path, re_path

app_name = 'articles'

from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet, ArticlesFavoriteAPIView, ArticlesFeedAPIView,
    CommentsListCreateAPIView, CommentsDestroyAPIView, TagListAPIView,
    ArticlesByCategoryAPIView, ArticlesLikeAPIView, ArticlesDislikeAPIView,
    ArticleSearchAPIView, ArticlesByDateRangeAPIView,
)

router = DefaultRouter(trailing_slash=True)
router.register(r'articles', ArticleViewSet)

urlpatterns = [
    re_path(r'^', include(router.urls)),

    re_path(r'^articles/feed/?$', ArticlesFeedAPIView.as_view()),

    re_path(r'^articles/search/?$', ArticleSearchAPIView.as_view()),

    re_path(r'^articles/category/?$', ArticlesByCategoryAPIView.as_view()),

    re_path(r'^articles/date-range/?$', ArticlesByDateRangeAPIView.as_view()),

    re_path(r'^articles/(?P<article_slug>[-\w]+)/favorite/?$',
        ArticlesFavoriteAPIView.as_view()),

    re_path(r'^articles/(?P<article_slug>[-\w]+)/like/?$',
        ArticlesLikeAPIView.as_view()),
    re_path(r'^articles/(?P<article_slug>[-\w]+)/dislike/?$',
        ArticlesDislikeAPIView.as_view()),

    re_path(r'^articles/(?P<article_slug>[-\w]+)/comments/?$', 
        CommentsListCreateAPIView.as_view()),

    re_path(r'^articles/(?P<article_slug>[-\w]+)/comments/(?P<comment_pk>[\d]+)/?$',
        CommentsDestroyAPIView.as_view()),

    re_path(r'^tags/?$', TagListAPIView.as_view()),
]
