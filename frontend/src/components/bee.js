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

  if (!["float", "fly", "follow"].includes(movement)) {
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

  let frame = 0;
  let flapFrameRequest;
  let followFrameRequest;
  let lastFrameTime = 0;
  let destroyed = false;

  const preloadedFrames = beeFrames.map((src) => {
    const image = new Image();
    image.src = src;
    return image.decode();
  });

  Promise.all(preloadedFrames)
    .then(() => {
      const flap = (timestamp) => {
        if (destroyed) return;
        if (timestamp - lastFrameTime >= 60) {
          frame = (frame + 1) % beeFrames.length;
          bee.src = beeFrames[frame];
          lastFrameTime = timestamp;
        }
        flapFrameRequest = window.requestAnimationFrame(flap);
      };

      flapFrameRequest = window.requestAnimationFrame(flap);
    })
    .catch((error) => {
      console.error("Failed to load bee animation frames.", error);
    });

  let animation = null;
  let stopFollowing = () => {};

  if (movement === "follow") {
    const bounds = container.getBoundingClientRect();
    let x = bee.offsetLeft;
    let y = bee.offsetTop;
    const startX = bounds.width * 0.08;
    const startY = bounds.height * 0.15;
    let targetX = x;
    let targetY = y;
    const cursorOffsetX = 36;
    const cursorOffsetY = 30;

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const onPointerMove = (event) => {
      if (event.pointerType === "touch") return;
      const rect = container.getBoundingClientRect();
      targetX = clamp(event.clientX - rect.left - bee.offsetWidth / 2 - cursorOffsetX, 0, rect.width - bee.offsetWidth);
      targetY = clamp(event.clientY - rect.top - bee.offsetHeight / 2 - cursorOffsetY, 0, rect.height - bee.offsetHeight);
    };
    const onPointerLeave = () => {
      targetX = startX;
      targetY = startY;
    };
    const follow = () => {
      if (destroyed) return;
      const previousX = x;
      x += (targetX - x) * 0.007;
      y += (targetY - y) * 0.007;
      const horizontalMovement = x - previousX;
      if (Math.abs(horizontalMovement) > 0.05) {
        bee.style.transform = `scaleX(${horizontalMovement < 0 ? -1 : 1})`;
      }
      bee.style.left = `${x}px`;
      bee.style.top = `${y}px`;
      followFrameRequest = window.requestAnimationFrame(follow);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerleave", onPointerLeave);
    followFrameRequest = window.requestAnimationFrame(follow);
    stopFollowing = () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
    };
  } else {
    const keyframes = movement === "float"
      ? [
        { transform: "translateY(-12px) rotate(-3deg)" },
        { transform: "translateY(12px) rotate(3deg)" }
      ]
      : [
        { transform: "translate(0, 0) rotate(-4deg)" },
        { transform: "translate(300px, -60px) rotate(7deg)" }
      ];

    animation = bee.animate(keyframes, {
        duration,
        easing: "ease-in-out",
        direction: "alternate",
        iterations: Infinity
      });
  }

  return {
    bee,
    destroy() {
      destroyed = true;
      if (flapFrameRequest !== undefined) window.cancelAnimationFrame(flapFrameRequest);
      if (followFrameRequest !== undefined) window.cancelAnimationFrame(followFrameRequest);
      stopFollowing();
      animation?.cancel();
      bee.remove();
    }
  };
}