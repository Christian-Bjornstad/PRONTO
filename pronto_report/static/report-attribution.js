(() => {
  'use strict';
  window.requestDeclaredInitials = (action) => {
    const dialog = document.getElementById('initials-dialog');
    if (!dialog || dialog.open) return Promise.resolve(null);
    const input = document.getElementById('declared-initials');
    const error = document.getElementById('initials-error');
    const previous = document.activeElement;
    document.getElementById('initials-action').textContent = action;
    input.value = '';
    error.textContent = '';
    return new Promise((resolve) => {
      let value = null;
      const accept = () => {
        const raw = input.value.trim();
        if (!/^[A-Za-zÆØÅæøå]{2,8}$/.test(raw)) {
          error.textContent = 'Oppgi 2–8 bokstaver som initialer.';
          input.focus();
          return;
        }
        value = raw.toUpperCase();
        dialog.close();
      };
      const key = (event) => { if (event.key === 'Enter') { event.preventDefault(); accept(); } };
      const confirm = document.getElementById('initials-confirm');
      const cancel = document.getElementById('initials-cancel');
      const dismiss = () => dialog.close();
      confirm.addEventListener('click', accept);
      cancel.addEventListener('click', dismiss);
      input.addEventListener('keydown', key);
      dialog.addEventListener('close', () => {
        confirm.removeEventListener('click', accept);
        cancel.removeEventListener('click', dismiss);
        input.removeEventListener('keydown', key);
        previous?.focus();
        resolve(value);
      }, { once: true });
      dialog.showModal();
      input.focus();
    });
  };
})();
