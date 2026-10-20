/* Kairo – Start-Animation „Vom Lärm zum einen Moment“ (≈ 3 s beim ersten Öffnen, danach kurz). Ablauf auf reinem Schwarz:
   0,00 s  graue Kerzen (der Markt) laufen über einer feinen blauen Kurslinie ein
   0,56 s  eine Kerze wird blau und leuchtet auf, die übrigen treten zurück
   0,95 s  an ihrer Stelle wächst die Kerze des Zeichens, 1,15 s der Körper federt auf
   1,45 s  die zwei silbernen Klingen des K gleiten mit Bewegungsunschärfe heran
   1,70 s  die Kachel materialisiert sich dahinter, 1,90 s Lichtreflex über das Zeichen
   1,90 s  das Zeichen rückt nach links, KAIRO wird Buchstabe für Buchstabe scharf
   2,30 s  Claim „Der richtige Moment“
   Übergang: Logo zoomt sanft weg, die App blendet ein. Wartet die App noch, läuft eine feine Ladelinie.
   Startet den Übergang erst, wenn die Animation durch ist UND die App KairoSplash.ready() gemeldet hat – spätestens nach 6 s. */
(function () {
  const L = {"K": "M257.3 420.6V340.7H279.51V377.75L316.83 340.7H344.57L311.56 373.48L345.27 420.6H318.35L295.67 387.68L279.51 401.58V420.6Z", "R": "M502.3 420.6V340.7H558.36Q567.18 340.7 573 344.15Q578.82 347.61 581.74 353.39Q584.66 359.17 584.66 366.2Q584.66 373.86 581.09 379.96Q577.51 386.06 570.7 389.53L586.9 420.6H562.01L548.72 393.21H524.51V420.6ZM524.51 376.78H552.57Q556.85 376.78 559.41 374.08Q561.98 371.37 561.98 366.81Q561.98 363.83 560.83 361.72Q559.68 359.62 557.59 358.48Q555.49 357.34 552.57 357.34H524.51Z", "O": "M642.2 422Q627.68 422 617.14 417.26Q606.61 412.52 600.95 403.29Q595.3 394.06 595.3 380.66Q595.3 367.15 600.95 357.95Q606.61 348.75 617.14 344.02Q627.68 339.3 642.2 339.3Q656.88 339.3 667.37 344.02Q677.87 348.75 683.52 357.95Q689.18 367.15 689.18 380.66Q689.18 394.06 683.52 403.29Q677.87 412.52 667.37 417.26Q656.88 422 642.2 422ZM642.22 405.12Q647.85 405.12 652.32 403.59Q656.79 402.07 659.94 399.16Q663.09 396.26 664.75 392.07Q666.4 387.88 666.4 382.63V378.61Q666.4 373.35 664.75 369.17Q663.09 364.99 659.94 362.1Q656.79 359.21 652.32 357.69Q647.85 356.18 642.22 356.18Q636.6 356.18 632.13 357.69Q627.66 359.21 624.52 362.1Q621.38 364.99 619.76 369.17Q618.13 373.35 618.13 378.61V382.63Q618.13 387.88 619.76 392.07Q621.38 396.26 624.52 399.16Q627.66 402.07 632.13 403.59Q636.6 405.12 642.22 405.12Z", "A": "M341.11 420.6 375.59 340.7H401.19L435.7 420.6H411.83L406.46 407.24H369.28L363.94 420.6ZM375.73 390.82H400.02L393.53 374.28Q393.07 373.08 392.36 371.14Q391.65 369.2 390.9 366.97Q390.15 364.75 389.46 362.68Q388.77 360.61 388.32 359.29H387.51Q386.8 361.46 385.81 364.26Q384.83 367.06 383.89 369.75Q382.94 372.44 382.21 374.3Z"};
  const LOGO = `
    <div class="sp-bg"></div>
    <div class="sp-line"></div>
    <div class="sp-stage">
      <div class="sp-lock">
        <div class="sp-mark">
          <div class="sp-tile"></div>
          <div class="sp-noise"><i style="--x:-6;--h:0.3;--y:0.1;--o:12;--d:6"></i><i style="--x:-5;--h:0.42;--y:0.04;--o:11;--d:5"></i><i style="--x:-4;--h:0.26;--y:0.12;--o:10;--d:4"></i><i style="--x:-3;--h:0.48;--y:-0.02;--o:9;--d:3"></i><i style="--x:-2;--h:0.34;--y:0.06;--o:8;--d:2"></i><i style="--x:-1;--h:0.52;--y:-0.06;--o:7;--d:1"></i><i class="on" style="--x:0;--h:0.376;--y:-0.016;--o:6;--d:0"></i><i style="--x:1;--h:0.4;--y:-0.04;--o:5;--d:1"></i><i style="--x:2;--h:0.28;--y:0.08;--o:4;--d:2"></i><i style="--x:3;--h:0.46;--y:-0.1;--o:3;--d:3"></i><i style="--x:4;--h:0.32;--y:-0.02;--o:2;--d:4"></i><i style="--x:5;--h:0.44;--y:-0.12;--o:1;--d:5"></i><i style="--x:6;--h:0.3;--y:-0.06;--o:0;--d:6"></i></div>
          <svg viewBox="0 0 1000 1000" aria-hidden="true">
            <defs>
              <linearGradient id="spW" x1="0" y1="159" x2="0" y2="833" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#3D9BFF"/><stop offset="1" stop-color="#0A6FFF"/></linearGradient>
              <linearGradient id="spB" x1="0" y1="296" x2="0" y2="672" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#4AA3FF"/><stop offset="1" stop-color="#0A6FFF"/></linearGradient>
              <linearGradient id="spS" x1="413" y1="222" x2="819" y2="819" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".55" stop-color="#E3E6EB"/><stop offset="1" stop-color="#B4BAC3"/></linearGradient>
              <filter id="spF" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="26"/></filter>
            </defs>
            <rect class="sp-glow" x="240" y="296" width="150" height="376" rx="20" fill="#0A84FF" filter="url(#spF)"/>
            <rect class="sp-wick" x="301.5" y="159" width="30" height="674" rx="15" fill="url(#spW)"/>
            <rect class="sp-body" x="240" y="296" width="150" height="376" rx="20" fill="url(#spB)"/>
            <path class="sp-arm sp-up" d="M413 433L627 222H816L413 590Z" fill="url(#spS)"/>
            <path class="sp-arm sp-lo" d="M441 620L567 505L819 819H607Z" fill="url(#spS)"/>
          </svg>
          <div class="sp-shine"></div>
        </div>
        <div class="sp-word">
          <svg viewBox="255 327 436 110" aria-hidden="true">
            <path class="sp-l sp-l1" d="${L.K}"/><path class="sp-l sp-l2" d="${L.A}"/>
            <g class="sp-wc"><rect x="462.35" y="329.3" width="4.7" height="105.7" rx="2.35"/><rect x="451.6" y="352" width="25.8" height="60.3" rx="3.5"/></g>
            <path class="sp-l sp-l3" d="${L.R}"/><path class="sp-l sp-l4" d="${L.O}"/>
          </svg>
        </div>
      </div>
      <div class="sp-tag">Der richtige Moment</div>
      <div class="sp-load"><i></i></div>
    </div>`;
  const ANIM_MS = 3000, SHORT_MS = 850, EXIT_MS = 560, TIMEOUT_MS = 6000;
  const INTRO_V = "4";                                   // neue Version → beim nächsten Öffnen wieder das volle Intro
  const seen = () => { try { return localStorage.getItem("kairo-intro") === INTRO_V; } catch (e) { return false; } };
  const mark = () => { try { localStorage.setItem("kairo-intro", INTRO_V); } catch (e) {} };
  let current = null;
  // Nach dem Intro: Start-Schwarz entfernen, damit helle Designs ihre eigene Hintergrundfarbe zeigen
  const unboot = () => { const b = document.getElementById("preboot"); if (b) b.remove(); document.documentElement.style.background = ""; };

  function play(opts = {}) {
    if (current) current.el.remove();
    const el = document.createElement("div");
    el.className = "splash"; el.setAttribute("aria-hidden", "true"); el.innerHTML = LOGO;
    const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) el.classList.add("reduce");
    const short = !reduce && (opts.full === false || (opts.full !== true && seen()));   // volles Intro nur beim ersten Öffnen / nach Update
    if (short) el.classList.add("short");
    mark();
    document.body.appendChild(el);
    let resolveReady;
    const ready = new Promise(r => { resolveReady = r; });
    const animDone = new Promise(r => setTimeout(r, reduce ? 300 : short ? SHORT_MS : ANIM_MS));
    animDone.then(() => el.classList.add("waiting"));               // App lädt noch → feine Ladelinie
    const handle = { el, ready: resolveReady };
    current = handle;
    Promise.race([Promise.all([animDone, ready]), new Promise(r => setTimeout(r, TIMEOUT_MS))]).then(() => {
      el.classList.add("exit");
      setTimeout(() => { el.remove(); if (current === handle) current = null; unboot(); opts.onDone && opts.onDone(); }, reduce ? 280 : EXIT_MS);
    });
    if (opts.readyAfter != null) setTimeout(resolveReady, opts.readyAfter);
    return handle;
  }

  window.KairoSplash = { play, ready() { if (current) current.ready(); } };
  if (document.currentScript && document.currentScript.dataset.autoplay !== undefined) play();
})();
