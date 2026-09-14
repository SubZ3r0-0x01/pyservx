#!/usr/bin/env python3
"""PyServeX Liquid Glass UI shell.

Single source of truth for the visual layer: design tokens, glass
component CSS, the animated aurora backdrop and a dependency-free
WebGL2 "liquid glass" engine (SDF superellipse lenses with refraction,
chromatic dispersion, Fresnel rim and glare) recreated after Apple's
Liquid Glass.  Falls back to pure CSS when WebGL2 is unavailable or the
user prefers reduced motion.
"""

# ---------------------------------------------------------------------------
# design tokens + component css
# ---------------------------------------------------------------------------
GLASS_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --glass-bg:rgba(255,255,255,.05);
  --glass-bg-strong:rgba(255,255,255,.09);
  --glass-bg-solid:rgba(16,17,24,.66);
  --glass-border:rgba(255,255,255,.16);
  --glass-highlight:rgba(255,255,255,.38);
  --glass-blur:9px;
  --glass-saturate:135%;
  --radius-panel:24px;
  --radius-btn:14px;
  --page-bg:#04050c;
  --text-primary:#f5f5f7;
  --text-secondary:rgba(235,235,245,.62);
  --accent:#0a84ff;
  --accent-2:#5e5ce6;
  --accent-contrast:#fff;
  --glow-rgb:10,132,255;
  --danger:#ff453a;
  --success:#30d158;
  --warning:#ffd60a;
  --shadow:0 12px 44px rgba(0,0,0,.42),
           inset 0 1px 0 var(--glass-highlight),
           inset 0 -1px 0 rgba(255,255,255,.06);
  --spring:cubic-bezier(.34,1.56,.64,1);
}
/* ---- accent colour themes -------------------------------------------- */
html[data-accent="violet"]{--accent:#bf5af2;--accent-2:#ff375f;--glow-rgb:191,90,242}
html[data-accent="teal"]{--accent:#4dd0e1;--accent-2:#30d158;--glow-rgb:77,208,225}
html[data-accent="sunset"]{--accent:#ff9f0a;--accent-2:#ff375f;--glow-rgb:255,159,10}
html[data-accent="emerald"]{--accent:#30d158;--accent-2:#64d2ff;--glow-rgb:48,209,88}
html[data-accent="rose"]{--accent:#ff6482;--accent-2:#bf5af2;--glow-rgb:255,100,130}

html[data-theme="light"], body.light-theme{
  --glass-bg:rgba(255,255,255,.42);
  --glass-bg-strong:rgba(255,255,255,.62);
  --glass-bg-solid:rgba(255,255,255,.82);
  --glass-border:rgba(20,25,45,.13);
  --glass-highlight:rgba(255,255,255,.95);
  --page-bg:#eef1f7;
  --text-primary:#1d1d1f;
  --text-secondary:rgba(60,60,67,.6);
  --shadow:0 12px 40px rgba(31,38,63,.14),inset 0 1px 0 #fff;
}

*{box-sizing:border-box}
html,body{margin:0;padding:0;min-height:100%}
body{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:var(--page-bg);color:var(--text-primary);
  -webkit-font-smoothing:antialiased;
  transition:background-color .3s ease,color .3s ease;
  overflow-x:hidden;
}

/* ---- animated aurora backdrop (css layer; canvas takes over if webgl2) */
.aurora{position:fixed;inset:-20%;z-index:-2;pointer-events:none;
  filter:blur(64px) saturate(115%);
  background:
   radial-gradient(42% 46% at 20% 24%,rgba(70,86,180,.20),transparent 68%),
   radial-gradient(36% 40% at 80% 16%,rgba(28,96,160,.16),transparent 70%),
   radial-gradient(48% 44% at 66% 82%,rgba(110,72,170,.14),transparent 72%),
   radial-gradient(30% 32% at 26% 88%,rgba(40,120,140,.10),transparent 70%),
   radial-gradient(120% 90% at 50% 0%,rgba(16,20,38,.35),transparent 60%),
   linear-gradient(180deg,#05060f 0%,#04050c 55%,#030409 100%);
  animation:auroraShift 44s ease-in-out infinite alternate;}
/* soft vignette + film grain for depth */
.lg-vignette{position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(130% 100% at 50% 40%,transparent 58%,rgba(2,3,8,.5) 100%)}
.lg-grain{position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.05;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
html[data-theme="light"] .lg-vignette,body.light-theme .lg-vignette{
  background:radial-gradient(130% 100% at 50% 40%,transparent 62%,rgba(84,98,138,.18) 100%)}
html[data-theme="light"] .lg-grain,body.light-theme .lg-grain{opacity:.035}
@keyframes auroraShift{
 0%{transform:translate3d(-1.5%,-1%,0) scale(1)}
 50%{transform:translate3d(2%,1.5%,0) scale(1.04)}
 100%{transform:translate3d(-1%,2%,0) scale(.98)}}
#lgCanvas{position:fixed;inset:0;z-index:-1;width:100%;height:100%;display:none;pointer-events:none}
#lgCanvas.on{display:block}
html[data-theme="light"] #lgCanvas,body.light-theme #lgCanvas{display:none!important}
html[data-theme="light"] .aurora,body.light-theme .aurora{
  background:
   radial-gradient(42% 46% at 20% 24%,rgba(120,140,235,.16),transparent 68%),
   radial-gradient(36% 40% at 80% 16%,rgba(96,170,220,.14),transparent 70%),
   radial-gradient(48% 44% at 66% 82%,rgba(190,140,230,.12),transparent 72%),
   linear-gradient(180deg,#f4f6fc 0%,#eef1f7 60%,#e9edf5 100%)}

/* ---- glass primitives ------------------------------------------------ */
.glass,.glass-panel{
  background:var(--glass-bg);
  -webkit-backdrop-filter:blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter:blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border:1px solid var(--glass-border);
  border-radius:var(--radius-panel);
  box-shadow:var(--shadow);
  position:relative;
}
.glass-panel::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  background:linear-gradient(118deg,rgba(255,255,255,.22),rgba(255,255,255,.02) 24%,transparent 42%);
  mix-blend-mode:screen;opacity:.55}
.glass-panel::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.22),inset 0 -1px 0 rgba(255,255,255,.05)}

.glass-btn,.glass-btn-accent,.glass-btn-danger,.glass-btn-success{
  display:inline-flex;align-items:center;justify-content:center;gap:.4rem;
  background:var(--glass-bg-strong);
  -webkit-backdrop-filter:blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter:blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border:1px solid var(--glass-border);border-radius:var(--radius-btn);
  color:var(--text-primary);padding:.52rem 1rem;cursor:pointer;font-family:inherit;
  font-size:.92rem;font-weight:500;line-height:1.25;
  box-shadow:0 2px 10px rgba(0,0,0,.25),inset 0 1px 0 var(--glass-highlight);
  transition:transform .18s var(--spring),background .18s ease,box-shadow .18s ease,border-color .18s ease;
  user-select:none;text-decoration:none;
}
.glass-btn:hover,.glass-btn-accent:hover,.glass-btn-danger:hover,.glass-btn-success:hover{
  transform:translateY(-2px) scale(1.02);border-color:rgba(255,255,255,.28);
  box-shadow:0 6px 22px rgba(0,0,0,.35),inset 0 1px 0 var(--glass-highlight);}
.glass-btn:active,.glass-btn-accent:active,.glass-btn-danger:active,.glass-btn-success:active{
  transform:translateY(0) scale(.97);}
.glass-btn:focus-visible,.glass-input:focus-visible{outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(var(--glow-rgb),.35)}
.glass-btn-accent{background:linear-gradient(135deg,var(--accent),var(--accent-2));
  color:var(--accent-contrast);border:none;
  box-shadow:0 4px 18px rgba(var(--glow-rgb),.35),inset 0 1px 0 rgba(255,255,255,.35)}
.glass-btn-danger{background:linear-gradient(135deg,#ff453a,#ff9f0a);color:#fff;border:none}
.glass-btn-success{background:linear-gradient(135deg,#30d158,#64d2ff);color:#06280f;border:none}

.glass-input,textarea.glass-input,select.glass-input{
  background:var(--glass-bg);
  -webkit-backdrop-filter:blur(var(--glass-blur));backdrop-filter:blur(var(--glass-blur));
  border:1px solid var(--glass-border);border-radius:var(--radius-btn);
  color:var(--text-primary);padding:.52rem .8rem;font-family:inherit;font-size:.95rem;
  transition:border-color .15s ease,box-shadow .15s ease,background .15s ease;
}
.glass-input::placeholder{color:var(--text-secondary)}
select.glass-input option{background:#1c1c20;color:#f5f5f7}

/* legacy compat: old templates keep their class names working */
.text-neon{color:var(--text-primary)}
.btn-green{composes:none;background:linear-gradient(135deg,var(--accent),var(--accent-2));
  color:#fff;border:none;border-radius:var(--radius-btn)}

table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:.6rem .8rem;border-bottom:1px solid var(--glass-border)}
th{color:var(--text-secondary);font-weight:600;font-size:.8rem;text-transform:uppercase;
  letter-spacing:.06em;cursor:pointer;position:sticky;top:0;z-index:5;
  background:var(--glass-bg-solid);
  -webkit-backdrop-filter:blur(var(--glass-blur));backdrop-filter:blur(var(--glass-blur))}
tbody tr{transition:background .15s ease}
tbody tr:hover{background:var(--glass-bg)}
input,textarea,button,select{font-family:inherit}
button{cursor:pointer}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:var(--glass-bg-strong);padding:2px 7px;border-radius:7px;font-size:.88em}

::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--glass-border);border-radius:5px;border:2px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:var(--text-secondary);background-clip:content-box}

dialog.glass-dialog,dialog{
  background:var(--glass-bg-solid);color:var(--text-primary);
  -webkit-backdrop-filter:blur(14px) saturate(135%);backdrop-filter:blur(14px) saturate(135%);
  border:1px solid var(--glass-border);border-radius:var(--radius-panel);
  padding:22px;min-width:320px;max-width:92vw;box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(3,4,9,.5);backdrop-filter:blur(4px)}
dialog input{width:100%;margin:4px 0 10px}

.theme-toggle-btn{position:fixed;top:.8rem;right:.8rem;z-index:1200;padding:.42rem .6rem;font-size:1.05rem}

/* ---- accent palette picker (injected by THEME_JS) --------------------- */
.lg-palette-btn{position:fixed;top:.8rem;right:3.6rem;z-index:1200;padding:.42rem .6rem;
  font-size:1.02rem}
.lg-palette{position:fixed;top:3.6rem;right:3.6rem;z-index:1201;display:none;gap:.55rem;
  padding:.7rem .8rem;border-radius:18px;align-items:center;flex-wrap:wrap;max-width:240px}
.lg-palette.open{display:flex}
.lg-dot{width:26px;height:26px;border-radius:50%;cursor:pointer;border:2px solid transparent;
  box-shadow:inset 0 1px 2px rgba(255,255,255,.45),0 2px 8px rgba(0,0,0,.35);
  transition:transform .15s var(--spring),border-color .15s ease}
.lg-dot:hover{transform:scale(1.15)}
.lg-dot.sel{border-color:#fff;transform:scale(1.12)}

.mono{font-family:'SF Mono','Cascadia Code','Courier New',monospace;word-break:break-all}
.danger{color:var(--danger);border-color:var(--danger)}

/* ---- inline documentation blocks -------------------------------------- */
.doc-card h3{margin-top:0}
.doc-steps{margin:.4rem 0 .6rem;padding-left:1.3rem;line-height:1.75}
.doc-steps li{margin:.15rem 0;color:var(--text-primary)}
.doc-steps code,.doc-notes code{font-size:.85em}
.doc-notes{margin:.4rem 0 0;padding-left:1.2rem;line-height:1.7;
  color:var(--text-secondary);font-size:.9rem}
.doc-cols{display:flex;gap:18px;flex-wrap:wrap}
.doc-cols>div{flex:1;min-width:220px}
.doc-cols h4{margin:.2rem 0 .4rem;font-size:.95rem}
.doc-code{padding:12px;border-radius:var(--radius-btn);overflow:auto;max-height:260px;
  font-size:.82rem;line-height:1.6;color:var(--text-secondary);
  background:rgba(120,120,128,.08);border:1px solid var(--glass-border);margin:.5rem 0}
.sftp-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;margin:.6rem 0;
  font-size:.92rem}
.sftp-grid>div{padding:8px 10px;border-radius:var(--radius-btn);
  background:rgba(120,120,128,.07);border:1px solid var(--glass-border)}
.sftp-grid .wide{grid-column:1/-1}
.sftp-grid .k{display:block;font-size:.72rem;text-transform:uppercase;
  letter-spacing:.06em;color:var(--text-secondary);margin-bottom:2px}
.sftp-grid .status-on{color:var(--success)}
.sftp-grid .status-off{color:var(--warning)}

@media (prefers-reduced-motion:reduce){
  .aurora{animation:none}
  *{transition-duration:.01ms!important;animation-duration:.01ms!important}
}
"""

# ---------------------------------------------------------------------------
# liquid glass engine (vanilla WebGL2, injected once per page)
# ---------------------------------------------------------------------------
LIQUID_JS = r"""
(function(){
'use strict';
if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
var canvas = document.getElementById('lgCanvas');
if (!canvas || !window.WebGL2RenderingContext) return;
var gl = canvas.getContext('webgl2',{antialias:true,alpha:false,powerPreference:'low-power'});
if (!gl) return;

var VS = '#version 300 es\nin vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';

var FS = [
'#version 300 es','precision highp float;',
'uniform vec2 uRes;uniform float uTime;',
'out vec4 frag;',
'float hash(vec2 q){return fract(sin(dot(q,vec2(127.1,311.7)))*43758.5453);}',
'float noise(vec2 q){vec2 i=floor(q),f=fract(q);f=f*f*(3.-2.*f);',
' return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}',
'float fbm(vec2 q){float v=0.,a=.5;for(int k=0;k<5;k++){v+=a*noise(q);q*=2.03;a*=.55;}return v;}',
'vec3 aurora(vec2 uv,float t){',
' vec2 m=uv*1.5;float t1=t*.030,t2=t*.021;',
' float b1=fbm(m+vec2(t1,-t2)+fbm(m*1.7-t1)*1.4);',
' float b2=fbm(m*1.3-vec2(t2,t1)+fbm(m*.9+t2)*1.2);',
' float b3=fbm(m*.8+vec2(sin(t*.026),cos(t*.033))*1.5);',
' vec3 col=vec3(.010,.012,.028);',                              /* deep space base */
' col+=vec3(.10,.13,.42)*smoothstep(.46,.92,b1)*.55;',          /* indigo silk */
' col+=vec3(.04,.22,.44)*smoothstep(.52,.95,b2)*.45;',          /* steel blue */
' col+=vec3(.26,.14,.48)*smoothstep(.54,.96,b3)*.38;',          /* soft violet */
' col+=vec3(.06,.34,.40)*smoothstep(.58,.97,fbm(m*2.1+t*.04))*.22;',
' col+=vec3(.85,.90,1.)*pow(max(b1*b2*1.6-.32,0.),2.6)*.22;',   /* faint starlight */
' return col;}',
'vec3 orbGlow(vec2 uv,vec2 c,float r,vec3 tint){',
' float d=length(uv-c);',
' return tint*exp(-d*d/(r*r));}',
'void main(){',
' vec2 fpx=gl_FragCoord.xy;',
' vec2 uv=(fpx-.5*uRes)/uRes.y;',
' float t=uTime;',
' vec3 bg=aurora(uv,t);',
/* elemental drifting lights: slow orbits, breathing intensity */
' vec3 o=vec3(0.);',
' vec2 p1=vec2(-.42+.16*sin(t*.09), .22+.12*cos(t*.061));',
' vec2 p2=vec2( .44+.13*sin(t*.052+.9), -.18+.15*cos(t*.081+.4));',
' vec2 p3=vec2( .05+.20*sin(t*.037+2.1), .34+.10*cos(t*.047+1.3));',
' vec2 p4=vec2(-.25+.14*sin(t*.068+4.0),-.30+.13*cos(t*.058+2.7));',
' float br1=.75+.25*sin(t*.21);',
' float br2=.75+.25*sin(t*.17+1.9);',
' float br3=.80+.20*sin(t*.19+3.1);',
' float br4=.70+.30*sin(t*.23+4.6);',
' o+=orbGlow(uv,p1,.16,vec3(.10,.28,.62))*br1;',   /* deep water */
' o+=orbGlow(uv,p2,.20,vec3(.24,.14,.50))*br2;',   /* violet ember */
' o+=orbGlow(uv,p3,.12,vec3(.06,.36,.42))*br3;',   /* mist teal */
' o+=orbGlow(uv,p4,.10,vec3(.30,.20,.55))*br4;',   /* dusk air */
' bg+=o*.55;',
' float vig=1.-.42*pow(length((fpx/uRes-vec2(.5,.45))*vec2(1.,1.15))*1.35,1.8);',
' bg*=clamp(vig,0.,1.);',                                       /* elegant vignette */
' bg+=(hash(fpx+fract(t))-.5)/255.;',                           /* dither: no banding */
' frag=vec4(bg,1.);}'
].join('\n');

function sh(type,src){var s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);
 if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){console.warn('lg:',gl.getShaderInfoLog(s));return null;}return s;}
var v=sh(gl.VERTEX_SHADER,VS),f=sh(gl.FRAGMENT_SHADER,FS);
if(!v||!f)return;
var prog=gl.createProgram();gl.attachShader(prog,v);gl.attachShader(prog,f);gl.linkProgram(prog);
if(!gl.getProgramParameter(prog,gl.LINK_STATUS)){console.warn('lg link:',gl.getProgramInfoLog(prog));return;}
gl.useProgram(prog);
var buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);
gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
var locP=gl.getAttribLocation(prog,'p');
gl.enableVertexAttribArray(locP);gl.vertexAttribPointer(locP,2,gl.FLOAT,false,0,0);
var U={};['uRes','uTime'].forEach(function(n){U[n]=gl.getUniformLocation(prog,n);});

canvas.classList.add('on');

var last=performance.now(),running=true,rafId=0;

function resize(){
  var dpr=Math.min(devicePixelRatio||1,2);
  canvas.width=Math.max(1,Math.floor(innerWidth*dpr));
  canvas.height=Math.max(1,Math.floor(innerHeight*dpr));
  gl.viewport(0,0,canvas.width,canvas.height);
}
resize();addEventListener('resize',resize);

document.addEventListener('visibilitychange',function(){
  var was=!running;running=!document.hidden;
  if(running&&was){last=performance.now();rafId=requestAnimationFrame(frame);}});

function frame(now){
  if(!running)return;
  var dt=Math.min((now-last)/1000,.05);last=now;
  gl.uniform2f(U.uRes,canvas.width,canvas.height);
  gl.uniform1f(U.uTime,now/1000);
  gl.drawArrays(gl.TRIANGLES,0,3);
  rafId=requestAnimationFrame(frame);
}
rafId=requestAnimationFrame(frame);
})();
"""

GLASS_BODY_OPEN = ('<canvas id="lgCanvas" aria-hidden="true"></canvas>'
                   '<div class="aurora" aria-hidden="true"></div>'
                   '<div class="lg-vignette" aria-hidden="true"></div>'
                   '<div class="lg-grain" aria-hidden="true"></div>')

THEME_JS = r"""
(function(){
  var ACCENTS=[
    {id:'blue',   c1:'#0a84ff',c2:'#5e5ce6'},
    {id:'violet', c1:'#bf5af2',c2:'#ff375f'},
    {id:'teal',   c1:'#4dd0e1',c2:'#30d158'},
    {id:'sunset', c1:'#ff9f0a',c2:'#ff375f'},
    {id:'emerald',c1:'#30d158',c2:'#64d2ff'},
    {id:'rose',   c1:'#ff6482',c2:'#bf5af2'}
  ];
  function apply(mode){
    document.documentElement.setAttribute('data-theme',mode);
    document.body.classList.toggle('light-theme',mode==='light');
    var ic=document.getElementById('themeIcon');
    if(ic){ic.textContent = mode==='light' ? '\u2600\uFE0F' : '\uD83C\uDF19';}
  }
  function applyAccent(id){
    if(ACCENTS.some(function(a){return a.id===id;})){
      document.documentElement.setAttribute('data-accent',id);
      localStorage.setItem('pyservx-accent',id);
    }
  }
  function buildPalette(pop){
    ACCENTS.forEach(function(a){
      var d=document.createElement('button');
      d.className='lg-dot';
      d.title=a.id;
      d.style.background='linear-gradient(135deg,'+a.c1+','+a.c2+')';
      d.setAttribute('aria-label','accent '+a.id);
      d.addEventListener('click',function(){
        applyAccent(a.id);
        Array.prototype.forEach.call(pop.children,function(el){el.classList.remove('sel');});
        d.classList.add('sel');
      });
      pop.appendChild(d);
    });
  }
  window.psxApplyTheme = apply;
  window.initTheme = function(){
    apply(localStorage.getItem('pyservx-theme')==='light' ? 'light' : 'dark');
    var saved=localStorage.getItem('pyservx-accent');
    if(saved)applyAccent(saved);

    var btn=document.getElementById('themeToggle');
    if(btn&&!btn.dataset.bound){btn.dataset.bound='1';
      btn.addEventListener('click',function(){
        var next=document.documentElement.getAttribute('data-theme')==='light'?'dark':'light';
        localStorage.setItem('pyservx-theme',next);apply(next);
      });}

    if(!document.getElementById('lgPaletteBtn')){
      var pb=document.createElement('button');
      pb.id='lgPaletteBtn';pb.className='glass-btn lg-palette-btn';
      pb.innerHTML='\uD83C\uDFA8';pb.title='Colour theme';
      var pop=document.createElement('div');
      pop.className='glass lg-palette';
      pop.id='lgPalette';
      buildPalette(pop);
      pb.addEventListener('click',function(ev){
        ev.stopPropagation();
        var cur=document.documentElement.getAttribute('data-accent')||'blue';
        Array.prototype.forEach.call(pop.children,function(el,i){
          el.classList.toggle('sel',ACCENTS[i]&&ACCENTS[i].id===cur);});
        pop.classList.toggle('open');
      });
      document.addEventListener('click',function(ev){
        if(pop.classList.contains('open')&&!pop.contains(ev.target))pop.classList.remove('open');
      });
      var anchor=document.getElementById('themeToggle')||document.body;
      anchor.parentNode.insertBefore(pb,anchor);
      document.body.appendChild(pop);
    }
  };
})();
"""


def shell(title, body_html, extra_head="", theme_init=True):
    """Wrap a page body in the full Liquid Glass document skeleton."""
    init = "<script>window.addEventListener('DOMContentLoaded',function(){" \
           "if(window.initTheme)window.initTheme();});</script>" if theme_init else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>{GLASS_CSS}</style>
{extra_head}
</head>
<body>
{GLASS_BODY_OPEN}
{body_html}
<script>{THEME_JS}</script>
<script>{LIQUID_JS}</script>
{init}
</body>
</html>
"""
