// Provino - logica dell'interfaccia
"use strict";
const $ = s => document.querySelector(s);
const post = (u,b)=>fetch(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)}).then(r=>r.json());

let S = null, CAMS = null, filter = "both", picked = new Set(), built = false, metaShown = null;
let LANG = "it";
let cur = null;   // scatto mostrato nell'anteprima grande
let META = {}, metaN = -1, filmFilter = "", pendingKey = "", multiSlot = false;   // metadati per scatto (ricetta), filtro per pellicola

// ---------------------------------------------------------------- testi
function t(key, vars){
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if(vars) for(const k in vars) s = s.split("{"+k+"}").join(vars[k]);
  return s.replace(/\{([A-Z_]+)\}/g, (m,k)=> CAMS && CAMS.menus[k] ? M(k) : m);
}
function applyStatic(){
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el=>el.textContent = t(el.dataset.i18n));
  document.querySelectorAll("[data-i18n-html]").forEach(el=>el.innerHTML = t(el.dataset.i18nHtml));
  document.querySelectorAll("[data-i18n-aria]").forEach(el=>el.setAttribute("aria-label", t(el.dataset.i18nAria)));
  document.querySelectorAll("[data-i18n-title]").forEach(el=>el.title = t(el.dataset.i18nTitle));
}
function esc(v){ return String(v).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function fmtSize(b){ if(!b) return ""; const mb=b/1048576; return mb>=1? (mb.toFixed(mb>=10?0:1)+" MB").replace(".", LANG==="it"?",":".") : Math.round(b/1024)+" KB"; }
function fmtNum(n){ return Number(n).toLocaleString(LANG==="it"?"it-IT":"en-US"); }
function fmtDay(d){ // "20261031T131930" -> "31 ott 2026" / "Oct 31, 2026"
  if(!d || d.length<8) return "";
  const y=d.slice(0,4), m=+d.slice(4,6), dd=+d.slice(6,8), mo=DATE_MONTHS[LANG][m-1];
  return LANG==="it" ? `${dd} ${mo} ${y}` : `${mo} ${dd}, ${y}`;
}
function fmtTime(d){ return d && d.length>=13 ? d.slice(9,11)+":"+d.slice(11,13) : ""; }

// nomi dei menu della fotocamera nella lingua usata sulla fotocamera
function camLang(){ const c=(S.choice||{}).camera || (wiz&&wiz.camera) || "X-Pro3"; return ((S.settings||{}).menu_lang||{})[c] || LANG; }
function M(k){
  const m = CAMS.menus[k]; if(!m) return k;
  const l = camLang();
  if(l!=="it") return `<span class="mn">${m.en}</span>`;
  return m.it_verified ? `<span class="mn">${m.it}</span>` : `<span class="mn">${m.it}</span> <span class="mnen">(${m.en})</span>`;
}
function loc(o){ return o ? (o[LANG] || o.en || o.it) : ""; }
function serverMsg(){
  if(!S.message_key) return "";
  return t("msg."+S.message_key, S.message_params||{});
}

// ---------------------------------------------------------------- dati
function groups(){
  const m = new Map();
  for(const f of S.files){ if(!m.has(f.base)) m.set(f.base,{base:f.base,date:f.date,files:{}}); m.get(f.base).files[f.kind]=f; }
  return [...m.values()];
}
function thumbHandle(g){
  const ready = new Set(S.thumbs_ready);
  const hit = Object.values(g.files).find(f=>ready.has(f.handle));
  return (hit || g.files.JPG || g.files.RAF || Object.values(g.files)[0]).handle;
}
const VIDEO = ["MOV","MP4"];
// icona di una scheda SD (angolo tagliato) con il numero dello slot
function sdIcon(n){
  return `<span class="sd" title="${esc(t("s.slot")+" "+t("slot.n",{n}))}" aria-label="SD ${n}"><svg viewBox="0 0 14 18" aria-hidden="true"><path d="M1.5 1h7.5l3.5 3.5v11.5a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1v-14a1 1 0 0 1 1-1z"/></svg><b>${n}</b></span>`;
}
function slotOf(g){ const sl=[...new Set(Object.values(g.files).map(f=>f.slot).filter(n=>n===1||n===2))].sort(); return sl.join("+"); }
function isVideo(g){ return !g.files.JPG && !g.files.RAF && !g.files.HIF; }
function wanted(g){
  if(filmFilter && ((META[g.base]||{}).film||"") !== filmFilter) return [];
  return Object.values(g.files).filter(f => filter==="both" || f.kind===filter || (filter==="VIDEO" && VIDEO.includes(f.kind)));
}

// ---------------------------------------------------------------- schermate di stato
let noticeKey = "";
function notice(title, text, busy, action, extra){
  $("#bar").hidden = !S || !S.files.length || S.status!=="ready";
  const key = [LANG,title,text,busy,action,extra].join("|");
  built = false;
  if(key===noticeKey) return;   // non ridisegnare: le spunte restano
  noticeKey = key;
  $("#main").innerHTML = `<section class="notice"><h1>${busy?'<span class="pulse"></span>':''}${title}</h1>${text?`<p>${text}</p>`:""}${extra||""}${action||""}</section>`;
}

function stepsFor(){
  const c = (S.choice||{}), cam = CAMS.cameras[c.camera] || {};
  const own = (cam.steps||{})[c.method];
  const list = (own || CAMS.default_steps[c.method] || []).map(s=>loc(s));
  if(c.method==="cable" && S.status==="cable")
    return list.concat([[t("cable.ic1"), t("cable.ic1.d",{cam:c.camera})],[t("cable.ic2"), t("cable.ic2.d")]]);
  return list;
}
const ticked = new Set();
function checklist(found){
  const c = S.choice||{}, key = (c.camera||"")+"/"+(c.method||"");
  const list = stepsFor();
  let html = '<ol class="steps">';
  list.forEach((st,i)=>{
    const id = key+i, on = found || ticked.has(id);
    html += `<li class="${on?'done':''}"><label><input type="checkbox" data-step="${id}" ${on?'checked':''}><span class="txt"><b>${t(st[0])}</b>${st[1]?`<small>${t(st[1])}</small>`:""}</span></label></li>`;
  });
  if(c.method==="cable" && S.status==="cable") return html + '</ol>';
  html += `<li class="auto ${found?'done':''}"><label>${found?'<input type="checkbox" checked disabled>':'<span class="spin"></span>'}<span class="txt"><b>${t(found?"auto.found":"auto.wait")}</b><small>${t(found?"auto.found.d":"auto.wait.d")}</small></span></label></li>`;
  const tip = (c.method==="cable" || c.method==="card") ? "" : `<p class="tip">${t(loc(CAMS.default_steps.tip))}</p>`;
  return html + `</ol>${tip}`;
}
document.addEventListener("change", e=>{
  const c = e.target.closest("input[data-step]"); if(!c) return;
  c.checked ? ticked.add(c.dataset.step) : ticked.delete(c.dataset.step);
  c.closest("li").classList.toggle("done", c.checked);
});

// ---------------------------------------------------------------- griglia (provino)
function build(){
  $("#bar").hidden = false;
  applyStatic();
  const gs = groups();
  const cm = S.camera_meta||{}, parts = [];
  if(cm.firmware) parts.push(t("meta.fw",{v:cm.firmware}));
  if(cm.serial) parts.push(t("meta.serial",{v:cm.serial})); else if(cm.internal_serial) parts.push(t("meta.internal",{v:cm.internal_serial}));
  const isCardSrc = (S.choice||{}).method==="card";
  // lettore di schede: il titolo e' la sorgente; la fotocamera che ha scattato va nella riga accanto
  const models = S.card_models||[];
  if(isCardSrc && models.length>1){ parts.length = 0; parts.push(t("card.fromN",{v:S.card||"", n:models.length, list:models.join(", ")})); }
  else if(isCardSrc) parts.unshift(t("card.from",{cam:S.camera, v:S.card||""}));
  $("#camMeta").textContent = parts.join(", ");
  $("#camMeta").title = cm.from ? t("meta.from",{f:cm.from}) : "";
  $("#camName").textContent = isCardSrc ? t("method.card") : S.camera;
  $("#camName").title = S.camera_id || "";
  const nRaf = S.files.filter(f=>f.kind==="RAF").length;
  const nVid = gs.filter(isVideo).length;
  const slots = new Set(S.files.map(f=>f.slot).filter(n=>n===1||n===2));
  multiSlot = slots.size > 1;
  document.querySelectorAll("[data-f=VIDEO],[data-all=VIDEO]").forEach(b=>b.hidden = !nVid);
  const method = (S.choice||{}).method;
  $("#camInfo").textContent = (S.camera_id? S.camera_id+". " : "") + t(multiSlot? "info.shots2" : "info.shots",{n:gs.length-nVid}) + (nRaf? t("info.withRaf",{n:nRaf}) : "") + (nVid? t("info.videos",{n:nVid}) : "")
    + (method==="cable" ? t("info.cable") : method==="card" ? "" : method==="direct" ? t("info.direct") : (!S.previews ? t("info.number") : ""));
  let html = "", lastDay = "";
  for(const g of gs){
    const day = fmtDay(g.date);
    if(day!==lastDay){ html += `<h2 class="day">${day}</h2>`; lastDay = day; }
    const kinds = ["JPG","RAF"].filter(k=>g.files[k]).concat(Object.keys(g.files).filter(k=>k!=="JPG"&&k!=="RAF"));
    const vid = isVideo(g);
    // solo HEIF e il sistema non sa mostrarlo (Linux senza libheif): segnaposto invece della rotella infinita
    const heifOnly = !vid && !g.files.JPG && !g.files.RAF && g.files.HIF && !S.heif_preview;
    html += `<div class="frame${vid||heifOnly?" video":""}" data-b="${esc(g.base)}">
      <div class="dtag"></div><div class="pic"><button class="photo" data-b="${esc(g.base)}" aria-label="${esc(t("select.photo",{name:g.base}))}">${vid? `<span class="vid" aria-hidden="true">▶</span><span class="vidl">${t("video")}</span>` : heifOnly? `<span class="vid" aria-hidden="true">HEIF</span><span class="vidl">${t("heif.nopreview")}</span>` : `<span class="wait"></span>`}</button>
      <svg class="mark" viewBox="0 0 100 70" preserveAspectRatio="none" aria-hidden="true"><rect x="3" y="3" width="94" height="64" rx="4" transform="rotate(-.6 50 35)"/></svg></div>
      <div class="cap"><span class="n">${esc(g.base.replace(/^_/,""))}</span><span class="t">${slotOf(g)? slotOf(g).split("+").map(n=>sdIcon(n)).join("")+" " : ""}${fmtTime(g.date)}</span><span class="film"></span></div>
      <div class="kinds">${kinds.map(k=>`<button class="kind" data-h="${g.files[k].handle}" aria-pressed="false">${k}${g.files[k].size? " "+fmtSize(g.files[k].size):""}</button>`).join("")}${vid? "" : `<button class="kind meta" data-meta="${esc(g.base)}">META</button>`}</div>
    </div>`;
  }
  $("#main").innerHTML = `<section class="sheet"><p class="nomatch" id="nomatch" hidden></p>${html}</section>`;
  built = true;
  noticeKey = "";   // la griglia ha sostituito l'avviso: il prossimo avviso (anche identico) va ridisegnato
  filmOptions();
  paint();
}

function hideEmptyDays(){
  // le foto scorrono una dopo l'altra senza andare a capo a ogni giorno (niente spazio sprecato):
  // la data compare sopra la prima foto visibile di ogni giorno
  for(const h of document.querySelectorAll(".sheet h2.day")){
    let el = h.nextElementSibling, first = null;
    while(el && !el.matches("h2.day")){
      if(el.classList.contains("frame")){
        const tag = el.querySelector(".dtag");
        if(!first && !el.hidden){ first = el; tag.textContent = h.textContent; el.classList.add("dfirst"); }
        else { tag.textContent = ""; el.classList.remove("dfirst"); }
      }
      el = el.nextElementSibling;
    }
    h.hidden = !first;
  }
}
function paint(){
  setTimeout(nativeState, 0);
  if(S.camera_meta && S.camera_meta.from && metaShown !== S.camera_meta.from) { metaShown = S.camera_meta.from; built=false; return build(); }
  const ready = new Set(S.thumbs_ready);
  const gm = new Map(groups().map(g=>[g.base,g]));
  const fm = new Map(S.files.map(f=>[f.handle,f]));
  for(const fr of document.querySelectorAll(".frame")){
    const g = gm.get(fr.dataset.b); if(!g) continue;
    const th = thumbHandle(g), ph = fr.querySelector(".photo");
    if(ready.has(th) && !fr.classList.contains("video") && !ph.querySelector("img")){ ph.innerHTML = `<img alt="" src="/api/thumb/${th}?b=${encodeURIComponent(g.base)}&z=${(g.files.JPG||g.files.RAF||{}).size||0}" onload="this.dataset.ld=1;orient(this)">`; }
    const im = ph.querySelector("img"); if(im && im.dataset.ld) orient(im);
    else if(!S.previews && !ph.querySelector("img") && !ph.querySelector(".nopv")){ ph.innerHTML = `<span class="nopv"><b>${esc(g.base.replace(/^\D+/,""))}</b><small>${fmtTime(g.date)}</small></span>`; }
    let any=false;
    for(const k of fr.querySelectorAll(".kind:not(.meta)")){
      const h = +k.dataset.h, f = fm.get(h);
      k.setAttribute("aria-pressed", picked.has(h));
      k.classList.toggle("onmac", !!(f && f.on_mac));
      any = any || picked.has(h);
    }
    fr.classList.toggle("sel", any);
    fr.classList.toggle("cur", fr.dataset.b===cur);
    const fm2 = META[g.base], fc = fr.querySelector(".film");
    if(fc){ const txt = fm2 && fm2.film ? filmName(fm2.film) : ""; if(fc.textContent!==txt) fc.textContent = txt; }
    fr.hidden = wanted(g).length===0;
    for(const k of fr.querySelectorAll(".kind:not(.meta)")){ const f = fm.get(+k.dataset.h); k.hidden = filter!=="both" && f && f.kind!==filter; }
  }
  hideEmptyDays();
  const nm = $("#nomatch");
  if(nm){ const none = !document.querySelector(".frame:not([hidden])"); nm.hidden = !none;
    if(none) nm.textContent = t(filmFilter ? "nomatch.film" : "nomatch.kind", {kind: filter, film: filmName(filmFilter)}); }
  viewerPaint();
  const n = picked.size;
  $("#go").disabled = n===0;
  let bytes = 0, known = true;
  for(const h of picked){ const f = fm.get(h); if(f && f.size) bytes += f.size; else known = false; }
  const speed = (S.choice||{}).method==="card" ? 40 : (S.choice||{}).method==="cable" ? 20 : 1.1;   // MB/s indicativi
  const secs = bytes / (speed*1048576);
  const eta = secs < 90 ? t("dl.eta.s",{n:Math.max(1,Math.round(secs))}) : t("dl.eta.m",{n:Math.round(secs/60)});
  const shown = new Set(); for(const g of groups()) for(const f of wanted(g)) shown.add(f.handle);
  const hid = [...picked].filter(h=>!shown.has(h)).length;
  const hidTxt = hid ? t(hid===1? "dl.hidden1" : "dl.hidden", {n:hid}) : "";
  const small = [known&&bytes? `${fmtSize(bytes)}, ${eta}` : "", hidTxt].filter(Boolean).join(" · ");
  $("#go").innerHTML = n? `${t("dl.btnN",{n})}${small? `<small>${small}</small>`:""}` : t("dl.btn");
  $("#go").title = hid ? t("dl.hidden.title") : "";
}

function setFilter(f){
  filter = f;
  document.querySelectorAll(".fmtseg button").forEach(b=>b.setAttribute("aria-pressed", b.dataset.f===f));
}
function toggleGroup(base){
  const g = groups().find(x=>x.base===base); if(!g) return;
  const hs = wanted(g).map(f=>f.handle);
  const allOn = hs.length && hs.every(h=>picked.has(h));
  for(const f of Object.values(g.files)) picked.delete(f.handle);
  if(!allOn) hs.forEach(h=>picked.add(h));
  paint();
}
function selectAll(kind){
  picked.clear();
  if(filter!=="both" && kind!==filter) setFilter(kind==="both"? "both" : kind);
  for(const f of S.files)
    if(kind==="both" ? (f.kind==="JPG"||f.kind==="RAF") : kind==="VIDEO" ? VIDEO.includes(f.kind) : f.kind===kind) picked.add(f.handle);
  paint();
}

let anchor = null, kAnchor = null, suppressClick = false;
document.addEventListener("click", e=>{
  const mc = e.target.closest("[data-meta]");
  if(mc){ openMeta(mc.dataset.meta); return; }
  const k = e.target.closest(".kind");
  if(k){
    // selezione per il download: si fa sulle etichette JPG / RAF (Maiusc+clic = una serie dello stesso tipo)
    const h=+k.dataset.h, f=S.files.find(x=>x.handle===h), base=k.closest(".frame").dataset.b;
    const order = groups().filter(g=>wanted(g).length).map(g=>g.base);
    if(e.shiftKey && kAnchor && f && order.includes(kAnchor)){
      const a=order.indexOf(kAnchor), b=order.indexOf(base), [lo,hi]=a<b?[a,b]:[b,a];
      for(const bs of order.slice(lo,hi+1)){ const g=groups().find(x=>x.base===bs); const x=g&&g.files[f.kind]; if(x) picked.add(x.handle); }
    } else picked.has(h)?picked.delete(h):picked.add(h);
    kAnchor = base; paint(); return; }
  const p = e.target.closest(".photo");
  if(p){
    // clic sulla foto = guardarla accanto alla griglia (apre la vista divisa); doppio clic = schermo intero.
    // Su una finestra stretta, dove la vista divisa non c'e', il clic apre lo schermo intero.
    if(suppressClick){ suppressClick=false; return; }
    setCur(p.dataset.b);
    if(!split && innerWidth > 900){ split = true; layout(); loadBig(); }
    else if(!splitActive()) openFull();
    return; }
  const all = e.target.closest("[data-all]");
  if(all){ selectAll(all.dataset.all); return; }
  const sb = e.target.closest(".fmtseg button");
  // il filtro cambia solo cosa si vede: le scelte restano (quelle nascoste si contano accanto a Scarica)
  if(sb){ setFilter(sb.dataset.f); paint(); return; }
});
document.addEventListener("keydown", e=>{
  if(!S || S.status!=="ready" || document.querySelector("dialog[open]")) return;
  if(e.target.closest && e.target.closest("input,textarea,select")) return;
  if(viewerKey(e)) return;
  if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==="a"){ e.preventDefault(); for(const g of groups()) wanted(g).forEach(f=>picked.add(f.handle)); paint(); }
  if(e.key==="Escape"){ picked.clear(); paint(); }
});
// selezione con riquadro
let drag = null;
document.addEventListener("mousedown", e=>{
  if(e.button!==0 || !e.target.closest(".sheet") || e.target.closest(".kind")) return;
  e.preventDefault();
  drag = {x:e.clientX, y:e.clientY, base:new Set(picked), add:e.shiftKey||e.metaKey||e.ctrlKey, moved:false};
});
document.addEventListener("dragstart", e=>{ if(e.target.closest && e.target.closest(".sheet")) e.preventDefault(); });
document.addEventListener("mousemove", e=>{
  if(!drag) return;
  const dx = e.clientX-drag.x, dy = e.clientY-drag.y;
  if(!drag.moved && Math.hypot(dx,dy) < 6) return;
  drag.moved = true;
  const L=Math.min(e.clientX,drag.x), T=Math.min(e.clientY,drag.y), W=Math.abs(dx), H=Math.abs(dy);
  const band = $("#band"); band.hidden=false; Object.assign(band.style,{left:L+"px",top:T+"px",width:W+"px",height:H+"px"});
  picked = drag.add? new Set(drag.base) : new Set();
  for(const fr of document.querySelectorAll(".frame")){
    const r = fr.querySelector(".photo").getBoundingClientRect();
    if(r.right>L && r.left<L+W && r.bottom>T && r.top<T+H){ const g = groups().find(x=>x.base===fr.dataset.b); if(g) wanted(g).forEach(f=>picked.add(f.handle)); }
  }
  paint();
});
document.addEventListener("mouseup", ()=>{
  if(drag && drag.moved){ suppressClick = true; setTimeout(()=>suppressClick=false, 50); }
  drag = null; $("#band").hidden = true;
});
$("#selNew").onclick = ()=>{ picked.clear(); for(const g of groups()) for(const f of wanted(g)) if(!f.on_mac) picked.add(f.handle); paint(); };
$("#selNone").onclick = ()=>{ picked.clear(); paint(); };

