const pages={catalogue,meal:mealDetail,publish:publishPage,host:hostPage,bookings:bookingsPage,
 login:()=>authPage(false),register:()=>authPage(true),verify:verifyPage,account,profile:publicProfile,messages:messagesPage,
 thread:threadPage,notes:notesPage,admin:adminPage,case:casePage};
async function render(){
 const gen=++renderId;
 const [route,id]=routeParts();
 if(!options)return;
 if(dialog.open)dialog.close();
 if(route==="main"){main.focus();return;}
 showNav();
 if(!["catalogue","meal","profile","login","register"].includes(route)){
    if(!auth.user){sessionStorage.setItem("return",location.hash);go("login");return;}
    if(!auth.user.verified&&route!=="verify"){go("verify");return;}
 }
 if(route==="verify"&&auth.user?.verified){go(getReturn());return;}
 if((route==="login"||route==="register")&&auth.user){go(auth.user.verified?getReturn():"verify");return;}
 main.setAttribute("aria-busy","true");
 try{
   const html=await (pages[route]||catalogue)(id);
   if(gen===renderId){main.innerHTML=html;document.title=(main.querySelector("h1")?.textContent||"Les tables")+" · BlablaCook";}
 }catch(e){if(gen===renderId)main.innerHTML=`<div class="panel stack"><h1>Page indisponible</h1><p>${esc(e.message)}</p>${a("catalogue","Revenir aux tables")}</div>`;}
 finally{if(gen===renderId)main.removeAttribute("aria-busy");}
}
function confirmAction(title,description,act,id,label){
 openDialog(`<div class="stack"><h2>${esc(title)}</h2><p>${esc(description)}</p><div class="actions">${action(label,act,id,"primary")}${action("Revenir","dismiss")}</div></div>`);
}
document.addEventListener("click",async e=>{
 const ret=e.target.closest("[data-return]");if(ret)sessionStorage.setItem("return",ret.dataset.return);
 const el=e.target.closest("[data-act]");if(!el)return;
 const {act,id}=el.dataset;el.disabled=true;
 try{
  switch(act){
   case "logout":await api("/auth/logout","POST");auth={user:null};go("catalogue");break;
   case "verify":auth=await api("/auth/verify-email","POST",{token:auth.demo_verification});go(getReturn());break;
   case "map":case "list":mapMode=act==="map";await render();break;
   case "sector":document.getElementById("sector-"+id)?.focus();break;
   case "clear":catalogueFilters={};filterOpen=false;await render();break;
   case "book":await api(`/meals/${id}/bookings`,"POST");message("Demande envoyée à l’hôte.");await render();break;
   case "thread":{const t=await api("/conversations","POST",{meal:Number(id)});go("thread/"+t.id);break;}
   case "accept":case "reject":case "withdraw":case "confirmedCancel":{
     const op=["withdraw","confirmedCancel"].includes(act)?"cancel":act;
     await api(`/bookings/${id}/${op}`,"POST");message("Réservation mise à jour.");await render();break;
   }
   case "cancelBooking":{
     const b=(await api("/bookings/me")).find(v=>v.id===Number(id));
     confirmAction("Annuler ma réservation",b.late?"Cette annulation tardive ajoutera un avis automatique de 1★ à votre profil invité.":"La place sera libérée. Une annulation à moins de cinq heures du début ajoute un avis automatique de 1★.","confirmedCancel",id,"Confirmer l’annulation");break;
   }
   case "present":await api(`/bookings/${id}/attendance`,"POST",{present:true});message("Présence enregistrée.");await render();break;
   case "absent":confirmAction("Déclarer une absence","Cette décision ajoute un avis automatique de 1★ à l’invité.","confirmedAbsent",id,"Déclarer absent");break;
   case "confirmedAbsent":await api(`/bookings/${id}/attendance`,"POST",{present:false});message("Absence enregistrée.");await render();break;
   case "cancelMeal":confirmAction("Annuler ce repas","Les réservations seront fermées et les invités seront informés.","confirmedMeal",id,"Confirmer l’annulation");break;
   case "confirmedMeal":await api(`/meals/${id}/cancel`,"POST");message("Repas annulé.");await render();break;
   case "report":{const [kind,target]=id.split("/");openDialog(`<div class="stack"><h2>Signaler ce contenu</h2>${form("report",`<input type="hidden" name="kind" value="${esc(kind)}"><input type="hidden" name="target" value="${esc(target)}">${selectField("Motif","reason",options.reasons,"","Choisir…",true)}${area("Précisions facultatives","comment")}`,"Envoyer le signalement")}</div>`);break;}
   case "note":{const n=(await api("/notifications/me")).find(v=>v.id===Number(id));await api(`/notifications/${id}/read`,"POST");go(n.link.slice(1));break;}
   case "dismiss":dialog.close();break;
  }
 }catch(err){if(dialog.open)dialog.close();message(err.message);if(err.data?.code==="MEAL_FULL")await render();}
 finally{el.disabled=false;}
});
document.addEventListener("submit",async e=>{
 const f=e.target, kind=f.dataset.form;if(!kind)return;
 e.preventDefault();const fd=new FormData(f),d=Object.fromEntries(fd),btn=f.querySelector("[type=submit]")||e.submitter;
 if(btn?.disabled)return;if(btn)btn.disabled=true;
 if(!f.dataset.key)f.dataset.key=crypto.randomUUID();
 const errBox=f.querySelector(".form-error");errBox.textContent="";
 f.querySelectorAll(".field-error").forEach(el=>el.remove());
 f.querySelectorAll("[aria-invalid]").forEach(el=>el.removeAttribute("aria-invalid"));
 try{
  switch(kind){
   case "filters":
    filterOpen=f.querySelector("details").open;
    if(d.distance&&!d.sector)throw new Error("Choisissez un secteur pour appliquer un rayon.");
    catalogueFilters=Object.fromEntries(Object.entries(d).filter(([,v])=>v!==""));await render();break;
   case "login":case "register":
    auth=await api("/auth/"+kind,"POST",d);go(auth.user.verified?getReturn():"verify");break;
   case "publish":{
    await applyPhoto(d,fd,"image");
    for(const k of ["diets","languages","allergens"])d[k]=fd.getAll(k);
    for(const k of ["women","uncertain"])d[k]=fd.has(k);
    for(const k of ["minimum","maximum"])d[k]=Number(d[k]);
    d.duration=d.duration?Number(d.duration):null;
    for(const k of ["start","check_at"])d[k]=new Date(d[k]).toISOString();
    const problems=[];
    if(d.maximum<d.minimum)problems.push({field:"maximum",message:"Le maximum doit couvrir le minimum d’invités."});
    if(d.check_at>=d.start)problems.push({field:"check_at",message:"Le contrôle doit précéder le repas."});
    if(!d.allergens.length&&!d.uncertain)problems.push({field:"uncertain",message:"Indiquez un allergène connu ou une information incertaine."});
    if(d.kind==="Repas + activité"&&!d.activity)problems.push({field:"activity",message:"Choisissez une activité."});
    if(problems.length)throw Object.assign(new Error(problems[0].message),{data:{fields:problems}});
    const m=await api("/meals","POST",d,f.dataset.key);message("Votre repas est publié.");go("meal/"+m.id);break;
   }
   case "account":
    if(d.keep_photo)delete d.photo;delete d.keep_photo;await applyPhoto(d,fd,"photo");
    d.age=d.age?Number(d.age):null;d.public_photo=fd.has("public_photo");d.hidden_guest=fd.has("hidden_guest");
    await api("/users/me","PATCH",d);auth=await api("/auth/session");message("Profil enregistré.");await render();break;
   case "message":await api(`/conversations/${d.thread}/messages`,"POST",{body:d.body},f.dataset.key);message("Message envoyé.");await render();break;
   case "review":{
    const bid=d.booking;delete d.booking;
    for(const k of Object.keys(d))if(k!=="comment")d[k]=Number(d[k]);
    await api(`/bookings/${bid}/reviews`,"POST",d);message("Avis enregistré.");await render();break;
   }
   case "report":d.target=Number(d.target);await api("/reports","POST",d,f.dataset.key);dialog.close();message("Signalement transmis.");break;
   case "decision":await api(`/admin/reports/${d.report}/decisions`,"POST",{action:d.action,reason:d.reason});message("Décision enregistrée.");await render();break;
  }
 }catch(err){
  errBox.textContent=err.message;
  const byCode={UNKNOWN_DOMAIN:"email",EMAIL_EXISTS:"email",INVALID_DATE:"start",ORIGIN_REQUIRED:"sector"};
  const issues=err.data?.fields||[{field:byCode[err.data?.code],message:err.message}];
  for(const problem of issues){
   const field=f.elements.namedItem(problem.field);
   if(!field?.setAttribute)continue;
   field.setAttribute("aria-invalid","true");
   const hint=document.createElement("small");
   hint.className="field-error error";hint.textContent=problem.message;
   hint.id="error-"+problem.field;field.setAttribute("aria-describedby",hint.id);
   field.closest("label")?.append(hint);field.focus();
  }
 }finally{if(btn)btn.disabled=false;}
});
window.addEventListener("hashchange",()=>{window.scrollTo(0,0);render();});
document.querySelector(".skip").addEventListener("click",e=>{e.preventDefault();main.focus();});
(async()=>{
 try{[options,auth]=await Promise.all([api("/catalog/options"),api("/auth/session")]);await render();}
 catch(e){main.textContent="Le chargement a échoué. "+e.message;}
})();

