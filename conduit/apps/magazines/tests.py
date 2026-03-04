from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Magazine
from conduit.apps.articles.models import Article

User = get_user_model()


class MagazineViewSetTestCase(TestCase):
    """Test cases for MagazineViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )

        # Create magazines
        self.magazine1 = Magazine.objects.create(
            title='Tech Magazine',
            description='A magazine about technology',
            slug='tech-magazine',
            is_active=True
        )
        self.magazine2 = Magazine.objects.create(
            title='Food Magazine',
            description='A magazine about food',
            slug='food-magazine',
            is_active=True
        )
        self.magazine3 = Magazine.objects.create(
            title='Inactive Magazine',
            description='An inactive magazine',
            slug='inactive-magazine',
            is_active=False
        )

        # Associate users with magazines
        self.user1.profile.magazine = self.magazine1
        self.user1.profile.save()
        self.user2.profile.magazine = self.magazine2
        self.user2.profile.save()

    def test_list_magazines(self):
        """Test listing all magazines"""
        response = self.client.get('/magazines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Only active magazines by default

    def test_list_magazines_with_inactive(self):
        """Test listing magazines with include_inactive=true"""
        response = self.client.get('/magazines/?include_inactive=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # All magazines

    def test_retrieve_magazine(self):
        """Test retrieving a single magazine"""
        response = self.client.get(f'/magazines/{self.magazine1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Tech Magazine')

    def test_active_magazines(self):
        """Test the active custom action"""
        response = self.client.get('/magazines/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_magazine(self):
        """Test creating a new magazine"""
        data = {
            'title': 'New Magazine',
            'description': 'A new magazine',
            'slug': 'new-magazine'
        }
        response = self.client.post('/magazines/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Magazine.objects.count(), 4)

    def test_update_magazine(self):
        """Test updating a magazine"""
        data = {
            'title': 'Updated Tech Magazine',
            'description': 'Updated description',
            'slug': 'tech-magazine'
        }
        response = self.client.put(f'/magazines/{self.magazine1.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.magazine1.refresh_from_db()
        self.assertEqual(self.magazine1.title, 'Updated Tech Magazine')

    def test_partial_update_magazine(self):
        """Test partially updating a magazine"""
        data = {'title': 'Partially Updated Magazine'}
        response = self.client.patch(f'/magazines/{self.magazine1.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.magazine1.refresh_from_db()
        self.assertEqual(self.magazine1.title, 'Partially Updated Magazine')

    def test_delete_magazine(self):
        """Test deleting a magazine"""
        response = self.client.delete(f'/magazines/{self.magazine1.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Magazine.objects.count(), 2)

    def test_activate_magazine(self):
        """Test activating a magazine"""
        response = self.client.post(f'/magazines/{self.magazine3.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.magazine3.refresh_from_db()
        self.assertTrue(self.magazine3.is_active)

    def test_deactivate_magazine(self):
        """Test deactivating a magazine"""
        response = self.client.post(f'/magazines/{self.magazine1.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.magazine1.refresh_from_db()
        self.assertFalse(self.magazine1.is_active)

    def test_magazine_articles(self):
        """Test getting articles for a magazine"""
        # Create some articles
        Article.objects.create(
            title='Test Article 1',
            slug='test-article-1',
            description='Test description',
            author=self.user1,
            status='published'
        )
        Article.objects.create(
            title='Test Article 2',
            slug='test-article-2',
            description='Test description 2',
            author=self.user1,
            status='published'
        )

        response = self.client.get(f'/magazines/{self.magazine1.id}/articles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['magazine'], 'Tech Magazine')
        self.assertEqual(response.data['article_count'], 2)
        self.assertEqual(len(response.data['articles']), 2)

    def test_magazine_search(self):
        """Test searching magazines"""
        response = self.client.get('/magazines/?search=Tech')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Tech Magazine')

    def test_magazine_ordering(self):
        """Test ordering magazines"""
        response = self.client.get('/magazines/?ordering=title')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['title'], 'Food Magazine')
        self.assertEqual(response.data[1]['title'], 'Tech Magazine')