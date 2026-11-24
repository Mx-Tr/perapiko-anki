# Perapiko Kaishi

In desktop Anki, open a Kaishi note in Browse, then choose Cards. Save a copy of the current Front Template, Back Template and Styling. Paste front.html, back.html and styling.css into the corresponding tabs for the reading card. Save and sync on this computer, then sync your other devices. Anki applies these changes to every card using that template.

The template uses the existing Kaishi fields Word, Word Reading, Word Meaning, Word Audio, Sentence, Sentence Furigana, Sentence Meaning, Sentence Audio, Picture, Notes, Pitch Accent and Pitch Accent Notes. Each referenced field must exist. Optional values may be empty. For another note type, adapt the field names first.

Tap the example to reveal the hint. Show Answer reveals the reading and translations. Audio uses the card's Anki playback controls. Aa switches between system, serif and gothic fonts available on the device. To choose your own default, append this to Styling:

```css
.card { --kaishi-font: "Your installed font", system-ui, sans-serif; }
```

Install the chosen font on each device or add a font you can use to Anki media and declare it with @font-face. The template runs independently of the Perapiko desktop add-on. To revert, restore your three saved templates and sync.
