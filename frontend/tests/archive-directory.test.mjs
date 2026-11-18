import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute,directoryPath,classificationPath,historyTarget,historyState,newHistoryEntry} from '../src/navigation.ts';
import {isSectionActive,shellNavigation} from '../src/shell.ts';
import {safeExternal,calendarDate} from '../src/archive.ts';

test('directory and classification routes use stable IDs',()=>{
  for(const c of ['people','genres','countries','languages','tags'])assert.deepEqual(parseRoute(directoryPath(c)),{kind:'directory',category:c});
  for(const c of ['genres','countries','languages','tags'])assert.deepEqual(parseRoute(classificationPath(c,3)+'/'),{kind:'classification',category:c,id:3});
  for(const p of ['/discover/people/3','/discover/tags/0','/discover/tags/-1','/discover/tags/0001','/discover/genres/2147483648','/discover/nope','/discover/tags/1/extra'])assert.equal(parseRoute(p).kind,'not-found',p);
});
test('archive routes highlight Explore without activating management or library',()=>{
  for(const view of ['directory','classification','movie','person'])assert.deepEqual(shellNavigation('admin').filter(i=>isSectionActive(i,view)).map(i=>i.href),['/discover']);
});
test('history preserves archive route and refuses cross-session entries',()=>{
  const entry=newHistoryEntry('scope',2);const p=classificationPath('languages',5);
  assert.equal(historyTarget('scope',historyState(entry),p).path,p);
  assert.equal(historyTarget('other',historyState(entry),p).path,'/');
});
test('external media accepts HTTP(S) only and disallows URL credentials',()=>{
  assert.equal(safeExternal('https://example.org/a.jpg'),'https://example.org/a.jpg');
  for(const s of ['javascript:alert(1)','data:image/png;base64,abc','file:///tmp/a','//example.org','https://u:p@example.org/a','invalid','',null])assert.equal(safeExternal(s),undefined);
});
test('date-only presentation uses UTC to retain the calendar date',()=>{
  assert.equal(calendarDate('1908-05-20'),new Date('1908-05-20T00:00:00Z').toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}));
  assert.equal(calendarDate('invalid'),'invalid');
});

import {releaseFact} from '../src/archive.ts';
import {gridLayout,pageForOffset} from '../src/gridPaging.ts';
import {initialSearch,searchParams,searchError} from '../src/searchOptions.ts';

test('release is one fact, with future schedules and non-released exceptions',()=>{
  const today='2026-11-18';
  assert.deepEqual(releaseFact('2020-01-02','released',today),{label:'Release date',value:calendarDate('2020-01-02')});
  assert.equal(releaseFact('2027-01-02','upcoming',today).label,'Scheduled release');
  assert.match(releaseFact('2020-01-02','cancelled',today).value,/cancelled/);
  assert.deepEqual(releaseFact(null,'in_production',today),{label:'Release',value:'In production'});
  assert.equal(releaseFact(null,null,today),null);
});
test('responsive pages fill whole grid rows within API limits',()=>{
  assert.deepEqual(gridLayout(1150,'films'),{columns:7,size:14});
  assert.deepEqual(gridLayout(960,'films'),{columns:6,size:12});
  for(const kind of ['films','people','classifications'])for(const width of [200,320,500,760,1000,1500,4000]){
    const {columns,size}=gridLayout(width,kind);assert.ok(columns>=1&&size<=50&&size%columns===0);
  }
  assert.equal(pageForOffset(28,14),3);
  assert.equal(pageForOffset(28,12),3);
  assert.equal(pageForOffset(0,14),1);
});
test('search parameters transmit all classification filters and responsive page size',()=>{
  const p=searchParams({...initialSearch,q:'test',genres:['Drama'],languages:[2,3],countries:[4],tags:[5,6],tagMode:'or'},2,14);
  assert.equal(p.get('q'),'test');assert.equal(p.get('page'),'2');assert.equal(p.get('size'),'14');
  assert.deepEqual(p.getAll('genres'),['Drama']);assert.deepEqual(p.getAll('language_ids'),['2','3']);
  assert.deepEqual(p.getAll('country_ids'),['4']);assert.deepEqual(p.getAll('tag_ids'),['5','6']);assert.equal(p.get('tag_mode'),'or');
  assert.equal(searchError({...initialSearch,yearMin:'2025',yearMax:'2020'}),'Release year: minimum must not exceed maximum.');
});
