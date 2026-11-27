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
  plate:'<circle cx="12" cy="12" r="6"/><path d="M2 3v7m2-7v7m-3 0h4m-2 0v11m18-18v18"/>'
};
function icon(name){return `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${paths[name]||""}</svg>`;}
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function dt(ts){return new Intl.DateTimeFormat("fr-FR",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}).format(ts*1000);}
function mealPhoto(image){return image.startsWith("data:image/jpeg;base64,")?image:"/static/images/"+image+".webp";}
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
  const res=await fetch("/api"+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),cache:"no-store"});
  const data=await res.json();
  if(!res.ok){
    if(res.status===401&&data.code==="SESSION_REQUIRED"&&auth.user){auth={user:null};sessionStorage.setItem("return",location.hash);location.hash="login";message("Votre session a expiré. Reconnectez-vous.");}
    throw Object.assign(new Error(data.message||"La demande a échoué."),{data,status:res.status});
  }
  return data;
}
function routeParts(){return (location.hash.slice(1)||"catalogue").split("/");}
function showNav(){
  const [route]=routeParts(), u=auth.user;
  const link=(r,t,cl="")=>a(r,t,`${cl} ${route===r?"current":""}`);
  nav.innerHTML=link("catalogue","Les tables","optional")+link("publish","Proposer un repas",u?.verified?"button":"optional")+
    (!u?link("login","Se connecter","button"):`<details><summary>${esc(u.name)}</summary><div class="menu">${
    u.verified?[["host","Mes repas"],["bookings","Mes réservations"],["messages","Messages"],["notes","Notifications"],["account","Mon profil"],...(u.admin?[["admin","Administration"]]:[])].map(([r,t])=>link(r,t)).join(""):link("verify","Vérifier mon compte")
    }${action("Se déconnecter","logout","","plain")}</div></details>`);
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
