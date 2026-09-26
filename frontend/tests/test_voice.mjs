import assert from 'node:assert/strict';
import {configureVoice,voiceEntry,clickVoice,submitVoice,stopVoice,wavBytes} from '../app/voice.mjs';

const nodes=new Map();
const node=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',value:'',replaceChildren(){}});return nodes.get(selector);};
globalThis.document={querySelector:node,querySelectorAll:()=>[]};
let identity='a',calls=[];
const context={identity:()=>identity,escape:s=>s.replaceAll('<','&lt;'),planCard:p=>`PLAN ${p.id}`,
  audio:async()=>{throw Error('Provider unavailable');},api:async(path,options)=>{
    calls.push([path,options]);
    if(path==='/integrations')return {gradium:{available:false}};
    return {reply:'Bonjour <test>',plans:options.body.recommend?[{id:'real-plan'}]:[]};
  }};
configureVoice(context);
assert.match(voiceEntry(),/voice-open/);
await clickVoice({dataset:{action:'voice-open'}});
assert.match(node('#voice-panel').innerHTML,/Bonjour &lt;test>/);
assert.match(node('#voice-panel').innerHTML,/audio est transmis à Gradium/);
node('#voice-text').value='Une balade';
await submitVoice({id:'voice-form'});
assert.deepEqual(calls.at(-1)[1].body.messages,['Une balade']);
node('#voice-text').value='';
await clickVoice({dataset:{action:'voice-recommend'}});
assert.equal(calls.at(-1)[1].body.recommend,true);
assert.match(node('#voice-plans').innerHTML,/real-plan/);

// A late response from A must never render into B's screen.
let resolve;
configureVoice({...context,api:async(path)=>path==='/integrations'?{gradium:{available:false}}:new Promise(r=>{resolve=r;})});
const opening=clickVoice({dataset:{action:'voice-open'}});
await new Promise(r=>setTimeout(r,0));
stopVoice();identity='b';node('#voice-panel').innerHTML='B PRIVATE SCREEN';
resolve({reply:'A PRIVATE RESPONSE',plans:[]});await opening;
assert.equal(node('#voice-panel').innerHTML,'B PRIVATE SCREEN');

// Permission granted after navigation must immediately release the microphone.
configureVoice({...context,api:async(path)=>path==='/integrations'?{gradium:{available:true}}:{reply:'Bonjour',plans:[]}});
await clickVoice({dataset:{action:'voice-open'}});
let permission,stops=0;
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:()=>new Promise(r=>{permission=r;})}}});
globalThis.MediaRecorder=class {};
const recording=clickVoice({dataset:{action:'voice-record'}});
stopVoice();permission({getTracks:()=>[{stop(){stops++;}}]});await recording;
assert.equal(stops,1);

// Signed PCM, mono downmix, sample rate and RIFF lengths match the server contract.
const bytes=wavBytes({length:2,numberOfChannels:2,sampleRate:24000,getChannelData:c=>c===0?new Float32Array([1,-1]):new Float32Array([1,1])});
const view=new DataView(bytes);
assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');
assert.equal(view.getUint32(24,true),24000);
assert.equal(view.getUint16(22,true),1);
assert.equal(view.getInt16(44,true),32767);
assert.equal(view.getInt16(46,true),0);
assert.equal(bytes.byteLength,48);
console.log('Voice discovery: dialogue, plans, escaping, identity cancellation, microphone release and PCM WAV PASS');
