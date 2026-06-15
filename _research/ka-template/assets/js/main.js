const $all = (selector, parent = document) => Array.from(parent.querySelectorAll(selector));

const themeState = {
  current: document.documentElement.classList.contains("dark") ? "dark" : "light",
};

function applyTheme(theme) {
  themeState.current = theme;
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem("ka-theme", theme);
  $all("[data-theme-toggle]").forEach((button) => {
    button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    const label = button.querySelector("[data-theme-label]");
    if (label) {
      label.textContent = theme === "dark" ? "Dark" : "Light";
    }
  });
}

function initThemeToggle() {
  $all("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      applyTheme(themeState.current === "dark" ? "light" : "dark");
    });
  });
}

function initHeaderState() {
  const header = document.querySelector("[data-site-header]");
  if (!header) {
    return;
  }

  const sync = () => {
    header.classList.toggle("scrolled", window.scrollY > 12);
  };

  sync();
  window.addEventListener("scroll", sync, { passive: true });
}

function initMobileMenu() {
  const menu = document.querySelector("[data-mobile-menu]");
  const toggle = document.querySelector("[data-mobile-toggle]");

  if (!menu || !toggle) {
    return;
  }

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
    menu.classList.toggle("hidden", expanded);
  });
}

function initAccordion() {
  $all("[data-accordion-item]").forEach((item, index) => {
    const button = item.querySelector("[data-accordion-trigger]");
    const panel = item.querySelector("[data-accordion-panel]");

    if (!button || !panel) {
      return;
    }

    const open = () => {
      item.classList.add("is-open");
      button.setAttribute("aria-expanded", "true");
      panel.style.maxHeight = `${panel.scrollHeight}px`;
    };

    const close = () => {
      item.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
      panel.style.maxHeight = "0px";
    };

    if (index === 0 || item.dataset.open === "true") {
      open();
    } else {
      close();
    }

    button.addEventListener("click", () => {
      const isOpen = item.classList.contains("is-open");
      const siblings = item.parentElement ? $all("[data-accordion-item]", item.parentElement) : [];
      siblings.forEach((sibling) => {
        if (sibling !== item) {
          const siblingButton = sibling.querySelector("[data-accordion-trigger]");
          const siblingPanel = sibling.querySelector("[data-accordion-panel]");
          sibling.classList.remove("is-open");
          if (siblingButton) siblingButton.setAttribute("aria-expanded", "false");
          if (siblingPanel) siblingPanel.style.maxHeight = "0px";
        }
      });

      if (isOpen) {
        close();
      } else {
        open();
      }
    });
  });
}

function initTabs() {
  $all("[data-tab-group]").forEach((group) => {
    const buttons = $all("[data-tab-target]", group);
    const panels = $all("[data-tab-panel]", group);

    if (!buttons.length || !panels.length) {
      return;
    }

    const activate = (target) => {
      buttons.forEach((button) => {
        const selected = button.dataset.tabTarget === target;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-selected", selected ? "true" : "false");
      });

      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.tabPanel === target);
      });
    };

    buttons.forEach((button, index) => {
      if (index === 0) {
        activate(button.dataset.tabTarget);
      }

      button.addEventListener("click", () => activate(button.dataset.tabTarget));
    });
  });
}

function initDropdowns() {
  $all("[data-dropdown]").forEach((dropdown) => {
    const trigger = dropdown.querySelector("[data-dropdown-trigger]");
    if (!trigger) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = dropdown.classList.contains("is-open");
      $all("[data-dropdown]").forEach((node) => node.classList.remove("is-open"));
      dropdown.classList.toggle("is-open", !isOpen);
    });
  });

  document.addEventListener("click", () => {
    $all("[data-dropdown]").forEach((dropdown) => dropdown.classList.remove("is-open"));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      $all("[data-dropdown]").forEach((dropdown) => dropdown.classList.remove("is-open"));
    }
  });
}

function initModals() {
  $all("[data-modal-open]").forEach((button) => {
    const target = button.getAttribute("data-modal-open");
    button.addEventListener("click", () => {
      const modal = document.getElementById(target);
      if (!modal) {
        return;
      }
      modal.classList.add("is-open");
      document.body.classList.add("overflow-hidden");
    });
  });

  $all("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = button.closest("[data-modal]");
      if (!modal) {
        return;
      }
      modal.classList.remove("is-open");
      document.body.classList.remove("overflow-hidden");
    });
  });

  $all("[data-modal]").forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        modal.classList.remove("is-open");
        document.body.classList.remove("overflow-hidden");
      }
    });
  });
}

