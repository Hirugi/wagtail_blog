(function(){
  var globalOverlay = null;
  var lightboxImages = [];
  var lightboxCurrent = 0;

  function ensureOverlay(){
    if (globalOverlay) return globalOverlay;
    globalOverlay = document.createElement('div');
    globalOverlay.className = 'carousel-zoom-overlay';
    
    var img = document.createElement('img');
    img.className = 'carousel-zoom-image';
    globalOverlay.appendChild(img);
    
    // Navigation buttons
    var prevBtn = document.createElement('button');
    prevBtn.className = 'lightbox-nav lightbox-nav--prev';
    prevBtn.innerHTML = '‹';
    prevBtn.setAttribute('aria-label', 'Previous');
    globalOverlay.appendChild(prevBtn);
    
    var nextBtn = document.createElement('button');
    nextBtn.className = 'lightbox-nav lightbox-nav--next';
    nextBtn.innerHTML = '›';
    nextBtn.setAttribute('aria-label', 'Next');
    globalOverlay.appendChild(nextBtn);
    
    // Counter
    var counter = document.createElement('div');
    counter.className = 'lightbox-counter';
    globalOverlay.appendChild(counter);
    
    // Close button
    var closeBtn = document.createElement('button');
    closeBtn.className = 'lightbox-close';
    closeBtn.innerHTML = '×';
    closeBtn.setAttribute('aria-label', 'Close');
    globalOverlay.appendChild(closeBtn);
    
    // Event listeners
    globalOverlay.addEventListener('click', function(e){
      if (e.target === globalOverlay || e.target.classList.contains('lightbox-close')){
        closeLightbox();
      }
    });
    
    prevBtn.addEventListener('click', function(e){
      e.stopPropagation();
      showLightboxImage(lightboxCurrent - 1);
    });
    
    nextBtn.addEventListener('click', function(e){
      e.stopPropagation();
      showLightboxImage(lightboxCurrent + 1);
    });
    
    document.body.appendChild(globalOverlay);
    return globalOverlay;
  }

  function showLightboxImage(index){
    if (lightboxImages.length === 0) return;
    lightboxCurrent = (index + lightboxImages.length) % lightboxImages.length;
    var img = globalOverlay.querySelector('.carousel-zoom-image');
    var counter = globalOverlay.querySelector('.lightbox-counter');
    img.setAttribute('src', lightboxImages[lightboxCurrent]);
    counter.textContent = (lightboxCurrent + 1) + ' / ' + lightboxImages.length;
  }

  function openLightbox(images, startIndex){
    lightboxImages = images;
    lightboxCurrent = startIndex;
    var overlay = ensureOverlay();
    showLightboxImage(startIndex);
    overlay.classList.add('is-open');
    
    // Keyboard navigation
    document.addEventListener('keydown', handleLightboxKeys);
    
    // Touch swipe for mobile
    var startX = null;
    var startY = null;
    var swiping = false;
    
    function handleTouchStart(e){
      var t = e.touches ? e.touches[0] : e;
      startX = t.clientX;
      startY = t.clientY;
      swiping = true;
    }
    
    function handleTouchEnd(e){
      if (!swiping) return;
      var t = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : e;
      var dx = t.clientX - startX;
      var dy = Math.abs(t.clientY - startY);
      var threshold = 40;
      
      if (Math.abs(dx) > threshold && dy < 60){
        if (dx < 0) showLightboxImage(lightboxCurrent + 1);
        else showLightboxImage(lightboxCurrent - 1);
      }
      startX = startY = null;
      swiping = false;
    }
    
    overlay.addEventListener('touchstart', handleTouchStart, { passive: true });
    overlay.addEventListener('touchend', handleTouchEnd);
  }

  function closeLightbox(){
    if (globalOverlay) globalOverlay.classList.remove('is-open');
    document.removeEventListener('keydown', handleLightboxKeys);
    lightboxImages = [];
    lightboxCurrent = 0;
  }

  function handleLightboxKeys(e){
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') { e.preventDefault(); showLightboxImage(lightboxCurrent - 1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); showLightboxImage(lightboxCurrent + 1); }
  }

  function initCarousel(root){
    var slides = Array.from(root.querySelectorAll('.carousel__slide'));
    if (!slides.length) return;
    var current = 0;
    var btnPrev = root.querySelector('[data-carousel-prev]');
    var btnNext = root.querySelector('[data-carousel-next]');
    var curEl = root.querySelector('[data-carousel-current]');
    var totalEl = root.querySelector('[data-carousel-total]');

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

    // Carousel zoom functionality
    root.addEventListener('click', function(e){
      var target = e.target;
      if (target && target.matches('[data-zoomable]')){
        var images = slides.map(function(slide){
          return slide.querySelector('img').getAttribute('src');
        });
        openLightbox(images, current);
      }
    });

    // Carousel swipe support (only for carousel navigation, not lightbox)
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
      var threshold = 40;
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

  // Global lightbox for single images
  function initGlobalLightbox(){
    document.addEventListener('click', function(e){
      var t = e.target;
      if (!t || !t.matches('[data-zoomable]')) return;
      
      // Check if it's part of a carousel
      var carousel = t.closest('[data-carousel]');
      if (carousel) return; // Let carousel handle it
      
      var src = t.getAttribute('data-fullsrc') || t.getAttribute('src');
      openLightbox([src], 0);
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('[data-carousel]').forEach(initCarousel);
    initGlobalLightbox();
  });
})();


