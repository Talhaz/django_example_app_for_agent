from django.test import TestCase
from conduit.apps.authentication.models import User
from conduit.apps.articles.models import Article
from conduit.apps.reviews.models import Review


class ReviewModelTest(TestCase):
    """Test cases for Review model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.article = Article.objects.create(
            title='Test Article',
            description='Test Description',
            body='Test Body',
            author=self.user
        )

    def test_create_review(self):
        """Test creating a review."""
        review = Review.objects.create(
            article=self.article,
            author=self.user,
            rating=5,
            body='Great article!'
        )
        self.assertEqual(review.article, self.article)
        self.assertEqual(review.author, self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.body, 'Great article!')

    def test_review_str(self):
        """Test review string representation."""
        review = Review.objects.create(
            article=self.article,
            author=self.user,
            rating=4,
            body='Good article'
        )
        expected = f'{self.user.username} - {self.article.slug}: 4/5'
        self.assertEqual(str(review), expected)

    def test_unique_review_per_user_per_article(self):
        """Test that a user can only review an article once."""
        Review.objects.create(
            article=self.article,
            author=self.user,
            rating=5,
            body='First review'
        )
        # Try to create another review for the same article by the same user
        with self.assertRaises(Exception):
            Review.objects.create(
                article=self.article,
                author=self.user,
                rating=4,
                body='Second review'
            )

    def test_rating_choices(self):
        """Test that only valid ratings are allowed."""
        valid_ratings = [1, 2, 3, 4, 5]
        for rating in valid_ratings:
            review = Review.objects.create(
                article=self.article,
                author=self.user,
                rating=rating,
                body=f'Rating {rating}'
            )
            self.assertEqual(review.rating, rating)

    def test_ordering(self):
        """Test that reviews are ordered by createdAt descending."""
        review1 = Review.objects.create(
            article=self.article,
            author=self.user,
            rating=5,
            body='First review'
        )
        review2 = Review.objects.create(
            article=self.article,
            author=self.user,
            rating=4,
            body='Second review'
        )
        # Create another user for the second review
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        review3 = Review.objects.create(
            article=self.article,
            author=user2,
            rating=3,
            body='Third review'
        )
        reviews = list(Review.objects.all())
        self.assertEqual(reviews[0], review3)
        self.assertEqual(reviews[1], review2)
        self.assertEqual(reviews[2], review1)