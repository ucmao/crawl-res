from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0004_searchtask_expire_time'),
    ]

    operations = [
        migrations.CreateModel(
            name='CrawlerNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('host', models.CharField(max_length=255)),
                ('enabled', models.BooleanField(db_index=True, default=True)),
                ('remark', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'crawler_nodes',
                'ordering': ['-created_at'],
            },
        ),
    ]
