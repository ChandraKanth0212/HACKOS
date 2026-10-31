document.querySelectorAll("[data-sidebar-toggle]").forEach((toggle) => {
  toggle.addEventListener("click", () => document.body.classList.toggle("nav-open"));
});

window.setTimeout(() => {
  document.querySelectorAll(".alert").forEach((alert) => {
    alert.style.transition = "opacity 220ms ease";
    alert.style.opacity = "0";
    window.setTimeout(() => alert.remove(), 240);
  });
}, 5000);
