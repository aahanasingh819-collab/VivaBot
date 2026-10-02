document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const submitButton = form.querySelector('button[type="submit"]');
      const loadingState = form.querySelector(".loading-state");
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent =
          submitButton.dataset.loadingLabel ||
          form.dataset.loadingLabel ||
          "Please wait…";
        submitButton.setAttribute("aria-busy", "true");
      }
      if (loadingState) loadingState.hidden = false;
    });
  });

  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll(".dismiss-message").forEach((button) => {
    button.addEventListener("click", () => button.closest(".flash-message")?.remove());
  });

  const fileInput = document.querySelector("#id_report_file");
  const fileName = document.querySelector("#upload-filename");
  if (fileInput && fileName) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files?.length) fileName.textContent = fileInput.files[0].name;
    });
  }

  const answer = document.querySelector("#answer-text");
  const count = document.querySelector("#answer-count");
  if (answer && count) {
    const updateCount = () => {
      count.textContent = answer.value.length.toLocaleString();
    };
    answer.addEventListener("input", updateCount);
    updateCount();
  }
});