(function () {
  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function initParticles() {
    var canvas = document.getElementById("gaboomParticles");
    if (!canvas) return;
    if (prefersReducedMotion()) return;

    var ctx = canvas.getContext("2d");
    if (!ctx) return;

    var particles = [];
    var raf = null;

    var state = {
      w: 0,
      h: 0,
      dpr: Math.max(1, Math.min(2, window.devicePixelRatio || 1)),
    };

    function density() {
      var dpr = state.dpr;
      return clamp(70 / dpr, 38, 90);
    }

    function resize() {
      var parent = canvas.parentElement;
      if (!parent) return;

      state.w = parent.clientWidth;
      state.h = parent.clientHeight;
      state.dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));

      canvas.width = Math.floor(state.w * state.dpr);
      canvas.height = Math.floor(state.h * state.dpr);
      canvas.style.width = state.w + "px";
      canvas.style.height = state.h + "px";

      ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);

      var targetCount = Math.floor((state.w * state.h) / (12000 + 2800 * (state.dpr - 1)));
      var count = clamp(targetCount, Math.floor(density() * 0.7), density());

      if (particles.length === 0) {
        for (var i = 0; i < count; i++) {
          var hue = Math.random() < 0.6 ? 26 : 212;
          particles.push({
            x: Math.random() * state.w,
            y: Math.random() * state.h,
            vx: (Math.random() - 0.5) * 0.22,
            vy: (Math.random() - 0.5) * 0.18,
            r: 0.8 + Math.random() * 1.8,
            a: 0.16 + Math.random() * 0.24,
            hue: hue,
          });
        }
      } else {
        particles = particles.slice(0, count);
      }
    }

    resize();

    var last = performance.now();

    function tick(t) {
      var dt = Math.min(40, t - last);
      last = t;

      ctx.clearRect(0, 0, state.w, state.h);
      ctx.globalCompositeOperation = "lighter";

      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx * (dt / 16);
        p.y += p.vy * (dt / 16);

        if (p.x < -10) p.x = state.w + 10;
        if (p.x > state.w + 10) p.x = -10;
        if (p.y < -10) p.y = state.h + 10;
        if (p.y > state.h + 10) p.y = -10;

        var grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 18);
        var c1 = "hsla(" + p.hue + ", 100%, 62%, " + p.a + ")";
        var c2 = "hsla(" + p.hue + ", 100%, 62%, 0)";
        grd.addColorStop(0, c1);
        grd.addColorStop(1, c2);

        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 18, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);

    window.addEventListener("resize", resize);

    window.addEventListener("beforeunload", function () {
      if (raf) cancelAnimationFrame(raf);
      raf = null;
      particles = [];
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initParticles);
  } else {
    initParticles();
  }
})();
