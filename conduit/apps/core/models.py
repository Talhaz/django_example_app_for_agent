from django.db import models
from django.db.models.query import QuerySet


class SoftDeleteQuerySet(QuerySet):
    """Custom QuerySet that filters out soft-deleted objects by default."""
    
    def delete(self):
        """Override delete to perform soft delete on all objects in queryset."""
        # Call the soft delete method on each object
        for obj in self:
            obj.hard_delete = False  # Use soft delete
            super().update(is_deleted=True, deleted_at=models.functions.Now())
        return (self.count(), {self.model._meta.label: self.count()})


class SoftDeleteManager(models.Manager):
    """Manager that returns only non-deleted objects by default."""
    
    def get_queryset(self):
        """Filter out soft-deleted objects from default queries."""
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)
    
    def include_deleted(self):
        """Include soft-deleted objects in the queryset."""
        return SoftDeleteQuerySet(self.model, using=self._db).all()
    
    def deleted_only(self):
        """Return only soft-deleted objects."""
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)


class SoftDeleteMixin(models.Model):
    """Mixin that adds soft delete functionality to models."""
    
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Use the custom manager for soft delete functionality
    objects = SoftDeleteManager()
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False, hard_delete=False):
        """
        Override delete to perform soft delete by default.
        
        Args:
            using: The database alias to use
            keep_parents: Whether to keep parent model objects
            hard_delete: If True, perform actual hard delete (default: False)
        """
        if hard_delete:
            # Perform actual hard delete
            super().delete(using=using, keep_parents=keep_parents)
        else:
            # Perform soft delete
            from django.utils import timezone
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(using=using)
    
    def restore(self):
        """Restore a soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def hard_delete(self):
        """Permanently delete the object from the database."""
        self.delete(hard_delete=True)


class TimestampedModel(SoftDeleteMixin):
    # A timestamp representing when this object was created.
    created_at = models.DateTimeField(auto_now_add=True)

    # A timestamp reprensenting when this object was last updated.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

        # By default, any model that inherits from `TimestampedModel` should
        # be ordered in reverse-chronological order. We can override this on a
        # per-model basis as needed, but reverse-chronological is a good
        # default ordering for most models.
        ordering = ['-created_at', '-updated_at']
