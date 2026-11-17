export type Route = {kind:'discover'|'watchlist'|'recommended'|'editor'|'admin'|'not-found'} | {kind:'movie'|'person';id:number};
export function parseRoute(path:string):Route {
  const clean=path.replace(/\/+$/,'')||'/';
  switch(clean){
    case '/': case '/discover': return {kind:'discover'};
    case '/watchlist': return {kind:'watchlist'};
    case '/for-you': return {kind:'recommended'};
    case '/editor': return {kind:'editor'};
    case '/admin': return {kind:'admin'};
  }
  const match=/^\/(movies|people)\/([1-9]\d*)$/.exec(clean);
  if(match){const id=Number(match[2]);if(Number.isSafeInteger(id)&&id<=2147483647)return {kind:match[1]==='movies'?'movie':'person',id};}
  return {kind:'not-found'};
}
export const moviePath=(id:number)=>`/movies/${id}`;
export const personPath=(id:number)=>`/people/${id}`;