// ---------------------------------------------------------------- download
async function startDownload(hs, options){
  batchBase = S.done.length; failBase = S.failed.length; trayClosedAt = -1; dlPending = true; tray();
  const r = await post("/api/download",{handles:hs, options});
  if(!(r && r.queued)){ dlPending = false; trayClosedAt = S.done.length + S.failed.length; tray(); }
  picked.clear(); paint(); poll();
}
$("#go").onclick = ()=>{ const hs=[...picked]; if(hs.length) askDest(hs); };

function askDest(hs){
  if(NATIVE){
    const st = S.settings||{};
    const sel = S.files.filter(f=>hs.includes(f.handle));
    const bytes = sel.reduce((a,f)=>a+(f.size||0),0);
    const kinds = {}; for(const f of sel){ const k = VIDEO.includes(f.kind)? "VIDEO" : f.kind==="HIF"? "HEIF" : f.kind; kinds[k]=(kinds[k]||0)+1; }
    const days = [...new Set(sel.map(f=>(f.date||"").slice(0,8)).filter(Boolean))].sort();
    nativeMsg({type:"askDest", hs, n:hs.length, size:fmtSize(bytes), kinds, days,
      files: sel.slice(0,400).map(f=>[f.name, (f.date||"").slice(0,8), VIDEO.includes(f.kind)? "VIDEO" : f.kind==="HIF"? "HEIF" : f.kind]),
      dest:S.dest, by_date:!!st.by_date, split_type:!!st.split_type});
    return;
  }
  const st = S.settings||{}, d = $("#dest");
  // cartella scelta in questa finestra: tenuta qui, perche' S viene riletto dal programma ogni secondo
  let dest = S.dest;
  const sample = S.files.find(f=>hs.includes(f.handle) && f.kind==="RAF") || S.files.find(f=>hs.includes(f.handle)) || {};
  $("#destPath").textContent = S.dest;
  $("#destSplit").checked = !!st.split_type;
  d.querySelector(`input[name=org][value=${st.by_date?"date":"single"}]`).checked = true;
  const nDays = new Set(S.files.filter(f=>hs.includes(f.handle)).map(f=>(f.date||"").slice(0,8))).size;
  const vid = S.files.find(f=>hs.includes(f.handle) && VIDEO.includes(f.kind));
  function preview(){
    const lab = d.querySelector("[data-i18n-html='dest.split']");
    if(lab) lab.innerHTML = splitLabel(hs);
    const parts = [dest.replace(/^\/(Users|home)\/[^/]+/,"~")];
    const dt = (sample.date||"").slice(0,8);
    const byDate = d.querySelector("input[name=org]:checked").value==="date";
    if(byDate && dt.length===8) parts.push(`${dt.slice(0,4)}-${dt.slice(4,6)}-${dt.slice(6,8)}`);
    if($("#destSplit").checked) parts.push(sample.kind==="HIF" ? "HEIF" : VIDEO.includes(sample.kind) ? "VIDEO" : (sample.kind||"RAF"));
    parts.push(sample.name||"DSCF0001.RAF");
    let txt = parts.join("/");
    if(vid && sample.handle!==vid.handle){
      const vp = [dest.replace(/^\/(Users|home)\/[^/]+/,"~")];
      const vd = (vid.date||"").slice(0,8);
      if(byDate && vd.length===8) vp.push(`${vd.slice(0,4)}-${vd.slice(4,6)}-${vd.slice(6,8)}`);
      if($("#destSplit").checked) vp.push("VIDEO");
      vp.push(vid.name); txt += "\n" + vp.join("/");
    }
    $("#destPrev").textContent = txt; $("#destPrev").style.whiteSpace = "pre-line";
    $("#destDays").textContent = byDate && nDays>1 ? t("dest.days",{n:nDays}) : "";
  }
  preview();
  d.querySelectorAll("input").forEach(i=>i.onchange=preview);
  $("#destPick").onclick = async ()=>{
    $("#destPick").disabled = true; $("#destPick").textContent = t("dest.picking");
    const r = await post("/api/choose-folder", {});
    $("#destPick").disabled = false; $("#destPick").textContent = t("dest.pick");
    if(r.path){ dest = r.path; $("#destPath").textContent = r.path; preview(); }
  };
  $("#destCancel").onclick = ()=>d.close();
  $("#destForm").onsubmit = async ev=>{
    ev.preventDefault();
    const r = await post("/api/dest-settings", {dest: dest, split_type: $("#destSplit").checked,
                       by_date: d.querySelector("input[name=org]:checked").value==="date"});
    if(r.error){ $("#destErr").textContent = r.error; return; }
    S.settings = r.settings; S.dest = r.dest;
    d.close();
    afterDest(hs);
  };
  $("#destErr").textContent = "";
  d.showModal();
}

