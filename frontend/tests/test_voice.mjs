import assert from 'node:assert/strict';
import {configureVoice,voiceEntry,clickVoice,submitVoice,stopVoice,wavBytes,voiceLevel} from '../app/voice.mjs';

const nodes=new Map();
const node=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',value:'',dataset:{},style:{values:{},setProperty(k,v){this.values[k]=v;}},setAttribute(k,v){this[k]=v;},replaceChildren(){}});return nodes.get(selector);};
globalThis.document={querySelector:node,querySelectorAll:()=>[]};
let identity='a',calls=[];
const context={identity:()=>identity,escape:s=>s.replaceAll('<','&lt;'),planCard:p=>`PLAN ${p.id}`,
  audio:async()=>{throw Error('Provider unavailable');},api:async(path,options)=>{
    calls.push([path,options]);
    if(path==='/integrations')return {gradium:{available:false}};
    return {reply:'Bonjour <test>',plans:options.body.recommend?[{id:'real-plan'}]:[]};
  }};
configureVoice(context);
assert.match(voiceEntry(),/data-action="voice-start"/);
assert.match(voiceEntry(),/voice-candles/);
assert.doesNotMatch(voiceEntry(),/Discuter avec Chandelle|data-action="voice-open"/);
assert.equal(calls.length,0,'Rendering the idle candle must not contact any endpoint');
await clickVoice({dataset:{action:'voice-start'}});
assert.equal(node('#voice-text-reply').textContent,'Bonjour <test>');
assert.doesNotMatch(node('#voice-panel').innerHTML,/voice-messages|voice-audio|transcription modifiable/);
assert.match(node('#voice-panel').innerHTML,/voice-orb/);
assert.match(node('#voice-panel').innerHTML,/audio est transmis à Gradium/);
assert.match(voiceEntry(),/OpenAI pour comprendre l’échange/);
assert.doesNotMatch(voiceEntry(),/id="voice-(cloud|web)"|Sans OpenAI/);
assert.match(voiceEntry(),/recherche web activés/);
node('#voice-text').value='Une balade';
await submitVoice({id:'voice-form'});
assert.equal(calls.at(-1)[1].body.message,'Une balade');
assert.equal(calls.at(-1)[1].body.cloud_consent,true);
assert.equal(calls.at(-1)[1].body.web_consent,true);
assert.ok(calls.at(-1)[1].body.request_id);
node('#voice-text').value='';
await clickVoice({dataset:{action:'voice-recommend'}});
assert.equal(calls.at(-1)[1].body.recommend,true);
assert.match(node('#voice-plans').innerHTML,/real-plan/);

// A late response from A must never render into B's screen.
let resolve;
configureVoice({...context,api:async(path)=>path==='/integrations'?{gradium:{available:false}}:new Promise(r=>{resolve=r;})});
const opening=clickVoice({dataset:{action:'voice-start'}});
await new Promise(r=>setTimeout(r,0));
stopVoice();identity='b';node('#voice-panel').innerHTML='B PRIVATE SCREEN';
resolve({reply:'A PRIVATE RESPONSE',plans:[]});await opening;
assert.equal(node('#voice-panel').innerHTML,'B PRIVATE SCREEN');

// Permission granted after navigation must immediately release the microphone.
configureVoice({...context,api:async(path)=>path==='/integrations'?{gradium:{available:true}}:{reply:'Bonjour',plans:[]}});
await clickVoice({dataset:{action:'voice-start'}});
let permission,stops=0;
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:()=>new Promise(r=>{permission=r;})}}});
globalThis.MediaRecorder=class {};
const recording=clickVoice({dataset:{action:'voice-orb'}});
stopVoice();permission({getTracks:()=>[{stop(){stops++;}}]});await recording;
assert.equal(stops,1);

// Colour/motion follows real playback events, not the completion of HTTP synthesis.
let playback;
globalThis.Audio=class {constructor(){playback=this;} async play(){this.onplaying?.();} pause(){}};
configureVoice({...context,audio:async()=>new Blob(['audio']),api:async(path)=>path==='/integrations'?{gradium:{available:true}}:{reply:'Question',plans:[]}});
await clickVoice({dataset:{action:'voice-start'}});
assert.equal(node('#voice-orb').dataset.phase,'speaking');
playback.onended();
assert.equal(node('#voice-orb').dataset.phase,'ready');
assert.match(node('#voice-status').textContent,/À vous/);
const previous=playback;
await clickVoice({dataset:{action:'voice-close'}});
node('#voice-status').textContent='CLOSED';previous.onended();
assert.equal(node('#voice-status').textContent,'CLOSED');

