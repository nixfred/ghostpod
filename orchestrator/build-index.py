#!/usr/bin/env python3
"""
Build a self-contained index.html at Docker build time.
Starts ttyd briefly, fetches its built-in HTML (which has CSS/JS inlined),
then injects a mobile toolbar with control key shortcuts and clipboard support.
"""
import subprocess, time, urllib.request

proc = subprocess.Popen(
    ['ttyd', '--port', '19999', 'true'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
time.sleep(2)

try:
    html = urllib.request.urlopen('http://127.0.0.1:19999/').read().decode()
finally:
    proc.terminate()

toolbar_css = (
    ':root{--toolbar-h:44px}'
    '@media(pointer:coarse){:root{--toolbar-h:56px}}'
    '#terminal-container{height:calc(100% - var(--toolbar-h)) !important}'
    '#toolbar{position:fixed;bottom:0;left:0;right:0;z-index:9999;height:var(--toolbar-h);display:flex;'
    'align-items:center;gap:4px;padding:0 6px;background:#181825;border-top:1px solid #313244;box-sizing:border-box}'
    '#toolbar button{background:#313244;color:#cdd6f4;border:none;padding:6px 10px;'
    'border-radius:4px;cursor:pointer;font-size:12px;font-family:monospace;font-weight:600;flex:1;white-space:nowrap}'
    '@media(pointer:coarse){#toolbar button{font-size:14px;border-radius:6px}}'
    '#toolbar button:active{background:#45475a}'
    '#toolbar button.accent,#toolbar button.active{background:#89b4fa;color:#1e1e2e}'
    # Sel button only shown on touch devices
    '#sel-btn{display:none}'
    '@media(pointer:coarse){#sel-btn{display:block}}'
)

toolbar_html = (
    '<div id="toolbar">'
    '<button id="ctrl-btn" onclick="toggleCtrl()">Ctrl</button>'
    '<button onclick="sendKey(\'\\x1b\')">Esc</button>'
    '<button onclick="sendKey(\'\\x09\')">Tab</button>'
    '<button onclick="sendKey(\'\\x1b[A\')">↑</button>'
    '<button onclick="sendKey(\'\\x1b[B\')">↓</button>'
    '<button onclick="sendKey(\'\\x1b[D\')">←</button>'
    '<button onclick="sendKey(\'\\x1b[C\')">→</button>'
    '<button id="sel-btn" onclick="toggleSel()">Sel</button>'
    '<button onclick="sendKey(\'\\x1bc\')" title="Reset terminal state">Rst</button>'
    '</div>'
)

toolbar_js = (
    '<script>'

    # Send raw control sequences to PTY
    'function sendKey(s){'
    'if(window.term){window.term._core.coreService.triggerDataEvent(s);window.term.focus()}'
    '}'

    # Sticky Ctrl modifier — tap Ctrl (turns blue), then tap any key to send Ctrl+key
    'var _ctrlPending=false;'
    'function toggleCtrl(){'
    '_ctrlPending=!_ctrlPending;'
    'document.getElementById("ctrl-btn").classList.toggle("active",_ctrlPending);'
    'if(window.term)window.term.focus()'
    '}'

    # Desktop clipboard: synchronous write via textarea (execCommand).
    # Works on desktop from click/keydown handlers. Does NOT work on iOS.
    'function _clipWrite(s){'
    'var ta=document.createElement("textarea");'
    'ta.value=s;ta.style.cssText="position:fixed;top:0;left:0;opacity:0;pointer-events:none";'
    'document.body.appendChild(ta);ta.focus();ta.select();'
    'document.execCommand("copy");document.body.removeChild(ta)'
    '}'

    # Mobile selection mode — uses term.select(col, row, length) driven by touch
    # events since xterm.js has no native touch selection (open issue since 2022).
    # Converts pixel coordinates to terminal cell coordinates via the render service.
    # navigator.clipboard.writeText() is used on touchend (valid iOS user gesture).
    'var _selMode=false,_selStart=null;'
    'function toggleSel(){'
    '_selMode=!_selMode;'
    'document.getElementById("sel-btn").classList.toggle("active",_selMode);'
    'if(!_selMode&&window.term)window.term.clearSelection();'
    'if(window.term)window.term.focus()'
    '}'

    # Convert a Touch to terminal {col, row}.
    # Cell size is derived from the terminal screen element dimensions divided by
    # cols/rows — this is renderer-agnostic and correct on retina displays because
    # getBoundingClientRect() and touch.clientX/Y are both in CSS pixels.
    'function _getCell(touch){'
    'var el=document.querySelector(".xterm-screen");'
    'if(!el||!window.term)return null;'
    'var r=el.getBoundingClientRect();'
    'var cw=r.width/window.term.cols;'
    'var ch=r.height/window.term.rows;'
    'var col=Math.floor((touch.clientX-r.left)/cw);'
    'var row=Math.floor((touch.clientY-r.top)/ch)+window.term.buffer.active.viewportY;'
    'return{col:Math.max(0,Math.min(col,window.term.cols-1)),row:Math.max(0,row)}'
    '}'

    'document.addEventListener("touchstart",function(e){'
    'if(!_selMode)return;'
    'if(e.target.closest("#toolbar"))return;'
    'e.preventDefault();'
    '_selStart=_getCell(e.touches[0])'
    '},{passive:false});'

    'document.addEventListener("touchmove",function(e){'
    'if(!_selMode||!_selStart||!window.term)return;'
    'if(e.target.closest("#toolbar"))return;'
    'e.preventDefault();'
    'var cur=_getCell(e.touches[0]);'
    'if(!cur)return;'
    'var s0=_selStart.row*window.term.cols+_selStart.col;'
    'var s1=cur.row*window.term.cols+cur.col;'
    'if(s1>=s0)window.term.select(_selStart.col,_selStart.row,s1-s0+1);'
    'else window.term.select(cur.col,cur.row,s0-s1+1)'
    '},{passive:false});'

    # touchend: copy via navigator.clipboard (valid iOS user gesture).
    # Stays in Sel mode so user can drag again without re-tapping the button.
    # Flash the Sel button green briefly to confirm the copy.
    'document.addEventListener("touchend",function(){'
    'if(!_selMode||!window.term)return;'
    '_selStart=null;'
    'var text=window.term.getSelection();'
    'if(!text)return;'
    'navigator.clipboard.writeText(text).catch(function(e){console.error("copy:",e)});'
    'var b=document.getElementById("sel-btn");'
    'b.style.background="#a6e3a1";b.style.color="#1e1e2e";'
    'setTimeout(function(){b.style.background="";b.style.color="";},600)'
    '});'

    # Sticky Ctrl: intercept at document capture phase before xterm.js sees it
    'document.addEventListener("keydown",function(e){'
    'if(!_ctrlPending)return;'
    'if(e.key.length!==1)return;'
    '_ctrlPending=false;'
    'document.getElementById("ctrl-btn").classList.remove("active");'
    'var code=e.key.toUpperCase().charCodeAt(0)-64;'
    'if(code>=1&&code<=26){'
    'e.preventDefault();e.stopImmediatePropagation();'
    'if(window.term)window.term._core.coreService.triggerDataEvent(String.fromCharCode(code))'
    '}'
    '},true);'

    # Cmd+C: copy xterm.js selection to clipboard (desktop).
    # Polls until window.term is ready.
    'var _tw=setInterval(function(){'
    'if(window.term){'
    'clearInterval(_tw);'
    'window.term.attachCustomKeyEventHandler(function(e){'
    'if(e.type==="keydown"&&e.metaKey&&(e.key==="c"||e.key==="C")){'
    'var s=window.term.getSelection();'
    'if(s){_clipWrite(s);window.term.clearSelection();return false}'
    '}'
    'return true'
    '})'
    '}'
    '},200);'

    # Reposition toolbar above the soft keyboard on iOS using visualViewport API
    'if(window.visualViewport){'
    'function _reposition(){'
    'var vvh=window.visualViewport.height;'
    'var offset=window.innerHeight-window.visualViewport.offsetTop-vvh;'
    'var tb=document.getElementById("toolbar");'
    'var tc=document.getElementById("terminal-container");'
    'var th=parseInt(getComputedStyle(document.documentElement).getPropertyValue("--toolbar-h"))||44;'
    'if(tb)tb.style.bottom=offset+"px";'
    'if(tc)tc.style.height=(vvh-th)+"px";'
    'setTimeout(function(){if(window.term&&window.term.fit)window.term.fit()},50);'
    '}'
    'window.visualViewport.addEventListener("resize",_reposition);'
    'window.visualViewport.addEventListener("scroll",_reposition);'
    '}'

    '</script>'
)

viewport = '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">'
html = html.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">' + viewport, 1)
html = html.replace('</style>', toolbar_css + '</style>', 1)
html = html.replace('</body>', toolbar_html + toolbar_js + '</body>')

import os
os.makedirs('/opt/ttyd', exist_ok=True)
with open('/opt/ttyd/index.html', 'w') as f:
    f.write(html)

print(f'Built /opt/ttyd/index.html ({len(html):,} bytes)')
