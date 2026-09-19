(function () {
    "use strict";

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
    }

    function initThemeToggle() {
        const toggle = document.getElementById("themeToggle");

        const savedTheme = localStorage.getItem("theme");
        const systemPrefersDark =
            window.matchMedia("(prefers-color-scheme: dark)").matches;

        applyTheme(savedTheme || (systemPrefersDark ? "dark" : "light"));

        if (toggle) {
            toggle.addEventListener("click", function () {
                const current =
                    document.documentElement.getAttribute("data-theme");

                const next = current === "dark" ? "light" : "dark";

                applyTheme(next);
                localStorage.setItem("theme", next);

                if (navigator.vibrate) {
                    navigator.vibrate(10);
                }
            });
        }

        const media =
            window.matchMedia("(prefers-color-scheme: dark)");

        if (media.addEventListener) {
            media.addEventListener("change", function (event) {
                if (!localStorage.getItem("theme")) {
                    applyTheme(event.matches ? "dark" : "light");
                }
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initThemeToggle,
            { once: true }
        );
    } else {
        initThemeToggle();
    }
})();
