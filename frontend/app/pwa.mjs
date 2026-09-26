import {clearDrafts} from './share-store.mjs';
let promptEvent;
const status=document.querySelector('[data-install-status]');
function message(text){if(status)status.textContent=text;}
if('serviceWorker' in navigator && globalThis.isSecureContext){
  navigator.serviceWorker.register('/sw.js',{scope:'/',type:'module'}).then(()=>navigator.serviceWorker.ready).then(()=>message('La réception est prête dans ce navigateur. Installez Chandelle pour l’ajouter au partage Android.')).catch(()=>message('La réception des partages n’a pas pu être activée. Utilisez l’import manuel.'));
}else message('Ouvrez Chandelle en HTTPS pour activer le partage. Une adresse HTTP du réseau local ne suffit pas.');
globalThis.addEventListener('beforeinstallprompt',event=>{event.preventDefault();promptEvent=event;const button=document.querySelector('[data-install]');if(button)button.hidden=false;});
document.querySelector('[data-install]')?.addEventListener('click',async()=>{
  if(!promptEvent)return;const event=promptEvent;promptEvent=null;await event.prompt();await event.userChoice;document.querySelector('[data-install]').hidden=true;
});
document.querySelector('[data-clear-shares]')?.addEventListener('click',async()=>{
  try{await clearDrafts();message('Les partages en attente sur cet appareil ont été supprimés.');}catch(error){message(error.message);}
});
