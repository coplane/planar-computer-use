from PIL import Image, ImageDraw, ImageFont
from typing import Optional  # Use TypingTuple for clarity


def draw_annotated_grid(
    image: Image.Image,  # Forward reference for PIL.Image.Image
    num_rows: int = 3,
    num_cols: int = 4,
    number_font_size: int = 25,
    grid_line_color: tuple[int, int, int, int] = (255, 0, 0, 255),
    grid_line_width: int = 1,
    text_color: tuple[int, int, int, int] = (255, 0, 0, 255),
    target_rect: Optional[tuple[int, int, int, int]] = None,
    target_rect_outline_color: Optional[tuple[int, int, int, int]] = (255, 0, 0, 255),
    target_rect_outline_width: int = 1,
) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """
    Draws an `num_rows` x `num_cols` grid on top of a PIL image, potentially within a specified sub-rectangle.
    If target_rect is specified, its outline is also drawn.
    Each cell contains a number (0 to `num_rows * num_cols - 1`) drawn in its center with transparency.

    Args:
        image: The input PIL.Image.Image object.
        num_rows: Number of rows in the grid. Must be positive.
        num_cols: Number of columns in the grid. Must be positive.
        number_font_size: The font size for the numbers in cells.
        grid_line_color: Color of the grid lines (R, G, B, A).
        grid_line_width: Width of the grid lines.
        text_color: Color of the text (R, G, B, A), including transparency.
        target_rect: Optional tuple (x1, y1, x2, y2) defining the rectangle
                     within the image where the grid should be drawn.
                     If None, the grid is drawn over the entire image. Coordinates can be
                     in any order (e.g., x2 < x1 is allowed).
        target_rect_outline_color: Color for the outline of the target_rect
                                   (R, G, B, A). If None, no outline is drawn.
        target_rect_outline_width: Width of the target_rect outline.

    Returns:
        A tuple containing:
        - modified_image: The PIL.Image.Image object with the grid and numbers.
        - cell_coords: A list of `num_rows * num_cols` tuples, where each tuple contains four
                       integer coordinates (x1, y1, x2, y2) representing the
                       top-left and bottom-right corners of the cell
                       corresponding to its index (0 to `num_rows * num_cols - 1`). These coordinates are
                       absolute to the original image.
    Raises:
        ValueError: If num_rows or num_cols is not positive.
    """
    if num_rows <= 0:
        raise ValueError("num_rows must be positive.")
    if num_cols <= 0:
        raise ValueError("num_cols must be positive.")

    # Ensure PIL types are available. These would typically be imported at the top of the file.
    # from PIL import Image, ImageDraw, ImageFont
    # The following lines assume ImageDraw and ImageFont are available in the global scope
    # or correctly imported (e.g., via `from PIL import ImageDraw, ImageFont`).

    img = image.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    img_full_width, img_full_height = img.size

    origin_x: float
    origin_y: float
    rect_width: float
    rect_height: float

    if target_rect:
        tx1, ty1, tx2, ty2 = target_rect
        effective_tx1 = float(min(tx1, tx2))
        effective_ty1 = float(min(ty1, ty2))
        effective_tx2 = float(max(tx1, tx2))
        effective_ty2 = float(max(ty1, ty2))

        origin_x = effective_tx1
        origin_y = effective_ty1
        rect_width = effective_tx2 - effective_tx1
        rect_height = effective_ty2 - effective_ty1

        if rect_width <= 0 or rect_height <= 0:
            print(
                f"Warning: Target rectangle has zero or negative effective width/height ({rect_width}x{rect_height}). Grid not drawn."
            )
            if target_rect_outline_color:
                draw.rectangle(
                    (effective_tx1, effective_ty1, effective_tx2, effective_ty2),
                    outline=target_rect_outline_color,
                    width=target_rect_outline_width,
                )
            coords = (
                round(effective_tx1),
                round(effective_ty1),
                round(effective_tx2),
                round(effective_ty2),
            )
            total_cells = num_rows * num_cols
            return img, [coords] * total_cells

        if target_rect_outline_color:
            draw.rectangle(
                (effective_tx1, effective_ty1, effective_tx2, effective_ty2),
                outline=target_rect_outline_color,
                width=target_rect_outline_width,
            )
    else:
        origin_x, origin_y = 0.0, 0.0
        rect_width, rect_height = float(img_full_width), float(img_full_height)

    cell_width = rect_width / float(num_cols)
    cell_height = rect_height / float(num_rows)

    try:
        font = ImageFont.truetype("arial.ttf", number_font_size)
    except IOError:
        font_fallback_message = "Arial font not found. Using default PIL font. "
        try:
            font = ImageFont.load_default(size=number_font_size)  # Pillow 10.0.0+
            font_fallback_message += "Using resizable default font (Pillow 10.0.0+)."
        except TypeError:
            font = ImageFont.load_default()
            font_fallback_message += "Number size may not be as specified. Consider installing Arial or upgrading Pillow for resizable default font."
        print(font_fallback_message)

    # --- 1. Draw grid lines ---
    if rect_width > 0 and rect_height > 0:  # Only draw lines if the rect is valid
        # Vertical lines
        if num_cols > 1:
            for i in range(1, num_cols):
                x_coord = origin_x + i * cell_width
                draw.line(
                    [(x_coord, origin_y), (x_coord, origin_y + rect_height)],
                    fill=grid_line_color,
                    width=grid_line_width,
                )

        # Horizontal lines
        if num_rows > 1:
            for i in range(1, num_rows):
                y_coord = origin_y + i * cell_height
                draw.line(
                    [(origin_x, y_coord), (origin_x + rect_width, y_coord)],
                    fill=grid_line_color,
                    width=grid_line_width,
                )

    # --- 2. Draw numbers and collect cell coordinates ---
    cell_coordinates_list = []
    for r in range(num_rows):
        for c in range(num_cols):
            cell_idx = r * num_cols + c
            text_to_draw = str(cell_idx)

            abs_x1 = origin_x + c * cell_width
            abs_y1 = origin_y + r * cell_height
            abs_x2 = origin_x + (c + 1) * cell_width
            abs_y2 = origin_y + (r + 1) * cell_height
            cell_coordinates_list.append(
                (round(abs_x1), round(abs_y1), round(abs_x2), round(abs_y2))
            )

            if (
                rect_width <= 0
                or rect_height <= 0
                or cell_width < 1.0
                or cell_height < 1.0
            ):
                continue  # Skip drawing text if cell or target_rect is too small/degenerate

            center_x_abs = (abs_x1 + abs_x2) / 2.0
            center_y_abs = (abs_y1 + abs_y2) / 2.0

            text_x_pos: float
            text_y_pos: float
            try:  # Pillow 9.2.0+ supports anchor="mm"
                draw.text(
                    (center_x_abs, center_y_abs),
                    text_to_draw,
                    font=font,
                    fill=text_color,
                    anchor="mm",
                )
            except AttributeError:  # Fallback for older Pillow versions
                if hasattr(font, "getbbox"):
                    ink_bbox = font.getbbox(text_to_draw)
                    ink_width = ink_bbox[2] - ink_bbox[0]
                    ink_height = ink_bbox[3] - ink_bbox[1]
                    text_x_pos = center_x_abs - (ink_bbox[0] + ink_width / 2.0)
                    text_y_pos = center_y_abs - (ink_bbox[1] + ink_height / 2.0)
                else:
                    text_w, text_h = -1.0, -1.0
                    if hasattr(draw, "textbbox"):  # Pillow 8.0.0+
                        bbox = draw.textbbox((0, 0), text_to_draw, font=font)
                        text_w, text_h = (
                            float(bbox[2] - bbox[0]),
                            float(bbox[3] - bbox[1]),
                        )
                    elif hasattr(draw, "textsize"):  # Deprecated
                        size_result = draw.textsize(text_to_draw, font=font)
                        text_w, text_h = float(size_result[0]), float(size_result[1])
                    elif hasattr(font, "getmask"):  # Ancient
                        mask = font.getmask(text_to_draw)
                        if mask:
                            text_w, text_h = float(mask.size[0]), float(mask.size[1])

                    if text_w != -1.0:
                        text_x_pos = center_x_abs - text_w / 2.0
                        text_y_pos = center_y_abs - text_h / 2.0
                    else:
                        text_x_pos, text_y_pos = center_x_abs, center_y_abs

                draw.text(
                    (text_x_pos, text_y_pos), text_to_draw, font=font, fill=text_color
                )

    return img, cell_coordinates_list


def draw_bounding_box(image: Image.Image, box: tuple[int, int, int, int]):
    draw = ImageDraw.Draw(image)
    xmin, ymin, xmax, ymax = box
    draw.rectangle([xmin, ymin, xmax, ymax], outline="red", width=2)
    return image
