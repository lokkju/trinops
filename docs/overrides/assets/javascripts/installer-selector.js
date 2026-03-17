(function () {
  const STORAGE_KEY = "trinops-installer";
  const INSTALLERS = {
    uvx: { prefix: "uvx ", install: null },
    pipx: { prefix: "pipx run ", install: null },
    pip: { prefix: "", install: "pip install trinops" },
  };

  function getInstaller() {
    return localStorage.getItem(STORAGE_KEY) || "uvx";
  }

  function setInstaller(name) {
    localStorage.setItem(STORAGE_KEY, name);
    applyInstaller(name);
  }

  function applyInstaller(name) {
    // Update selector buttons
    document.querySelectorAll(".installer-selector button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.installer === name);
    });

    // Update code blocks marked with data-install-command
    document.querySelectorAll("[data-install-command]").forEach((el) => {
      const cmd = el.dataset.installCommand;
      const installer = INSTALLERS[name];
      if (installer.install && cmd === "install") {
        el.textContent = installer.install;
      } else {
        el.textContent = installer.prefix + "trinops " + cmd;
      }
    });
  }

  function init() {
    // Bind click handlers on selector buttons
    document.querySelectorAll(".installer-selector button").forEach((btn) => {
      btn.addEventListener("click", () => setInstaller(btn.dataset.installer));
    });
    applyInstaller(getInstaller());
  }

  // Support MkDocs Material instant navigation
  if (typeof document$ !== "undefined") {
    document$.subscribe(() => init());
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
