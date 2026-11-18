import {test} from 'node:test';
import assert from 'node:assert/strict';
import {THEME_KEY, THEME_COLORS, normalizeTheme, resolveTheme, readTheme, writeTheme, updateDocumentTheme} from '../src/theme.ts';
import {readFileSync} from 'node:fs';

test('unknown theme preferences default to system',()=>{
  for(const value of [null,undefined,'','blue','Dark',0,{}]) assert.equal(normalizeTheme(value),'system');
  for(const value of ['light','dark','system']) assert.equal(normalizeTheme(value),value);
});
test('system follows the OS while explicit preferences override it',()=>{
  assert.equal(resolveTheme('system',true),'dark'); assert.equal(resolveTheme('system',false),'light');
  assert.equal(resolveTheme('light',true),'light'); assert.equal(resolveTheme('dark',false),'dark');
});
test('appearance preference survives storage reads without touching authentication keys',()=>{
  const data=new Map([['ca_session_id','identifier']]);
  const storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)};
  assert.equal(readTheme(storage),'system'); writeTheme(storage,'dark');
  assert.equal(data.get(THEME_KEY),'dark'); assert.equal(readTheme(storage),'dark');
  assert.equal(data.get('ca_session_id'),'identifier');
});
test('unavailable device storage does not break theme helpers',()=>{
  const storage={getItem:()=>{throw Error('Unavailable')},setItem:()=>{throw Error('Unavailable')}};
  assert.equal(readTheme(storage),'system'); assert.doesNotThrow(()=>writeTheme(storage,'light'));
});
test('document theme and browser chrome color follow appearance',()=>{
  const meta={value:'',setAttribute(key,value){assert.equal(key,'content');this.value=value}};
  const doc={documentElement:{dataset:{}},querySelector:()=>meta};
  assert.equal(updateDocumentTheme(doc,'system',true),'dark'); assert.equal(doc.documentElement.dataset.theme,'dark'); assert.equal(meta.value,THEME_COLORS.dark);
  assert.equal(updateDocumentTheme(doc,'light',true),'light'); assert.equal(doc.documentElement.dataset.theme,'light'); assert.equal(meta.value,THEME_COLORS.light);
  assert.doesNotThrow(()=>updateDocumentTheme({...doc,querySelector:()=>null},'system',false));
});
const css=readFileSync(new URL('../src/design.css',import.meta.url),'utf8');
const tokens=block=>Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map(m=>[m[1],m[2]]));
const light=tokens(css.match(/:root\s*\{([^}]+)\}/)[1]);
const dark=tokens(css.match(/:root\[data-theme='dark'\]\s*\{([^}]+)\}/)[1]);
const lum=hex=>{const rgb=hex.slice(1).match(/../g).map(h=>parseInt(h,16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722};
const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
test('both themes meet 4.5:1 contrast for core text, action and feedback roles',()=>{
  for(const palette of [light,dark]){
    for(const surface of ['canvas','surface','surface-raised']) for(const fg of ['text','muted','accent','danger']) assert.ok(ratio(palette[fg],palette[surface])>=4.5,`${fg} on ${surface}: ${ratio(palette[fg],palette[surface])}`);
    for(const [fg,bg] of [['on-accent','accent'],['on-accent','accent-hover'],['accent','accent-soft'],['on-forest','forest'],['danger','danger-bg'],['danger','danger-bg-hover'],['success','success-bg'],['warning','warning-bg']]) assert.ok(ratio(palette[fg],palette[bg])>=4.5,`${fg} on ${bg}: ${ratio(palette[fg],palette[bg])}`);
  }
});
test('control borders and focus indicators meet 3:1 against core surfaces',()=>{
  for(const palette of [light,dark]) for(const surface of ['canvas','surface','surface-raised']) for(const fg of ['control-border','accent']) assert.ok(ratio(palette[fg],palette[surface])>=3,`${fg} on ${surface}: ${ratio(palette[fg],palette[surface])}`);
});
