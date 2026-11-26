"""Standalone, responsive, authenticated screen-monitoring page."""


def monitor_page():
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Мониторинг экрана | Lunex PC Control</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#0b1018;color:#eff5ff}
.wrap{max-width:1150px;margin:0 auto;padding:25px 18px}
.top{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}
h1{font-size:clamp(25px,4vw,35px);margin:4px 0;letter-spacing:-.8px}
.brand{color:#82d3f4;font-size:12px;letter-spacing:.15em;text-transform:uppercase}
.sub{color:#a4b5c8;font-size:14px;line-height:1.6}
nav{display:flex;gap:8px;margin:23px 0 18px;flex-wrap:wrap}
nav a{text-decoration:none;color:#b5c9de;border:1px solid #2b3e52;padding:10px 17px;border-radius:12px;font-size:14px}
nav a[aria-current=page]{background:#173449;color:#9bdefb;border-color:#317091}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 295px;gap:15px}
.card{background:#141f2d;border:1px solid #293c50;border-radius:18px;padding:18px}
.head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
h2{font-size:17px;margin:4px 0 15px}
.pill{color:#a2cfdf;font-size:12px;border:1px solid #466174;border-radius:25px;padding:7px 12px}
.screen{display:flex;align-items:center;justify-content:center;aspect-ratio:16/9;min-height:175px;
 background:linear-gradient(140deg,#111e2d,#0a111b);border:1px dashed #3a4e64;border-radius:12px;
 overflow:hidden;color:#8fa5b9;text-align:center}
.screen img{width:100%;height:100%;object-fit:contain;display:none}
.screen .placeholder{max-width:300px;padding:15px;font-size:14px;line-height:1.7}
.controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:13px}
button,select{font:inherit}
button{border:1px solid #37627c;background:#17394d;color:#def4ff;padding:10px 15px;border-radius:11px;cursor:pointer}
button:hover{background:#214c65}
button:disabled{opacity:.42;cursor:not-allowed}
.btn-muted{background:transparent;border-color:#3a4d61}
select{width:100%;padding:10px;border-radius:10px;background:#0c1826;color:white;border:1px solid #3a4d61;margin:8px 0 14px}
label{color:#b8cbdd;font-size:13px}
.muted{color:#97a9bd;font-size:12px;line-height:1.6}
#gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px;margin-top:13px}
.thumb{border:1px solid #2b4156;background:#122334;border-radius:12px;overflow:hidden;padding:0;display:block;text-align:left;width:100%}
.thumb img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#070b12;display:block}
.thumb span{display:block;font-size:12px;color:#bdccda;padding:8px 10px}
.status{color:#a9d7a9}.err{color:#ffaeae}
dialog{background:#0c1522;border:1px solid #3d526a;color:white;border-radius:16px;max-width:96vw;max-height:95vh;padding:12px}
dialog::backdrop{background:#000e}
dialog img{display:block;max-width:92vw;max-height:80vh;object-fit:contain;margin:auto}
dialog .controls{justify-content:flex-end}
footer{margin:24px 0;color:#7990a6;font-size:12px}
@media(max-width:800px){.grid{grid-template-columns:1fr}.wrap{padding:17px 12px}}
</style></head><body><div class="wrap">
<div class="top"><div><div class="brand">Lunex • PC Control</div><h1>Мониторинг экрана</h1></div>
<div class="pill">🔒 Приватная история ИИ</div></div>
<nav><a href="/">Обзор</a><a aria-current="page" href="/monitor">Мониторинг экрана</a></nav>
<p class="sub">Снимки появляются автоматически, когда подключённый ИИ использует разрешённый инструмент Screenshot.
Обновление просмотра каждые 3 секунды. Это не непрерывная видеотрансляция.</p>
<div class="grid"><section class="card">
<div class="head"><h2>Последний снимок</h2><span class="pill" id="captureStatus">Проверка...</span></div>
<div class="screen" id="screen"><div class="placeholder" id="placeholder">Снимков пока нет. Запись должна быть включена, а Windows-агент подключён.</div>
<img id="latestImage" alt="Последний снимок рабочего стола ИИ"></div>
<div class="controls">
<button id="fullscreen" type="button" disabled>Во весь экран</button>
<a id="download" style="display:none;color:#87cfff" download="lunexpc-screenshot.png">Скачать PNG</a>
<span class="muted" id="latestTime">Ожидание изображения</span>
</div></section>
<aside class="card"><h2>Настройки записи</h2>
<p class="muted">Хранятся только снимки, полученные ИИ. Данные шифруются на VPS. Объём истории ограничен 64 МБ.</p>
<label for="retention">Срок хранения</label>
<select id="retention"><option value="0">Не сохранять (выключено)</option>
<option value="1">1 час</option><option value="24">24 часа</option><option value="168">7 дней</option></select>
<label for="maxCount">Количество снимков</label>
<select id="maxCount"><option value="1">Только последний</option>
<option value="50">До 50 снимков</option></select>
<button id="saveSettings" type="button">Сохранить настройки</button>
<button id="clear" type="button" class="btn-muted">Очистить историю</button>
<p class="muted" id="settingsStatus" role="status">Настройки хранятся на VPS.</p>
</aside></div>
<section class="card" style="margin-top:15px">
<div class="head"><h2>История скриншотов</h2><span class="pill" id="count">0 снимков</span></div>
<div id="gallery"></div><p id="empty" class="muted">Нет сохранённых снимков.</p></section>
<section class="card" style="margin-top:15px"><h2>Журнал действий ИИ</h2>
<p class="muted">Запросы Screenshot и ControlStatus и их HTTP-статусы. Ввод текста и нажатия мыши
не записываются: эти инструменты пока запрещены шлюзом.</p>
<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">
<thead><tr><th style="text-align:left;padding:9px">Время</th><th>Действие</th><th>Статус</th></tr></thead>
<tbody id="actions"></tbody></table></div></section>
<footer>История доступна только после авторизации. При отключении записи текущая история удаляется.</footer>
</div>
<dialog id="viewer"><div class="controls"><button id="closeViewer" type="button">Закрыть</button></div>
<img id="viewerImage" alt="Снимок рабочего стола в полном размере"></dialog>
<script>
const qs=id=>document.getElementById(id);
let selected="", settingsReady=false;
const formatTime=v=>{try{return new Date(v).toLocaleString('ru-RU')}catch{return v}};
async function fetchJSON(path,options={}){
 const response=await fetch(path,{cache:'no-store',...options});
 if(!response.ok)throw new Error('HTTP '+response.status);
 return response.json();
}
function show(id){
 const url='/api/screens/'+encodeURIComponent(id)+'.png';
 qs('viewerImage').src=url;
 qs('viewer').showModal();
}
function addThumb(item){
 const button=document.createElement('button');
 button.type='button';button.className='thumb';
 const image=document.createElement('img');
 image.src='/api/screens/'+encodeURIComponent(item.id)+'.png';
 image.alt='Скриншот '+formatTime(item.time);image.loading='lazy';
 const span=document.createElement('span');
 span.textContent=formatTime(item.time);
 button.append(image,span);
 button.addEventListener('click',()=>show(item.id));
 qs('gallery').append(button);
}
async function refresh(){
 try{
  const data=await fetchJSON('/api/screens');
  if(!settingsReady){
   qs('retention').value=String(data.settings.retention_hours);
   qs('maxCount').value=String(data.settings.max_count);
   settingsReady=true;
  }
  qs('captureStatus').textContent=data.settings.enabled?'Запись включена':'Запись выключена';
  qs('count').textContent=data.items.length+' снимков';
  const first=data.items[0];
  qs('empty').style.display=data.items.length?'none':'block';
  if(first){
   const url='/api/screens/'+encodeURIComponent(first.id)+'.png';
   if(selected!==first.id){
    selected=first.id;
    qs('latestImage').src=url;
    qs('latestImage').style.display='block';
    qs('placeholder').style.display='none';
    qs('download').href=url;qs('download').style.display='inline';
    qs('fullscreen').disabled=false;
    qs('latestTime').textContent=formatTime(first.time);
   }
  }else{
   selected='';qs('latestImage').removeAttribute('src');
   qs('latestImage').style.display='none';qs('placeholder').style.display='block';
   qs('download').style.display='none';qs('fullscreen').disabled=true;
   qs('latestTime').textContent='Ожидание изображения';
  }
  const ids=data.items.map(x=>x.id).join(',');
  if(qs('gallery').dataset.ids!==ids){
   qs('gallery').replaceChildren();data.items.forEach(addThumb);
   qs('gallery').dataset.ids=ids;
  }
 }catch(err){qs('captureStatus').textContent='Нет соединения';qs('captureStatus').className='pill err'}
}
async function action(path,payload,tag){
 qs('settingsStatus').textContent='Применение...';
 try{
  const data=await fetchJSON(path,{method:'POST',headers:{
   'Content-Type':'application/json','X-LunexPC-Action':tag
  },body:JSON.stringify(payload)});
  qs('settingsStatus').textContent='Сохранено';
  settingsReady=false;
  await refresh();
 }catch(e){qs('settingsStatus').textContent='Ошибка изменения: '+e.message}
}
qs('saveSettings').addEventListener('click',()=>action('/api/screens/settings',{
 retention_hours:Number(qs('retention').value),
 max_count:Number(qs('maxCount').value)},'screens-settings'));
qs('clear').addEventListener('click',()=>{
 if(confirm('Удалить все сохранённые снимки экрана?')){
  action('/api/screens/clear',{},'screens-clear');
 }
});
async function refreshActions(){
 try{
  const status=await fetchJSON('/api/status');
  const table=qs('actions');table.replaceChildren();
  const records=(status.audit||[]).filter(e=>e.method==='call_screenshot'||e.method==='call_status');
  for(const entry of records.slice().reverse().slice(0,15)){
   const tr=table.insertRow();
   for(const value of [formatTime(entry.time),entry.method==='call_screenshot'?'Снимок экрана':'Состояние управления',entry.status]){
    const td=tr.insertCell();td.style.padding='9px';td.style.borderBottom='1px solid #2b3e52';td.textContent=String(value);
   }
  }
  if(!records.length){const tr=table.insertRow();const td=tr.insertCell();td.colSpan=3;td.textContent='Нет событий';}
 }catch(e){qs('actions').textContent='Журнал недоступен'}
}
qs('fullscreen').addEventListener('click',()=>{if(selected)show(selected)});
qs('closeViewer').addEventListener('click',()=>qs('viewer').close());
refresh();refreshActions();setInterval(refresh,3000);setInterval(refreshActions,10000);
</script></body></html>""".encode("utf-8")
