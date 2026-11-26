"""Small private device portal and on-demand JPEG live viewer."""


def devices_page():
    return """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Устройства | LunexPCControl</title>
<style>
:root{color-scheme:dark;font-family:system-ui,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{background:#0b1018;color:#eef4ff;margin:0}
.wrap{max-width:1000px;margin:auto;padding:24px 16px}
header{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
h1{font-size:30px;letter-spacing:-.8px;margin:7px 0}
h2{font-size:18px;margin-top:0}
.kicker{letter-spacing:.17em;text-transform:uppercase;font-size:12px;color:#90d1ed}
p{line-height:1.65;color:#a9bbcc}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0}
nav a,.link{color:#b0d8f0;text-decoration:none;padding:9px 13px;border-radius:10px;border:1px solid #32506b}
nav a[aria-current=page]{background:#193b52;border-color:#427eaa}
.card{border:1px solid #2b4258;border-radius:18px;background:#142030;padding:20px;margin-bottom:15px}
.device{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.state{font-size:12px;padding:7px 12px;border-radius:25px;background:#293542;color:#d2dce8}
.on{background:#164735;color:#aaf0cb}.off{background:#473129;color:#ffc1a6}
button{font:inherit;background:#173f58;border:1px solid #38769b;color:#e2f7ff;border-radius:10px;padding:10px 14px;cursor:pointer}
button:focus-visible,a:focus-visible{outline:2px solid #a5eaff}
.muted{color:#8fa2b5;font-size:13px}
code{background:#0b1622;border-radius:6px;padding:2px 5px;word-break:break-word}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<header><div><div class="kicker">Lunex • PC Control</div><h1>Мои компьютеры</h1></div>
<span class="muted">🔒 Приватное подключение</span></header>
<nav><a href="/portalmcp/">Обзор</a><a aria-current="page" href="/portalmcp/devices">Устройства</a>
<a href="/portalmcp/live">Live View</a><a href="/portalmcp/monitor">История снимков</a></nav>
<section class="card"><h2>Подключённые устройства</h2>
<p>Windows самостоятельно соединяется с VPS. Публичный IP компьютера
не нужен: при переходе между Wi-Fi, кабелем и мобильным интернетом
соединение может восстановиться автоматически.</p>
<div id="devices" role="status"><p>Проверка подключения...</p></div>
<p class="muted">«В сети» означает доступность обратного SSH-туннеля.
Проверка разрешения на экран выполняется отдельно при открытии Live View.</p>
<button id="reload" type="button">Проверить сейчас</button></section>
<section class="grid">
<div class="card"><h2>1. Установить агент</h2><p>Установите клиент LunexPCControl
в Windows из проверенного релиза и войдите в свою пользовательскую сессию.</p></div>
<div class="card"><h2>2. Привязать компьютер</h2><p>Подтвердите ключ устройства.
Агент устанавливает исходящее зашифрованное соединение с VPS.
Порт Windows в интернет не открывается.</p></div>
<div class="card"><h2>3. Смотреть и управлять</h2><p>Откройте Live View.
Управление мышью и клавиатурой появится после отдельного разрешения
с аварийной остановкой.</p></div>
</section>
<section class="card"><h2>Параметры подключения</h2>
<p>Транспорт: исходящий SSH к VPS. Защита: закреплённый ключ сервера,
отдельный ключ MCP, независимая авторизация панели и клиентов.</p>
<p class="muted">Пока регистрация и выдача новых ключей выполняются через
проверенные серверные команды. Встроенный мастер сопряжения будет добавлен
после выпуска безопасного механизма отзыва и обновления ключей.
Пароли и приватные ключи в браузере не отображаются.</p></section>
</div><script>
const holder=document.getElementById('devices');
async function load(){
 try{
  const response=await fetch('/portalmcp/api/devices',{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const result=await response.json();
  holder.replaceChildren();
  if(!result.devices.length){const p=document.createElement('p');p.textContent='Пока нет зарегистрированных устройств.';holder.append(p);return}
  for(const d of result.devices){
   const wrap=document.createElement('div');wrap.className='device';
   wrap.style.padding='12px 0';wrap.style.borderTop='1px solid #334455';
   const left=document.createElement('div');
   const title=document.createElement('strong');title.textContent=d.id;
   const small=document.createElement('p');small.className='muted';
   small.textContent='Исходящее подключение · IP не привязан';
   left.append(title,small);
   const right=document.createElement('div');right.style.display='flex';right.style.gap='9px';right.style.alignItems='center';
   const state=document.createElement('span');state.className='state '+(d.tunnel_online?'on':'off');
   state.textContent=d.tunnel_online?'В сети':'Не в сети';
   const link=document.createElement('a');link.className='link';
   link.href='/portalmcp/live';link.textContent='Открыть экран';
   right.append(state,link);wrap.append(left,right);holder.append(wrap);
  }
 }catch(err){holder.textContent='Нет связи с сервером статуса.'}
}
document.getElementById('reload').addEventListener('click',load);
load();setInterval(load,5000);
</script></body></html>""".encode("utf-8")


