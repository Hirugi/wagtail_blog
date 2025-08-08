(function(){
  function initCarousel(root){
    var slides = Array.from(root.querySelectorAll('.carousel__slide'));
    if (!slides.length) return;
    var current = 0;
    var btnPrev = root.querySelector('[data-carousel-prev]');
    var btnNext = root.querySelector('[data-carousel-next]');
    var curEl = root.querySelector('[data-carousel-current]');
    var totalEl = root.querySelector('[data-carousel-total]');
    var overlay = null;

    function show(index){
      slides[current].classList.remove('is-active');
      current = (index + slides.length) % slides.length;
      slides[current].classList.add('is-active');
      if (curEl) curEl.textContent = String(current + 1);
    }

    if (totalEl) totalEl.textContent = String(slides.length);
    show(0);

    if (btnPrev) btnPrev.addEventListener('click', function(){ show(current - 1); });
    if (btnNext) btnNext.addEventListener('click', function(){ show(current + 1); });

    // Zoom overlay
    function ensureOverlay(){
      if (overlay) return overlay;
      overlay = document.createElement('div');
      overlay.className = 'carousel-zoom-overlay';
      var img = document.createElement('img');
      img.className = 'carousel-zoom-image';
      overlay.appendChild(img);
      overlay.addEventListener('click', function(){ overlay.classList.remove('is-open'); });
      document.body.appendChild(overlay);
      return overlay;
    }

    root.addEventListener('click', function(e){
      var target = e.target;
      if (target && target.matches('[data-zoomable]')){
        var bigSrc = target.getAttribute('src');
        var ov = ensureOverlay();
        ov.querySelector('img').setAttribute('src', bigSrc);
        ov.classList.add('is-open');
      }
    });

    // Swipe / touch support
    var startX = null;
    var startY = null;
    var swiping = false;

    function onPointerDown(e){
      var t = e.touches ? e.touches[0] : e;
      startX = t.clientX; startY = t.clientY; swiping = true;
    }
    function onPointerUp(e){
      if (!swiping) return;
      var t = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : e;
      var dx = t.clientX - startX;
      var dy = Math.abs(t.clientY - startY);
      var threshold = 40; // px
      // Ignore if mostly vertical move
      if (Math.abs(dx) > threshold && dy < 60){
        if (dx < 0) show(current + 1); else show(current - 1);
      }
      startX = startY = null; swiping = false;
    }

    root.addEventListener('touchstart', onPointerDown, { passive: true });
    root.addEventListener('touchend', onPointerUp);
    root.addEventListener('mousedown', onPointerDown);
    root.addEventListener('mouseup', onPointerUp);

    // Keyboard navigation when focused
    root.setAttribute('tabindex', '0');
    root.addEventListener('keydown', function(e){
      if (e.key === 'ArrowLeft') { e.preventDefault(); show(current - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); show(current + 1); }
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('[data-carousel]').forEach(initCarousel);
  });
})();


