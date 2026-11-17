// About how much of the map is on screen, in map pixels (16 px tiles). 800 wide frames the buildings like the user's
// reference picture: one FD quad is about a third of the screen wide.
//
// Smoothness: the canvas is drawn at the screen's real (device) pixel size, and the camera zooms by a WHOLE number,
// the one that shows closest to VIEW_W map pixels. Every map pixel is then exactly the same number of screen pixels.
// (Stretching an 800 x 450 canvas to the window gave a non-whole factor such as 3.6, so some pixel columns were 3
// screen pixels wide and some 4; while scrolling, that pattern crawled over the map and the movement looked jerky.)
export const VIEW_W = 800;

export function screenSize() {
  const dpr = window.devicePixelRatio || 1;
  return { w: Math.round(window.innerWidth * dpr), h: Math.round(window.innerHeight * dpr), dpr };
}

/** whole-number zoom that shows closest to VIEW_W map pixels across */
export function pixelZoom() {
  return Math.max(1, Math.round(screenSize().w / VIEW_W));
}
