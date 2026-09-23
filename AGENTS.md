# Workspace Rules & Development Standards

## 1. Architecture Context
This repository generates a self-contained learning web application (`index.html`), study handbook (`單字與片語學習手冊.md`), and documentation (`README.md`) from vocabulary sources (`g_translate.csv.csv`, `vocab_db.json`) via `update_learning_app.py`.
The web app's HTML and JavaScript (1,400+ lines) are embedded within Python multi-line templates.

---

## 2. Mandatory Rules & Quality Gates

### Rule 1: Automated Verification Gate (No Untested Code)
- **NEVER** commit or push changes without running the automated headless validation test.
- Every modification to `update_learning_app.py` MUST be tested with `python update_learning_app.py` followed by the automated JavaScript DOM and runtime test suite.
- Syntax-only checks (`node --check`) are INSUFFICIENT. The test suite must simulate runtime execution of core user flows:
  - Initial load (`DOMContentLoaded`)
  - Flashcard navigation (`nextCard`, `prevCard`)
  - Card flipping (`flipCard`, `setCardFlipped`)
  - Search filtering & modal actions (`handleGlobalFindInput`, `jumpToCardInFlashcard`)
  - Mastery status tagging (`setMastery`)

### Rule 2: JavaScript Template Safety & Variable Scoping
- In Python multi-line strings, never assume variables from other scopes exist.
- Always explicitly define and clamp state variables before accessing properties (e.g., `const card = filteredCards[currentCardIndex]; if (!card) return;`).
- Avoid raw unescaped newlines in Python f-string JavaScript literals (use `\\n` or `String.fromCharCode(10)`).
- Escape curly braces properly in Python f-strings (`{{` and `}}`).

### Rule 3: Modal & Overlay Display Specificity
- All modal overlays and backdrop dialogs MUST use inline `style="display: none;"` and direct JS style toggles (`el.style.display = 'flex' / 'none'`).
- **NEVER** rely exclusively on utility classes like `hidden` alongside `flex` on the same element, as Tailwind CSS class ordering can cause invisible layers to intercept user clicks.

### Rule 4: Web Speech API & Browser Hardware Resilience
- In Chromium-based browsers, speech synthesis instances (`SpeechSynthesisUtterance`) MUST be pinned to a global reference (`window._gt_active_utterance`) to prevent V8 garbage collection mid-speech.
- Always include an asynchronous watchdog timer (`setTimeout`) to recover from dropped hardware audio events or uninstalled voice packs.
- Never call `speechSynthesis.cancel()` concurrently with `speechSynthesis.speak()` without an event-loop deferral (at least 30-40ms delay).

### Rule 5: Touch & Accessibility Parity
- All clickable cards and navigation controls must support both pointer clicks (`cursor-pointer`, `active:scale-95`), keyboard shortcuts, and mobile touch gestures (swipe left for next, swipe right for previous).
