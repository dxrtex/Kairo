/* Kairo – Brand Reveal „Der Moment“ (≈ 1,9 s, nur beim ersten Öffnen und nach einem Update; sonst 0,5 s Logo).
   Idee: Eine ruhige Kurslinie fällt und wendet. Ein Fadenkreuz rastet am Tief ein – der richtige Moment. Aus dem Punkt wächst
   die blaue Kerze, die Kerze ist der Stamm des K, die Klingen schließen das Zeichen, KAIRO und der Claim erscheinen.
   0,00 s  Linie zeichnet sich von links (die Szene ist vergrößert)
   0,42 s  Punkt am Tief, Fadenkreuz rastet ein (von groß auf präzise)
   0,66 s  Zoom ins Zeichen, Linie tritt zurück; aus dem Punkt wächst der Docht, 0,78 s der Körper
   0,94 s  Klingen des K gleiten heran, 1,00 s Kachel
   1,18 s  Zeichen rückt nach links, KAIRO wird Buchstabe für Buchstabe sichtbar
   1,50 s  Claim „Patience, then precision.“
   Übergang ab ≈ 1,9 s (frühestens, wenn die App bereit ist): Logo zoomt sanft weg, die App blendet ein.
   Antippen, Klick oder Taste überspringt. „Bewegung reduzieren“: fertiges Logo, sanft ausgeblendet.
   Technik: nur transform/opacity (Grafikkarte), SVG + CSS, kein Video, keine Bibliothek. */
