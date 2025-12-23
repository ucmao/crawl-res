from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0005_crawlernode'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS resource_results;",
                "DROP TABLE IF EXISTS search_tasks;",
                """
                CREATE TABLE search_tasks (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    task_id CHAR(32) NOT NULL,
                    related_task_id CHAR(32) NOT NULL,
                    is_cache BOOL NOT NULL DEFAULT 0,
                    keyword VARCHAR(255) NOT NULL,
                    email VARCHAR(254) NOT NULL,
                    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
                    expire_time DATETIME NULL,
                    created_at DATETIME(6) NOT NULL
                );
                """,
                "CREATE UNIQUE INDEX search_tasks_task_id_uniq ON search_tasks(task_id);",
                "CREATE INDEX search_tasks_related_task_id_idx ON search_tasks(related_task_id);",
                "CREATE INDEX search_tasks_is_cache_idx ON search_tasks(is_cache);",
                "CREATE INDEX search_tasks_created_at_idx ON search_tasks(created_at);",
                """
                CREATE TABLE resource_results (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    task_id CHAR(32) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    disk_type VARCHAR(50) NOT NULL,
                    url LONGTEXT NOT NULL,
                    site_source VARCHAR(100) NOT NULL,
                    created_at DATETIME(6) NOT NULL
                );
                """,
                "CREATE INDEX resource_results_task_id_idx ON resource_results(task_id);",
                "CREATE INDEX resource_results_created_at_idx ON resource_results(created_at);",
            ],
            reverse_sql=[
                "DROP TABLE IF EXISTS resource_results;",
                "DROP TABLE IF EXISTS search_tasks;",
            ],
        ),
    ]
