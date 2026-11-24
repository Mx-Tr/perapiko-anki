from html import escape


def visible_nodes(tree):
    for node in tree.children:
        if node.deck_id != 1 or node.total_including_children or node.children:
            yield node


def decks(tree):
    for node in visible_nodes(tree):
        yield node
        yield from decks(node)


def button(label, action, **attrs):
    extra = " ".join(
        f'{key}="{escape(str(value), quote=True)}"' for key, value in attrs.items()
    )
    return f'<button type="button" data-pp="{escape(action)}" {extra}>{label}</button>'


def menu(symbol, title, items, extra="", group_label=""):
    links = "".join(button(label, cmd) for label, cmd in items)
    if group_label:
        links = f'<section class="pp-global-actions"><strong>{escape(group_label)}</strong>{links}</section>'
    return (
        f'<details class="pp-menu"><summary aria-label="{title}" title="{title}">{symbol}</summary>'
        f'<div class="pp-popup">{links}{extra}</div></details>'
    )


def tiles(tree, selected, closed, prefix="", depth=0):
    result = []
    for node in visible_nodes(tree):
        did = node.deck_id
        name = prefix + node.name
        full_name = escape(name, quote=True)
        counts = "".join(
            f'<span><b data-queue="{label}">{count}</b> {label}</span>'
            for label, count in zip(
                ("new", "learning", "due"),
                (node.new_count, node.learn_count, node.review_count),
            )
            if count
        )
        children = toggle = ""
        if node.children:
            expanded = did not in closed
            toggle = f"""<button class="group-toggle" aria-controls="children-{did}"
                aria-expanded="{str(expanded).lower()}" aria-label="{"Collapse" if expanded else "Expand"} · {full_name}"></button>"""
            nested = tiles(node, selected, closed, name + "::", depth + 1)
            children = f'<ul class="deck-children" id="children-{did}" {"" if expanded else "hidden"}>{nested}</ul>'
        active = str(did == selected).lower()
        result.append(f"""
<li class="deck-tile"><div class="deck-row" data-id="{did}" data-name="{full_name}"
 data-active="{active}" data-filtered="{str(node.filtered).lower()}" style="--depth:{depth}">
 {toggle}<button class="tile-surface" data-pp="select:{did}" aria-pressed="{active}"
 aria-label="Select · {full_name}" aria-describedby="counts-{did}"></button>
 <div class="tile-details"><strong class="tile-heading">{escape(node.name)}</strong>
 <span class="tile-counts" id="counts-{did}">{counts or "Done for today"}</span></div>
 <button class="study-button" data-pp="start:{did}" aria-label="Study · {full_name}" {"" if counts else "hidden"}>Study</button>
</div>{children}</li>""")
    return "".join(result)


def activity(col):
    # A review belongs to the collection even if its card later moves decks.
    counts = col.db.all("""
        SELECT date(id / 1000, 'unixepoch', 'localtime'), count(*) FROM revlog
        WHERE ease BETWEEN 1 AND 4 GROUP BY 1
    """)
    buried = col.db.list("SELECT DISTINCT did FROM cards WHERE queue IN (-2,-3)")
    return {"counts": dict(counts), "buried": [str(did) for did in buried]}


DECK_COMMANDS = (
    ("Deck statistics", "stats"),
    ("Deck options", "options"),
    ("Rename", "rename"),
    ("Export", "export"),
    ("Custom study", "custom"),
    ("Unbury cards", "unbury"),
    ("Rebuild", "rebuild"),
    ("Empty filtered deck", "empty"),
    ("Delete deck", "delete"),
)


def library(tree, selected, closed, today, session):
    section = (
        '<section class="pp-deck-actions" hidden><strong></strong>'
        + "".join(button(label, "deck-" + cmd) for label, cmd in DECK_COMMANDS)
        + "</section>"
    )
    actions = menu(
        "···",
        "Anki actions",
        [
            ("Add notes", "add"),
            ("Browse cards", "browse"),
            ("Create deck", "create"),
            ("Import file", "import"),
            ("Get shared decks", "shared"),
            ("Collection statistics", "stats"),
            ("Sync", "sync"),
        ],
        section,
        group_label="Collection",
    )
    rows = tiles(tree, selected, closed)
    options = "".join(
        f'<button data-months="{n}" aria-pressed="{str(n == 4).lower()}">{n} month{"s" if n > 1 else ""}</button>'
        for n in range(1, 6)
    )
    return f"""
<div id="pp-home" data-selected="{selected}" data-session="{session}" data-day="{today}">
{actions}<main class="home-main"><div class="library-home">
<section class="deck-viewport" aria-label="Deck library" tabindex="0">
<ul class="deck-tiles">{rows}</ul>{"" if rows else '<h2 class="empty-library">Add your first deck</h2>'}</section>
<aside class="deck-activity" aria-label="Collection activity" aria-busy="true">
<figure class="activity-calendar" aria-label="Review activity across all decks">
<div class="calendar-grid"></div><div class="activity-controls">
<span class="study-streak">Streak <strong></strong></span><details class="range-picker">
<summary title="Change activity date range">4 months</summary>
<div class="range-options" role="group" aria-label="Activity date range">{options}</div></details></div>
<figcaption class="day-label"></figcaption></figure>
<div class="pp-activity-error" role="status" hidden>Could not load collection activity. {button("Retry", "retry")}</div>
</aside></div></main></div>"""
