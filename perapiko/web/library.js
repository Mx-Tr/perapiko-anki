// Loaded in Anki's deck browser, after the calendar module.
(() => {
  let root, viewport, gear, section, revision, paintCalendar;
  let opener,
    menuDeck,
    buried = new Set();
  const tiles = new Map();

  function request() {
    root.querySelector(".deck-activity").ariaBusy = "true";
    pycmd("pp:activity:" + revision);
  }

  function updateMenu(id) {
    const row = tiles.get(id);
    section.hidden = !row;
    if (!row) return;
    section.querySelector("strong").textContent = row.dataset.name;
    const filtered = row.dataset.filtered === "true";
    section.querySelector('[data-pp="deck-custom"]').hidden = filtered;
    for (const command of ["empty", "rebuild"])
      section.querySelector('[data-pp="deck-' + command + '"]').hidden =
        !filtered;
    section.querySelector('[data-pp="deck-unbury"]').hidden = !buried.has(id);
  }

  function select(id) {
    if (id === root.dataset.selected) return;
    for (const key of [root.dataset.selected, id]) {
      const row = tiles.get(key);
      if (!row) continue;
      row.dataset.active = String(key === id);
      row.querySelector(".tile-surface").ariaPressed = row.dataset.active;
    }
    root.dataset.selected = id;
    pycmd("pp:selected:" + id);
  }

  window.ppActivity = (epoch, data) => {
    if (!root || epoch !== revision) return;
    root.querySelector(".deck-activity").ariaBusy = "false";
    root.querySelector(".pp-activity-error").hidden = !!data;
    if (data) {
      paintCalendar(data.counts);
      buried = new Set();
      for (const id of data.buried) {
        let tile = tiles.get(id)?.parentElement;
        while (tile) {
          buried.add(tile.firstElementChild.dataset.id);
          tile = tile.parentElement.closest(".deck-tile");
        }
      }
      updateMenu(menuDeck || root.dataset.selected);
    }
    window.ppPainted?.();
  };

  window.ppInvalidate = (epoch, day) => {
    if (!root || epoch <= revision) return;
    revision = epoch;
    if (day !== root.dataset.day) return pycmd("pp:refresh");
    request();
  };

  function closeMenu(restore) {
    gear.open = false;
    if (restore) opener?.focus({ preventScroll: true });
    opener = null;
    menuDeck = null;
  }

  function contextMenu(tile, x, y) {
    if (gear.open) closeMenu(false);
    tile.querySelector(".tile-surface").focus({preventScroll: true});
    const id = tile.dataset.id;
    pycmd(["pp", "context", id, Math.round(x), Math.round(y), buried.has(id) ? 1 : 0].join(":"));
  }

  function onClick(event) {
    const tile = event.target.closest(".deck-row");
    if (tile && event.ctrlKey) {
      event.preventDefault();
      return contextMenu(tile, event.clientX, event.clientY);
    }
    if (event.target.closest(".pp-menu summary")) {
      if (gear.open) {
        event.preventDefault();
        closeMenu(true);
      } else {
        opener = gear.querySelector("summary");
        menuDeck = root.dataset.selected;
        updateMenu(menuDeck);
      }
      return;
    }
    const btn = event.target.closest("button[data-pp]");
    if (!btn || !root.contains(btn)) return;
    let [cmd, id] = btn.dataset.pp.split(":");
    if (cmd.startsWith("deck-")) id = menuDeck || root.dataset.selected;
    if (gear.open) {
      const focus = opener?.closest(".deck-row")?.dataset.id || "gear";
      sessionStorage.setItem("pp.focus." + root.dataset.session, focus);
      closeMenu(true);
    }
    if (cmd === "retry") return request();
    if (cmd === "select") return select(id);
    if (cmd === "start") {
      sessionStorage.setItem(
        "pp.scroll." + root.dataset.session,
        String(viewport.scrollTop),
      );
      if (event.detail === 0)
        sessionStorage.setItem(
          "pp.focus." + root.dataset.session,
          "start:" + id,
        );
      else sessionStorage.removeItem("pp.focus." + root.dataset.session);
    }
    pycmd("pp:" + cmd + (id ? ":" + id : ""));
  }

  function onKey(event) {
    const tile = event.target.closest(".deck-row");
    if (
      tile &&
      (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10"))
    ) {
      event.preventDefault();
      const rect = tile.getBoundingClientRect();
      return contextMenu(tile, rect.left + 12, rect.top + 12);
    }
    if (gear.open && event.key === "Escape") {
      event.preventDefault();
      return closeMenu(true);
    }
  }

  window.ppInitHome = (initial, epoch, day) => {
    if (root) return;
    root = document.getElementById("pp-home");
    if (!root) return;
    if (day !== root.dataset.day) return pycmd("pp:refresh");
    revision = epoch;
    viewport = root.querySelector(".deck-viewport");
    gear = root.querySelector(".pp-menu");
    section = gear.querySelector(".pp-deck-actions");
    for (const row of root.querySelectorAll(".deck-row"))
      tiles.set(row.dataset.id, row);
    updateMenu(root.dataset.selected);
    paintCalendar = window.ppCalendar(day, root.dataset.session);
    const scrollKey = "pp.scroll." + root.dataset.session;
    viewport.scrollTop = Number(sessionStorage.getItem(scrollKey)) || 0;
    viewport.addEventListener("scroll", () =>
      sessionStorage.setItem(scrollKey, viewport.scrollTop),
    );
    const pageKey = scrollKey + ".page";
    window.scrollTo(0, Number(sessionStorage.getItem(pageKey)) || 0);
    window.addEventListener("scroll", () =>
      sessionStorage.setItem(pageKey, scrollY),
    );
    const focusKey = "pp.focus." + root.dataset.session;
    const saved = sessionStorage.getItem(focusKey);
    if (saved) {
      const [cmd, id] = saved.split(":");
      const row = tiles.get(id || cmd);
      const study = row?.querySelector(".study-button");
      const target =
        cmd === "gear"
          ? gear.querySelector("summary")
          : cmd === "start" && study && !study.hidden
            ? study
            : row?.querySelector(".tile-surface");
      target?.focus({ preventScroll: true });
      sessionStorage.removeItem(focusKey);
    }
    root.addEventListener("dblclick", (event) => {
      if (event.target.matches(".tile-surface") && !event.ctrlKey)
        pycmd("pp:start:" + event.target.closest(".deck-row").dataset.id);
    });
    root.addEventListener("click", (event) => {
      const toggle = event.target.closest(".group-toggle");
      if (!toggle || event.ctrlKey) return;
      const children = document.getElementById(
        toggle.getAttribute("aria-controls"),
      );
      const expanded = children.hidden;
      children.hidden = !expanded;
      toggle.ariaExpanded = String(expanded);
      const row = toggle.closest(".deck-row");
      toggle.ariaLabel =
        (expanded ? "Collapse · " : "Expand · ") + row.dataset.name;
      pycmd("pp:group:" + row.dataset.id + ":" + expanded);
    });
    // Keep pointer focus inside the menu until the dismissal click is consumed.
    // Otherwise focusin closes it early and the underlying button also activates.
    document.addEventListener(
      "pointerdown",
      (event) => {
        if (
          gear.open &&
          event.button === 0 &&
          !event.ctrlKey &&
          !gear.contains(event.target)
        )
          event.preventDefault();
      },
      true,
    );
    document.addEventListener(
      "click",
      (event) => {
        if (gear.open && !event.ctrlKey && !gear.contains(event.target)) {
          event.preventDefault();
          event.stopImmediatePropagation();
          closeMenu(true);
        }
      },
      true,
    );
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    document.addEventListener("contextmenu", (event) => {
      const tile = event.target.closest(".deck-row");
      if (tile) {
        event.preventDefault();
        contextMenu(tile, event.clientX, event.clientY);
      }
    });
    document.addEventListener("focusin", (e) => {
      if (gear.open && !gear.contains(e.target)) closeMenu(false);
    });
    if (initial) window.ppActivity(epoch, initial);
    else request();
    const midnight = new Date();
    midnight.setHours(24, 0, 0, 50);
    setTimeout(() => pycmd("pp:day"), midnight - Date.now());
    window.addEventListener("focus", () => pycmd("pp:day"));
  };
})();
