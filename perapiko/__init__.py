import json
from datetime import date
from html import escape
from uuid import uuid4

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser, DeckBrowserBottomBar
from aqt.operations import QueryOp
from aqt.operations.deck import set_current_deck
from aqt.overview import Overview
from aqt.qt import QLabel, Qt, QTimer
from aqt.reviewer import Reviewer, ReviewerBottomBar
from aqt.sound import av_player
from aqt.utils import showWarning

from . import deck_actions, preferences
from .library import activity, button, decks, library, menu

package = mw.addonManager.addonFromModule(__name__)
assets = f"/_addons/{package}/web"
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js|webp)")

mw.addonManager.setConfigAction(package, lambda: preferences.choose(package))

# The selection is local to the library until the user starts studying.
selected = None
available = {}
generation = 0
activity_cache = None
activity_revision = 0
library_session = uuid4().hex
calendar_day = date.today()
starting = False
reviewed = 0
finished = False
manual_end = False
screen_cover = None
waiting_for = set()
playing_commands = []


def study_header(name, actions=False):
    more = (
        menu(
            "···",
            "Card actions",
            [
                ("Edit note", "edit"),
                ("Bury card", "bury"),
                ("Suspend card", "suspend"),
                ("More Anki actions", "more"),
                ("End session", "finish"),
            ],
        )
        if actions
        else ""
    )
    back = button(
        "‹",
        "home",
        **{
            "class": "pp-return",
            "title": "Back to decks",
            "aria-label": "Back to decks",
        },
    )
    return f'<header class="pp-study-nav">{back}<span class="review-deck-name">{escape(name)}</span>{more}</header>'


def deck_name():
    return mw.col.decks.current()["name"]


def web_content(content, context):
    global available, selected
    if isinstance(context, DeckBrowser):
        data = context._render_data
        entries = decks(data.tree)
        if calendar_day != date.today():
            invalidate_activity()
        available = {node.deck_id: node for node in entries}
        if selected not in available:
            selected = (
                data.current_deck_id
                if data.current_deck_id in available
                else next(iter(available), 0)
            )
        # Preserve HTML contributed by deck_browser_will_render_content, including
        # the original DeckBrowser bridge used by those controls.
        extras = content.body.replace(context._renderDeckTree(data.tree), "", 1)
        extras = extras.replace(context._renderStats(), "", 1)
        shell = context._body % {"tree": "", "stats": ""}
        extras = extras.replace(shell, "", 1)
        content.body = library(
            data.tree,
            selected,
            mw.pm.profile.get("perapikoClosedGroups", []),
            calendar_day,
            library_session,
        ) + extras
        content.js.extend([f"{assets}/calendar.js", f"{assets}/library.js"])
        sheets = ["common", "library"]
    elif isinstance(context, DeckBrowserBottomBar):
        # Qt reuses this view for grading. Its old document can still be painted
        # while the reviewer's HTML is loading.
        content.head += (
            "<style>html {background:#faf7f3} body {visibility:hidden}</style>"
        )
        return
    elif isinstance(context, Reviewer):
        content.body = study_header(deck_name(), actions=True) + content.body
        sheets = ["common", "review"]
    elif isinstance(context, ReviewerBottomBar):
        if mw.col.conf.get("dueCounts", True):
            counts = " · ".join(
                f'<span><b data-queue="{queue}"></b> {label}</span>'
                for queue, label in (
                    ("new", "new"),
                    ("learning", "learning"),
                    ("due", "review"),
                )
            )
            content.body = content.body.replace(
                "<table id=innertable",
                f'<p id="pp-count" aria-label="Remaining cards">{counts}</p><table id=innertable',
                1,
            )
        sheets = ["common", "answers"]
    elif isinstance(context, Overview) and finished:
        sheets = ["common", "review"]
    else:
        return
    content.head += preferences.style(package)
    content.css.extend(f"{assets}/{name}.css" for name in sheets)
    if screen_cover is not None:
        content.head += f'<meta name="pp-transition" content="{generation}">'
    content.js.append(f"{assets}/interface.js")


def home_ready(browser):
    initial = activity_cache
    browser.web.eval(
        f"window.ppInitHome?.({json.dumps(initial)}, {activity_revision}, {json.dumps(calendar_day.isoformat())})"
    )


def release_screen(ticket):
    global screen_cover
    if ticket == generation and screen_cover is not None:
        screen_cover.hide()
        screen_cover.deleteLater()
        screen_cover = None
        waiting_for.clear()


