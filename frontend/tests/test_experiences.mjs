import assert from 'node:assert/strict';
import {configureExperiences, inspirations, availability, submitExperience, clickExperience, resetSelection, selectionIds} from '../app/experiences.mjs';

const calls=[];let rendered='',route='',identity='a';
const responses={
  '/calendar/status':{connected:false,providers:{google:false,outlook:false},window_policy:'Test'},
  '/proactive/settings':{enabled:false,both_enabled:false,scheduler:{running:false}},
  '/inspirations':{items:[{id:'fact',privacy_scope:'PRIVATE',value:{platform:'manual',text:'<script>private</script>',proposed_tags:['jazz'],imported_at:'2026-09-26T12:00:00Z'}}]},
  '/availability':{mode:'manual',both_configured:false,own_slots:[],common_slots:[]},
  '/activities/compare':{items:[{id:'a',title:'Jazz',price_per_person:null,duration_minutes:75}],known_total_eur:0,budget_complete:false,message:'À vérifier'},
  '/inspirations/import':{items:[],duplicates:0,warnings:[]},
  '/inspirations/fact/confirm':{},
  '/date-plans/plan/booking':{message:'Aucune réservation effectuée.',actions:[{title:'Jazz',start:'2026-09-26T19:00:00Z',participants:2,price_per_person:16,demo:true,booking_url:null}]},
};
configureExperiences({api:async(path,options)=>{calls.push({path,options});assert.ok(path in responses);return responses[path]},navigate:async next=>{route=next},notify:()=>{},modal:html=>{rendered=html},identity:()=>identity});
const html=await inspirations();
assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
assert.match(html,/signal-confirm/);assert.match(html,/Privé/);
assert.match(await availability(),/manque encore/);
globalThis.document={querySelector:()=>null};
const button=(id,action='compare-toggle')=>({dataset:{id,action,title:id},setAttribute(){}});
for(let i=0;i<5;i++)assert.equal(await clickExperience(button(String(i))),true);
await assert.rejects(()=>clickExperience(button('six')),/cinq/);
assert.equal(selectionIds().length,5);
await clickExperience(button('0'));assert.equal(selectionIds().length,4);
resetSelection();assert.equal(selectionIds().length,0);
await clickExperience(button('a'));await clickExperience(button('', 'compare-open'));
assert.match(rendered,/Inconnu/);assert.match(rendered,/compose-selection/);
assert.deepEqual(calls.at(-1).options.body.activity_ids,['a']);
await clickExperience(button('plan','prepare-booking'));
assert.match(rendered,/Aucune réservation effectuée/);assert.match(rendered,/Pas de lien/);
assert.match(rendered,/calendar-export/);
globalThis.FormData=class{constructor(form){this.values=form.values}get(key){return this.values[key]}};
assert.equal(await submitExperience({id:'signal-confirm',dataset:{id:'fact'},values:{tags:' jazz, creative ',privacy_scope:'PRIVATE',horizon:'durable'}}),true);
assert.deepEqual(calls.at(-1).options.body.tags,['jazz','creative']);
assert.equal(calls.at(-1).options.body.privacy_scope,'PRIVATE');assert.equal(route,'inspirations');
const before=calls.length;
await assert.rejects(()=>submitExperience({id:'signal-import',values:{file:{size:10,text:async()=>{identity='b';return 'private text'}}}}),/profil actif/);
assert.equal(calls.length,before,'A file read for A must never be submitted as B');
assert.equal(await clickExperience(button('','unrelated')),false);
assert.equal(await submitExperience({id:'unrelated'}),false);
console.log('Merged UI PASS: imports/escaping, consent, availability, comparison limit, unknown prices, booking/export actions, identity change during file read.');

responses['/reels/upload?wait=true']={source:'reel'};
identity='a';
const video={name:'video.mp4',size:100,type:'video/mp4'};
await submitExperience({id:'reel-import',values:{video,consent:'true',caption:'Jazz'}});
assert.equal(calls.at(-1).path,'/reels/upload?wait=true');
assert.equal(calls.at(-1).options.raw.get('video'),video);
assert.equal(calls.at(-1).options.body,undefined);
assert.match(html,/reel-import/);assert.match(html,/name="processing" value="standard"/);assert.doesNotMatch(html,/OpenAI|cloud_consent/);
const previousCount=calls.length;
await assert.rejects(()=>submitExperience({id:'reel-import',values:{video,consent:'false'}}),/autorisation/);
await assert.rejects(()=>submitExperience({id:'reel-import',values:{video:{...video,size:34*1024*1024},consent:'true'}}),/32 Mio/);
assert.equal(calls.length,previousCount);
console.log('Reel UI PASS: authenticated multipart submission, consent, size and visible upload form.');
