#!/usr/bin/env python3

import html
import os
import urllib.parse
import datetime

from . import ui_shell


def _glass(tmpl):
    """Fill Liquid Glass shell placeholders inside a page template."""
    return (tmpl
            .replace('__CSS__', ui_shell.GLASS_CSS)
            .replace('__BODY_OPEN__', ui_shell.GLASS_BODY_OPEN)
            .replace('__EXTRA_SCRIPTS__',
                     '<script>' + ui_shell.THEME_JS + '</script>\n'
                     '<script>' + ui_shell.LIQUID_JS + '</script>'))


def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / (1024**2):.2f} MB"
    else:
        return f"{size / (1024**3):.2f} GB"


def _base_css():
    return """
    @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');
    *{box-sizing:border-box}
    html,body{margin:0;padding:0;font-family:'VT323',monospace;background:#000;color:#00ff00;
        transition:background-color .3s ease,color .3s ease}
    body.light-theme{background:#ffffff;color:#000000}
    body.light-theme .text-neon{color:#000000}
    .text-neon{color:#00ff00}
    input,textarea,button,select{background:#111111;color:#00ff00;border:1px solid #00ff00;
        padding:.45rem;font-family:'VT323',monospace;transition:all .3s ease;border-radius:4px}
    body.light-theme input,body.light-theme textarea,body.light-theme button,
    body.light-theme select{background:#f8f9fa;color:#000;border-color:#000}
    input:focus,textarea:focus{outline:none;box-shadow:0 0 5px rgba(0,255,0,.5)}
    body.light-theme input:focus,body.light-theme textarea:focus{box-shadow:0 0 5px rgba(0,0,0,.3)}
    button{cursor:pointer}
    button:hover{background:rgba(0,255,0,.12)}
    body.light-theme button:hover{background:rgba(0,0,0,.08)}
    table{width:100%;border-collapse:collapse}
    th,td{text-align:left;padding:.5rem;border-bottom:1px solid rgba(0,255,0,.3)}
    body.light-theme th,body.light-theme td{border-bottom-color:rgba(0,0,0,.25)}
    th{background-color:rgba(0,255,0,.1);cursor:pointer;position:sticky;top:0;z-index:5}
    body.light-theme th{background-color:rgba(0,0,0,.08)}
    tr:nth-child(even){background-color:rgba(0,255,0,.05)}
    body.light-theme tr:nth-child(even){background-color:rgba(0,0,0,.04)}
    ::-webkit-scrollbar{width:8px;height:8px}
    ::-webkit-scrollbar-track{background:rgba(0,255,0,.08)}
    ::-webkit-scrollbar-thumb{background:#00ff00;border-radius:4px}
    body.light-theme ::-webkit-scrollbar-thumb{background:#000}
    .btn-green{background:#033200!important;color:#0f0!important;border:1px solid #0f0}
    body.light-theme .btn-green{background:#000!important;color:#fff!important;border-color:#000}
    .glitch{position:relative;animation:glitch 6s infinite}
    @keyframes glitch{0%,93%,100%{transform:translate(0)}95%{transform:translate(-1px,1px)}97%{transform:translate(1px,-1px)}}
    """


# ---------------------------------------------------------------------------
# main directory page
# ---------------------------------------------------------------------------
def list_directory_page(handler, path):
    try:
        entries = os.listdir(path)
    except OSError:
        handler.send_error(404, "Cannot list directory")
        return None

    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    search_query = query_params.get('q', [''])[0]
    sort_by = query_params.get('sort', ['name'])[0]
    sort_order = query_params.get('order', ['asc'])[0]

    if search_query:
        entries = [e for e in entries if search_query.lower() in e.lower()]

    def sort_key(item):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            return (0, item.lower())
        if sort_by == 'size':
            return (1, os.path.getsize(item_path))
        elif sort_by == 'date':
            return (1, os.path.getmtime(item_path))
        return (1, item.lower())

    entries.sort(key=sort_key, reverse=sort_order == 'desc')
    displaypath = html.escape(urllib.parse.unquote(handler.path))

    rows = []
    if handler.path != '/':
        parent = os.path.dirname(handler.path.rstrip('/'))
        if not parent.endswith('/'):
            parent += '/'
        rows.append(_parent_row(parent))

    for name in entries:
        fullpath = os.path.join(path, name)
        displayname = name + '/' if os.path.isdir(fullpath) else name
        href = urllib.parse.quote(name)
        if os.path.isdir(fullpath):
            href += '/'
        size = "-"
        date_modified = "-"
        if os.path.isfile(fullpath):
            try:
                size = format_size(os.path.getsize(fullpath))
                date_modified = datetime.datetime.fromtimestamp(
                    os.path.getmtime(fullpath)).strftime('%Y-%m-%d %H:%M:%S')
            except OSError:
                pass
        rows.append(_entry_row(href, displayname, size, date_modified,
                               os.path.isdir(fullpath),
                               prefix=handler.path))

    list_html = '\n'.join(rows)
    editable_exts = ('.txt', '.py', '.js', '.html', '.css', '.json', '.xml',
                     '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')

    page = _DIRECTORY_TEMPLATE
    page = page.replace('__TITLE__', displaypath)
    page = page.replace('__DISPLAYPATH__', displaypath)
    page.replace('__SEARCH__', html.escape(search_query))
    page = page.replace('__ROWS__', list_html)
    page = page.replace('__EDITABLE_EXTS__', ','.join(editable_exts))
    page = page.replace('__SORTNAME__',
                        '↓' if sort_by == 'name' and sort_order == 'desc' else
                        ('↑' if sort_by == 'name' else ''))
    page = page.replace('__SORTSIZE__',
                        '↓' if sort_by == 'size' and sort_order == 'desc' else
                        ('↑' if sort_by == 'size' else ''))
    page = page.replace('__SORTDATE__',
                        '↓' if sort_by == 'date' and sort_order == 'desc' else
                        ('↑' if sort_by == 'date' else ''))
    return _glass(page)


def _parent_row(parent):
    p = html.escape(parent)
    return f"""
<tr class="hover:bg-green-900/20 cursor-pointer" onclick="navigateToPath('{p}')">
 <td class="py-2 px-4">📁 .. (Parent Directory)</td>
 <td class="py-2 px-4 text-right">-</td><td class="py-2 px-4 text-right">-</td>
 <td class="py-2 px-4 text-right">-</td></tr>"""


def _entry_row(href, displayname, size, date_modified, is_dir, prefix="/"):
    h = href
    dn = html.escape(displayname)
    full = (prefix.rstrip('/') + '/' + h) if prefix != '/' else ('/' + h)
    if is_dir:
        icon = "📁"
        actions = (f"<button onclick=\"event.stopPropagation();downloadFolder('{h}')\" "
                   f"title='Download as zip'>📦</button>"
                   f"<button onclick=\"event.stopPropagation();"
                   f"trashFile(escJs('{full}'))\" title='Move to trash'>🗑️</button>")
    else:
        ext = os.path.splitext(displayname)[1].lower()
        media_video = ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']
        media_audio = ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac']
        media_img = ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        icon = ("🎬" if media_video else "🎵" if media_audio else
                "🖼️" if media_img else "📄")
        edit_btn = ""
        if ext in ('.txt', '.py', '.js', '.html', '.css', '.json', '.xml',
                   '.md', '.log', '.cfg', '.ini', '.yml', '.yaml'):
            edit_btn = (f"<button onclick=\"event.stopPropagation();"
                        f"editFile('{h}')\" title='Edit'>✏️</button>")
        actions = (f"<button onclick=\"event.stopPropagation();previewFile('{h}')\" title='Preview'>👁️</button>"
                   f"{edit_btn}"
                   f"<button onclick=\"event.stopPropagation();makeEphemeral('{h}','{dn}')\" "
                   f"title='Create self-destructing link'>⏳</button>"
                   f"<button onclick=\"event.stopPropagation();versionsDialog(escJs('{full}'))\" "
                   f"title='Saved versions'>🕘</button>"
                   f"<button onclick=\"event.stopPropagation();"
                   f"trashFile(escJs('{full}'))\" title='Move to trash'>🗑️</button>"
                   f"<button onclick=\"event.stopPropagation();downloadFile('{h}','{dn}')\" "
                   f"title='Download'>⬇️</button>")
    return f"""
<tr class="hover:bg-green-900/20 cursor-pointer" data-name="{dn.lower()}" onclick="navigateToPath('{h}')">
 <td class="py-2 px-4"><span class="text-neon">{icon} {dn}</span></td>
 <td class="py-2 px-4 text-right">{size}</td>
 <td class="py-2 px-4 text-right">{date_modified}</td>
 <td class="py-2 px-4 text-right">{actions}</td></tr>"""