async function afterDest(hs){
  const {conflicts} = await post("/api/check",{handles:hs});
  if(!conflicts.length) return startDownload(hs, {});
  const same = conflicts.filter(c=>c.kind==="same"), diff = conflicts.filter(c=>c.kind!=="same");
  const others = hs.length-conflicts.length;
  if(NATIVE){
    // la finestra nativa disegna la scelta; i testi (gia' tradotti) arrivano da qui, una sola fonte per GNOME e Mac
    nativeMsg({type:"conflicts", hs,
      title: conflicts.length===1 ? t("conf.title1") : t("conf.titleN",{n:conflicts.length}),
      sub: t(others? (others===1?"conf.sub1":"conf.sub") : "conf.sub0",{n:others}),
      items: [...same, ...diff].map(c=>({h:c.handle, name:c.name, same:c.kind==="same", proposed:c.proposed||"",
        why: c.kind==="same"
          ? t("conf.same",{size:fmtSize(c.cam_size)}) + (c.local_date? t("conf.sameDate",{date:fmtDay(c.local_date)+" "+fmtTime(c.local_date)}) : "") + "."
          : t("conf.diff") + (c.local_date? t("conf.diffDetail",{ld:fmtDay(c.local_date)+" "+fmtTime(c.local_date), ls:fmtSize(c.local_size), cd:fmtDay(c.cam_date)+" "+fmtTime(c.cam_date), cs:c.cam_size?", "+fmtSize(c.cam_size):""}) : "") + "."})),
      labels: {skip:t("conf.skip"), over:t("conf.over"), saveAs:t("conf.saveAs"), ok:t("dl.btn"), cancel:t("cancel"),
               nothing:t("conf.nothing"), skipAll:t("conf.skip"), overAll:t("conf.over"), sameAll:t("conf.sameAll",{n:same.length}), newName:t("conf.newName")},
      others});
    return;
  }
  let h = `<p class="sub">${t(others? (others===1?"conf.sub1":"conf.sub") : "conf.sub0",{n:others})}</p>`;
  if(same.length>1) h += `<div class="all"><button type="button" class="quiet2" data-bulk="skip">${t("conf.skipAll")}</button><button type="button" class="quiet2" data-bulk="overwrite">${t("conf.overAll")}</button></div>`;
  for(const c of same) h += `<div class="conf" data-h="${c.handle}">
      <div class="fn">${esc(c.name)}</div>
      <div class="why">${t("conf.same",{size:fmtSize(c.cam_size)})}${c.local_date?t("conf.sameDate",{date:esc(fmtDay(c.local_date)+" "+fmtTime(c.local_date))}):""}.</div>
      <div class="opts"><label><input type="radio" name="a${c.handle}" value="skip" checked> ${t("conf.skip")}</label>
      <label><input type="radio" name="a${c.handle}" value="overwrite"> ${t("conf.over")}</label></div></div>`;
  for(const c of diff) h += `<div class="conf" data-h="${c.handle}">
      <div class="fn">${esc(c.name)}</div>
      <div class="why">${t("conf.diff")}${c.local_date?t("conf.diffDetail",{ld:esc(fmtDay(c.local_date)+" "+fmtTime(c.local_date)), ls:fmtSize(c.local_size), cd:esc(fmtDay(c.cam_date)+" "+fmtTime(c.cam_date)), cs:c.cam_size?", "+fmtSize(c.cam_size):""}):""}.</div>
      <div class="opts"><label><input type="radio" name="a${c.handle}" value="rename" checked> ${t("conf.saveAs")} <input type="text" name="n${c.handle}" value="${esc(c.proposed)}" aria-label="${esc(t("conf.newName"))}"></label>
      <label><input type="radio" name="a${c.handle}" value="skip"> ${t("conf.skip")}</label></div></div>`;
  $("#dlgBody").innerHTML = h;
  $("#dlgTitle").textContent = conflicts.length===1 ? t("conf.title1") : t("conf.titleN",{n:conflicts.length});
  const d = $("#dlg"); d.showModal();
  d.querySelectorAll("[data-bulk]").forEach(b=>b.onclick=()=>{ for(const c of same){ const r=d.querySelector(`input[name=a${c.handle}][value=${b.dataset.bulk}]`); if(r) r.checked=true; } });
  d.querySelectorAll("input[type=text]").forEach(x=>x.addEventListener("focus",()=>{ const r=x.closest(".opts").querySelector("input[value=rename]"); if(r) r.checked=true; }));
  // se per tutti i file la scelta e' "Non scaricare", il pulsante dice "Chiudi": nessun dubbio su cosa succede
  const okLabel = ()=>{ const all = conflicts.every(c=>(d.querySelector(`input[name=a${c.handle}]:checked`)||{}).value==="skip");
    $("#dlgOk").textContent = all && others===0 ? t("conf.nothing") : t("dl.btn"); };
  d.querySelectorAll("input[type=radio]").forEach(r=>r.addEventListener("change", okLabel));
  d.querySelectorAll("[data-bulk]").forEach(b=>b.addEventListener("click", okLabel));
  okLabel();
  $("#dlgCancel").onclick = ()=>d.close("cancel");
  $("#dlgForm").onsubmit = (ev)=>{
    ev.preventDefault();
    const options = {};
    for(const c of conflicts){
      const act = (d.querySelector(`input[name=a${c.handle}]:checked`)||{}).value || "skip";
      options[c.handle] = {action: act, name: act==="rename" ? d.querySelector(`input[name=n${c.handle}]`).value : undefined};
    }
    d.close("ok");
    startDownload(hs, options);
  };
}
$("#cancel").onclick = ()=>fetch("/api/cancel",{method:"POST"});
$("#openDir").onclick = ()=>fetch("/api/open-folder",{method:"POST"});

