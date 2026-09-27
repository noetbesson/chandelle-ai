import assert from 'node:assert/strict';
import {activityMeta,discoverActivityRow,discoverSections,discoverPage} from '../app/discover.mjs';
const records=[
 {id:'a',type:'concert',name:'Premier <concert>',price_per_person:null,start:'2026-10-02T16:00:00+02:00',website:'https://example.org/a'},
 {id:'b',type:'exposition',name:'Expo',price_per_person:0,start:'2026-10-03',location:{address:'Paris'}},
 {id:'c',type:'concert',name:'Second concert',price_per_person:12.5},
];
const before=JSON.stringify(records),html=discoverSections(records);
assert.equal(JSON.stringify(records),before,'Rendering must not mutate API records');
assert.equal((html.match(/class="discover-section"/g)||[]).length,2);
assert.ok(html.indexOf('Premier &lt;concert&gt;')<html.indexOf('Second concert'));
assert.ok(html.indexOf('Second concert')<html.indexOf('>Expo<'));
assert.doesNotMatch(html,/Restaurants|undefined|NaN|Invalid Date/);
assert.match(html,/Prix à confirmer/);assert.match(html,/Gratuit/);assert.match(html,/12,5 € \/ pers\./);
assert.match(html,/2 oct. 2026, 16:00/);
assert.doesNotMatch(activityMeta(records[1]),/00:00/,'A date-only record must not invent a time');
assert.doesNotMatch(activityMeta({}),/activity-meta-date|activity-meta-place|Gratuit/);
assert.doesNotMatch(activityMeta({start:'invalid',price_per_person:-2}).replace(/<[^>]*>/g,''),/Invalid|NaN|-2/);
const unsafe=discoverActivityRow({name:'<img onerror=alert(1)>',type:'<script>',website:'javascript:alert(1)',image_url:'javascript:alert(1)',description:'<script>alert(1)</script>'},{label:'<svg>'});
assert.doesNotMatch(unsafe,/<img|<script|href="javascript|src="javascript/);
assert.match(unsafe,/&lt;img onerror/);
const image=discoverActivityRow({...records[0],image_url:'https://example.org/photo.jpg'},{label:'Concerts'});
assert.match(image,/object|data-activity-image/);assert.match(image,/art-fallback/);assert.match(image,/referrerpolicy="no-referrer"/);
const demo=discoverActivityRow({id:'demo-1',title:'Un test',category:'food',eligible:true},{demo:true,label:'À table',selectButton:a=>`<button data-id="${a.id}">Comparer</button>`,scores:()=>'<span>Scores fournis</span>'});
assert.match(demo,/Exemple fictif/);assert.match(demo,/data-action="activity" data-id="demo-1"/);assert.match(demo,/Comparer/);assert.match(demo,/Scores fournis/);
const page=discoverPage({real:records,catalog:[],query:'"><svg>',category:'culture',filterCategories:['culture','concerts'],selectButton:()=>'',compareBar:()=>''});
assert.match(page,/id="discover"/);assert.match(page,/name="query"/);assert.match(page,/name="category"/);
assert.match(page,/value="culture" selected/);assert.doesNotMatch(page,/value="food"|<svg>/);
assert.doesNotMatch(page,/discover-demo/,'No fictional section when the database has no demo records');
assert.doesNotMatch(page,/<details class="discover-demo" open/);
console.log('Discover presentation PASS: real categories, stable records/order, actual dates/prices, escaping, safe images/sources, demo actions and unchanged filter fields.');
