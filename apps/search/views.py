import csv
import json
import uuid
import time
import urllib.request
from datetime import timedelta
import os
import re

import redis

from django.db import models

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test

from .forms import AdminLoginForm, SiteConfigForm, EmailRuleForm, SystemConfigForm
from .models import SearchTask, ResourceResult, SiteConfig, EmailRule, SystemConfig
from .tasks import crawl_task
from .config_utils import (
    get_email_rate_limit_windows, get_keyword_cache_ttl, get_index_recent_tasks_count,
    get_square_display_count, get_square_fetch_count, get_square_expire_hours,
    get_result_expire_hours, get_email_config, get_crawl_timeout_seconds
)


def _get_redis_client():
    redis_url = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    return redis.Redis.from_url(redis_url, decode_responses=True)


_INCR_EXPIRE_LUA = """
local v = redis.call('INCR', KEYS[1])
if v == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return v
"""


def _check_email_rate_limit(rds, email: str):
    email_key = (email or '').strip().lower()
    if not email_key:
        return None

    windows = get_email_rate_limit_windows()

    for ttl, limit in windows:
        key = f"rl:email:{email_key}:{ttl}"
        cnt = int(rds.eval(_INCR_EXPIRE_LUA, 1, key, ttl))
        if cnt > limit:
            return {'ttl': ttl, 'limit': limit, 'count': cnt}
    return None


def _normalize_keyword(keyword: str) -> str:
    return (keyword or '').strip().lower()


def _load_email_rules():
    rules = list(EmailRule.objects.filter(enabled=True).order_by('id'))
    allow = [r for r in rules if r.list_type == EmailRule.TYPE_ALLOW]
    block = [r for r in rules if r.list_type == EmailRule.TYPE_BLOCK]
    return allow, block


def _is_email_allowed(email: str):
    allow, block = _load_email_rules()
    email_key = (email or '').strip().lower()
    if not email_key:
        return False

    for r in block:
        try:
            if re.match(r.regex_pattern, email_key, flags=re.IGNORECASE):
                return False
        except re.error:
            continue

    if allow:
        for r in allow:
            try:
                if re.match(r.regex_pattern, email_key, flags=re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    return True


def index(request):
    if request.method == "POST":
        keyword = request.POST.get('keyword')
        email = request.POST.get('email')
        no_email = (request.POST.get('no_email') or '').strip().lower() in {'1', 'true', 'on', 'yes'}
        notify_email = not no_email

        try:
            validate_email(email)
        except ValidationError:
            recent_tasks = SearchTask.objects.all()[:get_index_recent_tasks_count()]
            return render(request, 'search/index.html', {
                'recent_tasks': recent_tasks,
                'error': '邮箱格式无效，请输入正确的邮箱地址。'
            })

        if not _is_email_allowed(email):
            recent_tasks = SearchTask.objects.all()[:get_index_recent_tasks_count()]
            return render(request, 'search/index.html', {
                'recent_tasks': recent_tasks,
                'error': '该邮箱不允许提交请求，请更换邮箱或联系管理员。'
            })

        rds = _get_redis_client()
        limited = _check_email_rate_limit(rds, email)
        if limited:
            recent_tasks = SearchTask.objects.all()[:get_index_recent_tasks_count()]
            return render(request, 'search/index.html', {
                'recent_tasks': recent_tasks,
                'error': '提交过于频繁，请稍后再试。'
            })

        norm_keyword = _normalize_keyword(keyword)
        cache_key = f"kw:{norm_keyword}"
        cached_task_hex = rds.get(cache_key) if norm_keyword else None

        expire_time = timezone.now() + timedelta(hours=get_result_expire_hours())

        if cached_task_hex:
            try:
                related_uuid = uuid.UUID(hex=cached_task_hex)
            except ValueError:
                related_uuid = None

            if related_uuid:
                related_task = SearchTask.objects.filter(task_id=related_uuid).order_by('-created_at').first()
                status = related_task.status if related_task else 'PENDING'

                task = SearchTask.objects.create(
                    keyword=keyword,
                    email=email,
                    notify_email=notify_email,
                    expire_time=expire_time,
                    task_id=uuid.uuid4(),
                    related_task_id=related_uuid,
                    is_cache=True,
                    status=status,
                )
                return redirect(f"{reverse('result')}?related_task_id={task.related_task_id.hex}")

        task_uuid = uuid.uuid4()
        task = SearchTask.objects.create(
            keyword=keyword,
            email=email,
            notify_email=notify_email,
            expire_time=expire_time,
            task_id=task_uuid,
            related_task_id=task_uuid,
            is_cache=False,
        )

        if norm_keyword:
            rds.setex(cache_key, get_keyword_cache_ttl(), task_uuid.hex)

        crawl_task.delay(task.task_id, keyword)

        return redirect(f"{reverse('result')}?related_task_id={task.related_task_id.hex}")

    # 首页加载：获取最近的搜索动态给"广场"模块展示
    recent_tasks = SearchTask.objects.all()[:get_index_recent_tasks_count()]
    return render(request, 'search/index.html', {'recent_tasks': recent_tasks})


def verify_task_email(request):
    task_id_hex = (request.GET.get('task_id') or '').strip().lower()
    related_task_id_hex = (request.GET.get('related_task_id') or '').strip().lower()
    email = (request.GET.get('email') or '').strip()

    if (not task_id_hex and not related_task_id_hex) or not email:
        return JsonResponse({'ok': False, 'error': 'missing_params'}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'invalid_email'}, status=400)

    try:
        task_uuid = uuid.UUID(hex=task_id_hex) if task_id_hex else None
        related_uuid = uuid.UUID(hex=related_task_id_hex) if related_task_id_hex else None
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'invalid_task_id'}, status=400)

    task = None
    if task_uuid:
        task = SearchTask.objects.filter(task_id=task_uuid).order_by('-created_at').first()
    if not task and related_uuid:
        task = SearchTask.objects.filter(related_task_id=related_uuid).order_by('-created_at').first()
    if not task:
        return JsonResponse({'ok': False, 'error': 'task_not_found'}, status=404)

    if (task.email or '').strip().lower() != email.lower():
        return JsonResponse({'ok': False, 'error': 'email_mismatch'}, status=403)

    return JsonResponse({'ok': True, 'related_task_id': task.related_task_id.hex})


