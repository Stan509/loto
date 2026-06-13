document.addEventListener('DOMContentLoaded', () => {
    const editToggle = document.getElementById('toggle-edit-mode');
    const form = document.querySelector('.settings-form');
    
    // Toggle Visual Edit Mode
    if (editToggle) {
        editToggle.addEventListener('click', (e) => {
            e.preventDefault();
            document.body.classList.toggle('edit-mode');
            const isEditing = document.body.classList.contains('edit-mode');
            editToggle.textContent = isEditing ? 'Terminer' : 'Modifier';
            editToggle.classList.toggle('btn--primary', isEditing);
            editToggle.classList.toggle('btn--secondary', !isEditing);
        });
    }

    // AJAX Form Submission
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Enregistrement...';

            const formData = new FormData(form);
            
            try {
                const response = await fetch(window.location.href, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.ok) {
                    showToast('Paramètres enregistrés avec succès', 'success');
                } else {
                    showToast('Erreur lors de l\'enregistrement', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Erreur de connexion', 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
                // Optional: Turn off edit mode?
                // document.body.classList.remove('edit-mode');
            }
        });
    }

    function showToast(msg, type='info') {
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
});
