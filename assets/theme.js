(() => {
  "use strict";

  const storageKey = "jwknt-theme";
  const legacyStorageKeys = ["bst-reader-theme", "solverTheme"];
  const darkMedia = window.matchMedia("(prefers-color-scheme: dark)");
  const root = document.documentElement;
  let followsSystem = true;

  function storedTheme() {
    try {
      const current = localStorage.getItem(storageKey);
      if (current === "dark" || current === "light") return current;

      for (const legacyKey of legacyStorageKeys) {
        const legacy = localStorage.getItem(legacyKey);
        if (legacy === "dark" || legacy === "light") {
          localStorage.setItem(storageKey, legacy);
          return legacy;
        }
      }
    } catch {
      // A private or restricted browsing context may deny storage.
    }
    return "";
  }

  function updateControls(theme) {
    const isDark = theme === "dark";
    const label = isDark ? "Use light theme" : "Use dark theme";
    for (const button of document.querySelectorAll("[data-theme-toggle]")) {
      button.setAttribute("aria-pressed", String(isDark));
      button.setAttribute("aria-label", label);
      button.title = label;
    }
  }

  function applyTheme(theme) {
    const isDark = theme === "dark";
    root.dataset.theme = theme;
    root.classList.toggle("dark", isDark);
    root.style.colorScheme = theme;

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = isDark ? "#121416" : "#ffffff";

    updateControls(theme);
    window.dispatchEvent(new CustomEvent("jwknt:themechange", { detail: { theme } }));
  }

  function createControl() {
    if (document.querySelector("[data-theme-toggle]")) return;

    const button = document.createElement("button");
    button.className = "theme-toggle";
    button.type = "button";
    button.dataset.themeToggle = "";
    button.textContent = "◐";

    const slot = document.querySelector(
      "[data-theme-toggle-slot], .site-header nav, header nav, .toolbar, .detail-nav",
    );
    if (slot) {
      slot.append(button);
    } else {
      button.classList.add("theme-toggle--floating");
      document.body.prepend(button);
    }
  }

  const savedTheme = storedTheme();
  followsSystem = !savedTheme;
  applyTheme(savedTheme || (darkMedia.matches ? "dark" : "light"));

  function setupControls() {
    createControl();
    updateControls(root.dataset.theme);

    for (const button of document.querySelectorAll("[data-theme-toggle]")) {
      if (button.dataset.themeBound === "true") continue;
      button.dataset.themeBound = "true";
      button.addEventListener("click", () => {
        const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
        followsSystem = false;
        try {
          localStorage.setItem(storageKey, nextTheme);
        } catch {
          // A private or restricted browsing context may deny storage.
        }
        applyTheme(nextTheme);
      });
    }
  }

  const followSystemChange = (event) => {
    if (followsSystem) applyTheme(event.matches ? "dark" : "light");
  };
  if (typeof darkMedia.addEventListener === "function") {
    darkMedia.addEventListener("change", followSystemChange);
  } else if (typeof darkMedia.addListener === "function") {
    darkMedia.addListener(followSystemChange);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupControls, { once: true });
  } else {
    setupControls();
  }
})();

