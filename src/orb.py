"""Floating purple mic orb (PyQt6). Frameless, translucent, always-on-top, no
taskbar button. Left-click records/stops; a hover button shows Abrir/Cancelar;
right-click opens a menu. Drag to move (clamped to the screen)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QRectF
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient, QBrush,
                         QPen, QRegion, QGuiApplication, QPainterPath, QFont, QPixmap)
from PyQt6.QtWidgets import QWidget, QPushButton, QMenu

import paths
import theme
import controller as C

W, H = 120, 118
ORB_D = 60
ORB_CX = W // 2
ORB_CY = H - 6 - ORB_D // 2     # center from top
ORB_R = ORB_D // 2


class Orb(QWidget):
    def __init__(self, ctrl: C.Controller, open_window, open_settings, quit_app):
        super().__init__()
        self.ctrl = ctrl
        self.open_window = open_window
        self.open_settings = open_settings
        self.quit_app = quit_app
        self._level = 0.0
        self._ring = 0.0
        self._drag_origin = None
        self._press_global = None
        self._moved = False
        # The Socius mark (the Ü) shown as the orb face — brand always present.
        self._mark = QPixmap(paths.app_icon())

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            # Never take focus (WS_EX_NOACTIVATE): clicking the orb must leave the
            # caret in the user's app so Ctrl+V lands there, like the Mac app.
            | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(W, H)
        self.setMouseTracking(True)

        self.btn = QPushButton("Abrir", self)
        self.btn.setGeometry(4, 4, W - 8, 28)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._menu_clicked)
        self.btn.setStyleSheet(
            "QPushButton{color:white;background:rgba(10,10,14,200);border:1px solid "
            "rgba(255,255,255,20);border-radius:14px;font-size:12px;font-weight:600;"
            "padding:0 10px;}"
            "QPushButton:hover{background:rgba(10,10,14,235);}")
        self.btn.hide()

        # Grace period before hiding the hover button, so brief exits don't hide it.
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(400)
        self._hide_timer.timeout.connect(self._hide_btn_if_away)

        self._ring_timer = QTimer(self)
        self._ring_timer.timeout.connect(self._tick_ring)

        ctrl.state_changed.connect(self._on_state)
        ctrl.level_changed.connect(self._on_level)

        self._place_bottom_right()
        self._apply_mask()

    # ---- placement ----
    def _place_bottom_right(self):
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - W - 16, geo.bottom() - H + 6)

    def _apply_mask(self):
        # No window mask on purpose. A mask is 1-bit (jagged edges), and on Windows
        # every setMask() resets mouse tracking -> spurious leaveEvent -> the hover
        # button flickers/hides. The translucent (layered) window already lets clicks
        # through fully transparent pixels; paintEvent draws a near-invisible bridge
        # between orb and button while it's shown so the hover isn't lost.
        self.update()

    def _bridge_rect(self) -> QRect:
        b = self.btn.geometry()
        return QRect(ORB_CX - ORB_R, b.top(), ORB_D, ORB_CY - b.top())

    # ---- state / level ----
    def _menu_open(self) -> bool:
        return self.ctrl.state in (C.RECORDING, C.TRANSCRIBING)

    def _on_state(self, s: str):
        if s in (C.RECORDING, C.TRANSCRIBING):
            self.btn.setText("Cancelar")
            self.btn.show()
        else:
            if not self.underMouse():
                self.btn.hide()
            else:
                self.btn.setText("Abrir")
        if s == C.TRANSCRIBING:
            self._ring = 0.0
            self._ring_timer.start(30)
        else:
            self._ring_timer.stop()
        self._apply_mask()
        self.update()

    def _on_level(self, lv: float):
        self._level = lv
        if self.ctrl.state == C.RECORDING:
            self.update()

    def _tick_ring(self):
        self._ring = (self._ring + 12) % 360
        self.update()

    # ---- hover ----
    def enterEvent(self, e):
        self._hide_timer.stop()
        if not self._menu_open():
            self.btn.setText("Abrir")
        self.btn.show()
        self._apply_mask()

    def leaveEvent(self, e):
        if not self._menu_open():
            self._hide_timer.start()

    def _hide_btn_if_away(self):
        if self._menu_open() or self.underMouse() or self.btn.underMouse():
            return
        self.btn.hide()
        self._apply_mask()

    def _menu_clicked(self):
        self.ctrl.menu_action()

    # ---- mouse: click vs drag ----
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_global = e.globalPosition().toPoint()
            self._drag_origin = self.frameGeometry().topLeft()
            self._moved = False
        elif e.button() == Qt.MouseButton.RightButton:
            self._context_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press_global is None:
            return
        delta = e.globalPosition().toPoint() - self._press_global
        if abs(delta.x()) + abs(delta.y()) > 4:
            self._moved = True
            self.move(self._clamp(self._drag_origin + delta))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            if not self._moved and self._in_orb(e.position().toPoint()):
                self.ctrl.primary_tap()
            self._press_global = None

    def _in_orb(self, p: QPoint) -> bool:
        dx, dy = p.x() - ORB_CX, p.y() - ORB_CY
        return dx * dx + dy * dy <= ORB_R * ORB_R

    def _clamp(self, pos: QPoint) -> QPoint:
        geo = QGuiApplication.primaryScreen().geometry()
        x, y = pos.x(), pos.y()
        # keep the orb circle fully on screen
        min_x = geo.left() - (ORB_CX - ORB_R)
        max_x = geo.right() + 1 - (ORB_CX + ORB_R)
        min_y = geo.top() - (ORB_CY - ORB_R)
        max_y = geo.bottom() + 1 - (ORB_CY + ORB_R)
        return QPoint(max(min_x, min(x, max_x)), max(min_y, min(y, max_y)))

    def _context_menu(self, gpos):
        m = QMenu(self)
        if self._menu_open():
            m.addAction("Cancelar", self.ctrl.cancel)
        m.addAction("Abrir ventana", self.open_window)
        m.addAction("Ajustes", self.open_settings)
        m.addSeparator()
        m.addAction("Salir", self.quit_app)
        m.exec(gpos)

    # ---- painting ----
    def _base_color(self) -> QColor:
        s = self.ctrl.state
        if s == C.RECORDING:
            return QColor(theme.RECORDING)
        if s == C.DONE:
            return QColor(theme.SUCCESS)
        if s == C.COPIED_ONLY:
            return QColor(theme.WARNING)
        if s == C.ERROR:
            return QColor(theme.RECORDING)
        return QColor(config_purple())

    def _ring_color(self) -> QColor:
        s = self.ctrl.state
        if s == C.RECORDING:
            return QColor(theme.RECORDING)
        if s == C.DONE:
            return QColor(theme.SUCCESS)
        if s == C.COPIED_ONLY:
            return QColor(theme.WARNING)
        if s == C.ERROR:
            return QColor(theme.RECORDING)
        if s == C.TRANSCRIBING:
            c = QColor(config_purple()); c.setAlpha(90); return c
        c = QColor("white"); c.setAlpha(40); return c   # calm idle rim

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.btn.isVisible():   # alpha 1: invisible, but hit-testable (keeps hover)
            p.fillRect(self._bridge_rect(), QColor(0, 0, 0, 1))

        scale = 1.0 + (self._level * 0.16 if self.ctrl.state == C.RECORDING else 0.0)
        d = ORB_D * scale
        rect = QRectF(ORB_CX - d / 2, ORB_CY - d / 2, d, d)

        # No drop shadow: the window is transparent, so any shadow outside the orb
        # smears onto the desktop. Depth comes only from the inner light rim below.

        # Face: indigo circle (the mark's own background) with the Socius mark at
        # 75% size, centered — so the smaller Ü blends seamlessly.
        p.save()
        clip = QPainterPath(); clip.addEllipse(rect); p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#3B3293")); p.drawEllipse(rect)
        if not self._mark.isNull():
            md = d * 0.75
            p.drawPixmap(QRectF(rect.center().x() - md / 2, rect.center().y() - md / 2, md, md).toRect(),
                         self._mark)
        else:
            base = self._base_color()
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor(theme.adjust(base.name(), 0.10)))
            grad.setColorAt(0.55, base)
            grad.setColorAt(1.0, QColor(theme.NEAR_BLACK))
            p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(rect)
        p.restore()

        # Light-catching top rim.
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, 70)); rim.setColorAt(1.0, QColor(255, 255, 255, 8))
        pen = QPen(QBrush(rim), 1); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        # State ring.
        rc = self._ring_color()
        is_feedback = self.ctrl.state in (C.DONE, C.COPIED_ONLY, C.ERROR, C.RECORDING)
        p.setPen(QPen(rc, 3 if is_feedback else 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect.adjusted(1.5, 1.5, -1.5, -1.5))

        # Transcribing: spinning arc on top.
        if self.ctrl.state == C.TRANSCRIBING:
            pen = QPen(QColor(theme.adjust(config_purple(), 0.35)), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(rect.adjusted(1.5, 1.5, -1.5, -1.5), int(-self._ring * 16), int(100 * 16))

        self._draw_badge(p)

    def _draw_badge(self, p: QPainter):
        """Small corner badge for the brief done / copied / error moments — the Ü
        mark stays visible underneath."""
        s = self.ctrl.state
        spec = {C.DONE: ("check", QColor(theme.SUCCESS)),
                C.COPIED_ONLY: ("copy", QColor(theme.WARNING)),
                C.ERROR: ("bang", QColor(theme.RECORDING))}.get(s)
        if not spec:
            return
        kind, color = spec
        bx, by, br = ORB_CX + ORB_R - 6, ORB_CY + ORB_R - 6, 9
        p.save()
        p.setPen(QPen(QColor(255, 255, 255, 235), 1.5)); p.setBrush(color)
        p.drawEllipse(QRectF(bx - br, by - br, br * 2, br * 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if kind == "check":
            pen = QPen(QColor("white"), 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); p.setPen(pen)
            path = QPainterPath(); path.moveTo(bx - 4, by); path.lineTo(bx - 1, by + 3); path.lineTo(bx + 4, by - 3)
            p.drawPath(path)
        elif kind == "copy":
            pen = QPen(QColor("white"), 1.6); p.setPen(pen)
            p.drawRoundedRect(QRectF(bx - 3, by - 4, 5, 6), 1, 1)
            p.drawRoundedRect(QRectF(bx - 1, by - 2, 5, 6), 1, 1)
        else:  # bang
            f = QFont(); f.setPixelSize(12); f.setBold(True); p.setFont(f); p.setPen(QColor("white"))
            p.drawText(QRectF(bx - br, by - br, br * 2, br * 2), Qt.AlignmentFlag.AlignCenter, "!")
        p.restore()


def config_purple() -> str:
    import config
    return config.get("purple_hex") or theme.PURPLE


def toggle_visibility(orb: "Orb"):
    orb.hide() if orb.isVisible() else orb.show()
