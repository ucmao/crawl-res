from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0006_rebuild_search_tasks_and_resource_results'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailRule',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('rule', models.CharField(max_length=255, db_index=True)),
                ('list_type', models.PositiveSmallIntegerField(db_index=True, choices=[(1, '白名单'), (2, '黑名单')])),
                ('regex_pattern', models.CharField(max_length=500)),
                ('enabled', models.BooleanField(default=True, db_index=True)),
                ('remark', models.CharField(max_length=500, blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'email_rules',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='emailrule',
            constraint=models.UniqueConstraint(fields=('list_type', 'rule'), name='uniq_email_rule_type_rule'),
        ),
    ]
