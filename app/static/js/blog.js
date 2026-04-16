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
    var prevBtn = globalOverlay.querySelector('.lightbox-nav--prev');
    var nextBtn = globalOverlay.querySelector('.lightbox-nav--next');
    
    img.setAttribute('src', lightboxImages[lightboxCurrent]);
    
    // Show/hide navigation elements based on image count
    if (lightboxImages.length > 1) {
      counter.textContent = (lightboxCurrent + 1) + ' / ' + lightboxImages.length;
      counter.style.display = 'block';
      prevBtn.style.display = 'flex';
      nextBtn.style.display = 'flex';
    } else {
      counter.style.display = 'none';
      prevBtn.style.display = 'none';
      nextBtn.style.display = 'none';
    }
  }

  function openLightbox(images, startIndex){
    // Reset global state
    lightboxImages = [];
    lightboxCurrent = 0;
    
    // Set new data
    lightboxImages = images;
    lightboxCurrent = startIndex;
    
    var overlay = ensureOverlay();
    showLightboxImage(startIndex);
    overlay.classList.add('is-open');
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
    
    // Keyboard navigation
    document.addEventListener('keydown', handleLightboxKeys);
    
    // Touch swipe for mobile
    var startX = null;
    var startY = null;
    var swiping = false;
    var lastSwipeTime = 0;
    var swipeCooldown = 500;
    var minSwipeDistance = 80;
    
    function handleTouchStart(e){
      // Don't prevent default on buttons
      if (e.target.closest('button')) return;
      
      var t = e.touches ? e.touches[0] : e;
      startX = t.clientX;
      startY = t.clientY;
      swiping = true;
    }
    
    function handleTouchMove(e){
      if (!swiping) return;
      
      // Only prevent scroll if we're actually swiping
      var t = e.touches ? e.touches[0] : e;
      var dx = Math.abs(t.clientX - startX);
      var dy = Math.abs(t.clientY - startY);
      
      if (dx > 10 || dy > 10) {
        e.preventDefault();
      }
    }
    
    function handleTouchEnd(e){
      if (!swiping) return;
      
      var now = Date.now();
      if (now - lastSwipeTime < swipeCooldown) {
        startX = startY = null;
        swiping = false;
        return;
      }
      
      var t = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : e;
      var dx = t.clientX - startX;
      var dy = Math.abs(t.clientY - startY);
      
      if (Math.abs(dx) > minSwipeDistance && dy < 100 && lightboxImages.length > 1){
        if (dx < 0) showLightboxImage(lightboxCurrent + 1);
        else showLightboxImage(lightboxCurrent - 1);
        lastSwipeTime = now;
      }
      startX = startY = null;
      swiping = false;
    }
    
    // Store handlers for cleanup
    overlay._touchStartHandler = handleTouchStart;
    overlay._touchMoveHandler = handleTouchMove;
    overlay._touchEndHandler = handleTouchEnd;
    
    overlay.addEventListener('touchstart', handleTouchStart, { passive: true });
    overlay.addEventListener('touchmove', handleTouchMove, { passive: false });
    overlay.addEventListener('touchend', handleTouchEnd, { passive: true });
  }

  function closeLightbox(){
    if (globalOverlay) {
      // Remove touch event listeners
      if (globalOverlay._touchStartHandler) {
        globalOverlay.removeEventListener('touchstart', globalOverlay._touchStartHandler);
        globalOverlay.removeEventListener('touchmove', globalOverlay._touchMoveHandler);
        globalOverlay.removeEventListener('touchend', globalOverlay._touchEndHandler);
        globalOverlay._touchStartHandler = null;
        globalOverlay._touchMoveHandler = null;
        globalOverlay._touchEndHandler = null;
      }
      
      globalOverlay.classList.remove('is-open');
    }
    
    document.removeEventListener('keydown', handleLightboxKeys);
    // Restore body scroll
    document.body.style.overflow = '';
    
    // Reset global state
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

// ── Image loading placeholders ────────────────────────────
(function(){
  var SEL = '.post-media, .post-responsive-image, .carousel__slide';

  function markLoaded(img){
    var c = img.closest(SEL);
    if (c) c.classList.add('is-loaded');
  }

  // Capture-phase 'load' catches non-bubbling events from every <img>
  document.addEventListener('load', function(e){
    if (e.target.tagName === 'IMG') markLoaded(e.target);
  }, true);

  // Mark already-cached images on page load
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll(SEL).forEach(function(c){
      var img = c.querySelector('img');
      if (img && img.complete && img.naturalHeight > 0) markLoaded(img);
    });
  });
})();


