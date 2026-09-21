#!/usr/bin/env python3
"""Rebuild church/index.html from the dated pages church/YYYY-MM-DD.html (newest first)
and make sure every weekly page carries the manifest link + offline-cache registration."""
import re, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent / "church"
HEAD_TAGS = '<link rel="manifest" href="/church/manifest.webmanifest"><meta name="theme-color" content="#7A1F1F">'
SW_TAG = '<script>if("serviceWorker" in navigator){navigator.serviceWorker.register("/church/sw.js").catch(function(){});}</script>'
WEEKDAY = "一二三四五六日"

def patch(page: pathlib.Path):
    t = page.read_text(encoding="utf-8")
    if "manifest.webmanifest" not in t:
        t = t.replace("</head>", HEAD_TAGS + "</head>", 1)
    if "serviceWorker" not in t:
        t = t.replace("</body>", SW_TAG + "</body>", 1)
    page.write_text(t, encoding="utf-8")

def title_of(page: pathlib.Path):
    m = re.search(r"<title>(.*?)</title>", page.read_text(encoding="utf-8"), re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

import collections
dates = collections.OrderedDict()
for p in sorted(ROOT.glob("*.html"), reverse=True):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(-en)?\.html$", p.name)
    if not m:
        continue
    patch(p)
    dates.setdefault(m.group(1), {})["en" if m.group(2) else "zh"] = p.name
items = []
for ds, files in sorted(dates.items(), reverse=True):
    d = datetime.date.fromisoformat(ds)
    label = f"{d.year}年{d.month}月{d.day}日（星期{WEEKDAY[d.weekday()]}）"
    links = ""
    if "zh" in files:
        links += f'<a class="b" href="/church/{files["zh"]}">中文</a>'
    if "en" in files:
        links += f'<a class="b en" href="/church/{files["en"]}">English</a>'
    items.append(f'<li><span class="d">{label}</span><span class="bs">{links}</span></li>')
pages = [ROOT / f for f in files.values() for files in [dates[k] for k in dates]]
html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>沙市堂 主日崇拜指南</title>{HEAD_TAGS}
<link rel="icon" href="/church/icon-192.png">
<style>
:root{{color-scheme:light dark;--fg:#111;--bg:#fff;--sect:#7A1F1F;--rule:#c9b8b8;--chip:#f3ecec}}
@media (prefers-color-scheme:dark){{:root{{--fg:#e8e8e8;--bg:#121212;--sect:#e39a9a;--rule:#5a4444;--chip:#2a2222}}}}
body{{margin:0;padding:calc(10px + env(safe-area-inset-top,0px)) 14px 40px;background:var(--bg);color:var(--fg);font-family:"PingFang SC","HarmonyOS Sans SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;font-size:24px;line-height:1.5}}
h1{{font-size:1.25em;color:var(--sect);margin:10px 0 4px;border-bottom:2px solid var(--sect);padding-bottom:4px}}
p{{margin:6px 0 12px}}
ul{{list-style:none;padding:0;margin:0}}
li{{padding:12px 14px;margin:0 0 12px;border:1px solid var(--rule);border-radius:12px;background:var(--chip)}}
.d{{display:block;font-weight:bold;color:var(--sect);margin-bottom:8px}}
.bs{{display:flex;gap:10px}}
.b{{flex:1;text-align:center;padding:12px 8px;border-radius:10px;background:var(--sect);color:#fff;text-decoration:none;font-weight:bold}}
.b.en{{background:#1F4E79}}
.tip{{font-size:.8em;opacity:.8}}
</style></head><body>
<h1>沙市堂 主日崇拜指南</h1>
<p>请点下面的日期，打开当天的崇拜指南。</p>
<ul>
{chr(10).join(items)}
</ul>
<p class="tip">带虚线的词，点一下可以看解释。打开过的页面，没有网络时也能看。</p>
{SW_TAG}
</body></html>
'''
(ROOT / "index.html").write_text(html, encoding="utf-8")
print(f"index.html written with {len(items)} week(s):", ", ".join(dates))
