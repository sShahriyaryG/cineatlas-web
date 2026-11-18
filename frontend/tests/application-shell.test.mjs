import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute,newHistoryEntry,historyTarget,historyState} from '../src/navigation.ts';
import {shellNavigation,shellView,isSectionActive,visibleCount} from '../src/shell.ts';
test('root respects authentication readiness and identity',()=>{
 const root=parseRoute('/');assert.equal(shellView(root,true,true),'home');assert.equal(shellView(root,true,false),'discover');assert.equal(shellView(root,false,false),'checking-session');
});
test('explicit discovery and details preserve routes',()=>{
 for(const ready of [true,false])for(const signedIn of [true,false])for(const [path,kind] of [['/discover','discover'],['/movies/17','movie'],['/people/3','person']])assert.equal(shellView(parseRoute(path),ready,signedIn),kind);
});
test('role-based management links',()=>{
 assert.deepEqual(shellNavigation(null).map(i=>i.href),['/discover','/library','/for-you']);assert.deepEqual(shellNavigation('member').map(i=>i.href),['/','/discover','/library','/for-you']);assert.deepEqual(shellNavigation('editor').filter(i=>i.group==='management').map(i=>i.href),['/editor']);assert.deepEqual(shellNavigation('admin').filter(i=>i.group==='management').map(i=>i.href),['/editor','/admin']);
});
test('legacy and ratings routes highlight library',()=>{
 for(const path of ['/watchlist','/library','/library/ratings'])assert.deepEqual(shellNavigation('member').filter(i=>isSectionActive(i,shellView(parseRoute(path),true,true))).map(i=>i.href),['/library']);
});
test('unloaded collections never display false zero',()=>{
 assert.equal(visibleCount('loading',[]),null);assert.equal(visibleCount('error',[1,2]),null);assert.equal(visibleCount('ready',[]),0);assert.equal(visibleCount('ready',[1,2]),2);
});
test('back history retains authenticated library tab but rejects old account history',()=>{
 const scope='current',entry=newHistoryEntry(scope,2);assert.deepEqual(historyTarget(scope,historyState(entry),'/library/ratings'),{entry,path:'/library/ratings',replace:false});assert.equal(historyTarget('other',historyState(entry),'/library/ratings').path,'/');
});