_DIRECTORY_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PyServeX v4 - __TITLE__</title>
<style>
__CSS__
 /* layout */
 html,body{height:100vh;overflow:hidden}
 .main-container{display:flex;height:100vh;flex-direction:column}
 .header{height:84px;flex-shrink:0;display:flex;align-items:center;justify-content:center;
     position:relative;margin:14px 14px 0}
 .header .links{position:absolute;left:16px;top:50%;transform:translateY(-50%);
     display:flex;gap:8px;z-index:5}
 .header .links a{color:var(--text-primary)}
 .content-area{flex:1;display:flex;gap:14px;padding:14px;overflow:hidden}
 .file-explorer{width:60%;display:flex;flex-direction:column;overflow:hidden;padding:0}
 .search-controls{padding:.9rem 1rem;border-bottom:1px solid var(--glass-border);flex-shrink:0;
      position:relative}
  .search-drop{position:absolute;left:1rem;right:1rem;top:100%;z-index:40;
      background:rgba(18,20,30,.96);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);
      border:1px solid var(--glass-border);border-radius:var(--radius-btn);
      box-shadow:var(--glass-shadow);max-height:320px;overflow:auto}
  .search-hit{padding:.5rem .8rem;display:flex;flex-direction:column;gap:2px;cursor:pointer;
      border-bottom:1px solid var(--glass-border)}
  .search-hit:hover{background:rgba(255,255,255,.06)}
  .search-sub{font-size:.72rem;color:var(--text-secondary);
      font-family:ui-monospace,Consolas,monospace}
  .search-snip{font-size:.78rem;color:var(--text-secondary);white-space:nowrap;
      overflow:hidden;text-overflow:ellipsis}
 .file-list-container{flex:1;overflow-y:auto;padding:.25rem .5rem}
 .text-panel{width:40%;display:flex;flex-direction:column;overflow:hidden;padding:0}
 .text-area{flex:1;display:flex;flex-direction:column;padding:1rem;overflow:hidden}
 .text-content{flex:1;resize:none}
 .row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;align-items:center}
 .upload-progress{margin-top:.6rem;padding:.6rem;border:1px dashed var(--glass-border);
     border-radius:var(--radius-btn);display:none;
     background:rgba(255,255,255,.03)}
 .progress-bar{width:0%;height:18px;border-radius:9px;color:#fff;font-size:.85rem;
     text-align:center;line-height:18px;transition:width .2s ease;
     background:linear-gradient(90deg,var(--accent),var(--accent-2),#bf5af2);
     background-size:200% 100%;animation:pbFlow 2.4s linear infinite}
 @keyframes pbFlow{to{background-position:200% 0}}
 #dropOverlay{position:absolute;inset:0;display:none;z-index:50;pointer-events:none;
     align-items:center;justify-content:center;font-size:1.6rem;font-weight:600;
     color:var(--text-primary);border-radius:inherit;
     background:rgba(10,132,255,.14);
     -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
 dialog input{width:100%;margin:4px 0 10px}
 @media(max-width:900px){.content-area{flex-direction:column}.file-explorer{width:100%;height:60%}
     .text-panel{width:100%;height:40%}}
</style>
</head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>

<div class="main-container">
 <div class="header">
   <div class="links">
<a class="glass-btn" href="/p2p" target="_blank">📡 P2P</a>
      <a class="glass-btn" href="/tokens" target="_blank">🔑 Tokens</a>
      <a class="glass-btn" href="/trash">🗑️</a>
      <button class="glass-btn" onclick="openSftpDialog()">🖥 SFTP / SCP</button>
     <a class="glass-btn" id="tunnelChip" style="display:none" target="_blank" rel="noopener"
        title="public share link — anyone on the internet can open this"></a>
   </div>
   <div class="text-center" id="lgHero">
     <h1 style="margin:0;font-size:2rem;font-weight:700;letter-spacing:-.02em" class="text-neon">PyServeX v4.0</h1>
     <p style="margin:0;color:var(--text-secondary);font-size:.92rem">secure • resumable • P2P-ready file server</p>
   </div>
 </div>

 <div class="content-area">
  <div class="file-explorer glass-panel" id="dropZone" style="position:relative">
    <div class="search-controls" id="searchControls">
      <div class="row">
        <h2 style="margin:0;flex:1;font-size:1.05rem;font-weight:600">📁 __DISPLAYPATH__</h2>
        <label class="glass-input" style="white-space:nowrap;display:inline-flex;gap:6px;align-items:center;padding:.35rem .6rem">🐢 Limit
          <select id="speedSel" onchange="setSpeed(this.value)" class="glass-btn" style="padding:.3rem .5rem">
            <option value="">off</option>
            <option value="64K">64 KB/s</option>
            <option value="256K">256 KB/s</option>
            <option value="1M">1 MB/s</option>
            <option value="2M">2 MB/s</option>
            <option value="5M">5 MB/s</option>
          </select></label>
      </div>
      <div class="row">
        <span id="liveBadge" style="font-size:.72rem;color:var(--success);letter-spacing:.08em">● LIVE</span>
        <input type="text" id="searchInput" placeholder="🔍 instant search (whole share)…" class="glass-input" style="flex:1;min-width:160px">
        <button onclick="clearSearch()" class="glass-btn">Clear</button>
      </div>
      <div id="searchDrop" class="search-drop" style="display:none"></div>
      <form id="uploadForm" class="row">
        <input type="file" id="fileUpload" multiple class="glass-input" style="flex:1;min-width:180px">
        <button type="submit" class="glass-btn-accent">⬆ Upload</button>
        <button type="button" onclick="createNewFolder()" class="glass-btn">📁 Folder</button>
        <button type="button" onclick="createNewFile()" class="glass-btn">📄 File</button>
      </form>
      <div id="uploadProgress" class="upload-progress">
        <div id="progressBar" class="progress-bar"></div>
        <div id="progressText" style="text-align:center;margin-top:4px"></div>
      </div>
    </div>
    <div id="dropOverlay"><span>⬇ drop files / folders ⬇</span></div>

    <div class="file-list-container">
      <table>
        <thead><tr>
          <th onclick="sortFiles('name')">📄 Name __SORTNAME__</th>
          <th onclick="sortFiles('size')" class="text-right">📏 Size __SORTSIZE__</th>
          <th onclick="sortFiles('date')" class="text-right">📅 Modified __SORTDATE__</th>
          <th class="text-right">⚡ Actions</th>
        </tr></thead>
        <tbody id="fileTableBody">
__ROWS__
        </tbody>
      </table>
    </div>
  </div>

  <div class="text-panel glass-panel">
   <div class="text-area">
    <div class="row" style="justify-content:space-between">
      <h3 style="margin:0;font-size:1.05rem;font-weight:600">📝 Text Clipboard
        <span id="clipLive" style="font-size:.72rem;color:var(--success);
          letter-spacing:.08em">● LIVE</span></h3>
      <div class="row" style="margin:0">
        <button onclick="saveTextClipboard()" class="glass-btn-success" style="padding:.4rem .75rem">💾 Save</button>
        <button onclick="clearTextClipboard()" class="glass-btn-danger" style="padding:.4rem .75rem">🗑️</button>
        <button onclick="copyToClipboard()" class="glass-btn" style="padding:.4rem .75rem">📋 Copy</button>
      </div>
    </div>
    <textarea id="textClipboard" class="glass-input text-content"
      placeholder="📝 persistent text clipboard…"></textarea>
    <div id="clipboardStatus" style="text-align:center;font-size:.9rem"></div>
   </div>
  </div>
 </div>
</div>

<!-- ephemeral dialog -->
<dialog id="ephDialog" class="glass-dialog">
  <h3 style="margin-top:0">⏳ Self-destructing link</h3>
  <p id="ephFile" class="mono"></p>
  <label>Expires after (seconds)<input id="ephTtl" type="number" value="3600" min="30" max="604800" class="glass-input"></label>
  <label>Max downloads<input id="ephMax" type="number" value="1" min="1" max="999" class="glass-input"></label>
  <div id="ephResult" style="display:none">
    <label>One-time URL<input id="ephUrl" readonly class="glass-input mono"></label>
    <button onclick="copyEphemeral()" class="glass-btn-accent">Copy</button>
  </div>
  <div class="row" style="justify-content:flex-end;margin-top:8px">
    <button onclick="createEphemeralLink()" id="ephGo" class="glass-btn-accent">Generate</button>
    <button onclick="document.getElementById('ephDialog').close()" class="glass-btn">Close</button>
  </div>
</dialog>

<!-- sftp/scp connect dialog -->
<dialog id="sftpDialog" class="glass-dialog" style="max-width:700px">
  <h3 style="margin-top:0">🖥 SFTP / SCP connections</h3>

  <h4 style="margin:.2rem 0 .5rem;font-size:.95rem">New connection</h4>
  <div class="row">
    <input id="sp_alias" class="glass-input" placeholder="alias (e.g. home-nas)"
           style="flex:1;min-width:130px">
    <input id="sp_host" class="glass-input" placeholder="hostname or IP *"
           style="flex:1.4;min-width:160px">
    <input id="sp_port" class="glass-input" type="number" value="22" min="1" max="65535"
           title="SSH port" style="width:86px">
  </div>
  <div class="row">
    <input id="sp_user" class="glass-input" placeholder="username"
           style="flex:1;min-width:130px">
    <select id="sp_auth" class="glass-input" onchange="sftpAuthUi()"
            style="width:auto;min-width:150px">
      <option value="password">Password</option>
      <option value="key">SSH key</option>
      <option value="cert">Certificate</option>
      <option value="fido2">FIDO2 / hardware key</option>
    </select>
  </div>
  <div class="row" id="sp_authrows"></div>
  <div class="row">
    <button class="glass-btn-accent" onclick="sftpConnect()">Connect ▸ build commands</button>
    <button class="glass-btn-success" onclick="spBrowse()">🔌 Connect &amp; browse files</button>
  </div>
  <div id="sp_browse" style="display:none;margin-top:10px">
    <div class="row" style="justify-content:space-between;align-items:center">
      <b id="sp_bpath" class="mono" style="font-size:.85rem"></b>
      <div class="row" style="margin:0">
        <button class="glass-btn" style="padding:.25rem .6rem"
                onclick="spNav(spHome)">⌂ home</button>
        <button class="glass-btn-danger" style="padding:.25rem .6rem"
                onclick="spCloseSession()">disconnect</button>
      </div>
    </div>
    <div id="sp_entries" style="max-height:260px;overflow:auto;margin-top:6px"></div>
  </div>
  <div class="row" id="sp_savebar" style="display:none;margin-top:6px;padding:10px;
      border:1px dashed var(--glass-border);border-radius:var(--radius-btn)">
    <span style="flex:1;font-size:.9rem;color:var(--text-secondary)">
      Save this connection?</span>
    <button class="glass-btn-success" onclick="sftpFinish(true)">💾 Save permanently</button>
    <button class="glass-btn" onclick="sftpFinish(false)">Skip (use once)</button>
  </div>

  <h4 style="margin:.9rem 0 .4rem;font-size:.95rem">Saved connections
    <span class="hint">(stored only in this browser)</span></h4>
  <div id="sp_list"></div>

  <pre id="sftpCmds" class="mono doc-code" style="display:none"></pre>
  <div class="row" style="justify-content:flex-end;margin-top:8px">
    <button onclick="copySftpCmds()" id="sp_copy" class="glass-btn-accent"
            style="display:none">📋 Copy commands</button>
    <button class="glass-btn" onclick="document.getElementById('sftpDialog').close()">Close</button>
  </div>
</dialog>

__EXTRA_SCRIPTS__
<script>
/* ============================ state ============================ */
const EDITABLE_EXTS = '__EDITABLE_EXTS__'.split(',');
const CHUNK_SIZE = 1024*1024;           // 1 MiB chunks
const CHUNK_THRESHOLD = 8*1024*1024;    // files above go chunked/resumable
let currentPath = '__DISPLAYPATH__';
let searchTimeout;

window.onload = function(){
  initTheme(); loadTextClipboard(); setupRealTimeSearch(); setupUploadHandling();
  startLiveRefresh();
};

/* ============================ theme ============================ */
/* provided by the Liquid Glass shell (THEME_JS) — initTheme() */

/* ============================ sftp/scp manager ============================ */
const SP_KEY='pyservx_sftp_profiles';
let spDraft=null,spCmdText='';

function spLoadAll(){
  try{return JSON.parse(localStorage.getItem(SP_KEY)||'[]');}catch(e){return[];}
}
function spStoreAll(list){
  try{localStorage.setItem(SP_KEY,JSON.stringify(list));return true;}
  catch(e){showStatus('⚠ cannot save (storage blocked) — connection stays temporary');return false;}
}
function sftpAuthUi(){
  const m=document.getElementById('sp_auth').value;
  const r=document.getElementById('sp_authrows');
  let h='';
  if(m==='password'){
    h='<input id="sp_secret" type="password" class="glass-input" placeholder="password" style="flex:1;min-width:150px">';
  }else if(m==='key'||m==='fido2'){
    h='<input id="sp_key" class="glass-input" placeholder="'+
      (m==='fido2'?'~/.ssh/id_ed25519_sk (FIDO2 key)':'~/.ssh/id_ed25519 (private key path)')+
      '" style="flex:1;min-width:180px">'+
      '<input id="sp_sshid" class="glass-input" placeholder="SSH ID / key comment (optional)" style="flex:1;min-width:150px">';
    if(m==='fido2'){
      h+='<label class="hint" style="white-space:nowrap"><input type="checkbox" id="sp_res"> resident key</label>';
    }
  }else if(m==='cert'){
    h='<input id="sp_key" class="glass-input" placeholder="~/.ssh/id_ed25519 (private key path)" style="flex:1;min-width:170px">'+
      '<input id="sp_cert" class="glass-input" placeholder="~/.ssh/id_ed25519-cert.pub (certificate)" style="flex:1.3;min-width:190px">'+
      '<input id="sp_sshid" class="glass-input" placeholder="SSH ID / comment (optional)" style="flex:1;min-width:140px">';
  }
  r.innerHTML=h;
}
function sftpCollect(){
  const host=document.getElementById('sp_host').value.trim();
  if(!host){showStatus('hostname or IP is required');document.getElementById('sp_host').focus();return null;}
  return {
    alias:document.getElementById('sp_alias').value.trim()||host,
    host:host,
    port:+document.getElementById('sp_port').value||22,
    user:document.getElementById('sp_user').value.trim()||'your-username',
    auth:document.getElementById('sp_auth').value,
    secret:(document.getElementById('sp_secret')||{}).value||'',
    key:(document.getElementById('sp_key')||{}).value||'',
    cert:(document.getElementById('sp_cert')||{}).value||'',
    sshid:(document.getElementById('sp_sshid')||{}).value||'',
    resident:!!(document.getElementById('sp_res')&&document.getElementById('sp_res').checked)
  };
}
function sftpAuthFlags(p){
  let f='';
  if((p.auth==='key'||p.auth==='cert'||p.auth==='fido2')&&p.key)f+='-i '+p.key+' ';
  if(p.cert)f+='-o CertificateFile='+p.cert+' ';
  if(f)return f;
  return '';
}
function sftpBuildCommands(p){
  const U=(p.user||'user')+'@'+p.host,P=p.port||22,A=sftpAuthFlags(p);
  let t='# interactive session\nsftp '+A+'-P '+P+' '+U+
        '\n\n# upload a file\nscp '+A+'-P '+P+' myfile.txt '+U+':/'+
        '\n\n# download a file\nscp '+A+'-P '+P+' '+U+':/myfile.txt .';
  if(p.auth==='fido2'){
    t+='\n\n# FIDO2 note: create the key once with:\n'+
       'ssh-keygen -t ed25519-sk'+(p.resident?' -O resident':'');
  }
  if(p.secret){
    t+='\n\n# password auth cannot be passed on the scp/sftp command line;\n'+
       '# type it when prompted (or set up sshpass / keys for automation).';
  }
  return t;
}
function sftpConnect(){
  const p=sftpCollect();
  if(!p)return;
  spDraft=p;
  spCmdText=sftpBuildCommands(p);
  document.getElementById('sftpCmds').textContent=spCmdText;
  document.getElementById('sftpCmds').style.display='block';
  document.getElementById('sp_copy').style.display='';
  document.getElementById('sp_savebar').style.display='flex';
}
function sftpFinish(save){
  document.getElementById('sp_savebar').style.display='none';
  if(save&&spDraft){
    const saved={...spDraft};
    delete saved.secret;                 // never persist plaintext passwords
    const list=spLoadAll().filter(x=>x.alias!==saved.alias);
    list.push(saved);
    if(spStoreAll(list))renderSpList();
    showStatus('💾 saved "'+(saved.alias)+'" — it will appear here every time'+
      (spDraft.secret?' (password isn\\'t stored)':''));
  }else{
    showStatus('connection kept temporarily (until reload)');
  }
}
function renderSpList(){
  const list=spLoadAll(),box=document.getElementById('sp_list');
  box.innerHTML=list.length?'':'<p class="hint" style="margin:.2rem 0">no saved connections yet</p>';
  list.forEach(p=>{
    const el=document.createElement('div');
    el.className='glass-btn';
    el.style.cssText='width:100%;justify-content:flex-start;margin-bottom:6px;padding:.45rem .7rem;cursor:default';
    el.innerHTML='<b>'+esc(p.alias)+'</b>&nbsp;<span class="hint">'+esc(p.user+'@'+p.host+':'+(p.port||22))+
      ' · '+esc(p.auth)+'</span>'+
      '<span style="flex:1"></span>';
    const bUse=document.createElement('button');
    bUse.className='glass-btn-accent';bUse.textContent='Use';bUse.style.padding='.25rem .6rem';
    bUse.onclick=()=>{sftpFillForm(p);sftpConnect();};
    const bDel=document.createElement('button');
    bDel.className='glass-btn-danger';bDel.textContent='🗑';bDel.style.padding='.25rem .55rem';
    bDel.onclick=()=>{if(!confirm('Delete saved connection "'+p.alias+'"?'))return;
      spStoreAll(spLoadAll().filter(x=>x.alias!==p.alias));renderSpList();};
    el.appendChild(bUse);el.appendChild(bDel);
    box.appendChild(el);
  });
}
function sftpFillForm(p){
  document.getElementById('sp_alias').value=p.alias||'';
  document.getElementById('sp_host').value=p.host||'';
  document.getElementById('sp_port').value=p.port||22;
  document.getElementById('sp_user').value=p.user||'';
  document.getElementById('sp_auth').value=p.auth||'password';
  sftpAuthUi();
  const set=(id,v)=>{const el=document.getElementById(id);if(el)el.value=v||'';};
  set('sp_secret',p.secret);set('sp_key',p.key);set('sp_cert',p.cert);set('sp_sshid',p.sshid);
  if(document.getElementById('sp_res'))document.getElementById('sp_res').checked=!!p.resident;
}
async function openSftpDialog(){
  document.getElementById('sftpDialog').showModal();
  document.getElementById('sp_savebar').style.display='none';
  sftpAuthUi();
  renderSpList();
  try{
    const j=await (await fetch('/api/sftp/info')).json();
    if(j.enabled&&!spLoadAll().length&&!document.getElementById('sp_host').value){
      sftpFillForm({alias:'this-server',host:j.hosts[0],port:j.port,user:j.usernames[0]});
    }
  }catch(e){}
}
function copySftpCmds(){
  if(!spCmdText)return;
  navigator.clipboard.writeText(spCmdText).catch(()=>{});
}
/* ---- live remote browsing through the server-side SFTP bridge ---- */
let spSid=null,spHome='/';
async function spBrowse(){
  const p=sftpCollect();
  if(!p)return;
  if(p.auth==='fido2'){
    showStatus('FIDO2 keys only work from your terminal — use password or key here');
    return;
  }
  showStatus('connecting to '+p.host+'…');
  try{
    const r=await fetch('/api/remote/connect',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({host:p.host,port:p.port,user:p.user,
        auth:p.auth==='password'?'password':'key',
        secret:p.secret,key:p.key})});
    const d=await r.json();
    if(d.status!=='success'){showStatus('❌ '+d.message);return;}
    spSid=d.sid;spHome=d.home;
    document.getElementById('sp_browse').style.display='block';
    showStatus('✔ connected to '+d.host);
    spRender(d.path,d.entries);
  }catch(e){showStatus('❌ network error');}
}
function spRender(path,entries){
  document.getElementById('sp_bpath').textContent=path;
  const box=document.getElementById('sp_entries');
  box.innerHTML='';
  if(path&&path!=='/'&&!Object.is(path,spHome)){
    const up=document.createElement('a');
    up.className='glass-btn';up.style.cssText='width:100%;justify-content:flex-start;margin-bottom:4px;padding:.3rem .6rem';
    up.textContent='⬆ ..';
    up.onclick=()=>spNav(path.replace(/\\/g,'/').replace(/\/[^\/]*\/?$/,'')||'/');
    box.appendChild(up);
  }
  entries.forEach(e=>{
    const row=document.createElement(e.isdir?'div':'a');
    row.className='glass-btn';
    row.style.cssText='width:100%;justify-content:flex-start;margin-bottom:4px;padding:.35rem .7rem;font-weight:400';
    if(e.isdir){
      row.textContent='📁 '+e.name;
      row.onclick=()=>spNav((path==='/'?'':path)+'/'+e.name);
    }else{
      row.href='/api/remote/download?sid='+encodeURIComponent(spSid)+
               '&path='+encodeURIComponent((path==='/'?'':path)+'/'+e.name);
      row.setAttribute('download',e.name);
      row.textContent='📄 '+e.name+'  ('+(e.size>=1048576?(e.size/1048576).toFixed(1)+' MB':(e.size/1024).toFixed(1)+' KB')+')';
    }
    box.appendChild(row);
  });
}
async function spNav(path){
  try{
    const r=await fetch('/api/remote/list',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({sid:spSid,path:path})});
    const d=await r.json();
    if(d.status!=='success'){showStatus('❌ '+d.message);return;}
    spRender(d.path,d.entries);
  }catch(e){showStatus('❌ network error');}
}
function spCloseSession(){
  if(spSid)fetch('/api/remote/close',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({sid:spSid})}).catch(()=>{});
  spSid=null;
  document.getElementById('sp_browse').style.display='none';
  showStatus('disconnected');
}
/* tunnel chip */
fetch('/api/tunnel').then(r=>r.json()).then(d=>{
  if(d.active){
    const chip=document.getElementById('tunnelChip');
    chip.href=d.url;chip.style.display='';
    chip.innerHTML='🌍 Public link <span class="hint">('+d.provider+')</span>';
  }
}).catch(()=>{});

