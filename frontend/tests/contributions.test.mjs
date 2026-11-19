import test from 'node:test';
import assert from 'node:assert/strict';
import {emptySnapshot,updateField,diffRows,moveCredit,reviseChanges,contributionValidation,finderPath,historyKey,historyTitle,historyType,historyPath} from '../src/contributions.ts';

test('field updates distinguish unchanged values and explicit clearing',()=>{
 const b={...emptySnapshot(),metadata:{birthday:'1980-01-01',tags:['Drama']}};
 let c={core:{},metadata:{}};c=updateField(c,b,'metadata','birthday',null);
 assert.deepEqual(diffRows(b,c),[{key:'birthday',before:'1980-01-01',after:null}]);
 c=updateField(c,b,'metadata','birthday','1980-01-01');assert.deepEqual(c.metadata,{});
 c=updateField(c,b,'metadata','tags',[]);assert.deepEqual(c.metadata,{tags:[]});
});
test('ordering affects only the chosen professional role',()=>{
 const rows=[{related_id:1,role:'actor',character:'A'},{related_id:2,role:'director',character:''},{related_id:3,role:'actor',character:'B'}];
 const result=moveCredit(rows,2,-1);assert.deepEqual(result.map(x=>x.related_id),[3,2,1]);assert.equal(result[0].position,0);assert.equal(result[2].position,1);assert.equal(result[1].position,undefined);
 assert.equal(moveCredit(rows,0,-1),rows);
});
test('revising a rejected contribution preserves unrelated newly added credits',()=>{
 const a={related_id:1,role:'actor',character:'A'},b={related_id:2,role:'actor',character:'B'},c={related_id:3,role:'actor',character:'C'};
 const old={baseline:{...emptySnapshot(),credits:[a]},changes:{core:{},metadata:{},credits:[b]}};
 assert.deepEqual(reviseChanges(old,{...emptySnapshot(),credits:[a,c]}).credits,[c,b]);
});

test('draft validation allows incomplete records and rejects invalid year and runtime',()=>{
 const b=emptySnapshot();const changes={core:{},metadata:{}};
 assert.deepEqual(contributionValidation('movie',b,changes,'',false),[]);
 assert.deepEqual(contributionValidation('movie',b,changes,'',true),['Enter a film title.','Enter a release year.','Enter a contribution reason of at least 5 characters.']);
 assert.deepEqual(contributionValidation('movie',b,{core:{year:1800,runtime:-3},metadata:{}},'reason',false),['Enter a whole release year between 1888 and 2200.','Enter a whole runtime between 1 and 10,000 minutes.']);
 assert.equal(contributionValidation('movie',b,{core:{year:2000,runtime:1.5},metadata:{}},'reason',false).length,1);
 assert.deepEqual(contributionValidation('movie',b,{core:{title:'Film',year:2000,runtime:null},metadata:{}},'reason',true),[]);
});
test('record finder does not request a catalog list without a query',()=>{
 assert.equal(finderPath('movie','',1,6),null);
 assert.equal(finderPath('person','  ',1,6),null);
 assert.equal(finderPath('movie','  A & B  ',2,6),'/movies?q=A+%26+B&page=2&size=6');
 assert.equal(finderPath('person','Jimmy Stewart',1,6),'/directory/people?q=Jimmy+Stewart&page=1&size=6');
});

test('unified history keeps legacy and structured identities distinct',()=>{
 const legacy={kind:'synopsis',id:1,movie_title:'Orbit',status:'approved'};
 const structured={kind:'structured',id:1,entity:'movie',target_id:null,changes:{core:{title:'New Orbit'},metadata:{}},baseline:emptySnapshot()};
 assert.notEqual(historyKey(legacy),historyKey(structured));
 assert.equal(historyTitle(legacy),'Orbit');assert.equal(historyTitle(structured),'New Orbit');
 assert.equal(historyType(legacy),'Edit film · Synopsis');assert.equal(historyType(structured),'New film');
 assert.equal(historyPath(true,'pending',2,5),'/admin/contribution-history?page=2&size=5&status=pending');
 assert.equal(historyPath(false,'all',1,5),'/me/contribution-history?page=1&size=5');
});
