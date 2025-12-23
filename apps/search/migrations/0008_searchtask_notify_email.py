from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0007_emailrule'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchtask',
            name='notify_email',
            field=models.BooleanField(default=True, db_index=True),
        ),
    ]
