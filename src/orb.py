"""Floating purple mic orb (PyQt6). Frameless, translucent, always-on-top, no
taskbar button. Left-click records/stops; a hover button shows Abrir/Cancelar;
right-click opens a menu. Drag to move (clamped to the screen)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QRectF
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient, QBrush,
                         QPen, QRegion, QGuiApplication, QPainterPath, QFont)
from PyQt6.QtWidgets import QWidget, QPushButton, QMenu

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

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(W, H)
        self.setMouseTracking(True)

        self.btn = QPushButton("Abrir", self)
        self.btn.setGeometry(4, 4, W - 8, 28)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._menu_clicked)
        self.btn.setStyleSheet(
            "QPushButton{color:white;background:rgba(0,0,0,180);border:none;"
            "border-radius:14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:rgba(0,0,0,220);}")
        self.btn.hide()

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
        region = QRegion(ORB_CX - ORB_R, ORB_CY - ORB_R, ORB_D, ORB_D, QRegion.RegionType.Ellipse)
        if self.btn.isVisible():
            region = region.united(QRegion(self.btn.geometry()))
        self.setMask(region)

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
        if not self._menu_open():
            self.btn.setText("Abrir")
        self.btn.show()
        self._apply_mask()

    def leaveEvent(self, e):
        if not self._menu_open():
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

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = self._base_color()
        scale = 1.0 + (self._level * 0.16 if self.ctrl.state == C.RECORDING else 0.0)
        d = ORB_D * scale
        rect = QRectF(ORB_CX - d / 2, ORB_CY - d / 2, d, d)

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(theme.adjust(base.name(), 0.10)))
        grad.setColorAt(0.55, base)
        grad.setColorAt(1.0, QColor(theme.NEAR_BLACK))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect)

        sheen = QRadialGradient(rect.center().x() - d * 0.18, rect.center().y() - d * 0.22, d * 0.6)
        c = QColor(theme.adjust(base.name(), 0.22)); c.setAlpha(120)
        sheen.setColorAt(0.0, c); sheen.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(sheen)); p.drawEllipse(rect)

        if self.ctrl.state == C.TRANSCRIBING:
            pen = QPen(QColor(theme.adjust(base.name(), 0.4)), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            rr = QRectF(ORB_CX - ORB_R + 5, ORB_CY - ORB_R + 5, ORB_D - 10, ORB_D - 10)
            p.drawArc(rr, int(-self._ring * 16), int(100 * 16))

        self._draw_icon(p, QColor("white"))

    def _draw_icon(self, p: QPainter, color: QColor):
        s = self.ctrl.state
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        cx, cy = ORB_CX, ORB_CY
        if s == C.RECORDING:                      # stop square
            p.drawRoundedRect(QRectF(cx - 7, cy - 7, 14, 14), 3, 3)
        elif s == C.DONE:                          # check
            pen = QPen(color, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(); path.moveTo(cx - 7, cy); path.lineTo(cx - 2, cy + 6); path.lineTo(cx + 8, cy - 6)
            p.drawPath(path)
        elif s == C.ERROR:
            f = QFont(); f.setPixelSize(20); f.setBold(True); p.setFont(f); p.setPen(color)
            p.drawText(QRectF(cx - 10, cy - 13, 20, 26), Qt.AlignmentFlag.AlignCenter, "!")
        else:                                       # mic
            p.drawRoundedRect(QRectF(cx - 5, cy - 11, 10, 15), 5, 5)
            pen = QPen(color, 2); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - 8, cy - 6, 16, 14), 200 * 16, 140 * 16)
            p.setPen(QPen(color, 2)); p.drawLine(cx, cy + 7, cx, cy + 11)
            p.drawLine(cx - 4, cy + 11, cx + 4, cy + 11)
        p.restore()


def config_purple() -> str:
    import config
    return config.get("purple_hex") or theme.PURPLE


def toggle_visibility(orb: "Orb"):
    orb.hide() if orb.isVisible() else orb.show()
