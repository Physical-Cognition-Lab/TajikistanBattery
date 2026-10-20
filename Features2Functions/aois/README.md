# AOI coordinates

These files match the **displayed 1350 × 1080 images**, not the original
720 × 576 image files. Coordinates are relative to the image's top-left corner:
x increases rightwards and y increases downwards. They are not screen or DeToX
gaze coordinates.

The original centers, widths and heights were multiplied by **1.875**. The
original `area_px` values were multiplied by **1.875²**; `area_percent` is
unchanged. Decimal values are intentional, to avoid rounding the AOI boundaries.
The original areas were preserved proportionally, not recalculated as width ×
height, because some original values differ from that product.

The same files apply on both planned screen resolutions because the displayed
image size is fixed. Do not scale these coordinates again. If converting to
top-left screen coordinates, the centered image starts at (285, 0) on a
1920 × 1080 screen or (285, 60) on a 1920 × 1200 screen.

For the current center-origin, y-up DeToX gaze coordinates, an AOI center would
instead be `(centre_x - 675, 540 - centre_y)`; widths and heights stay unchanged.
