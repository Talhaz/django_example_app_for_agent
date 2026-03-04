"""
Utility functions and helpers for the magazines app.
"""
from functools import wraps
from django.db.models import OuterRef, Subquery, Count, IntegerField
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ParseError, NotFound
from django.db import DatabaseError, IntegrityError


def safe_method_return(default_value):
    """
    Decorator for serializer method fields to gracefully handle exceptions.

    Returns the specified default_value if any exception occurs during method execution.

    Args:
        default_value: Value to return on any exception (e.g., 0, False, None)

    Example usage:
        @safe_method_return(0)
        def get_article_count(self, obj):
            return obj.article_count  # Returns 0 if this raises
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, obj):
            try:
                return func(self, obj)
            except (DatabaseError, IntegrityError, AttributeError, TypeError):
                # Gracefully handle all common data access errors
                return default_value
        return wrapper
    return decorator


def get_article_count_subquery():
    """
    Returns a subquery that counts articles for each magazine.

    This is used to annotate magazines with their article count
    without executing N+1 queries.

    Note: The relationship is Article -> Profile (author) -> Magazine

    Returns:
        Subquery: A Django subquery for counting articles
    """
    from conduit.apps.articles.models import Article

    return Subquery(
        Article.objects.filter(
            author__magazine=OuterRef('pk'),
            status='published'
        ).values('author__magazine')
        .annotate(count=Count('pk'))
        .values('count')[:1],
        output_field=IntegerField()
    )


def handle_database_errors(action_name='performing action', error_type='ParseError', error_message='An error occurred'):
    """
    Decorator to handle common database and validation errors in view actions.

    This decorator wraps view action methods to catch and convert common exceptions
    into appropriate API error responses. It checks for a `.mapping` attribute on
    the wrapped function to customize error handling for specific exception types.

    The `.mapping` attribute should be a dict with keys matching exception types
    and values containing:
        - 'message': Error message string (can use {str(e)} for exception details)
        - 'exception': Exception class to raise

    Example usage:
        @handle_database_errors(action_name='retrieving data')
        def my_action(self, request, pk=None):
            return Response({'data': 'some data'})

        my_action.mapping = {
            'value_error': {'message': 'Invalid value: {str(e)}', 'exception': ParseError},
            'not_found': {'message': 'Resource not found', 'exception': NotFound},
        }

    Args:
        action_name: Description of the action being performed (for error messages)
        error_type: Default exception type to raise ('ParseError' or 'NotFound')
        error_message: Default error message when no mapping matches

    Returns:
        Decorator function that wraps the view action
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (ValueError, TypeError):
                # Check for custom value error mapping
                mapping = getattr(func, 'mapping', {})
                if 'value_error' in mapping:
                    config = mapping['value_error']
                    raise config['exception'](config['message'])
                raise ParseError('Invalid input value provided.')
            except NotFound:
                # Check for custom not found mapping
                mapping = getattr(func, 'mapping', {})
                if 'not_found' in mapping:
                    config = mapping['not_found']
                    raise config['exception'](config['message'])
                # Re-raise if no custom mapping
                raise
            except (DatabaseError, IntegrityError) as e:
                # Check for custom database error mapping
                mapping = getattr(func, 'mapping', {})
                if 'database_error' in mapping:
                    config = mapping['database_error']
                    message = config['message']
                    if '{str(e)}' in message:
                        message = message.format(str(e))
                    raise config['exception'](message)
                # Default database error handling
                if error_type == 'NotFound':
                    raise NotFound(error_message)
                raise ParseError(f'Database error while {action_name}: {str(e)}')
            except Exception as e:
                # Check for generic error mapping
                mapping = getattr(func, 'mapping', {})
                if 'generic_error' in mapping:
                    config = mapping['generic_error']
                    raise config['exception'](config['message'])
                # Default generic error handling
                if error_type == 'NotFound':
                    raise NotFound(error_message)
                raise ParseError(f'Error while {action_name}: {str(e)}')

        return wrapper
    return decorator