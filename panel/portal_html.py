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
button,input,select{font:inherit;background:#173f58;border:1px solid #38769b;color:#e2f7ff;border-radius:10px;padding:10px 14px}
button{cursor:pointer}
input{max-width:250px;width:100%}
select{max-width:200px}
.form-row{display:flex;align-items:center;flex-wrap:wrap;gap:10px}
#pairCode{display:block;overflow-wrap:anywhere;line-height:1.9;user-select:all;padding:12px;margin:10px 0}
#inviteBox{border:1px solid #3b718b;border-radius:12px;padding:15px;margin:14px 0;background:#102b3e}
#inviteBox[hidden]{display:none}
.manage-row{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;border-top:1px solid #2b4258;padding:12px 0}
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
<section class="card" id="addDevice">
<h2>Добавить Windows или Linux</h2>
<p>Создайте одноразовый код на 10 минут. На новом компьютере скачайте
Lunex Connector, запустите сопряжение и введите код. Установка не
открывает входящие порты и не даёт ИИ доступ к мыши или терминалу.</p>
<div class="form-row">
<label for="newOs">Система</label>
<select id="newOs"><option value="windows">Windows</option>
<option value="linux">Ubuntu / Linux</option></select>
<label for="newName">Имя</label>
<input id="newName" maxlength="48" value="Мой компьютер" aria-label="Имя устройства">
<button id="createInvite" type="button">Создать код подключения</button>
</div>
<div id="inviteBox" hidden>
<strong>Код подключения, действителен 10 минут</strong>
<code id="pairCode"></code>
<button id="copyCode" type="button">Копировать код</button>
<p class="muted">Код показывается только один раз и не сохраняется
в браузере. Не отправляйте его посторонним.</p>
<p>1. <a href="https://github.com/maillunex-lang/LunexPCControl/releases"
target="_blank" rel="noopener noreferrer">Скачать коннектор с GitHub</a></p>
<p>2. Откройте терминал в папке скачанного файла и запустите:</p>
<code id="pairCommand"></code>
<p>3. Введите код выше. Для подключения выполните:</p>
<code id="runCommand"></code>
<p class="muted">При первом запуске соединение только сообщает
онлайн-статус. Права доступа выдаются отдельно.</p>
</div>
<p id="inviteState" role="status" class="muted"></p>
</section>
<section class="card"><h2>Коннекторы</h2>
<p class="muted">Подтверждённые устройства. Отзыв подключения немедленно
отменяет право отправлять статус.</p>
<div id="managedDevices" role="status">Загрузка списка...</div>
<button id="refreshManaged" type="button">Обновить список</button>
</section>
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
<p class="muted">Мастер сопряжения доступен выше. Приватный ключ создаётся
на самом устройстве и не передаётся порталу. В этой версии коннектор
показывает состояние онлайн. Удалённое управление подключим после
отдельного утверждения разрешений и механизма аварийной остановки.</p></section>
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
const managed=document.getElementById('managedDevices');
async function refreshManaged(){
 try{
  const response=await fetch('/portalmcp/api/connectors',{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const data=await response.json();
  managed.replaceChildren();
  if(!data.devices.length){
   const p=document.createElement('p');p.textContent='Новых коннекторов пока нет.';
   managed.append(p);return
  }
  for(const dev of data.devices){
   const wrap=document.createElement('div');wrap.className='manage-row';
   const info=document.createElement('div');
   const title=document.createElement('strong');title.textContent=dev.name;
   const meta=document.createElement('p');meta.className='muted';
   meta.textContent=dev.os+' · '+(dev.online?'В сети':'Офлайн')+' · '+dev.id.slice(0,8);
   info.append(title,meta);
   const revoke=document.createElement('button');revoke.type='button';
   revoke.textContent='Отозвать';
   revoke.addEventListener('click',async()=>{
    if(!confirm('Отозвать подключение '+dev.name+'?'))return;
    revoke.disabled=true;
    try{
     const res=await fetch('/portalmcp/api/connectors/revoke',{
      method:'POST',headers:{'Content-Type':'application/json',
       'X-LunexPC-Action':'connector-revoke'},
      body:JSON.stringify({device_id:dev.id})});
     if(!res.ok)throw Error('HTTP '+res.status);
     await refreshManaged();
    }catch(err){revoke.disabled=false;alert('Не удалось отозвать: '+err.message)}
   });
   wrap.append(info,revoke);managed.append(wrap);
  }
 }catch(e){managed.textContent='Не удалось получить список: '+e.message}
}
document.getElementById('createInvite').addEventListener('click',async()=>{
 const btn=document.getElementById('createInvite'),state=document.getElementById('inviteState');
 const os=document.getElementById('newOs').value;
 const name=document.getElementById('newName').value.trim();
 document.getElementById('inviteBox').hidden=true;
 btn.disabled=true;
 try{
  const res=await fetch('/portalmcp/api/connectors/invitations',{
   method:'POST',headers:{'Content-Type':'application/json',
    'X-LunexPC-Action':'connector-invite'},
   body:JSON.stringify({os,name})});
  if(!res.ok)throw Error('HTTP '+res.status);
  const data=await res.json();
  document.getElementById('pairCode').textContent=data.pairing_code;
  const bin=os==='windows'?'.\\lunex-connector-windows-amd64.exe':'./lunex-connector-linux-amd64';
  document.getElementById('pairCommand').textContent=bin+' pair';
  document.getElementById('runCommand').textContent=bin+' run';
  document.getElementById('inviteBox').hidden=false;
  state.textContent='Код готов. Используйте его на выбранном устройстве.';
 }catch(e){state.textContent='Ошибка создания приглашения: '+e.message}
 finally{btn.disabled=false}
});
document.getElementById('copyCode').addEventListener('click',async()=>{
 try{await navigator.clipboard.writeText(document.getElementById('pairCode').textContent);
  document.getElementById('inviteState').textContent='Код скопирован';
 }catch(e){document.getElementById('inviteState').textContent='Выделите и скопируйте код вручную'}
});
document.getElementById('reload').addEventListener('click',load);
document.getElementById('refreshManaged').addEventListener('click',refreshManaged);
load();refreshManaged();setInterval(load,5000);setInterval(refreshManaged,10000);
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
.canvas video{max-width:100%;max-height:100%;width:100%;height:100%;object-fit:contain;display:none}
#placeholder{color:#abc0d0;text-align:center;padding:24px;max-width:360px;line-height:1.7}
.pill{border:1px solid #415b70;color:#bad2df;padding:6px 11px;border-radius:25px;font-size:12px}
small{font-size:12px}
footer{color:#8197ad;font-size:12px;margin:20px 0}
@media(max-width:600px){h1{font-size:25px}.toolbar{gap:7px}.wrap{padding:13px 9px}}
</style></head><body><div class="wrap">
<h1>Live View</h1>
<nav><a href="/portalmcp/">Обзор</a><a href="/portalmcp/devices">Устройства</a>
<a aria-current="page" href="/portalmcp/live">Live View</a><a href="/portalmcp/monitor">История</a></nav>
<p class="muted">Защищённая онлайн-трансляция экрана Windows. Выбери
H.264 для аппаратного видео (цель 10–30 FPS), MJPEG для резервного
потока или JPEG для отдельных кадров. Захват запускается только по кнопке
и останавливается, когда закрываешь просмотр.</p>
<section class="panel"><div class="toolbar">
<label for="device">Компьютер</label><select id="device"></select>
<label for="quality">Качество</label>
<select id="quality"><option value="data">Экономный</option>
<option value="balanced" selected>Баланс</option>
<option value="quality">Высокий</option></select>
<label for="mode">Режим</label>
<select id="mode"><option value="h264" selected>H.264 · Аппаратное видео</option>
<option value="stream">MJPEG · Резервный поток</option>
<option value="jpeg">JPEG · Отдельные кадры</option></select>
<button id="start">Начать просмотр</button><button id="stop" disabled>Остановить</button>
<button id="fullscreen">На весь экран</button>
<span class="pill" id="state" role="status">Остановлено</span>
</div>
<div class="canvas" id="canvas"><div id="placeholder">Просмотр выключен.
Выберите компьютер и нажмите «Начать просмотр».</div>
<img id="frame" alt="Текущий кадр компьютера Windows">
<video id="h264Video" muted playsinline autoplay aria-label="Видеопоток Windows"></video></div>
<div class="toolbar"><span class="muted" id="metrics">Нет активной трансляции</span>
<span class="muted" id="updated"></span></div></section>
<p class="muted">H.264 использует NVENC и воспроизводится браузером через
Media Source Extensions. При отсутствии кодировщика или совместимого браузера
автоматически включится резервный MJPEG. Фактические FPS и задержка зависят
от сети и состояния интерактивного сеанса Windows.</p>
<footer>Логин обязателен. Скриншоты в режиме Live View не сохраняются на диск и не
попадают в историю, если ИИ отдельно не запросил Screenshot через MCP.</footer>
</div><script>
const el=id=>document.getElementById(id);
let active=false, frames=0, transfer=0, controller=null, photoUrl=null;
let streamWatchdog=null, streamRestarts=0, mode='h264';
let h264Abort=null, h264ObjectUrl=null, h264Media=null;
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
 stopH264();
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
  const url='/portalmcp/api/live/stream/'+encodeURIComponent(device)+'/'+quality+'.mjpg';
  image.src=url;
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
const h264Codec='video/mp4; codecs="avc1.42E02A"';
function canPlayH264(){
 return !!(window.MediaSource && MediaSource.isTypeSupported(h264Codec));
}
function stopH264(){
 if(h264Abort){h264Abort.abort();h264Abort=null}
 const v=el('h264Video');
 v.pause();v.removeAttribute('src');v.load();v.style.display='none';
 if(h264ObjectUrl){URL.revokeObjectURL(h264ObjectUrl);h264ObjectUrl=null}
 h264Media=null;
}
function waitMediaOpen(media,signal){
 return new Promise((resolve,reject)=>{
  if(media.readyState==='open'){resolve();return}
  const clean=()=>{media.removeEventListener('sourceopen',ready);signal.removeEventListener('abort',abort)};
  const ready=()=>{clean();resolve()};
  const abort=()=>{clean();reject(new Error('Stopped'))};
  media.addEventListener('sourceopen',ready);
  signal.addEventListener('abort',abort,{once:true});
 });
}
function updateBuffer(buffer,operation,signal){
 return new Promise((resolve,reject)=>{
  if(signal.aborted){reject(new Error('Stopped'));return}
  const clean=()=>{buffer.removeEventListener('updateend',ready);buffer.removeEventListener('error',error);signal.removeEventListener('abort',abort)};
  const ready=()=>{clean();resolve()};
  const error=()=>{clean();reject(new Error('Video decoder rejected stream'))};
  const abort=()=>{clean();reject(new Error('Stopped'))};
  buffer.addEventListener('updateend',ready);
  buffer.addEventListener('error',error);
  signal.addEventListener('abort',abort,{once:true});
  try{operation()}catch(e){clean();reject(e)}
 });
}
async function h264Once(){
 const device=el('device').value, quality=el('quality').value;
 if(!device)throw new Error('Компьютер не выбран');
 const video=el('h264Video');
 h264Abort=new AbortController();
 const signal=h264Abort.signal;
 h264Media=new MediaSource();
 h264ObjectUrl=URL.createObjectURL(h264Media);
 video.src=h264ObjectUrl;
 video.muted=true;video.autoplay=true;video.playsInline=true;
 video.style.display='block';
 el('frame').style.display='none';
 el('placeholder').style.display='none';
 await waitMediaOpen(h264Media,signal);
 if(signal.aborted)throw new Error('Stopped');
 const buffer=h264Media.addSourceBuffer(h264Codec);
 buffer.mode='segments';
 const url='/portalmcp/api/live/h264/'+encodeURIComponent(device)+'/'+quality+'.mp4';
 const response=await fetch(url,{cache:'no-store',signal,headers:{'X-LunexPC-Video':'active'}});
 if(!response.ok)throw new Error('HTTP '+response.status);
 if(!response.body)throw new Error('No stream response');
 const reader=response.body.getReader();
 const profileName={data:'480p / 10 FPS',balanced:'720p / 20 FPS',quality:'1080p / 30 FPS'}[quality];
 let received=0;
 try{
  video.play().catch(()=>{});
  while(active && mode==='h264' && !signal.aborted){
   const part=await reader.read();
   if(part.done)break;
   if(!part.value || !part.value.byteLength)continue;
   await updateBuffer(buffer,()=>buffer.appendBuffer(part.value),signal);
   received+=part.value.byteLength;
   if(video.buffered.length){
    const last=video.buffered.length-1;
    const liveEdge=video.buffered.end(last);
    if(liveEdge-video.currentTime>2.5)video.currentTime=Math.max(0,liveEdge-0.5);
    if(liveEdge-video.buffered.start(0)>8){
     const trimBefore=Math.max(0,liveEdge-4);
     await updateBuffer(buffer,()=>buffer.remove(0,trimBefore),signal);
    }
   }
   el('metrics').textContent='H.264 NVENC · профиль '+profileName+' · получено '+Math.round(received/1024)+' КБ';
   el('updated').textContent=new Date().toLocaleTimeString('ru-RU');
   setStatus('H.264 видео подключено');
  }
 }finally{
  try{await reader.cancel()}catch(e){}
 }
}
async function h264Loop(){
 if(!canPlayH264()){
  mode='stream';el('mode').value='stream';
  setStatus('Нет поддержки H.264 MSE, переключаюсь на MJPEG');
  startStream();return;
 }
 let failures=0;
 while(active && mode==='h264'){
  try{
   await h264Once();
   if(!active)break;
   failures=0;
   setStatus('Повторное подключение H.264...');
  }catch(error){
   if(!active || mode!=='h264')break;
   failures++;
   if(failures>=2){
    stopH264();
    mode='stream';el('mode').value='stream';
    setStatus('H.264 недоступен, включаю резервный MJPEG');
    startStream();return;
   }
   setStatus('Повтор H.264: '+error.message);
  }finally{
   stopH264();
  }
  if(active && mode==='h264')await pause(2500);
 }
}
el('start').addEventListener('click',()=>{
 if(active)return;active=true;frames=0;transfer=0;
 mode=el('mode').value;
 el('start').disabled=true;el('stop').disabled=false;
 el('device').disabled=true;el('quality').disabled=true;el('mode').disabled=true;
 setStatus('Подключение...');
 if(mode==='h264')h264Loop();
 else if(mode==='stream')startStream();
 else poll().finally(()=>{if(active && mode==='jpeg')stop()});
});
function stop(){
 active=false;
 if(controller)controller.abort();
 stopH264();
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
