const beeFrames = [
  "/src/assets/bee/cbee-1.png",
  "/src/assets/bee/cbee-2.png",
  "/src/assets/bee/cbee-3.png",
  "/src/assets/bee/cbee-4.png"
];

export function createBee({
  container,
  size = 80,
  movement = "float",
  duration = 4000
}) {
  if (!(container instanceof HTMLElement)) {
    throw new TypeError("createBee requires a valid container element");
  }

  if (!["float", "fly"].includes(movement)) {
    throw new TypeError(`Unsupported bee movement: ${movement}`);
  }

  const bee = document.createElement("img");

  bee.className = "bee";
  bee.src = beeFrames[0];
  bee.alt = "";
  bee.draggable = false;

  bee.style.width = `${size}px`;
  bee.style.position = "absolute";
  bee.style.top = "15%";
  bee.style.left = "8%";
  bee.style.display = "block";
  bee.style.pointerEvents = "none";
  bee.style.userSelect = "none";

  container.appendChild(bee);

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let frame = 0;
  let flap;

  if (!reducedMotion.matches) {
    flap = window.setInterval(() => {
      frame = (frame + 1) % beeFrames.length;
      bee.src = beeFrames[frame];
    }, 80);
  }

  const keyframes = movement === "float"
    ? [
        { transform: "translateY(-12px) rotate(-3deg)" },
        { transform: "translateY(12px) rotate(3deg)" }
      ]
    : [
        { transform: "translate(0, 0) rotate(-4deg)" },
        { transform: "translate(300px, -60px) rotate(7deg)" }
      ];

  const animation = reducedMotion.matches
    ? null
    : bee.animate(keyframes, {
        duration,
        easing: "ease-in-out",
        direction: "alternate",
        iterations: Infinity
      });

  return {
    bee,
    destroy() {
      if (flap !== undefined) window.clearInterval(flap);
      animation?.cancel();
      bee.remove();
    }
  };
}