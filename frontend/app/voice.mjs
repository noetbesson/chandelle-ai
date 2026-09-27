// Turn-based Gradium discovery. Audio and dialogue stay in memory until navigation.
let ctx, current;
export function configureVoice(context){ctx=context;}
export function stopVoice(){
  if(!current)return;
  current.closed=true;stopMeter(current);current.soundContext?.close().catch(()=>{});clearTimeout(current.timer);current.abort.abort();
  current.recorder?.state==='recording'&&current.recorder.stop();
  current.stream?.getTracks().forEach(t=>t.stop());
  current.audio?.pause();if(current.url)URL.revokeObjectURL(current.url);
  current=null;
}
// The drawing stays vector-native: each flame has its own anchored group.
function candleDrawing(){
  const flame=(x,y,delay)=>`<g transform="translate(${x} ${y})"><g class="candle-flame" style="--flicker-delay:${delay}s"><path class="flame-outer" d="M0 0 C-20 -4 -20 -23 -11 -42 C-5 -55 -2 -66 -3 -75 C8 -59 11 -45 16 -31 C24 -13 13 -2 0 0Z"/><path class="flame-inner" d="M0 -8 C-7 -14 -7 -23 -2 -33 C1 -39 2 -44 2 -48 C7 -34 11 -24 9 -18 C7 -12 4 -9 0 -8Z"/></g></g>`;
  return `<svg class="voice-candles" viewBox="0 -65 300 440" aria-hidden="true" focusable="false">
    <g class="candle-ink" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M72 128 L70 116 M150 91 L150 79 M228 128 L228 116"/>
      <path d="M61 131 Q72 127 82 131 L84 250 Q72 254 61 250Z M139 95 Q150 91 161 95 L160 239 Q149 241 138 239Z M217 131 Q228 127 240 132 L239 251 Q228 254 217 251Z"/>
      <path d="M63 134 Q71 141 67 174 M141 99 Q148 107 144 158 M220 135 Q228 143 223 185" stroke-width="3"/>
      <path d="M52 253 Q72 248 92 253 L90 263 Q72 268 53 262Z M130 240 Q150 236 171 241 L168 251 Q150 254 130 250Z M207 254 Q228 249 249 254 L247 265 Q228 269 208 263Z"/>
      <path d="M60 267 Q58 288 76 288 Q88 286 84 267 M138 254 Q135 277 152 277 Q165 275 162 254 M216 269 Q213 290 230 290 Q243 286 240 269"/>
      <path d="M74 289 Q73 316 107 301 Q132 286 146 300 M230 290 Q225 315 194 301 Q171 286 155 300 M146 280 L145 309 Q136 319 151 322 Q165 319 156 309 L155 280"/>
      <path d="M143 319 Q112 308 88 334 Q77 354 109 340Z M159 320 Q187 308 211 334 Q225 354 191 340Z M142 323 Q127 344 119 360 L132 354 L133 365 Q147 342 149 328 M157 324 Q169 348 185 360 L176 346 L190 351 Q175 332 164 326" stroke-width="3.5"/>
      <path d="M150 328 L150 347 Q147 355 140 357 L129 363 Q125 367 138 368 L165 368 Q177 366 169 362 L158 357 Q152 353 153 346"/>
    </g>${flame(72,116,-.5)}${flame(150,79,-1.3)}${flame(228,116,-.9)}</svg>`;
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
export function voiceEntry(){return `<section class="hero card"><h2>Une idée de sortie ? Parlons-en.</h2><p>Un échange guidé en français pour trouver une recommandation à deux.</p><button class="primary" data-action="voice-open">🎙 Discuter avec Chandelle</button><div id="voice-panel" class="spaced"></div></section>`;}
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
  recommend.disabled=s.busy||value==='listening';
}
const status=(s,text)=>phase(s,'error',text);
function render(s){
  if(!live(s))return;
  document.querySelector('#voice-panel').innerHTML=`<div class="voice-stage">
    <button type="button" id="voice-orb" class="voice-candle" data-action="voice-orb" data-phase="thinking" aria-label="Chandelle réfléchit" disabled>${candleDrawing()}</button>
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
    audio.onplaying=()=>{if(activeAudio()){phase(s,'speaking');startMeter(s,{audio});}};
    audio.onwaiting=()=>{if(activeAudio())phase(s,'thinking','La voix arrive…');};
    audio.onended=()=>{if(activeAudio()){stopMeter(s);phase(s,'ready');}};
    audio.onerror=()=>{if(activeAudio()){stopMeter(s);status(s,'Lecture impossible. Réessayez ou utilisez le clavier.');}};
    try{await audio.play();}catch{if(activeAudio())phase(s,'replay');}
  }catch(e){if(live(s))status(s,'Lecture vocale indisponible : '+e.message);}
}
async function send(s,text,recommend=false){
  if(!live(s)||s.busy)return;
  s.busy=true;stopMeter(s);if(s.audio){s.audio.onplaying=s.audio.onwaiting=s.audio.onended=s.audio.onerror=null;s.audio.pause();}
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
    stopVoice();document.querySelector('#voice-panel').innerHTML='';return true;
  }
  if(action==='voice-open'||action==='voice-restart'){
    stopVoice();const s=current={identity:ctx.identity(),messages:[],available:false,abort:new AbortController()};
    prepareSound(s);render(s);phase(s,'thinking');
    try{const integrations=await ctx.api('/integrations');if(live(s)){s.available=!!integrations.gradium?.available;await send(s,'');}}
    catch(e){status(s,e.message);}
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
