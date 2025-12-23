import json
import re

from django import forms
from django.core.exceptions import ValidationError

from .models import SiteConfig, EmailRule, SystemConfig


class AdminLoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)


class SiteConfigForm(forms.ModelForm):
    config = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = SiteConfig
        fields = ['key', 'name', 'host', 'enabled', 'config']

    def clean_config(self):
        raw = (self.cleaned_data.get('config') or '').strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
        except Exception as e:
            raise ValidationError(f'Config 必须是合法 JSON: {e}')
        if not isinstance(val, dict):
            raise ValidationError('Config 必须是 JSON object（字典）')
        return val


def _compile_email_rule_to_regex(rule: str) -> str:
    raw = (rule or '').strip().lower()
    if not raw:
        raise ValidationError('规则不能为空')

    if not re.fullmatch(r"[a-z0-9@.*]+", raw):
        raise ValidationError('规则仅允许字母、数字、@、.、*')

    if '@' in raw:
        body = ''.join('.*' if c == '*' else re.escape(c) for c in raw)
        return f"^{body}$"

    if raw.startswith('*.'):
        suffix = raw[2:]
        if not suffix:
            raise ValidationError('域名规则不合法')
        suffix_esc = re.escape(suffix)
        domain_body = f"(?:.*\\.)?{suffix_esc}"
        return f"^.*@{domain_body}$"

    domain_body = ''.join('.*' if c == '*' else re.escape(c) for c in raw)
    return f"^.*@{domain_body}$"


class EmailRuleForm(forms.ModelForm):
    class Meta:
        model = EmailRule
        fields = ['rule', 'list_type', 'enabled', 'remark']

    def clean_rule(self):
        raw = (self.cleaned_data.get('rule') or '').strip().lower()
        if not raw:
            raise ValidationError('规则不能为空')
        _compile_email_rule_to_regex(raw)
        return raw

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.regex_pattern = _compile_email_rule_to_regex(obj.rule)
        if commit:
            obj.save()
        return obj


class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ['key', 'value', 'description']
        widgets = {
            'key': forms.Select(choices=SystemConfig.KEY_CHOICES),
            'value': forms.Textarea(attrs={'rows': 3}),
            'description': forms.TextInput(attrs={'placeholder': '可选，用于说明此配置的用途'}),
        }

    def clean_value(self):
        value = self.cleaned_data.get('value', '').strip()
        if not value:
            raise ValidationError('配置值不能为空')
        return value