// Recording is transcribed and sent automatically, with no visible transcript.
let recorder;
globalThis.MediaRecorder=class {constructor(){recorder=this;this.state='inactive';} start(){this.state='recording';} stop(){this.state='inactive';this.done=this.onstop?.();}};
globalThis.AudioContext=class {async decodeAudioData(){return {length:2,numberOfChannels:1,sampleRate:24000,getChannelData:()=>new Float32Array([0,0])};}async close(){}};
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}]})}}});
calls=[];let failSpokenTurn=false;
configureVoice({...context,audio:async()=>new Blob(['audio']),api:async(path,options)=>{
 calls.push([path,options]);
 if(path==='/integrations')return {gradium:{available:true}};
 if(path==='/voice/transcribe')return {text:'Une balade à deux'};
 if(path==='/ask/chat'&&failSpokenTurn)throw Error('OpenAI indisponible');
 return {reply:'Question suivante',plans:[]};
}});
await clickVoice({dataset:{action:'voice-start'}});playback.onended();
await clickVoice({dataset:{action:'voice-orb'}});
assert.equal(node('#voice-orb').dataset.phase,'listening');
await clickVoice({dataset:{action:'voice-orb'}});await recorder.done;
assert.equal(calls.at(-1)[1].body.message,'Une balade à deux');
assert.equal(calls.at(-1)[1].body.cloud_consent,true,'Transcribed speech always goes through OpenAI');
assert.equal(node('#voice-orb').dataset.phase,'speaking');
playback.onended();failSpokenTurn=true;
await clickVoice({dataset:{action:'voice-orb'}});
await clickVoice({dataset:{action:'voice-orb'}});await recorder.done;
assert.equal(node('#voice-text').value,'Une balade à deux','Failed speech can be resubmitted without another recording');
assert.equal(node('.voice-text-option').open,true);
assert.equal(node('#voice-status').textContent,'OpenAI indisponible');
failSpokenTurn=false;
stopVoice();

// Measured energy drives flames. Microphone analysis must never feed speakers.
assert.equal(voiceLevel(new Float32Array([0,0])),0);
assert.equal(voiceLevel(new Float32Array([.005,-.005])),0);
assert.ok(voiceLevel(new Float32Array([.1,-.1]))>voiceLevel(new Float32Array([.03,-.03])));
assert.equal(voiceLevel(new Float32Array([1,-1])),1);
let amplitude=.12,frameNumber=0,closedContexts=0,mediaSources=0;
const frames=new Map(),connections=[];
globalThis.requestAnimationFrame=callback=>{frames.set(++frameNumber,callback);return frameNumber;};
globalThis.cancelAnimationFrame=id=>frames.delete(id);
const audioNode=kind=>({kind,connect(target){connections.push([kind,target.kind]);},disconnect(){}});
globalThis.AudioContext=class {
 constructor(){this.state='running';this.destination={kind:'speakers'};}
 createAnalyser(){return {...audioNode('analyser'),getFloatTimeDomainData(samples){samples.fill(amplitude);}};}
 createMediaElementSource(){mediaSources++;return audioNode('playback');}
 createMediaStreamSource(){return audioNode('microphone');}
 async close(){closedContexts++;}
};
await clickVoice({dataset:{action:'voice-start'}});
assert.match(node('#voice-panel').innerHTML,/voice-candles/);
assert.match(node('#voice-panel').innerHTML,/candle-flame/);
assert.equal(node('#voice-orb').dataset.phase,'speaking');
assert.ok(Number(node('#voice-orb').style.values['--voice-level'])>0);
assert.ok(connections.some(([a,b])=>a==='analyser'&&b==='speakers'));
playback.onwaiting();playback.onplaying();assert.equal(mediaSources,1,'Reuse the media source on rebuffer/play');
playback.onended();assert.equal(frames.size,0);
assert.equal(node('#voice-orb').style.values['--voice-level'],'0');
connections.length=0;amplitude=.01;
await clickVoice({dataset:{action:'voice-orb'}});
assert.equal(node('#voice-orb').dataset.phase,'listening');
assert.equal(Number(node('#voice-orb').style.values['--voice-level']),0);
assert.ok(connections.some(([a,b])=>a==='microphone'&&b==='analyser'));
assert.ok(!connections.some(([,b])=>b==='speakers'),'Never echo the microphone');
amplitude=.18;const [frame,draw]=frames.entries().next().value;frames.delete(frame);draw();
assert.ok(Number(node('#voice-orb').style.values['--voice-level'])>0);
stopVoice();assert.equal(frames.size,0);assert.equal(closedContexts,1);

