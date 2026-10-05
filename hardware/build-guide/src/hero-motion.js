/* Decorative homepage lighting, derived from the native Fusion presentation image.
 * No microphone, audio, device connection or external service is used.
 */
window.BGBHero = (() => {
  const assetPaths = [
    'assets/hero/base.png',
    'assets/hero/mouth-mask.png',
    'assets/hero/body-mask.png',
    'assets/hero/eyes-mask.png',
    'assets/hero/body-shade.png'
  ];
  const regions = {
    mouth: {x: 545, y: 500, width: 220, height: 78},
    body: {x: 525, y: 565, width: 345, height: 475},
    eyes: {x: 550, y: 425, width: 210, height: 93}
  };
  // Preserve an explicit pause choice when navigating away and back.
  let userPaused = null;

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Could not load hero lighting asset'));
      image.src = src;
    });
  }

  function renderer(canvas, loaded) {
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas is unavailable');
    const [base, ...images] = loaded;
    const patches = {};
    ['mouth', 'body', 'eyes'].forEach((name, i) => {
      const region = regions[name], c = document.createElement('canvas');
      c.width = region.width;
      c.height = region.height;
      const blur = {mouth: 5.6, body: 16, eyes: 9.2}[name];
      const margin = Math.ceil(blur * 3);
      const glow = Array.from({length: 2}, () => {
        const buffer = document.createElement('canvas');
        buffer.width = region.width + margin * 2;
        buffer.height = region.height + margin * 2;
        return {canvas: buffer, ctx: buffer.getContext('2d')};
      });
      patches[name] = {...region, c, ctx: c.getContext('2d'), mask: images[i], blur, margin, glow};
    });
    const palette = [
      [255, 91, 69], [255, 163, 65], [255, 226, 95], [102, 242, 143],
      [89, 228, 244], [112, 171, 255], [157, 130, 255], [237, 130, 243]
    ];
    // Cache the eight feathered color zones. Only their brightness changes.
    const mouthColors = Array.from({length: regions.mouth.width}, (_, x) => {
      const zone = Math.max(0, Math.min(7.999, (x - 22) / 171 * 8));
      const boundary = Math.round(zone), distance = zone - boundary;
      if (boundary > 0 && boundary < 8 && Math.abs(distance) < .25) {
        let blend = (distance + .25) / .5;
        blend = blend * blend * (3 - 2 * blend);
        return palette[boundary - 1].map((v, c) => v * (1 - blend) + palette[boundary][c] * blend);
      }
      return palette[Math.floor(zone)];
    });
    const mouthStrip = document.createElement('canvas');
    mouthStrip.width = regions.mouth.width;
    mouthStrip.height = 1;
    const mouthContext = mouthStrip.getContext('2d');
    const mouthPixels = mouthContext.createImageData(mouthStrip.width, 1);
    const mouthNotes = [];
    let lastMouthNote = -1;
    let nextBlink = 2.8 + Math.random() * 2.5, blinkStart = -99;
    let doubleAt = -99, blinkLength = .24;

    // A separable Gaussian also works in browsers without canvas filter support.
    const taps = Array.from({length: 9}, (_, i) => ({offset: (i - 4) * .75,
      weight: Math.exp(-.5 * ((i - 4) * .75) ** 2)}));
    const totalWeight = taps.reduce((total, tap) => total + tap.weight, 0);
    for (const tap of taps) tap.weight /= totalWeight;

    function composite(name, strength = 1) {
      const p = patches[name], g = p.ctx;
      g.globalCompositeOperation = 'destination-in';
      g.drawImage(p.mask, 0, 0);
      g.globalCompositeOperation = 'source-over';
      for (let axis = 0; axis < 2; axis++) {
        const {canvas: buffer, ctx: glowContext} = p.glow[axis];
        glowContext.clearRect(0, 0, buffer.width, buffer.height);
        glowContext.globalCompositeOperation = 'lighter';
        for (const {offset, weight} of taps) {
          glowContext.globalAlpha = weight;
          const shift = offset * p.blur;
          if (axis === 0) glowContext.drawImage(p.c, p.margin + shift, p.margin);
          else glowContext.drawImage(p.glow[0].canvas, 0, shift);
        }
      }
      ctx.save();
      ctx.globalAlpha = strength;
      ctx.globalCompositeOperation = 'screen';
      ctx.drawImage(p.glow[1].canvas, p.x - p.margin, p.y - p.margin);
      ctx.restore();
      ctx.drawImage(p.c, p.x, p.y);
    }

    function draw(t) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(base, 0, 0);
      // Slow, broad color currents, with barely perceptible breathing.
      let p = patches.body, g = p.ctx;
      g.clearRect(0, 0, p.width, p.height);
      const drift = t * .095, breath = 1.4 * Math.sin(t * .43) + .6 * Math.sin(t * .19);
      g.fillStyle = `hsl(${185 + 25 * Math.sin(drift)},68%,${74 + breath}%)`;
      g.fillRect(0, 0, p.width, p.height);
      const pools = [
        [.08, .15, 165], [.88, .2, 242], [.12, .53, 202],
        [.85, .55, 284], [.18, .94, 151], [.91, .94, 316]
      ];
      pools.forEach(([x, y, hue], i) => {
        const cx = p.width * (x + .27 * Math.sin(drift + i * 1.4));
        const cy = p.height * (y + .2 * Math.sin(drift * .73 + i * 1.8));
        const rad = g.createRadialGradient(cx, cy, 0, cx, cy, p.width * .96);
        const h = hue + 36 * Math.sin(drift * .9 + i * .8);
        const light = 72 + breath + 2 * Math.sin(drift + i);
        rad.addColorStop(0, `hsla(${h},84%,${light}%,.87)`);
        rad.addColorStop(.42, `hsla(${h},80%,${light}%,.53)`);
        rad.addColorStop(1, `hsla(${h},80%,${light}%,0)`);
        g.fillStyle = rad;
        g.fillRect(0, 0, p.width, p.height);
      });
      g.globalCompositeOperation = 'multiply';
      g.drawImage(images[3], 0, 0);
      g.globalCompositeOperation = 'source-over';
      composite('body', .3);

      // One horizontal amplitude meter: lit zones form a contiguous run from the left.
      p = patches.mouth;
      g = p.ctx;
      g.clearRect(0, 0, p.width, p.height);
      // Choose each pulse height once, so it varies without flickering between frames.
      while (lastMouthNote < Math.floor(t / .62)) {
        const note = ++lastMouthNote;
        mouthNotes.push({
          start: note * .62 + .025 * Math.sin(note * 2.13),
          loudness: .3 + .65 * Math.pow(Math.random(), 1.2)
        });
        if (mouthNotes.length > 9) mouthNotes.shift();
      }
      let amplitude = 0;
      for (const {start, loudness} of mouthNotes) {
        const age = t - start;
        if (age < 0) continue;
        const envelope = (1 - Math.exp(-age / .12)) * Math.exp(-age / .85);
        amplitude = Math.max(amplitude, loudness * envelope);
      }
      const level = Math.min(.99, .1 + amplitude);
      const edge = 22 + 171 * level;
      for (let x = 0; x < p.width; x++) {
        const fill = 1 / (1 + Math.exp((x - edge) / 7.5));
        const brightness = .48 + .52 * fill;
        for (let channel = 0; channel < 3; channel++) {
          mouthPixels.data[x * 4 + channel] = Math.round(mouthColors[x][channel] * brightness);
        }
        mouthPixels.data[x * 4 + 3] = 255;
      }
      mouthContext.putImageData(mouthPixels, 0, 0);
      g.drawImage(mouthStrip, 0, 0, p.width, p.height);
      composite('mouth', 1);

      // Fast close, tiny closed hold, softer opening; occasional restrained double blink.
      if (t >= nextBlink) {
        blinkStart = t;
        blinkLength = .225 + Math.random() * .065;
        nextBlink = t + 3.4 + Math.random() * 5.2;
        doubleAt = Math.random() < .1 ? t + blinkLength + .13 : -99;
      }
      if (doubleAt > 0 && t >= doubleAt) {
        blinkStart = t;
        blinkLength = .21;
        doubleAt = -99;
      }
      const elapsed = t - blinkStart, close = .055, hold = .035;
      const open = blinkLength - close - hold;
      const smooth = x => {
        x = Math.max(0, Math.min(1, x));
        return x * x * (3 - 2 * x);
      };
      let openness = 1;
      if (elapsed >= 0 && elapsed < close) openness = 1 - smooth(elapsed / close);
      else if (elapsed >= close && elapsed < close + hold) openness = 0;
      else if (elapsed >= close + hold && elapsed < blinkLength) {
        openness = smooth((elapsed - close - hold) / open);
      }
      p = patches.eyes;
      g = p.ctx;
      g.clearRect(0, 0, p.width, p.height);
      g.fillStyle = `rgb(${Math.round(94 + 161 * openness)},${Math.round(89 + 149 * openness)},${Math.round(78 + 113 * openness)})`;
      g.fillRect(0, 0, p.width, p.height);
      for (const [x, y, r] of [[38, 43, 20], [161, 50, 27]]) {
        const light = g.createRadialGradient(x, y, 0, x, y, r);
        light.addColorStop(0, `rgba(255,255,241,${.8 * openness})`);
        light.addColorStop(1, 'rgba(255,255,241,0)');
        g.fillStyle = light;
        g.fillRect(0, 0, p.width, p.height);
      }
      composite('eyes', openness);
      ctx.globalCompositeOperation = 'destination-in';
      ctx.drawImage(base, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
    }
    return draw;
  }

  function mount(figure) {
    if (!figure) return () => {};
    const surface = figure.querySelector('[data-zoom]');
    const button = figure.querySelector('[data-hero-pause]');
    const canvas = document.createElement('canvas');
    canvas.width = 1400;
    canvas.height = 1600;
    canvas.className = 'hero-motion';
    canvas.setAttribute('aria-hidden', 'true');
    surface.append(canvas);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const printing = matchMedia('print');
    let paused = reduced.matches || userPaused === true;
    let destroyed = false, failed = false, loading = false, draw = null;
    let inView = false, interacted = false, raf = 0, previous = null, paintElapsed = 0, time = 0;
    const frameInterval = 1000 / 30;

    function updateButton() {
      button.textContent = failed ? 'Retry animation' : paused ? 'Play animation' :
        loading ? 'Pause animation (loading)' : 'Pause animation';
      button.hidden = !interacted && (failed || (!draw && !paused));
    }
    function stop() {
      cancelAnimationFrame(raf);
      raf = 0;
      previous = null;
      paintElapsed = 0;
    }
    function frame(now) {
      raf = 0;
      if (destroyed || paused || !inView || document.hidden || printing.matches) return;
      const elapsed = previous === null ? 0 : Math.min(100, now - previous);
      time += elapsed / 1000;
      paintElapsed += elapsed;
      previous = now;
      if (paintElapsed >= frameInterval) {
        draw(time);
        paintElapsed %= frameInterval;
      }
      raf = requestAnimationFrame(frame);
    }
    function sync() {
      stop();
      if (destroyed || failed || paused || !inView || document.hidden || printing.matches) return;
      if (!draw) {
        if (!loading) {
          loading = true;
          updateButton();
          Promise.all(assetPaths.map(loadImage)).then(loaded => {
            if (destroyed) return;
            draw = renderer(canvas, loaded);
            loading = false;
            updateButton();
            sync();
          }).catch(() => {
            if (destroyed) return;
            failed = true;
            loading = false;
            figure.classList.remove('hero-motion-ready');
            updateButton();
          });
        }
        return;
      }
      draw(time);
      figure.classList.add('hero-motion-ready');
      raf = requestAnimationFrame(frame);
    }
    function toggle() {
      interacted = true;
      paused = failed ? false : !paused;
      failed = false;
      userPaused = paused;
      updateButton();
      sync();
    }
    function preferenceChanged() {
      paused = reduced.matches || userPaused === true;
      if (reduced.matches) figure.classList.remove('hero-motion-ready');
      updateButton();
      sync();
    }
    const observer = new IntersectionObserver(entries => {
      inView = entries[entries.length - 1].isIntersecting;
      sync();
    }, {threshold: .01});
    observer.observe(surface);
    button.addEventListener('click', toggle);
    reduced.addEventListener('change', preferenceChanged);
    printing.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    updateButton();
    return () => {
      destroyed = true;
      stop();
      observer.disconnect();
      button.removeEventListener('click', toggle);
      reduced.removeEventListener('change', preferenceChanged);
      printing.removeEventListener('change', sync);
      document.removeEventListener('visibilitychange', sync);
      canvas.remove();
    };
  }
  return {mount};
})();
