"""
dxf_kernel.py
-------------
Kernel CAD interattivo per editing DXF.
- Apre un DXF con backup automatico
- Rendering zoomabile e pannable su QGraphicsScene
- Click su entità → selezione
- Pannello destro: cambio layer (con aggiunta nuovi) e colore ACI
- Tasto Salva
"""

import sys
import shutil
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.backend import BackendInterface

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
    QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QInputDialog, QFileDialog,
    QSplitter, QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QPainterPath, QTransform
)
from PyQt6.QtCore import Qt, QRectF, QPointF

import math

# ---------------------------------------------------------------------------
# Colori ACI standard DXF (indice → QColor)
# ---------------------------------------------------------------------------

ACI_COLORS = {
    1:  QColor(255, 0, 0),       # rosso
    2:  QColor(255, 255, 0),     # giallo
    3:  QColor(0, 255, 0),       # verde
    4:  QColor(0, 255, 255),     # ciano
    5:  QColor(0, 0, 255),       # blu
    6:  QColor(255, 0, 255),     # magenta
    7:  QColor(255, 255, 255),   # bianco
    8:  QColor(128, 128, 128),   # grigio scuro
    9:  QColor(192, 192, 192),   # grigio chiaro
    10: QColor(255, 0, 0),
    20: QColor(255, 127, 0),
    30: QColor(255, 165, 0),
    40: QColor(255, 255, 0),
    50: QColor(127, 255, 0),
    60: QColor(0, 255, 0),
    70: QColor(0, 255, 127),
    80: QColor(0, 255, 255),
    90: QColor(0, 127, 255),
    140: QColor(0, 0, 255),
    150: QColor(127, 0, 255),
    160: QColor(255, 0, 255),
    170: QColor(255, 0, 127),
    256: QColor(200, 200, 200),  # BYLAYER
}

# ---------------------------------------------------------------------------
# Conversione entità DXF → QPainterPath
# ---------------------------------------------------------------------------

def arc_path(entity):
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r  = entity.dxf.radius
    sa = entity.dxf.start_angle
    ea = entity.dxf.end_angle
    path = QPainterPath()
    rect = QRectF(cx - r, -(cy + r), 2 * r, 2 * r)
    span = ea - sa
    if span <= 0:
        span += 360
    path.arcMoveTo(rect, sa)
    path.arcTo(rect, sa, span)
    return path


def entity_to_path(entity):
    """Converte un'entità DXF in QPainterPath. Restituisce None se non supportata."""
    t = entity.dxftype()
    path = QPainterPath()

    if t == 'LINE':
        s = entity.dxf.start
        e = entity.dxf.end
        path.moveTo(s.x, -s.y)
        path.lineTo(e.x, -e.y)
        return path

    elif t == 'ARC':
        return arc_path(entity)

    elif t == 'CIRCLE':
        cx = entity.dxf.center.x
        cy = entity.dxf.center.y
        r  = entity.dxf.radius
        path.addEllipse(QPointF(cx, -cy), r, r)
        return path

    elif t == 'LWPOLYLINE':
        points = list(entity.get_points('xyb'))
        if not points:
            return None
        path.moveTo(points[0][0], -points[0][1])
        for i in range(len(points) - 1):
            x0, y0, bulge = points[i]
            x1, y1, _ = points[i + 1]
            if bulge == 0:
                path.lineTo(x1, -y1)
            else:
                # arco da bulge
                _add_bulge_arc(path, x0, y0, x1, y1, bulge)
        if entity.closed and len(points) > 1:
            x0, y0, bulge = points[-1]
            x1, y1, _ = points[0]
            if bulge == 0:
                path.lineTo(x1, -y1)
            else:
                _add_bulge_arc(path, x0, y0, x1, y1, bulge)
            path.closeSubpath()
        return path

    elif t == 'SPLINE':
        try:
            pts = list(entity.flattening(0.5))
            if len(pts) < 2:
                return None
            path.moveTo(pts[0][0], -pts[0][1])
            for p in pts[1:]:
                path.lineTo(p[0], -p[1])
            return path
        except Exception:
            return None

    return None