// Signed PCM, mono downmix, sample rate and RIFF lengths match the server contract.
const bytes=wavBytes({length:2,numberOfChannels:2,sampleRate:24000,getChannelData:c=>c===0?new Float32Array([1,-1]):new Float32Array([1,1])});
const view=new DataView(bytes);
assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');
assert.equal(view.getUint32(24,true),24000);
assert.equal(view.getUint16(22,true),1);
assert.equal(view.getInt16(44,true),32767);
assert.equal(view.getInt16(46,true),0);
assert.equal(bytes.byteLength,48);
console.log('Voice chandelier: sound-reactive flames, playback/microphone routing, cleanup, turns, privacy and PCM WAV PASS');

// Stateful protocol, source escaping, consent, retry deduplication and close cleanup.
const {suggestionCards}=await import('../app/voice.mjs');
assert.doesNotMatch(suggestionCards([{name:'<img src=x>',website:'javascript:alert(1)',unknown:[],reasons:[]}]),/<img|href=/);
assert.match(suggestionCards([{name:'Lieu',website:'https://example.org',unknown:['Prix inconnu'],reasons:[]}]),/Prix inconnu/);
let turnCalls=[],failNext=false;
configureVoice({...context,api:async(path,options)=>{
 if(path==='/integrations')return {gradium:{available:false}};
 if(options.method==='DELETE'){turnCalls.push([path,options]);return {closed:true};}
 turnCalls.push([path,options]);
 if(failNext){failNext=false;throw Error('Connection lost');}
 return {session_id:'session-A',revision:(options.body.revision||0)+1,reply:'Continuons',plans:[],suggestions:[],mode:'openai'};
}});
await clickVoice({dataset:{action:'voice-start'}});
node('#voice-text').value='Finalement, plutôt japonais';failNext=true;
await submitVoice({id:'voice-form'});
const failedBody=turnCalls.at(-1)[1].body;
await submitVoice({id:'voice-form'});
assert.equal(turnCalls.at(-1)[1].body.request_id,failedBody.request_id);
assert.equal(failedBody.session_id,'session-A');
assert.equal(failedBody.revision,1);
assert.equal(failedBody.cloud_consent,true);assert.equal(failedBody.web_consent,true);
stopVoice();assert.equal(turnCalls.at(-1)[0],'/ask/chat/session-A');
assert.equal(turnCalls.at(-1)[1].method,'DELETE');
console.log('Ask dialogue UI: sessions, consent, retry identity, safe sources and close PASS');

// Finishing keeps a clickable idle candle; typing can also start without a welcome turn.
await clickVoice({dataset:{action:'voice-close'}});
assert.match(node('#voice-panel').innerHTML,/data-action="voice-start"/);
assert.match(node('#voice-panel').innerHTML,/Touchez la chandelle pour commencer/);
const beforeTypedStart=turnCalls.length;
node('#voice-text').value='Un restaurant calme';
await submitVoice({id:'voice-form'});
assert.equal(turnCalls.length,beforeTypedStart+1);
assert.equal(turnCalls.at(-1)[1].body.message,'Un restaurant calme');
assert.equal(turnCalls.at(-1)[1].body.cloud_consent,true);
assert.equal(turnCalls.at(-1)[1].body.session_id,null);
assert.doesNotMatch(node('#voice-panel').innerHTML,/voice-cloud/);
assert.equal(node('.voice-text-option').open,true);
stopVoice();

// A second click while the first start awaits configuration cannot create two sessions.
let releaseIntegration,starts=0;
configureVoice({...context,api:async(path,options)=>{
 if(path==='/integrations')return new Promise(resolve=>{releaseIntegration=resolve;});
 if(options.method==='POST')starts++;
 return {reply:'Bonjour',plans:[],mode:'offline'};
}});
const firstStart=clickVoice({dataset:{action:'voice-start'}});
await clickVoice({dataset:{action:'voice-start'}});
releaseIntegration({gradium:{available:false}});await firstStart;
assert.equal(starts,1);
stopVoice();
console.log('Ask entry PASS: visible idle candle, no automatic call, preserved consent, direct keyboard start, close/restart and duplicate-click guard.');