/* ========================= navigation ========================== */
function navigateToPath(p){ window.location.href=p; }
function sortFiles(by){
  const u=new URL(window.location); const cur=u.searchParams.get('sort');
  const ord=(cur===by && u.searchParams.get('order')==='asc')?'desc':'asc';
  u.searchParams.set('sort',by); u.searchParams.set('order',ord);
  window.location.href=u.toString();
}
function setupRealTimeSearch(){
  const inp=document.getElementById('searchInput');
  const dd=document.getElementById('searchDrop');
  inp.addEventListener('input',()=>{
    clearTimeout(searchTimeout);
    const q=inp.value.trim();
    searchTimeout=setTimeout(async()=>{
      if(!q){dd.style.display='none';
        document.querySelectorAll('#fileTableBody tr').forEach(r=>r.style.display='');
        return;}
      // filter the current directory instantly too
      document.querySelectorAll('#fileTableBody tr').forEach(r=>{
        const n=r.dataset.name||'';
        r.style.display = n.includes(q.toLowerCase()) ? '' : 'none';});
      // and search the whole share
      try{
        const res=await fetch('/api/search?q='+encodeURIComponent(q));
        const d=await res.json();
        if(!d.results||!d.results.length){dd.style.display='none';return;}
        dd.innerHTML=d.results.slice(0,30).map(r=>
          `<div class="search-hit" onclick="navigateToPath('${escJs(r.path)}')">`+
          `<span>📄 ${escHtml(r.name)}</span>`+
          `<span class="search-sub">${r.path}</span>`+
          (r.snippet?`<span class="search-snip">${escHtml(r.snippet)}</span>`:'')+
          `</div>`).join('');
        dd.style.display='block';
      }catch(e){dd.style.display='none';}
    },180);
  });
  inp.addEventListener('keydown',e=>{if(e.key==='Escape')clearSearch();});
  document.addEventListener('click',e=>{
    if(!document.getElementById('searchControls').contains(e.target))dd.style.display='none';});
}
function clearSearch(){ document.getElementById('searchInput').value='';
  document.getElementById('searchDrop').style.display='none';
  document.querySelectorAll('#fileTableBody tr').forEach(r=>r.style.display=''); }

