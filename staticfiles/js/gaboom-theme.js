// Force dark mode by default
(function() {
  'use strict';
  
  // Set dark mode immediately
  document.documentElement.classList.add('dark');
  localStorage.setItem('theme', 'dark');
  
  // Prevent theme toggle (dark mode only)
  window.__gaboomToggleTheme = function() {
    // Do nothing - dark mode only
    console.log('Dark mode is enforced');
  };
})();
