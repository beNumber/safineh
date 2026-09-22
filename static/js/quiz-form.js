document.addEventListener('DOMContentLoaded', () => {
  const school = document.getElementById('student-filter-school');
  const grade = document.getElementById('student-filter-grade');
  const field = document.getElementById('student-filter-field');
  const count = document.getElementById('student-result-count');
  if (!school || !grade || !field) return;

  const studentInputs = [...document.querySelectorAll('#id_students input[type="checkbox"]')];
  const refresh = () => {
    [...grade.options].forEach(option => {
      option.hidden = Boolean(school.value && option.dataset.school && option.dataset.school !== school.value);
    });
    if (grade.selectedOptions[0]?.hidden) grade.value = '';
    [...field.options].forEach(option => {
      option.hidden = Boolean(grade.value && option.dataset.grade && option.dataset.grade !== grade.value);
    });
    if (field.selectedOptions[0]?.hidden) field.value = '';
    let visible = 0;
    studentInputs.forEach(input => {
      const matches = (!school.value || input.dataset.school === school.value)
        && (!grade.value || input.dataset.grade === grade.value)
        && (!field.value || input.dataset.field === field.value);
      input.closest('li').hidden = !matches;
      if (matches) visible += 1;
    });
    count.textContent = `${visible.toLocaleString('fa-IR')} دانش‌آموز`;
  };
  [school, grade, field].forEach(select => select.addEventListener('change', refresh));
  refresh();
});