def square(request):
    # 广场页展示最新发现的资源
    q = (request.GET.get('q') or '').strip()
    expire_hours = get_square_expire_hours()
    expire_time = timezone.now() - timedelta(hours=expire_hours)
    
    qs = ResourceResult.objects.filter(created_at__gte=expire_time).order_by('-created_at')
    if q:
        qs = qs.filter(
            models.Q(title__icontains=q)
            | models.Q(disk_type__icontains=q)
            | models.Q(site_source__icontains=q)
            | models.Q(url__icontains=q)
        )
    # 获取更多资源以便去重后仍有足够数量
    fetch_count = get_square_fetch_count()
    display_count = get_square_display_count()
    all_resources = list(qs[:fetch_count])
    # 对URL进行去重，保留第一次出现的资源
    seen_urls = set()
    latest_resources = []
    for res in all_resources:
        url = res.url.strip() if res.url else ''
        if url and url not in seen_urls:
            seen_urls.add(url)
            latest_resources.append(res)
            if len(latest_resources) >= display_count:
                break
    return render(request, 'search/square.html', {'resources': latest_resources, 'q': q})


def status(request):
    # 引擎状态页面
    total_sites = SiteConfig.objects.count()
    enabled_sites = SiteConfig.objects.filter(enabled=True).count()
    sites = SiteConfig.objects.all().order_by('key')
    return render(request, 'search/status.html', {
        'total_sites': total_sites,
        'enabled_sites': enabled_sites,
        'sites': sites,
    })


def about(request):
    # 关于项目页面
    return render(request, 'search/about.html')


def result(request):
    related_task_id_hex = (request.GET.get('related_task_id') or '').strip().lower()
    if not related_task_id_hex:
        return render(request, 'search/result_detail.html', {'task': None, 'resources': []})

    try:
        related_uuid = uuid.UUID(hex=related_task_id_hex)
    except ValueError:
        return render(request, 'search/result_detail.html', {'task': None, 'resources': []})

    request_task = SearchTask.objects.filter(related_task_id=related_uuid).order_by('-created_at').first()
    crawl_task_obj = SearchTask.objects.filter(task_id=related_uuid).order_by('-created_at').first()
    task = crawl_task_obj or request_task
    if not task:
        return render(request, 'search/result_detail.html', {'task': None, 'resources': []})

    # 过期校验
    now = timezone.now()
    expire_time = (request_task.expire_time if request_task else task.expire_time)
    if expire_time and now > expire_time:
        return render(request, 'search/result_detail.html', {
            'task': task,
            'resources': [],
            'expired': True,
        })

    resources_qs = ResourceResult.objects.filter(task_id=related_uuid).order_by('-created_at')

    # 导出 CSV
    if (request.GET.get('export') or '').lower() == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="crawl-res-{related_uuid.hex}.csv"'
        writer = csv.writer(response)
        writer.writerow(['title', 'disk_type', 'url', 'site_source', 'created_at'])
        for r in resources_qs.iterator():
            writer.writerow([r.title, r.disk_type, r.url, r.site_source, r.created_at])
        return response

    resources = list(resources_qs)
    return render(request, 'search/result_detail.html', {
        'task': task,
        'resources': resources,
        'expired': False,
    })


