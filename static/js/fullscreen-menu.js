// Открытие/закрытие вручную
function toggleMenu() {
    const menu = document.getElementById("fullscreenMenu");
    menu.classList.toggle("show");
}

// Закрытие по крестику
document.getElementById("closeMenu").addEventListener("click", () => {
    document.getElementById("fullscreenMenu").classList.remove("show");
});

// Закрытие по клику вне меню
document.getElementById("fullscreenMenu").addEventListener("click", function (event) {
    const menuBox = this.querySelector(".menu-box");
    if (!menuBox.contains(event.target)) {
        this.classList.remove("show");
    }
});

// Автоматическое закрытие при ширине экрана > 768px
window.addEventListener("resize", () => {
    const menu = document.getElementById("fullscreenMenu");
    if (window.innerWidth > 768 && menu.classList.contains("show")) {
        menu.classList.remove("show");
    }
});