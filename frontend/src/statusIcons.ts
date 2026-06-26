// String-status icons, imported as raw SVG and inlined as data URIs.
//
// Why inline instead of "/foo.svg" file paths: the map renders each icon via
// `new Image(); img.src = url`, which is served from the browser/service-worker
// cache. When an SVG file changed, the map kept drawing the stale cached raster
// even after the app updated. Bundling the SVG content means the icons ship
// inside the JS (cache-busted by Vite's content hash) — editing an SVG changes
// the bundle, so a normal app update always shows the new artwork, online or
// offline. Single source for both the map sprites and the grid/legend <img>.
import newSvg from "../public/new.svg?raw";
import optimizerSvg from "../public/optimizer-mounted.svg?raw";
import connectionSvg from "../public/panel-connected.svg?raw";
import avlSvg from "../public/avl.svg?raw";
import voltSvg from "../public/volt-test.svg?raw";
import cableSvg from "../public/tga-cable.svg?raw";
import tgaCommSvg from "../public/tga-commissioned.svg?raw";

const uri = (svg: string) => "data:image/svg+xml;utf8," + encodeURIComponent(svg);

// Keyed by string-status code (matches STATUS_SVG usage in App + map).
export const STATUS_ICON_URI: Record<string, string> = {
  new: uri(newSvg),
  optimizer: uri(optimizerSvg),
  connection: uri(connectionSvg),
  avl: uri(avlSvg),
  volt_checked: uri(voltSvg),
  cable_to_tga: uri(cableSvg),
  tga_commissioning: uri(tgaCommSvg),
};