def result_legacy(request, task_id):
    return redirect(f"{reverse('result')}?related_task_id={task_id.hex}")


def result_legacy_hex(request, task_id):
    return redirect(f"{reverse('result')}?related_task_id={task_id}")


def _is_admin(user):
    return bool(user and user.is_authenticated and user.is_staff)


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_nodes')

    form = AdminLoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user and user.is_staff:
            auth_login(request, user)
            return redirect('admin_nodes')
        error = '用户名或密码错误，或无管理员权限。'

    return render(request, 'admin/login.html', {'form': form, 'error': error})


@login_required(login_url='/admin/login/')
def admin_logout(request):
    auth_logout(request)
    return redirect('admin_login')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_nodes(request):
    sites = SiteConfig.objects.all().order_by('key')
    return render(request, 'admin/nodes.html', {'sites': sites})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rules(request):
    allow_rules = EmailRule.objects.filter(list_type=EmailRule.TYPE_ALLOW).order_by('-updated_at')
    block_rules = EmailRule.objects.filter(list_type=EmailRule.TYPE_BLOCK).order_by('-updated_at')
    return render(request, 'admin/email_rules.html', {
        'allow_rules': allow_rules,
        'block_rules': block_rules,
    })


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rule_new(request, list_type: int):
    error = None
    if request.method == 'POST':
        post = request.POST.copy()
        post['list_type'] = str(list_type)
        if 'enabled' not in post:
            post['enabled'] = ''
        form = EmailRuleForm(post)
        if form.is_valid():
            form.save()
            return redirect('admin_email_rules')
        error = '请检查输入项。'
    else:
        form = EmailRuleForm(initial={'enabled': True, 'list_type': list_type})
    return render(request, 'admin/email_rule_form.html', {'form': form, 'error': error, 'is_edit': False, 'list_type': list_type})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rule_edit(request, rule_id: int):
    obj = EmailRule.objects.filter(id=rule_id).first()
    if not obj:
        return redirect('admin_email_rules')

    error = None
    if request.method == 'POST':
        post = request.POST.copy()
        if 'enabled' not in post:
            post['enabled'] = ''
        form = EmailRuleForm(post, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('admin_email_rules')
        error = '请检查输入项。'
    else:
        form = EmailRuleForm(instance=obj)
    return render(request, 'admin/email_rule_form.html', {'form': form, 'error': error, 'is_edit': True, 'rule_obj': obj, 'list_type': obj.list_type})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rule_delete(request, rule_id: int):
    obj = EmailRule.objects.filter(id=rule_id).first()
    if not obj:
        return redirect('admin_email_rules')

    if request.method == 'POST':
        obj.delete()
        return redirect('admin_email_rules')
    return render(request, 'admin/email_rule_confirm_delete.html', {'rule_obj': obj})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rule_toggle(request, rule_id: int):
    if request.method != 'POST':
        return redirect('admin_email_rules')
    obj = EmailRule.objects.filter(id=rule_id).first()
    if not obj:
        return redirect('admin_email_rules')
    obj.enabled = not obj.enabled
    obj.save(update_fields=['enabled', 'updated_at'])
    return redirect('admin_email_rules')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_email_rules_bulk(request, list_type: int):
    if request.method != 'POST':
        return redirect('admin_email_rules')

    raw = (request.POST.get('rules') or '').strip()
    remark = (request.POST.get('remark') or '').strip()
    enabled = (request.POST.get('enabled') or '').lower() in ('1', 'true', 'yes', 'on')

    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    created = 0
    for ln in lines:
        post = {
            'rule': ln,
            'list_type': str(list_type),
            'enabled': 'on' if enabled else '',
            'remark': remark,
        }
        form = EmailRuleForm(post)
        if form.is_valid():
            try:
                form.save()
                created += 1
            except Exception:
                continue
    return redirect('admin_email_rules')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_node_new(request):
    error = None
    if request.method == 'POST':
        post = request.POST.copy()
        if 'enabled' not in post:
            post['enabled'] = ''
        form = SiteConfigForm(post)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.config = form.cleaned_data.get('config') or {}
            obj.save()
            return redirect('admin_nodes')
        error = '请检查输入项。'
    else:
        form = SiteConfigForm(initial={'enabled': True, 'config': json.dumps({}, ensure_ascii=False, indent=2)})
    return render(request, 'admin/node_form.html', {'form': form, 'error': error, 'key_locked': False})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_node_edit(request, node_id):
    site = SiteConfig.objects.filter(id=node_id).first()
    if not site:
        return redirect('admin_nodes')

    error = None
    if request.method == 'POST':
        post = request.POST.copy()
        if 'enabled' not in post:
            post['enabled'] = ''
        form = SiteConfigForm(post, instance=site)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.config = form.cleaned_data.get('config') or {}
            obj.save()
            return redirect('admin_nodes')
        error = '请检查输入项。'
    else:
        initial = {
            'config': json.dumps(site.config or {}, ensure_ascii=False, indent=2)
        }
        form = SiteConfigForm(instance=site, initial=initial)

    return render(request, 'admin/node_form.html', {'form': form, 'error': error, 'site': site, 'key_locked': True})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_node_delete(request, node_id):
    site = SiteConfig.objects.filter(id=node_id).first()
    if not site:
        return redirect('admin_nodes')

    if request.method == 'POST':
        site.delete()
        return redirect('admin_nodes')

    return render(request, 'admin/node_confirm_delete.html', {'site': site})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_node_toggle(request, node_id):
    if request.method != 'POST':
        return redirect('admin_nodes')
    site = SiteConfig.objects.filter(id=node_id).first()
    if not site:
        return redirect('admin_nodes')
    site.enabled = not site.enabled
    site.save(update_fields=['enabled', 'updated_at'])
    return redirect('admin_nodes')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_nodes_enable_all(request):
    if request.method != 'POST':
        return redirect('admin_nodes')
    SiteConfig.objects.all().update(enabled=True, updated_at=timezone.now())
    return redirect('admin_nodes')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_nodes_disable_all(request):
    if request.method != 'POST':
        return redirect('admin_nodes')
    SiteConfig.objects.all().update(enabled=False, updated_at=timezone.now())
    return redirect('admin_nodes')


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_node_test(request, node_id):
    site = SiteConfig.objects.filter(id=node_id).first()
    if not site:
        return JsonResponse({'ok': False, 'error': 'site_not_found'}, status=404)

    url = (site.host or '').strip()
    if not url:
        return JsonResponse({'ok': False, 'error': 'empty_host'}, status=400)

    if not (url.startswith('http://') or url.startswith('https://')):
        url = f"http://{url}"

    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            status_code = getattr(resp, 'status', 200)
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return JsonResponse({'ok': False, 'error': str(e), 'elapsed_ms': elapsed_ms}, status=502)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return JsonResponse({'ok': True, 'status_code': status_code, 'elapsed_ms': elapsed_ms})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_system_configs(request):
    """系统配置列表页"""
    configs = SystemConfig.objects.all().order_by('key')
    return render(request, 'admin/system_configs.html', {'configs': configs})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_system_config_new(request):
    """新建系统配置"""
    error = None
    if request.method == 'POST':
        form = SystemConfigForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_system_configs')
        error = '请检查输入项。'
    else:
        form = SystemConfigForm()
    return render(request, 'admin/system_config_form.html', {'form': form, 'error': error, 'is_edit': False})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_system_config_edit(request, config_id):
    """编辑系统配置"""
    config = SystemConfig.objects.filter(id=config_id).first()
    if not config:
        return redirect('admin_system_configs')

    error = None
    if request.method == 'POST':
        form = SystemConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            return redirect('admin_system_configs')
        error = '请检查输入项。'
    else:
        form = SystemConfigForm(instance=config)
    return render(request, 'admin/system_config_form.html', {'form': form, 'error': error, 'is_edit': True, 'config': config})


@login_required(login_url='/admin/login/')
@user_passes_test(_is_admin, login_url='/admin/login/')
def admin_system_config_delete(request, config_id):
    """删除系统配置"""
    config = SystemConfig.objects.filter(id=config_id).first()
    if not config:
        return redirect('admin_system_configs')

    if request.method == 'POST':
        config.delete()
        return redirect('admin_system_configs')

    return render(request, 'admin/system_config_confirm_delete.html', {'config': config})