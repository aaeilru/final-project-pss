from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0002_add_indexes'),
    ]

    operations = [
        # Tambah created_at dan updated_at ke CourseContent
        migrations.AddField(
            model_name='coursecontent',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='coursecontent',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Hapus field member_id dari Comment
        migrations.RemoveField(
            model_name='comment',
            name='member_id',
        ),
        # Tambah field user_id ke Comment
        migrations.AddField(
            model_name='comment',
            name='user_id',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
                verbose_name='pengguna',
                default=1,
            ),
            preserve_default=False,
        ),
    ]
