document.addEventListener('DOMContentLoaded', () => {
    const digits = '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩';
    document.querySelectorAll('.course-schedule input[data-jdp]').forEach(input => {
        const normalizeDigits = () => {
            input.value = input.value.replace(/[۰-۹٠-٩]/g, digit => String(digits.indexOf(digit) % 10));
        };
        normalizeDigits();
        input.addEventListener('focus', normalizeDigits);
        input.addEventListener('jdp:change', normalizeDigits);
    });
    window.jalaliDatepicker?.startWatch({
        time: true, hasSecond: false, persianDigits: false, autoHide: true,
        hideAfterChange: false, showSelectTimeBtnAlways: true, zIndex: 2000
    });
    document.querySelectorAll('.choice-box input[type="checkbox"]').forEach(input => input.classList.add('ios-check'));
});
