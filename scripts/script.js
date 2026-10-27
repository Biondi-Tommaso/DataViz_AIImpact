
  const canvas = document.getElementById("network");
  const ctx = canvas.getContext("2d");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let width = 0;
  let height = 0;
  let nodes = [];

  const maxDistance = 155;
  const color = "190, 75, 92";

  const pointer = {
    x: 0,
    y: 0,
    active: false
  };

  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.active = true;
  });

  window.addEventListener("pointerleave", () => {
    pointer.active = false;
  });

  function resizeCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    width = window.innerWidth;
    height = window.innerHeight;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const nodeCount = Math.min(
      340,
      Math.max(120, Math.round((width * height) / 1700))
    );

    nodes = Array.from({ length: nodeCount }, () => {
      const angle = Math.random() * Math.PI * 2;
      const speed = 0.35 + Math.random() * 0.45;
      const baseVx = Math.cos(angle) * speed;
      const baseVy = Math.sin(angle) * speed;

      return {
        x: Math.random() * width,
        y: Math.random() * height,
        baseVx,
        baseVy,
        vx: baseVx,
        vy: baseVy,
        radius: 1.7 + Math.random() * 1.5
      };
    });

    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    for (const node of nodes) {
      if (!reducedMotion.matches) {
        // La velocità di base resta attiva anche dopo il passaggio del mouse.
        // La spinta del puntatore svanisce gradualmente, senza fermare i punti.
        node.vx = node.baseVx + (node.vx - node.baseVx) * 0.97;
        node.vy = node.baseVy + (node.vy - node.baseVy) * 0.97;

        if (pointer.active) {
          const dx = node.x - pointer.x;
          const dy = node.y - pointer.y;
          const distance = Math.hypot(dx, dy);
          const interactionRadius = 135;

          if (distance < interactionRadius && distance > 0) {
            const strength = (1 - distance / interactionRadius) * 0.12;
            node.vx += (dx / distance) * strength;
            node.vy += (dy / distance) * strength;
          }
        }

        const speed = Math.hypot(node.vx, node.vy);
        const maxSpeed = 2.2;

        if (speed > maxSpeed) {
          node.vx = (node.vx / speed) * maxSpeed;
          node.vy = (node.vy / speed) * maxSpeed;
        }

        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 0 || node.x > width) {
          node.vx *= -1;
          node.baseVx *= -1;
        }

        if (node.y < 0 || node.y > height) {
          node.vy *= -1;
          node.baseVy *= -1;
        }

        node.x = Math.max(0, Math.min(width, node.x));
        node.y = Math.max(0, Math.min(height, node.y));
      }
    }

    // Disegna le linee tra i punti vicini
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const distance = Math.hypot(a.x - b.x, a.y - b.y);

        if (distance < maxDistance) {
          const opacity = (1 - distance / maxDistance) * 0.28;

          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = `rgba(${color}, ${opacity})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    // Disegna i punti
    for (const node of nodes) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
      ctx.fill();
      ctx.strokeStyle = `rgba(${color}, 0.48)`;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }

    if (!reducedMotion.matches) {
      requestAnimationFrame(draw);
    }
  }

  window.addEventListener("resize", resizeCanvas);

  if (reducedMotion.addEventListener) {
    reducedMotion.addEventListener("change", resizeCanvas);
  }

  resizeCanvas();