def _add_bulge_arc(path, x0, y0, x1, y1, bulge):
    """Aggiunge un arco bulge al QPainterPath."""
    try:
        angle = 4 * math.atan(abs(bulge))
        d = math.hypot(x1 - x0, y1 - y0)
        if d == 0:
            return
        r = d / (2 * math.sin(angle / 2))
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        dx = x1 - x0
        dy = y1 - y0
        px = -dy / d
        py = dx / d
        sign = 1 if bulge > 0 else -1
        h = math.sqrt(max(r * r - (d / 2) ** 2, 0))
        cx = mx + sign * h * px
        cy = my + sign * h * py
        sa = math.degrees(math.atan2(y0 - cy, x0 - cx))
        ea = math.degrees(math.atan2(y1 - cy, x1 - cx))
        span = ea - sa
        if bulge > 0 and span < 0:
            span += 360
        elif bulge < 0 and span > 0:
            span -= 360
        rect = QRectF(cx - r, -(cy + r), 2 * r, 2 * r)
        path.arcTo(rect, sa, span)
    except Exception:
        path.lineTo(x1, -y1)


# ---------------------------------------------------------------------------
# Item grafico selezionabile
# ---------------------------------------------------------------------------

class DxfItem(QGraphicsPathItem):
    def __init__(self, entity, path, color):
        super().__init__(path)
        self.entity = entity
        self.base_color = color
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPen(QPen(color, 0))
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor(255, 200, 0), 0))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.isSelected():
            self.setPen(QPen(self.base_color, 0))
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setPen(QPen(QColor(255, 200, 0), 0))
            else:
                self.setPen(QPen(self.base_color, 0))
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# Vista zoomabile
# ---------------------------------------------------------------------------

class CadView(QGraphicsView):
    def __init__(self, scene, on_select):
        super().__init__(scene)
        self.on_select = on_select
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            item = self.itemAt(event.pos())
            if isinstance(item, DxfItem):
                self.scene().clearSelection()
                item.setSelected(True)
                self.on_select(item)
            else:
                self.scene().clearSelection()
                self.on_select(None)
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Finestra principale
# ---------------------------------------------------------------------------

