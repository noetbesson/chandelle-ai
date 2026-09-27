// Gradium audio plus an owner-scoped dialogue; local UI state ends on navigation.
import {renderWebResult} from './ai.mjs';
import {candleDrawing} from './chandelier.mjs';
let ctx, current;
export function configureVoice(context){ctx=context;}
export function stopVoice(){
  if(!current)return;
  const closing=current;
  if(closing.sessionId&&ctx.identity()===closing.identity)ctx.api('/ask/chat/'+encodeURIComponent(closing.sessionId),{method:'DELETE'}).catch(()=>{});
  current.closed=true;current.deck?.destroy();stopMeter(current);current.soundContext?.close().catch(()=>{});clearTimeout(current.timer);current.abort.abort();
  current.recorder?.state==='recording'&&current.recorder.stop();
  current.stream?.getTracks().forEach(t=>t.stop());
  current.audio?.pause();if(current.url)URL.revokeObjectURL(current.url);
  current=null;
}
export function voiceLevel(samples){
  let power=0;for(const sample of samples)power+=sample*sample;
  return Math.min(1,Math.max(0,(Math.sqrt(power/(samples.length||1))-.012)*7));
}
function stopMeter(s){
  if(s.frame!==undefined)globalThis.cancelAnimationFrame?.(s.frame);
  s.frame=undefined;s.meterSource?.disconnect();s.analyser?.disconnect();s.meterSource=s.analyser=null;
  if(live(s))document.querySelector('#voice-orb')?.style?.setProperty('--voice-level','0');
}
function prepareSound(s){
  try{
    const AudioEngine=globalThis.AudioContext||globalThis.webkitAudioContext;
    if(!AudioEngine)return;
    s.soundContext ||= new AudioEngine();
    if(s.soundContext.state==='suspended')s.soundContext.resume().catch(()=>{});
  }catch{/* Native audio remains usable if the visual analyser is unavailable. */}
}
function startMeter(s,{stream,audio}){
  stopMeter(s);
  const engine=s.soundContext;
  if(!engine||engine.state!=='running'||!globalThis.requestAnimationFrame)return;
  try{
    const analyser=engine.createAnalyser();analyser.fftSize=1024;
    s.sources ||= new WeakMap();
    const source=stream?engine.createMediaStreamSource(stream):(s.sources.get(audio)||engine.createMediaElementSource(audio));
    if(audio)s.sources.set(audio,source);
    s.meterSource=source;s.analyser=analyser;source.connect(analyser);
    if(audio)analyser.connect(engine.destination); // Never route the microphone to speakers.
    const samples=new Float32Array(analyser.fftSize);let level=0;
    const draw=()=>{
      if(!live(s)||s.analyser!==analyser)return;
      analyser.getFloatTimeDomainData(samples);
      const target=['speaking','listening'].includes(s.phase)?voiceLevel(samples):0;
      level+=(target-level)*(target>level?.28:.09);
      document.querySelector('#voice-orb')?.style?.setProperty('--voice-level',level.toFixed(3));
      s.frame=requestAnimationFrame(draw);
    };draw();
  }catch{stopMeter(s);}
}
export function voiceEntry(){return `<section class="ask-conversation" aria-label="Conversation avec Chandelle"><div id="voice-panel">${panelMarkup()}</div></section>`;}
const live=s=>current===s&&!s.closed&&ctx.identity()===s.identity;
const labels={ready:'À vous de parler',listening:'Je vous écoute',thinking:'Un instant…',speaking:'Chandelle vous parle',replay:'Touchez la chandelle pour écouter',error:'Une petite pause'};
function phase(s,value,text=labels[value]){
  if(!live(s))return;
  s.phase=value;
  const orb=document.querySelector('#voice-orb');
  orb.dataset.phase=value;
  const actions={ready:'Parler à Chandelle',listening:'Terminer ma prise de parole',speaking:'Interrompre Chandelle et parler',replay:'Écouter la réponse',error:'Réessayer le micro'};
  orb.setAttribute('aria-label',actions[value]||'Chandelle réfléchit');
  orb.disabled=value==='thinking'||(!s.available&&value!=='replay');
  document.querySelector('#voice-status').textContent=text;
  document.querySelector('#voice-hint').textContent=value==='listening'?'Touchez pour terminer · 45 secondes maximum':value==='speaking'?'Touchez pour prendre la parole':value==='ready'?'Touchez la chandelle pour parler':'';
  const recommend=document.querySelector('[data-action="voice-recommend"]');
  recommend.disabled=s.starting||s.busy||value==='listening';
}
const status=(s,text)=>phase(s,'error',text);
function panelMarkup(started=false){
  return `<div class="voice-stage">
    <button type="button" id="voice-orb" class="voice-candle" data-action="${started?'voice-orb':'voice-start'}" data-phase="${started?'thinking':'idle'}" aria-label="${started?'Chandelle réfléchit':'Commencer la conversation'}" ${started?'disabled':''}>${candleDrawing()}</button>
    <p id="voice-status" class="voice-status" role="status" aria-live="polite">${started?'':'Touchez la chandelle pour commencer'}</p><small id="voice-hint">${started?'':'Une envie, une question, une sortie à deux.'}</small>
    <div class="voice-actions" ${started?'':'hidden'}><button type="button" data-action="voice-recommend">Trouver des idées</button><button type="button" data-action="voice-restart">↻ Recommencer</button><button type="button" data-action="voice-close">Terminer</button></div>
    </div><p id="voice-mode" class="muted" role="status"></p>
    <small class="muted">Catalogue et recherche web activés pour trouver des adresses et leurs prix.</small>
    <div id="voice-suggestions" class="grid spaced"></div><div id="voice-web-results"></div><div id="voice-plans" class="grid spaced"></div>
    <details class="voice-text-option"><summary>Utiliser le clavier</summary><p id="voice-text-reply"></p><form id="voice-form"><label for="voice-text">Votre message</label><textarea id="voice-text" required maxlength="1500"></textarea><button type="submit">Envoyer</button></form></details>
    <small class="voice-privacy">En parlant ou en envoyant un message, vous utilisez OpenAI pour comprendre l’échange et formuler les réponses. Les notes privées des profils ne sont pas envoyées. Le micro s’active au clic ; votre audio est transmis à Gradium. Échange privé qui expire après deux heures côté serveur, supprimé à la fermeture quand elle peut être transmise. Aucun apprentissage automatique ; programmes enregistrés pour le couple.</small>`;
}
function render(s){if(live(s))document.querySelector('#voice-panel').innerHTML=panelMarkup(true);}
async function startConversation(message=''){
  if(current?.starting)return;
  stopVoice();const s=current={identity:ctx.identity(),revision:0,available:false,starting:true,abort:new AbortController()};
  prepareSound(s);render(s);phase(s,'thinking');
  if(message){document.querySelector('#voice-text').value=message;document.querySelector('.voice-text-option').open=true;}
  try{
    const integrations=await ctx.api('/integrations');
    if(live(s)){s.available=!!integrations.gradium?.available;s.starting=false;await send(s,message);}
  }catch(e){if(live(s)){s.starting=false;status(s,e.message);}}
}
async function speak(s,text){
  if(!s.available){status(s,'Voix non configurée. Le clavier reste disponible ci-dessous.');return;}
  try{
    const blob=await ctx.audio(text,s.abort.signal);
    if(!live(s))return;
    s.audio?.pause();if(s.url)URL.revokeObjectURL(s.url);
    s.url=URL.createObjectURL(blob);const audio=s.audio=new Audio(s.url);
    const activeAudio=()=>live(s)&&s.audio===audio;
    audio.onplaying=()=>{if(activeAudio()){phase(s,'speaking');startMeter(s,{audio});}};
    audio.onwaiting=()=>{if(activeAudio())phase(s,'thinking','La voix arrive…');};
    audio.onended=()=>{if(activeAudio()){stopMeter(s);phase(s,'ready');}};
    audio.onerror=()=>{if(activeAudio()){stopMeter(s);status(s,'Lecture impossible. Réessayez ou utilisez le clavier.');}};
    try{await audio.play();}catch{if(activeAudio())phase(s,'replay');}
  }catch(e){if(live(s))status(s,'Lecture vocale indisponible : '+e.message);}
}
const escapeText=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function suggestionCards(items){
  return items.map(a=>{
    let link='';try{const url=new URL(a.website);if(['https:','http:'].includes(url.protocol))link=`<a href="${escapeText(url.href)}" target="_blank" rel="noopener noreferrer">Consulter la source</a>`;}catch{}
    return `<article class="card"><span class="badge">Piste réelle · disponibilité à vérifier</span><h3>${escapeText(a.name)}</h3><p>${escapeText(a.description||'')}</p><p>${escapeText(a.location?.address||'Adresse à confirmer')}</p><p>${a.total_couple_cost==null?'Prix à confirmer':escapeText(a.total_couple_cost)+' € pour deux, selon la source'}</p><p>${escapeText((a.reasons||[]).join(' · '))}</p><p class="muted">${escapeText((a.unknown||[]).join(' · '))}</p>${link}</article>`;
  }).join('');
}
async function send(s,text,recommend=false){
  if(!live(s)||s.busy||s.starting)return;
  s.busy=true;stopMeter(s);if(s.audio){s.audio.onplaying=s.audio.onwaiting=s.audio.onended=s.audio.onerror=null;s.audio.pause();}
  const body={message:text,session_id:s.sessionId||null,revision:s.revision||0,recommend,cloud_consent:true,web_consent:true};
  // Retry the same failed HTTP turn with the same ID; the server replays completed work.
  const fingerprint=JSON.stringify(body);
  if(s.pending?.fingerprint!==fingerprint)s.pending={fingerprint,id:globalThis.crypto.randomUUID()};
  body.request_id=s.pending.id;
  try{
    phase(s,'thinking');
    const result=await ctx.api('/ask/chat',{method:'POST',body,signal:s.abort.signal});
    if(!live(s))return;
    s.pending=null;s.sessionId=result.session_id;s.revision=result.revision;
    document.querySelector('#voice-text-reply').textContent=result.reply;
    document.querySelector('#voice-text').value='';
    document.querySelector('#voice-mode').textContent=result.warning||(result.mode==='openai'?'Dialogue OpenAI · idées issues de sources réelles':'Chaque demande est traitée par OpenAI.');
    document.querySelector('#voice-suggestions').innerHTML=suggestionCards(result.suggestions||[]);
    document.querySelector('#voice-web-results').innerHTML=result.web?renderWebResult(result.web):'';
    document.querySelector('#voice-plans').innerHTML=(result.plans||[]).map(ctx.planCard).join('');
    s.deck?.destroy();
    const target=document.querySelector('#voice-plans');
    if(ctx.renderSearch&&result.run_id)s.deck=ctx.renderSearch(target,result);
    else target.innerHTML=(result.plans||[]).map(ctx.planCard).join('');
    await speak(s,result.reply);
  }catch(e){
    if(live(s)){
      if(text){document.querySelector('#voice-text').value=text;document.querySelector('.voice-text-option').open=true;}
      document.querySelector('#voice-mode').textContent='Le message n’a pas reçu de réponse. Vous pouvez le renvoyer.';
      status(s,e.message);
    }
  }finally{if(live(s)){s.busy=false;phase(s,s.phase,document.querySelector('#voice-status').textContent);}}
}
export async function submitVoice(form){
  if(form.id!=='voice-form')return false;
  const text=document.querySelector('#voice-text').value.trim();
  if(current)await send(current,text);else if(text)await startConversation(text);
  return true;
}
// Convert a complete browser recording to the documented PCM WAV input format.
export function wavBytes(buffer){
  const frames=buffer.length,channels=buffer.numberOfChannels;
  const out=new ArrayBuffer(44+frames*2),v=new DataView(out);
  const tag=(i,s)=>[...s].forEach((c,k)=>v.setUint8(i+k,c.charCodeAt(0)));
  tag(0,'RIFF');v.setUint32(4,36+frames*2,true);tag(8,'WAVE');tag(12,'fmt ');
  v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
  v.setUint32(24,buffer.sampleRate,true);v.setUint32(28,buffer.sampleRate*2,true);
  v.setUint16(32,2,true);v.setUint16(34,16,true);tag(36,'data');v.setUint32(40,frames*2,true);
  const samples=Array.from({length:channels},(_,c)=>buffer.getChannelData(c));
  for(let i=0;i<frames;i++){let sample=0;for(const data of samples)sample+=data[i]/channels;sample=Math.max(-1,Math.min(1,sample));v.setInt16(44+i*2,sample<0?sample*32768:sample*32767,true);}
  return out;
}
async function record(s){
  if(s.busy||!s.available)return;
  if(!navigator.mediaDevices?.getUserMedia||!globalThis.MediaRecorder){status(s,'Micro indisponible. Ouvrez le site sur localhost ou HTTPS, ou écrivez votre réponse.');return;}
  prepareSound(s);s.busy=true;stopMeter(s);if(s.audio){s.audio.onplaying=s.audio.onwaiting=s.audio.onended=s.audio.onerror=null;s.audio.pause();}phase(s,'thinking','Ouverture du micro…');
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    if(!live(s)){stream.getTracks().forEach(t=>t.stop());return;}
    s.stream=stream;
    const recorder=s.recorder=new MediaRecorder(stream),chunks=[];
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onerror=()=>{stopMeter(s);stream.getTracks().forEach(t=>t.stop());s.busy=false;status(s,'Enregistrement interrompu. Réessayez ou utilisez le clavier.');};
    recorder.onstop=async()=>{
      stopMeter(s);clearTimeout(s.timer);stream.getTracks().forEach(t=>t.stop());if(!live(s))return;
      let audioContext;
      try{
        phase(s,'thinking');
        audioContext=new AudioContext({sampleRate:24000});
        const buffer=await audioContext.decodeAudioData(await new Blob(chunks,{type:recorder.mimeType}).arrayBuffer());
        if(!live(s))return;
        const result=await ctx.api('/voice/transcribe',{method:'POST',raw:new Blob([wavBytes(buffer)],{type:'audio/wav'}),headers:{'Content-Type':'audio/wav'}});
        if(!live(s))return;
        s.busy=false;
        await send(s,result.text);
      }catch(e){status(s,'Transcription impossible : '+e.message);}finally{await audioContext?.close();if(live(s)){s.busy=false;phase(s,s.phase,document.querySelector('#voice-status').textContent);}}
    };
    recorder.start();phase(s,'listening');startMeter(s,{stream});
    s.timer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},45000);
  }catch(e){s.stream?.getTracks().forEach(t=>t.stop());if(live(s)){s.busy=false;phase(s,s.phase,document.querySelector('#voice-status').textContent);status(s,'Accès au micro impossible : '+e.message);}}
}
export async function clickVoice(button){
  const action=button.dataset.action;
  if(!action?.startsWith('voice-'))return false;
  if(action==='voice-close'){
    stopVoice();document.querySelector('#voice-panel').innerHTML=panelMarkup();return true;
  }
  if(['voice-start','voice-open','voice-restart'].includes(action)){
    await startConversation();
  }else if(current){
    const s=current;
    if(action==='voice-orb'){
      if(s.recorder?.state==='recording'){phase(s,'thinking');s.recorder.stop();}
      else if(s.phase==='replay'&&s.audio){prepareSound(s);try{await s.audio.play();}catch{status(s,'Lecture bloquée. Utilisez le clavier ou réessayez.');}}
      else await record(s);
    }
    if(action==='voice-recommend')await send(s,document.querySelector('#voice-text').value.trim(),true);
  }
  return true;
}
