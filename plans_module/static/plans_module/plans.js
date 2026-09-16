document.addEventListener('DOMContentLoaded', function () {
    const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
    const englishDigits = '0123456789';
    const dateInputs = document.querySelectorAll('input[data-jdp]');
    const toEnglishDigits = value => value.replace(/[۰-۹]/g, digit => englishDigits[persianDigits.indexOf(digit)]);
    const toPersianDigits = value => value.replace(/\d/g, digit => persianDigits[Number(digit)]);

    document.addEventListener('focusin', function (event) {
        if (event.target.matches?.('input[data-jdp]')) {
            event.target.value = toEnglishDigits(event.target.value);
        }
    }, true);

    dateInputs.forEach(input => {
        input.addEventListener('jdp:change', function () {
            input.value = toPersianDigits(input.value);
        });
    });

    if (window.jalaliDatepicker) {
        window.jalaliDatepicker.startWatch({
            persianDigits: true,
            autoHide: true,
            hideAfterChange: true,
            zIndex: 1500
        });
    }
    const modal = document.getElementById('plan-modal');
    const openButtons = document.querySelectorAll('[data-open-plan-modal]');
    const closeButtons = document.querySelectorAll('[data-close-plan-modal]');

    function openModal() {
        if (!modal) return;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('overflow-hidden');
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('overflow-hidden');
    }

    openButtons.forEach(button => button.addEventListener('click', openModal));
    closeButtons.forEach(button => button.addEventListener('click', closeModal));
    document.addEventListener('keydown', event => event.key === 'Escape' && closeModal());

    const activitySelect = document.querySelector('[name="activity_type"]');
    const subjectField = document.querySelector('[data-subject-field]');
    function syncSubjectField() {
        if (!activitySelect || !subjectField) return;
        const isSubject = activitySelect.value === 'SUBJECT';
        subjectField.classList.toggle('is-hidden', !isSubject);
        const select = subjectField.querySelector('select');
        if (select) select.disabled = !isSubject;
    }
    activitySelect?.addEventListener('change', syncSubjectField);
    syncSubjectField();

    const mainStudentInputs = Array.from(document.querySelectorAll('[data-main-student]'));
    const modalStudentInputs = Array.from(document.querySelectorAll('.target-list [name="target_students"]'));
    const selectedCounter = document.querySelector('[data-selected-count]');
    const selectionSnapshot = document.querySelector('[data-selection-snapshot]');

    function paintStudentSelection(selected) {
        mainStudentInputs.forEach(input => {
            input.checked = selected.has(input.value);
            input.closest('.student-glass-card')?.classList.toggle('is-selected', input.checked);
        });
        if (selectedCounter) selectedCounter.textContent = selected.size.toLocaleString('fa-IR');
        if (selectionSnapshot) selectionSnapshot.value = Array.from(selected).join(',');
    }

    function syncFromMainStudents() {
        const selected = new Set(mainStudentInputs.filter(input => input.checked).map(input => input.value));
        modalStudentInputs.forEach(input => { input.checked = selected.has(input.value); });
        paintStudentSelection(selected);
    }

    function syncFromModalStudents() {
        const selected = new Set(modalStudentInputs.filter(input => input.checked).map(input => input.value));
        paintStudentSelection(selected);
    }

    document.querySelector('[data-toggle-students]')?.addEventListener('click', function () {
        const checkboxes = modalStudentInputs;
        const shouldCheck = checkboxes.some(input => !input.checked);
        checkboxes.forEach(input => { input.checked = shouldCheck; });
        this.textContent = shouldCheck ? 'لغو انتخاب همه' : 'انتخاب همه';
        syncFromModalStudents();
    });

    mainStudentInputs.forEach(input => input.addEventListener('change', syncFromMainStudents));
    modalStudentInputs.forEach(input => input.addEventListener('change', syncFromModalStudents));
    document.querySelectorAll('[data-open-plan-modal]').forEach(button => {
        button.addEventListener('click', syncFromMainStudents);
    });
    document.getElementById('plan-entry-form')?.addEventListener('submit', syncFromModalStudents);
    if (modal?.dataset.hasFormErrors === 'true') syncFromModalStudents();
    else syncFromMainStudents();

    document.querySelectorAll('[data-completion-form]').forEach(form => {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            const button = form.querySelector('button');
            button.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    body: new FormData(form)
                });
                if (!response.ok) throw new Error('Request failed');
                const data = await response.json();
                document.querySelector(`[data-entry-id="${data.entry_id}"]`)?.classList.toggle('is-completed', data.completed);
            } catch (error) {
                form.submit();
            } finally {
                button.disabled = false;
            }
        });
    });
});
