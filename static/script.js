document.addEventListener('DOMContentLoaded', () => {
    // Session management buttons
    const createSessionBtn = document.getElementById('create-session');
    const copyLinkBtn = document.getElementById('copy-link');

    // Setup session management
    if (createSessionBtn) {
        createSessionBtn.addEventListener('click', () => {
            window.location.href = '/session/create';
        });
    }

    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', () => {
            const url = window.location.href;
            navigator.clipboard.writeText(url).then(() => {
                alert('Session link copied to clipboard! Share this with your students.');
            }).catch(err => {
                console.error('Could not copy link: ', err);
                prompt('Copy this link to share with your students:', url);
            });
        });
    }

    const elements = {
        imageReel: document.getElementById('image-reel'),
        largeImage: document.getElementById('large-image'),
        imageDetail: document.getElementById('image-detail'),
        refreshBtn: document.getElementById('refresh'),
        downloadZipBtn: document.getElementById('download-zip'),
        downloadPdfBtn: document.getElementById('download-pdf'),
        prevBtn: document.getElementById('prev'),
        nextBtn: document.getElementById('next'),
        saveBtn: document.getElementById('save'),
        fullscreenBtn: document.getElementById('fullscreen'),
        deleteBtn: document.getElementById('delete')
    };

    let images = [];  // List of images from the server
    let currentIndex = 0;  // Track currently viewed image

    // Toggle fullscreen mode
    const toggleFullscreen = () => {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            (elements.largeImage.requestFullscreen || elements.largeImage.mozRequestFullScreen || 
             elements.largeImage.webkitRequestFullscreen || elements.largeImage.msRequestFullscreen).call(elements.largeImage);
        }
    };

    // Delete current image
    const deleteImage = async () => {
        if (images.length === 0 || currentIndex < 0 || !confirm("Delete this image?")) return;

        const filename = images[currentIndex].filename;
        try {
            const response = await fetch(`/api/delete/${filename}`, { method: 'DELETE' });
            if (!response.ok) throw new Error("Deletion failed");

            images.splice(currentIndex, 1);
            if (images.length === 0) {
                elements.imageDetail.classList.add('hidden');
            } else {
                currentIndex = Math.min(currentIndex, images.length - 1);
                showImage(currentIndex);
            }
            displayThumbnails();
        } catch (error) {
            console.error('Deletion error:', error);
            alert("Failed to delete. Try again.");
        }
    };

    // Fetch images from server
    const fetchImages = async () => {
        try {
            const response = await fetch('/api/images');
            if (!response.ok) throw new Error("Fetch failed");
            const newImages = await response.json();

            // Update current index if new images are added
            if (newImages.length > images.length) {
                currentIndex = newImages.length - 1;  // Jump to newest image
                // Auto-scroll reel to right
                elements.imageReel.scrollTo({
                    left: elements.imageReel.scrollWidth,
                    behavior: 'smooth'
                });
            }

            images = newImages;
            displayThumbnails();
            if (images.length) showImage(currentIndex);
        } catch (error) {
            console.error('Fetch error:', error);
            alert("Failed to load images. Refresh page.");
        }
    };

    // Display thumbnails
    const displayThumbnails = () => {
        elements.imageReel.innerHTML = images.length ? '' : '<p>No images found.</p>';
        images.forEach((img, index) => {
            const container = document.createElement('div');
            container.className = 'thumbnail-container';
            
            const imgElement = document.createElement('img');
            // Use Cloudinary URL if available, otherwise use local path
            imgElement.src = img.cloudinary_url || `/api/images/${img.filename}`;
            imgElement.alt = `Thumbnail ${index + 1}`;
            imgElement.title = `Image ${index + 1}`;
            imgElement.addEventListener('click', () => showImage(index));

            const numberLabel = document.createElement('div');
            numberLabel.textContent = index + 1;
            numberLabel.className = 'number-label';

            container.appendChild(imgElement);
            container.appendChild(numberLabel);
            elements.imageReel.appendChild(container);
        });
        highlightCurrentImage();
    };

    // Show selected image
    const showImage = (index) => {
        currentIndex = index;
        // Use Cloudinary URL if available, otherwise use local path
        elements.largeImage.src = images[index].cloudinary_url || `/api/images/${images[index].filename}`;
        elements.imageDetail.classList.remove('hidden');
        highlightCurrentImage();
        elements.prevBtn.disabled = index === 0;
        elements.nextBtn.disabled = index === images.length - 1;
    };

    // Highlight current image in the reel
    const highlightCurrentImage = () => {
        document.querySelectorAll('.thumbnail-container img').forEach((img, i) => {
            img.classList.toggle('selected', i === currentIndex);
        });
    };

    // Set up event listeners
    [
        ['dblclick', elements.largeImage, toggleFullscreen],
        ['click', elements.fullscreenBtn, toggleFullscreen],
        ['click', elements.deleteBtn, deleteImage],
        ['click', elements.refreshBtn, fetchImages],
        ['click', elements.downloadZipBtn, () => window.location.href = '/api/download'],
        ['click', elements.downloadPdfBtn, () => window.location.href = '/api/download-pdf'],
        ['click', elements.prevBtn, () => currentIndex > 0 && showImage(currentIndex - 1)],
        ['click', elements.nextBtn, () => currentIndex < images.length - 1 && showImage(currentIndex + 1)],
        ['click', elements.saveBtn, () => {
            if (images.length && currentIndex >= 0) {
                const link = document.createElement('a');
                // Use Cloudinary URL if available
                link.href = images[currentIndex].cloudinary_url || elements.largeImage.src;
                link.download = images[currentIndex].filename;
                link.click();
            }
        }]
    ].forEach(([event, element, handler]) => element.addEventListener(event, handler));

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (!images.length) return;
        switch(e.key) {
            case 'ArrowLeft': currentIndex > 0 && showImage(currentIndex - 1); break;
            case 'ArrowRight': currentIndex < images.length - 1 && showImage(currentIndex + 1); break;
            case 'Delete': e.ctrlKey && deleteImage(); break;
        }
    });

    // Handle image load errors
    elements.largeImage.addEventListener('error', () => {
        alert('Image load failed. Refresh the page.');
        elements.imageDetail.classList.add('hidden');
    });

    // Initial fetch and setup polling
    fetchImages();
    setInterval(fetchImages, 55000);
});