/* ========================== live updates ========================== */
let liveReloadTimer=null, liveStatsEl=null;
function scheduleLiveReload(){
  if(liveReloadTimer)return;
  liveReloadTimer=setTimeout(()=>{liveReloadTimer=null;location.reload();},700);
}
function startLiveRefresh(){
  if(!window.EventSource){document.getElementById('liveBadge').textContent='offline only';return;}
  const es=new EventSource('/api/events');
  es.addEventListener('file',ev=>{
    const d=JSON.parse(ev.data);
    const here=(d.path||'').startsWith(currentPath);
    const hereDir=here && (d.path!==currentPath);
    scheduleLiveReload();
  });
  es.addEventListener('stats',ev=>{
    if(liveStatsEl){
      try{const d=JSON.parse(ev.data);}catch(e){}
    }
  });
}

function trashFile(path){
  if(!confirm('Move "'+path+'" to trash?'))return;
  fetch('/api/trash/move',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({path})})
   .then(r=>r.json()).then(d=>{showStatus(d.message||d.status);
     if(d.status==='success')scheduleLiveReload();});
}
function versionsDialog(path){
  const url='/api/versions/list?path='+encodeURIComponent(path);
  fetch(url).then(r=>r.json()).then(d=>{
    if(!d.versions||!d.versions.length){alert('No saved versions for this file.');return;}
    const names=d.versions.map(v=>v.version+'  ('+v.size+', '+v.at+')').join('\n');
    const pick=prompt('Saved versions of '+path+'\nPick the version ID to restore:',d.versions[0].version);
    if(!pick)return;
    fetch('/api/versions/restore',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path,version:pick})})
     .then(r=>r.json()).then(x=>{alert(x.status==='success'?'Restored ✔':('❌ '+x.message));
       if(x.status==='success')scheduleLiveReload();});
  });
}
function escHtml(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML;}
function escJs(s){return (s??'').replace(/\\/g,'/').replace(/'/g,'%27');}

/* ==================== basic file operations ===================== */
function downloadFile(path,name){ const a=document.createElement('a');a.href=path;a.download=name;a.click(); }
function downloadFolder(path){ window.location.href=path+'download_folder'; }
function previewFile(path){ window.open(path+'/preview','_blank'); }
function editFile(path){ window.open(path+'/edit','_blank'); }
function showStatus(msg,type){
  console.log(type+': '+msg);
}
function createNewFolder(){
  const n=prompt('📁 New folder name:'); if(!n) return;
  fetch(window.location.pathname+n,{method:'MKCOL'})
   .then(r=>r.json()).then(d=>{alert(d.message);if(d.status==='success')location.reload();});
}
function createNewFile(){ window.open(window.location.pathname+'notepad','_blank'); }

/* ======================= speed limiting ======================== */
async function setSpeed(v){
  await fetch('/api/config/speed',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:v})});
}

