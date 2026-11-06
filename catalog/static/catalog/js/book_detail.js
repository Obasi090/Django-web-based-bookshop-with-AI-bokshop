document.addEventListener("DOMContentLoaded", function () {
  var description = document.getElementById("book-description");
  var toggle = document.getElementById("description-toggle");
  if (!description || !toggle) return;
  if (description.innerText.trim().length < 550) return;
  description.classList.add("bh-description-clamped");
  description.style.maxHeight = "12em";
  description.style.overflow = "hidden";
  toggle.hidden = false;
  toggle.addEventListener("click", function () {
    var expanded = description.classList.toggle("bh-description-expanded");
    description.style.maxHeight = expanded ? "none" : "12em";
    description.style.overflow = expanded ? "visible" : "hidden";
    toggle.textContent = expanded ? "Show less" : "Show more";
  });
});
