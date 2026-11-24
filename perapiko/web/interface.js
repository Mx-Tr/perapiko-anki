(() => {
  const transition = document.querySelector('meta[name="pp-transition"]');
  if (transition) {
    window.ppPainted = () => {
      window.ppPainted = undefined;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => pycmd("pp:painted:" + transition.content)),
      );
    };
  }
  // Consume the first click outside an open card menu, including a click on Back.
  for (const type of ["pointerdown", "click"]) {
    document.addEventListener(
      type,
      (event) => {
        const menu = document.querySelector(".pp-study-nav .pp-menu[open]");
        if (!menu || menu.contains(event.target)) return;
        event.preventDefault();
        if (type === "click") {
          event.stopImmediatePropagation();
          menu.open = false;
          menu.querySelector("summary").focus({ preventScroll: true });
        }
      },
      true,
    );
  }

  // Optional playback feedback for templates using Anki's native replay links.
  let activeCommands = [];
  function replayCommand(link) {
    return link.getAttribute("onclick")?.match(/play:[qa]:\d+/)?.[0];
  }
  window.ppAudioState = (commands) => {
    activeCommands = commands;
    for (const link of document.querySelectorAll("[data-perapiko-replay] .replay-button"))
      link.ariaPressed = String(commands.includes(replayCommand(link)));
  };
  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-perapiko-replay] .replay-button");
    if (!link || !activeCommands.includes(replayCommand(link))) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    pycmd("pp:stop-audio:" + replayCommand(link));
  }, true);

  document.addEventListener("click", (event) => {
    const open = document.querySelector(".pp-study-nav .pp-menu[open]");
    const button = event.target.closest(
      ".pp-study-nav [data-pp], .pp-summary [data-pp]",
    );
    if (!button) return;
    if (open) {
      open.open = false;
      open.querySelector("summary").focus({ preventScroll: true });
    }
    pycmd("pp:" + button.dataset.pp);
  });

  document.addEventListener("keydown", (event) => {
    const menu = document.querySelector(".pp-study-nav .pp-menu[open]");
    if (event.key === "Escape" && menu) {
      event.preventDefault();
      menu.open = false;
      menu.querySelector("summary").focus({ preventScroll: true });
    }
  });

  document.addEventListener("keydown", (event) => {
    const menu = event.target.closest?.(".pp-menu");
    if (!menu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key))
      return;
    if (!menu.open && !event.key.startsWith("Arrow")) return;
    event.preventDefault();
    if (!menu.open) menu.querySelector("summary").click();
    const items = [...menu.querySelectorAll(".pp-popup button")].filter(
      (button) => button.getClientRects().length && !button.disabled,
    );
    if (!items.length) return;
    const index = items.indexOf(document.activeElement);
    let next = 0;
    if (event.key === "End" || (event.key === "ArrowUp" && index <= 0))
      next = items.length - 1;
    else if (event.key === "ArrowUp") next = index - 1;
    else if (event.key === "ArrowDown") next = (index + 1) % items.length;
    items[next].focus();
  });

  document.addEventListener("focusin", (event) => {
    const menu = document.querySelector(".pp-study-nav .pp-menu[open]");
    if (menu && !menu.contains(event.target)) menu.open = false;
  });

  function init() {
    if (document.querySelector(".pp-summary")) window.ppPainted?.();
    const qa = document.getElementById("qa");
    if (qa) {
      const format = () => {
        if (qa.hasChildNodes() && qa.style.opacity === "1")
          window.ppPainted?.();
      };
      new MutationObserver(format).observe(qa, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["style"],
      });
      format();
    }
    const middle = document.getElementById("middle");
    if (middle) {
      const format = () => {
        const reveal = middle.querySelector("#ansbut");
        if (reveal && !reveal.querySelector("kbd")) {
          const key = document.createElement("kbd");
          key.textContent = "Space";
          reveal.replaceChildren("Show answer ", key);
        }
        if (reveal || middle.querySelector("[data-ease]")) window.ppPainted?.();
      };
      new MutationObserver(format).observe(middle, {
        childList: true,
        subtree: true,
      });
      format();
    }
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
