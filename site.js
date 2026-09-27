// "On this page": mark the section currently under the top of the viewport.
(() => {
  const links = [...document.querySelectorAll('.here a')];
  const targets = links.map(a => document.getElementById(a.hash.slice(1))).filter(Boolean);
  if (!targets.length) return;
  const mark = () => {
    const y = window.scrollY + window.innerHeight * 0.3;
    let current = targets[0];
    for (const t of targets) if (t.offsetTop <= y) current = t;
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 2) current = targets[targets.length - 1];
    for (const a of links) a.toggleAttribute('aria-current', a.hash === '#' + current.id);
  };
  addEventListener('scroll', mark, { passive: true });
  addEventListener('resize', mark);
  mark();
})();