/* =================== ephemeral (vanishing) links ================= */
let ephTarget=null;
function makeEphemeral(path,name){
  ephTarget={path,name};
  document.getElementById('ephFile').textContent=name;
  document.getElementById('ephResult').style.display='none';
  document.getElementById('ephDialog').showModal();
}
async function createEphemeralLink(){
  const body={path:currentPath+ephTarget.path,
              ttl_seconds:+document.getElementById('ephTtl').value,
              max_downloads:+document.getElementById('ephMax').value};
  const r=await fetch('/api/ephemeral/create',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.status==='success'){
    document.getElementById('ephUrl').value=d.url;
    document.getElementById('ephResult').style.display='block';
    document.getElementById('ephGo').style.display='none';
  } else alert(d.message);
}
function copyEphemeral(){
  const i=document.getElementById('ephUrl'); i.select();
  navigator.clipboard.writeText(i.value).catch(()=>document.execCommand('copy'));
}

/* ===================== chunked upload engine ==================== */
function fnv1a(s){let h=0x811c9dc5;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);
  h=Math.imul(h,0x01000193)>>>0;}return ('0000000'+h.toString(16)).slice(-8);}
async function fileIdOf(file){
  const key=file.name+':'+file.size+':'+file.lastModified;
  if(crypto && crypto.subtle && window.isSecureContext){
    try{
      const buf=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(key));
      return [...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('');
    }catch(e){}
  }
  return fnv1a(key)+'-'+fnv1a(key.split('').reverse().join(''))+file.size.toString(36);
}
function setProgress(pct,text){
  const box=document.getElementById('uploadProgress');
  box.style.display='block';
  document.getElementById('progressBar').style.width=pct.toFixed(1)+'%';
  document.getElementById('progressText').textContent=text;
}
function hideProgress(){ setTimeout(()=>{document.getElementById('uploadProgress').style.display='none';},1200); }

async function apiJSON(url,method,payload){
  const opt={method,headers:{'Content-Type':'application/json'}};
  if(payload!==undefined) opt.body=JSON.stringify(payload);
  const r=await fetch(url,opt);
  return r.json();
}

async function uploadFileChunked(file,dir,onPct){
  const uid=await fileIdOf(file);
  let st=await apiJSON('/api/upload/init','POST',
      {upload_id:uid,filename:file.name,size:file.size,chunk_size:CHUNK_SIZE,dir});
  if(st.status!=='success') throw new Error(st.error||'init failed');
  const total=st.total;
  const missing=st.missing&&st.missing.length?st.missing:
      [...Array(total).keys()];
  for(const idx of missing){
    const start=idx*CHUNK_SIZE;
    const blob=file.slice(start,Math.min(start+CHUNK_SIZE,file.size));
    let ok=false;
    for(let attempt=0;attempt<4&&!ok;attempt++){
      try{
        const r=await fetch('/api/upload/chunk?upload_id='+encodeURIComponent(uid)+
                            '&index='+idx,{method:'POST',body:blob});
        const j=await r.json();
        ok=!j.error;
      }catch(e){ await new Promise(r=>setTimeout(r,800*(attempt+1))); }
    }
    if(!ok) throw new Error('chunk '+idx+' failed (resume later)');
    onPct((idx+1)/total*100,file.name);
  }
  const fin=await apiJSON('/api/upload/complete?upload_id='+encodeURIComponent(uid),'POST',{});
  if(fin.status!=='success') throw new Error(fin.error||'complete failed');
}

async function uploadPlain(filesWithRel,endpoint){
  const fd=new FormData();
  filesWithRel.forEach(({file,rel})=>{
    fd.append('file',file,file.name);
    fd.append('relpath',rel||'');
  });
  const r=await fetch(endpoint,{method:'POST',body:fd});
  return r.json();
}

async function processUploadQueue(items){
  // items: [{file, rel}]
  const big=items.filter(i=>i.file.size>CHUNK_THRESHOLD);
  const small=items.filter(i=>i.file.size<=CHUNK_THRESHOLD);
  try{
    if(big.length){
      for(let k=0;k<big.length;k++){
        await uploadFileChunked(big[k].file,big[k].relDir(),(pct,name)=>
          setProgress(((k+pct/100)/big.length)*100,`chunking ${name} ${pct.toFixed(1)}%`));
      }
    }
    if(small.length){
      // group by target dir so each request lands correctly
      const groups={};
      small.forEach(i=>{(groups[i.relBase()] ||= []).push(i);});
      let gi=0,gtotal=Object.keys(groups).length;
      for(const [dir,list] of Object.entries(groups)){
        setProgress(gi/gtotal*100,'uploading '+list.length+' file(s)…');
        await uploadPlain(list.map(i=>({file:i.file,rel:i.rel})),
                          '/api/upload/folder?dir='+encodeURIComponent(dir));
        gi++;
      }
    }
    setProgress(100,'✅ done — reloading…'); hideProgress();
    setTimeout(()=>location.reload(),900);
  }catch(e){
    setProgress(0,'❌ '+e.message+' (retry resumes automatically)');
  }
}

// helper accessors attached to items
function itemHelpers(item){
  item.relDir=function(){ const i=this.rel.lastIndexOf('/');
    return i===-1?'':this.rel.slice(0,i); };
  item.relBase=item.relDir;
  return item;
}

function setupUploadHandling(){
  const form=document.getElementById('uploadForm');
  form.addEventListener('submit',e=>{
    e.preventDefault();
    const files=[...document.getElementById('fileUpload').files];
    if(!files.length){alert('Select files first');return;}
    const items=files.map(f=>itemHelpers({file:f,rel:f.webkitRelativePath||f.name}));
    processUploadQueue(items);
  });

  const zone=document.getElementById('dropZone');
  const overlay=document.getElementById('dropOverlay');
  ['dragenter','dragover','dragleave','drop'].forEach(ev=>
    zone.addEventListener(ev,e=>{e.preventDefault();e.stopPropagation();}));
  ['dragenter','dragover'].forEach(ev=>zone.addEventListener(ev,()=>overlay.style.display='flex'));
  ['dragleave','drop'].forEach(ev=>zone.addEventListener(ev,()=>overlay.style.display='none'));

  zone.addEventListener('drop',async e=>{
    const entries=[...(e.dataTransfer.items||[])]
       .map(i=>i.webkitGetAsEntry&&i.webkitGetAsEntry()).filter(Boolean);
    let items=[];
    if(entries.length){
      overlay.style.display='flex';
      items=await collectEntries(entries);
      overlay.style.display='none';
    }else{
      items=[...(e.dataTransfer.files||[])].map(f=>itemHelpers(
          {file:f,rel:f.webkitRelativePath||f.name}));
    }
    if(!items.length) return;
    processUploadQueue(items.map(itemHelpers));
  });
}