let trayClosedAt = -1, batchBase = 0, failBase = 0, dlPending = false;
function tray(){
  const tr=$("#tray"), c=S.current, q=S.queue.length;
  const set = (mode, name, info, pct)=>{
    tr.dataset.mode = mode;
    $("#trName").textContent = name; $("#trInfo").textContent = info;
    $("#trBar").style.width = (pct||0)+"%";
    $("#cancel").hidden = mode!=="run"; $("#trClose").hidden = mode==="run";
    $("#trIcon").textContent = mode==="ok" ? "✓" : mode==="warn" ? "!" : "";
    if(NATIVE){ nativeTransfer({mode, name, info, pct:pct||0, n:S.done.length+S.failed.length,
                                cancel:t("cancel"), open:t("tray.openDir")}); return; }
    tr.classList.add("show");
  };
  if(c || S.done.length > batchBase || S.failed.length > failBase) dlPending = false;
  if(!c && (dlPending || S.queue.length)){
    set("run", t("tray.start"), "", 0);
  } else if(!c && S.pending_n){
    set("warn", t("tray.interrupted",{n:S.pending_n}), t(S.status==="ready" ? "tray.interrupted.go" : "tray.interrupted.wait"));
  } else if(c){
    trayClosedAt = -1;
    const pct = c.total? Math.round(100*c.got/c.total):0;
    const left = c.speed? Math.round((c.total-c.got)/c.speed):null;
    set("run", `${c.name}  ${pct}%`, t("tray.of",{a:fmtSize(c.got), b:fmtSize(c.total), speed:(c.speed/1048576).toFixed(1)}) + (left!==null? t("tray.left",{n:left}):"") + (q? t("tray.queue",{n:q}):""), pct);
  } else if((S.done.length || S.failed.length) && trayClosedAt !== S.done.length + S.failed.length){
    // download finiti: riquadro di riepilogo con "Apri cartella" al posto della barra
    const n = Math.max(0, S.done.length - batchBase), last = S.done[S.done.length-1];
    const dir = last && last.path ? last.path.replace(/\/[^/]+$/,"").replace(/^\/(Users|home)\/[^/]+/,"~") : S.dest;
    const fl = S.failed.length;
    set(fl? "warn" : "ok",
        fl? t("tray.doneFail",{n, f:fl}) : (n===1? t("tray.done1") : t("tray.done",{n})),
        fl? S.failed[fl-1].name+": "+S.failed[fl-1].error : t("tray.where",{dir}));
  } else { tr.classList.remove("show"); if(NATIVE) nativeTransfer({mode:"none"}); }
}
let nativeTrKey = "";
function nativeTransfer(o){
  const k = JSON.stringify({type:"transfer", ...o});
  if(k===nativeTrKey) return;
  nativeTrKey = k; nativeMsg(JSON.parse(k));
}
$("#trClose").onclick = ()=>{ trayClosedAt = S.done.length + S.failed.length; $("#tray").classList.remove("show"); };

// ---------------------------------------------------------------- scelta iniziale
let wiz = null, xaRunning = "", xaChecked = 0;
function checkXA(){
  if(Date.now()-xaChecked < 3000) return; xaChecked = Date.now();
  post("/api/xacquire", {}).then(r=>{ if(r.running!==xaRunning){ xaRunning=r.running; noticeKey=""; render(); } });
}
function langSeg(attr, current, label){
  return `<div class="seg" role="group" aria-label="${esc(label)}">${Object.entries(LANGS).map(([k,v])=>`<button ${attr}="${k}" aria-pressed="${current===k}">${v}</button>`).join("")}</div>`;
}
function wizard(){
  const names = Object.keys(CAMS.cameras);
  if(!wiz){ const st=S.settings||{}; wiz = {camera: CAMS.cameras[st.camera]? st.camera : names[0], method: st.method}; }
  const cam = CAMS.cameras[wiz.camera];
  // il cavo c'e' su macOS (ImageCaptureCore) e su Linux (libgphoto2); su Windows arrivera' dopo
  const methods = cam.methods.filter(m => m!=="cable" || !S.platform || S.platform==="darwin" || S.platform.startsWith("linux"));
  if(!methods.includes(wiz.method)) wiz.method = methods[0];
  let h = `<div class="pick" role="radiogroup" aria-label="${esc(t("wiz.title"))}">`;
  for(const c of names) h += `<button class="opt ${wiz.camera===c?'on':''}" role="radio" aria-checked="${wiz.camera===c}" data-cam="${esc(c)}"><b>${esc(CAMS.cameras[c].label? loc(CAMS.cameras[c].label) : c)}</b></button>`;
  const ml = ((S.settings||{}).menu_lang||{})[wiz.camera] || LANG;
  const camLabel = cam.label? loc(cam.label) : wiz.camera;
  h += `</div>`;
  if(cam.methods.some(m=>m!=="card")) h += `<div class="langrow"><span class="lbl">${t("wiz.menuLang",{cam:esc(camLabel)})}</span>${langSeg("data-ml", ml, t("wiz.menuLang",{cam:camLabel}))}</div>`;
  else if(cam.note) h += `<p class="tip">${esc(loc(cam.note))}</p>`;
  const onlyCard = cam.methods.length===1 && cam.methods[0]==="card";   // "Lettore di schede": niente da scegliere
  h += `<h2 class="q" ${onlyCard?'hidden':''}>${t("wiz.how")}</h2><div class="pick col" role="radiogroup" aria-label="${esc(t("wiz.how"))}" ${onlyCard?'hidden':''}>`;
  for(const m of ["home","direct","cable","card"]){
    const ok = methods.includes(m);
    if(!cam.methods.includes(m)) continue;   // si mostrano solo i collegamenti che questa fotocamera ha davvero
    const why = cam.methods.includes(m) ? t("method.notHere") : loc(cam.unavailable);
    h += `<button class="opt ${wiz.method===m?'on':''}" role="radio" aria-checked="${wiz.method===m}" data-m="${m}" ${ok?'':'disabled'}><b>${t("method."+m)}</b><small>${ok?t("method."+m+".d"):esc(why)}</small></button>`;
  }
  h += `</div><div class="wizbar"><button class="go" id="wizGo">${t("wiz.start")}</button>`;
  if(cam.methods.includes("home")) h += `<button class="linkish" id="wizReg">${t("wiz.register")}</button>`;
  h += `</div><div class="foot"><div class="langrow"><span class="lbl">${t("lang.label")}</span>${langSeg("data-lang", LANG, t("lang.label"))}</div><p class="disc">Provino ${esc(S.version)} · ${t("app.disclaimer")}</p></div>`;
  return h;
}
document.addEventListener("click", e=>{
  const c = e.target.closest("[data-cam]"); if(c){ wiz.camera=c.dataset.cam; noticeKey=""; render(); return; }
  const m = e.target.closest("[data-m]"); if(m && !m.disabled){ wiz.method=m.dataset.m; noticeKey=""; render(); return; }
  const ml = e.target.closest("[data-ml]");
  if(ml){ post("/api/menu-lang", {camera: wiz.camera, lang: ml.dataset.ml}).then(r=>{ S.settings = r.settings; noticeKey=""; render(); }); return; }
  const lg = e.target.closest("[data-lang]");
  if(lg){ setLang(lg.dataset.lang, true); return; }
  if(e.target.closest("#wizGo")){ ticked.clear(); post("/api/start", wiz).then(poll); return; }
  if(e.target.closest("#wizReg")){ post("/api/register", {camera: wiz.camera}).then(poll); return; }
  if(e.target.closest("[data-change]")){ wiz=null; built=false; post("/api/stop", {}).then(poll); return; }
  if(e.target.closest("#xaQuit")){ post("/api/xacquire-quit", {}).then(r=>{ xaRunning=r.running; noticeKey=""; render(); }); return; }
  if(e.target.closest("#openIC")){ post("/api/open-imagecapture", {}); return; }
  if(e.target.closest("#openDir2")){ post("/api/open-folder", {}); return; }
});
function setLang(l, save){
  if(!I18N[l]) l = "en";
  LANG = l; noticeKey = ""; built = false; metaShown = null;
  applyStatic();
  if(save) post("/api/ui-lang", {lang: l});
  if(S) render();
}

