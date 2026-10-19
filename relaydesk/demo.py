"""Synthetic demo only: these messages are not real user or course evidence."""


def seed_demo(store):
    root = store.path.parent / 'demo-documents'
    root.mkdir(exist_ok=True)
    path = root / '复习稿.md'
    if not path.exists():
        path.write_text('# 虚构课程演示\n\nQ: 2+2?\nA: 4.\n', encoding='utf8')
    store.set_setting('roots', list(dict.fromkeys(store.setting('roots', []) + [str(root)])))
    rows = [
        {'thread_id':'demo-study','item_id':'demo-u1','role':'user','title':'课程资料 · 完整稿与考前稿',
         'text':'这是虚构演示：中文资料需要原题、答案和解析。','time':'2026-01-01T10:00:00Z'},
        {'thread_id':'demo-study','item_id':'demo-u2','role':'user',
         'text':'最新更正：新增题也要整理，另外给我精简背诵版。<img src=x onerror=alert(1)>','time':'2026-01-02T10:00:00Z'},
        {'thread_id':'demo-study','item_id':'demo-a1','role':'assistant_final',
         'text':f'历史助手声称整理完成，演示文件：[复习稿](<{path.as_posix()}>). 这不是实际课程验收。','time':'2026-01-03T10:00:00Z'},
        {'thread_id':'demo-project','item_id':'demo-p1','role':'user','title':'项目接力 · 换对话继续',
         'text':'读取已有计划继续，不要从头开始。此内容为虚构演示。','time':'2026-01-03T12:00:00Z'},
        {'thread_id':'demo-unknown','item_id':'demo-m1','role':'user','title':'缺失成果 · 保留未知',
         'text':'这份演示任务没有足够的验收依据。','time':'2026-01-04T10:00:00Z'},
    ]
    result = store.import_records(rows)
    task = next(x for x in store.search('') if x['thread_id'] == 'demo-study')
    store.discover_artifacts(task['id'])
    if not task['goal']:
        store.edit(task['id'], {'category':'study','goal':'虚构演示：整理完整稿与精简稿',
                               'open_items':'新增题尚未逐源核对；真实可用性 UNKNOWN',
                               'next_step':'打开源消息，核对后编辑接力卡'})
    return dict(result, synthetic=True)
