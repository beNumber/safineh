document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("activity-filters");
    form?.querySelectorAll("[data-auto-submit]").forEach((field) => {
        field.addEventListener("change", () => form.requestSubmit());
    });

    document.querySelectorAll(".person-card").forEach((card) => {
        card.addEventListener("pointermove", (event) => {
            const bounds = card.getBoundingClientRect();
            card.style.setProperty("--mouse-x", `${event.clientX - bounds.left}px`);
            card.style.setProperty("--mouse-y", `${event.clientY - bounds.top}px`);
        });
    });
});
