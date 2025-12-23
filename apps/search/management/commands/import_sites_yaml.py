import os
import yaml

from django.core.management.base import BaseCommand, CommandError

from apps.search.models import SiteConfig


class Command(BaseCommand):
    help = 'Import config/sites.yaml into SiteConfig table (upsert by key)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default=None,
            help='Path to sites.yaml (default: <BASE_DIR>/config/sites.yaml)',
        )
        parser.add_argument(
            '--disable-missing',
            action='store_true',
            help='Disable SiteConfig rows that are not present in yaml',
        )

    def handle(self, *args, **options):
        path = options.get('path')
        if not path:
            # project root is two levels up from scraper/settings.py, but easiest is cwd-based
            path = os.path.join(os.getcwd(), 'config', 'sites.yaml')

        if not os.path.exists(path):
            raise CommandError(f'sites.yaml not found: {path}')

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        sites = data.get('sites')
        if not isinstance(sites, dict) or not sites:
            raise CommandError('Invalid sites.yaml: missing top-level "sites" mapping')

        yaml_keys = set(sites.keys())
        updated = 0
        created = 0

        for key, cfg in sites.items():
            if not isinstance(cfg, dict):
                continue

            name = cfg.get('name') or key
            host = cfg.get('host') or ''

            obj, is_created = SiteConfig.objects.update_or_create(
                key=key,
                defaults={
                    'name': name,
                    'host': host,
                    'enabled': True,
                    'config': cfg,
                },
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        disabled = 0
        if options.get('disable_missing'):
            qs = SiteConfig.objects.exclude(key__in=yaml_keys).filter(enabled=True)
            disabled = qs.update(enabled=False)

        self.stdout.write(self.style.SUCCESS(
            f'Imported sites.yaml: created={created}, updated={updated}, disabled_missing={disabled}'
        ))