// ---------------------------------------------------------------- rendering
// ---------------------------------------------------------------- cornice nativa (finestra GNOME)
// Nella finestra GNOME il titolo, Scarica, il pannello e "Cambia fotocamera" stanno nella barra della finestra:
// la pagina manda lo stato alla finestra e la finestra rimanda i comandi (window.provinoNative).
const NATIVE = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.provino);
if(NATIVE) document.documentElement.classList.add("native");
let nativeKey = "";
function nativeState(){
  if(!NATIVE) return;
  const ready = S.status==="ready" && S.files.length>0;
  const go = $("#go");
  const st = {
    ready, status: S.status,
    title: ready ? ($("#camName").textContent || "Provino") : "Provino",
    subtitle: ready ? [$("#camMeta").textContent, $("#camInfo").textContent].filter(Boolean)[0] || "" : "",
    go: { label: go.firstChild ? (go.childNodes[0].textContent || t("dl.btn")) : t("dl.btn"), small: (go.querySelector("small")||{}).textContent || "", enabled: ready && !go.disabled },
    split: !!split, canChange: S.status!=="setup", lang: LANG,
  };
  if(ready){
    const files = S.files||[];
    const nK = k => files.filter(f=>k==="VIDEO"? VIDEO.includes(f.kind) : f.kind===k).length;
    const sel = $("#filmSel");
    st.filter = filter;
    st.hasVideo = files.some(f=>VIDEO.includes(f.kind));
    st.films = sel && !sel.hidden ? [...sel.options].map(o=>[o.value, o.textContent]) : [];
    st.film = filmFilter || "";
    st.counts = {JPG:nK("JPG"), RAF:nK("RAF"), HIF:nK("HIF"), VIDEO:nK("VIDEO"),
                 both:nK("JPG")+nK("RAF"), fresh:files.filter(f=>!f.on_mac).length};
    st.picked = picked.size;
    st.sum = (go.querySelector("small")||{}).textContent || "";
  }
  const k = JSON.stringify({type:"state", ...st});
  if(k===nativeKey) return;
  nativeKey = k;
  try{ window.webkit.messageHandlers.provino.postMessage(k); }catch(e){}
}
function nativeMsg(o){ try{ window.webkit.messageHandlers.provino.postMessage(JSON.stringify(o)); }catch(e){} }
window.provinoNative = function(cmd, arg){
  if(cmd==="download"){ const hs=[...picked]; if(hs.length) askDest(hs); }
  else if(cmd==="filter"){ setFilter(arg); paint(); }
  else if(cmd==="film"){ filmFilter = arg||""; filmOptions(); paint(); }
  else if(cmd==="select"){ if(arg==="fresh") $("#selNew").click(); else if(arg==="none") $("#selNone").click();
    else if(arg==="visible"){ for(const g of groups()) wanted(g).forEach(f=>picked.add(f.handle)); paint(); }
    else selectAll(arg); }
  else if(cmd==="conflictsDone"){ startDownload(arg.hs, arg.options||{}); }
  else if(cmd==="lang"){ setLang(arg, true); }
  else if(cmd==="trayClosed"){ trayClosedAt = S.done.length + S.failed.length; tray(); }
  else if(cmd==="cancelDownload"){ fetch("/api/cancel",{method:"POST"}); }
  else if(cmd==="openFolder"){ fetch("/api/open-folder",{method:"POST"}); }
  else if(cmd==="destConfirmed"){ (async ()=>{
      const r = await post("/api/dest-settings", {dest: arg.dest, split_type: !!arg.split_type, by_date: !!arg.by_date});
      if(r.error){ nativeMsg({type:"error", text:r.error}); return; }
      S.settings = r.settings; S.dest = r.dest; afterDest(arg.hs); })(); }
  else if(cmd==="split"){ $("#viewToggle").click(); }
  else if(cmd==="change"){ wiz=null; built=false; post("/api/stop", {}).then(poll); }
  else if(cmd==="theme"){ document.documentElement.dataset.theme = arg || ""; }
  nativeState();
};

function render(){
  setTimeout(nativeState, 0);
  // collegamento perso: chiudo la foto a tutto schermo, cosi' si vede subito il messaggio
  if(S.status!=="ready" && !$("#full").hidden){ $("#full").hidden = true; zoomFit($("#fbox")); try{ if(document.fullscreenElement) document.exitFullscreen().catch(()=>{}); }catch(e){} }
  layout();
  const back = `<button class="linkish" data-change>${t("changeLong")}</button>`;
  if(S.status==="ready" && !S.files.length){ tray(); notice(t("empty.title"), t("empty.text"), false, back); return; }
  if(S.status==="ready"){ if(!built) build(); else paint(); tray(); return; }
  tray();
  const c = S.choice||{}, cam = c.camera || "";
  const msg = serverMsg();
  if(S.status==="setup"){ notice(t("wiz.title"), msg? `<span class="ok">${msg}</span>`:"", false, "", wizard()); return; }
  if(S.status==="registering"){ const reg = ((CAMS.cameras[cam]||{}).steps||{}).register; notice(t("register.title"), t(loc(reg)), true, back); return; }
  const isCable = c.method==="cable";
  if(isCable) checkXA();
  const xaWarn = (isCable && xaRunning) ? `<span class="warn">${t("xa.warn",{app:esc(xaRunning)})} <button class="quiet2" id="xaQuit">${t("xa.quit",{app:esc(xaRunning)})}</button></span>` : "";
  const cableWarn = isCable ? `<span class="warn">${t("cable.warn")}</span>` : "";
  if(S.status==="cable"){
    notice(t("connect.cable.title",{cam}), cableWarn + (msg? `<span class="err">${msg}</span>` : ""), false,
      xaWarn + `<div class="wizbar"><button class="go" id="openIC">${t("cable.openIC")}</button><button class="quiet" id="openDir2">${t("cable.openDir")}</button></div>` + back, checklist(false));
    return;
  }
  const btn = `<button class="go" id="reconnect">${t("reconnect")}</button>`;
  const isCard = c.method==="card";
  if(S.status==="waiting") notice(isCard? t("connect.card.title") : isCable? t("connect.cable.title",{cam}) : t("connect.title",{cam}), cableWarn + xaWarn + (msg? `<span class="err">${msg}</span>` : t("connect.follow")), false, back, checklist(false));
  else if(S.status==="connecting") notice(isCard? t("card.found") : t("connected.title",{cam:S.camera||cam}), (S.camera_id? S.camera_id+". ":"") + msg, true, "", checklist(true));
  else if(S.status==="error") notice(t("notconnected.title"), `<span class="err">${msg}</span>`, false, btn+back, checklist(false));
  else notice("Provino", t("starting"), true);
}
document.addEventListener("click", e=>{ if(e.target.closest("#reconnect")) post("/api/reconnect",{}).then(poll); });

let timer=null;
async function poll(){
  clearTimeout(timer);
  try{
    const r = await fetch("/api/state"); const prev=S; S = await r.json();
    if(prev && prev.files.length!==S.files.length) built=false;
    // l'ora di scatto puo' arrivare dopo, dall'EXIF: se cambia, ridisegno la griglia (giorni e ordine)
    if(prev && prev.files.map(f=>f.date).join()!==S.files.map(f=>f.date).join()) built=false;
    if(S.meta_n!==metaN){ metaN = S.meta_n; loadMeta(); }
    // download interrotti dal cavo: tornano selezionati, basta premere Scarica
    const pk = (S.pending||[]).join(",");
    if(pk && pk!==pendingKey){ for(const h of S.pending) picked.add(h); }
    pendingKey = pk;
    render();
  } catch(e){ noticeKey=""; notice(t("closed.title"), t("closed.text"), false); findNewer(); return; }
  timer = setTimeout(poll, S && (S.current||dlPending||S.status!=="ready") ? 700 : 1500);
}

(async function init(){
  CAMS = await (await fetch("/api/cameras")).json();
  const st = await (await fetch("/api/state")).json();
  const saved = (st.settings||{}).ui_lang;
  const sys = (navigator.language||"en").slice(0,2).toLowerCase();
  setLang(saved || (I18N[sys] ? sys : "en"), !saved);
  poll();
})();

// ---------------------------------------------------------------- anteprima grande
// Vista divisa: griglia a sinistra, foto grande a destra. Clic sulla foto grande = 100% (1 pixel
// della foto = 1 pixel dello schermo), trascina per spostarti. F o doppio clic = schermo intero.
let split = false;   // all'avvio sempre la griglia con tutte le foto; la vista divisa e' un'opzione
const bigCache = new Map();     // base -> {url, kind, w, h}
let bigReq = null, bigFor = null, bigRetry = null;

