# Generated migration for MySQL 5.7 compatibility
# Converts JSONField to TextField for SiteConfig.config

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0009_systemconfig'),
    ]

    operations = [
        # 第一步：先修改数据库列类型（从 JSON 到 TEXT）
        # 兼容 MySQL 8.0（JSON 类型）和 MySQL 5.7（可能已经是 TEXT）
        migrations.RunSQL(
            sql=[
                # 直接修改列类型为 TEXT
                # 在 MySQL 8.0 中会从 JSON 转换为 TEXT
                # 在 MySQL 5.7 中如果已经是 TEXT 则无影响
                "ALTER TABLE site_configs MODIFY COLUMN config TEXT;",
            ],
            reverse_sql=[
                # 回滚时尝试转换回 JSON（仅适用于 MySQL 8.0）
                "ALTER TABLE site_configs MODIFY COLUMN config JSON;",
            ],
        ),
        # 第二步：重命名字段（从 config 到 _config_json），保持数据库列名为 config
        migrations.RenameField(
            model_name='siteconfig',
            old_name='config',
            new_name='_config_json',
        ),
        # 第三步：更新字段定义（改为 TextField，并指定 db_column）
        migrations.AlterField(
            model_name='siteconfig',
            name='_config_json',
            field=models.TextField(default='{}', db_column='config'),
        ),
    ]

