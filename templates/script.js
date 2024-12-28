function changeStyle() {
    const currentStyle = document.getElementById("stylesheet");
    const newStyle = currentStyle.getAttribute("href") === "styles.css"
        ? "vintage.css"
        : "styles.css";

    currentStyle.setAttribute("href", newStyle);
}