class DxfKernel(QMainWindow):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = Path(filepath)
        self.selected_item = None

        # Backup automatico
        bak = self.filepath.with_suffix('.bak')
        if not bak.exists():
            shutil.copy2(self.filepath, bak)

        # Carica DXF
        self.doc = ezdxf.readfile(str(self.filepath))
        self.msp = self.doc.modelspace()

        self.setWindowTitle(f"DXF Kernel — {self.filepath.name}")
        self.resize(1400, 800)

        self._build_ui()
        self._render()

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Scena + vista
        self.scene = QGraphicsScene()
        self.view = CadView(self.scene, self._on_select)

        # Pannello destro
        right = QWidget()
        right.setFixedWidth(260)
        right.setStyleSheet("background: #1e1e2e; color: #cdd6f4;")
        rl = QVBoxLayout(right)
        rl.setSpacing(8)

        # Info entità selezionata
        self.info_label = QLabel("Nessuna entità selezionata")
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 4px;")
        self.info_label.setWordWrap(True)
        rl.addWidget(self.info_label)

        rl.addWidget(self._separator())

        # Layer
        rl.addWidget(QLabel("Layer:"))
        self.layer_list = QListWidget()
        self.layer_list.setStyleSheet("""
            QListWidget { background: #313244; border: none; }
            QListWidget::item:selected { background: #89b4fa; color: #1e1e2e; }
            QListWidget::item:hover { background: #45475a; }
        """)
        self.layer_list.setMaximumHeight(200)
        self.layer_list.itemClicked.connect(self._apply_layer)
        rl.addWidget(self.layer_list)

        btn_add_layer = QPushButton("+ Nuovo layer")
        btn_add_layer.setStyleSheet(self._btn_style())
        btn_add_layer.clicked.connect(self._add_layer)
        rl.addWidget(btn_add_layer)

        rl.addWidget(self._separator())

        # Colori ACI
        rl.addWidget(QLabel("Colore ACI:"))
        color_grid = QWidget()
        color_grid.setStyleSheet("background: #313244; padding: 4px;")
        grid = QGridLayout(color_grid)
        grid.setSpacing(3)
        self._color_buttons = {}
        aci_list = list(ACI_COLORS.items())
        cols = 5
        for i, (aci, qcolor) in enumerate(aci_list):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {qcolor.name()};
                    border: 2px solid #45475a;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid #cdd6f4;
                }}
            """)
            btn.setToolTip(f"ACI {aci}")
            btn.clicked.connect(lambda checked, a=aci: self._apply_color(a))
            grid.addWidget(btn, i // cols, i % cols)
            self._color_buttons[aci] = btn
        rl.addWidget(color_grid)

        rl.addWidget(self._separator())

        # Tasto elimina
        btn_delete = QPushButton("🗑 Elimina entità")
        btn_delete.setStyleSheet(self._btn_style("#e06c75"))
        btn_delete.clicked.connect(self._delete_entity)
        rl.addWidget(btn_delete)

        rl.addStretch()

        # Salva
        btn_save = QPushButton("💾 Salva DXF")
        btn_save.setStyleSheet(self._btn_style("#a6e3a1"))
        btn_save.clicked.connect(self._save)
        rl.addWidget(btn_save)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.view)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        layout.addWidget(splitter)

    def _separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #45475a;")
        return sep

    def _btn_style(self, color="#89b4fa"):
        return f"""
            QPushButton {{
                background: {color};
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.85; }}
        """

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def _render(self):
        self.scene.clear()
        self._items = []

        layers = set()

        for entity in self.msp:
            path = entity_to_path(entity)
            if path is None:
                continue

            color = self._entity_color(entity)
            item = DxfItem(entity, path, color)
            self.scene.addItem(item)
            self._items.append(item)

            layer = entity.dxf.layer if entity.dxf.hasattr('layer') else '0'
            layers.add(layer)

        # Popola lista layer
        self.layer_list.clear()
        for layer in sorted(layers):
            self.layer_list.addItem(layer)

        # Fit view
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _entity_color(self, entity):
        aci = entity.dxf.color if entity.dxf.hasattr('color') else 256
        return ACI_COLORS.get(aci, QColor(200, 200, 200))

    # -----------------------------------------------------------------------
    # Selezione
    # -----------------------------------------------------------------------

    def _on_select(self, item):
        self.selected_item = item
        if item is None:
            self.info_label.setText("Nessuna entità selezionata")
        else:
            e = item.entity
            layer = e.dxf.layer if e.dxf.hasattr('layer') else '0'
            color = e.dxf.color if e.dxf.hasattr('color') else 256
            self.info_label.setText(
                f"Tipo: {e.dxftype()}\nLayer: {layer}\nColore ACI: {color}"
            )

    # -----------------------------------------------------------------------
    # Azioni
    # -----------------------------------------------------------------------

    def _apply_layer(self, list_item):
        if self.selected_item is None:
            return
        new_layer = list_item.text()
        self.selected_item.entity.dxf.layer = new_layer
        self._on_select(self.selected_item)

    def _add_layer(self):
        name, ok = QInputDialog.getText(self, "Nuovo layer", "Nome layer:")
        if ok and name.strip():
            name = name.strip()
            # Aggiunge al doc se non esiste
            if name not in self.doc.layers:
                self.doc.layers.new(name)
            # Aggiunge alla lista se non c'è
            existing = [self.layer_list.item(i).text()
                        for i in range(self.layer_list.count())]
            if name not in existing:
                self.layer_list.addItem(name)

    def _apply_color(self, aci):
        if self.selected_item is None:
            return
        self.selected_item.entity.dxf.color = aci
        new_color = ACI_COLORS.get(aci, QColor(200, 200, 200))
        self.selected_item.base_color = new_color
        self.selected_item.setPen(QPen(QColor(255, 200, 0), 0))  # resta selezionato
        self._on_select(self.selected_item)

    def _delete_entity(self):
        if self.selected_item is None:
            return
        entity = self.selected_item.entity
        self.msp.delete_entity(entity)
        self.scene.removeItem(self.selected_item)
        self._items.remove(self.selected_item)
        self.selected_item = None
        self.info_label.setText("Nessuna entità selezionata")

    def _save(self):
        self.doc.saveas(str(self.filepath))
        self.setWindowTitle(f"DXF Kernel — {self.filepath.name} ✓ salvato")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def open_kernel(filepath=None):
    app = QApplication.instance() or QApplication(sys.argv)
    if filepath is None:
        filepath, _ = QFileDialog.getOpenFileName(
            None, "Apri DXF", "", "DXF Files (*.dxf *.DXF)"
        )
        if not filepath:
            return
    win = DxfKernel(filepath)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    open_kernel(path)
