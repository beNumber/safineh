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
    const scheduleList = document.querySelector('[data-schedule-list]');
    const scheduleData = document.querySelector('[name="schedule_rows"]');
    const mainDate = document.querySelector('[name="scheduled_date"]');
    const mainStart = document.querySelector('[name="start_hour"]');
    const mainEnd = document.querySelector('[name="end_hour"]');
    function syncSchedules() {
        if (!scheduleData || !scheduleList) return;
        scheduleData.value = JSON.stringify(Array.from(scheduleList.querySelectorAll('[data-schedule-row]')).map(row => ({date: row.querySelector('[data-row-date]').value, start: row.querySelector('[data-row-start]').value, end: row.querySelector('[data-row-end]').value})));
    }
    function addScheduleRow(values = {}) {
        if (!scheduleList) return;
        const row = document.createElement('div');
        row.dataset.scheduleRow = '';
        row.className = 'grid grid-cols-[1fr_100px_100px_38px] gap-2';
        const hours = (from, to, selected) => Array.from({length: to - from + 1}, (_, i) => from + i).map(hour => `<option value="${hour}" ${String(hour) === String(selected) ? 'selected' : ''}>${String(hour).padStart(2, '0')}:00</option>`).join('');
        row.innerHTML = `<input data-row-date data-jdp autocomplete="off" placeholder="۱۴۰۵/۰۷/۰۱" class="rounded-xl border border-indigo-100 bg-white px-3 py-2 text-sm" value="${values.date || mainDate?.value || ''}"><select data-row-start class="rounded-xl border border-indigo-100 bg-white px-2 text-sm">${hours(8, 23, values.start || mainStart?.value)}</select><select data-row-end class="rounded-xl border border-indigo-100 bg-white px-2 text-sm">${hours(9, 24, values.end || mainEnd?.value)}</select><button type="button" data-remove-schedule class="rounded-xl bg-rose-50 text-rose-500"><i class="fa-solid fa-xmark"></i></button>`;
        scheduleList.appendChild(row);
        row.querySelector('[data-remove-schedule]').addEventListener('click', () => { row.remove(); syncSchedules(); });
        row.addEventListener('change', syncSchedules);
        window.jalaliDatepicker?.startWatch({persianDigits: true, autoHide: true, hideAfterChange: true, zIndex: 1600});
        syncSchedules();
    }
    document.querySelector('[data-add-schedule]')?.addEventListener('click', () => addScheduleRow());
    document.getElementById('plan-entry-form')?.addEventListener('submit', syncSchedules);
    if (scheduleData?.value) { try { JSON.parse(scheduleData.value).forEach(addScheduleRow); } catch (error) {} }
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
