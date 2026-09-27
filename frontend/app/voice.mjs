// Turn-based Gradium discovery. Audio and dialogue stay in memory until navigation.
let ctx, current;
export function configureVoice(context){ctx=context;}
export function stopVoice(){
  if(!current)return;
  current.closed=true;clearTimeout(current.timer);current.abort.abort();
  current.recorder?.state==='recording'&&current.recorder.stop();
  current.stream?.getTracks().forEach(t=>t.stop());
  current.audio?.pause();if(current.url)URL.revokeObjectURL(current.url);
  current=null;
}
export function voiceEntry(){return `<section class="hero card"><h2>Une idée de sortie ? Parlons-en.</h2><p>Un échange guidé en français pour trouver une recommandation à deux.</p><button class="primary" data-action="voice-open">🎙 Discuter avec Chandelle</button><div id="voice-panel" class="spaced"></div></section>`;}
const live=s=>current===s&&!s.closed&&ctx.identity()===s.identity;
const labels={ready:'À vous de parler',listening:'Je vous écoute',thinking:'Un instant…',speaking:'Chandelle vous parle',replay:'Touchez le cercle pour écouter',error:'Une petite pause'};
function phase(s,value,text=labels[value]){
  if(!live(s))return;
  s.phase=value;
  const orb=document.querySelector('#voice-orb');
  orb.dataset.phase=value;
  const actions={ready:'Parler à Chandelle',listening:'Terminer ma prise de parole',speaking:'Interrompre Chandelle et parler',replay:'Écouter la réponse',error:'Réessayer le micro'};
  orb.setAttribute('aria-label',actions[value]||'Chandelle réfléchit');
  orb.disabled=value==='thinking'||(!s.available&&value!=='replay');
  document.querySelector('#voice-status').textContent=text;
  document.querySelector('#voice-hint').textContent=value==='listening'?'Touchez pour terminer · 45 secondes maximum':value==='speaking'?'Touchez pour prendre la parole':value==='ready'?'Touchez le cercle pour parler':'';
  const recommend=document.querySelector('[data-action="voice-recommend"]');
  recommend.disabled=s.busy||value==='listening';
}
const status=(s,text)=>phase(s,'error',text);
function render(s){
  if(!live(s))return;
  document.querySelector('#voice-panel').innerHTML=`<div class="voice-stage">
    <button type="button" id="voice-orb" class="voice-orb" data-action="voice-orb" data-phase="thinking" aria-label="Chandelle réfléchit" disabled><span class="voice-orb-core" aria-hidden="true"></span></button>
    <p id="voice-status" class="voice-status" role="status" aria-live="polite"></p><small id="voice-hint"></small>
    <div class="voice-actions"><button type="button" data-action="voice-recommend">Voir ma recommandation</button><button type="button" data-action="voice-restart">↻ Recommencer</button><button type="button" data-action="voice-close">Quitter</button></div>
    </div><div id="voice-plans" class="grid spaced"></div>
    <details class="voice-text-option"><summary>Utiliser le clavier</summary><p id="voice-text-reply"></p><form id="voice-form"><label for="voice-text">Votre réponse</label><textarea id="voice-text" required maxlength="1500"></textarea><button type="submit">Envoyer</button></form></details>
    <small class="voice-privacy">Le micro s’active au clic. Votre audio est transmis à Gradium. Échange temporaire, programme enregistré pour le couple.</small>`;
}
async function speak(s,text){
  if(!s.available){status(s,'Voix non configurée. Le clavier reste disponible ci-dessous.');return;}
  try{
    const blob=await ctx.audio(text,s.abort.signal);
    if(!live(s))return;
    s.audio?.pause();if(s.url)URL.revokeObjectURL(s.url);
    s.url=URL.createObjectURL(blob);const audio=s.audio=new Audio(s.url);
    const activeAudio=()=>live(s)&&s.audio===audio;
    audio.onplaying=()=>{if(activeAudio())phase(s,'speaking');};
    audio.onwaiting=()=>{if(activeAudio())phase(s,'thinking','La voix arrive…');};
    audio.onended=()=>{if(activeAudio())phase(s,'ready');};
    audio.onerror=()=>{if(activeAudio())status(s,'Lecture impossible. Réessayez ou utilisez le clavier.');};
    try{await audio.play();}catch{if(activeAudio())phase(s,'replay');}
  }catch(e){if(live(s))status(s,'Lecture vocale indisponible : '+e.message);}
}
async function send(s,text,recommend=false){
  if(!live(s)||s.busy)return;
  s.busy=true;if(s.audio){s.audio.onplaying=s.audio.onwaiting=s.audio.onended=s.audio.onerror=null;s.audio.pause();}
  const messages=[...s.messages,...(text?[text]:[])];
  try{
    phase(s,'thinking');
    const result=await ctx.api('/discover/chat',{method:'POST',body:{messages,recommend}});
    if(!live(s))return;
    s.messages=messages;
    document.querySelector('#voice-text-reply').textContent=result.reply;
    document.querySelector('#voice-text').value='';
    document.querySelector('#voice-plans').innerHTML=(result.plans||[]).map(ctx.planCard).join('');
    await speak(s,result.reply);
  }catch(e){status(s,e.message);}finally{if(live(s)){s.busy=false;phase(s,s.phase,document.querySelector('#voice-status').textContent);}}
}
export async function submitVoice(form){
  if(form.id!=='voice-form')return false;
  if(current)await send(current,document.querySelector('#voice-text').value.trim());
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
  s.busy=true;if(s.audio){s.audio.onplaying=s.audio.onwaiting=s.audio.onended=s.audio.onerror=null;s.audio.pause();}phase(s,'thinking','Ouverture du micro…');
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    if(!live(s)){stream.getTracks().forEach(t=>t.stop());return;}
    s.stream=stream;
    const recorder=s.recorder=new MediaRecorder(stream),chunks=[];
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onerror=()=>{stream.getTracks().forEach(t=>t.stop());s.busy=false;status(s,'Enregistrement interrompu. Réessayez ou utilisez le clavier.');};
    recorder.onstop=async()=>{
      clearTimeout(s.timer);stream.getTracks().forEach(t=>t.stop());if(!live(s))return;
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
    recorder.start();phase(s,'listening');
    s.timer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},45000);
  }catch(e){s.stream?.getTracks().forEach(t=>t.stop());if(live(s)){s.busy=false;phase(s,s.phase,document.querySelector('#voice-status').textContent);status(s,'Accès au micro impossible : '+e.message);}}
}
export async function clickVoice(button){
  const action=button.dataset.action;
  if(!action?.startsWith('voice-'))return false;
  if(action==='voice-close'){
    stopVoice();document.querySelector('#voice-panel').innerHTML='';return true;
  }
  if(action==='voice-open'||action==='voice-restart'){
    stopVoice();const s=current={identity:ctx.identity(),messages:[],available:false,abort:new AbortController()};
    render(s);phase(s,'thinking');
    try{const integrations=await ctx.api('/integrations');if(live(s)){s.available=!!integrations.gradium?.available;await send(s,'');}}
    catch(e){status(s,e.message);}
  }else if(current){
    const s=current;
    if(action==='voice-orb'){
      if(s.recorder?.state==='recording'){phase(s,'thinking');s.recorder.stop();}
      else if(s.phase==='replay'&&s.audio){try{await s.audio.play();}catch{status(s,'Lecture bloquée. Utilisez le clavier ou réessayez.');}}
      else await record(s);
    }
    if(action==='voice-recommend')await send(s,document.querySelector('#voice-text').value.trim(),true);
  }
  return true;
}