function curGroup(){ return cur ? groups().find(g=>g.base===cur) : null; }
function visibleBases(){ return groups().filter(g=>wanted(g).length).map(g=>g.base); }
function fullOpen(){ return !$("#full").hidden; }
// divisione trascinabile tra griglia e foto grande (larghezza ricordata, separata per foto e foto+META)
const VW = {photo:0, meta:0};
try{ const o = JSON.parse(localStorage.getItem("provino.vw")||"{}"); VW.photo = +o.photo||0; VW.meta = +o.meta||0; }catch(e){}
function vwKey(){ return document.body.classList.contains("metaon") ? "meta" : "photo"; }
function vwClamp(w){ return Math.round(Math.max(320, Math.min(innerWidth - 220, w))); }
function vwApply(){
  const w = VW[vwKey()];
  if(w) document.body.style.setProperty("--vw", vwClamp(w)+"px"); else document.body.style.removeProperty("--vw");
}
new MutationObserver(vwApply).observe(document.body, {attributes:true, attributeFilter:["class"]});
addEventListener("resize", vwApply);
(function(){
  const g = $("#vgrip"); if(!g) return;
  let x0 = 0, w0 = 0;
  g.addEventListener("pointerdown", e=>{
    e.preventDefault(); g.setPointerCapture(e.pointerId);
    x0 = e.clientX; w0 = $("#viewer").getBoundingClientRect().width;
    document.body.classList.add("vdrag");
  });
  g.addEventListener("pointermove", e=>{
    if(!document.body.classList.contains("vdrag")) return;
    VW[vwKey()] = vwClamp(w0 + (x0 - e.clientX)); vwApply();
  });
  const end = ()=>{ if(!document.body.classList.contains("vdrag")) return;
    document.body.classList.remove("vdrag");
    try{ localStorage.setItem("provino.vw", JSON.stringify(VW)); }catch(e){} };
  g.addEventListener("pointerup", end); g.addEventListener("pointercancel", end);
  g.addEventListener("dblclick", ()=>{ VW[vwKey()] = 0; vwApply(); try{ localStorage.setItem("provino.vw", JSON.stringify(VW)); }catch(e){} });
})();
function splitActive(){ return split && innerWidth > 900; }

function layout(){
  document.body.classList.toggle("split", splitActive() && S && S.status==="ready");
  $("#viewer").hidden = !(splitActive() && S && S.status==="ready");
  $("#viewToggle").setAttribute("aria-pressed", split);
  const bar = $("#bar");
  if(!bar.hidden) document.documentElement.style.setProperty("--barh", bar.offsetHeight+"px");
}
addEventListener("resize", ()=>{ layout(); zoomFit($("#vbox")); zoomFit($("#fbox")); });
$("#viewToggle").onclick = ()=>{
  split = !split;
  if(!split) document.body.classList.remove("metaon"); else if(vtab==="meta") document.body.classList.add("metaon");
  layout(); if(split) loadBig();
};

function setCur(base, scroll){
  if(!base) return;
  const changed = base!==cur;
  cur = base;
  for(const fr of document.querySelectorAll(".frame")) fr.classList.toggle("cur", fr.dataset.b===cur);
  if(scroll){ const fr = document.querySelector(`.frame[data-b="${CSS.escape(base)}"]`); if(fr) fr.scrollIntoView({block:"nearest"}); }
  if(changed){ zoomFit($("#vbox")); zoomFit($("#fbox")); }
  viewerPaint(); loadBig();
}
function step(d){
  const v = visibleBases(); if(!v.length) return;
  let i = v.indexOf(cur);
  i = i<0 ? 0 : Math.max(0, Math.min(v.length-1, i+d));
  setCur(v[i], true);
}
function toggleCur(){ if(cur){ toggleGroup(cur); anchor = cur; } }

function viewerPaint(){
  layout();
  const g = curGroup();
  const on = g && wanted(g).some(f=>picked.has(f.handle));
  for(const id of ["#vsel","#fsel"]){ const b=$(id); b.textContent = t(on?"view.selected":"view.sel"); b.setAttribute("aria-pressed", !!on); b.disabled = !g; }
  $("#vfull").disabled = !g;
  const name = g ? g.base.replace(/^_/,"") : "";
  const c = g && bigCache.get(g.base);
  const src = c ? `${t(c.kind==="RAF"?"view.srcRAF":"view.srcJPG")}, ${c.w}×${c.h} px` : (g? fmtDay(g.date)+" "+fmtTime(g.date) : "");
  if(vtab==="meta" || fmetaOn) renderMeta();
  $("#vname").textContent = $("#fname").textContent = name;
  $("#vsrc").textContent = $("#fsrc").textContent = src;
}

// ---------------------------------------------------------------- istogramma (calcolato qui dalla foto mostrata)
const HISTO = new Map();
function histoOf(img){
  const k = img.currentSrc || img.src;
  if(!k || !img.complete || !img.naturalWidth) return null;
  if(HISTO.has(k)) return HISTO.get(k);
  const W = Math.min(480, img.naturalWidth), H = Math.max(1, Math.round(W*img.naturalHeight/img.naturalWidth));
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const x = c.getContext("2d", {willReadFrequently:true});
  let d;
  try{ x.drawImage(img, 0, 0, W, H); d = x.getImageData(0, 0, W, H).data; }catch(e){ return null; }
  const r = new Float32Array(256), g = new Float32Array(256), b = new Float32Array(256), l = new Float32Array(256);
  for(let i=0; i<d.length; i+=4){ r[d[i]]++; g[d[i+1]]++; b[d[i+2]]++; l[(0.2126*d[i]+0.7152*d[i+1]+0.0722*d[i+2])|0]++; }
  const h = {r, g, b, l, low: img.classList.contains("low")};
  if(!h.low){ HISTO.set(k, h); if(HISTO.size > 60) HISTO.delete(HISTO.keys().next().value); }
  return h;
}
function drawHisto(){
  for(const [pane, pic] of [["#vmeta","#vpic"],["#fmeta","#fpic"]]){
    const cv = document.querySelector(pane+" .histo canvas"), img = $(pic);
    if(!cv || !img) continue;
    const h = histoOf(img), x = cv.getContext("2d"), W = cv.width, H = cv.height;
    x.clearRect(0, 0, W, H);
    if(!h) continue;
    // scala: il picco tra i toni intermedi (i pixel bruciati o chiusi non schiacciano tutto il resto)
    let top = 1;
    for(const a of [h.r, h.g, h.b, h.l]) for(let i=2; i<254; i++) if(a[i] > top) top = a[i];
    const curve = (a, fill)=>{
      x.beginPath(); x.moveTo(0, H);
      for(let i=0; i<256; i++) x.lineTo(i*W/255, H - Math.min(1, a[i]/top)*(H-4));
      x.lineTo(W, H); x.closePath(); x.fillStyle = fill; x.fill();
    };
    const dark = getComputedStyle(document.body).getPropertyValue("color-scheme").includes("dark")
      || matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light"
      || document.documentElement.dataset.theme === "dark";
    x.globalCompositeOperation = dark ? "lighter" : "multiply";
    if(dark){ curve(h.r, "rgba(255,69,58,.55)"); curve(h.g, "rgba(48,209,88,.55)"); curve(h.b, "rgba(10,132,255,.6)"); }
    else { curve(h.r, "rgba(255,110,100,.75)"); curve(h.g, "rgba(110,220,130,.75)"); curve(h.b, "rgba(100,160,255,.75)"); }
    x.globalCompositeOperation = "source-over";
    cv.parentElement.classList.toggle("low", h.low);
  }
}
for(const id of ["#vpic","#fpic"]){ const im = $(id); if(im) im.addEventListener("load", ()=>setTimeout(drawHisto, 0)); }

function showImg(which, url, low){
  const img = $(which==="v"?"#vpic":"#fpic");
  if(img.dataset.url !== url){ img.dataset.url = url||""; if(url) img.src = url; else img.removeAttribute("src"); }
  img.classList.toggle("low", !!low);
  img.hidden = !url;
}
function setMsg(text, busy){
  $("#vmsg").textContent = $("#fmsg").textContent = text||"";
  $("#vwait").hidden = $("#fwait").hidden = !busy;
}

async function loadBig(){
  clearTimeout(bigRetry);
  const g = curGroup();
  if(!g){ showImg("v",null); showImg("f",null); setMsg(t("view.empty"), false); return; }
  if(!splitActive() && !fullOpen()) return;
  if(isVideo(g)){ showImg("v",null); showImg("f",null); setMsg(t("view.video"), false); return; }
  const c = bigCache.get(g.base);
  if(c){ showImg("v",c.url); showImg("f",c.url); setMsg("", false); viewerPaint(); prefetchNext(); return; }
  const th = thumbHandle(g);
  const lowUrl = (S.thumbs_ready||[]).includes(th) ? `/api/thumb/${th}?b=${encodeURIComponent(g.base)}&z=${(g.files.JPG||g.files.RAF||{}).size||0}` : null;
  showImg("v", lowUrl, true); showImg("f", lowUrl, true); setMsg("", true);
  if(bigFor===g.base) return;          // gia' in arrivo
  if(bigReq) bigReq.abort();
  bigReq = new AbortController(); bigFor = g.base;
  const base = g.base, h = (g.files.JPG||g.files.RAF||Object.values(g.files)[0]).handle;
  try{
    const r = await fetch(`/api/big/${h}?b=${encodeURIComponent(base)}&z=${(g.files.JPG||g.files.RAF||{}).size||0}`, {signal: bigReq.signal});
    if(r.status===409){
      const why = (await r.json()).error;
      bigFor = null;
      if(cur===base){ if(why==="busy") setMsg(t("view.busy"), false); bigRetry = setTimeout(loadBig, why==="busy"?2000:300); }
      return;
    }
    if(!r.ok){ bigFor = null; if(cur===base) setMsg(t("view.none"), false); return; }
    const kind = r.headers.get("X-Provino-Source") || "JPG";
    const url = URL.createObjectURL(await r.blob());
    const dim = await new Promise(res=>{ const im=new Image(); im.onload=()=>res([im.naturalWidth, im.naturalHeight]); im.onerror=()=>res([0,0]); im.src=url; });
    remember(base, {url, kind, w:dim[0], h:dim[1]});
    bigFor = null;
    if(cur===base) loadBig();
  }catch(e){ if(bigFor===base) bigFor = null; }
}
function remember(base, v){
  bigCache.set(base, v);
  while(bigCache.size > 30){ const k = bigCache.keys().next().value; if(k===cur) break; URL.revokeObjectURL(bigCache.get(k).url); bigCache.delete(k); }
}
// via cavo prepara anche la foto successiva, cosi' scorrere con le frecce e' immediato
let prefetching = null;
async function prefetchNext(){
  const pm = (S.choice||{}).method;
  if((pm!=="cable" && pm!=="card") || prefetching) return;
  const v = visibleBases(), i = v.indexOf(cur), base = v[i+1];
  if(!base || bigCache.has(base)) return;
  const g = groups().find(x=>x.base===base); if(!g) return;
  prefetching = base;
  try{
    const h = (g.files.JPG||g.files.RAF||Object.values(g.files)[0]).handle;
    const r = await fetch(`/api/big/${h}?b=${encodeURIComponent(base)}&z=${(g.files.JPG||g.files.RAF||{}).size||0}`);
    if(r.ok){
      const kind = r.headers.get("X-Provino-Source") || "JPG", url = URL.createObjectURL(await r.blob());
      const dim = await new Promise(res=>{ const im=new Image(); im.onload=()=>res([im.naturalWidth, im.naturalHeight]); im.onerror=()=>res([0,0]); im.src=url; });
      remember(base, {url, kind, w:dim[0], h:dim[1]});
    }
  }catch(e){}
  prefetching = null;
}

