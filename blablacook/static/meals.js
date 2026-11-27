function card(m){
  const href=`#meal/${m.id}`;
  return `<article class="card"><div class="photo-wrap"><a href="${href}" aria-label="Découvrir ${esc(m.title)}"><img class="card-photo" src="${esc(mealPhoto(m.image))}" alt=""></a><span class="badge">${icon("group")} ${m.available?`${m.available} place${m.available>1?"s":""}`:"Complet · demandes ouvertes"}</span></div>
  <div class="card-body"><span class="date">${icon("date")} ${esc(dt(m.start))}</span><h3><a href="${href}">${esc(m.title)}</a></h3><p class="meta">${icon("pin")} ${esc(m.city||"Lieu communiqué après acceptation")}${homePoint()?" · à ~"+km(distanceKm(homePoint(),m.area)):""} · ${esc(m.mood)}</p><p class="meta">${esc([m.activity||m.kind,m.women?"Entre femmes":"",m.uncertain?"Allergènes incertains":""].filter(Boolean).join(" · "))}</p></div>
  <div class="card-foot">${avatar(m.host)}<a href="#profile/${m.host.id}">Chez ${esc(m.host.name)}</a><a class="arrow" href="${href}" aria-label="Voir ${esc(m.title)}">↗</a></div></article>`;
}
function filterMarkup(){
  const f=catalogueFilters,o=options;
  return `<form data-form="filters"><div class="filters"><label class="search"><span>Recherche</span>${icon("search")}<input type="search" name="search" value="${esc(f.search)}" placeholder="Un plat, un mot-clé…"></label>
  ${field("Date","date","date",f.date)}
  <button class="primary">Rechercher</button></div><details class="filter-area" ${filterOpen?"open":""}><summary>Plus de filtres</summary><div class="fields">
  ${homePoint()?field("Rayon autour de chez moi (km)","distance","number",f.distance,'min="0" step="0.1"'):""}${selectField("Régime","diet",o.diets,f.diet,"Tous")}${selectField("Écarter un allergène déclaré","allergen",o.allergens,f.allergen,"Aucun")}
  ${selectField("Langue","language",o.languages,f.language,"Toutes")}${selectField("Ambiance","mood",o.moods,f.mood,"Toutes")}${selectField("Type","kind",["Repas seul","Repas + activité"],f.kind,"Tous")}
  ${selectField("Activité","activity",o.activities,f.activity,"Toutes")}${check("Entre femmes","women",!!f.women)}${check("Places disponibles","available",!!f.available)}</div>
  <div class="actions" style="margin-top:12px"><button class="secondary">Appliquer les filtres</button>${action("Réinitialiser","clear","","plain")}</div></details><p class="form-error" role="alert"></p></form>`;
}
function mapHtml(rows){
  const groups={};
  for(const m of rows)(groups[m.city||"Autres"]??=[]).push(m);
  const circles=rows.map(m=>({...m.area,title:m.title+" · "+dt(m.start),href:"#meal/"+m.id}));
  return `${mapBox({circles,home:homePoint()},"Carte des zones approximatives des repas")}<p class="muted">Chaque cercle indique une zone approximative : l’adresse exacte n’est jamais affichée publiquement.</p>
  <div class="stack maplist">${Object.entries(groups).map(([k,v])=>`<section class="item"><h3>${esc(k)}</h3>${v.map(m=>a("meal/"+m.id,m.title+" · "+dt(m.start))).join("")}</section>`).join("")}</div>`;
}
async function suggestionsHtml(){
  const s=await api("/meals/suggestions").catch(()=>null);
  if(!s)return "";
  if(s.needs_address)return `<section class="suggestions panel"><h2>Des repas près de chez toi</h2><p>Ajoute ton adresse (elle reste privée) pour voir en priorité les tables proches de chez toi.</p>${a("account","Renseigner mon adresse","button")}</section>`;
  return `<section class="suggestions"><div class="section-head"><h2>Près de chez toi</h2></div>${s.meals.length?`<div class="cards">${s.meals.map(card).join("")}</div>`:empty("Aucune table avec des places libres à moins de 10 km pour l’instant.")}</section>`;
}
async function catalogue(){
  const f={...catalogueFilters};
  if(f.distance&&homePoint())Object.assign(f,homePoint());else delete f.distance;
  if(f.date){const d=new Date(f.date+"T00:00:00");f.after=d.getTime()/1000;d.setDate(d.getDate()+1);f.before=d.getTime()/1000;delete f.date;}
  const rows=await api("/meals?"+new URLSearchParams(f));
  rows.sort((a,b)=>Number(!a.available)-Number(!b.available)||a.start-b.start);
  return `${auth.user?await suggestionsHtml():""}<section class="hero"><div class="hero-text"><h1>À table,<br><em>ensemble.</em></h1><p>Découvre les repas faits maison que des étudiants partagent près de chez toi.</p></div><img src="static/images/table.webp" alt="Des étudiants partagent des plats autour d’une table"></section>
  <section><div class="section-head"><h2>Les tables à venir</h2><div class="toggle" aria-label="Affichage"><button data-act="list" aria-pressed="${!mapMode}">${icon("list")} Liste</button><button data-act="map" aria-pressed="${mapMode}">${icon("map")} Carte</button></div></div>
  ${filterMarkup()}<p class="result-count">${rows.length} table${rows.length>1?"s":""} à découvrir</p>${rows.length?(mapMode?mapHtml(rows):`<div class="cards">${rows.map(card).join("")}</div>`):empty("Aucun repas ne correspond à cette recherche.")}</section>`;
}
async function mealDetail(id){
  const u=auth.user;
  const p=u?.verified?await api(`/meals/${id}/personal`):null;
  const m=p?p.meal:await api(`/meals/${id}`), b=p?.booking, isHost=m.host.id===u?.id;
  let controls;
  if(!u?.verified)controls=loginLink("#meal/"+id);
  else if(isHost)controls=a("host","Gérer les demandes","button");
  else controls=`${b?`<p>${badge(states[b.status])}</p>`:""}${p.can_request?action("Demander une place","book",id,"primary"):""}${b?.overlap?'<p class="warn">Ce repas chevauche une autre de vos demandes ou réservations.</p>':""}${b?a("bookings","Mes réservations"):""}${!p.can_request&&!b?'<p class="muted">Ce repas est réservé aux étudiantes vérifiées déclarant « Femme ».</p>':""}
  ${p.can_message?action("Écrire à l’hôte","thread",id):""}`;
  return `${a("catalogue","← Toutes les tables","back")}<div class="detail-grid"><section class="stack"><figure class="stack"><img class="meal-img" src="${esc(mealPhoto(m.image))}" alt="${esc(m.menu)}">${photoCredit(m)}</figure><h1>${esc(m.title)}</h1><p>${esc(m.description)}</p><div class="panel stack"><h2>Au menu</h2><p>${esc(m.menu)}</p><h3>Ingrédients</h3><p>${esc(m.ingredients)}</p><h3>Allergènes</h3><p>${esc(m.allergens.join(", "))}${m.uncertain?" · Information incertaine":""}</p>
  <div class="tags">${[...m.diets,...m.languages,m.mood,m.activity||m.kind,...(m.women?["Entre femmes"]:[])].map(t=>`<span>${esc(t)}</span>`).join("")}</div></div></section>
  <aside class="panel stack"><p class="eyedate">${icon("date")} ${esc(dt(m.start))}</p><h2>Chez ${esc(m.host.name)}</h2><p>${icon("pin")} ${esc(m.city||"Zone approximative")}${homePoint()?" · à ~"+km(distanceKm(homePoint(),m.area))+" de chez toi":""}</p><p>${m.status==="OPEN"?`${m.available?`${m.available} place(s) sur ${m.maximum}`:"Complet · demandes ouvertes"}`:states[m.status]} · ${m.duration||90} min</p>${p?.address?`<div class="success"><strong>Adresse du repas</strong><p>${esc(p.address)}</p></div>`:p?.address_at?`<p class="warn">L’adresse exacte te sera dévoilée le ${esc(dt(p.address_at))}, une heure avant le repas.</p>`:""}
  ${mapBox({circles:p?.location?[]:[m.area],marker:p?.location||null,home:homePoint()},p?.location?"Carte de l’adresse du repas":"Carte de la zone approximative du repas")}<small class="muted">${p?.location?"Adresse exacte":"Zone approximative d’environ "+m.area.radius+" m autour du lieu"}</small>${p?.guests?.length?`<p>À table avec ${p.guests.map(g=>a("profile/"+g.id,g.name)).join(", ")}.</p>`:""}
  ${p?.group_thread?a("thread/"+p.group_thread,"Ouvrir le chat du repas","button"):""}${controls}<hr class="line">${a("profile/"+m.host.id,"Voir le profil de "+m.host.name)}${reportBtn("meal",id)}</aside></div>`;
}
function publishPage(){
 const o=options;
 return `<div class="narrow">${head("Proposer un repas","Les étudiants pourront demander une place dès la publication.")}
 ${form("publish",`<section class="panel stack"><h2>Le repas</h2>${field("Titre","title","text","","required maxlength=80")}${area("Description","description")}${area("Menu","menu","",true)}${area("Ingrédients","ingredients","",true)}
 ${choice("Allergènes connus","allergens",o.allergens)}${check("Information incertaine sur les allergènes","uncertain")}${choice("Régimes","diets",o.diets,[o.diets[0]])}${choice("Langues","languages",o.languages,["Français"])}
 <div class="fields">${selectField("Ambiance","mood",o.moods,"Conviviale",null)}${selectField("Type de repas","kind",["Repas seul","Repas + activité"],"Repas seul",null)}${selectField("Activité associée","activity",o.activities,"","Aucune")}
 </div><div class="wide photo-auto"><span class="place-label">Photo d’illustration</span><input type="hidden" name="image" value=""><figure class="stack"><img class="photo-preview" src="static/images/table.webp" alt="Aperçu de la photo du repas"><small class="photo-note muted">Une photo est choisie automatiquement d’après le titre.</small></figure>${photoInput("Ou importer ta propre photo du repas")}</div></section>
 <section class="panel stack"><h2>Le rendez-vous</h2><div class="fields">${field("Début","start","datetime-local","","required")}${field("Durée en minutes (facultatif)","duration","number","","min=1 max=10080")}
 </div>${placeField("Adresse du repas (privée)",{address:"address",lat:"lat",lng:"lng",city:"city"},{},true)}<small>Les étudiants ne voient qu’une zone d’environ 500 m. L’adresse exacte est dévoilée aux invités acceptés une heure avant le repas.</small></section>
 <section class="panel stack"><h2>Les invités</h2><div class="fields">${field("Minimum d’invités","minimum","number",1,"min=1 required")}${field("Maximum d’invités","maximum","number",4,"min=1 required")}${field("Date limite pour atteindre le minimum d’invités","check_at","datetime-local","","required")}</div>
 <small>Si le minimum d’invités n’est pas atteint à cette date, tu seras prévenu·e. Le repas n’est pas annulé automatiquement : tu pourras le maintenir ou l’annuler.</small>
 ${check("Organiser un repas entre femmes","women")}<small>Cette option est ouverte aux hôtes déclarant « Femme » sur leur profil. Après publication, les informations du repas sont définitives.</small></section>`,"Publier le repas")}</div>`;
}
function reviewEntry(b,host){
 if(b.mine)return `<p>Votre avis · ${esc(states[b.mine.status])} · ${b.mine.score.toFixed(1)} ★</p>`;
 if(!b.review_open)return "";
 const keys=host?[["Note globale","global_score"]]:[["Accueil","accueil"],["Ambiance","ambiance"],["Repas","repas"]];
 return `<details><summary>Déposer un avis</summary>${form("review",`<input type="hidden" name="booking" value="${b.id}"><div class="fields">${keys.map(([l,k])=>field(l+" (1 à 5)",k,"number","","min=1 max=5 required")).join("")}</div>${area("Commentaire facultatif","comment")}`,"Envoyer mon avis")}</details>`;
}
async function hostPage(){
 const rows=await api("/meals/mine");
 const html=await Promise.all(rows.map(async p=>{
   const m=p.meal, bs=await api(`/meals/${m.id}/bookings`);
   return `<article class="panel stack"><div><h2>${a("meal/"+m.id,m.title)}</h2><p class="sub">${esc(dt(m.start))} · ${states[m.status]} · ${m.maximum-m.available}/${m.maximum} invités confirmés · minimum ${m.minimum} à atteindre avant le ${esc(dt(p.check_at))}</p></div>
   ${p.warning?'<p class="warn">Le minimum d’invités n’est pas atteint.</p>':""}${bs.some(b=>b.attendance_open)?'<p class="warn">Le repas est terminé. Renseignez les présences pour le clôturer.</p>':""}
   ${bs.length?bs.map(b=>`<div class="item"><strong>${a("profile/"+b.guest.id,b.guest.name)}</strong><p>${esc(states[b.status])}</p><div class="actions">${b.status==="PENDING"&&b.before_start?action("Accepter","accept",b.id,"primary")+action("Refuser","reject",b.id):""}${b.attendance_open?action("Présent","present",b.id,"primary")+action("Absent","absent",b.id):""}</div>${reviewEntry(b,true)}</div>`).join(""):empty("Aucune demande pour le moment.")}
   ${p.can_cancel?`<div>${action("Annuler le repas","cancelMeal",m.id,"plain")}</div>`:""}</article>`;
 }));
 return `<div class="narrow">${head("Mes repas")}<div class="stack">${a("publish","Proposer un repas","button")}${html.join("")||empty("Vous n’avez pas encore proposé de repas.")}</div></div>`;
}
async function bookingsPage(){
 const rows=await api("/bookings/me");
 return `<div class="narrow">${head("Mes réservations")}<div class="stack">${rows.map(b=>`<article class="panel stack"><h2>${a("meal/"+b.meal,b.title)}</h2><p>${esc(dt(b.start))} · ${esc(states[b.status])}</p>${b.overlap?'<p class="warn">Ce repas chevauche une autre de vos demandes ou réservations.</p>':""}<div class="actions">${b.before_start&&["PENDING","ACCEPTED"].includes(b.status)?action(b.status==="PENDING"?"Retirer ma demande":"Annuler ma réservation",b.status==="ACCEPTED"?"cancelBooking":"withdraw",b.id):""}${a("meal/"+b.meal,"Voir la fiche")}</div>${reviewEntry(b,false)}</article>`).join("")||empty("Vos demandes et confirmations apparaîtront ici.")}</div></div>`;
}

