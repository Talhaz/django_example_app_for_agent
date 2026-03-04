# Generated migration to add soft delete fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0007_rename_tag_tag_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='comment',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]