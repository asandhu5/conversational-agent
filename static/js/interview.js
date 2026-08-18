(() => {
  const session = window.__SESSION__;
  const timerEl = document.getElementById("timer");
  const endBtn = document.getElementById("end-btn");
  const processingPanel = document.getElementById("processing-panel");
  const callFrame = document.getElementById("call-frame");

  let remaining = session.durationSeconds;
  let countdownHandle = null;
  let pollHandle = null;

  function formatTime(sec) {
    const m = Math.max(0, Math.floor(sec / 60));
    const s = Math.max(0, sec % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function tickTimer() {
    if (!timerEl) return;
    remaining -= 1;
    timerEl.textContent = formatTime(remaining);
    timerEl.classList.toggle("warning", remaining <= 60 && remaining > 20);
    timerEl.classList.toggle("critical", remaining <= 20);
    if (remaining <= 0) {
      clearInterval(countdownHandle);
      showProcessing();
    }
  }

  function showProcessing() {
    if (callFrame) callFrame.closest(".video-frame")?.remove();
    document.querySelector(".room-header")?.remove();
    document.querySelector(".room-controls")?.remove();
    document.querySelectorAll("p").forEach((p) => {
      if (p.textContent.includes("ends automatically")) p.remove();
    });
    if (processingPanel) processingPanel.style.display = "block";
    startPolling();
  }

  async function endInterview() {
    if (endBtn) {
      endBtn.disabled = true;
      endBtn.textContent = "Ending…";
    }
    try {
      await fetch(session.endUrl, { method: "POST" });
    } catch (err) {
      // The background worker on the server keeps polling Tavus regardless,
      // so a failed request here just means the "please hold" screen takes
      // a little longer to appear -- not a dead end.
      console.warn("Failed to explicitly end the call, waiting on the server instead.", err);
    }
    clearInterval(countdownHandle);
    showProcessing();
  }

  let stepIndex = 0;
  function animateSteps() {
    const steps = document.querySelectorAll(".processing-steps li");
    if (!steps.length) return;
    steps.forEach((li) => li.classList.remove("active"));
    steps[stepIndex % steps.length].classList.add("active");
    stepIndex += 1;
  }

  function startPolling() {
    const stepAnim = setInterval(animateSteps, 2500);
    pollHandle = setInterval(async () => {
      try {
        const resp = await fetch(session.statusUrl);
        const data = await resp.json();
        if (data.status === "ready") {
          clearInterval(pollHandle);
          clearInterval(stepAnim);
          window.location.href = session.reportUrl;
        } else if (data.status === "error") {
          clearInterval(pollHandle);
          clearInterval(stepAnim);
          window.location.href = session.reportUrl;
        }
      } catch (err) {
        console.warn("Status check failed, retrying...", err);
      }
    }, 3000);
  }

  if (session.status === "live") {
    timerEl.textContent = formatTime(remaining);
    countdownHandle = setInterval(tickTimer, 1000);
    endBtn.addEventListener("click", endInterview);
  } else {
    startPolling();
  }
})();
