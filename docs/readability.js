/* Accessibility controls, browser-native translation guidance. No tracking/network. */
(()=>{'use strict';
 const $=id=>document.getElementById(id);
 const root=document.documentElement;
 const toggle=$('fontToggle'),open=$('translateHelp'),panel=$('translatePanel'),close=$('closeTranslatePanel');
 const key='guardian.readability.size.v1';
 try { if(localStorage.getItem(key)==='large') root.dataset.fontSize='large'; } catch {}
 const refresh=()=>{if(toggle){ const large=root.dataset.fontSize==='large';toggle.textContent=large?'A−':'A+';toggle.setAttribute('aria-pressed',String(large));toggle.title=large?'Standard text size':'Larger text';}};
 if(toggle){toggle.addEventListener('click',()=>{const large=root.dataset.fontSize!=='large';root.dataset.fontSize=large?'large':'normal';try{localStorage.setItem(key,large?'large':'normal');}catch{}refresh();});refresh();}
 if(open&&panel){open.addEventListener('click',()=>{panel.hidden=!panel.hidden;if(!panel.hidden)close.focus()});}
 if(close&&panel)close.addEventListener('click',()=>{panel.hidden=true;open.focus()});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&panel&&!panel.hidden){panel.hidden=true;open.focus()}});
})();
