import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseRoute,moviePath,personPath} from '../src/navigation.ts';
import {groupFilmography} from '../src/catalogTypes.ts';

test('canonical navigation routes and optional trailing slash',()=>{
  for(const [path,kind] of [['/','home'],['/discover','discover'],['/watchlist','watchlist'],['/library','watchlist'],['/library/ratings','ratings'],['/for-you','recommended'],['/editor','editor'],['/admin','admin']]) assert.deepEqual(parseRoute(path),{kind});
  assert.deepEqual(parseRoute('/movies/42/'),{kind:'movie',id:42});
  assert.deepEqual(parseRoute(personPath(12)),{kind:'person',id:12});
  assert.deepEqual(parseRoute(moviePath(7)),{kind:'movie',id:7});
});
test('rejects malformed, unsupported and unsafe routes',()=>{
  for(const path of ['/movies','/movies/-1','/movies/0','/movies/1.2','/people/foo','/movies/2147483648','/movies/1/credits','/unknown','/people/0001']) assert.deepEqual(parseRoute(path),{kind:'not-found'},path);
});
test('filmography displays each movie once while retaining all credits',()=>{
  const a={movie_id:9,title:'Film',year:2020,poster_url:'https://example.org/a.jpg',role:'actor',character:'Pilot'};
  const b={...a,role:'director',character:''};
  const c={...a,movie_id:7,title:'Earlier film',year:2010,role:'writer',character:'',poster_url:''};
  const films=groupFilmography([a,b,c]);
  assert.deepEqual(films.map(f=>f.movie_id),[9,7]);
  assert.equal(films[0].poster_url,a.poster_url);
  assert.deepEqual(films[0].credits,[a,b]);
  assert.deepEqual(groupFilmography([]),[]);
});
