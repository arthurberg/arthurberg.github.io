#!/usr/bin/env python3
"""Rebuild church/index.html — the single-page worship-guide app — from the dated pages
church/YYYY-MM-DD.html (Chinese) and church/YYYY-MM-DD-en.html (English), and make sure every
weekly page carries the manifest link + offline-cache registration."""
import re, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent / "church"
HEAD_TAGS = '<link rel="manifest" href="/church/manifest.webmanifest"><meta name="theme-color" content="#7A1F1F">'
SW_TAG = '<script>if("serviceWorker" in navigator){navigator.serviceWorker.register("/church/sw.js").catch(function(){});}</script>'

def patch(page: pathlib.Path):
    t = page.read_text(encoding="utf-8")
    if "manifest.webmanifest" not in t:
        t = t.replace("</head>", HEAD_TAGS + "</head>", 1)
    if "serviceWorker" not in t:
        t = t.replace("</body>", SW_TAG + "</body>", 1)
    page.write_text(t, encoding="utf-8")

weeks = {}
for p in sorted(ROOT.glob("*.html")):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(-en)?\.html$", p.name)
    if not m:
        continue
    patch(p)
    weeks.setdefault(m.group(1), {"d": m.group(1)})["en" if m.group(2) else "zh"] = p.name
WEEKS = [weeks[k] for k in sorted(weeks, reverse=True)]  # newest first

