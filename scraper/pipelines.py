import json
import asyncio
from apps.search.models import ResourceResult, SearchTask
from asgiref.sync import sync_to_async

class DebugPipeline:
    def process_item(self, item, spider):
        print(f"DebugPipeline: {json.dumps(item, ensure_ascii=False, indent=2)}")
        return item

class DjangoPipeline:
    async def process_item(self, item, spider):
        # 使用sync_to_async将同步的数据库操作包装为异步操作
        try:
            # 存入资源，处理字段映射关系
            create_resource = sync_to_async(ResourceResult.objects.create)
            await create_resource(
                task_id=spider.task_id,
                title=item['title'],
                disk_type=item['disk_type'],
                url=item['resource_url'],  # 修正：使用resource_url代替url
                site_source=item['site_name']  # 修正：使用site_name代替site_source
            )
            return item
        except Exception as e:
            print(f"DjangoPipeline错误: {e}")
            return item