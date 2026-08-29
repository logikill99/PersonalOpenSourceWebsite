# jQuery → Alpine.js Migration Inventory
**Repo:** PersonalOpenSourceWebsite
**Date:** 2026-08-06
**Author:** Wren (kanban task t_ef37ad83)

---

## Executive Summary

jQuery usage is **extremely limited**: a single 13-line file (`home/static/expand.js`) plus the jQuery 3.7.1 CDN script tag in two templates. There are **no AJAX calls, no complex DOM manipulation, no event delegation beyond simple click handlers**. The entire jQuery footprint can be replaced with a single Alpine.js `x-data` component.

---

## Current jQuery Artifacts

### 1. CDN Inclusion (2 templates)

| Template | Lines | Purpose |
|----------|-------|---------|
| `templates/index.html` | 13–14 | Loads jQuery 3.7.1 from CDN |
| `templates/about.html` | 5–6 | Loads jQuery 3.7.1 from CDN |

Both also load `{% static 'expand.js' %}` immediately after.

### 2. Static JS File (1 file)

**`home/static/expand.js`** — 13 lines, full content below:

```javascript
$(document).ready(function () {
    $('.info').hide();
    $('.skill-button').click(function () {
        let contentwidth = $(this).find(".info").width();
        $('.info').not($(this).find('.info')).hide({queue: true, duration: 100}, "linear")
            .parent('.experience-skills');
        $(this).find('.info').toggle(
            {queue: true, duration: 100}, "linear");
    });
});
```

#### What it does:
1. On DOM ready, hides **all** elements with class `.info`
2. Attaches a click handler to every `.skill-button`
3. On click:
   - Hides all `.info` elements **except** the one inside the clicked button (with a 100ms linear animation)
   - Toggles the visibility of the `.info` inside the clicked button (100ms linear)

#### DOM structure it operates on:
```html
<div class="skill-button">
    <a class="btn btn-default skills-list-item show-info">
        {{ skill.name }}
        <div class="info">{{ skill.description }}</div>
    </a>
</div>
```

#### CSS context:
- `.skill-button` is a flex-styled pill/button (`style.css:400`)
- `.info` has only `margin: 10px` (`style.css:430`) — visibility is controlled entirely by JS, not CSS
- `.skill-button > a > div` (which matches `.info`) has `font-size: 0.8em`

---

## Template-by-Template Breakdown

### `templates/base.html`
- **jQuery usage:** None
- **Notes:** No script tags, no jQuery dependency. Pure layout template.
- **Migration action:** None.

### `templates/index.html`
- **jQuery usage:** CDN script tag (lines 13–14) + `expand.js` (line 15)
- **Dynamic elements:**
  - `{% for skill in highlighted_skills %}` loop renders `.skill-button` / `.info` pairs (lines 44–51)
  - Each `.info` contains `{{ skill.description }}`
- **Behavior:** Click-to-toggle skill descriptions in the "I specialize in" section
- **Migration action:** Replace jQuery CDN + `expand.js` with Alpine `x-data` on the skills container

### `templates/about.html`
- **jQuery usage:** CDN script tag (lines 5–6) + `expand.js` (line 7)
- **Dynamic elements:** Same `.skill-button` / `.info` pattern, repeated in **four** loops:
  1. `{% for skill in experience.skills.all %}` inside Work Experience (lines 46–53)
  2. `{% for skill in experience.skills.all %}` inside Education (lines 67–74)
  3. `{% for skill in experience.skills.all %}` inside Personal/Achievements (lines 86–93)
  4. `{% for skill in languages %}` / `frameworks` / `other_skills` / `hobbies` (lines 100–148)
- **Behavior:** Same click-to-toggle as index.html
- **Migration action:** Same Alpine component as index.html; single `x-data` can wrap all instances or use multiple independent `x-data` attributes

### `templates/about_me.html`
- **jQuery usage:** None (extends `index.html` but overrides an empty block)
- **Migration action:** None.

### `templates/blog_index.html`
- **jQuery usage:** None
- **Migration action:** None.

### `templates/contact.html`
- **jQuery usage:** None
- **Migration action:** None.

### `templates/contact_success.html`
- **jQuery usage:** None
- **Migration action:** None.

### `templates/logos.html`
- **jQuery usage:** None (empty placeholder template)
- **Migration action:** None.

### `templates/post_detail.html`
- **jQuery usage:** None
- **Migration action:** None.

---

## Proposed Alpine.js Replacement

### Component Design

```html
<!-- Replace the jQuery CDN + expand.js script tags with Alpine.js CDN -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

### Pattern A: Independent toggles (closest to current behavior)

Current jQuery hides all other `.info` elements when one is clicked. If you want to preserve that "accordion" behavior:

```html
<div class="skills-list" x-data="{ open: null }">
    {% for skill in highlighted_skills %}
        <div class="skill-button">
            <a class="btn btn-default skills-list-item show-info"
               @click="open === {{ loop.index }} ? open = null : open = {{ loop.index }}">
                {{ skill.name }}
                <div class="info" x-show="open === {{ loop.index }}" x-transition>
                    {{ skill.description }}
                </div>
            </a>
        </div>
    {% endfor %}
</div>
```

### Pattern B: Independent toggles (simpler, recommended)

If you don't need the "close others when one opens" behavior, each button is self-contained:

```html
<div class="skill-button" x-data="{ show: false }">
    <a class="btn btn-default skills-list-item show-info"
       @click="show = !show">
        {{ skill.name }}
        <div class="info" x-show="show" x-transition>
            {{ skill.description }}
        </div>
    </a>
</div>
```

**Recommendation:** Pattern B is cleaner and the UX is fine — the current "close others" logic is barely noticeable with 4+ skill categories on the about page. But Pattern A is a 1:1 behavioral match if you want it.

### CSS Addition

Add one rule to `style.css` so `.info` starts hidden before Alpine loads (avoids flash of unhidden content):

```css
[x-cloak] { display: none !important; }
```

And add `x-cloak` to the `.info` divs:

```html
<div class="info" x-show="show" x-cloak x-transition>
```

---

## Files to Change

| File | Change |
|------|--------|
| `templates/index.html` | Remove jQuery CDN + `expand.js` script tags; add Alpine CDN; add `x-data` to skills container |
| `templates/about.html` | Same as above |
| `home/static/expand.js` | **Delete** |
| `home/static/style.css` | Add `[x-cloak]` rule |

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Flash of unstyled content | Low | `x-cloak` + CSS rule |
| Animation jank | Low | Alpine `x-transition` handles enter/leave; 100ms jQuery toggle is barely perceptible anyway |
| Behavior change (accordion vs independent) | Low | Pattern A preserves exact behavior; Pattern B is arguably better UX |
| CDN availability | Low | Same risk profile as current jQuery CDN |

---

## Verdict

**Trivial migration.** One file, two templates, one behavior. This is a 30-minute swap, not a project.
