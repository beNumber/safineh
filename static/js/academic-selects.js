document.addEventListener('DOMContentLoaded', () => {
    const source = document.getElementById('academic-hierarchy') || document.getElementById('question-hierarchy');
    if (!source) return;
    const data = JSON.parse(source.textContent);
    const school = document.getElementById('id_school');
    const grade = document.getElementById('id_grade');
    const field = document.getElementById('id_field');
    if (!school || !grade) return;
    const selected = {grade: grade.value, field: field?.value};
    if (!selected.grade && selected.field) selected.grade = String(data.fields.find(item => String(item.id) === selected.field)?.grade_id || '');
    if (!school.value && selected.grade) school.value = String(data.grades.find(item => String(item.id) === selected.grade)?.school_id || '');
    function fill(select, items, keep) {
        select.replaceChildren(new Option('انتخاب کنید', ''));
        items.forEach(item => select.add(new Option(item.title, item.id, false, String(item.id) === String(keep))));
    }
    function fillFields(keep) {
        if (!field) return;
        fill(field, data.fields.filter(item => String(item.grade_id) === grade.value), keep);
        field.dispatchEvent(new Event('academic:change'));
    }
    function fillGrades(keepGrade, keepField) {
        fill(grade, data.grades.filter(item => String(item.school_id) === school.value), keepGrade);
        fillFields(keepField);
        grade.dispatchEvent(new Event('academic:change'));
    }
    school.addEventListener('change', () => fillGrades());
    grade.addEventListener('change', () => fillFields());
    fillGrades(selected.grade, selected.field);
});
