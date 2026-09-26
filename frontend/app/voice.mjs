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
const status=(s,text)=>{if(live(s))document.querySelector('#voice-status').textContent=text;};
function controls(s,busy){
  if(!live(s))return;
  document.querySelectorAll('#voice-panel button, #voice-panel textarea').forEach(el=>{
    el.disabled=busy || (el.dataset.action==='voice-record'&&!s.available);
  });
}
function render(s){
  if(!live(s))return;
  document.querySelector('#voice-panel').innerHTML=`<p class="privacy">Au clic sur le micro, votre audio est transmis à Gradium pour transcription. Les réponses y sont envoyées pour lecture. Cet échange est temporaire et n’ajoute pas de goûts à votre mémoire ; le programme créé est enregistré pour le couple.</p>
    <div id="voice-messages" aria-live="polite">${s.lines.map(([who,text])=>`<p><strong>${who==='user'?'Vous':'Chandelle'} :</strong> ${ctx.escape(text)}</p>`).join('')}</div>
    <p id="voice-status" role="status"></p><div id="voice-audio"></div>
    <form id="voice-form"><label for="voice-text">Votre réponse (transcription modifiable)</label><textarea id="voice-text" required maxlength="1500"></textarea>
    <div class="row"><button type="button" data-action="voice-record" ${s.available?'':'disabled'}>🎙 Parler (45 s max)</button><button type="button" data-action="voice-stop" hidden>Terminer la prise</button><button type="submit">Envoyer</button><button type="button" data-action="voice-recommend">Voir ma recommandation</button><button type="button" data-action="voice-restart">Recommencer</button></div></form><div id="voice-plans" class="grid spaced"></div>`;
  if(!s.available)status(s,'Voix non configurée côté serveur. Vous pouvez déjà échanger par écrit.');
}
async function speak(s,text){
  if(!s.available)return;
  try{
    const blob=await ctx.audio(text,s.abort.signal);
    if(!live(s))return;
    s.audio?.pause();if(s.url)URL.revokeObjectURL(s.url);
    s.url=URL.createObjectURL(blob);s.audio=new Audio(s.url);s.audio.controls=true;
    document.querySelector('#voice-audio').replaceChildren(s.audio);
    try{await s.audio.play();}catch{status(s,'Appuyez sur lecture pour écouter la réponse.');}
  }catch(e){if(live(s))status(s,'Lecture vocale indisponible : '+e.message);}
}
async function send(s,text,recommend=false){
  if(!live(s)||s.busy)return;
  s.busy=true;controls(s,true);s.audio?.pause();
  const messages=[...s.messages,...(text?[text]:[])];
  try{
    status(s,'Chandelle prépare sa réponse…');
    const result=await ctx.api('/discover/chat',{method:'POST',body:{messages,recommend}});
    if(!live(s))return;
    s.messages=messages;if(text)s.lines.push(['user',text]);s.lines.push(['assistant',result.reply]);
    render(s);controls(s,true);
    document.querySelector('#voice-plans').innerHTML=(result.plans||[]).map(ctx.planCard).join('');
    await speak(s,result.reply);
  }catch(e){status(s,e.message);}finally{if(live(s)){s.busy=false;controls(s,false);}}
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
  s.busy=true;controls(s,true);s.audio?.pause();
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    if(!live(s)){stream.getTracks().forEach(t=>t.stop());return;}
    s.stream=stream;
    const recorder=s.recorder=new MediaRecorder(stream),chunks=[];
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onerror=()=>{stream.getTracks().forEach(t=>t.stop());s.busy=false;controls(s,false);status(s,'Enregistrement interrompu. Réessayez ou écrivez votre message.');};
    recorder.onstop=async()=>{
      clearTimeout(s.timer);stream.getTracks().forEach(t=>t.stop());if(!live(s))return;
      document.querySelector('[data-action="voice-stop"]').hidden=true;
      let audioContext;
      try{
        status(s,'Transcription en cours…');
        audioContext=new AudioContext({sampleRate:24000});
        const buffer=await audioContext.decodeAudioData(await new Blob(chunks,{type:recorder.mimeType}).arrayBuffer());
        if(!live(s))return;
        const result=await ctx.api('/voice/transcribe',{method:'POST',raw:new Blob([wavBytes(buffer)],{type:'audio/wav'}),headers:{'Content-Type':'audio/wav'}});
        if(!live(s))return;
        document.querySelector('#voice-text').value=result.text;
        status(s,'Vérifiez la transcription, puis cliquez sur Envoyer.');
      }catch(e){status(s,'Transcription impossible : '+e.message);}finally{await audioContext?.close();if(live(s)){s.busy=false;controls(s,false);}}
    };
    recorder.start();status(s,'Je vous écoute… Cliquez sur Terminer la prise pour transcrire.');
    const stop=document.querySelector('[data-action="voice-stop"]');stop.hidden=false;stop.disabled=false;
    s.timer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},45000);
  }catch(e){s.stream?.getTracks().forEach(t=>t.stop());if(live(s)){s.busy=false;controls(s,false);status(s,'Accès au micro impossible : '+e.message);}}
}
export async function clickVoice(button){
  const action=button.dataset.action;
  if(!action?.startsWith('voice-'))return false;
  if(action==='voice-open'||action==='voice-restart'){
    stopVoice();const s=current={identity:ctx.identity(),messages:[],lines:[],available:false,abort:new AbortController()};
    render(s);controls(s,true);
    try{const integrations=await ctx.api('/integrations');if(live(s)){s.available=!!integrations.gradium?.available;await send(s,'');}}
    catch(e){status(s,e.message);controls(s,false);}
  }else if(current){
    if(action==='voice-record')await record(current);
    if(action==='voice-stop'&&current.recorder?.state==='recording'){button.hidden=true;current.recorder.stop();}
    if(action==='voice-recommend')await send(current,document.querySelector('#voice-text').value.trim(),true);
  }
  return true;
}
