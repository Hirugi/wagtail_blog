document.addEventListener("DOMContentLoaded", () => {
  const carousels = document.querySelectorAll(".carousel");

  const preloadCarousel = (carousel) => {
    const images = carousel.querySelectorAll("img.lazy");
    images.forEach(img => {
      if (img.dataset.src) {
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
        img.classList.remove("lazy");
      }
    });
  };

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        preloadCarousel(entry.target);
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });

  carousels.forEach(c => observer.observe(c));
});