(function () {
  const L = {"K": "M257.3 420.6V340.7H279.51V377.75L316.83 340.7H344.57L311.56 373.48L345.27 420.6H318.35L295.67 387.68L279.51 401.58V420.6Z", "R": "M502.3 420.6V340.7H558.36Q567.18 340.7 573 344.15Q578.82 347.61 581.74 353.39Q584.66 359.17 584.66 366.2Q584.66 373.86 581.09 379.96Q577.51 386.06 570.7 389.53L586.9 420.6H562.01L548.72 393.21H524.51V420.6ZM524.51 376.78H552.57Q556.85 376.78 559.41 374.08Q561.98 371.37 561.98 366.81Q561.98 363.83 560.83 361.72Q559.68 359.62 557.59 358.48Q555.49 357.34 552.57 357.34H524.51Z", "O": "M642.2 422Q627.68 422 617.14 417.26Q606.61 412.52 600.95 403.29Q595.3 394.06 595.3 380.66Q595.3 367.15 600.95 357.95Q606.61 348.75 617.14 344.02Q627.68 339.3 642.2 339.3Q656.88 339.3 667.37 344.02Q677.87 348.75 683.52 357.95Q689.18 367.15 689.18 380.66Q689.18 394.06 683.52 403.29Q677.87 412.52 667.37 417.26Q656.88 422 642.2 422ZM642.22 405.12Q647.85 405.12 652.32 403.59Q656.79 402.07 659.94 399.16Q663.09 396.26 664.75 392.07Q666.4 387.88 666.4 382.63V378.61Q666.4 373.35 664.75 369.17Q663.09 364.99 659.94 362.1Q656.79 359.21 652.32 357.69Q647.85 356.18 642.22 356.18Q636.6 356.18 632.13 357.69Q627.66 359.21 624.52 362.1Q621.38 364.99 619.76 369.17Q618.13 373.35 618.13 378.61V382.63Q618.13 387.88 619.76 392.07Q621.38 396.26 624.52 399.16Q627.66 402.07 632.13 403.59Q636.6 405.12 642.22 405.12Z", "A": "M341.11 420.6 375.59 340.7H401.19L435.7 420.6H411.83L406.46 407.24H369.28L363.94 420.6ZM375.73 390.82H400.02L393.53 374.28Q393.07 373.08 392.36 371.14Q391.65 369.2 390.9 366.97Q390.15 364.75 389.46 362.68Q388.77 360.61 388.32 359.29H387.51Q386.8 361.46 385.81 364.26Q384.83 367.06 383.89 369.75Q382.94 372.44 382.21 374.3Z"};
  const LOGO = `
    <div class="sp-bg"></div>
    <div class="sp-line"></div>
    <div class="sp-stage">
      <div class="sp-lock">
        <div class="sp-mark">
          <div class="sp-tile"></div>
          <div class="sp-scene"><svg class="sp-curve" viewBox="0 0 600 170" aria-hidden="true"><defs><linearGradient id="spC" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#8a93a3" stop-opacity="0"/><stop offset=".25" stop-color="#8a93a3" stop-opacity=".55"/><stop offset=".5" stop-color="#c9d0db"/><stop offset=".75" stop-color="#8a93a3" stop-opacity=".55"/><stop offset="1" stop-color="#8a93a3" stop-opacity="0"/></linearGradient></defs><path d="M0 18 C 120 24, 205 150, 300 150 C 395 150, 470 46, 600 8" fill="none" stroke="url(#spC)" stroke-width="2.2" stroke-linecap="round" pathLength="1"/></svg>
            <i class="sp-x sp-xh"></i><i class="sp-x sp-xv"></i><i class="sp-dot"></i></div>
          <!-- Jede Ebene eigenes Element: nur transform/opacity → läuft auf der Grafikkarte (flüssig, auch während die App lädt) -->
          <div class="sp-lay sp-glow"></div>
          <svg class="sp-lay sp-wick" viewBox="0 0 1000 1000" aria-hidden="true"><defs><linearGradient id="spW" x1="0" y1="159" x2="0" y2="833" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#3D9BFF"/><stop offset="1" stop-color="#0A6FFF"/></linearGradient></defs><rect x="301.5" y="159" width="30" height="674" rx="15" fill="url(#spW)"/></svg>
          <svg class="sp-lay sp-body" viewBox="0 0 1000 1000" aria-hidden="true"><defs><linearGradient id="spB" x1="0" y1="296" x2="0" y2="672" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#4AA3FF"/><stop offset="1" stop-color="#0A6FFF"/></linearGradient></defs><rect x="240" y="296" width="150" height="376" rx="20" fill="url(#spB)"/></svg>
          <svg class="sp-lay sp-arm sp-up" viewBox="0 0 1000 1000" aria-hidden="true"><defs><linearGradient id="spS" x1="413" y1="222" x2="819" y2="819" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".55" stop-color="#E3E6EB"/><stop offset="1" stop-color="#B4BAC3"/></linearGradient></defs><path d="M413 433L627 222H816L413 590Z" fill="url(#spS)"/></svg>
          <svg class="sp-lay sp-arm sp-lo" viewBox="0 0 1000 1000" aria-hidden="true"><path d="M441 620L567 505L819 819H607Z" fill="url(#spS)"/></svg>
          <div class="sp-shine"></div>
        </div>
        <div class="sp-word">
          <svg class="sp-lay sp-l sp-l1" viewBox="255 327 436 110" aria-hidden="true"><path d="${L.K}"/></svg>
          <svg class="sp-lay sp-l sp-l2" viewBox="255 327 436 110" aria-hidden="true"><path d="${L.A}"/></svg>
          <svg class="sp-lay sp-wc" viewBox="255 327 436 110" aria-hidden="true"><rect x="462.35" y="329.3" width="4.7" height="105.7" rx="2.35"/><rect x="451.6" y="352" width="25.8" height="60.3" rx="3.5"/></svg>
          <svg class="sp-lay sp-l sp-l3" viewBox="255 327 436 110" aria-hidden="true"><path d="${L.R}"/></svg>
          <svg class="sp-lay sp-l sp-l4" viewBox="255 327 436 110" aria-hidden="true"><path d="${L.O}"/></svg>
        </div>
      </div>
      <div class="sp-tag">Patience, then precision.</div>
      <div class="sp-load"><i></i></div>
    </div>`;
  const ANIM_MS = 1900, SHORT_MS = 520, EXIT_MS = 520, TIMEOUT_MS = 5000;
  const INTRO_V = "10";                                   // neue Version → beim nächsten Öffnen wieder das volle Intro
  const mark = () => { try { localStorage.setItem("kairo-intro", INTRO_V); } catch (e) {} };
  const seen = () => { try { return localStorage.getItem("kairo-intro") === INTRO_V; } catch (e) { return false; } };
  let current = null;
  // Nach dem Intro: Start-Schwarz entfernen, damit helle Designs ihre eigene Hintergrundfarbe zeigen
  const unboot = () => { const b = document.getElementById("preboot"); if (b) b.remove(); document.documentElement.style.background = ""; };

  function play(opts = {}) {
    if (current) current.el.remove();
    const el = document.createElement("div");
    el.className = "splash"; el.setAttribute("role", "img"); el.setAttribute("aria-label", "Kairo – Patience, then precision."); el.innerHTML = LOGO;
    const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) el.classList.add("reduce");
    // Volles Intro beim ersten Öffnen und nach einem Update (neue INTRO_V); sonst nur kurz das Logo – keine Wartezeit bei jedem Start
    const short = !reduce && (opts.full === false || (opts.full !== true && seen()));
    if (short) el.classList.add("short");
    mark();
    let doneRes; const animDone = new Promise(r => { doneRes = r; });
    const useVideo = !reduce && !short && opts.video === true;          // altes Video-Intro nur noch auf Wunsch (Vorschau)
    if (useVideo) {                                                    // Video-Intro; bei Problemen die Animation als Ersatz
      el.classList.add("vid"); el.innerHTML = `<div class="sp-bg"></div><div class="sp-load"><i></i></div>`;
      const v = document.createElement("video"), port = innerHeight > innerWidth;
      v.className = "sp-vid"; v.muted = true; v.defaultMuted = true; v.playsInline = true; v.preload = "auto";
      ["muted", "playsinline", "webkit-playsinline", "disablepictureinpicture"].forEach(a => v.setAttribute(a, ""));
      v.src = `intro-${port ? "hoch" : "quer"}.mp4?v=${INTRO_V}`;
      let started = false, fell = false;
      const fallback = () => { if (started || fell) return; fell = true; v.remove(); el.classList.remove("vid"); el.innerHTML = LOGO; setTimeout(doneRes, ANIM_MS); };
      v.addEventListener("playing", () => { if (fell) return; started = true; v.classList.add("on"); }, { once: true });
      v.addEventListener("ended", () => doneRes());
      v.addEventListener("error", fallback);
      el.appendChild(v);
      const pr = v.play(); if (pr && pr.catch) pr.catch(fallback);
      setTimeout(fallback, 1200);                                       // startet nicht rechtzeitig → Animation
    } else setTimeout(doneRes, reduce ? 300 : short ? SHORT_MS : ANIM_MS);
    document.body.appendChild(el);
    const skip = () => { doneRes(); el.classList.add("skip"); };          // Antippen/Taste: sofort weiter, sobald die App bereit ist
    el.addEventListener("pointerdown", skip, { once: true }); const ks = e => { skip(); removeEventListener("keydown", ks); }; addEventListener("keydown", ks);
    let resolveReady;
    const ready = new Promise(r => { resolveReady = r; });
    animDone.then(() => el.classList.add("waiting"));               // App lädt noch → feine Ladelinie
    const handle = { el, ready: resolveReady };
    current = handle;
    if (opts.hold) return handle;                                      // Vorschau: Logo bleibt stehen
    Promise.race([Promise.all([animDone, ready]), new Promise(r => setTimeout(r, TIMEOUT_MS))]).then(() => {
      el.classList.add("exit"); removeEventListener("keydown", ks);
      setTimeout(() => { el.remove(); if (current === handle) current = null; unboot(); opts.onDone && opts.onDone(); }, reduce ? 280 : EXIT_MS);
    });
    if (opts.readyAfter != null) setTimeout(resolveReady, opts.readyAfter);
    return handle;
  }

  window.KairoSplash = { play, ready() { if (current) current.ready(); } };
  if (document.currentScript && document.currentScript.dataset.autoplay !== undefined && !/nosplash/.test(location.search)) play();
})();
