// Dark/Light theme toggle, persisted in localStorage. Shared by every page.
// Loaded in <head> (before paint) so the saved theme applies with no flash.
(function () {
  const root = document.documentElement;
  const apply = (t) => root.classList.toggle("dark", t === "dark");

  apply(localStorage.getItem("theme"));

  // Delegated so it works no matter when the header button is parsed.
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#themeToggle")) return;
    const next = root.classList.contains("dark") ? "light" : "dark";
    localStorage.setItem("theme", next);
    apply(next);
  });
})();