/* recursive folder traversal preserving relative paths */
async function collectEntries(topEntries){
  const out=[];
  async function walk(entry,prefix){
    if(!entry) return;
    if(entry.isFile){
      await new Promise(res=>entry.file(f=>{
        out.push({file:f,rel:(prefix+f.name)});res();},()=>res()));
    }else if(entry.isDirectory){
      const reader=entry.createReader();
      let batch;
      do{
        batch=await new Promise(res=>reader.readEntries(res,()=>res([])));
        for(const child of batch) await walk(child,prefix+entry.name+'/');
      }while(batch.length);
    }
  }
  for(const t of topEntries) await walk(t,'');
  return out;
}

/* ======================= live text clipboard ========================= */
let clipMtime=0,clipLocal=false;
function clipStatus(msg){
  const s=document.getElementById('clipboardStatus');
  s.textContent=msg; setTimeout(()=>s.textContent='',2500);
}
function clipPath(){return window.location.pathname;}
function applyClip(content,mtime){
  const ta=document.getElementById('textClipboard');
  if(document.activeElement===ta)return;          /* never clobber typing */
  if(ta.value!==content){ta.value=content;}
  clipMtime=mtime||0;
}
function loadTextClipboard(){
  fetch(clipPath()+'load_clipboard?path='+encodeURIComponent(clipPath()))
   .then(r=>r.json())
   .then(d=>{ if(d.status==='success')applyClip(d.content,d.mtime); })
   .catch(()=>{});
}
/* poll for remote edits so the panel is LIVE on every device */
setInterval(()=>{
  fetch(clipPath()+'load_clipboard?path='+encodeURIComponent(clipPath()))
   .then(r=>r.json()).then(d=>{
      if(d.status!=='success')return;
      if((d.mtime||0)!==clipMtime){
        applyClip(d.content,d.mtime);
        clipStatus('● synced '+new Date().toLocaleTimeString());
        const dot=document.getElementById('clipLive');if(dot)dot.style.color='var(--success)';
      }
   }).catch(()=>{});
},900);
function saveTextClipboard(){
  const c=document.getElementById('textClipboard').value;
  return fetch(clipPath()+'save_clipboard',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:c,path:clipPath()})})
    .then(r=>r.json())
}
function clearTextClipboard(){
  document.getElementById('textClipboard').value='';
  saveTextClipboard().then(()=>{clipMtime=Date.now()/1000;clipStatus('cleared');});
}
function copyToClipboard(){
  const ta=document.getElementById('textClipboard'); ta.select();
  navigator.clipboard.writeText(ta.value).then(()=>clipStatus('📋 copied'))
   .catch(()=>{try{document.execCommand('copy');clipStatus('📋 copied');}catch(e){}});
}
let clipTimer;
document.addEventListener('DOMContentLoaded',()=>{
  const ta=document.getElementById('textClipboard');
  ta.addEventListener('input',()=>{clearTimeout(clipTimer);
    clipTimer=setTimeout(()=>saveTextClipboard().then(d=>{
        clipStatus(d.status==='success'?'● live':'❌ '+d.message);
      }).catch(()=>clipStatus('⚠ offline')),350);});
  loadTextClipboard();
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# login page
# ---------------------------------------------------------------------------
_LOGIN_TMPL = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PyServeX — Login</title>
<style>
__CSS__
 .wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
 .card{padding:38px 34px;width:min(92vw,400px)}
 h1{text-align:center;margin:0 0 6px;font-size:1.9rem;font-weight:700;letter-spacing:-.02em}
 .sub{text-align:center;color:var(--text-secondary);margin:0 0 22px;font-size:.95rem}
 label{display:block;margin-top:12px;font-size:.9rem;color:var(--text-secondary)}
 input{width:100%;font-size:1.05rem;margin-top:4px}
 button{width:100%;margin-top:22px;font-size:1.05rem;padding:.65rem}
 #msg{min-height:1.2em;text-align:center;color:var(--danger);margin-top:10px}
 .note{color:var(--text-secondary);font-size:.85rem;text-align:center;margin-top:14px}
</style></head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>
<div class="wrap"><div class="glass-panel card" id="lgHero">
 <h1>PyServeX</h1>
 <p class="sub">🔒 remote access requires authentication<br>(local network connects freely)</p>
 <form onsubmit="return doLogin(event)">
  <label>Username<input id="u" class="glass-input" autocomplete="username" required></label>
  <label>Password<input id="p" type="password" class="glass-input" autocomplete="current-password" required></label>
  <button class="glass-btn-accent" type="submit">Login</button>
  <div id="msg"></div>
 </form>
 <p class="note">or call the API with:<br><code>Authorization: Bearer &lt;token&gt;</code></p>
</div></div>
__EXTRA_SCRIPTS__
<script>
async function doLogin(ev){
 ev.preventDefault();
 const msg=document.getElementById('msg');
 msg.textContent='…';
 try{
  const r=await fetch('/api/auth/login',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({username:u.value,password:p.value})});
  const d=await r.json();
  if(d.status==='success'){ location.href='/'; return false; }
  msg.textContent=d.message||'login failed';
 }catch(e){ msg.textContent='network error'; }
 return false;
}
window.addEventListener('DOMContentLoaded',function(){ if(window.initTheme) window.initTheme(); });
</script></body></html>
"""


def login_page():
    return _glass(_LOGIN_TMPL)


# ---------------------------------------------------------------------------
# tokens management page
# ---------------------------------------------------------------------------
_TOKENS_TMPL = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PyServeX — API Tokens</title>
<style>
__CSS__
 .wrap{max-width:900px;margin:30px auto;padding:0 14px}
 .card{padding:20px;margin-bottom:18px}
 table{margin-top:10px}
 td,th{padding:6px 10px}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
 .row label{display:flex;flex-direction:column;font-size:.9rem;color:var(--text-secondary)}
 a.back{color:var(--text-primary)}
 h1{font-size:1.6rem;font-weight:700;letter-spacing:-.02em;display:flex;align-items:center;gap:12px}
</style></head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>
<div class="wrap">
 <h1>🔑 API Token Manager <a class="glass-btn back" href="/">←</a></h1>
 <div class="glass-panel card doc-card">
  <h3>📖 How to use API tokens</h3>
  <ol class="doc-steps">
   <li><b>Create</b> a token below — pick a name, optional max-uses and expiry.</li>
   <li><b>Copy</b> the generated token (shown right after you press Generate).</li>
   <li><b>Call any API route</b> from remote machines with the header
       <code>Authorization: Bearer &lt;token&gt;</code>.</li>
   <li><b>Revoke</b> it anytime — it stops working instantly everywhere.</li>
  </ol>
  <pre class="doc-code"># check server stats remotely
curl -H "Authorization: Bearer YOUR_TOKEN" http://YOUR_HOST:8088/api/stats

# download a file without a browser
curl -H "Authorization: Bearer YOUR_TOKEN" -O http://YOUR_HOST:8088/report.pdf

# list a folder as JSON
curl -H "Authorization: Bearer YOUR_TOKEN" http://YOUR_HOST:8088/api/list?path=/</pre>
  <ul class="doc-notes">
   <li>Browsers on the local network never need tokens — they connect freely;
       only remote/internet clients need them (or a login session).</li>
   <li><b>Max uses</b> = how many requests the token accepts (0 = unlimited).</li>
   <li><b>Expires</b> = lifetime in hours (0 = never expires).</li>
   <li>Tokens live server-side in <code>~/.pyservx_tokens.db</code>.</li>
  </ul>
 </div>
 <div class="glass-panel card">
  <h3>Create token</h3>
  <div class="row">
   <label>Name<input id="tname" class="glass-input" value="cli-token"></label>
   <label>Max uses (0=∞)<input id="tuses" type="number" class="glass-input" value="0" min="0"></label>
   <label>Expires (hours, 0=never)<input id="texp" type="number" class="glass-input" value="0" min="0"></label>
   <button class="glass-btn-accent" onclick="createToken()">＋ Generate</button>
  </div>
  <p id="newToken" class="mono" style="display:none;margin-top:10px"></p>
 </div>
 <div class="glass-panel card">
  <h3>Active tokens</h3>
  <table id="tbl"><thead><tr><th>Name</th><th>Token</th><th>Uses</th><th>Expires</th><th></th></tr></thead>
  <tbody id="rows"></tbody></table>
  <p class="note" style="opacity:.7">Use with curl:
  <code>curl -H "Authorization: Bearer TOKEN" http://host:8088/api/stats</code></p>
 </div>
</div>
<script>
async function refresh(){
  const d=await (await fetch('/api/tokens')).json();
  const tb=document.getElementById('rows'); tb.innerHTML='';
  (d.tokens||[]).filter(t=>t.active).forEach(t=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${esc(t.name)}</td><td class="mono">${esc(t.token)}</td>
      <td>${t.uses}${t.max_uses!=null?'/'+t.max_uses:''}</td>
      <td>${t.expires_at?new Date(t.expires_at*1000).toLocaleString():'never'}</td>
      <td><button class="glass-btn-danger" onclick="revoke('${esc(t.full_token||t.token)}')">Revoke</button></td>`;
    tb.appendChild(tr);
  });
}
function esc(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML;}
async function createToken(){
  const body={name:tname.value,
              max_uses:+tuses.value>0?+tuses.value:null,
              expires_hours:+texp.value>0?+texp.value:null};
  const d=await (await fetch('/api/tokens',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  const el=document.getElementById('newToken');
  if(d.token){el.style.display='block';el.textContent=d.token;refresh();}
}
async function revoke(tok){
  if(!confirm('Revoke this token?'))return;
  await fetch('/api/tokens',{method:'DELETE',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({token:tok})});
  refresh();
}
refresh();
window.addEventListener('DOMContentLoaded',function(){ if(window.initTheme) window.initTheme(); });
</script>
__EXTRA_SCRIPTS__
</body></html>
"""


def tokens_page():
    return _glass(_TOKENS_TMPL)


# ---------------------------------------------------------------------------
# P2P WebRTC transfer page
# ---------------------------------------------------------------------------
_P2P_TMPL = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport"content="width=device-width,initial-scale=1">
<title>PyServeX — P2P Transfer</title>
<style>
__CSS__
 .wrap{max-width:860px;margin:26px auto;padding:0 14px;position:relative;z-index:1}
 .card{padding:20px;margin-bottom:16px}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 input{font-size:1.05rem}
 pre{padding:12px;border-radius:var(--radius-btn);max-height:220px;overflow:auto;
   font-size:.85rem;color:var(--text-secondary);
   background:rgba(120,120,128,.08);border:1px solid var(--glass-border)}
 .hint{color:var(--text-secondary);font-size:.9rem}
 progress{width:100%;height:14px;border-radius:7px;overflow:hidden}
 h1{font-size:1.6rem;font-weight:700;letter-spacing:-.02em;display:flex;align-items:center;gap:12px}
</style></head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>
<div class="wrap">
<h1>📡 Direct P2P Transfer <a class="glass-btn" href="/">←</a></h1>
<p class="hint">Bypasses firewalled hosts: bytes travel peer-to-peer (WebRTC data channel),
only tiny signalling messages relay through this server. STUN: Google public.</p>

<div class="glass-panel card doc-card">
 <h3>📖 How to transfer — 4 steps</h3>
 <div class="doc-cols">
  <div>
   <h4>📤 Sender</h4>
   <ol class="doc-steps">
    <li>Pick a file with <b>Choose file</b>.</li>
    <li>Leave the room code blank and press <b>Send ➤</b> — a code is generated.</li>
    <li>Share the code (and this page's URL) with the receiver.</li>
    <li>Keep the tab open until the log says <b>sent ✔</b>.</li>
   </ol>
  </div>
  <div>
   <h4>📥 Receiver</h4>
   <ol class="doc-steps">
    <li>Open the same <b>/p2p</b> URL on your device.</li>
    <li>Type the room code into <b>Receive</b> and press <b>Receive ⬇</b>.</li>
    <li>The file saves automatically when the transfer finishes.</li>
   </ol>
  </div>
 </div>
 <ul class="doc-notes">
  <li><b>Private by design:</b> file bytes go directly device-to-device over an
      encrypted WebRTC channel — nothing is stored on or passes through the server.</li>
  <li><b>Where it works:</b> same Wi-Fi/LAN always; across the internet whenever
      both networks allow UDP hole-punching (Google STUN assists discovery).</li>
  <li>Reusing a room code lets you resume pairing; close the tab to end the session.</li>
 </ul>
</div>

<div class="glass-panel card">
 <h3>Send a file</h3>
 <div class="row">
  <input type="file" id="filePick" class="glass-input">
  <input id="roomA" class="glass-input" placeholder="room code (blank=new)" style="width:170px">
  <button class="glass-btn-accent" onclick="startSend()">Send ➤</button>
 </div>
 <progress id="pbSend" value="0" max="100" style="display:none;margin-top:10px"></progress>
 <pre id="logA" style="margin-top:10px"></pre>
</div>

<div class="glass-panel card">
 <h3>Receive a file</h3>
 <div class="row">
  <input id="roomB" class="glass-input" placeholder="room code from sender" style="width:190px">
  <button class="glass-btn-accent" onclick="startRecv()">Receive ⬇</button>
 </div>
 <progress id="pbRecv" value="0" max="100" style="display:none;margin-top:10px"></progress>
 <div id="dlArea" style="margin-top:10px"></div>
 <pre id="logB" style="margin-top:10px"></pre>
</div>
</div>
<script>
const RTC_CFG={iceServers:[{urls:['stun:stun.l.google.com:19302','stun:stun1.l.google.com:19302']}]};
let peerId=Math.random().toString(36).slice(2,9);
let sinceA=0,sinceB=0;

function log(el,msg){const p=document.getElementById(el);
 p.textContent=msg+'\n'+p.textContent;}
function esc(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML;}

/* ---------- signalling helpers ---------- */
async function signal(room,type,data){
  await fetch('/webrtc/signal',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({room,from:peerId,type,data})});
}
async function poll(room,since,exclude){
  const r=await fetch(`/webrtc/poll?room=${encodeURIComponent(room)}&since=${since}&peer=${exclude}`);
  const d=await r.json();
  return d;
}

/* ---------- SENDER ---------- */
let sendPC=null,sendChan=null;
async function startSend(){
  const room=(document.getElementById('roomA').value||
              Math.random().toString(36).slice(2,8)).toLowerCase();
  document.getElementById('roomA').value=room;
  log('logA','room='+room+' waiting for receiver…');
  await signal(room,'join',{role:'sender'});
  sendPC=new RTCPeerConnection(RTC_CFG);
  sendChan=sendPC.createDataChannel('file');
  wireChannel(sendChan,room);
  sendPC.onicecandidate=e=>{if(e.candidate)signal(room,'candidate',e.candidate.toJSON());};
  const offer=await sendPC.createOffer();
  await sendPC.setLocalDescription(offer);
  await signal(room,'offer',{sdp:offer.sdp,type:offer.type});
  pumpSenderSignals(room);
}

async function pumpSenderSignals(room){
  while(true){
    const d=await poll(room,sinceA,peerId);
    for(const m of d.messages){
      sinceA=m.seq;
      if(m.type==='answer'&&sendPC){
        await sendPC.setRemoteDescription({type:m.data.type,sdp:m.data.sdp});
        log('logA','receiver answered ✔');
      }else if(m.type==='candidate'&&sendPC&&m.data){
        try{await sendPC.addIceCandidate(m.data);}catch(e){}
      }
    }
    if(sendChan&&sendChan.readyState==='open')break;
    await new Promise(r=>setTimeout(r,700));
  }
}

function wireChannel(chan,room){
  chan.bufferedThreshold=1<<20;
  chan.onopen=async()=>{
    log('logA','data channel OPEN');
    const f=document.getElementById('filePick').files[0];
    if(!f){chan.close();return;}
    chan.send(JSON.stringify({meta:true,name:f.name,size:f.size}));
    const CH=16384;
    let off=0;
    const pb=document.getElementById('pbSend');pb.style.display='block';
    while(off<f.size){
      if(chan.bufferedAmount>chan.bufferedThreshold){
        await new Promise(r=>setTimeout(r,30));continue;
      }
      const slice=f.slice(off,off+CH);
      const buf=await slice.arrayBuffer();
      chan.send(buf);
      off+=buf.byteLength;
      pb.value=off/f.size*100;
    }
    chan.send(JSON.stringify({eof:true}));
    log('logA','sent '+f.name+' ✔');
    fetch('/api/stats/ping',{method:'POST'}).catch(()=>{});
  };
  chan.onerror=e=>log('logA','channel error');
}

/* ---------- RECEIVER ---------- */
let recvPC=null,recvChan=null,recvBuf=[],recvMeta=null,recvBytes=0;
async function startRecv(){
  const room=document.getElementById('roomB').value.trim().toLowerCase();
  if(!room)return alert('enter room code');
  await signal(room,'join',{role:'receiver'});
  recvPC=new RTCPeerConnection(RTC_CFG);
  recvPC.ondatachannel=e=>{
    recvChan=e.channel;
    recvChan.binaryType='arraybuffer';
    recvChan.onmessage=ev=>{
      if(typeof ev.data==='string'){
        const j=JSON.parse(ev.data);
        if(j.meta){recvMeta=j;recvBuf=[];recvBytes=0;
          const pb=document.getElementById('pbRecv');pb.style.display='block';
          log('logB','incoming: '+j.meta.name);}
        if(j.eof){finishRecv();}
      }else{
        recvBuf.push(ev.data);recvBytes+=ev.data.byteLength;
        if(recvMeta)document.getElementById('pbRecv').value=recvBytes/recvMeta.size*100;
      }
    };
    recvChan.onopen=()=>log('logB','data channel OPEN ✔');
  };
  recvPC.onicecandidate=e=>{if(e.candidate)signal(room,'candidate',e.candidate.toJSON());};
  pumpReceiverSignals(room);
}

async function pumpReceiverSignals(room){
  while(true){
    const d=await poll(room,sinceB,peerId);
    for(const m of d.messages){
      sinceB=m.seq;
      if(m.type==='offer'&&recvPC){
        await recvPC.setRemoteDescription({type:m.data.type,sdp:m.data.sdp});
        const ans=await recvPC.createAnswer();
        await recvPC.setLocalDescription(ans);
        await signal(room,'answer',{sdp:ans.sdp,type:ans.type});
        log('logB','answered sender');
      }else if(m.type==='candidate'&&recvPC&&m.data){
        try{await recvPC.addIceCandidate(m.data);}catch(e){}
      }
    }
    await new Promise(r=>setTimeout(r,700));
  }
}

function finishRecv(){
  const blob=new Blob(recvBuf);
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=(recvMeta&&recvMeta.name)||'p2p-file.bin';
  a.click();
  log('logB','saved '+a.download+' ('+blob.size+' bytes) ✔');
}
window.addEventListener('DOMContentLoaded',function(){ if(window.initTheme) window.initTheme(); });
</script>
__EXTRA_SCRIPTS__
</body></html>
"""


def p2p_page():
    return _glass(_P2P_TMPL)


# ---------------------------------------------------------------------------
# editor / notepad page
# ---------------------------------------------------------------------------
_EDITOR_TMPL = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
__CSS__
 body{padding:16px}
 .bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:10px;flex-wrap:wrap}
 .editor-card{padding:16px;position:relative;z-index:1}
 #editor{width:100%;min-height:70vh;font-family:ui-monospace,'Cascadia Code','Courier New',monospace;
   font-size:14px;line-height:1.55;border:none;border-radius:var(--radius-btn);resize:vertical;
   background:transparent;color:var(--text-primary);outline:none;padding:12px;
   caret-color:var(--accent)}
 .editor-card:focus-within{box-shadow:var(--glass-shadow-hover),0 0 0 1.5px rgba(10,132,255,.45)}
 #status{min-height:1.4em;text-align:center;margin-top:10px;color:var(--text-secondary)}
 h2{margin:0;font-size:1.25rem;font-weight:600;letter-spacing:-.01em}
</style></head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>
<div class="bar">
 <h2 id="lgHero">__TITLE__</h2>
 <div style="display:flex;gap:8px">
  <button class="glass-btn-accent" onclick="saveFile()">💾 Save (Ctrl+S)</button>
  <button class="glass-btn" onclick="window.close()">Close</button>
 </div>
</div>
<div class="glass-panel editor-card">
__FILENAME_BLOCK__
<textarea id="editor" class="glass-input" placeholder="Start typing…">__CONTENT__</textarea>
</div>
<div id="status"></div>
<script>
const SAVE_URL='__SAVE_URL__';
const HAS_NAME=__HAS_NAME__;
async function saveFile(){
 const content=document.getElementById('editor').value;
 let payload;
 if(HAS_NAME){payload={filename:document.getElementById('filename').value,content};}
 else payload={content};
 const s=document.getElementById('status');
 try{
  const r=await fetch(SAVE_URL,{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json();
  s.textContent=(d.status==='success'?'✅ ':'❌ ')+d.message;
  setTimeout(()=>s.textContent='',3000);
 }catch(e){s.textContent='❌ network error';}
}
document.addEventListener('keydown',e=>{
 if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();saveFile();}});
window.addEventListener('DOMContentLoaded',function(){ if(window.initTheme) window.initTheme(); });
</script>
__EXTRA_SCRIPTS__
</body></html>
"""


def editor_page(title, content, save_url, include_filename=False):
    fname_block = ("<div><label>Filename:"
                   "<input id='filename' class='glass-input' placeholder='myfile.txt'></label></div>"
                   if include_filename else "")
    tmpl = (_EDITOR_TMPL
            .replace('__TITLE__', html.escape(title))
            .replace('__FILENAME_BLOCK__', fname_block)
            .replace('__HAS_NAME__', 'true' if include_filename else 'false')
            .replace('__SAVE_URL__', save_url))
    # content goes last: escape it for safe embedding
    return _glass(tmpl).replace('__CONTENT__', html.escape(content))


# ---------------------------------------------------------------------------
# Trash / version history page
# ---------------------------------------------------------------------------
_TRASH_TMPL = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark"><head><meta charset="UTF-8">
<meta name="viewport"content="width=device-width,initial-scale=1">
<title>PyServeX — Trash</title>
<style>
__CSS__
 .wrap{max-width:900px;margin:26px auto;padding:0 14px;position:relative;z-index:1}
 .card{padding:20px;margin-bottom:16px}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}
 .hint{color:var(--text-secondary);font-size:.9rem}
 table{width:100%;border-collapse:collapse}
 th,td{padding:.5rem .6rem;text-align:left;border-bottom:1px solid var(--glass-border)}
 tr:hover{background:rgba(255,255,255,.03)}
 .mono{font-family:ui-monospace,Consolas,monospace;font-size:.85rem}
 .badge{display:inline-block;font-size:.7rem;padding:.1rem .5rem;border-radius:999px;
   color:var(--warning);border:1px solid var(--glass-border)}
