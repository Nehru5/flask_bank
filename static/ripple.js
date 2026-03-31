document.querySelectorAll("button, .btn").forEach(button => {
  button.addEventListener("click", function (e) {
    const ripple = document.createElement("span");
    ripple.classList.add("ripple");

    const rect = this.getBoundingClientRect();
    ripple.style.left = e.clientX - rect.left + "px";
    ripple.style.top = e.clientY - rect.top + "px";

    this.appendChild(ripple);

    setTimeout(() => ripple.remove(), 600);
  });
});
