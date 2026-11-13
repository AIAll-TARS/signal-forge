"""Local-only browser cockpit for Signal Forge, built with the Python standard library."""
from __future__ import annotations
import json, shutil, subprocess, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .brief import as_json, markdown
from .collect import ingest_url
from .pipeline import run_collect
from .scoring import Analyst
from .sources import save_source, sync_registry
from .store import Store

SHELL = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal Forge | Galia Green Power</title><style>
:root{--bg:#09110f;--panel:#101c19;--line:#254039;--ink:#e7f2ec;--muted:#91aaa0;--lime:#86e48d;--amber:#ffc96b;--red:#ff8375}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#16342b,#09110f 55%);color:var(--ink);font:15px system-ui,-apple-system,Segoe UI,sans-serif}header{display:flex;align-items:center;justify-content:space-between;padding:20px max(5vw,24px);border-bottom:1px solid var(--line)}.brand{font-size:22px;font-weight:800;letter-spacing:.04em}.brand small{display:block;color:var(--lime);font-size:10px;letter-spacing:.18em;margin-top:4px}.status{color:var(--muted);font-size:13px}.dot{color:var(--lime)}main{max-width:1440px;margin:auto;padding:28px max(5vw,24px)}nav{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 25px}button,.button,input,select{border:1px solid var(--line);border-radius:8px;background:#142620;color:var(--ink);padding:10px 12px;font:inherit}button,.button{cursor:pointer}.button.primary{background:var(--lime);color:#07100c;border-color:var(--lime);font-weight:700}.tabs button.active{background:#254a3d}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:linear-gradient(145deg,#12221e,#0e1916);border:1px solid var(--line);border-radius:12px;padding:18px}.metric b{display:block;font-size:30px;color:var(--lime);margin-top:8px}.muted{color:var(--muted)}a{color:var(--lime)}h1{font-size:26px;margin:8px 0}h2{font-size:18px;margin-top:0}.page{display:none}.page.active{display:block}.list{display:grid;gap:12px;margin-top:18px}.finding{border-left:3px solid var(--lime)}.priority{font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.1em}.critical{color:var(--red)}.high{color:var(--amber)}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:12px}form{display:grid;grid-template-columns:1fr 1fr;gap:10px}.full{grid-column:1/-1}pre{white-space:pre-wrap;font:14px ui-monospace,monospace;line-height:1.55}.empty{padding:30px;text-align:center;color:var(--muted)}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}@media(max-width:800px){.grid{grid-template-columns:repeat(2,1fr)}form{grid-template-columns:1fr}header{align-items:flex-start;gap:14px;flex-direction:column}}@media(max-width:480px){.grid{grid-template-columns:1fr}main{padding:20px}th:nth-child(4),td:nth-child(4){display:none}}
</style></head><body><header><div class="brand">SIGNAL FORGE<small>GALIA GREEN POWER · INVESTMENT INTELLIGENCE</small></div><div class="status"><span class="dot">●</span> <span id="db">Checking local database</span></div></header><main><nav class="tabs" aria-label="Cockpit sections"><button class="active" data-page="overview">Overview</button><button data-page="findings">Findings</button><button data-page="sources">Sources</button><button data-page="briefing">Briefing</button><button class="primary" id="scan">Run RSS / Atom scan</button></nav>
<section id="overview" class="page active"><h1>Decision cockpit</h1><p class="muted">A local-first watchtower for Polish and EU biogas and biomethane signals.</p><div class="grid" id="metrics"></div><div class="list" id="latest"></div></section>
<section id="findings" class="page"><h1>Findings</h1><div class="tools"><input id="search" placeholder="Search topic, source, rationale"><select id="priority"><option value="">All priorities</option><option>critical</option><option>high</option><option>watch</option></select></div><div class="card"><table><thead><tr><th>Priority</th><th>Topic / finding</th><th>Score</th><th>Source</th><th>Rationale</th></tr></thead><tbody id="findings-body"></tbody></table><div id="findings-empty" class="empty"></div></div></section>
<section id="sources" class="page"><h1>Source registry</h1><p class="muted" id="registry-note">The source list is a file you can edit on its own. This window reads it.</p><div class="card"><h2>Add a monitored feed</h2><form id="source-form"><input name="name" placeholder="Source name" required><input name="url" type="url" placeholder="https://… RSS or Atom URL" required><input name="authority" placeholder="Authority (primary, industry…)" value="unknown"><input name="topics" placeholder="Topics, comma separated"><button class="primary full">Add to the source file</button></form><p id="source-message" class="muted"></p></div><div class="list" id="sources-list"></div><div class="card"><h2>Capture one decision signal</h2><p class="muted">Paste a public article or announcement. Signal Forge will fetch it only when you submit it, analyse it locally, and add it to Findings.</p><form id="ingest-form"><input class="full" name="url" type="url" placeholder="https://… article or announcement URL" required><input name="topics" placeholder="Topics, comma separated"><button class="primary full">Capture and analyse</button></form><p id="ingest-message" class="muted"></p></div></section>
<section id="briefing" class="page"><h1>Investment briefing</h1><div class="tools"><button id="export-json">Export JSON</button><button id="export-md">Export Markdown</button></div><article class="card"><pre id="brief"></pre></article></section></main><script>
const $=s=>document.querySelector(s);let data={items:[]};
async function api(path,opt){let r=await fetch(path,opt);let j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
function esc(x){return String(x??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function priority(x){return `<span class="priority ${esc(x)}">${esc(x||'unscored')}</span>`}
function published(v){if(!v)return 'No published time in the feed';if(/^\d{4}-\d{2}-\d{2}$/.test(String(v)))return v+' · no time in the feed';let d=new Date(v);if(Number.isNaN(d.getTime()))return String(v);let parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23',timeZoneName:'longOffset'}).formatToParts(d);let g=t=>parts.find(p=>p.type===t).value;return `${g('year')}-${g('month')}-${g('day')} ${g('hour')}:${g('minute')}:${g('second')} ${g('timeZoneName')}`}
function sourceLink(url,label){if(!/^https?:\/\//i.test(url||''))return esc(label||url||'No link');return `<a href="${String(url).replace(/"/g,'%22')}" target="_blank" rel="noopener">${esc(label||url)}</a>`}
async function refresh(){data=await api('/api/status');let c=data.collector;$('#db').textContent=`Vault online · ${data.metrics.sources} sources`+(c?` · collector ${c.created_at}`:' · collector waiting');if($('#registry-note')){if(data.registry_error)$('#registry-note').textContent='Source file problem: '+data.registry_error;else if(data.registry)$('#registry-note').textContent=`Source file: ${data.registry}. Edit it in any editor. The collector reads that file on its own.`;}$('#metrics').innerHTML=[['Sources',data.metrics.sources],['Collected items',data.metrics.items],['Critical findings',data.metrics.critical],['High findings',data.metrics.high]].map(x=>`<div class="card metric"><span class="muted">${x[0]}</span><b>${x[1]}</b></div>`).join('');let f=data.items;$('#latest').innerHTML=f.length?f.slice(0,5).map(x=>`<article class="card finding"><div>${priority(x.priority)} · ${esc(x.source_name||'Direct ingest')}</div><h2>${sourceLink(x.url,x.title)}</h2><p class="muted">${published(x.published_at)} · ${sourceLink(x.url,'Open source')}</p><p>${esc(x.why_it_matters||'Unscored signal. Run a scan, then score it from the CLI if needed.')}</p><p class="muted">${esc(x.recommendation||'Review source evidence.')}</p></article>`).join(''):'<div class="card empty">No findings yet. Add trusted RSS or Atom sources, then run a scan to begin building decision-ready intelligence.</div>';renderFindings();renderSources();$('#brief').textContent=data.markdown}
function renderFindings(){let q=$('#search').value.toLowerCase(),p=$('#priority').value;let a=data.items.filter(x=>(!p||x.priority===p)&&JSON.stringify(x).toLowerCase().includes(q));$('#findings-body').innerHTML=a.map(x=>`<tr><td>${priority(x.priority)}</td><td><b>${sourceLink(x.url,x.title)}</b><br><span class="muted">${published(x.published_at)} · ${sourceLink(x.url,'Open source')}</span><br><span class="muted">${esc(x.impact||'Awaiting analysis')}</span></td><td>${esc(x.score??'—')}</td><td>${esc(x.source_name||'Direct ingest')}</td><td>${esc(x.rationale||'Not scored yet')}</td></tr>`).join('');$('#findings-empty').textContent=a.length?'':'No matching findings. Run a scan after adding RSS/Atom sources to produce useful output.'}
function renderSources(){$('#sources-list').innerHTML=data.sources.length?data.sources.map(x=>`<div class="card"><b>${esc(x.name)}</b><p class="muted">${esc(x.url)}</p><span>${esc(x.authority||'unknown')} · ${esc(x.scan_method)}</span></div>`).join(''):'<div class="card empty">No sources configured. Add an official Polish/EU RSS or Atom feed above, then run a scan.</div>'}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-page],.page').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.page).classList.add('active')});$('#search').oninput=renderFindings;$('#priority').onchange=renderFindings;
$('#source-form').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));o.topics=o.topics.split(',').map(x=>x.trim()).filter(Boolean);try{let r=await api('/api/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});$('#source-message').textContent=r.created?'Source written to the source file. The collector fetches it on the next pass.':'That source is already in the file.';e.target.reset();await refresh()}catch(err){$('#source-message').textContent=err.message}};
$('#ingest-form').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));o.topics=o.topics.split(',').map(x=>x.trim()).filter(Boolean);let out=$('#ingest-message');out.textContent='Capturing source…';try{let r=await api('/api/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});out.textContent=r.created?'Signal captured and analysed.':'This signal is already in the vault.';e.target.reset();await refresh()}catch(err){out.textContent=err.message}};$('#scan').onclick=async()=>{let b=$('#scan');b.textContent='Scanning configured feeds…';b.disabled=true;try{let r=await api('/api/scan',{method:'POST'});alert(`Scan completed: ${r.added} new item(s), ${r.scored} scored.`+(r.errors&&r.errors.length?'\n'+r.errors.join('\n'):'')+(r.skipped?'\n'+r.skipped+' source(s) are web pages, not RSS or Atom feeds. Paste one article under Sources, Capture one decision signal.':''));await refresh()}catch(e){alert(e.message)}finally{b.textContent='Run RSS / Atom scan';b.disabled=false}};function download(path,name){fetch(path).then(r=>r.blob()).then(b=>{let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;a.click()})}$('#export-json').onclick=()=>download('/api/briefing?format=json','signal-forge-briefing.json');$('#export-md').onclick=()=>download('/api/briefing?format=md','signal-forge-briefing.md');refresh();</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    db_path = 'signal-forge.db'
    sources_path = None
    def log_message(self, fmt, *args): pass
    def send_json(self, payload, status=200):
        body=json.dumps(payload, ensure_ascii=False, default=str).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def store(self): s=Store(self.db_path);s.init();return s
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=='/':
            body=SHELL.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        s=self.store()
        try:
            registry_error=self._sync(s)
            rows=s.items();
            if p.path in ('/api/health','/api/status'):
                sources=s.sources(); m={'sources':len(sources),'items':len(rows),'critical':sum(r['priority']=='critical' for r in rows),'high':sum(r['priority']=='high' for r in rows)}
                log=s.last_log('watch'); collector=None if log is None else {'status':log['status'],'detail':log['detail'],'created_at':log['created_at']}
                self.send_json({'ok':True,'db':s.path,'registry':self.sources_path,'registry_error':registry_error,'collector':collector,'metrics':m,'sources':[dict(x) for x in sources],'items':[dict(x) for x in rows],'markdown':markdown(rows)})
            elif p.path=='/api/briefing':
                fmt=parse_qs(p.query).get('format',['json'])[0]; body=(markdown(rows) if fmt=='md' else as_json(rows)).encode();self.send_response(200);self.send_header('Content-Type','text/markdown; charset=utf-8' if fmt=='md' else 'application/json; charset=utf-8');self.end_headers();self.wfile.write(body)
            else:self.send_json({'error':'Not found'},404)
        finally:s.close()
    def do_POST(self):
        if self.path not in ('/api/sources','/api/scan','/api/ingest'):return self.send_json({'error':'Not found'},404)
        s=self.store()
        try:
            if self.path=='/api/sources':
                n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) or b'{}');
                if not d.get('name') or not d.get('url') or not d['url'].startswith(('http://','https://')):raise ValueError('A name and http(s) feed URL are required.')
                source={'name':d['name'],'url':d['url'],'authority':d.get('authority','unknown'),'topics':d.get('topics',[]),'scan_method':'rss'}
                if self.sources_path:
                    created=save_source(self.sources_path, source); self._sync(s); row=s.source_by_url(d['url']); self.send_json({'id':row['id'],'created':created,'registry':self.sources_path},201 if created else 200)
                else:
                    sid,created=s.add_source(source);self.send_json({'id':sid,'created':created},201 if created else 200)
            elif self.path=='/api/ingest':
                n=int(self.headers.get('Content-Length','0'));d=json.loads(self.rfile.read(n) or b'{}')
                if not d.get('url') or not d['url'].startswith(('http://','https://')):raise ValueError('A public http(s) URL is required.')
                item=ingest_url(d['url'], topics=d.get('topics',[]));iid,created=s.add_item(item)
                if created:s.save_analysis(iid,Analyst().analyze(item))
                self.send_json({'id':iid,'created':created},201 if created else 200)
            else:
                self._sync(s); result=run_collect(s); self.send_json(result)
        except (ValueError,json.JSONDecodeError) as e:self.send_json({'error':str(e)},400)
        finally:s.close()
    def _sync(self, store):
        if not self.sources_path: return None
        try: sync_registry(store, self.sources_path); return None
        except Exception as exc: return str(exc)

def open_local(url: str) -> None:
    """Open the cockpit in the Windows browser. WSL gio cannot open URLs here."""
    if shutil.which('cmd.exe'):
        subprocess.run(['cmd.exe', '/c', 'start', '', url], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if shutil.which('wslview'):
        subprocess.run(['wslview', url], check=False)
        return
    try:
        webbrowser.open(url)
    except Exception:
        print(f'Open this in your browser: {url}')

def serve(host='127.0.0.1',port=8765,db='signal-forge.db',open_browser=False,sources=None):
    Handler.db_path=db; Handler.sources_path=sources
    if sources:
        store=Store(db); store.init()
        try: sync_registry(store, sources)
        finally: store.close()
    server=ThreadingHTTPServer((host,port),Handler)
    if open_browser: threading.Timer(.25,lambda:open_local(f'http://{host}:{port}/')).start()
    print(f'Signal Forge cockpit running at http://{host}:{port}/');server.serve_forever()
