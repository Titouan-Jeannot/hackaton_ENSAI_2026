"use strict";
/* Intégration Google Maps : autocomplétion d’adresse (Places API New) et cartes à zones approximatives.
   La clé vient du serveur (GOOGLE_MAPS_API_KEY dans .env) ; sans clé, des replis lisibles sont affichés. */
let mapsReady;
function mapsKey(){return options?.maps_key||"";}
function loadGoogle(){
 if(!mapsKey())return Promise.reject(new Error("Clé Google Maps absente."));
 if(!mapsReady)mapsReady=new Promise((resolve,reject)=>{
  window.__bcMapsLoaded=()=>resolve(window.google);
  const s=document.createElement("script");
  s.src="https://maps.googleapis.com/maps/api/js?"+new URLSearchParams({key:mapsKey(),v:"weekly",loading:"async",language:"fr",region:"FR",callback:"__bcMapsLoaded"});
  s.async=true;s.onerror=()=>{mapsReady=null;reject(new Error("Google Maps n’a pas pu être chargé."));};
  document.head.append(s);
 });
 return mapsReady;
}
/* Champ adresse. names = {address, lat, lng, city?} : noms des champs envoyés au serveur. */
function placeField(label,names,current={},required=false){
 const hidden=Object.entries(names).filter(([k])=>k!=="address").map(([k,n])=>`<input type="hidden" name="${n}" value="${esc(current[k]??"")}">`).join("");
 const now=current.address?`<small class="place-current">Adresse actuelle : <strong>${esc(current.address)}</strong></small>`:"";
 if(!mapsKey())return `<div class="wide place-field"><label><span>${esc(label)}</span><input name="${names.address}" value="${esc(current.address||"")}" ${required?"required":""} maxlength="200"></label>${hidden}<small class="warn">Autocomplétion indisponible : ajoute GOOGLE_MAPS_API_KEY dans le fichier .env pour localiser l’adresse.</small></div>`;
 return `<div class="wide place-field" data-place="${esc(JSON.stringify(names))}" data-required="${required}"><span class="place-label">${esc(label)}</span>${now}<div class="place-slot"></div><input type="hidden" name="${names.address}" value="${esc(current.address||"")}">${hidden}<small>Commence à taper puis choisis une adresse dans la liste.</small></div>`;
}
async function mountPlace(box){
 const names=JSON.parse(box.dataset.place), slot=box.querySelector(".place-slot");
 const set=(key,value)=>{const el=box.querySelector(`[name="${names[key]}"]`);if(el)el.value=value??"";};
 try{
  await loadGoogle();
  const {PlaceAutocompleteElement}=await google.maps.importLibrary("places");
  const input=new PlaceAutocompleteElement({includedRegionCodes:["fr"]});
  input.setAttribute("aria-label",box.querySelector(".place-label").textContent);
  slot.replaceChildren(input);
  const pick=async place=>{
   await place.fetchFields({fields:["formattedAddress","location","addressComponents"]});
   set("address",place.formattedAddress);set("lat",place.location.lat());set("lng",place.location.lng());
   set("city",(place.addressComponents||[]).find(c=>c.types.includes("locality"))?.longText||"");
   const now=box.querySelector(".place-current");
   if(now)now.innerHTML=`Adresse choisie : <strong>${esc(place.formattedAddress)}</strong>`;
   else slot.insertAdjacentHTML("beforebegin",`<small class="place-current">Adresse choisie : <strong>${esc(place.formattedAddress)}</strong></small>`);
  };
  input.addEventListener("gmp-select",e=>pick(e.placePrediction.toPlace()));
  input.addEventListener("gmp-placeselect",e=>pick(e.place)); // anciennes versions de l’API
 }catch(e){slot.innerHTML=`<p class="warn">${esc(e.message)}</p>`;}
}
/* Carte : data = {circles:[{lat,lng,radius,title,href}], marker:{lat,lng}|null, home:{lat,lng}|null} */
function mapBox(data,label){return `<div class="gmap" role="region" aria-label="${esc(label)}" data-map="${esc(JSON.stringify(data))}">${mapsKey()?'<p class="muted">Chargement de la carte…</p>':'<p class="muted">Carte indisponible : ajoute GOOGLE_MAPS_API_KEY dans le fichier .env.</p>'}</div>`;}
async function mountMap(box){
 const data=JSON.parse(box.dataset.map);
 try{
  await loadGoogle();
  const {Map,Circle,InfoWindow}=await google.maps.importLibrary("maps");
  const {AdvancedMarkerElement,PinElement}=await google.maps.importLibrary("marker");
  const first=data.marker||data.circles[0]||data.home||{lat:48.1113,lng:-1.68};
  const map=new Map(box,{center:first,zoom:14,mapId:"DEMO_MAP_ID",streetViewControl:false,mapTypeControl:false,fullscreenControl:false});
  const info=new InfoWindow(), bounds=new google.maps.LatLngBounds();
  for(const c of data.circles){
   const circle=new Circle({map,center:{lat:c.lat,lng:c.lng},radius:c.radius,fillColor:"#b94427",fillOpacity:.22,strokeColor:"#a73c24",strokeWeight:1.5});
   bounds.union(circle.getBounds());
   if(c.href)circle.addListener("click",()=>{
    const link=document.createElement("a");link.href=c.href;link.textContent=c.title;
    info.setContent(link);info.setPosition({lat:c.lat,lng:c.lng});info.open({map});
   });
  }
  if(data.marker){new AdvancedMarkerElement({map,position:data.marker,title:"Adresse du repas"});bounds.extend(data.marker);}
  if(data.home){new AdvancedMarkerElement({map,position:data.home,title:"Chez moi",content:new PinElement({background:"#344d38",borderColor:"#344d38",glyphColor:"#fff"}).element});}
  if(data.circles.length>1)map.fitBounds(bounds,24);
 }catch(e){box.innerHTML=`<p class="warn">${esc(e.message)}</p>`;}
}
function mountWidgets(root){
 root.querySelectorAll("[data-place]").forEach(mountPlace);
 root.querySelectorAll("[data-map]").forEach(mountMap);
}
function km(d){return d<1?`${Math.round(d*10)*100} m`:`${d.toLocaleString("fr-FR",{maximumFractionDigits:1})} km`;}
function distanceKm(a,b){
 const r=Math.PI/180, dLat=(b.lat-a.lat)*r, dLng=(b.lng-a.lng)*r;
 const h=Math.sin(dLat/2)**2+Math.cos(a.lat*r)*Math.cos(b.lat*r)*Math.sin(dLng/2)**2;
 return 2*6371*Math.asin(Math.sqrt(h));
}
function homePoint(){const u=auth.user;return u&&u.home_lat!=null&&u.home_lng!=null?{lat:u.home_lat,lng:u.home_lng}:null;}
