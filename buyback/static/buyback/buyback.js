document.addEventListener('DOMContentLoaded', () => {
  const button = document.querySelector('[data-copy-total]');
  if (!button) return;
  button.addEventListener('click', async () => {
    const feedback = document.getElementById('copy-feedback');
    const text = button.dataset.copyTotal;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const field = document.createElement('textarea');
        field.value = text;
        field.style.position = 'fixed';
        field.style.opacity = '0';
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand('copy');
        field.remove();
        if (!copied) throw new Error('Copy failed');
      }
      feedback.textContent = 'Buyback total copied.';
    } catch (_) {
      feedback.textContent = 'Select and copy the Buyback Total above.';
    }
  });
});
