# HoneyChain Bee

Reusable animated bee component.

Include `bee.css`, then place this markup wherever the bee should appear:

```html
<main class="honeychain-bee" aria-label="Animated bee">
  <span class="honeychain-bee-head">
    <span class="honeychain-bee-antenna"></span>
    <span class="honeychain-bee-antenna"></span>
  </span>
  <span class="honeychain-bee-sting"></span>
  <span class="honeychain-bee-wings"></span>
</main>
```

The component is scoped under `.honeychain-bee`, so its styles do not change the page body or other `main` elements. `bee.html` is a standalone include example.
