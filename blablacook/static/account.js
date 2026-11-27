function authPage(register=false){
 const demo=register?"Inscris-toi avec ton adresse mail étudiante (université ou école). Un mail de confirmation te sera envoyé.":"Comptes de démonstration : voir le README.";
 return `<div class="form-small panel stack"><h1>${register?"Créer un compte":"Se connecter"}</h1><p class="muted">${esc(demo)}</p>${form(register?"register":"login",`${register?field("Prénom","name","text","","autocomplete=given-name required maxlength=80"):""}${field("Adresse étudiante","email","email","","autocomplete=username required")}${field("Mot de passe","password","password","",register?"minlength=8 autocomplete=new-password required":"autocomplete=current-password required")}`,register?"Créer mon compte":"Se connecter")}${register?a("login","J’ai déjà un compte"):a("register","Créer un compte étudiant")}</div>`;
}
function verifyBox(){
 return `<section class="panel stack verify-box"><h2>Confirme ton adresse étudiante</h2><p>Un mail a été envoyé à <strong>${esc(auth.user.email)}</strong>. Clique sur le lien qu’il contient ou saisis le code à 6 chiffres. Tant que ton adresse n’est pas confirmée, tu peux compléter ton profil, mais pas réserver, publier ni écrire.</p>
 ${form("code",field("Code reçu par mail","code","text","",'inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" required'),"Valider mon adresse")}<div>${action("Renvoyer le mail","resend","","plain")}</div></section>`;
}
async function verifyPage(token){
 if(token){
  history.replaceState(null,"","#verify");
  try{
   const s=await api("/auth/verify-email","POST",{token});
   if(s.user)auth=s;
  }catch(e){
   return `<div class="form-small panel stack"><h1>Lien invalide</h1><p>${esc(e.message)}</p>${auth.user&&!auth.user.verified?verifyBox():a("login","Se connecter","button")}</div>`;
  }
  showNav();
  return `<div class="form-small panel stack"><h1>Adresse vérifiée</h1><p>Ton compte est activé, bienvenue sur BlablaCook !</p>${auth.user?a("account","Compléter mon profil","button")+a("catalogue","Voir les tables"):a("login","Se connecter","button")}</div>`;
 }
 return `<div class="narrow">${head("Vérifier mon adresse")}${verifyBox()}<p>${a("account","Compléter mon profil en attendant")}</p></div>`;
}
async function account(){
 const p=await api("/users/me");
 return `<div class="narrow">${head("Mon profil",p.email)}${p.verified?"":verifyBox()}${form("account",`<section class="panel stack"><h2>Profil public</h2>${field("Prénom","name","text",p.name,"required maxlength=80")}${area("Présentation","bio",p.bio)}
 ${selectField("Avatar illustré","photo",options.photos.filter(Boolean),p.photo,"Initiale")}${p.photo.startsWith("data:")?'<label class="check"><input type="checkbox" name="keep_photo" checked>Conserver ma photo actuelle</label>':""}${photoInput("Importer une photo de profil")}${check("Rendre ma photo publique","public_photo",p.public_photo)}
 ${check("Me masquer auprès des autres invités confirmés","hidden_guest",p.hidden_guest)}</section>
 <section class="panel stack"><h2>Informations privées</h2><div class="fields">${selectField("Genre déclaré","gender",options.genders,p.gender,"Non renseigné")}${field("Âge","age","number",p.age,"min=1 max=120")}${selectField("Régime alimentaire","diet",options.profile_diets,p.diet,"Non renseigné")}${field("Allergies","allergies","text",p.allergies)}</div>
 ${placeField("Mon adresse (privée, sert aux suggestions de repas proches)",{address:"home_address",lat:"home_lat",lng:"home_lng"},{address:p.home_address,lat:p.home_lat,lng:p.home_lng})}${p.home_address?check("Effacer mon adresse","clear_home"):""}</section>`,"Enregistrer le profil")}<p>${a("profile/"+p.id,"Voir mon profil et mes avis")}</p></div>`;
}
async function publicProfile(id){
 const [p,r]=await Promise.all([api("/users/"+id),api(`/users/${id}/reviews`)]);
 const reviewList=(role)=>r.reviews.filter(v=>v.role===role).map(v=>`<div class="item"><strong>${v.score.toLocaleString("fr-FR",{maximumFractionDigits:2})} ★ ${esc(v.reason)}</strong>${v.criteria?`<p>${Object.entries(v.criteria).map(([k,x])=>esc(k)+" "+x+"/5").join(" · ")}</p>`:""}<p class="preserve">${esc(v.comment)}</p>${reportBtn("review",v.id)}</div>`).join("")||empty("Aucun avis publié.");
 return `<div class="narrow">${a("catalogue","← Les tables","back")}<div class="panel stack"><div>${avatar(p)}<h1>${esc(p.name)}</h1></div><p>${esc(p.bio)}</p>${reportBtn("user",id)}<h2>Avis en tant qu’hôte${r.host_average!==null?" · "+r.host_average+" ★":""}</h2>${reviewList("host")}
 ${auth.user?.id===Number(id)||r.guest_average!==null?`<h2>Avis en tant qu’invité${r.guest_average!==null?" · "+r.guest_average+" ★":""}</h2>${reviewList("guest")}`:""}</div></div>`;
}
async function messagesPage(){
 const threads=await api("/conversations/me"),notes=await api("/notifications/me");
 return `<div class="narrow">${head("Messages")}<div class="stack">${threads.map(t=>`<article class="item"><h3>${a("thread/"+t.id,t.group?"Chat du repas · "+t.title:t.other)}</h3><p>${esc(t.group?t.members.join(", "):t.title)}${t.readonly?" · Lecture seule":""}${notes.some(n=>!n.read&&n.link==="#thread/"+t.id)?" · Nouveau message":""}</p></article>`).join("")||empty("Pour écrire à un hôte, ouvrez la fiche de son repas.")}</div></div>`;
}
async function threadPage(id){
 const t=await api(`/conversations/${id}/messages`);
 await api(`/conversations/${id}/read`,"POST");
 return `<div class="narrow">${a("messages","← Tous les messages","back")}${head(t.group?"Chat du repas":t.other,t.group?t.title+" · "+t.members.join(", "):t.title)}<div class="stack">${t.messages.map(m=>m.system?`<p class="system-msg">${esc(m.body)} · ${esc(dt(m.created))}</p>`:`<article class="item"><strong>${esc(m.author)} · ${esc(dt(m.created))}</strong><p class="preserve">${esc(m.body)}</p>${reportBtn("message",m.id)}</article>`).join("")||empty("Commencez la conversation.")}${t.readonly?empty("Cette conversation est en lecture seule."):form("message",`<input type="hidden" name="thread" value="${t.id}">${area("Votre message","body","",true)}`,"Envoyer le message")}</div></div>`;
}
async function notesPage(){
 const n=await api("/notifications/me");
 return `<div class="narrow">${head("Notifications")}<div class="stack">${n.map(v=>`<div class="item ${v.read?"":"unread"}"><strong>${esc(v.label)}</strong><p>${esc(dt(v.created))} · ${v.read?"Lue":"Non lue"}</p><div>${action("Ouvrir","note",v.id,"secondary")}</div></div>`).join("")||empty("Aucune notification.")}</div></div>`;
}
const reportTypes={meal:"Annonce",user:"Profil",message:"Message",review:"Avis"}, reportStates={OPEN:"À traiter",IN_PROGRESS:"En instruction",CLOSED:"Classé"};
async function adminPage(){
 const list=await api("/admin/reports");
 return `<div class="narrow">${head("Signalements")}<div class="stack">${list.map(r=>`<article class="item"><h3>${a("case/"+r.id,reportTypes[r.kind]+" · "+r.reason)}</h3><p>${esc(dt(r.created))} · ${reportStates[r.status]}</p></article>`).join("")||empty("Aucun signalement.")}</div></div>`;
}
async function casePage(id){
 const r=await api("/admin/reports/"+id);
 return `<div class="narrow">${a("admin","← Signalements","back")}${head(reportTypes[r.kind]+" · "+r.reason,reportStates[r.status])}<div class="stack"><section class="panel stack"><h2>Contenu signalé</h2><p class="preserve">${esc(r.content)}</p>${r.comment?`<p>Commentaire du signalement · ${esc(r.comment)}</p>`:""}</section>
 ${r.actions.length?form("decision",`<input type="hidden" name="report" value="${r.id}">${selectField("Décision","action",r.actions,"","Choisir…",true)}${area("Motif de la décision","reason","",true)}`,"Enregistrer la décision"):""}<h2>Journal des décisions</h2>${r.audit.map(d=>`<div class="item"><strong>${esc(d.action)} · ${esc(d.moderator)}</strong><p>${esc(dt(d.created))} · ${esc(d.reason)}</p></div>`).join("")||empty("Aucune décision enregistrée.")}</div></div>`;
}

