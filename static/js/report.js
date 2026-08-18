(() => {
  const analysis = window.__ANALYSIS__;
  const root = getComputedStyle(document.documentElement);
  const c = (name) => root.getPropertyValue(name).trim();

  const palette = {
    accent: c("--accent") || "#6d8cff",
    accent2: c("--accent-2") || "#9b6dff",
    success: c("--success") || "#34d399",
    warning: c("--warning") || "#fbbf24",
    danger: c("--danger") || "#f87171",
    text: c("--text") || "#eef1fa",
    textDim: c("--text-dim") || "#9aa5c4",
    border: c("--border") || "#26314c",
  };
  const emotionColors = [palette.accent, palette.accent2, palette.success, palette.warning, palette.danger, "#5eead4", "#f472b6"];

  Chart.defaults.color = palette.textDim;
  Chart.defaults.font.family = "Inter, sans-serif";
  Chart.defaults.borderColor = palette.border;

  // ---- stat tiles --------------------------------------------------------
  const exchanges = analysis.exchanges || [];
  const totalWords = exchanges.reduce((sum, e) => sum + e.word_count, 0);
  const avgWords = exchanges.length ? Math.round(totalWords / exchanges.length) : 0;
  const talkTotal = analysis.candidate_words + analysis.interviewer_words;
  const talkPct = talkTotal ? Math.round((analysis.candidate_words / talkTotal) * 100) : 0;
  const positivity = analysis.overall_positivity;
  let toneLabel = "Balanced";
  if (positivity >= 0.62) toneLabel = "Positive";
  else if (positivity <= 0.4) toneLabel = "Reserved";

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  setText("stat-avg-words", avgWords);
  setText("stat-talk-pct", `${talkPct}%`);
  setText("stat-tone", toneLabel);

  // ---- AI summary (markdown) ---------------------------------------------
  const summaryEl = document.getElementById("ai-summary");
  if (summaryEl && window.marked) {
    summaryEl.innerHTML = marked.parse(analysis.summary || "");
  } else if (summaryEl) {
    summaryEl.textContent = analysis.summary || "";
  }

  // ---- sentiment line chart -----------------------------------------------
  const sentimentCtx = document.getElementById("chart-sentiment");
  if (sentimentCtx) {
    new Chart(sentimentCtx, {
      type: "line",
      data: {
        labels: exchanges.map((e) => `Q${e.index + 1}`),
        datasets: [{
          label: "Positivity",
          data: exchanges.map((e) => Math.round(e.positivity * 100)),
          borderColor: palette.accent,
          backgroundColor: (ctx) => {
            const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 240);
            g.addColorStop(0, "rgba(109,140,255,0.35)");
            g.addColorStop(1, "rgba(109,140,255,0)");
            return g;
          },
          fill: true,
          tension: 0.35,
          pointBackgroundColor: palette.accent,
          pointRadius: 4,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { min: 0, max: 100, grid: { color: palette.border }, ticks: { callback: (v) => `${v}%` } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  // ---- talk-time doughnut --------------------------------------------------
  const talkCtx = document.getElementById("chart-talktime");
  if (talkCtx) {
    new Chart(talkCtx, {
      type: "doughnut",
      data: {
        labels: ["You", "Interviewer"],
        datasets: [{
          data: [analysis.candidate_words, analysis.interviewer_words],
          backgroundColor: [palette.accent, palette.border],
          borderWidth: 0,
        }],
      },
      options: {
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  // ---- emotion doughnut -----------------------------------------------------
  const emotionCtx = document.getElementById("chart-emotion");
  if (emotionCtx) {
    const entries = Object.entries(analysis.emotion_counts || {});
    new Chart(emotionCtx, {
      type: "doughnut",
      data: {
        labels: entries.map(([k]) => k),
        datasets: [{
          data: entries.map(([, v]) => v),
          backgroundColor: emotionColors,
          borderWidth: 0,
        }],
      },
      options: { maintainAspectRatio: false, cutout: "60%", plugins: { legend: { position: "bottom" } } },
    });
  }

  // ---- competency bar ---------------------------------------------------------
  const compCtx = document.getElementById("chart-competency");
  if (compCtx) {
    const entries = Object.entries(analysis.competency_counts || {}).sort((a, b) => b[1] - a[1]);
    new Chart(compCtx, {
      type: "bar",
      data: {
        labels: entries.map(([k]) => k),
        datasets: [{
          data: entries.map(([, v]) => v),
          backgroundColor: palette.accent2,
          borderRadius: 6,
          maxBarThickness: 28,
        }],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: palette.border } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  // ---- Q&A accordion ------------------------------------------------------------
  document.querySelectorAll("[data-toggle]").forEach((header) => {
    header.addEventListener("click", () => {
      header.closest(".qa-item").classList.toggle("open");
    });
  });
  const firstItem = document.querySelector(".qa-item");
  if (firstItem) firstItem.classList.add("open");
})();
