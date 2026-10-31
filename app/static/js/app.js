document.querySelectorAll("[data-sidebar-toggle]").forEach((toggle) => {
  toggle.addEventListener("click", () => document.body.classList.toggle("nav-open"));
});

const landingMenuToggle = document.querySelector(".landing-menu-toggle");
const landingMenu = document.querySelector(".landing-menu");
if (landingMenuToggle && landingMenu) {
  landingMenuToggle.addEventListener("click", () => {
    const expanded = landingMenuToggle.getAttribute("aria-expanded") === "true";
    landingMenuToggle.setAttribute("aria-expanded", String(!expanded));
    landingMenu.classList.toggle("is-open", !expanded);
  });
  landingMenu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      landingMenuToggle.setAttribute("aria-expanded", "false");
      landingMenu.classList.remove("is-open");
    });
  });
}

const landingCurtain = document.querySelector(".landing-curtain");
if (landingCurtain) {
  landingCurtain.addEventListener("animationend", (event) => {
    if (event.animationName === "curtain-fade") {
      landingCurtain.classList.add("is-open");
    }
  });
  document.querySelectorAll(".landing-curtain-panel").forEach((panel) => {
    panel.addEventListener("animationend", () => {
      panel.classList.add("is-open");
    });
  });
}

const landingRevealItems = document.querySelectorAll(".landing-reveal");
if (landingRevealItems.length && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.14 });
  landingRevealItems.forEach((item) => revealObserver.observe(item));
} else {
  landingRevealItems.forEach((item) => item.classList.add("is-visible"));
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

const timeline = document.querySelector("[data-timeline]");
if (timeline && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const timelineObserver = new IntersectionObserver((entries, observer) => {
    if (entries[0].isIntersecting) {
      timeline.classList.add("is-active");
      observer.disconnect();
    }
  }, { threshold: 0.2 });
  timelineObserver.observe(timeline);
}

window.setTimeout(() => {
  document.querySelectorAll(".alert").forEach((alert) => {
    alert.style.transition = "opacity 220ms ease";
    alert.style.opacity = "0";
    window.setTimeout(() => alert.remove(), 240);
  });
}, 5000);
