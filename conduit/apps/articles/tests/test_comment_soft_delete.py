"""Tests for comment soft delete functionality."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from conduit.apps.articles.models import Article, Comment
from conduit.apps.profiles.models import Profile


User = get_user_model()


class CommentSoftDeleteTestCase(TestCase):
    """Test suite for comment soft delete feature."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users
        self.author_user = User.objects.create_user(
            username='author',
            email='author@example.com',
            password='testpass123'
        )
        self.author_profile = self.author_user.profile

        self.commenter_user = User.objects.create_user(
            username='commenter',
            email='commenter@example.com',
            password='testpass123'
        )
        self.commenter_profile = self.commenter_user.profile

        # Create article
        self.article = Article.objects.create(
            title='Test Article',
            slug='test-article',
            description='Test Description',
            body='Test Body',
            author=self.author_profile
        )

        # Create comment
        self.comment = Comment.objects.create(
            article=self.article,
            author=self.commenter_profile,
            body='Test comment body'
        )

    def test_comment_has_is_deleted_field(self):
        """Test that Comment model has is_deleted field."""
        self.assertTrue(hasattr(self.comment, 'is_deleted'))
        self.assertFalse(self.comment.is_deleted)

    def test_comment_is_deleted_defaults_to_false(self):
        """Test that new comments have is_deleted=False."""
        new_comment = Comment.objects.create(
            article=self.article,
            author=self.commenter_profile,
            body='Another test comment'
        )
        self.assertFalse(new_comment.is_deleted)

    def test_soft_delete_via_model(self):
        """Test soft delete by setting is_deleted directly."""
        self.comment.is_deleted = True
        self.comment.save()

        # Refresh from database
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)

        # Comment should still exist in database
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_list_comments_excludes_deleted(self):
        """Test that deleted comments are excluded from list views."""
        # Create additional comments
        comment2 = Comment.objects.create(
            article=self.article,
            author=self.commenter_profile,
            body='Second comment'
        )

        # Soft delete first comment
        self.comment.is_deleted = True
        self.comment.save()

        # Authenticate and get comments
        self.client.force_authenticate(user=self.author_user)
        url = f'/api/articles/{self.article.slug}/comments'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comments_data = response.data['comments']
        comment_ids = [c['id'] for c in comments_data]

        # Only non-deleted comments should be returned
        self.assertNotIn(self.comment.id, comment_ids)
        self.assertIn(comment2.id, comment_ids)
        self.assertEqual(len(comments_data), 1)

    def test_delete_api_soft_deletes_comment(self):
        """Test that DELETE endpoint soft deletes instead of hard deleting."""
        self.client.force_authenticate(user=self.commenter_user)
        url = f'/api/articles/{self.article.slug}/comments/{self.comment.pk}'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Refresh from database
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)

        # Comment should still exist in database
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_deleted_comment_not_retrievable(self):
        """Test that soft-deleted comments are not returned in list."""
        # Soft delete comment
        self.comment.is_deleted = True
        self.comment.save()

        self.client.force_authenticate(user=self.author_user)
        url = f'/api/articles/{self.article.slug}/comments'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comments_data = response.data['comments']

        # No comments should be returned
        self.assertEqual(len(comments_data), 0)

    def test_multiple_articles_with_deleted_comments(self):
        """Test that soft delete works correctly across multiple articles."""
        # Create second article
        article2 = Article.objects.create(
            title='Second Article',
            slug='second-article',
            description='Second Description',
            body='Second Body',
            author=self.author_profile
        )

        # Create comments on both articles
        comment2 = Comment.objects.create(
            article=article2,
            author=self.commenter_profile,
            body='Comment on article 2'
        )

        # Delete comment on first article
        self.comment.is_deleted = True
        self.comment.save()

        self.client.force_authenticate(user=self.author_user)

        # Check first article - should have no comments
        url1 = f'/api/articles/{self.article.slug}/comments'
        response1 = self.client.get(url1)
        self.assertEqual(len(response1.data['comments']), 0)

        # Check second article - should have one comment
        url2 = f'/api/articles/{article2.slug}/comments'
        response2 = self.client.get(url2)
        self.assertEqual(len(response2.data['comments']), 1)
        self.assertEqual(response2.data['comments'][0]['id'], comment2.id)

    def test_create_comment_after_soft_delete(self):
        """Test that creating new comments works after soft deletes."""
        # Soft delete existing comment
        self.comment.is_deleted = True
        self.comment.save()

        # Create new comment via API
        self.client.force_authenticate(user=self.commenter_user)
        url = f'/api/articles/{self.article.slug}/comments'
        data = {
            'comment': {
                'body': 'New comment after delete'
            }
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify only the new comment is visible
        list_response = self.client.get(url)
        self.assertEqual(len(list_response.data['comments']), 1)
        self.assertEqual(
            list_response.data['comments'][0]['body'],
            'New comment after delete'
        )

    def test_is_deleted_field_is_indexed(self):
        """Test that is_deleted field has database index."""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type='index' AND tbl_name='articles_comment'
                AND sql LIKE '%is_deleted%'
            """)
            result = cursor.fetchone()
            # At least one index should involve is_deleted
            self.assertIsNotNone(result)