// ------ zoom al 100% e spostamento
function zoomFit(box){
  box.classList.remove("z","drag");
  const img = box.querySelector("img"); img.style.cssText = "";
}
function zoomAt(box, cx, cy){
  const img = box.querySelector("img");
  if(!img.naturalWidth || img.classList.contains("low")) return;
  const ib = img.getBoundingClientRect(), bb = box.getBoundingClientRect();
  const fx = Math.min(1, Math.max(0, (cx-ib.left)/ib.width)), fy = Math.min(1, Math.max(0, (cy-ib.top)/ib.height));
  const dpr = window.devicePixelRatio || 1;
  const W = img.naturalWidth/dpr, H = img.naturalHeight/dpr;
  box.classList.add("z");
  img.style.width = W+"px"; img.style.height = H+"px";
  place(box, (cx-bb.left) - fx*W, (cy-bb.top) - fy*H);
}
function place(box, x, y){
  const img = box.querySelector("img"), bw = box.clientWidth, bh = box.clientHeight;
  const W = parseFloat(img.style.width), H = parseFloat(img.style.height);
  x = W<=bw ? (bw-W)/2 : Math.min(0, Math.max(bw-W, x));
  y = H<=bh ? (bh-H)/2 : Math.min(0, Math.max(bh-H, y));
  img.style.left = x+"px"; img.style.top = y+"px";
}
for(const id of ["#vbox","#fbox"]){
  const box = $(id);
  let pan = null;
  box.addEventListener("mousedown", e=>{
    if(e.button!==0) return; e.preventDefault();
    const img = box.querySelector("img");
    pan = {x:e.clientX, y:e.clientY, l:parseFloat(img.style.left)||0, t:parseFloat(img.style.top)||0, moved:false};
  });
  addEventListener("mousemove", e=>{
    if(!pan) return;
    if(!pan.moved && Math.hypot(e.clientX-pan.x, e.clientY-pan.y) < 4) return;
    pan.moved = true;
    if(box.classList.contains("z")){ box.classList.add("drag"); place(box, pan.l + e.clientX-pan.x, pan.t + e.clientY-pan.y); }
  });
  addEventListener("mouseup", e=>{
    if(!pan) return;
    const p = pan; pan = null; box.classList.remove("drag");
    if(p.moved) return;
    box.classList.contains("z") ? zoomFit(box) : zoomAt(box, e.clientX, e.clientY);
  });
  box.addEventListener("dblclick", e=>{ if(id==="#vbox"){ zoomFit(box); openFull(); } });
}

// ------ schermo intero
function openFull(){
  if(!curGroup()) return;
  $("#full").hidden = false; zoomFit($("#fbox"));
  try{ const el=document.documentElement; if(el.requestFullscreen && !document.fullscreenElement) el.requestFullscreen().catch(()=>{}); }catch(e){}
  viewerPaint(); loadBig();
}
function closeFull(){
  $("#full").hidden = true; zoomFit($("#fbox"));
  try{ if(document.fullscreenElement) document.exitFullscreen().catch(()=>{}); }catch(e){}
  if(cur) setCur(cur, true);
}
document.addEventListener("fullscreenchange", ()=>{ if(!document.fullscreenElement && fullOpen()) closeFull(); });
document.addEventListener("dblclick", e=>{
  const p = e.target.closest(".photo"); if(!p) return;
  setCur(p.dataset.b); openFull();
});
$("#vfull").onclick = openFull;
$("#fclose").onclick = closeFull;
$("#fprev").onclick = ()=>step(-1);
$("#fnext").onclick = ()=>step(1);
$("#vsel").onclick = $("#fsel").onclick = toggleCur;

function viewerKey(e){
  if(e.metaKey || e.ctrlKey || e.altKey) return false;
  const k = e.key;
  if(fullOpen() && k==="Escape"){ e.preventDefault(); closeFull(); return true; }
  if(k==="ArrowRight" || k==="ArrowDown"){ e.preventDefault(); step(k==="ArrowDown" && !fullOpen() ? cols() : 1); return true; }
  if(k==="ArrowLeft" || k==="ArrowUp"){ e.preventDefault(); step(k==="ArrowUp" && !fullOpen() ? -cols() : -1); return true; }
  if(k===" "){ e.preventDefault(); if(!cur) step(0); else toggleCur(); return true; }
  // F come il clic del mouse: dalla griglia apre la foto intera; nella foto intera alterna 100% e foto intera.
  // Per tornare alla griglia: Esc.
  if(k==="f" || k==="F"){ e.preventDefault(); if(!cur) step(0);
    if(!fullOpen()) openFull();
    else { const box=$("#fbox"); if(box.classList.contains("z")) zoomFit(box); else { const r=box.getBoundingClientRect(); zoomAt(box, r.left+r.width/2, r.top+r.height/2); } }
    return true; }
  return false;
}
function cols(){
  const fr = [...document.querySelectorAll(".frame")].filter(f=>!f.hidden);
  if(fr.length<2) return 1;
  const top = fr[0].getBoundingClientRect().top;
  const n = fr.findIndex(f=>Math.abs(f.getBoundingClientRect().top-top) > 5);
  return n>0 ? n : fr.length;
}

// ---------------------------------------------------------------- metadati e ricetta (META)
function filmName(k){ return (typeof FILM_NAMES!=="undefined" && FILM_NAMES[k]) || k; }
async function loadMeta(){
  try{ META = await (await fetch("/api/meta")).json(); }catch(e){ return; }
  filmOptions();
  if(S && S.status==="ready" && built) paint();
}
function filmOptions(){
  const sel = $("#filmSel"); if(!sel) return;
  const count = {};
  for(const g of (S? groups() : [])){ const f=(META[g.base]||{}).film; if(f) count[f]=(count[f]||0)+1; }
  const keys = Object.keys(count).sort((a,b)=>count[b]-count[a]);
  if(filmFilter && !count[filmFilter]) keys.unshift(filmFilter);
  const html = `<option value="">${esc(t("film.all"))}</option>` + keys.map(k=>`<option value="${esc(k)}">${esc(filmName(k))} (${count[k]||0})</option>`).join("");
  if(sel.dataset.html!==html){ sel.dataset.html = html; sel.innerHTML = html; }
  sel.value = filmFilter; sel.classList.toggle("on", !!filmFilter);
  sel.hidden = keys.length===0;
}
document.addEventListener("change", e=>{
  if(e.target.id!=="filmSel") return;
  filmFilter = e.target.value;
  filmOptions(); paint();
});

let vtab = "photo", fmetaOn = false;
function openMeta(base){
  setCur(base);
  if(!split && innerWidth > 900){ split = true; layout(); loadBig(); }
  if(splitActive()){ setTab("meta"); }
  else { fmetaOn = true; openFull(); }
}
function setTab(tb){
  // "meta" = ricetta accanto alla foto (niente piu' schede Foto/META: si vedono insieme)
  vtab = tb;
  const on = tb==="meta";
  $("#vmeta").hidden = !on;
  $("#vmetaBtn").setAttribute("aria-pressed", on);
  document.body.classList.toggle("metaon", on && splitActive());
  renderMeta();
  requestAnimationFrame(()=>zoomFit($("#vbox")));
}
$("#vmetaBtn").onclick = ()=>setTab(vtab==="meta" ? "photo" : "meta");
document.addEventListener("click", e=>{
  const tb = e.target.closest("[data-vtab]"); if(tb){ setTab(tb.dataset.vtab); return; }
  if(e.target.closest("#fmetaBtn")){ fmetaOn = !fmetaOn; renderMeta(); return; }
  const cp = e.target.closest("[data-copy]");
  if(cp){ const txt = recipeText(META[cp.dataset.copy]||{});
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(()=>{ cp.textContent = t("meta.copied"); setTimeout(()=>cp.textContent=t("meta.copy"), 1500); }).catch(()=>{});
    return; }
});