def live_page():
    return """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Live View | LunexPCControl</title>
<style>
:root{color-scheme:dark;font-family:system-ui,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;background:#0b1018;color:#eaf4ff}
.wrap{max-width:1200px;margin:auto;padding:20px 14px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0}
nav a{border:1px solid #38546f;border-radius:10px;padding:9px 13px;color:#c2e7fd;text-decoration:none;font-size:14px}
nav a[aria-current=page]{background:#16415a}
h1{font-size:30px;margin:5px 0;letter-spacing:-.6px}
.muted{color:#a0b4c7;font-size:13px;line-height:1.65}
.panel{background:#142030;border:1px solid #2b4258;border-radius:16px;padding:16px}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:10px 0 16px}
button,select{font:inherit;border:1px solid #3d6a86;background:#183a51;color:white;border-radius:10px;padding:9px 13px}
button{cursor:pointer}button:disabled{opacity:.5;cursor:default}
select{max-width:175px}
.canvas{background:#080e16;display:flex;align-items:center;justify-content:center;
border:1px solid #31475f;border-radius:12px;aspect-ratio:16/9;overflow:hidden;position:relative}
.canvas img{max-width:100%;max-height:100%;width:100%;height:100%;object-fit:contain;display:none}
#placeholder{color:#abc0d0;text-align:center;padding:24px;max-width:360px;line-height:1.7}
.pill{border:1px solid #415b70;color:#bad2df;padding:6px 11px;border-radius:25px;font-size:12px}
small{font-size:12px}
footer{color:#8197ad;font-size:12px;margin:20px 0}
@media(max-width:600px){h1{font-size:25px}.toolbar{gap:7px}.wrap{padding:13px 9px}}
</style></head><body><div class="wrap">
<h1>Live View</h1>
<nav><a href="/portalmcp/">Обзор</a><a href="/portalmcp/devices">Устройства</a>
<a aria-current="page" href="/portalmcp/live">Live View</a><a href="/portalmcp/monitor">История</a></nav>
<p class="muted">Онлайн-трансляция экрана через защищённый туннель.
Видео передаётся единым MJPEG-потоком и запускается только по кнопке.
Можно переключиться на прежний JPEG-режим. Максимум один кадр в секунду
до внедрения аппаратного H.264-кодирования на Windows.</p>
<section class="panel"><div class="toolbar">
<label for="device">Компьютер</label><select id="device"></select>
<label for="quality">Качество</label>
<select id="quality"><option value="data">Экономный · 640p</option>
<option value="balanced" selected>Баланс · 960p</option>
<option value="quality">Чёткий · 1280p</option></select>
<label for="mode">Режим</label>
<select id="mode"><option value="stream" selected>Потоковое видео</option>
<option value="jpeg">Резервный JPEG</option></select>
<button id="start">Начать просмотр</button><button id="stop" disabled>Остановить</button>
<button id="fullscreen">На весь экран</button>
<span class="pill" id="state" role="status">Остановлено</span>
</div>
<div class="canvas" id="canvas"><div id="placeholder">Просмотр выключен.
Выберите компьютер и нажмите «Начать просмотр».</div>
<img id="frame" alt="Текущий кадр компьютера Windows"></div>
<div class="toolbar"><span class="muted" id="metrics">Нет активной трансляции</span>
<span class="muted" id="updated"></span></div></section>
<p class="muted">Режим потока непрерывно передаёт кадры пока открыт просмотр,
но пока это MJPEG, не H.264/WebRTC. Переключение на H.264 запланировано после
установки и проверки аппаратного кодировщика Windows. В случае ошибки соединения
можно выбрать резервный JPEG.</p>
<footer>Логин обязателен. Скриншоты в режиме Live View не сохраняются на диск и не
попадают в историю, если ИИ отдельно не запросил Screenshot через MCP.</footer>
</div><script>
const el=id=>document.getElementById(id);
let active=false, frames=0, transfer=0, controller=null, photoUrl=null;
let streamWatchdog=null, streamRestarts=0, streamNonce=0, mode='stream';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function setStatus(message){el('state').textContent=message}
async function loadDevices(){
 try{
  const r=await fetch('/portalmcp/api/devices',{cache:'no-store'});
  if(!r.ok)throw Error('status');
  const data=await r.json();el('device').replaceChildren();
  for(const dev of data.devices){
   const option=document.createElement('option');
   option.value=dev.id;option.textContent=dev.id+(dev.tunnel_online?' · в сети':' · офлайн');
   el('device').append(option);
  }
  if(!data.devices.length)setStatus('Нет зарегистрированных устройств');
 }catch(e){setStatus('Ошибка получения устройств')}
}
function acceptJpeg(blob){
 return new Promise((resolve,reject)=>{
  const url=URL.createObjectURL(blob);
  const image=new Image();
  image.onload=()=>{resolve(url);};
  image.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('Не удалось декодировать кадр'))};
  image.src=url;
 });
}
async function poll(){
 while(active && mode==='jpeg'){
  try{
   const device=el('device').value, quality=el('quality').value;
   if(!device){setStatus('Устройство не выбрано');break}
   controller=new AbortController();
   const r=await fetch('/portalmcp/api/live/frame/'+encodeURIComponent(device)+'/'+quality+'.jpg',{
    cache:'no-store',headers:{'X-LunexPC-LiveView':'active'},
    signal:controller.signal
   });
   if(!active)break;
   if(r.status===429 || r.status===503){setStatus('Ожидание кадра');await pause(1200);continue}
   if(!r.ok)throw Error('HTTP '+r.status);
   const blob=await r.blob();
   if(!active)break;
   const url=await acceptJpeg(blob);
   if(!active){URL.revokeObjectURL(url);break}
   const prev=photoUrl;photoUrl=url;
   el('frame').src=url;el('frame').style.display='block';
   el('placeholder').style.display='none';
   if(prev)URL.revokeObjectURL(prev);
   frames++;transfer+=blob.size;
   el('metrics').textContent='Отображено '+frames+' кадров · '+Math.round(transfer/1024)+' КБ';
   el('updated').textContent=new Date().toLocaleTimeString('ru-RU');
   setStatus('JPEG · просмотр включён');
  }catch(e){
   if(active){setStatus('Ожидание Windows: '+e.message);await pause(2200)}
  }
  controller=null;
  if(active)await pause(1050);
 }
}
function startStream(){
 const device=el('device').value, quality=el('quality').value;
 if(!device){setStatus('Устройство не выбрано');stop();return}
 const image=el('frame');
 image.style.display='block';
 el('placeholder').style.display='none';
 streamRestarts=0;
 function connect(){
  if(!active || mode!=='stream')return;
  // Force browser to close previous stream before opening a new one.
  image.removeAttribute('src');
  streamNonce++;
  const url='/portalmcp/api/live/stream/'+encodeURIComponent(device)+'/'+quality+'.mjpg';
  image.src=url+'?session='+streamNonce;
  setStatus('Подключение видеопотока...');
 }
 image.onload=()=>{
  if(!active || mode!=='stream')return;
  frames++;
  el('metrics').textContent='Поток MJPEG · кадры отображаются · до 1 FPS';
  el('updated').textContent=new Date().toLocaleTimeString('ru-RU');
  setStatus('Потоковое видео включено');
 };
 image.onerror=()=>{
  if(active && mode==='stream'){
   setStatus('Ошибка видеопотока. Переключись на резервный JPEG');
   stop();
  }
 };
 connect();
 // Server stream has a finite lifetime; restart it occasionally while
 // the user is still watching. Switching away stops this watchdog.
 streamWatchdog=setInterval(()=>{
  if(active && mode==='stream'){
   streamRestarts++;
   if(streamRestarts<100)connect();
  }
 },170000);
}
el('start').addEventListener('click',()=>{
 if(active)return;active=true;frames=0;transfer=0;
 mode=el('mode').value;
 el('start').disabled=true;el('stop').disabled=false;
 el('device').disabled=true;el('quality').disabled=true;el('mode').disabled=true;
 setStatus('Подключение...');
 if(mode==='stream')startStream();
 else poll().finally(()=>{if(active && mode==='jpeg')stop()});
});
function stop(){
 active=false;
 if(controller)controller.abort();
 if(streamWatchdog)clearInterval(streamWatchdog);
 streamWatchdog=null;
 const img=el('frame');img.onerror=null;img.onload=null;
 // Immediate abort of streaming <img> transport; no screenshot request
 // remains active when the tab is hidden or the user presses Stop.
 img.removeAttribute('src');img.style.display='none';
 el('placeholder').style.display='block';
 if(photoUrl)URL.revokeObjectURL(photoUrl);
 photoUrl=null;
 el('start').disabled=false;el('stop').disabled=true;
 el('device').disabled=false;el('quality').disabled=false;el('mode').disabled=false;
 setStatus('Остановлено');
}
el('stop').addEventListener('click',stop);
el('fullscreen').addEventListener('click',()=>{
 if(el('canvas').requestFullscreen)el('canvas').requestFullscreen().catch(()=>{});
});
window.addEventListener('pagehide',stop);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
loadDevices();
</script></body></html>""".encode("utf-8")
