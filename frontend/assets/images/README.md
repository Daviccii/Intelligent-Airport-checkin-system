# Image Assets Organization Guide

## 📁 Folder Structure

```
assets/
└── images/
    ├── airport/          # Airport terminal, check-in, boarding areas
    ├── destinations/     # Beach, cities, travel destinations
    ├── aircraft/         # Planes, cabins, aircraft interiors
    ├── heroes/           # Hero section banners (large background images)
    └── icons/            # Small icons and logos
```

## 📸 Recommended Image Usage

### **airport/**
- Terminal interiors/exteriors
- Check-in counters
- Boarding gates
- Security areas
- Departure boards
- Airport signage
**Image size:** 800x600px or larger
**Format:** JPG or WebP

### **destinations/**
- Beach destinations
- City skylines
- Cultural landmarks
- Nature/scenic views
- Tourist attractions
**Image size:** 600x400px (for cards)
**Format:** JPG or WebP

### **aircraft/**
- Airplane exteriors
- Cabin interiors
- Seat configurations
- Airplane views from window
- Aircraft on runway
**Image size:** 800x600px or larger
**Format:** JPG or WebP

### **heroes/**
- Large banner images for hero sections
- Full-width background images
- Slideshow images
**Image size:** 1920x1080px or larger
**Format:** JPG or WebP (optimized)

### **icons/**
- Navigation icons
- Feature icons
- Status indicators
- Small UI graphics
**Image size:** 32x32px to 256x256px
**Format:** PNG (transparent) or SVG

## 🔗 How to Reference Images in HTML

```html
<!-- Hero image -->
<img src="/assets/images/heroes/airport-terminal.jpg" alt="Airport Terminal">

<!-- Destination card -->
<img src="/assets/images/destinations/beach-sunset.jpg" alt="Beach Destination">

<!-- Aircraft cabin -->
<img src="/assets/images/aircraft/cabin-interior.jpg" alt="Cabin Interior">

<!-- Airport feature -->
<img src="/assets/images/airport/check-in-counter.jpg" alt="Check-in Counter">

<!-- Icon -->
<img src="/assets/images/icons/flight-icon.svg" alt="Flight Icon">
```

## 📥 Steps to Add Images

1. **Download from Unsplash** (unsplash.com)
   - Search: "airport", "airplane", "destinations", etc.
   - Download the image

2. **Place in appropriate folder**
   - Airport images → `airport/`
   - Destination images → `destinations/`
   - Aircraft images → `aircraft/`
   - Hero images → `heroes/`
   - Icons → `icons/`

3. **Name the file clearly**
   - Example: `airport-terminal-interior.jpg`
   - Use lowercase, hyphens for spaces
   - Keep names descriptive

4. **Reference in HTML**
   - Use path `/assets/images/folder-name/image-name.jpg`

## 🖼️ Recommended Search Terms for Unsplash

- "airport terminal"
- "airplane cabin"
- "boarding gate"
- "check-in counter"
- "airplane window"
- "flight attendant"
- "luggage"
- "passport"
- "boarding pass"
- "aircraft exterior"
- "beach destination"
- "city skyline"

## 💡 Tips

- **Optimize images** before uploading to reduce file size
- **Use WebP format** for modern browsers (better compression)
- **Keep hero images** under 500KB each
- **Use consistent dimensions** within each category
- **Add alt text** to all images for accessibility

---

Ready to start adding images? Download from Unsplash and place them in the appropriate folders! 🚀
