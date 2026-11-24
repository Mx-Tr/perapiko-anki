window.ppCalendar = function (snapshotDay, session) {
  let collectionReviews = {};
  const calendarGrid = document.querySelector(".calendar-grid");
  const dayLabel = document.querySelector(".day-label");
  const monthName = new Intl.DateTimeFormat("en-US", {
    month: "short",
    timeZone: "UTC",
  });
  const fullDate = new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
  const rangePicker = document.querySelector(".range-picker");
  const rangeTrigger = rangePicker.querySelector("summary");
  const dayCells = [];
  let pickedDay;
  const rangeKey = "pp.months." + session;
  const options = [...rangePicker.querySelectorAll("[data-months]")];

  function selectRange(option) {
    options.forEach((item) => (item.ariaPressed = String(item === option)));
    rangeTrigger.textContent = option.textContent;
  }
  const saved = options.find(
    (option) => option.dataset.months === sessionStorage.getItem(rangeKey),
  );
  if (saved) selectRange(saved);

  function buildCalendar() {
    const today = new Date(snapshotDay + "T12:00:00Z");
    const start = new Date(today);
    start.setUTCDate(1);
    start.setUTCMonth(
      start.getUTCMonth() -
        Number(
          rangePicker.querySelector('[aria-pressed="true"]').dataset.months,
        ) +
        1,
    );
    calendarGrid.replaceChildren();
    dayCells.length = 0;
    let week = 0;

    for (
      const date = new Date(start);
      date <= today;
      date.setUTCDate(date.getUTCDate() + 1)
    ) {
      const day = date.getUTCDate();
      const weekday = (date.getUTCDay() + 6) % 7;
      if (week === 0 || weekday === 0) week++;
      if (day === 1) {
        const label = document.createElement("span");
        label.className = "calendar-month";
        label.style.gridArea = "1 / " + week;
        label.textContent = monthName.format(date);
        if (!calendarGrid.firstChild) {
          ["Mon", "", "Wed", "", "Fri", "", "Sun"].forEach((text, index) => {
            if (!text) return;
            const weekdayLabel = document.createElement("span");
            weekdayLabel.className = "calendar-weekday";
            weekdayLabel.textContent = text;
            weekdayLabel.style.gridArea = index + 2 + " / 1";
            calendarGrid.append(weekdayLabel);
          });
        }
        calendarGrid.append(label);
      }
      const cell = document.createElement("button");
      cell.className = "calendar-day";
      cell.dataset.day = date.toISOString().slice(0, 10);
      cell.dataset.label = fullDate.format(date);
      cell.ariaLabel = cell.dataset.label;
      cell.tabIndex = -1;
      cell.style.gridArea = weekday + 2 + " / " + week;
      calendarGrid.append(cell);
      dayCells.push(cell);
    }
    calendarGrid.style.setProperty("--weeks", week);
    dayCells.at(-1).setAttribute("aria-current", "date");
    dayCells.at(-1).tabIndex = 0;
  }
  function inspectDay(cell, remember = false) {
    calendarGrid
      .querySelector("[data-inspected]")
      ?.removeAttribute("data-inspected");
    if (cell) cell.dataset.inspected = "true";
    dayLabel.textContent = cell?.getAttribute("aria-label") ?? "";
    if (remember) {
      calendarGrid.querySelector('[tabindex="0"]').tabIndex = -1;
      cell.tabIndex = 0;
      pickedDay = cell;
    }
  }
  function paintCalendar() {
    const day = new Date(snapshotDay + "T12:00:00Z");
    const key = () => day.toISOString().slice(0, 10);
    if (!collectionReviews[key()]) day.setUTCDate(day.getUTCDate() - 1);
    let streak = 0;
    while (collectionReviews[key()]) {
      streak++;
      day.setUTCDate(day.getUTCDate() - 1);
    }
    document.querySelector(".study-streak strong").textContent =
      streak + (streak === 1 ? " day" : " days");
    pickedDay = null;
    for (const cell of dayCells) {
      const n = collectionReviews[cell.dataset.day] ?? 0;
      cell.dataset.level =
        n >= 60 ? 4 : n >= 30 ? 3 : n >= 10 ? 2 : n > 0 ? 1 : 0;
      cell.setAttribute(
        "aria-label",
        cell.dataset.label + " · " + n + " " + (n === 1 ? "review" : "reviews"),
      );
      cell.tabIndex = cell === dayCells.at(-1) ? 0 : -1;
    }
    inspectDay(null);
  }
  function showRange() {
    buildCalendar();
    paintCalendar();
  }
  rangePicker.addEventListener("click", (event) => {
    const option = event.target.closest("[data-months]");
    if (!option) return;
    selectRange(option);
    sessionStorage.setItem(rangeKey, option.dataset.months);
    rangePicker.open = false;
    rangeTrigger.focus();
    showRange();
  });
  rangePicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && rangePicker.open) {
      rangePicker.open = false;
      rangeTrigger.focus();
    }
  });
  for (const name of ["pointerdown", "focusin"]) {
    document.addEventListener(name, (event) => {
      if (!rangePicker.contains(event.target)) rangePicker.open = false;
    });
  }
  for (const name of ["focusin", "click", "pointerover"]) {
    calendarGrid.addEventListener(name, (e) => {
      if (e.target.matches(".calendar-day"))
        inspectDay(e.target, name !== "pointerover");
    });
  }
  calendarGrid.addEventListener("pointerleave", () => inspectDay(pickedDay));
  calendarGrid.addEventListener("keydown", (e) => {
    const i = dayCells.indexOf(e.target);
    if (i < 0) return;
    const weekday = (new Date(e.target.dataset.day).getUTCDay() + 6) % 7;
    const next = {
      ArrowLeft: i - 7,
      ArrowRight: i + 7,
      ArrowUp: weekday > 0 ? i - 1 : i,
      ArrowDown: weekday < 6 ? i + 1 : i,
      Home: 0,
      End: dayCells.length - 1,
    }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    dayCells[Math.max(0, Math.min(dayCells.length - 1, next))].focus();
  });
  buildCalendar();
  return (counts) => {
    collectionReviews = counts;
    paintCalendar();
  };
};
