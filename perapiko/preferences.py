import json

from aqt import mw
from aqt.qt import QFont, QFontDatabase, QInputDialog


def family(package):
    name = (mw.addonManager.getConfig(package) or {}).get("interfaceFont", "")
    return name if name and name in QFontDatabase.families() else ""


def css_stack(name):
    # Quote the family as one CSS string, even if it contains spaces or punctuation.
    primary = json.dumps(name, ensure_ascii=False) + ", " if name else ""
    return primary + "system-ui, sans-serif"


def style(package):
    value = css_stack(family(package)).replace("<", r"\3c ")
    return f"<style>:root:root{{--pp-font:{value}}}</style>"


def menu_font(package):
    name = family(package)
    return QFont(name) if name else mw.font()


def choose(package):
    choices = ["System default", *QFontDatabase.families()]
    current = family(package)
    choice, accepted = QInputDialog.getItem(
        mw, "Perapiko", "Interface font", choices, choices.index(current) if current else 0, False
    )
    if not accepted:
        return
    name = "" if choice == choices[0] else choice
    config = mw.addonManager.getConfig(package) or {}
    config["interfaceFont"] = name
    mw.addonManager.writeConfig(package, config)
    if mw.state == "deckBrowser":
        mw.deckBrowser.refresh()
    elif mw.state == "review":
        # Apply without restarting the current card.
        script = f"document.documentElement.style.setProperty('--pp-font', {json.dumps(css_stack(name))})"
        for web in (mw.web, mw.bottomWeb):
            web.eval(script)