def hold_screen(new):
    global screen_cover
    # The card and answer bar are separate Chromium surfaces. Keep the last
    # composed frame until both replacements have painted.
    if screen_cover is None:
        parent = mw.centralWidget()
        if not parent.isVisible():
            return
        frame = parent.grab()
        screen_cover = QLabel(parent)
        screen_cover.setGeometry(parent.rect())
        screen_cover.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        screen_cover.setPixmap(frame)
        screen_cover.show()
        screen_cover.raise_()
    waiting_for.clear()
    waiting_for.add("page")
    if new == "review":
        waiting_for.add("answers")
    ticket = generation
    # A third-party card script or interrupted navigation must never trap input.
    QTimer.singleShot(1200, lambda: release_screen(ticket))


def before_state(new, old):
    global reviewed, finished, manual_end, generation, starting, selected
    generation += 1
    starting = False
    if old in ("review", "deckBrowser") or (old == "overview" and finished):
        if new != old and (
            new in ("deckBrowser", "review") or (old == "review" and new == "overview")
        ):
            hold_screen(new)
        else:
            release_screen(generation)
    else:
        release_screen(generation)
    if new == "review" and old != "resetRequired":
        if not (old == "overview" and finished and manual_end):
            reviewed = 0
        manual_end = False
    if new == "overview" and old == "review":
        finished = True
    elif new != "overview":
        finished = False
    if new == "profileManager":
        selected = None


def after_state(new, old):
    # An empty review may already have transitioned to the overview inside nextCard().
    state = mw.state
    themed = state in ("deckBrowser", "review") or (state == "overview" and finished)
    mw.toolbarWeb.setVisible(not themed)
    mw.bottomWeb.setVisible(
        state != "deckBrowser" and not (state == "overview" and finished)
    )


def summary(overview):
    if mw.state != "overview" or not finished:
        return
    title = "Session ended" if manual_end else "Queue complete"
    detail = f"Reviews this session · {reviewed}"
    if not reviewed and not manual_end:
        title = "No cards due"
    action = (
        button("Resume studying", "resume")
        if manual_end
        else button("Back to decks", "home")
    )
    overview.web.stdHtml(
        study_header(deck_name())
        + f"""
<main class="pp-summary"><img src="{assets}/shore.webp" alt=""><section><h1>{title}</h1>
<p>{detail}</p>{action}</section></main>""",
        context=overview,
    )
    mw.bottomWeb.setVisible(False)


def start():
    mw.col.startTimebox()
    mw.moveToState("review")


def enter(did):
    global starting
    if starting or did not in available:
        return
    starting = True
    ticket = generation

    def ready(_):
        global starting, selected
        if generation == ticket and mw.state == "deckBrowser":
            starting = False
            selected = did
            start()

    def failed(error):
        global starting
        starting = False
        showWarning(str(error), parent=mw)

    set_current_deck(parent=mw, deck_id=did).success(ready).failure(
        failed
    ).run_in_background(initiator=mw.deckBrowser)


def invalidate_activity(*_):
    global activity_revision, calendar_day, activity_cache
    activity_revision += 1
    calendar_day = date.today()
    activity_cache = None
    if mw.state == "deckBrowser":
        mw.web.eval(
            f"window.ppInvalidate?.({activity_revision}, {json.dumps(calendar_day.isoformat())})"
        )


def profile_closed():
    global selected, library_session, available
    selected = None
    available = {}
    library_session = uuid4().hex
    invalidate_activity()


def collection_changed(changes, handler):
    if (
        changes.card
        or changes.deck
        or changes.study_queues
        or changes.deck_config
        or changes.config
    ):
        invalidate_activity()


def load_activity(revision):
    if revision != activity_revision:
        return
    session = library_session

    def deliver(result):
        global activity_cache
        if revision != activity_revision or session != library_session:
            return
        activity_cache = result
        if mw.state == "deckBrowser":
            mw.web.eval(f"window.ppActivity?.({revision}, {json.dumps(result)})")

    if activity_cache is not None:
        deliver(activity_cache)
    else:
        QueryOp(parent=mw, op=activity, success=deliver).failure(
            lambda _: deliver(None)
        ).run_in_background()


