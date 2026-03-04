# Generated migration to rename Tag.tag to Tag.name

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0006_article_dislikes_article_likes_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tag',
            old_name='tag',
            new_name='name',
        ),
    ]