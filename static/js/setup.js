(() => {
  const form = document.getElementById("setup-form");
  const roleGrid = document.getElementById("role-grid");
  const customFields = document.getElementById("custom-fields");
  const errorBox = document.getElementById("form-error");
  const startBtn = document.getElementById("start-btn");

  roleGrid.addEventListener("change", () => {
    const selected = roleGrid.querySelector("input[name=role]:checked").value;
    roleGrid.querySelectorAll(".role-card").forEach((card) => {
      card.classList.toggle("selected", card.dataset.role === selected);
    });
    customFields.style.display = selected === "custom" ? "block" : "none";
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.style.display = "block";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.style.display = "none";

    const role = roleGrid.querySelector("input[name=role]:checked").value;
    const payload = {
      role,
      candidate_name: document.getElementById("candidate_name").value,
      duration_minutes: document.getElementById("duration_minutes").value,
    };
    if (role === "custom") {
      payload.custom_role_title = document.getElementById("custom_role_title").value;
      payload.custom_prompt = document.getElementById("custom_prompt").value;
      if (!payload.custom_prompt.trim()) {
        showError("Please describe what the interviewer should ask about.");
        return;
      }
    }

    startBtn.disabled = true;
    startBtn.textContent = "Starting…";

    try {
      const resp = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Something went wrong starting the interview.");
      }
      window.location.href = `/interview/${data.session_id}`;
    } catch (err) {
      showError(err.message);
      startBtn.disabled = false;
      startBtn.textContent = "Start Interview";
    }
  });
})();