html = '''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>沙市堂 主日崇拜指南</title>''' + HEAD_TAGS + '''
<link rel="icon" href="/church/icon-192.png">
<style>
:root{color-scheme:light dark;--fg:#111;--bg:#fff;--sect:#7A1F1F;--en:#1F4E79;--rule:#c9b8b8;--chip:#f3ecec}
@media (prefers-color-scheme:dark){:root{--fg:#e8e8e8;--bg:#121212;--sect:#e39a9a;--en:#8fb8ea;--rule:#5a4444;--chip:#2a2222}}
html,body{height:100%;margin:0;overflow:hidden;background:var(--bg);color:var(--fg);font-family:"PingFang SC","HarmonyOS Sans SC","Noto Sans CJK SC","Helvetica Neue",Arial,sans-serif}
#bar{position:fixed;top:0;left:0;right:0;min-height:50px;padding:calc(3px + env(safe-area-inset-top,0px)) 5px 3px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 5px;border-bottom:1px solid var(--rule);background:var(--bg);font-size:16px;z-index:2;-webkit-text-size-adjust:none;text-size-adjust:none}
#bar button,#bar select{font:inherit;min-height:42px;border:1px solid var(--rule);border-radius:10px;background:var(--chip);color:var(--fg)}
#sel,#sec{min-width:0;font-weight:bold;color:var(--sect);padding:0 4px;-webkit-appearance:none;appearance:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center}
#sel{flex:0 0 auto;width:6.4em}
#sec{flex:1 1 130px;min-width:130px;color:var(--fg);font-weight:normal}
#lang{display:flex;flex:0 0 auto}
#lang button{padding:0 10px;min-width:42px;font-weight:bold;color:#fff;background:var(--sect);border-color:var(--sect)}
#lang button.toen{background:var(--en);border-color:var(--en)}
#bar button:disabled{opacity:.35}
#f{position:fixed;left:0;right:0;bottom:0;top:50px;width:100%;height:calc(100% - 50px);border:0;background:var(--bg)}
#empty{padding:80px 20px;font-size:22px;text-align:center}
</style></head><body>
<div id="bar"><select id="sel" aria-label="日期"></select><select id="sec" aria-label="章节"></select>
<span id="lang"><button id="lb" type="button" aria-label="语言">E</button></span></div>
<iframe id="f" title="主日崇拜指南"></iframe>
<script>
var WEEKS=''' + json.dumps(WEEKS, ensure_ascii=False) + ''';
(function(){
var f=document.getElementById('f'),sel=document.getElementById('sel'),
    lb=document.getElementById('lb'),sec=document.getElementById('sec');
function fmt(d){var p=d.split('-');return (+p[1])+'月'+(+p[2])+'日';}
function fit(){var h=document.getElementById('bar').offsetHeight;f.style.top=h+'px';f.style.height='calc(100% - '+h+'px)';}
window.addEventListener('resize',fit);window.addEventListener('load',fit);
function pad(n){return (n<10?'0':'')+n;}
function pick(){var t=new Date(),today=t.getFullYear()+'-'+pad(t.getMonth()+1)+'-'+pad(t.getDate());
  var fut=WEEKS.filter(function(w){return w.d>=today;});   /* next Sunday (or today) if its guide is up */
  if(fut.length)return fut[fut.length-1].d;                /* WEEKS is newest-first, so the last future one is the nearest */
  return WEEKS.length?WEEKS[0].d:null;}                    /* otherwise the most recent past Sunday */
function idx(d){for(var i=0;i<WEEKS.length;i++)if(WEEKS[i].d===d)return i;return -1;}
var q=new URLSearchParams(location.search),stored=null;try{stored=localStorage.getItem('lang');}catch(e){}
var lang=q.get('lang')||stored||'zh',cur=(q.get('d')&&idx(q.get('d'))>=0)?q.get('d'):pick();
WEEKS.forEach(function(w){var o=document.createElement('option');o.value=w.d;o.textContent=fmt(w.d);sel.appendChild(o);});
function load(){var w=WEEKS[idx(cur)];if(!w){document.body.innerHTML='<div id="empty">还没有内容。</div>';return;}
  if(lang==='en'&&!w.en)lang='zh';if(lang==='zh'&&!w.zh)lang='en';
  var file=lang==='en'?w.en:w.zh;if(f.getAttribute('src')!=='/church/'+file)f.src='/church/'+file;
  sel.value=cur;lb.textContent=lang==='en'?'中':'E';lb.className=lang==='en'?'':'toen';lb.disabled=lang==='en'?!w.zh:!w.en;
  try{localStorage.setItem('lang',lang);}catch(e){}
}
function buildSections(){sec.innerHTML='';var d=null;try{d=f.contentDocument;}catch(e){}
  var o=document.createElement('option');o.value='';o.textContent=(lang==='en'?'Sections':'目录')+' ▾';sec.appendChild(o);if(!d)return;
  var hs=d.querySelectorAll('h1[id],h2[id],h3[id]');for(var i=0;i<hs.length;i++){var h=hs[i],c=h.cloneNode(true),ups=c.querySelectorAll('a');
    for(var j=0;j<ups.length;j++)ups[j].parentNode.removeChild(ups[j]);
    var txt=(c.textContent||'').replace(/\\s+/g,' ').trim(),k=txt.indexOf(' — ');if(k>8)txt=txt.slice(0,k);if(!txt)continue;
    var op=document.createElement('option');op.value=h.id;op.textContent=(h.tagName==='H1'?'':'· ')+txt;sec.appendChild(op);}}
f.addEventListener('load',buildSections);
sec.addEventListener('change',function(){var id=sec.value;sec.selectedIndex=0;if(!id)return;var d=null;try{d=f.contentDocument;}catch(e){}
  var el=d&&d.getElementById(id);if(el){el.scrollIntoView({block:'start'});}});
sel.addEventListener('change',function(){cur=sel.value;load();});
lb.addEventListener('click',function(){lang=(lang==='en')?'zh':'en';load();});
load();
})();
</script>''' + SW_TAG + '''
</body></html>
'''
(ROOT / "index.html").write_text(html, encoding="utf-8")
(ROOT.parent / "church.html").write_text('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=/church/"><title>沙市堂 主日崇拜指南</title></head><body><a href="/church/">/church/</a></body></html>\n', encoding="utf-8")
print("index.html (app) written with weeks:", ", ".join(w["d"] for w in WEEKS), "| church.html redirect written")