const sgn = v => v>0 ? "+"+fmtDec(v) : v<0 ? "−"+fmtDec(-v) : "0";
function fmtDec(v){ return (Math.round(v*10)/10).toString().replace(".", LANG==="it"?",":"."); }
function strength(v){ return v ? t("v."+v) : ""; }
function recipeRows(m){
  const r = [];
  if(m.film) r.push(["r.film", filmName(m.film), "film"]);
  if(m.grain!==undefined) r.push(["r.grain", m.grain==="off" ? t("v.off") : `${t("v."+m.grain)}${m.grain_size?", "+t("v."+m.grain_size):""}`]);
  if(m.chrome!==undefined) r.push(["r.chrome", strength(m.chrome)]);
  if(m.chrome_blue!==undefined) r.push(["r.chrome_blue", strength(m.chrome_blue)]);
  if(m.wb) r.push(["r.wb", (t("wb."+m.wb)) + (m.wb_kelvin? ` ${m.wb_kelvin} K` : "")]);
  if(m.wb_shift) r.push(["r.wb_shift", `R ${sgn(m.wb_shift[0])}, B ${sgn(m.wb_shift[1])}`]);
  if(m.dr) r.push(["r.dr", m.dr==="auto" ? t("v.auto") : m.dr]);
  if(m.dr_priority) r.push(["r.dr_priority", t("v."+m.dr_priority)]);
  if(m.highlight!==undefined) r.push(["r.highlight", sgn(m.highlight)]);
  if(m.shadow!==undefined) r.push(["r.shadow", sgn(m.shadow)]);
  if(m.color!==undefined) r.push(["r.color", sgn(m.color)]);
  if(m.mono_wc!==undefined || m.mono_mg!==undefined) r.push(["r.mono", `${sgn(m.mono_wc||0)}, ${sgn(m.mono_mg||0)}`]);
  if(m.sharpness!==undefined) r.push(["r.sharpness", sgn(m.sharpness)]);
  if(m.nr!==undefined) r.push(["r.nr", sgn(m.nr)]);
  if(m.clarity!==undefined) r.push(["r.clarity", sgn(m.clarity)]);
  return r;
}
function expoText(m){
  const p = [];
  if(m.exposure) p.push(m.exposure>=0.3 ? fmtDec(m.exposure)+" s" : "1/"+Math.round(1/m.exposure)+" s");
  if(m.fnumber) p.push("f/"+fmtDec(m.fnumber));
  if(m.iso) p.push("ISO "+m.iso);
  return p.join("  ·  ");
}
function shotRows(m){
  const r = [];
  if(m.model) r.push(["s.camera", m.model + (m.firmware? `  (firmware ${m.firmware})`:"")]);
  if(m.lens) r.push(["s.lens", m.lens]);
  if(m.focal) r.push(["s.focal", m.focal35 && Math.round(m.focal35)!==Math.round(m.focal) ? t("s.focal35",{mm:fmtDec(m.focal), eq:m.focal35}) : fmtDec(m.focal)+" mm"]);
  const ex = expoText(m); if(ex) r.push(["s.exposure", ex]);
  if(m.ev!==undefined) r.push(["s.ev", sgn(m.ev)+" EV"]);
  if(m.program) r.push(["s.program", t("v."+m.program)]);
  if(m.shutter) r.push(["s.shutter", t("v."+m.shutter)]);
  if(m.date){ const d = m.date.replace(/[: ]/g,""); r.push(["s.date", fmtDay(d.slice(0,8)+"T"+d.slice(8))+" "+m.date.slice(11,16)]); }
  if(m.shots!==undefined) r.push(["s.count", fmtNum(m.shots)]);
  return r;
}
function recipeText(m){
  return [filmName(m.film||"")].concat(recipeRows(m).filter(r=>r[0]!=="r.film").map(r=>`${t(r[0])}: ${r[1]}`)).join("\n");
}
function slotRow(g){ const sl = g && slotOf(g); return sl ? [["s.slot", t("slot.n",{n:sl})]] : []; }
function pixelRow(m){
  // dimensioni in pixel della foto (per il RAF le legge il motore dall'intestazione del file)
  if(!(m && m.width && m.height)) return [];
  const w=Math.max(m.width,m.height), h=Math.min(m.width,m.height);
  const [a,b] = m.portrait ? [h,w] : [w,h];
  return [["meta.pixels", `${fmtNum(a)} × ${fmtNum(b)} px · ${Math.round(w*h/1e6)} MP`]];
}
function metaHTML(g){
  if(!g) return `<p class="soon">${t("view.empty")}</p>`;
  if(isVideo(g)) return `<p class="soon">${t("meta.video")}</p>`;
  const m = META[g.base];
  if(!m) return `<p class="soon">${t("meta.loading")}</p>`;
  const dl = rows => `<dl>${rows.map(([k,v,c])=>`<dt>${esc(t(k))}</dt><dd${c?` class="${c}"`:""}>${esc(v)}</dd>`).join("")}</dl>`;
  return `<div class="histo" aria-label="${esc(t("meta.histo"))}"><canvas width="512" height="140"></canvas></div>
    <h3>${t("meta.recipe")}</h3>${dl(recipeRows(m))}
    <h3>${t("meta.shot")}</h3>${dl(shotRows(m).concat(pixelRow(m), slotRow(g)))}
    <div class="mfoot"><button class="quiet" data-copy="${esc(g.base)}">${t("meta.copy")}</button><span>${esc(t("meta.readFrom",{f:m.from||""}))}</span></div>
    <p class="soon">${t("meta.editSoon")}</p>`;
}
const metaAsked = new Set();
function renderMeta(){
  const g = curGroup();
  if(g && !isVideo(g) && !META[g.base] && !metaAsked.has(g.base)){
    metaAsked.add(g.base);
    const h = (g.files.JPG||g.files.RAF||Object.values(g.files)[0]).handle;
    fetch(`/api/meta/${h}`).then(r=>r.ok?r.json():null).then(m=>{ if(m){ META[g.base]=m; filmOptions(); renderMeta(); paint(); } else setTimeout(()=>metaAsked.delete(g.base), 3000); });
  }
  const html = metaHTML(g);
  for(const id of ["#vmeta","#fmeta"]){ const el=$(id); if(el.dataset.html!==html){ el.dataset.html=html; el.innerHTML=html; } }
  drawHisto();
  $("#fmeta").hidden = !fmetaOn; $("#fmetaBtn").setAttribute("aria-pressed", fmetaOn);
}

// Foto verticali nella griglia. Due casi possibili:
//  - miniatura orizzontale "coricata" (da girare secondo l'orientamento EXIF) -> la giro;
//  - miniatura gia' dritta (verticale, o orizzontale con bande nere ai lati) -> la ritaglio in verticale.
//    Via cavo il Mac (ImageCaptureCore) la manda gia' verticale: verificato con la X-Pro3, 2 nov 2026.
// In entrambi i casi la foto occupa una cornice verticale al centro del provino, cosi' si vede che e' verticale.
function orient(img){
  const fr = img.closest(".frame"), m = fr && META[fr.dataset.b];
  let cls = "";
  if(m && img.naturalWidth){
    const landscapeThumb = img.naturalWidth > img.naturalHeight;
    if(m.portrait) cls = !landscapeThumb || pillarbox(img) ? "port" : (m.orientation===270 ? "r270" : "r90");
    else if(m.orientation===180) cls = "r180";
  }
  if((img.dataset.rot||"") !== cls){
    img.classList.remove("r90","r180","r270","port"); if(cls) img.classList.add(cls); img.dataset.rot = cls;
    if(fr) fr.classList.toggle("vert", cls==="port" || cls==="r90" || cls==="r270");
  }
}
function pillarbox(img){
  if(img.dataset.pb) return img.dataset.pb==="1";
  let r = false;
  try{
    const w=48, h=36, c=document.createElement("canvas"); c.width=w; c.height=h;
    const x=c.getContext("2d"); x.drawImage(img,0,0,w,h);
    const d=x.getImageData(0,0,w,h).data, lum=(i)=>0.3*d[i]+0.59*d[i+1]+0.11*d[i+2];
    let edge=0, mid=0, ne=0, nm=0;
    for(let yy=0; yy<h; yy++) for(let xx=0; xx<w; xx++){
      const v=lum((yy*w+xx)*4);
      if(xx<4 || xx>=w-4){ edge+=v; ne++; } else if(xx>w*0.3 && xx<w*0.7){ mid+=v; nm++; }
    }
    edge/=ne; mid/=nm;
    r = edge < 14 && mid > edge + 10;
  }catch(e){}
  img.dataset.pb = r ? "1" : "0";
  return r;
}

// Provino riaperto: questa scheda e' vecchia. Cerco la copia nuova sulle porte vicine (una risposta,
// anche "opaca", basta a sapere che c'e') e lo scrivo, cosi' non si resta su una scheda che non funziona.
async function findNewer(tries){
  tries = tries || 0;
  const here = +location.port || 80;
  for(let p=8765; p<8795; p++){
    if(p===here) continue;
    try{
      await fetch(`http://127.0.0.1:${p}/api/state`, {mode:"no-cors", cache:"no-store"});
      noticeKey=""; notice(t("moved.title"), t("moved.text"), false);
      return;
    }catch(e){}
  }
  // la copia nuova puo' metterci qualche secondo a partire: riprovo per circa un minuto
  if(tries < 30) setTimeout(()=>findNewer(tries+1), 2000);
}

// Testo della casella "Separa ...": solo i tipi di file scelti (es. RAF + video: niente JPG).
function splitLabel(hs){
  const sel = S.files.filter(f=>hs.includes(f.handle));
  const kinds = [];
  if(sel.some(f=>f.kind==="RAF")) kinds.push(["RAF", t("dest.kRAF")]);
  if(sel.some(f=>f.kind==="JPG")) kinds.push(["JPG", t("dest.kJPG")]);
  if(sel.some(f=>f.kind==="HIF")) kinds.push(["HEIF", "HEIF"]);
  if(sel.some(f=>VIDEO.includes(f.kind))) kinds.push(["VIDEO", t("dest.kVIDEO")]);
  if(!kinds.length) return t("dest.split");
  const join = a => a.length<2 ? a.join("") : a.slice(0,-1).join(", ") + t("dest.and") + a[a.length-1];
  const dirs = join(kinds.map(k=>"<b>"+k[0]+"</b>"));
  if(kinds.length===1) return t("dest.split1",{dir:dirs});
  return t("dest.splitN",{list:join(kinds.map(k=>k[1])), dirs});
}
