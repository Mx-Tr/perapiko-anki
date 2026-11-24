from aqt import dialogs, gui_hooks, mw
from aqt.qt import QMenu, QPoint

from .library import DECK_COMMANDS
from .preferences import menu_font
from aqt.customstudy import CustomStudy
from aqt.operations import QueryOp
from aqt.operations.deck import set_current_deck
from aqt.operations.scheduling import (
    empty_filtered_deck,
    rebuild_filtered_deck,
    unbury_deck,
)


def statistics(did=None):
    def open_dialog(_=None):
        if mw.state != "deckBrowser":
            return
        dialog = dialogs.open("NewDeckStats", mw)
        if did is not None:
            dialog.deck_chooser.selected_deck_id = did
        # The native graphs page initially scopes its results to deck:current.
        # Refresh reused windows too, then select Collection in Anki's own controls.
        dialog.refresh()
        if did is None:
            dialog.form.web.eval("""
              (() => {
                const apply = () => {
                  const scope = document.querySelector('.range-box input[type=radio][value="2"]');
                  if (scope) scope.click();
                  return !!scope;
                };
                if (apply()) return;
                const observer = new MutationObserver(() => { if (apply()) observer.disconnect(); });
                observer.observe(document.documentElement, {childList:true, subtree:true});
              })()
            """)

    if did is None:
        open_dialog()
    else:
        set_current_deck(parent=mw, deck_id=did).success(
            open_dialog
        ).run_in_background()


def run(browser, command, did, filtered):
    # A tile's menu can target a deck other than Anki's current study deck.
    actions = {
        "options": browser._options,
        "rename": browser._rename,
        "export": browser._export,
        "delete": browser._delete,
    }
    if command in actions:
        actions[command](did)
    elif command == "stats":
        statistics(did)
    elif command == "unbury":
        unbury_deck(parent=mw, deck_id=did).run_in_background()
    elif filtered and command in ("empty", "rebuild"):
        operation = empty_filtered_deck if command == "empty" else rebuild_filtered_deck
        operation(parent=mw, deck_id=did).run_in_background()
    elif command == "custom" and not filtered:
        collection = mw.col

        def open_dialog(data):
            if mw.col is collection and mw.state == "deckBrowser":
                count, defaults = data
                CustomStudy(mw=mw, deck_id=did, card_count=count, defaults=defaults)

        QueryOp(
            parent=mw,
            op=lambda col: (
                col.decks.card_count(did, True),
                col.sched.custom_study_defaults(did),
            ),
            success=open_dialog,
        ).run_in_background()


def popup(browser, did, filtered, buried, x, y, package):
    menu = QMenu(browser.web)
    menu.setFont(menu_font(package))
    menu.setStyleSheet("""
        QMenu { color: #463242; background: #fffaf7; border: 1px solid #dfd4da;
                border-radius: 9px; padding: 5px; }
        QMenu::item { padding: 6px 24px; border-radius: 5px; }
        QMenu::item:selected { background: #f1e7ef; }
        QMenu::item:disabled { color: #897c83; }
        QMenu::separator { height: 1px; background: #dfd4da; margin: 4px; }
    """)
    menu.addSection(mw.col.decks.name(did))
    for label, command in DECK_COMMANDS:
        if command == "custom" and filtered:
            continue
        if command in ("rebuild", "empty") and not filtered:
            continue
        if command == "unbury" and not buried:
            continue
        if command == "delete":
            menu.addSeparator()
        action = menu.addAction(label)
        action.setData(command)
        action.triggered.connect(lambda checked=False, cmd=command: run(browser, cmd, did, filtered))
    gui_hooks.deck_browser_will_show_options_menu(menu, did)
    menu.aboutToHide.connect(menu.deleteLater)
    scale = browser.web.zoomFactor()
    menu.popup(browser.web.mapToGlobal(QPoint(round(x * scale), round(y * scale))))
