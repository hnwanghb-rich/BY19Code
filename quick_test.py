"""快速验证配置"""
from by19code.config.settings import load_config
from pathlib import Path

config = load_config(project_dir=Path.cwd())

print('已配置的模型:')
for p in config.llm_providers:
    has_key = p.api_key and p.api_key != f'${{BY19CODE_{p.name.upper()}_API_KEY}}'
    status = 'OK' if has_key else 'NO'
    marker = '*' if p.name == config.active_provider else ' '
    print(f'{marker} {p.name:10s} [{status}] - {p.display_name}')

print(f'\n当前激活: {config.active_provider}')
print(f'支持的模型数量: {len(config.llm_providers)}')
