(function(){
  var root=document.documentElement;
  function set(l){
    root.dataset.lang=l; root.lang=l;
    document.querySelectorAll('.lang button').forEach(function(b){b.setAttribute('aria-pressed', String(b.dataset.set===l));});
    try{localStorage.setItem('provino-lang',l);}catch(e){}
  }
  var saved=null; try{saved=localStorage.getItem('provino-lang');}catch(e){}
  set(saved || ((navigator.language||'it').toLowerCase().indexOf('it')===0 ? 'it' : 'en'));
  document.querySelectorAll('.lang button').forEach(function(b){b.addEventListener('click',function(){set(b.dataset.set);});});
  var lb=document.getElementById('lb'); if(!lb) return; var li=lb.querySelector('img');
  document.querySelectorAll('.gallery img, .plat img, .flow img').forEach(function(img){
    img.addEventListener('click',function(){ if(!lb.showModal) return; li.src=img.src; li.alt=img.alt; lb.showModal(); });
  });
  lb.addEventListener('click',function(){lb.close();});
})();
(function(){
  var links=[].slice.call(document.querySelectorAll('.toc a')); if(!links.length || !('IntersectionObserver' in window)) return;
  var map={}; links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
  var io=new IntersectionObserver(function(es){es.forEach(function(e){ if(e.isIntersecting){ links.forEach(function(a){a.classList.remove('on');}); var a=map[e.target.id]; if(a) a.classList.add('on'); } });},{rootMargin:'-20% 0px -70% 0px'});
  Object.keys(map).forEach(function(id){var s=document.getElementById(id); if(s) io.observe(s);});
})();
