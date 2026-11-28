"use strict";
const main = document.querySelector("main");
const nav = document.querySelector("#nav");
const dialog = document.querySelector("dialog");
let auth = {user:null}, options, noticeTimer;
let catalogueFilters = {}, mapMode = false, filterOpen = false, renderId = 0;
const states = {PENDING:"Demande en attente", ACCEPTED:"Réservation confirmée", WITHDRAWN:"Demande retirée",
  REJECTED:"Demande refusée", EXPIRED:"Demande expirée", CANCELLED_BY_HOST:"Annulée par l’hôte",
  CANCELLED_BY_GUEST:"Annulée par l’invité", ADMIN_CLOSED:"Fermée par la modération", ATTENDED:"Présence confirmée",
  NO_SHOW:"Absence déclarée", OPEN:"Programmé", CANCELLED:"Annulé", COMPLETED:"Terminé", WAITING:"En attente de publication",
  PUBLISHED:"Publié", HIDDEN:"Masqué", NEUTRALIZED:"Neutralisé"};
const paths = {
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  date:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v5m10-5v5M3 11h18"/>',
  group:'<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2m1-14a3 3 0 0 1 0 6m2 2a5 5 0 0 1 3 5"/>',
  list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h1m-1 6h1m-1 6h1"/>',
  map:'<path d="m3 5 6-2 6 3 6-2v15l-6 2-6-3-6 2zm6-2v15m6-12v15"/>',
  plate:'<circle cx="12" cy="12" r="6"/><path d="M2 3v7m2-7v7m-3 0h4m-2 0v11m18-18v18"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  bell:'<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4zm4 4h4"/>',
  chevron:'<path d="m9 6 6 6-6 6"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/>',
  shield:'<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  spark:'<path d="M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M6 18l2.5-2.5m7-7L18 6"/>'

};
function icon(name){return `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${paths[name]||""}</svg>`;}
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function dt(ts){return new Intl.DateTimeFormat("fr-FR",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}).format(ts*1000);}
function mealPhoto(image){return image.startsWith("data:image/jpeg;base64,")?image:"static/images/"+image+".webp";}
function photoCredit(m){return m.image_credit?`<small class="credit">Photo : <a href="${esc(m.image_credit_url)}" target="_blank" rel="noopener noreferrer">${esc(m.image_credit)}</a> (via Openverse)</small>`:"";}
function avatar(u){if(u.photo?.startsWith("data:image/jpeg;base64,"))return `<img class="avatar" src="${esc(u.photo)}" alt="">`;return `<span class="avatar ${esc(u.photo)}" aria-hidden="true">${esc(u.name.slice(0,1))}</span>`;}
function badge(s){return `<span class="badge">${esc(s)}</span>`;}
function empty(s){return `<p class="empty">${esc(s)}</p>`;}
function a(hash,label,cls=""){return `<a class="${cls}" href="#${hash}">${esc(label)}</a>`;}
function action(label,act,id="",cls="secondary"){return `<button type="button" class="${cls}" data-act="${act}" data-id="${esc(id)}">${esc(label)}</button>`;}
function reportBtn(kind,id){return auth.user?.verified?action("Signaler","report",`${kind}/${id}`,"plain"):"";}
function head(title,sub=""){return `<div class="section-head"><div><h1>${esc(title)}</h1>${sub?`<p class="sub">${esc(sub)}</p>`:""}</div></div>`;}
function field(label,name,type="text",val="",attrs=""){return `<label><span>${esc(label)}</span><input name="${name}" type="${type}" value="${esc(val)}" ${attrs}></label>`;}
function area(label,name,val="",required=false){return `<label class="wide"><span>${esc(label)}</span><textarea name="${name}" maxlength="2400" ${required?"required":""}>${esc(val)}</textarea></label>`;}
function selectField(label,name,values,selected="",blank="Choisir…",req=false){return `<label><span>${esc(label)}</span><select aria-label="${esc(label)}" name="${name}" ${req?"required":""}>${blank!==null?`<option value="">${esc(blank)}</option>`:""}${values.map(v=>`<option ${selected===v?"selected":""} value="${esc(v)}">${esc(v)}</option>`).join("")}</select></label>`;}
function check(label,name,on=false,value="1"){return `<label class="check"><input type="checkbox" name="${name}" value="${esc(value)}" ${on?"checked":""}>${esc(label)}</label>`;}
function choice(title,key,values,on=[]){return `<fieldset class="wide"><legend>${esc(title)}</legend><div class="choice">${values.map(v=>check(v,key,on.includes(v),v)).join("")}</div></fieldset>`;}
function form(id,content,submit){return `<form data-form="${id}" class="stack">${content}<p class="form-error" role="alert"></p><div><button class="primary" type="submit">${esc(submit)}</button></div></form>`;}
function message(msg){let n=document.querySelector("#notice");n.textContent=msg;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>n.textContent="",5000);}
async function api(path,method="GET",body,key){
  const headers={"Accept":"application/json"};
  if(key)headers["Idempotency-Key"]=key;
  if(body!==undefined)headers["Content-Type"]="application/json";
  if(method!=="GET"&&auth.csrf)headers["X-CSRF-Token"]=auth.csrf;
  let res;
  try{res=await fetch("api"+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),cache:"no-store"});}
  catch{throw new Error(navigator.onLine?"Le serveur ne répond pas. Réessaie dans un instant.":"Tu es hors connexion : vérifie ton réseau puis réessaie.");}
  const data=await res.json();
  if(!res.ok){
    if(res.status===401&&data.code==="SESSION_REQUIRED"&&auth.user){auth={user:null};sessionStorage.setItem("return",location.hash);location.hash="login";message("Votre session a expiré. Reconnectez-vous.");}
    throw Object.assign(new Error(data.message||"La demande a échoué."),{data,status:res.status});
  }
  return data;
}
function routeParts(){return (location.hash.slice(1)||"catalogue").split("/");}
/* Onglet de la barre du bas correspondant à chaque route. */
const TAB_OF={catalogue:"catalogue",meal:"catalogue",profile:"catalogue",bookings:"bookings",publish:"publish",
  messages:"messages",thread:"messages",me:"me",account:"me",host:"me",notes:"me",admin:"me",case:"me",verify:"me",login:"me",register:"me"};
