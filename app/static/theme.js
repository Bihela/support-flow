// Dark/Light theme toggle, persisted in localStorage. Shared by every page.
// Loaded in <head> (before paint) so the saved theme applies with no flash.
(function () {
  const root = document.documentElement;
  const apply = (t) => root.classList.toggle("dark", t === "dark");

  apply(localStorage.getItem("theme"));

  // Delegated so it works no matter when the header button is parsed.
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#themeToggle")) return;
    const next = root.classList.contains("dark") ? "light" : "dark";
    localStorage.setItem("theme", next);
    apply(next);
  });
})();

window.showConfirm = function(title, message, options = {}) {
  return new Promise((resolve) => {
    const container = document.createElement('div');
    container.className = 'fixed inset-0 z-[9999] flex items-center justify-center p-4 transition-opacity duration-300 opacity-0 pointer-events-none';
    
    const backdrop = document.createElement('div');
    backdrop.className = 'absolute inset-0 bg-slate-900/60 backdrop-blur-sm';
    container.appendChild(backdrop);
    
    const card = document.createElement('div');
    card.className = 'relative bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl max-w-md w-full shadow-2xl p-6 transform scale-95 transition-transform duration-300 ease-out space-y-4';
    
    const titleRow = document.createElement('div');
    titleRow.className = 'flex items-center space-x-3';
    
    const isDestructive = options.isDestructive !== false;
    const iconColor = isDestructive ? 'text-rose-500 bg-rose-50 dark:bg-rose-950/30' : 'text-blue-500 bg-blue-50 dark:bg-blue-950/30';
    
    titleRow.innerHTML = `
      <div class="p-2 rounded-lg ${iconColor} flex-shrink-0">
        ${isDestructive ? `
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        ` : `
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        `}
      </div>
      <h3 class="text-lg font-bold text-slate-900 dark:text-white leading-6">${title}</h3>
    `;
    card.appendChild(titleRow);
    
    const body = document.createElement('div');
    body.className = 'text-sm text-slate-500 dark:text-slate-400 break-words';
    body.textContent = message;
    card.appendChild(body);
    
    const actions = document.createElement('div');
    actions.className = 'flex justify-end space-x-3 pt-2';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'px-4 py-2 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-semibold transition duration-150 focus:outline-none focus:ring-2 focus:ring-slate-500/20';
    cancelBtn.textContent = options.cancelText || 'Cancel';
    
    const confirmBtn = document.createElement('button');
    const confirmColors = isDestructive 
      ? 'bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white focus:ring-rose-500/20' 
      : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white focus:ring-blue-500/20';
    confirmBtn.className = `px-4 py-2 rounded-lg text-sm font-semibold transition duration-150 focus:outline-none focus:ring-2 ${confirmColors}`;
    confirmBtn.textContent = options.confirmText || 'Confirm';
    
    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    card.appendChild(actions);
    container.appendChild(card);
    document.body.appendChild(container);
    
    requestAnimationFrame(() => {
      container.classList.remove('opacity-0', 'pointer-events-none');
      card.classList.remove('scale-95');
    });
    
    let closed = false;
    function close(confirmed) {
      if (closed) return;
      closed = true;
      container.classList.add('opacity-0', 'pointer-events-none');
      card.classList.add('scale-95');
      document.removeEventListener('keydown', handleKeydown);
      setTimeout(() => {
        container.remove();
        resolve(confirmed);
      }, 300);
    }
    
    function handleKeydown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        close(false);
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        if (document.activeElement === cancelBtn) {
          close(false);
        } else {
          close(true);
        }
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        e.stopPropagation();
        if (e.shiftKey) {
          if (document.activeElement === cancelBtn) {
            confirmBtn.focus();
          } else {
            cancelBtn.focus();
          }
        } else {
          if (document.activeElement === confirmBtn) {
            cancelBtn.focus();
          } else {
            confirmBtn.focus();
          }
        }
      }
    }
    document.addEventListener('keydown', handleKeydown);
    
    backdrop.addEventListener('click', () => close(false));
    cancelBtn.addEventListener('click', () => close(false));
    confirmBtn.addEventListener('click', () => close(true));
    
    cancelBtn.focus();
  });
};

