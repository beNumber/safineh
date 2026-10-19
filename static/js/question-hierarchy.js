document.addEventListener('DOMContentLoaded', () => {
    const source = document.getElementById('question-hierarchy');
    if (!source) return;
    const data = JSON.parse(source.textContent);
    const selects = Object.fromEntries(['field', 'subject', 'chapter', 'topic'].map(name => [name, document.getElementById('id_' + name)]));
    const relations = [['subject', 'field', 'subjects'], ['chapter', 'subject', 'chapters'], ['topic', 'chapter', 'topics']];
    function fill(name, parent, collection, keep) {
        const select = selects[name];
        select.replaceChildren(new Option('انتخاب کنید', ''));
        data[collection].filter(item => String(item[parent]) === selects[parent].value)
            .forEach(item => select.add(new Option(item.title, item.id, false, String(item.id) === String(keep))));
    }
    function refresh(from, previous = {}) {
        relations.slice(from).forEach(([name, parent, collection]) => fill(name, parent, collection, previous[name]));
    }
    selects.field.addEventListener('change', () => refresh(0));
    selects.field.addEventListener('academic:change', () => refresh(0));
    selects.subject.addEventListener('change', () => refresh(1));
    selects.chapter.addEventListener('change', () => refresh(2));
    refresh(0, Object.fromEntries(Object.entries(selects).map(([name, select]) => [name, select.value])));
});
