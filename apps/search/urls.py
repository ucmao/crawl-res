from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.index, name='index'),               # 首页（Banner + 搜索框）
    path('square/', views.square, name='square'),      # 资源广场
    path('status/', views.status, name='status'),      # 引擎状态
    path('about/', views.about, name='about'),          # 关于项目
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/logout/', views.admin_logout, name='admin_logout'),
    path('admin/nodes/', views.admin_nodes, name='admin_nodes'),
    path('admin/email/', views.admin_email_rules, name='admin_email_rules'),
    path('admin/email/<int:list_type>/new/', views.admin_email_rule_new, name='admin_email_rule_new'),
    path('admin/email/<int:list_type>/bulk/', views.admin_email_rules_bulk, name='admin_email_rules_bulk'),
    path('admin/email/<int:rule_id>/edit/', views.admin_email_rule_edit, name='admin_email_rule_edit'),
    path('admin/email/<int:rule_id>/delete/', views.admin_email_rule_delete, name='admin_email_rule_delete'),
    path('admin/email/<int:rule_id>/toggle/', views.admin_email_rule_toggle, name='admin_email_rule_toggle'),
    path('admin/nodes/new/', views.admin_node_new, name='admin_node_new'),
    path('admin/nodes/<int:node_id>/edit/', views.admin_node_edit, name='admin_node_edit'),
    path('admin/nodes/<int:node_id>/delete/', views.admin_node_delete, name='admin_node_delete'),
    path('admin/nodes/<int:node_id>/toggle/', views.admin_node_toggle, name='admin_node_toggle'),
    path('admin/nodes/<int:node_id>/test/', views.admin_node_test, name='admin_node_test'),
    path('admin/nodes/enable-all/', views.admin_nodes_enable_all, name='admin_nodes_enable_all'),
    path('admin/nodes/disable-all/', views.admin_nodes_disable_all, name='admin_nodes_disable_all'),
    path('admin/configs/', views.admin_system_configs, name='admin_system_configs'),
    path('admin/configs/new/', views.admin_system_config_new, name='admin_system_config_new'),
    path('admin/configs/<int:config_id>/edit/', views.admin_system_config_edit, name='admin_system_config_edit'),
    path('admin/configs/<int:config_id>/delete/', views.admin_system_config_delete, name='admin_system_config_delete'),
    path('api/verify_task_email', views.verify_task_email, name='verify_task_email'),
    path('result', views.result, name='result'),        # 任务结果页（query: task_id=32位hex）
    path('result/<uuid:task_id>/', views.result_legacy, name='result_legacy'), # 兼容旧链接
    re_path(r'^result/(?P<task_id>[0-9a-f]{32})/$', views.result_legacy_hex, name='result_legacy_hex'),
]