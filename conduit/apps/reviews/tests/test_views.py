from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from conduit.apps.authentication.models import User
from conduit.apps.articles.models import Article
from conduit.apps.reviews.models import Review


class ReviewViewSetTest(TestCase):
    """Test cases for ReviewViewSet."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.article = Article.objects.create(
            title='Test Article',
            description='Test Description',
            body='Test Body',
            author=self.user
        )
        self.review = Review.objects.create(
            article=self.article,
            author=self.user,
            rating=5,
            body='Great article!'
        )

    def test_list_reviews(self):
        """Test listing all reviews."""
        response = self.client.get('/api/reviews')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_reviews_by_article(self):
        """Test listing reviews filtered by article."""
        response = self.client.get(f'/api/reviews?article_slug={self.article.slug}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['article'], self.article.slug)

    def test_create_review_authenticated(self):
        """Test creating a review when authenticated."""
        self.client.force_authenticate(user=self.user2)
        data = {
            'article': self.article.id,
            'rating': 4,
            'body': 'Good article'
        }
        response = self.client.post('/api/reviews', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 2)

    def test_create_review_unauthenticated(self):
        """Test creating a review when not authenticated."""
        data = {
            'article': self.article.id,
            'rating': 4,
            'body': 'Good article'
        }
        response = self.client.post('/api/reviews', data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_duplicate_review(self):
        """Test that a user cannot create multiple reviews for the same article."""
        self.client.force_authenticate(user=self.user)
        data = {
            'article': self.article.id,
            'rating': 4,
            'body': 'Another review'
        }
        response = self.client.post('/api/reviews', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_review(self):
        """Test retrieving a specific review."""
        response = self.client.get(f'/api/reviews/{self.review.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.review.id)

    def test_update_review_owner(self):
        """Test updating a review as the owner."""
        self.client.force_authenticate(user=self.user)
        data = {
            'rating': 4,
            'body': 'Updated review'
        }
        response = self.client.patch(f'/api/reviews/{self.review.id}', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 4)
        self.assertEqual(self.review.body, 'Updated review')

    def test_update_review_non_owner(self):
        """Test updating a review as a non-owner."""
        self.client.force_authenticate(user=self.user2)
        data = {
            'rating': 4,
            'body': 'Updated review'
        }
        response = self.client.patch(f'/api/reviews/{self.review.id}', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_review_owner(self):
        """Test deleting a review as the owner."""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/reviews/{self.review.id}')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Review.objects.count(), 0)

    def test_delete_review_non_owner(self):
        """Test deleting a review as a non-owner."""
        self.client.force_authenticate(user=self.user2)
        response = self.client.delete(f'/api/reviews/{self.review.id}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_reviews_authenticated(self):
        """Test getting reviews by the current user."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/reviews/my_reviews')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_my_reviews_unauthenticated(self):
        """Test getting reviews when not authenticated."""
        response = self.client.get('/api/reviews/my_reviews')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_by_article(self):
        """Test getting reviews for a specific article by slug."""
        response = self.client.get(f'/api/reviews/article/{self.article.slug}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_by_article_not_found(self):
        """Test getting reviews for a non-existent article."""
        response = self.client.get('/api/reviews/article/nonexistent')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)