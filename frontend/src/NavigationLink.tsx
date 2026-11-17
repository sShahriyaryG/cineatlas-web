import {type AnchorHTMLAttributes, type MouseEvent} from 'react';
export type Navigate=(path:string)=>void;
export function NavigationLink({navigate,href,onClick,...props}:AnchorHTMLAttributes<HTMLAnchorElement>&{href:string;navigate:Navigate}){
  function follow(e:MouseEvent<HTMLAnchorElement>){
    onClick?.(e);
    if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||(props.target&&props.target!=='_self'))return;
    e.preventDefault();navigate(href);
  }
  return <a {...props} href={href} onClick={follow}/>;
}
