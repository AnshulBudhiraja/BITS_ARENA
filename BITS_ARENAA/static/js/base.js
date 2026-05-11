/**
 * BITS ARENA — base.js
 * Active bottom-nav link highlighting
 */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Active nav link highlighting ── */
  const currentPath = window.location.pathname.replace(/\/$/, '') || '/';

  document.querySelectorAll('.bnav-item').forEach(link => {
    const href = (link.getAttribute('href') || '').replace(/\/$/, '') || '/';
    if (currentPath === href || (href !== '/' && currentPath.startsWith(href))) {
      link.classList.add('active');
    }
  });

  /* ── Header shadow on scroll ── */
  const header = document.getElementById('site-header');
  if (header) {
    window.addEventListener('scroll', () => {
      header.style.boxShadow = window.scrollY > 10
        ? '0 2px 20px rgba(0,245,255,0.08)'
        : 'none';
    }, { passive: true });
  }

});
