import base64
import sys
import os
import logging
import json
import imageio
from PIL import Image, ImageEnhance
import numpy as np
from typing import Any, Dict, Optional
import argparse

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QGraphicsOpacityEffect, QWidget, QSystemTrayIcon, QSplashScreen
from PySide6.QtCore import Qt, QTimer, QEventLoop, QPropertyAnimation, QEasingCurve, Slot, QUrl, QSize
from PySide6.QtNetwork import QTcpServer, QHostAddress
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtSvg import QSvgRenderer

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import (
    QPainter,
    QPixmap,
    QFont,
    QFontMetrics,
    QPainterPath,
    QColor,
    QPen,
    QImage,
    qRed,
    qGreen,
    qBlue,
    QIcon
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CardMakerWidget(QWidget):
    """
    Widget for rendering a card based on provided card data.
    """

    def __init__(self, card_data: Dict[str, Any], background_path: str, base_path: str = "", image_path: str = "", extra_args: dict = None, flags: dict = None ,parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Constants for card dimensions
        CARD_WIDTH = 549
        CARD_HEIGHT = 800
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.card_data = card_data
        self.base_path = base_path  # Store the base path

        # Load images.
        self.background = QPixmap(self._get_path(background_path))

        # Set Flags
        self.flags = flags

        # Set Fonts
        self.fonts = {
                    "title_font": "MatrixRegularSmallCaps",
                    "lore_font": "Stone Serif ITC Medium",
                    "main_font": "ITC Stone Serif",
                    "link_font": "EurostileCandyW01"
                    }

        # Override defaults if user provided arguments
        for key in ["title_font", "lore_font", "main_font", "link_font"]:
            if self.flags.get(key):
                self.fonts[key] = self.flags[key]

        # Convert b64 image to pixmap.
        image_data = base64.b64decode(image_path)
        # Create a QPixmap and load the image data
        img_pixmap = QPixmap()
        if not img_pixmap.loadFromData(image_data):
            raise ValueError("Failed to load pixmap from base64 data.")
        self.card_art = img_pixmap

        if extra_args:
            self.edition = extra_args.get("edition", "")
            self.passcode = extra_args.get("passcode", "")
            self.setId = extra_args.get("set_string", "")
            self.copyright = extra_args.get("copyright", "")

        # self.card_art = QPixmap(self._get_path(self.card_data.get("card_art", "assets/card/frame/blank_art.png")))
        self.art_rect = QRect(66, 146, 417, 417)
        self.pend_art_rect = QRect(38, 144, 477, 455)
        self.level_star = QPixmap(self._get_path("assets/card/stars/level.png"))
        self.rank_star = QPixmap(self._get_path("assets/card/stars/rank.png"))
        # print(self._get_path("assets/card/stars/level.png"))

    def _get_path(self, relative_path: str) -> str:
        """
        Helper function to construct the full file path using the base path.
        Splits the relative path string and joins it with base path using os.path.join.
        """
        path_components = relative_path.split('/')
        if self.base_path:
            return os.path.join(self.base_path, *path_components)
        return relative_path  # If no base path, assume relative to current working directory

    def draw_stretched_name(self, painter: QPainter, rect: QRect, text: str, fixed_font_size: int = 22) -> None:
        """
        Draw the card name stretched to fit within the given rectangle.
        """
        font = QFont(self.fonts.get("title_font"), fixed_font_size, QFont.Normal)
        path = QPainterPath()
        path.addText(0, 0, font, text)
        bounds = path.boundingRect()

        if bounds.width() < rect.width():
            scale_factor = 1.0
            offset_x = round(rect.x() - bounds.x())
        else:
            scale_factor = rect.width() / bounds.width()
            offset_x = round(rect.x() - bounds.x() * scale_factor)

        offset_y = round(rect.y() + (rect.height() - bounds.height()) / 2 - bounds.y())

        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale_factor, 1)
        card_type = self.card_data.get("frameType", "").lower()
        fill_color = QColor(255, 255, 255) if card_type.startswith("xyz") or card_type == "link" or card_type == "spell" or card_type == "trap" else QColor(0, 0, 0)
        painter.setBrush(fill_color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
        painter.restore()

    def draw_fitted_description(
        self,
        painter: QPainter,
        rect: QRect,
        text: str,
        max_font_size: int = 12,
        min_font_size: int = 10,
        min_letter_spacing: float = -1.0,
    ) -> None:
        """
        Adjust the font size and letter spacing so the text fits within the given rectangle.
        """
        lore = self.card_data.get("frameType", "").lower() == "normal"
        chosen_font: Optional[QFont] = None

        if lore:
            text = text.strip('\'"')

        for font_size in range(max_font_size, min_font_size - 1, -1):
            letter_spacing = 0.0
            while letter_spacing >= min_letter_spacing:
                font_family = self.fonts.get("lore_font") if lore else self.fonts.get("main_font")
                font = QFont(font_family, font_size, QFont.Light)
                font.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)
                font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
                metrics = QFontMetrics(font)
                bounding = metrics.boundingRect(rect, Qt.TextWordWrap, text)
                if bounding.height() <= rect.height():
                    chosen_font = font
                    break
                letter_spacing -= 0.5
            if chosen_font is not None:
                break

        if chosen_font is None:
            chosen_font = QFont(self.fonts.get("main_font"), min_font_size, QFont.Normal)
            chosen_font.setLetterSpacing(QFont.AbsoluteSpacing, min_letter_spacing)

        painter.setFont(chosen_font)
        painter.drawText(rect, Qt.TextWordWrap, text)

    def draw_level_stars(self, painter: QPainter, rect: QRect, level_value: Any, max_stars: int = 12) -> None:
        """
        Draw star images representing the card's level.
        """
        try:
            level = int(level_value)
        except (ValueError, TypeError):
            level = 0
        stars_count = min(level, max_stars)

        if self.level_star.isNull() or stars_count <= 0:
            return

        star_height = rect.height()
        star_scaled = self.level_star.scaledToHeight(star_height, Qt.SmoothTransformation)
        star_width = star_scaled.width()
        gap = 4

        for i in range(stars_count):
            x = rect.right() - (i + 1) * star_width - i * gap
            y = rect.top() + (rect.height() - star_height) // 2
            painter.drawPixmap(x, y, star_scaled)

    def draw_rank_stars(self, painter: QPainter, rect: QRect, level_value: Any, max_stars: int = 13) -> None:
        """
        Draw star images representing the card's XYZ rank.
        """
        try:
            level = int(level_value)
        except (ValueError, TypeError):
            level = 0
        stars_count = min(level, max_stars)

        if self.rank_star.isNull() or stars_count <= 0:
            return

        star_height = rect.height()
        star_scaled = self.rank_star.scaledToHeight(star_height, Qt.SmoothTransformation)
        star_width = star_scaled.width()
        gap = 4

        if stars_count == 13:
            extra_width = star_width // 2
            rect = QRect(rect.x() - 18, rect.y(), rect.width() + extra_width, rect.height())

        for i in range(stars_count):
            x = rect.left() - 25 + i * (star_width + gap)
            y = rect.top() + (rect.height() - star_height) // 2
            painter.drawPixmap(x, y, star_scaled)

    def _draw_background(self, painter: QPainter) -> None:
        """Draw the background image scaled to the widget size."""
        painter.drawPixmap(0, 0, self.width(), self.height(), self.background)

    def _fade_image(self, image: QImage, fade_start: int, fade_height: int) -> QImage:
        """
        Apply a vertical fade effect to the provided image.
        """
        for y in range(fade_start, image.height()):
            fade_progress = (y - fade_start) / float(fade_height)
            alpha = int(255 * (1.0 - fade_progress))
            alpha = max(0, min(255, alpha))
            for x in range(image.width()):
                pixel = image.pixel(x, y)
                r = qRed(pixel)
                g = qGreen(pixel)
                b = qBlue(pixel)
                image.setPixelColor(x, y, QColor(r, g, b, alpha))
        return image

    def _draw_card_art(self, painter: QPainter, pendulum: bool) -> None:
        """
        Draw the card art. Uses different layout logic for pendulum cards.
        """
        if self.card_art.isNull():
            return

        if pendulum:
            art_rect = self.pend_art_rect
            scaled_art = self.card_art.scaledToWidth(art_rect.width(), Qt.SmoothTransformation)
            art_x, art_y = art_rect.x(), art_rect.y()

            # Crop and apply fade to the art image.
            crop_height = 465
            crop_rect = QRect(0, 0, scaled_art.width(), crop_height)
            cropped_art = scaled_art.copy(crop_rect)

            scaled_image = cropped_art.toImage()
            if scaled_image.format() != QImage.Format_ARGB32:
                scaled_image = scaled_image.convertToFormat(QImage.Format_ARGB32)

            fade_end = 100
            fade_height = 90
            fade_start = max(0, scaled_image.height() - fade_end)
            faded_image = self._fade_image(scaled_image, fade_start, fade_height)
            faded_art = QPixmap.fromImage(faded_image)
            painter.drawPixmap(art_x, art_y, faded_art)
        else:
            scaled_art = self.card_art.scaled(self.art_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            art_x = self.art_rect.x() + (self.art_rect.width() - scaled_art.width()) // 2
            art_y = self.art_rect.y() + (self.art_rect.height() - scaled_art.height()) // 2
            painter.drawPixmap(art_x, art_y, scaled_art)

    def _draw_pendulum_frame(self, painter: QPainter) -> None:
        """Draw the pendulum frame overlay."""
        pend_overlay = QPixmap(self._get_path("assets/card/frame/pendulum_frame_internal.png"))
        painter.drawPixmap(0, 0, self.width(), self.height(), pend_overlay)

    def _draw_link_arrows(self, painter: QPainter) -> None:
        """Draw link arrows as specified in card data."""
        link_arrows = self.card_data.get("linkmarkers", [])
        if not link_arrows:
            return

        base_link_arrows = QPixmap(self._get_path("assets/card/arrows/link_arrows_base_all.png"))
        painter.drawPixmap(0, 0, self.width(), self.height(), base_link_arrows)

        arrow_positions = {
            "Top": (self.width() // 2, 116),
            "Bottom": (self.width() // 2, 562),
            "Left": (35, 304),
            "Right": (482, 304),
            "Top-Left": (46, 126),
            "Top-Right": (453, 126),
            "Bottom-Left": (46, 534),
            "Bottom-Right": (453, 534),
        }

        for arrow in link_arrows:
            arrow_name = arrow
            arrow_image_path = self._get_path(f"assets/card/arrows/{arrow_name}.png")
            arrow_pixmap = QPixmap(arrow_image_path)
            if arrow_pixmap.isNull():
                logger.error("Error loading arrow image: %s", arrow_image_path)
                continue

            pos = arrow_positions.get(arrow_name, (0, 0))
            x, y = pos
            # Center adjustments for common arrow types.
            if arrow_name in ("Top", "Bottom"):
                x -= arrow_pixmap.width() // 2

            painter.drawPixmap(x, y, arrow_pixmap)

    def _draw_card_name(self, painter: QPainter) -> None:
        """Draw the card name using stretched text."""
        name_rect = QRect(42, 38, 412, 50)
        painter.setPen(QColor(0, 0, 0))
        card_name = self.card_data.get("name", "Unknown Card")
        self.draw_stretched_name(painter, name_rect, card_name, fixed_font_size=48)

    def _draw_level_and_rank_stars(self, painter: QPainter) -> None:
        """Draw level or rank stars below the card name."""
        card_type = self.card_data.get("type", "")
        name_rect = QRect(42, 40, 415, 50)
        level_rect = QRect(name_rect.x() + 40, name_rect.bottom() + 9, name_rect.width(), 33)
        if card_type not in ("Spell Card", "Trap Card"):
            if self.card_data.get("frameType", "").lower().startswith("xyz"):
                self.draw_rank_stars(painter, level_rect, self.card_data.get("level", 0), max_stars=13)
            else:
                self.draw_level_stars(painter, level_rect, self.card_data.get("level", 0), max_stars=12)

    def load_svg_with_antialiasing(self, path: str, target_size: QSize) -> QPixmap:
        """Load an SVG file and return a QPixmap rendered with anti-aliasing."""
        renderer = QSvgRenderer(path)
        # Create an image with an alpha channel
        image = QImage(target_size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter_img = QPainter(image)
        painter_img.setRenderHint(QPainter.Antialiasing)
        painter_img.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter_img)
        painter_img.end()

        return QPixmap.fromImage(image)

    def _draw_spell_trap_text(self, painter: QPainter) -> None:
        """Draw the Spell/Trap type text with resized brackets and scaled letters."""
        card_type = self.card_data.get("type", "")
        if card_type in ("Spell Card", "Trap Card"):
            base_font = QFont(self.fonts.get("main_font"), 19.5, QFont.Bold)
            painter.setFont(base_font)

            # Default text rectangle
            st_text_rect = QRect(300, 90, 202, 44)
            text_padding = ""

            if self.card_data.get("race", "").lower() != "normal":
                text_padding = "     "
                st_type = self.card_data.get("race", "").lower()
                icon_path = self._get_path(f"assets/card/attribute/{st_type}.svg")
                icon_pixmap = self.load_svg_with_antialiasing(icon_path, QSize(28, 28))
                icon_rect = QRect(452, 98, 28, 28)
                painter.drawPixmap(icon_rect, icon_pixmap)
                st_text_rect = QRect(290, 90, 202, 44)

            frame_type = self.card_data.get("frameType", "").upper()

            # Scaled font for non-capitalized letters
            scale_factor = 0.85
            scaled_font = QFont(self.fonts.get("main_font"), base_font.pointSizeF() * scale_factor, QFont.Bold)

            # Larger font for brackets
            bracket_scale = 1.10
            bracket_font = QFont(self.fonts.get("main_font"), base_font.pointSizeF() * bracket_scale, QFont.Bold)

            # Font metrics
            base_metrics = QFontMetrics(base_font)
            scaled_metrics = QFontMetrics(scaled_font)
            bracket_metrics = QFontMetrics(bracket_font)

            # Text components
            left_bracket = "["
            right_bracket = "]"
            ft_first = frame_type[0] if frame_type else ""
            ft_rest = frame_type[1:] if len(frame_type) > 1 else ""
            space = " "
            card_first = "C"
            card_rest = "ARD"
            padding = text_padding

            # Measure widths
            w_left_bracket = bracket_metrics.horizontalAdvance(left_bracket)
            w_ft_first = base_metrics.horizontalAdvance(ft_first)
            w_ft_rest = scaled_metrics.horizontalAdvance(ft_rest)
            w_space = base_metrics.horizontalAdvance(space)
            w_card_first = base_metrics.horizontalAdvance(card_first)
            w_card_rest = scaled_metrics.horizontalAdvance(card_rest)
            w_padding = base_metrics.horizontalAdvance(padding)
            w_right_bracket = bracket_metrics.horizontalAdvance(right_bracket)

            total_width = (w_left_bracket + w_ft_first + w_ft_rest +
                           w_space + w_card_first + w_card_rest +
                           w_padding + w_right_bracket)

            start_x = st_text_rect.x() + (st_text_rect.width() - total_width) / 2
            base_baseline = st_text_rect.y() + (st_text_rect.height() + base_metrics.ascent() - base_metrics.descent()) / 2

            current_x = start_x

            # Draw left bracket (larger font)
            painter.setFont(bracket_font)
            painter.drawText(current_x, base_baseline, left_bracket)
            current_x += w_left_bracket

            # Draw frame type (first letter full size, rest smaller)
            painter.setFont(base_font)
            painter.drawText(current_x, base_baseline, ft_first)
            current_x += w_ft_first

            painter.setFont(scaled_font)
            painter.drawText(current_x, base_baseline, ft_rest)
            current_x += w_ft_rest

            # Draw space
            painter.setFont(base_font)
            painter.drawText(current_x, base_baseline, space)
            current_x += w_space

            # Draw "CARD" (first letter full size, rest smaller)
            painter.setFont(base_font)
            painter.drawText(current_x, base_baseline, card_first)
            current_x += w_card_first

            painter.setFont(scaled_font)
            painter.drawText(current_x, base_baseline, card_rest)
            current_x += w_card_rest

            # Draw optional padding
            painter.setFont(base_font)
            painter.drawText(current_x, base_baseline, padding)
            current_x += w_padding

            # Draw right bracket (larger font)
            painter.setFont(bracket_font)
            painter.drawText(current_x, base_baseline, right_bracket)

    def _draw_attribute(self, painter: QPainter) -> None:
        """Draw the attribute icon on the card."""
        frame_type = self.card_data.get("frameType", "").lower()
        if frame_type in ("trap", "spell"):
            attribute_text = frame_type
            ext_attr = "svg"
        else:
            attribute_text = self.card_data.get("attribute", "")
            ext_attr = "png"
        attribute_path = self._get_path(f"assets/card/attribute/{attribute_text.lower()}.{ext_attr}")
        attribute_pixmap = QPixmap(attribute_path)
        if not attribute_pixmap.isNull():
            attribute_rect = QRect(458, 36, 55, 55)
            scaled_attribute = attribute_pixmap.scaled(attribute_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x_offset = attribute_rect.x() + (attribute_rect.width() - scaled_attribute.width()) // 2
            y_offset = attribute_rect.y() + (attribute_rect.height() - scaled_attribute.height()) // 2
            painter.drawPixmap(x_offset, y_offset, scaled_attribute)

    def _draw_typeline(self, painter: QPainter) -> None:
        """Draw the typeline with mixed font sizes."""
        card_type = self.card_data.get("type", "")
        if card_type in ("Spell Card", "Trap Card"):
            return

        typeline_rect = QRect(40, 600, 420, 30)
        x = typeline_rect.x()
        font_size = 15
        font_percentage = 0.85
        front_font_offset = 1

        front_font = QFont(self.fonts.get("main_font"), font_size + front_font_offset, QFont.Bold)
        full_font = QFont(self.fonts.get("main_font"), font_size, QFont.Bold)
        small_font = QFont(self.fonts.get("main_font"), int(font_size * font_percentage), QFont.Bold)
        fm_full = QFontMetrics(full_font)
        baseline = typeline_rect.y() + (typeline_rect.height() + fm_full.ascent() - fm_full.descent()) // 2

        painter.setFont(front_font)
        painter.drawText(x, baseline, "[")
        x += QFontMetrics(full_font).horizontalAdvance("[")

        typeline_words = self.card_data.get("typeline", [])
        for i, word in enumerate(typeline_words):
            if word:
                first_letter = word[0].upper()
                painter.setFont(full_font)
                painter.drawText(x, baseline, first_letter)
                x += QFontMetrics(full_font).horizontalAdvance(first_letter)
                if len(word) > 1:
                    rest = word[1:].upper()
                    painter.setFont(small_font)
                    painter.drawText(x, baseline, rest)
                    x += QFontMetrics(small_font).horizontalAdvance(rest)
            if i < len(typeline_words) - 1:
                separator = "/"
                painter.setFont(front_font)
                painter.drawText(x, baseline, separator)
                x += QFontMetrics(full_font).horizontalAdvance(separator)
        painter.setFont(front_font)
        painter.drawText(x, baseline, "]")

    def _draw_description(self, painter: QPainter, pendulum: bool) -> None:
        """Draw the card description (or pendulum-specific description if applicable)."""
        card_type = self.card_data.get("type", "")
        offset_desc = 25 if card_type in ("Spell Card", "Trap Card") else 0
        offset_desc2 = 40 if card_type in ("Spell Card", "Trap Card") else 0
        desc_rect = QRect(42, 628 - offset_desc, 465, 99 + offset_desc2)
        if pendulum:
            pend_desc_rect = QRect(84, 506, 380, 85)
            self.draw_fitted_description(
                painter,
                pend_desc_rect,
                self.card_data.get("pend_desc", "No description available."),
                max_font_size=12,
                min_font_size=8,
            )
            self.draw_fitted_description(
                painter,
                desc_rect,
                self.card_data.get("monster_desc", "No description available."),
                max_font_size=12,
                min_font_size=9,
            )
        else:
            self.draw_fitted_description(
                painter,
                desc_rect,
                self.card_data.get("desc", "No description available."),
                max_font_size=12,
                min_font_size=9,
            )

    def drawStretchedTextStats(self, painter, rect, text, alignment=Qt.AlignRight):
        """
        Draws the given text in the specified rect by dynamically adjusting the font size
        so that the text fills the rect horizontally (and vertically if needed).
        """
        # Save painter state
        painter.save()

        # Get the current font as the base font.
        base_font = painter.font()
        fm = QFontMetrics(base_font)
        text_width = fm.horizontalAdvance(text)

        # If for some reason text width is zero, just draw normally.
        if text_width <= 0:
            painter.drawText(rect, alignment, text)
            painter.restore()
            return

        # Calculate the scale factor to match the rect width.
        scale_factor = rect.width() / text_width

        # Adjust the font size based on the scale factor.
        new_font_size = base_font.pointSizeF() * scale_factor
        new_font = QFont(base_font)
        new_font.setPointSizeF(new_font_size)
        painter.setFont(new_font)

        # Check if the new font's height exceeds the rect height.
        new_fm = QFontMetrics(new_font)
        if new_fm.height() > rect.height():
            # Scale down further if needed.
            vertical_scale = rect.height() / new_fm.height()
            new_font_size *= vertical_scale
            new_font.setPointSizeF(new_font_size)
            painter.setFont(new_font)

        # Draw the text with the updated font.
        painter.drawText(rect, alignment, text)

        # Restore the painter's state.
        painter.restore()

    def _draw_stats(self, painter: QPainter, link: bool) -> None:
        # Set the base font for your card design.
        painter.setFont(QFont(self.fonts.get("title_font"), 23.5))

        # Draw the "ATK/" label.
        atk_stats_text = "ATK/"
        atk_stats_rect = QRect(293, 731, 50, 30)
        painter.drawText(atk_stats_rect, Qt.AlignLeft, atk_stats_text)

        # Get the attack value.
        atk = self.card_data.get("atk", "")
        if atk == -1:
            atk = "?"
        atk_val_rect = QRect(336, 731, 58, 21.5) # 329
        self.drawStretchedTextStats(painter, atk_val_rect, str(atk), Qt.AlignRight)

        # If the card isn't a LINK card, do the same for DEF.
        if not link:
            painter.setFont(QFont(self.fonts.get("title_font"), 23.5))
            deff = self.card_data.get("def", "")
            if deff == -1:
                deff = "?"
            def_stats_text = "DEF/"
            def_stats_rect = QRect(399, 731, 110, 30)
            painter.drawText(def_stats_rect, Qt.AlignLeft, def_stats_text)
            def_val_rect = QRect(444, 731, 58, 21.5) #435
            self.drawStretchedTextStats(painter, def_val_rect, str(deff), Qt.AlignRight)

        else:
            painter.setFont(QFont(self.fonts.get("link_font"), 16.5))
            painter.drawText(QRect(400, 726, 87, 27), Qt.AlignCenter, "LINK")
            painter.drawText(QRect(464, 724, 27, 27), Qt.AlignCenter, "-")
            painter.setFont(QFont(self.fonts.get("link_font"), 16.2))
            link_rating = str(self.card_data.get("linkval", ""))
            link_rect = QRect(480, 726, 27, 27)
            painter.drawText(link_rect, Qt.AlignCenter, link_rating)

    def _draw_pendulum_scales(self, painter: QPainter) -> None:
        """Draw the pendulum scales on the card."""
        pend_scale_text = str(self.card_data.get("scale", ""))
        left_rect = QRect(43, 550, 27, 38)
        right_rect = QRect(477, 550, 27, 38)

        font = QFont(self.fonts.get("title_font"), 34, QFont.Bold)
        # If there are exactly two characters, reduce the spacing between them
        if len(pend_scale_text) == 2:
            font.setLetterSpacing(QFont.PercentageSpacing, 70)  # Adjust the value as needed
            left_rect = QRect(40, 550, 27, 38)
            right_rect = QRect(475, 550, 27, 38)

        painter.setFont(font)
        painter.drawText(left_rect, Qt.AlignCenter, pend_scale_text)
        painter.drawText(right_rect, Qt.AlignCenter, pend_scale_text)

    def _draw_separator(self, painter: QPainter) -> None:
        """Draw a separator line near the bottom of the card."""
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        painter.drawLine(45, 728, 505, 728)

    def _draw_extra(self, painter: QPainter) -> None:
        """Draws the extra limitation texts with the provided painter,
        squishing the text horizontally to fit the designated QRects."""
        painter.save()
        card_type = self.card_data.get("frameType", "").lower()
        fill_color = QColor(255, 255, 255) if card_type == "xyz" else QColor(0, 0, 0)

        # Helper function to draw text with horizontal squish if needed.
        def draw_squished_text(text: str, rect: QRect, base_font: QFont, alignment=Qt.AlignLeft):
            # Create a copy of the base font so we don't modify the original.
            font = QFont(base_font)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(text)
            # Only squash if the text is too wide.
            if text_width > rect.width() and text_width > 0:
                # Calculate a new stretch percentage (default is 100).
                new_stretch = int(100 * rect.width() / text_width)
                font.setStretch(new_stretch)
            painter.setFont(font)
            painter.drawText(rect, alignment, text)

        show_limits = self.flags.get("show_limitations", False)

        # Draw the Set-ID String.
        if self.setId and self.flags.get("show_limitations_setid", False):
            set_rect = QRect(382, 574, 108, 20)  # Default QRect.
            if card_type == "link":
                set_rect = QRect(346, 574, 108, 20)
            if "pendulum" in card_type:
                set_rect = QRect(44, 730, 108, 20)
            font = QFont(self.fonts.get("main_font"), 13, QFont.Normal)
            painter.setPen(fill_color)
            draw_squished_text(self.setId, set_rect, font, Qt.AlignLeft)

        # Draw the Passcode.
        if self.passcode and self.flags.get("show_limitations_passcode", False):
            passcode_rect = QRect(21, 761, 90, 20)
            font = QFont(self.fonts.get("main_font"), 13, QFont.Normal)
            painter.setPen(fill_color)
            draw_squished_text(self.passcode, passcode_rect, font, Qt.AlignLeft)

        # Draw Edition.
        if self.edition and self.edition != "Unlimited Edition" and self.flags.get("show_limitations_edition", False):
            edition_text = self.edition
            if self.edition.lower() == "limited edition":
                edition_text = "LIMITED EDITION"
            edition_rect = QRect(110, 761, 140, 20)
            font = QFont(self.fonts.get("main_font"), 13, QFont.DemiBold)
            painter.setPen(fill_color)
            draw_squished_text(edition_text, edition_rect, font, Qt.AlignLeft)

        # Draw Copyright.
        if self.flags.get("show_limitations_copyright", False):
            if not self.copyright:
                self.copyright = "©2020 Studio Dice/SHUEISHA, TV TOKYO, KONAMI"
            copyright_rect = QRect(270, 761, 236, 20)
            font = QFont(self.fonts.get("main_font"), 13, QFont.Thin)
            painter.setPen(fill_color)
            draw_squished_text(self.copyright, copyright_rect, font, Qt.AlignLeft)

        if self.flags.get("show_limitations_sticker", False):
            # Draw the Sticker for Eye of Anubis (Currently Proxy Style)
            rect = QRect(506, 755, 32, 32)
            # Choose the fill color: set use_gold based on your condition.
            if self.edition and self.edition != "Unlimited Edition":
                use_gold = True
            else:
                use_gold = False
            fill_color = QColor(255, 215, 0) if use_gold else QColor(192, 192, 192)

            painter.setBrush(fill_color)
            # Optionally, set the pen. Qt.NoPen avoids drawing a border.
            painter.setPen(Qt.NoPen)
            # Draw the rounded square; the last two parameters are the x and y radii for the rounded corners.
            painter.drawRoundedRect(rect, 5, 5)

        painter.restore()

    def _draw_card_content(self, painter: QPainter):  # NEW METHOD: Encapsulates all drawing
        """Draws all the card content using the provided painter."""
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.VerticalSubpixelPositioning)

        self._draw_background(painter)  # Important: Decide if background should be drawn for transparency

        frame_type = self.card_data.get("frameType", "").lower()
        pendulum = "pendulum" in frame_type
        link = frame_type == "link"

        self._draw_card_art(painter, pendulum)
        if pendulum:
            self._draw_pendulum_frame(painter)
        if link:
            self._draw_link_arrows(painter)

        self._draw_card_name(painter)
        self._draw_level_and_rank_stars(painter)
        self._draw_spell_trap_text(painter)
        self._draw_attribute(painter)
        self._draw_typeline(painter)
        self._draw_description(painter, pendulum)

        if self.card_data.get("type", "") not in ("Spell Card", "Trap Card"):
            self._draw_stats(painter, link)
            self._draw_separator(painter)

        if pendulum:
            self._draw_pendulum_scales(painter)

        # Draw Extra
        self._draw_extra(painter)

    def paintEvent(self, event: Any) -> None:
        """
        Main paint event handler that composes all parts of the card.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        self._draw_card_content(painter) # Call the new method
        painter.end()


    def render_to_pixmap(self, width: int, height: int) -> QPixmap:
        """
        Renders the card content to a QPixmap of the specified size.
        """
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent) # Important: Make background transparent initially

        painter = QPainter(pixmap)
        self._draw_card_content(painter) # Reuse the same drawing logic
        painter.end()
        return pixmap

    def save_card_to_file(self, filename: str, width: int, height: int) -> bool:
        """
        Renders the card to a QPixmap and saves it to a file.
        Returns True if successful, False otherwise.
        """
        pixmap = self.render_to_pixmap(width, height)
        return pixmap.save(filename, "PNG")  # PNG format supports transparency


class OverlayServer(QTcpServer):
    def __init__(self, main_window, rootpath ,args=None):
        super().__init__(main_window)
        self.args = args
        self.main_window = main_window
        self.newConnection.connect(self.handle_new_connection)
        self.buffers = {}
        self.rootpath = rootpath

    @Slot()
    def handle_new_connection(self):
        client_connection = self.nextPendingConnection()
        # Initialize a buffer for the new connection
        self.buffers[client_connection] = b""
        client_connection.readyRead.connect(self.read_client)
        client_connection.disconnected.connect(lambda: self.buffers.pop(client_connection, None))

    def read_client(self):
        socket = self.sender()
        if socket is None:
            return

        # Read new data and convert the QByteArray to bytes.
        new_data = socket.readAll()
        self.buffers[socket] += bytes(new_data)

        try:
            # Convert buffered bytes to a string and try to decode JSON.
            data_str = self.buffers[socket].decode("utf-8").strip()
            data = json.loads(data_str)
        except json.decoder.JSONDecodeError:
            # Incomplete JSON, wait for more data.
            return

        # Clear the buffer for this socket since we've processed the message.
        self.buffers[socket] = b""

        frame_type = "Default"
        card_pix = QPixmap("Default.png")

        if data.get("status") == "NewCard":
            background_path = "default.png.none"  # Ensure this image is 549x800
            card_data = data.get("card_data", "")
            card_data = json.loads(card_data)
            image_path = data.get("card_image", "")
            frame_type = card_data.get("frameType", "Default")

            # Extra Args
            set_string = data.get("set_string", "")
            edition = data.get("edition", "")
            passcode = data.get("passcode", "")

            extra_args = {
                "set_string": set_string,
                "edition": edition,
                "passcode": passcode
                          }

            card_widget = CardMakerWidget(card_data,
                                          background_path,
                                          base_path=os.path.join(self.rootpath ,"painted"),
                                          image_path=image_path,
                                          extra_args=extra_args,
                                          flags=self.args
                                          )

            # Define the desired dimensions and filename
            output_width = 549
            output_height = 800
            card_pix = card_widget.render_to_pixmap(output_width, output_height)

        # Write ACK and disconnect immediately.
        socket.write(b"ACK")
        socket.disconnectFromHost()

        # Schedule the overlay update after the network event is fully processed.
        QTimer.singleShot(0, lambda: self.main_window.set_overlay_custom(frame=frame_type, card_pixmap=card_pix))


class AnimatedWebPLabel(QLabel):
    def __init__(self, parent=None, initial_opacity=1.0):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.frames = []
        self.current_frame = 0

        # Set up the opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(initial_opacity)  # Start with given opacity

        # Create an animation for opacity changes
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(1000)  # Default duration (ms)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Internal flag to manage fade out state
        self._is_fading_out = False

    def adjust_hue(self, image, hue):
        """
        Adjust the hue of the given PIL image.

        Parameters:
            image (PIL.Image): The image to adjust.
            hue (float): The hue shift in degrees (-180 to +180).

        Returns:
            PIL.Image: The hue-adjusted image (alpha resets).
        """
        # Convert hue from degrees (-180 to +180) to a shift on a 0–255 scale.
        shift = int((hue / 360.0) * 255)
        hsv = image.convert("HSV")
        h, s, v = hsv.split()
        np_h = np.array(h, dtype=np.uint8)
        # Shift hue values with wrap-around
        np_h = (np_h.astype(int) + shift) % 256
        new_h = Image.fromarray(np_h.astype("uint8"), "L")
        hsv = Image.merge("HSV", (new_h, s, v))
        return hsv.convert("RGBA")

    def adjust_frame(self, frame, hue, saturation, brightness=0, region=None):
        """
        Adjust the hue, saturation, and brightness of the frame while preserving non-opaque pixels
        outside the specified region.

        Parameters:
            frame (PIL.Image): An RGBA image.
            hue (float): Hue shift in degrees.
            saturation (float): Saturation factor (1.0 means no change).
            brightness (float): Brightness adjustment (-150 to 150; 0 means no change).
            region (tuple or None): Optional (x, y, width, height) region to apply adjustments.

        Returns:
            PIL.Image: The adjusted image.
        """
        if region:
            x, y, w, h = region
            region_box = (x, y, x + w, y + h)
            # Crop the region to modify.
            orig_region = frame.crop(region_box)
            mod_region = orig_region.copy()

            if hue != 0.0:
                mod_region = self.adjust_hue(mod_region, hue)
            if saturation != 1.0:
                enhancer = ImageEnhance.Color(mod_region)
                mod_region = enhancer.enhance(saturation)
            if brightness != 0:
                enhancer = ImageEnhance.Brightness(mod_region)
                factor = 1.0 + (brightness / 150.0)
                mod_region = enhancer.enhance(factor)

            # Convert cropped region to arrays to preserve translucency.
            orig_arr = np.array(orig_region)
            mod_arr = np.array(mod_region)
            # Create a mask for pixels that are not fully opaque.
            translucent_mask = (orig_arr[:, :, 3] < 255)
            # For translucent pixels, revert to the original values.
            mod_arr[translucent_mask] = orig_arr[translucent_mask]
            mod_region = Image.fromarray(mod_arr, "RGBA")
            # Paste the modified region back onto the original frame.
            frame.paste(mod_region, region_box)
            return frame
        else:
            # Adjust the entire frame.
            orig = frame.copy()
            mod = frame
            if hue != 0.0:
                mod = self.adjust_hue(mod, hue)
            if saturation != 1.0:
                enhancer = ImageEnhance.Color(mod)
                mod = enhancer.enhance(saturation)
            if brightness != 0:
                enhancer = ImageEnhance.Brightness(mod)
                factor = 1.0 + (brightness / 150.0)
                mod = enhancer.enhance(factor)
            orig_arr = np.array(orig)
            mod_arr = np.array(mod)
            # Preserve pixels that were originally transparent.
            transparent_mask = (orig_arr[:, :, 3] == 0)
            mod_arr[transparent_mask] = orig_arr[transparent_mask]
            return Image.fromarray(mod_arr, "RGBA")

    def apply_gradient(self, frame):
        """
        Apply a vertical gradient over a 100-pixel band in the middle of the frame.
        Pixels above the band become fully transparent and within the band the alpha channel
        is linearly interpolated from 0 (transparent) to 1 (opaque), while pixels below the band remain opaque.

        Parameters:
            frame (PIL.Image): An RGBA image.

        Returns:
            PIL.Image: The image with the gradient applied.
        """
        width, height = frame.size
        frame_arr = np.array(frame)

        # Define the gradient band (100 pixels tall, centered vertically)
        gradient_band_height = 100
        start_y = (height - gradient_band_height) // 2
        end_y = start_y + gradient_band_height

        # Create a 1D mask for each row.
        mask = np.ones((height,), dtype=np.float32)
        mask[:start_y] = 0.0  # Above the band: fully transparent.
        # Create a linear gradient within the band: from transparent (0.0) to opaque (1.0)
        mask[start_y:end_y] = np.linspace(0.0, 1.0, gradient_band_height, endpoint=True)
        mask[end_y:] = 1.0  # Below the band: fully opaque.

        # Expand the mask to the full image width.
        mask = np.tile(mask[:, None], (1, width))

        # Apply the mask to the original alpha channel.
        original_alpha = frame_arr[..., 3].astype(np.float32)
        new_alpha = (original_alpha * mask).astype(np.uint8)
        frame_arr[..., 3] = new_alpha

        return Image.fromarray(frame_arr, "RGBA")

    def set_webp(self, webp_path, hue=0.0, saturation=1.0, brightness=0, region=None, gradient=False):
        """
        Load an animated WebP, convert its frames to QPixmap, and optionally adjust hue, saturation, brightness,
        and apply a gradient effect.

        Parameters:
            webp_path (str): Path to the WebP file.
            hue (float): Hue shift in degrees (-180 to +180; 0 means no change).
            saturation (float): Saturation factor (1.0 means no change).
            brightness (float): Brightness adjustment (-150 to 150; 0 means no change).
            region (tuple or None): Optional (x, y, width, height) region to apply hue/saturation/brightness adjustments.
            gradient (bool): If True, apply a vertical gradient to fade the top half of each frame to transparent.
        """
        self.frames = []
        self.current_frame = 0
        image = Image.open(webp_path)
        try:
            while True:
                frame = image.convert("RGBA")
                if hue != 0.0 or saturation != 1.0 or brightness != 0:
                    frame = self.adjust_frame(frame, hue, saturation, brightness, region)
                if gradient:
                    frame = self.apply_gradient(frame)
                width, height = frame.size
                qimage = QImage(frame.tobytes(), width, height, QImage.Format_RGBA8888)
                self.frames.append(QPixmap.fromImage(qimage))
                image.seek(image.tell() + 1)
        except EOFError:
            pass

        # Start cycling frames immediately if visible.
        self.timer.start(42)  # ~24 FPS
        self.update_frame()

    def update_frame(self):
        if self.frames:
            self.setPixmap(self.frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def next_frame(self):
        self.update_frame()

    def fade_in(self, duration=500):
        """Animate the label to become fully opaque and restart frame cycling."""
        self.fade_animation.stop()
        # Reset frame index and restart timer.
        self.current_frame = 0
        self.timer.start(42)
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

    def fade_out(self, duration=500):
        """Animate the label to become fully transparent and stop frame cycling after fading."""
        self.fade_animation.stop()
        self._is_fading_out = True
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(0.0)
        # Connect to the finished signal to stop the timer after fade-out completes.
        self.fade_animation.finished.connect(self._on_fade_out_finished)
        self.fade_animation.start()

    def _on_fade_out_finished(self):
        if self._is_fading_out:
            self.timer.stop()
            self._is_fading_out = False
        try:
            self.fade_animation.finished.disconnect(self._on_fade_out_finished)
        except Exception:
            pass

    def set_opacity(self, opacity):
        """Immediately set the label's opacity without animation."""
        self.fade_animation.stop()
        self.opacity_effect.setOpacity(opacity)


class AnimatedAPNGLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.frames = []
        self.current_frame = 0

    def set_apng(self, apng_path):
        self.frames = []
        self.current_frame = 0
        with imageio.get_reader(apng_path) as reader:
            for frame in reader:
                image = np.array(frame)
                height, width, channels = image.shape
                if channels == 4:
                    q_image = QImage(image.data, width, height, 4 * width, QImage.Format_RGBA8888)
                else:
                    q_image = QImage(image.data, width, height, 3 * width, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image)
                self.frames.append(pixmap)
        self.timer.start(42)  # ~24 FPS
        self.update_frame()

    def update_frame(self):
        if self.frames:
            self.setPixmap(self.frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def next_frame(self):
        self.update_frame()

    def restart(self):
        self.current_frame = 0
        self.update_frame()


class MainWindow(QMainWindow):
    def __init__(self, args=None):
        super().__init__()
        version = "0.1.0"
        self.setWindowTitle(f"Yu-Gi-Oh! NFC Card Viewer v{version} - By SideswipeeZ")
        self.ico = QIcon(os.path.join(self.getRootPath(), "logo.png"))
        self.setWindowIcon(self.ico)
        self.tray_icon = QSystemTrayIcon(self.ico, self)

        self.setGeometry(100, 100, 549, 800)
        self.setFixedSize(549, 800)
        self.port = args.get("port")

        self.args = args

        self.rootpath = self.getRootPath()

        full_rect = QRect(0, 0, 549, 800)
        card_main_border = (17, 17, 522, 768)

        # -- Hues and Saturation --
        hue_normal = 30.0
        hue_ritual = -159.0
        hue_fusion = -108.0
        hue_trap = -44
        sat_main = 0.8
        sat_normal = 0.8
        sat_fusion = 0.8
        sat_ritual = 0.8
        bright_synchro = 120

        self.active_border = "token"

        card_border_webp = self.get_asset_path("Card_Border")
        main_webp = self.get_asset_path("Main")
        spell_webp = self.get_asset_path("spell")
        link_webp = self.get_asset_path("LINK")
        xyz_webp = self.get_asset_path("XYZ")
        art_frame = self.get_asset_path("art_frame")

        # --- Build Card Background Elements (New Code) ---
        # Border
        self.webp_border_label = AnimatedWebPLabel(self)
        self.webp_border_label.set_webp(card_border_webp)
        self.webp_border_label.setGeometry(full_rect)

        # Main Image Variants

        self.webp_main_token_label = AnimatedWebPLabel(self, initial_opacity=1.0)
        self.webp_main_token_label.set_webp(main_webp, saturation=0.0, region=card_main_border)
        self.webp_main_token_label.setGeometry(full_rect)

        self.webp_main_spell_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_spell_label.set_webp(spell_webp, region=card_main_border)
        self.webp_main_spell_label.setGeometry(full_rect)

        self.webp_main_trap_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_trap_label.set_webp(main_webp, hue=hue_trap, region=card_main_border)
        self.webp_main_trap_label.setGeometry(full_rect)

        self.webp_main_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_label.set_webp(main_webp, saturation=sat_main)
        self.webp_main_label.setGeometry(full_rect)

        self.webp_main_normal_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_normal_label.set_webp(main_webp, hue=hue_normal, saturation=sat_normal ,region=card_main_border)
        self.webp_main_normal_label.setGeometry(full_rect)

        self.webp_main_ritual_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_ritual_label.set_webp(main_webp, hue=hue_ritual, saturation=sat_ritual, region=card_main_border)
        self.webp_main_ritual_label.setGeometry(full_rect)

        self.webp_main_fusion_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_fusion_label.set_webp(main_webp, hue=hue_fusion, saturation=sat_fusion, region=card_main_border)
        self.webp_main_fusion_label.setGeometry(full_rect)

        self.webp_main_synchro_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_synchro_label.set_webp(main_webp, saturation=0.0, brightness=bright_synchro, region=card_main_border)
        self.webp_main_synchro_label.setGeometry(full_rect)

        # LINK and XYZ variants
        self.webp_link_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_link_label.set_webp(link_webp)
        self.webp_link_label.setGeometry(full_rect)

        self.webp_xyz_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_xyz_label.set_webp(xyz_webp)
        self.webp_xyz_label.setGeometry(full_rect)

        # Pendulum variant
        self.webp_main_pendulum_label = AnimatedWebPLabel(self, initial_opacity=0.0)
        self.webp_main_pendulum_label.set_webp(spell_webp, region=card_main_border, gradient=True)
        self.webp_main_pendulum_label.setGeometry(full_rect)

        # Art Border, Description, and Title (Non-Pendulum)
        self.webp_artframe_label = AnimatedWebPLabel(self)
        self.webp_artframe_label.set_webp(art_frame)
        self.webp_artframe_label.setGeometry(full_rect)

        self.webp_desc_label = AnimatedWebPLabel(self)
        self.webp_desc_label.set_webp(os.path.join(self.rootpath,'all_card/card_desc_box.png'))
        self.webp_desc_label.setGeometry(full_rect)

        self.webp_title_label = AnimatedWebPLabel(self)
        self.webp_title_label.set_webp(os.path.join(self.rootpath,'all_card/title_box.png'))
        self.webp_title_label.setGeometry(full_rect)

        # --- Overlay Transition (Original Code) ---
        # PNG overlay with opacity effect.
        self.overlay = QLabel(self)
        self.overlay.setGeometry(full_rect)
        self.overlay.setAttribute(Qt.WA_TranslucentBackground)

        self.opacity_effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(350)
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Transition APNG overlay.
        self.transition_overlay = AnimatedAPNGLabel(self)
        self.transition_overlay.set_apng(os.path.join(self.rootpath,'transition.apng'))
        self.transition_overlay.setGeometry(full_rect)
        self.transition_overlay.setVisible(False)

        # Sound effect for transitions.
        self.transition_sound = QSoundEffect(self)
        self.transition_sound.setSource(QUrl.fromLocalFile(os.path.join(self.rootpath,"AudioTransitionCardSFX.wav")))
        self.transition_sound.setVolume(1.0)  # 100% volume

        # --- TCP Server ---
        self.server = OverlayServer(self, args=self.args, rootpath=self.rootpath)
        port = self.port  # Change port as needed.
        if not self.server.listen(QHostAddress.Any, port):
            print(f"Server could not start on port {port}")
        else:
            print(f"Server listening on port {port}")

        self.show()

    def getRootPath(self, extended=False):
        """
        Gets the appropriate root path depending on whether the app is running
        from PyInstaller bundle or directly.

        Parameters:
        extended (bool): If True, returns current working directory even when bundled

        Returns:
        str: Path to use as root for accessing resources
        """
        try:
            if sys._MEIPASS and not extended:
                return sys._MEIPASS
            else:
                return os.getcwd()
        except AttributeError:
            return os.getcwd()

    def get_asset_path(self, asset_name):
        """
        Returns the full path of the asset.
        If the 'static' flag is passed in self.args, only PNG is used.
        Otherwise, it first tries WebP, then falls back to PNG.
        """
        # Determine the extension order based on the 'static' flag.
        if self.args and self.args.get("static", False):
            ext_order = ['png']
        else:
            ext_order = ['webp', 'png']

        for ext in ext_order:
            candidate = os.path.join(self.rootpath, f'all_card/{asset_name}.{ext}')
            if os.path.exists(candidate):
                return candidate
        raise FileNotFoundError(f"Asset {asset_name} not found as either {', '.join(['.' + ext for ext in ext_order])}")

    def get_border_widget(self, border):
        if border == "spell":
            return self.webp_main_spell_label
        elif border == "trap":
            return self.webp_main_trap_label
        elif border.startswith("xyz"):
            return self.webp_xyz_label
        elif border.startswith("fusion"):
            return self.webp_main_fusion_label
        elif border.startswith("normal"):
            return self.webp_main_normal_label
        elif border.startswith("effect"):
            return self.webp_main_label
        elif border.startswith("ritual"):
            return self.webp_main_ritual_label
        elif border.startswith("link"):
            return self.webp_link_label
        elif border.startswith("synchro"):
            return self.webp_main_synchro_label
        return None

    def fade_border(self, border, fade_method, duration):
        widget = self.get_border_widget(border)
        if widget:
            # Call fade_in or fade_out on the widget based on fade_method.
            getattr(widget, fade_method)(duration)

    def set_overlay_custom(self, frame, card_pixmap):
        """
        Changes the overlay image using the same fade and transition animation.
        """
        fadeout_duration = 250
        fadein_duration = 500

        # Fade out the currently active border.
        self.fade_border(self.active_border, "fade_out", fadeout_duration)
        if "_pendulum" in self.active_border:
            self.webp_main_pendulum_label.fade_out(fadeout_duration)
            self.webp_desc_label.fade_in(fadein_duration)
            self.webp_artframe_label.fade_in(fadein_duration)

        # Update active border.
        self.active_border = frame

        # Fade in the new active border.
        self.fade_border(self.active_border, "fade_in", fadein_duration)
        if "_pendulum" in self.active_border:
            self.webp_main_pendulum_label.fade_in(fadein_duration)
            self.webp_desc_label.fade_out(fadeout_duration)
            self.webp_artframe_label.fade_out(fadeout_duration)


        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.start()

        self.transition_overlay.setVisible(True)
        self.transition_overlay.restart()

        # Play the transition sound effect.
        self.transition_sound.play()

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._update_overlay(card_pixmap))
        timer.start(350)

        loop = QEventLoop()
        QTimer.singleShot(375, loop.quit)
        loop.exec()

        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()

        self.transition_overlay.setVisible(False)

    def _update_overlay(self, image_path):
        self.overlay.setPixmap(image_path)


def parse_args():
    parser = argparse.ArgumentParser(description="Card Viewer Args.")

    # Optional flags for showing limitations
    parser.add_argument('--show-limitations-setid', action='store_true', help="Show limitations based on Set ID")
    parser.add_argument('--show-limitations-passcode', action='store_true', help="Show limitations based on Passcode")
    parser.add_argument('--show-limitations-copyright', action='store_true', help="Show limitations based on Copyright")
    parser.add_argument('--show-limitations-sticker', action='store_true', help="Show limitations based on Sticker")
    parser.add_argument('--show-limitations-edition', action='store_true', help="Show limitations based on Edition")
    parser.add_argument('--static', action='store_true', help="Load the static background version of the app.")
    parser.add_argument('--port', type=int, default=41112, help="Specify the port number, (Default Port= 41112)")

    # New font override options
    parser.add_argument('--title_font', type=str, help="Override title font")
    parser.add_argument('--lore_font', type=str, help="Override lore font")
    parser.add_argument('--main_font', type=str, help="Override main font")
    parser.add_argument('--link_font', type=str, help="Override link font")

    args = parser.parse_args()

    # Return arguments as a dictionary
    return vars(args)


def resource_path(relative_path):
    """
    Get absolute path to resource, works for development and PyInstaller packaged app.
    """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS.
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    try:
        # This is to add the icon to the Taskbar while running in an IDE (Windows).
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ygocardview.app.sideswipe')
    except Exception:
        pass

    # Parse the command line arguments
    args_dict = parse_args()

    # Initialize the QApplication
    app = QApplication(sys.argv)

    # --- Create and show the splash screen ---
    splash_pix = QPixmap(resource_path("splash1.png"))
    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()  # Ensure the splash screen displays immediately

    # Optionally update the splash screen message
    splash.showMessage("Initializing...", alignment=Qt.AlignBottom | Qt.AlignCenter, color=Qt.white)

    # --- Initialize your MainWindow ---
    # This is where your heavy initialization happens.
    window = MainWindow(args_dict)
    # Once the main window is fully loaded, close the splash screen.
    splash.finish(window)
    # Start the application
    sys.exit(app.exec())
