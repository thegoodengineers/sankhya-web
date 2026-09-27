// "On this page": mark the section currently under the top of the viewport.
(() => {
  const links = [...document.querySelectorAll('.here a')];
  const targets = links.map(a => document.getElementById(a.hash.slice(1))).filter(Boolean);
  if (!targets.length) return;
  const mark = () => {
    const y = window.scrollY + window.innerHeight * 0.3;
    let current = targets[0];
    for (const t of targets) if (t.offsetParent !== null && t.offsetTop <= y) current = t;
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 2) current = targets[targets.length - 1];
    for (const a of links) a.toggleAttribute('aria-current', a.hash === '#' + current.id);
  };
  addEventListener('scroll', mark, { passive: true });
  addEventListener('resize', mark);
  mark();
})();

// Generated documents fold long included passages into <details>. A link into one opens it,
// and printing opens them all, then puts them back.
(() => {
  const open = (hash) => {
    const el = hash && document.getElementById(decodeURIComponent(hash.slice(1)));
    for (let d = el && el.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
    if (el) el.scrollIntoView();
  };
  addEventListener('hashchange', () => open(location.hash));
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (a && a.hash) { open(a.hash); }
  });
  if (location.hash) open(location.hash);
  let closed = [];
  addEventListener('beforeprint', () => {
    closed = [...document.querySelectorAll('details:not([open])')];
    closed.forEach((d) => { d.open = true; });
  });
  addEventListener('afterprint', () => { closed.forEach((d) => { d.open = false; }); closed = []; });
})();
