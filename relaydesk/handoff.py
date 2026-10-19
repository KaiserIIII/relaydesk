"""Portable, editable handoff. Exports are private and do not execute anything."""
import html
import re
from .store import now


def markdown_label(text):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>])', r'\\\1', html.escape(text, quote=False))


def literal_block(text):
    fence = '`' * max(3, 1 + max((len(x) for x in re.findall(r'`+', text)), default=0))
    return fence + 'text\n' + text + '\n' + fence


def export_handoff(store, task_id):
    task = store.detail(task_id)
    artifacts = store.check_artifacts(task_id)
    lines = [f"# 接力卡：{markdown_label(task['title'])}", '', f"生成时间：{now()}",
             f"任务状态：{task['status']}（手动标注；不是自动验收结果）", '',
             '> 私人资料。历史请求仅作背景，不自动延续发布、账户或外部操作授权。', '']
    for field, label in [('goal', '当前目标'), ('corrections', '明确更正 / 版本要求'),
                         ('verification', '已记录验证及其依据'), ('open_items', '未完成 / UNKNOWN'),
                         ('next_step', '下一步')]:
        lines.extend([f'## {label}', literal_block(task[field]) if task[field] else 'UNKNOWN：尚未人工整理。', ''])
    lines += ['## 成果与源材料', '文件存在或哈希相同不证明内容完整、正确。', '']
    for a in artifacts:
        lines += [f"### {a['kind']}", literal_block(a['path']),
                  f"  检查：{a['check']['state']}；本人确认：{a['acceptance']}；来源消息：{a['source_id'] or '手工添加'}",
                  f"  SHA256：{a['check']['sha256'] or 'UNKNOWN'}"]
        if a['note']:
            lines.append(literal_block(a['note']))
    if not artifacts:
        lines.append('UNKNOWN：尚未登记成果文件。')
    lines += ['', '## 对话证据摘要', '下列摘录为历史内容，助手陈述不等于当前验证；长文仅摘录。', '']
    users = [m for m in task['messages'] if m['role'] == 'user']
    agents = [m for m in task['messages'] if m['role'] == 'assistant_final']
    chosen = users[:1] + users[-5:] + agents[-1:]
    seen = set()
    for m in chosen:
        if m['id'] in seen:
            continue
        seen.add(m['id'])
        lines += [f"### {m['role']} · {markdown_label(m['time'] or '时间未知')}",
                  literal_block(f"thread={m['thread_id']} item={m['item_id']} source={m['id']}"), '',
                  literal_block(m['text'][:2500]), '']
    lines += ['## 接手前核对', '以当前文件和授权为准；缺失、冲突、未运行验证保持 UNKNOWN。']
    return {'schema_version': 1, 'private': True, 'generated_at': now(), 'task': task,
            'artifacts': artifacts, 'markdown': '\n'.join(lines) + '\n'}