function initReveal() {
  const nodes = $all("[data-reveal]");
  if (!nodes.length) {
    return;
  }

  if (!("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  nodes.forEach((node) => observer.observe(node));
}

function initCounters() {
  const counters = $all("[data-counter]");
  if (!counters.length || !("IntersectionObserver" in window)) {
    return;
  }

  const animate = (node) => {
    const target = Number(node.dataset.counter || 0);
    const suffix = node.dataset.suffix || "";
    const prefix = node.dataset.prefix || "";
    const duration = Number(node.dataset.duration || 1400);
    const start = performance.now();

    const frame = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = Math.round(target * eased);
      node.textContent = `${prefix}${value.toLocaleString()}${suffix}`;
      if (progress < 1) {
        requestAnimationFrame(frame);
      }
    };

    requestAnimationFrame(frame);
  };

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          animate(entry.target);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.6 }
  );

  counters.forEach((counter) => observer.observe(counter));
}

function initDemoForms() {
  $all("[data-demo-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const message = form.querySelector("[data-form-message]");
      if (message) {
        message.textContent = "Demo form submitted. Hook this action to your backend or email tool.";
        message.classList.remove("hidden");
      }
    });
  });
}

function initCharts() {
  if (typeof window.Chart === "undefined") {
    return;
  }

  const trendCanvas = document.getElementById("revenueChart");
  if (trendCanvas) {
    new window.Chart(trendCanvas, {
      type: "line",
      data: {
        labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
        datasets: [
          {
            label: "MRR",
            data: [22, 28, 35, 41, 46, 53, 64],
            tension: 0.42,
            borderColor: "rgba(99, 102, 241, 1)",
            backgroundColor: "rgba(99, 102, 241, 0.14)",
            borderWidth: 3,
            pointRadius: 0,
            fill: true,
          },
          {
            label: "Expansion",
            data: [10, 16, 21, 26, 32, 38, 44],
            tension: 0.42,
            borderColor: "rgba(6, 182, 212, 0.95)",
            backgroundColor: "rgba(6, 182, 212, 0.08)",
            borderWidth: 3,
            pointRadius: 0,
            fill: true,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: { legend: { display: false } },
        scales: {
          y: {
            grid: { color: "rgba(148, 163, 184, 0.12)" },
            ticks: { color: "rgba(148, 163, 184, 0.9)" },
          },
          x: {
            grid: { display: false },
            ticks: { color: "rgba(148, 163, 184, 0.9)" },
          },
        },
      },
    });
  }

  const funnelCanvas = document.getElementById("funnelChart");
  if (funnelCanvas) {
    new window.Chart(funnelCanvas, {
      type: "bar",
      data: {
        labels: ["Visitors", "Trials", "PQL", "Closed Won"],
        datasets: [
          {
            data: [18920, 4300, 1260, 318],
            borderRadius: 10,
            backgroundColor: [
              "rgba(99, 102, 241, 0.9)",
              "rgba(139, 92, 246, 0.88)",
              "rgba(6, 182, 212, 0.84)",
              "rgba(34, 197, 94, 0.82)",
            ],
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            grid: { color: "rgba(148, 163, 184, 0.12)" },
            ticks: { color: "rgba(148, 163, 184, 0.9)" },
          },
          x: {
            grid: { display: false },
            ticks: { color: "rgba(148, 163, 184, 0.9)" },
          },
        },
      },
    });
  }
}

function initSwiper() {
  if (typeof window.Swiper === "undefined") {
    return;
  }

  const testimonialSlider = document.querySelector(".testimonials-swiper");
  if (testimonialSlider) {
    new window.Swiper(testimonialSlider, {
      slidesPerView: 1.08,
      spaceBetween: 18,
      pagination: {
        el: ".swiper-pagination",
        clickable: true,
      },
      breakpoints: {
        768: { slidesPerView: 2, spaceBetween: 22 },
        1200: { slidesPerView: 3, spaceBetween: 24 },
      },
    });
  }
}

function initYearStamp() {
  $all("[data-current-year]").forEach((node) => {
    node.textContent = new Date().getFullYear();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(themeState.current);
  initThemeToggle();
  initHeaderState();
  initMobileMenu();
  initAccordion();
  initTabs();
  initDropdowns();
  initModals();
  initReveal();
  initCounters();
  initDemoForms();
  initCharts();
  initSwiper();
  initYearStamp();
});
