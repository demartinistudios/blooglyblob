'use strict';
const assert = require('assert/strict');

module.exports = async function checkHeroMotion(browser, base) {
  const page = await browser.newPage({reducedMotion: 'reduce'});
  try {
    let releaseFailure;
    const failureReleased = new Promise(resolve => { releaseFailure = resolve; });
    await page.route('**/assets/hero/body-mask.png', async route => {
      await failureReleased;
      await route.abort();
    });
    await page.goto(base + '#start');
    const button = page.locator('[data-hero-pause]');
    await button.focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('[data-hero-pause]').textContent.includes('loading'));
    assert.ok(await button.isVisible(), 'loading keeps the control visible');
    assert.ok(await button.evaluate(el => document.activeElement === el), 'loading retains keyboard focus');
    releaseFailure();
    await page.waitForFunction(() => document.querySelector('[data-hero-pause]').textContent === 'Retry animation');
    assert.ok(await button.isVisible(), 'failed explicit play offers a visible retry');
    assert.ok(await button.evaluate(el => document.activeElement === el), 'failure retains keyboard focus');
    assert.equal(await page.locator('.hero-motion-ready').count(), 0, 'failure leaves the still visible');
    await page.unroute('**/assets/hero/body-mask.png');
    await page.keyboard.press('Enter');
    await page.locator('.hero-motion-ready').waitFor();
    assert.equal(await button.textContent(), 'Pause animation', 'retry starts the animation');
    assert.ok(await button.evaluate(el => document.activeElement === el), 'retry retains keyboard focus');
  } finally {
    await page.close();
  }

  const timing = await browser.newPage();
  try {
    await timing.goto(base + '#parts');
    await timing.evaluate(() => {
      Math.random = () => .5;
      let nextId = 0;
      const callbacks = new Map();
      window.requestAnimationFrame = callback => {
        callbacks.set(++nextId, callback);
        return nextId;
      };
      window.cancelAnimationFrame = id => callbacks.delete(id);
      window.heroTick = now => {
        const pending = [...callbacks.values()];
        callbacks.clear();
        for (const callback of pending) callback(now);
      };
      window.heroPendingFrames = () => callbacks.size;
      window.IntersectionObserver = class {
        constructor(callback) { window.heroIntersect = callback; }
        observe() {}
        disconnect() {}
      };
      window.heroMouthFrames = [];
      const putImageData = CanvasRenderingContext2D.prototype.putImageData;
      CanvasRenderingContext2D.prototype.putImageData = function (image, ...args) {
        if (image.width === 220 && image.height === 1) {
          window.heroMouthFrames.push(Array.from({length: 8}, (_, i) => {
            const x = Math.round(22 + (i + .5) * 171 / 8);
            return Array.from(image.data.slice(x * 4, x * 4 + 3));
          }));
        }
        return putImageData.call(this, image, ...args);
      };
      window.heroPaints = 0;
      window.heroAlphas = [];
      window.heroScreenAlphas = [];
      const clearRect = CanvasRenderingContext2D.prototype.clearRect;
      CanvasRenderingContext2D.prototype.clearRect = function (...args) {
        if (this.canvas.className === 'hero-motion') window.heroPaints++;
        return clearRect.apply(this, args);
      };
      const alpha = Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, 'globalAlpha');
      Object.defineProperty(CanvasRenderingContext2D.prototype, 'globalAlpha', {
        ...alpha,
        set(value) {
          window.heroAlphas.push(value);
          if (this.canvas.className === 'hero-motion') window.heroScreenAlphas.push(value);
          alpha.set.call(this, value);
        }
      });
      const figure = document.createElement('figure');
      figure.innerHTML = '<button data-zoom></button><button data-hero-pause></button>';
      document.body.append(figure);
      window.heroDispose = window.BGBHero.mount(figure);
      window.heroIntersect([{isIntersecting: true}]);
    });
    await timing.waitForFunction(() => document.querySelector('figure.hero-motion-ready'), null, {polling: 50});
    for (const refreshRate of [60, 120]) {
      const paints = await timing.evaluate(refreshRate => {
        window.heroIntersect([{isIntersecting: false}]);
        window.heroIntersect([{isIntersecting: true}]);
        const start = window.heroPaints;
        window.heroTick(0);
        for (let tick = 1; tick <= refreshRate * 2; tick++) window.heroTick(tick * 1000 / refreshRate);
        return window.heroPaints - start;
      }, refreshRate);
      assert.ok(paints >= 59 && paints <= 60, `30 fps at ${refreshRate} Hz: got ${paints} frames in two seconds`);
    }
    const mouths = await timing.evaluate(() => window.heroMouthFrames);
    const lit = frame => frame.filter(rgb => rgb.some(channel => channel > 0)).length;
    assert.equal(lit(mouths[0]), 0, 'the mouth starts dark without speech');
    assert.ok(mouths.some(frame => lit(frame) === 8), 'loud syllables reach all eight LEDs');
    assert.ok(mouths.some(frame => lit(frame) === 2), 'quiet syllables light only the center pair');
    const firstSpeech = mouths.findIndex(frame => lit(frame) > 0);
    assert.ok(firstSpeech >= 0 && mouths.slice(firstSpeech + 1).some(frame => lit(frame) === 0),
      'pauses extinguish the mouth after speech');
    for (const frame of mouths) {
      assert.deepEqual(frame, [...frame].reverse(), 'speech LEDs are mirrored, never a left-to-right meter');
      assert.ok(Math.max(...frame[0]) <= 64, 'end LEDs retain the runtime brightness cap');
      for (let i = 0; i < 3; i++) {
        if (frame[i].some(channel => channel > 0)) {
          const fullInner = [[146, 111, 170], [173, 123, 148], [185, 140, 106]][i];
          // Python and JavaScript round half values differently by one channel step.
          assert.ok(frame[i + 1].every((channel, c) => Math.abs(channel - fullInner[c]) <= 1),
            'inner pair fills before the next outer pair, using the runtime speech palette');
        }
      }
    }
    assert.ok(mouths.some(frame => frame[0].join(',') === '48,42,64'),
      'outer pair uses the runtime lavender color at its cap');
    const visibility = await timing.evaluate(() => {
      for (let tick = 241; tick <= 360; tick++) window.heroTick(tick * 1000 / 120);
      const blinkFades = window.heroScreenAlphas.some(alpha => alpha > 0 && alpha < 1 && alpha !== .3);
      window.heroIntersect([{isIntersecting: true}, {isIntersecting: false}]);
      const stopped = window.heroPendingFrames();
      window.heroIntersect([{isIntersecting: false}, {isIntersecting: true}]);
      const resumed = window.heroPendingFrames();
      window.heroDispose();
      return {stopped, resumed, blinkFades, disposed: window.heroPendingFrames(), validAlpha: window.heroAlphas.every(a => a >= 0 && a <= 1)};
    });
    assert.deepEqual(visibility, {stopped: 0, resumed: 1, blinkFades: true, disposed: 0, validAlpha: true},
      'latest intersection in each batch controls scheduling; all glow alpha assignments are valid');
  } finally {
    await timing.close();
  }
};

if (require.main === module) {
  (async () => {
    const {chromium} = require('playwright');
    const browser = await chromium.launch({headless: true,
      ...(process.env.BGB_CHROME ? {executablePath: process.env.BGB_CHROME} : {})});
    try {
      await module.exports(browser, process.env.BGB_REVIEW_URL);
      console.log('PASS hero loading focus, retry, frame cadence, visibility batches and glow alpha');
    } finally {
      await browser.close();
    }
  })().catch(error => { console.error(error); process.exitCode = 1; });
}