function showNav(){
  const [route]=routeParts(), u=auth.user, tab=TAB_OF[route]||"catalogue";
  const link=(r,t,cl="")=>a(r,t,`${cl} ${route===r?"current":""}`);
  // Ordinateur : menu du haut. Téléphone : cloche ou bouton de connexion en haut, onglets en bas.
  const desk=link("catalogue","Les tables","optional")+link("publish","Proposer un repas",u?.verified?"button":"optional")+
    (!u?link("login","Se connecter","button"):`<details><summary data-initial="${esc(u.name.slice(0,1).toUpperCase())}">${esc(u.name)}</summary><div class="menu">${
    u.verified?[["host","Mes repas"],["bookings","Mes réservations"],["messages","Messages"],["notes","Notifications"],["account","Mon profil"],...(u.admin?[["admin","Administration"]]:[])].map(([r,t])=>link(r,t)).join(""):link("account","Mon profil")+link("verify","Vérifier mon compte")
    }${action("Se déconnecter","logout","","plain")}</div></details>`);
  const mob=u?.verified?`<a class="bell" href="#notes" aria-label="Notifications">${icon("bell")}<b class="dot" data-badge="notes" hidden></b></a>`
    :!u&&!["login","register"].includes(route)?`<a class="button small-btn" href="#login">Connexion</a>`:"";
  nav.innerHTML=`<div class="desk">${desk}</div><div class="mob">${mob}</div>`;
  const item=(r,label,ic)=>`<a href="#${r}" class="tab" ${tab===r?'aria-current="page"':""}>${icon(ic)}<span>${esc(label)}</span><b class="dot" data-badge="${r}" hidden></b></a>`;
  document.querySelector("#tabs").innerHTML=item("catalogue","Tables","plate")+item("bookings","Réservations","date")+
    `<a href="#publish" class="tab tab-plus" aria-label="Proposer" ${tab==="publish"?'aria-current="page"':""}>${icon("plus")}</a>`+
    item("messages","Messages","chat")+item("me",u?"Profil":"Connexion","user");
  if(u?.verified)refreshBadges();
}
/* Pastilles de non-lus (cloche et onglet Messages). */
async function refreshBadges(){
  const notes=await api("/notifications/me").catch(()=>[]), unread=notes.filter(n=>!n.read);
  const counts={notes:unread.length,me:unread.length,messages:unread.filter(n=>n.link.startsWith("#thread/")).length};
  for(const el of document.querySelectorAll("[data-badge]")){
    const n=counts[el.dataset.badge]||0;el.hidden=!n;el.textContent=n>9?"9+":n||"";
  }
}
function openDialog(html){document.querySelector("#dialog-body").innerHTML=html;dialog.showModal();}
function go(hash){if(location.hash==="#"+hash)render();else location.hash=hash;}
function getReturn(){const h=sessionStorage.getItem("return")||"#catalogue";sessionStorage.removeItem("return");return /^#[a-z]+(\/\d+)?$/.test(h)?h.slice(1):"catalogue";}
function loginLink(target){return `<a class="button" href="#login" data-return="${esc(target)}">Se connecter</a>`;}


function photoInput(label){return `<label><span>${esc(label)}</span><input type="file" name="upload" accept="image/jpeg,image/png,image/webp"><small>JPEG, PNG ou WebP · 3 Mio maximum</small></label>`;}
async function applyPhoto(data,fd,key){
 const file=fd.get("upload");delete data.upload;
 if(!file?.size)return;
 if(file.size>3*1024*1024)throw new Error("La photo dépasse 3 Mio.");
 data[key]=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error("Photo illisible."));reader.readAsDataURL(file);});
}

/* ===== Animations : apparition au défilement, zoom de la bannière, transition de page ===== */
const motionOK=!matchMedia("(prefers-reduced-motion: reduce)").matches;
let revealer=null;
function animateIn(root){
  root.classList.remove("page-enter");void root.offsetWidth;root.classList.add("page-enter");
  if(!motionOK||!("IntersectionObserver" in window))return;
  revealer?.disconnect();
  revealer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add("in");revealer.unobserve(e.target);}},
    {rootMargin:"0px 0px -6% 0px",threshold:.06});
  let n=0;
  for(const el of root.querySelectorAll(".card,.panel,.item,.tile,.section-head,.hero-media,.suggest-hint,.install-card,.empty")){
    if(el.parentElement.closest(".reveal"))continue;           // un seul niveau d’animation
    el.classList.add("reveal");el.style.setProperty("--i",n++%6);revealer.observe(el);
  }
  heroZoom();
}
/* Bannière d’accueil : l’image s’élargit et se « pose » à mesure qu’on fait défiler (façon pages produit). */
function heroZoom(){
  const m=document.querySelector("[data-zoom]");if(!m||!motionOK)return;
  const r=m.getBoundingClientRect(), p=Math.min(1,Math.max(0,(innerHeight-r.top)/(innerHeight*.9)));
  m.style.setProperty("--p",p.toFixed(3));
}
addEventListener("scroll",()=>requestAnimationFrame(heroZoom),{passive:true});
addEventListener("resize",()=>requestAnimationFrame(heroZoom));
