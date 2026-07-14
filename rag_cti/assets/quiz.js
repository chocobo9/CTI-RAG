(() => {
  function evaluateChoice(question, button) {
    const correct = button.dataset.correct === "true";
    question.querySelectorAll("button[data-correct]").forEach((candidate) => {
      candidate.classList.remove("correct", "incorrect");
      candidate.setAttribute("aria-pressed", "false");
    });
    button.classList.add(correct ? "correct" : "incorrect");
    button.setAttribute("aria-pressed", "true");
    const feedback = question.querySelector(".feedback");
    if (feedback) {
      feedback.textContent = button.dataset.feedback || "";
      feedback.className = `feedback ${correct ? "good" : "bad"}`;
    }
  }

  function revealFreeform(question) {
    const feedback = question.querySelector(".feedback");
    const answer = question.dataset.answer || "";
    if (feedback) {
      feedback.textContent = answer;
      feedback.className = "feedback good";
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) {
      return;
    }
    const question = button.closest(".quiz-question");
    if (!question) {
      return;
    }
    if (button.dataset.correct) {
      evaluateChoice(question, button);
    }
    if (button.dataset.reveal) {
      revealFreeform(question);
    }
  });
})();
