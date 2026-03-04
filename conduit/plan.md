# Implementation Plan – New Django App *magazines*

## Goal
Create a brand‑new Django app called **magazines** that provides models for magazines and their issues, along with DRF serializers, viewsets, and URL routing.

---

## Step‑by‑step Plan

| # | Action | Details | Files Affected |
|---|--------|---------|----------------|
| 1 | **Create the app** | Run `django_command(command_type="startapp", app="magazines")` | – (creates `magazines/` package) |
| 2 | **Add to INSTALLED_APPS** | Append `'magazines'` to the `INSTALLED_APPS` list in `conduit/settings.py`. | `conduit/settings.py` |
| 3 | **Define models** | *Magazine*: `owner` (FK to `profiles.Profile`), `title`, `description`.<br>*Issue*: `magazine` (FK), `number`, `pub_date`. Add `unique_together` for `(magazine, number)` and ordering. | `magazines/models.py` |
| 4 | **Make migrations** | `django_command(command_type="makemigrations", app="magazines")` | – |
| 5 | **Apply migrations** | `django_command(command_type="migrate")` | – |
| 6 | **Create serializers** | `MagazineSerializer` (includes read‑only nested `issues`) and `IssueSerializer`. | `magazines/serializers.py` |
| 7 | **Create viewsets** | `MagazineViewSet` and `IssueViewSet` using `ModelViewSet`, permission `IsAuthenticatedOrReadOnly`. | `magazines/views.py` |
| 8 | **Add router & URLs** | Create `magazines/urls.py` with a `DefaultRouter` registering the two viewsets under `magazines/` and `issues/` prefixes. | `magazines/urls.py` |
| 9 | **Include app URLs in project** | In the main `conduit/urls.py` add `path('api/', include('magazines.urls'))`. | `conduit/urls.py` |
|10| **(Optional) Permissions** | If only owners may edit magazines, add a custom permission class in `magazines/permissions.py` and reference it in the viewsets. | `magazines/permissions.py` (optional) |
|11| **(Optional) Tests** | Add unit tests for models, serializers, and API endpoints under `magazines/tests/`. | `magazines/tests/…` |
|12| **(Optional) Documentation** | Update `README.md` or API docs with the new endpoints (`/api/magazines/`, `/api/issues/`). | `README.md` |

---

## File Skeletons (copy‑paste ready)

### `magazines/models.py`
```python
from django.db import models
from apps.profiles.models import Profile  # adjust import if needed


class Magazine(models.Model):
    owner = models.ForeignKey(
        Profile, related_name='magazines', on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Issue(models.Model):
    magazine = models.ForeignKey(
        Magazine, related_name='issues', on_delete=models.CASCADE
    )
    number = models.PositiveIntegerField()
    pub_date = models.DateField()

    class Meta:
        unique_together = ('magazine', 'number')
        ordering = ['-pub_date']

    def __str__(self):
        return f"{self.magazine.title} – Issue {self.number}"
```

### `magazines/serializers.py`
```python
from rest_framework import serializers
from .models import Magazine, Issue


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = ('id', 'magazine', 'number', 'pub_date')


class MagazineSerializer(serializers.ModelSerializer):
    issues = IssueSerializer(many=True, read_only=True)

    class Meta:
        model = Magazine
        fields = ('id', 'owner', 'title', 'description', 'issues')
```

### `magazines/views.py`
```python
from rest_framework import viewsets, permissions
from .models import Magazine, Issue
from .serializers import MagazineSerializer, IssueSerializer


class MagazineViewSet(viewsets.ModelViewSet):
    queryset = Magazine.objects.all()
    serializer_class = MagazineSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
```

### `magazines/urls.py`
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MagazineViewSet, IssueViewSet

router = DefaultRouter()
router.register(r'magazines', MagazineViewSet, basename='magazine')
router.register(r'issues', IssueViewSet, basename='issue')

urlpatterns = [
    path('', include(router.urls)),
]
```

---

## Acceptance Criteria
- `magazines` appears in `INSTALLED_APPS`.
- Running `python manage.py makemigrations magazines && python manage.py migrate` creates the two tables.
- API endpoints `/api/magazines/` and `/api/issues/` are reachable, listable, and CRUD‑able (subject to permission).
- The plan is saved in **plan.md** at the repository root.

---

*Prepared by the AI assistant – ready for execution when you confirm.*