def bridge(handled, message, context):
    global manual_end, selected
    if handled[0] or not message.startswith("pp:"):
        return handled
    command, _, arg = message[3:].partition(":")
    state = mw.state
    if command == "painted":
        if screen_cover is not None and arg == str(generation):
            waiting_for.discard(
                "answers" if isinstance(context, ReviewerBottomBar) else "page"
            )
            if not waiting_for:
                release_screen(generation)
        return (True, None)
    if isinstance(context, DeckBrowser) and state == "deckBrowser":
        if command == "activity" and arg.isdecimal():
            load_activity(int(arg))
        elif command == "group":
            did, _, expanded = arg.partition(":")
            if (
                did.isdecimal()
                and int(did) in available
                and expanded in ("true", "false")
            ):
                closed = set(mw.pm.profile.get("perapikoClosedGroups", []))
                if expanded == "true":
                    closed.discard(int(did))
                else:
                    closed.add(int(did))
                mw.pm.profile["perapikoClosedGroups"] = sorted(closed)
        elif (
            command == "selected"
            and arg.isdecimal()
            and int(arg) in available
            and not starting
        ):
            selected = int(arg)
        elif command == "start" and arg.isdecimal():
            enter(int(arg))
        elif command == "day" and date.today() != calendar_day:
            invalidate_activity()
        elif command == "refresh":
            context.refresh()
        elif command == "context":
            parts = arg.split(":")
            if len(parts) == 4 and all(p.isdecimal() and len(p) <= 19 for p in parts):
                did, x, y, buried = map(int, parts)
                if did in available and x <= 100000 and y <= 100000:
                    deck_actions.popup(context, did, available[did].filtered, bool(buried), x, y, package)
        elif command.startswith("deck-") and arg.isdecimal() and int(arg) in available:
            did = int(arg)
            deck_actions.run(context, command[5:], did, available[did].filtered)
        elif command == "stats":
            deck_actions.statistics()
        elif command in ("add", "browse", "sync"):
            mw.toolbar._linkHandler(command)
        elif command in ("create", "import", "shared"):
            context._linkHandler(command)
    elif isinstance(context, Reviewer) and state == "review":
        if command == "home":
            mw.moveToState("deckBrowser")
        elif context.card and context.state in ("question", "answer"):
            if command == "finish":
                manual_end = True
                mw.moveToState("overview")
            elif command == "stop-audio" and arg in playing_commands:
                av_player.stop_and_clear_queue()
            elif command == "more":
                context.showContextMenu()
            elif command == "edit":
                mw.onEditCurrent()
            elif command == "bury":
                context.bury_current_card()
            elif command == "suspend":
                context.suspend_current_card()
    elif isinstance(context, Overview) and state == "overview" and finished:
        if command == "home":
            mw.moveToState("deckBrowser")
        elif command == "resume":
            start()
    return (True, None)


def audio_started(player, tag):
    global playing_commands
    card = mw.reviewer.card if mw.state == "review" else None
    if card is None:
        return
    filename = getattr(tag, "filename", None)
    side = "a" if mw.reviewer.state == "answer" else "q"
    tags = card.answer_av_tags() if side == "a" else card.question_av_tags()
    playing_commands = [f"play:{side}:{i}" for i, item in enumerate(tags)
                        if filename and getattr(item, "filename", None) == filename]
    mw.web.eval(f"window.ppAudioState?.({json.dumps(playing_commands)})")


def audio_ended(player):
    global playing_commands
    if playing_commands and mw.state == "review":
        mw.web.eval("window.ppAudioState?.([])")
    playing_commands = []


def question(card):
    current_queue, counts = mw.reviewer._v3.counts()
    mw.bottomWeb.eval(
        f"""document.querySelectorAll("#pp-count > span").forEach((item, index) => {{
            item.querySelector("b").textContent = {json.dumps(counts)}[index];
            item.setAttribute("aria-current", String(index === {current_queue}));
        }});"""
    )


def answered(reviewer, card, ease):
    global reviewed
    reviewed += 1


def answer_labels(buttons, reviewer, card):
    if tuple(ease for ease, _ in buttons) == (1, 2, 3, 4):
        return tuple(enumerate(("Again", "Hard", "Good", "Easy"), 1))
    return buttons


gui_hooks.webview_will_set_content.append(web_content)
gui_hooks.webview_did_receive_js_message.append(bridge)
gui_hooks.deck_browser_did_render.append(home_ready)
gui_hooks.state_will_change.append(before_state)
gui_hooks.state_did_change.append(after_state)
gui_hooks.overview_did_refresh.append(summary)
gui_hooks.reviewer_did_show_question.append(question)
gui_hooks.reviewer_did_answer_card.append(answered)
gui_hooks.av_player_did_begin_playing.append(audio_started)
gui_hooks.av_player_did_end_playing.append(audio_ended)
gui_hooks.reviewer_will_init_answer_buttons.append(answer_labels)

gui_hooks.operation_did_execute.append(collection_changed)
gui_hooks.sync_did_finish.append(invalidate_activity)
gui_hooks.day_did_change.append(invalidate_activity)
gui_hooks.profile_will_close.append(profile_closed)
gui_hooks.collection_did_load.append(invalidate_activity)