</style></head>
<body>
__BODY_OPEN__
<button id="themeToggle" class="glass-btn theme-toggle-btn"><span id="themeIcon">🌙</span></button>
<div class="wrap">
<h1>🗑️ Trash <a class="glass-btn" href="/">←</a>
 <button class="glass-btn-danger" style="margin-left:10px" onclick="emptyTrash()">Empty trash</button>
 <span id="liveBadge" class="badge" style="color:var(--accent-2)">LIVE</span></h1>
<p class="hint">Deleted items stay here for 30 days, then purge automatically.
Restored files go back to their original folder as-is.</p>
<div class="glass-panel card">
 <table>
  <thead><tr><th>Name</th><th>Original path</th><th>Size</th>
   <th>Trashed</th><th style="text-align:right">Restore</th></tr></thead>
  <tbody id="rows"><tr><td colspan="5" class="hint">…</td></tr></tbody>
 </table>
</div>
</div>
<script>
function esc(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML;}
async function api(path,method,body){
  const r=await fetch(path,{method:method||'GET',
    headers:body?{'Content-Type':'application/json'}:undefined,
    body:body?JSON.stringify(body):undefined});
  return r.json();
}
async function load(){
  const d=await api('/api/trash/list');
  const tb=document.getElementById('rows');
  if(d.status!=='success'||!d.entries.length){
    tb.innerHTML='<tr><td colspan="5" class="hint">trash is empty ✨</td></tr>';return;
  }
  tb.innerHTML=d.entries.map(e=>
    `<tr><td>📄 ${esc(e.name)}</td>
        <td class="mono">${esc(e.path)}</td>
        <td>${esc(e.size)}</td>
        <td>${esc(e.trashed_at)}</td>
        <td style="text-align:right">${e.restorable
          ? `<button class="glass-btn" onclick="restore('${esc(e.path)}')">↩️</button>`
          : '<span class="hint">missing</span>'}</td></tr>`).join('');
}
async function restore(p){
  const d=await api('/api/trash/restore','POST',{path:p});
  alert(d.status==='success'?('Restored '+d.path):('❌ '+d.message));
  load();
}
async function emptyTrash(){
  if(!confirm('Permanently delete every item in the trash?'))return;
  await api('/api/trash/empty','POST',{});
  load();
}
load();
if(window.EventSource){
  const es=new EventSource('/api/events');
  es.addEventListener('trash',res=>load());
  es.addEventListener('file',res=>{const d=JSON.parse(res.data);if(d&&d.action==='trashed')load();});
}
window.addEventListener('DOMContentLoaded',function(){ if(window.initTheme) window.initTheme(); });
</script>
__EXTRA_SCRIPTS__
</body></html>
"""


def trash_page():
    return _glass(_TRASH_TMPL)
