import sys
import os
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QAction, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsItem, QGraphicsTextItem, QGraphicsRectItem,
    QTreeWidget, QTreeWidgetItem, QDockWidget, QInputDialog, QMessageBox, QToolBar,
    QLabel, QLineEdit, QPushButton, QColorDialog, QFontDialog, QSlider, QHBoxLayout,
    QWidget, QVBoxLayout, QGraphicsEllipseItem, QDialog, QSpinBox, QComboBox, QCheckBox,
    QPlainTextEdit, QUndoStack, QUndoCommand, QAbstractItemView, QListWidget, QTreeWidgetItemIterator
)
from PyQt5.QtGui import (
    QPixmap, QImage, QTransform, QPainter, QColor, QFont, QCursor, QPen, QBrush, QIcon,
    QWheelEvent, QDoubleValidator, QMouseEvent, QTextCursor, QTextBlockFormat, QKeySequence
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QBuffer, QIODevice, QThread, pyqtSignal, QObject, QTimer,
    QLineF, QEvent, QItemSelectionModel, QMimeData
)
from PIL import Image, ImageEnhance, ImageFilter
from rembg import remove
from io import BytesIO

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 日志处理器，用于将日志输出到GUI
class GuiLogger(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)

# 线程类用于去除背景
class RemoveBackgroundThread(QThread):
    finished = pyqtSignal(QPixmap, object)
    error = pyqtSignal(str)

    def __init__(self, pixmap, item):
        super().__init__()
        self.pixmap = pixmap
        self.item = item

    def run(self):
        try:
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            self.pixmap.save(buffer, "PNG")
            input_bytes = buffer.data().data()

            logging.debug(f"开始去除背景，图层: {self.item.layer_name}")

            # 使用 rembg 去除背景
            output_bytes = remove(input_bytes)
            output_image = Image.open(BytesIO(output_bytes)).convert("RGBA")

            # 转换回QPixmap
            data = output_image.tobytes("raw", "RGBA")
            qimage = QImage(data, output_image.width, output_image.height, QImage.Format_RGBA8888)
            output_pixmap = QPixmap.fromImage(qimage)

            self.finished.emit(output_pixmap, self.item)
        except Exception as e:
            logging.error(f"背景去除失败: {e}")
            self.error.emit(str(e))

# 自定义图层类型，支持选中时显示边框和拖动缩放
class ResizableGraphicsPixmapItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, layer_name):
        super().__init__(pixmap)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.layer_name = layer_name
        self.setCursor(Qt.OpenHandCursor)
        self.locked = False  # 图层锁定状态
        self.rotation_center = self.boundingRect().center()
        self.rotation_angle = 0
        self.setTransformOriginPoint(self.rotation_center)
        self.scale_factor = 1.0
        self.show_border = True  # 底图边框显示开关

    def hoverMoveEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.OpenHandCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.layer_name == "底图" and self.show_border:
            # 绘制底图边框
            pen = QPen(Qt.blue, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())
        if self.isSelected():
            pen = QPen(Qt.red, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    # 添加 render 方法以支持图层合并
    def render(self, painter, option=None, widget=None):
        super().paint(painter, option, widget)

# 自定义文字图层
class ResizableGraphicsTextItem(QGraphicsTextItem):
    def __init__(self, text, layer_name):
        super().__init__(text)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges |
            QGraphicsItem.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.layer_name = layer_name
        font = QFont("Microsoft YaHei", 20)
        self.setFont(font)
        self.setDefaultTextColor(Qt.black)
        self.setCursor(Qt.IBeamCursor)
        self.locked = False  # 图层锁定状态
        self.rotation_center = self.boundingRect().center()
        self.rotation_angle = 0
        self.setTransformOriginPoint(self.rotation_center)
        self.scale_factor = 1.0
        self.background_color = QColor(255, 255, 255, 0)  # 默认背景透明

    def hoverMoveEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.IBeamCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.ClosedHandCursor)
            self.setFocus()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.locked:
            self.setCursor(Qt.IBeamCursor)
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # 失去焦点后更新文本内容
        self.update()

    def paint(self, painter, option, widget):
        # 绘制背景
        painter.setBrush(QBrush(self.background_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)

    def set_background_color(self, color):
        self.background_color = color
        self.update()

    def setPixmap(self, pixmap):
        # 文字图层不支持直接设置pixmap，但为了兼容画笔工具，需要此方法
        pass

    # 添加 render 方法以支持图层合并
    def render(self, painter, option=None, widget=None):
        super().paint(painter, option, widget)

# 裁剪覆盖层
class CropOverlay(QGraphicsRectItem):
    handleSize = +8.0
    handleSpace = -4.0
    handleCursors = {
        0: Qt.SizeFDiagCursor,  # Top-left
        1: Qt.SizeVerCursor,    # Top-center
        2: Qt.SizeBDiagCursor,  # Top-right
        3: Qt.SizeHorCursor,    # Center-left
        4: Qt.SizeHorCursor,    # Center-right
        5: Qt.SizeBDiagCursor,  # Bottom-left
        6: Qt.SizeVerCursor,    # Bottom-center
        7: Qt.SizeFDiagCursor,  # Bottom-right
    }

    def __init__(self, *args):
        super().__init__(*args)
        self.handles = {}
        self._handleSelected = None
        self._mousePressPos = None
        self._mousePressRect = None
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.updateHandlesPos()

    def boundingRect(self):
        o = self.handleSize + self.handleSpace
        return self.rect().adjusted(-o, -o, o, o)

    def updateHandlesPos(self):
        s = self.handleSize
        b = self.rect()
        self.handles[0] = QRectF(b.left(), b.top(), s, s)
        self.handles[1] = QRectF(b.center().x() - s / 2, b.top(), s, s)
        self.handles[2] = QRectF(b.right() - s, b.top(), s, s)
        self.handles[3] = QRectF(b.left(), b.center().y() - s / 2, s, s)
        self.handles[4] = QRectF(b.right() - s, b.center().y() - s / 2, s, s)
        self.handles[5] = QRectF(b.left(), b.bottom() - s, s, s)
        self.handles[6] = QRectF(b.center().x() - s / 2, b.bottom() - s, s, s)
        self.handles[7] = QRectF(b.right() - s, b.bottom() - s, s, s)

    def paint(self, painter, option, widget=None):
        # Draw rectangle
        painter.setPen(QPen(Qt.green, 2, Qt.DashLine))
        painter.drawRect(self.rect())

        # Draw handles
        painter.setPen(QPen(Qt.green))
        painter.setBrush(QBrush(Qt.green))
        for handle in self.handles.values():
            painter.drawRect(handle)

    def hoverMoveEvent(self, event):
        # Change cursor
        handle = self.handleAt(event.pos())
        if handle is not None:
            cursor = self.handleCursors[handle]
        else:
            cursor = Qt.SizeAllCursor
        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def handleAt(self, point):
        for k, rect in self.handles.items():
            if rect.contains(point):
                return k
        return None

    def mousePressEvent(self, event):
        self._handleSelected = self.handleAt(event.pos())
        if self._handleSelected is not None:
            self._mousePressPos = event.pos()
            self._mousePressRect = self.rect()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._handleSelected is not None:
            self.interactiveResize(event.pos())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._handleSelected = None
        super().mouseReleaseEvent(event)

    def interactiveResize(self, mousePos):
        offset = mousePos - self._mousePressPos
        rect = self.rect()
        if self._handleSelected == 0:  # Top-left
            rect.setTopLeft(rect.topLeft() + offset)
        elif self._handleSelected == 1:  # Top-center
            rect.setTop(rect.top() + offset.y())
        elif self._handleSelected == 2:  # Top-right
            rect.setTopRight(rect.topRight() + offset)
        elif self._handleSelected == 3:  # Center-left
            rect.setLeft(rect.left() + offset.x())
        elif self._handleSelected == 4:  # Center-right
            rect.setRight(rect.right() + offset.x())
        elif self._handleSelected == 5:  # Bottom-left
            rect.setBottomLeft(rect.bottomLeft() + offset)
        elif self._handleSelected == 6:  # Bottom-center
            rect.setBottom(rect.bottom() + offset.y())
        elif self._handleSelected == 7:  # Bottom-right
            rect.setBottomRight(rect.bottomRight() + offset)
        self.setRect(rect.normalized())
        self.updateHandlesPos()

# 旋转句柄
class RotationHandle(QGraphicsEllipseItem):
    def __init__(self, parent_item, parent_view):
        super().__init__(-5, -5, 10, 10)
        self.parent_item = parent_item
        self.parent_view = parent_view
        self.setBrush(QBrush(Qt.blue))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsScenePositionChanges)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(parent_item.zValue() + 1)  # 确保在父项之上显示

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            # 更新父项的旋转中心点
            scene_pos = new_pos
            local_pos = self.parent_item.mapFromScene(scene_pos)
            self.parent_item.setTransformOriginPoint(local_pos)
            # 更新属性面板中的坐标
            self.parent_view.parent.property_panel.update_rotation_center(self.parent_item)
            return new_pos
        return super().itemChange(change, value)

# 画笔工具
class BrushTool(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()

        # 颜色选择
        self.color_btn = QPushButton("颜色")
        self.color_btn.clicked.connect(self.choose_color)
        layout.addWidget(self.color_btn)
        self.current_color = QColor(Qt.black)
        self.color_btn.setStyleSheet("background-color: black;")

        # 画笔大小
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(5)
        layout.addWidget(QLabel("大小:"))
        layout.addWidget(self.size_slider)

        # 模式选择（绘画/擦除）
        self.mode_btn = QPushButton("模式: 绘画")
        self.mode = 'draw'
        self.mode_btn.clicked.connect(self.toggle_mode)
        layout.addWidget(self.mode_btn)

        self.setLayout(layout)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color
            self.color_btn.setStyleSheet(f"background-color: {color.name()};")

    def toggle_mode(self):
        if self.mode == 'draw':
            self.mode = 'erase'
            self.mode_btn.setText("模式: 擦除")
        else:
            self.mode = 'draw'
            self.mode_btn.setText("模式: 绘画")

# 调整对话框
class AdjustmentDialog(QDialog):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.setWindowTitle("调整图层")
        self.item = item
        self.resize(400, 500)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # 保存原始状态
        self.original_pixmap = None
        self.original_text = None
        self.preview_timer = None

        if isinstance(item, ResizableGraphicsPixmapItem):
            self.original_pixmap = item.pixmap()
            self.init_image_adjustments()
        elif isinstance(item, ResizableGraphicsTextItem):
            self.original_text = item.toHtml()
            self.init_text_adjustments()

    def init_image_adjustments(self):
        # 对比度
        contrast_label = QLabel("对比度")
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.update_preview)
        self.layout.addWidget(contrast_label)
        self.layout.addWidget(self.contrast_slider)

        # 亮度
        brightness_label = QLabel("亮度")
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 200)
        self.brightness_slider.setValue(100)
        self.brightness_slider.valueChanged.connect(self.update_preview)
        self.layout.addWidget(brightness_label)
        self.layout.addWidget(self.brightness_slider)

        # 饱和度
        saturation_label = QLabel("饱和度")
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 200)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(self.update_preview)
        self.layout.addWidget(saturation_label)
        self.layout.addWidget(self.saturation_slider)

        # 锐化
        sharpen_label = QLabel("锐化度")
        self.sharpen_slider = QSlider(Qt.Horizontal)
        self.sharpen_slider.setRange(0, 200)
        self.sharpen_slider.setValue(100)
        self.sharpen_slider.valueChanged.connect(self.update_preview)
        self.layout.addWidget(sharpen_label)
        self.layout.addWidget(self.sharpen_slider)

        # RGBA 调整
        rgba_label = QLabel("RGBA 调整")
        self.layout.addWidget(rgba_label)
        self.rgba_sliders = []
        for channel in ['R', 'G', 'B', 'A']:
            channel_label = QLabel(f"{channel}:")
            channel_slider = QSlider(Qt.Horizontal)
            channel_slider.setRange(0, 200)
            channel_slider.setValue(100)
            channel_slider.valueChanged.connect(self.update_preview)
            self.layout.addWidget(channel_label)
            self.layout.addWidget(channel_slider)
            self.rgba_sliders.append(channel_slider)

        # 曲线调整（伽马校正）
        gamma_label = QLabel("Gamma 调整")
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(10, 300)
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self.update_preview)
        self.layout.addWidget(gamma_label)
        self.layout.addWidget(self.gamma_slider)

        # 滤镜选择
        filter_label = QLabel("滤镜")
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("无")
        self.filter_combo.addItem("模糊")
        self.filter_combo.addItem("锐化")
        self.filter_combo.addItem("浮雕")
        self.filter_combo.currentIndexChanged.connect(self.update_preview)
        self.layout.addWidget(filter_label)
        self.layout.addWidget(self.filter_combo)

        # 按钮
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("确定")
        apply_btn.clicked.connect(self.apply_adjustments)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.cancel_adjustments)
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        self.layout.addLayout(button_layout)

    def init_text_adjustments(self):
        # 字体选择
        font_label = QLabel("字体:")
        self.layout.addWidget(font_label)
        font_button = QPushButton("选择字体")
        font_button.clicked.connect(self.choose_font)
        self.layout.addWidget(font_button)

        # 字体大小
        size_label = QLabel("字体大小:")
        self.layout.addWidget(size_label)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 500)
        point_size = self.item.font().pointSize()
        if point_size == -1:
            point_size = 12  # 默认字体大小
        self.size_spin.setValue(point_size)
        self.size_spin.valueChanged.connect(self.update_preview)
        self.layout.addWidget(self.size_spin)

        # 字体颜色
        color_label = QLabel("字体颜色:")
        self.layout.addWidget(color_label)
        self.color_button = QPushButton()
        self.color_button.setStyleSheet(f"background-color: {self.item.defaultTextColor().name()};")
        self.color_button.clicked.connect(self.choose_color)
        self.layout.addWidget(self.color_button)

        # 背景颜色
        bg_label = QLabel("背景颜色:")
        self.layout.addWidget(bg_label)
        self.bg_color_button = QPushButton()
        self.bg_color_button.setStyleSheet(f"background-color: {self.item.background_color.name()};")
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        self.layout.addWidget(self.bg_color_button)

        # 字体样式
        self.bold_check = QCheckBox("加粗")
        self.bold_check.setChecked(self.item.font().bold())
        self.bold_check.stateChanged.connect(self.update_preview)
        self.layout.addWidget(self.bold_check)

        self.italic_check = QCheckBox("斜体")
        self.italic_check.setChecked(self.item.font().italic())
        self.italic_check.stateChanged.connect(self.update_preview)
        self.layout.addWidget(self.italic_check)

        self.underline_check = QCheckBox("下划线")
        self.underline_check.setChecked(self.item.font().underline())
        self.underline_check.stateChanged.connect(self.update_preview)
        self.layout.addWidget(self.underline_check)

        # 对齐方式
        align_label = QLabel("对齐方式:")
        self.layout.addWidget(align_label)
        self.align_combo = QComboBox()
        self.align_combo.addItems(["左对齐", "居中对齐", "右对齐"])
        self.align_combo.currentIndexChanged.connect(self.update_preview)
        self.layout.addWidget(self.align_combo)

        # 按钮
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("确定")
        apply_btn.clicked.connect(self.apply_adjustments)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.cancel_adjustments)
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        self.layout.addLayout(button_layout)

    def update_preview(self):
        if isinstance(self.item, ResizableGraphicsPixmapItem):
            # 临时应用调整
            contrast = self.contrast_slider.value() / 100
            brightness = self.brightness_slider.value() / 100
            saturation = self.saturation_slider.value() / 100
            sharpen = self.sharpen_slider.value() / 100
            gamma = self.gamma_slider.value() / 100

            pil_image = self.qpixmap_to_pil(self.original_pixmap)

            # 调整亮度
            enhancer = ImageEnhance.Brightness(pil_image)
            pil_image = enhancer.enhance(brightness)

            # 调整对比度
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(contrast)

            # 调整饱和度
            enhancer = ImageEnhance.Color(pil_image)
            pil_image = enhancer.enhance(saturation)

            # 调整锐化
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(sharpen)

            # RGBA 调整
            rgba_values = [slider.value() / 100 for slider in self.rgba_sliders]
            r, g, b, a = pil_image.split()
            r = r.point(lambda i: i * rgba_values[0])
            g = g.point(lambda i: i * rgba_values[1])
            b = b.point(lambda i: i * rgba_values[2])
            a = a.point(lambda i: i * rgba_values[3])
            pil_image = Image.merge('RGBA', (r, g, b, a))

            # Gamma 调整
            pil_image = pil_image.point(lambda i: ((i / 255.0) ** (1 / gamma)) * 255)

            # 滤镜
            filter_name = self.filter_combo.currentText()
            if filter_name == "模糊":
                pil_image = pil_image.filter(ImageFilter.BLUR)
            elif filter_name == "锐化":
                pil_image = pil_image.filter(ImageFilter.SHARPEN)
            elif filter_name == "浮雕":
                pil_image = pil_image.filter(ImageFilter.EMBOSS)

            # 更新图层
            qimage = self.pil_image_to_qimage(pil_image)
            self.item.setPixmap(QPixmap.fromImage(qimage))

        elif isinstance(self.item, ResizableGraphicsTextItem):
            font = self.item.font()
            font.setPointSize(self.size_spin.value())
            font.setBold(self.bold_check.isChecked())
            font.setItalic(self.italic_check.isChecked())
            font.setUnderline(self.underline_check.isChecked())
            self.item.setFont(font)
            # 字体颜色
            self.item.setDefaultTextColor(self.item.defaultTextColor())
            # 背景颜色
            self.item.set_background_color(self.item.background_color)
            # 对齐方式
            alignment = self.align_combo.currentIndex()
            self.change_alignment(self.item, alignment)

    def apply_adjustments(self):
        self.accept()

    def cancel_adjustments(self):
        if isinstance(self.item, ResizableGraphicsPixmapItem):
            self.item.setPixmap(self.original_pixmap)
        elif isinstance(self.item, ResizableGraphicsTextItem):
            self.item.setHtml(self.original_text)
        self.reject()

    def choose_font(self):
        font, ok = QFontDialog.getFont(self.item.font())
        if ok:
            self.item.setFont(font)

    def choose_color(self):
        color = QColorDialog.getColor(self.item.defaultTextColor())
        if color.isValid():
            self.item.setDefaultTextColor(color)
            self.color_button.setStyleSheet(f"background-color: {color.name()};")

    def choose_bg_color(self):
        color = QColorDialog.getColor(self.item.background_color)
        if color.isValid():
            self.item.set_background_color(color)
            self.bg_color_button.setStyleSheet(f"background-color: {color.name()};")

    def qpixmap_to_pil(self, pixmap):
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        input_bytes = buffer.data().data()
        pil_image = Image.open(BytesIO(input_bytes)).convert("RGBA")
        return pil_image

    def pil_image_to_qimage(self, pil_image):
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
        return qimage

    def change_alignment(self, item, index):
        alignments = [Qt.AlignLeft, Qt.AlignCenter, Qt.AlignRight]
        alignment = alignments[index]
        # 创建文本块格式
        block_format = QTextBlockFormat()
        block_format.setAlignment(alignment)
        # 创建文本光标并应用格式
        cursor = item.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.mergeBlockFormat(block_format)
        item.setTextCursor(cursor)

# 属性面板
class PropertyPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)  # 传递父对象
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.parent = parent  # 引用父级 ImageEditor

        # 旋转中心相关
        self.rotation_center_size = 10  # 默认大小
        self.rotation_center_label = QLabel("旋转中心点大小:")
        self.rotation_center_slider = QSlider(Qt.Horizontal)
        self.rotation_center_slider.setRange(5, 50)
        self.rotation_center_slider.setValue(self.rotation_center_size)
        self.rotation_center_slider.valueChanged.connect(self.change_rotation_center_size)
        self.rotation_center_coord_label = QLabel("旋转中心点坐标: (0, 0)")
        self.rotation_center_x = QLineEdit("0")
        self.rotation_center_y = QLineEdit("0")
        self.rotation_center_x.setValidator(QDoubleValidator())
        self.rotation_center_y.setValidator(QDoubleValidator())
        self.rotation_center_x.editingFinished.connect(self.change_rotation_center_coord)
        self.rotation_center_y.editingFinished.connect(self.change_rotation_center_coord)

        # 旋转角度相关
        self.rotation_angle_label = QLabel("旋转角度:")
        self.rotation_angle_slider = QSlider(Qt.Horizontal)
        self.rotation_angle_slider.setRange(-180, 180)
        self.rotation_angle_slider.setValue(0)
        self.rotation_angle_slider.valueChanged.connect(self.change_rotation_angle)
        self.rotation_angle_input = QLineEdit("0")
        self.rotation_angle_input.setValidator(QDoubleValidator())
        self.rotation_angle_input.editingFinished.connect(self.change_rotation_angle_input)

    def update_properties(self, item):
        # 清空当前布局
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        if self.parent.crop_mode:
            # 裁剪模式下的控件
            crop_label = QLabel("裁剪操作")
            self.layout.addWidget(crop_label)

            confirm_btn = QPushButton("确认裁剪")
            confirm_btn.clicked.connect(self.parent.confirm_crop)
            self.layout.addWidget(confirm_btn)

            cancel_btn = QPushButton("取消裁剪")
            cancel_btn.clicked.connect(self.parent.cancel_crop)
            self.layout.addWidget(cancel_btn)
            return

        if not self.parent.rotate_btn.isChecked():
            # 如果不是旋转模式，更新为选中图层的属性
            if item is None:
                return

            try:
                if isinstance(item, ResizableGraphicsPixmapItem):
                    # 显示图像属性
                    size_label = QLabel(f"尺寸: {item.pixmap().width()} x {item.pixmap().height()}")
                    self.layout.addWidget(size_label)
                    opacity_label = QLabel("不透明度:")
                    self.layout.addWidget(opacity_label)
                    opacity_slider = QSlider(Qt.Horizontal)
                    opacity_slider.setRange(0, 100)
                    opacity_slider.setValue(int(item.opacity() * 100))
                    opacity_slider.valueChanged.connect(lambda val: item.setOpacity(val / 100))
                    self.layout.addWidget(opacity_slider)
                    # 底图边框显示开关
                    if item.layer_name == "底图":
                        border_check = QCheckBox("显示边框")
                        border_check.setChecked(item.show_border)
                        border_check.stateChanged.connect(lambda val: self.toggle_border(item, val))
                        self.layout.addWidget(border_check)

                elif isinstance(item, ResizableGraphicsTextItem):
                    # 显示文字属性
                    text_label = QLabel("文字内容:")
                    self.layout.addWidget(text_label)
                    text_edit = QLineEdit(item.toPlainText())
                    text_edit.textChanged.connect(item.setPlainText)
                    self.layout.addWidget(text_edit)

                    # 字体选择
                    font_label = QLabel("字体:")
                    self.layout.addWidget(font_label)
                    font_button = QPushButton("选择字体")
                    font_button.clicked.connect(lambda: self.choose_font(item))
                    self.layout.addWidget(font_button)

                    # 字体大小
                    size_label = QLabel("字体大小:")
                    self.layout.addWidget(size_label)
                    size_spin = QSpinBox()
                    size_spin.setRange(1, 500)
                    point_size = item.font().pointSize()
                    if point_size == -1:
                        point_size = 12  # 默认字体大小
                    size_spin.setValue(point_size)
                    size_spin.valueChanged.connect(lambda val: self.change_font_size(item, val))
                    self.layout.addWidget(size_spin)

                    # 字体颜色
                    color_label = QLabel("字体颜色:")
                    self.layout.addWidget(color_label)
                    color_button = QPushButton()
                    color_button.setStyleSheet(f"background-color: {item.defaultTextColor().name()};")
                    color_button.clicked.connect(lambda: self.choose_color(item, color_button))
                    self.layout.addWidget(color_button)

                    # 背景颜色
                    bg_label = QLabel("背景颜色:")
                    self.layout.addWidget(bg_label)
                    bg_color_button = QPushButton()
                    bg_color_button.setStyleSheet(f"background-color: {item.background_color.name()};")
                    bg_color_button.clicked.connect(lambda: self.choose_bg_color(item, bg_color_button))
                    self.layout.addWidget(bg_color_button)

                    # 字体样式
                    bold_check = QCheckBox("加粗")
                    bold_check.setChecked(item.font().bold())
                    bold_check.stateChanged.connect(lambda val: self.change_font_style(item, 'bold', val))
                    self.layout.addWidget(bold_check)

                    italic_check = QCheckBox("斜体")
                    italic_check.setChecked(item.font().italic())
                    italic_check.stateChanged.connect(lambda val: self.change_font_style(item, 'italic', val))
                    self.layout.addWidget(italic_check)

                    underline_check = QCheckBox("下划线")
                    underline_check.setChecked(item.font().underline())
                    underline_check.stateChanged.connect(lambda val: self.change_font_style(item, 'underline', val))
                    self.layout.addWidget(underline_check)

                    # 对齐方式
                    align_label = QLabel("对齐方式:")
                    self.layout.addWidget(align_label)
                    align_combo = QComboBox()
                    align_combo.addItems(["左对齐", "居中对齐", "右对齐"])
                    align_combo.currentIndexChanged.connect(lambda idx: self.change_alignment(item, idx))
                    self.layout.addWidget(align_combo)
            except Exception as e:
                logging.error(f"更新属性面板失败: {e}")

        else:
            # 如果是旋转模式，显示旋转中心设置
            selected_items = self.parent.scene.selectedItems()
            if not selected_items:
                return
            item = selected_items[0]
            if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
                # 旋转中心点设置
                self.layout.addWidget(QLabel("旋转中心点设置:"))
                self.layout.addWidget(self.rotation_center_label)
                self.layout.addWidget(self.rotation_center_slider)
                self.layout.addWidget(self.rotation_center_coord_label)

                coord_layout = QHBoxLayout()
                coord_layout.addWidget(QLabel("X:"))
                coord_layout.addWidget(self.rotation_center_x)
                coord_layout.addWidget(QLabel("Y:"))
                coord_layout.addWidget(self.rotation_center_y)
                self.layout.addLayout(coord_layout)

                # 旋转角度设置
                self.layout.addWidget(self.rotation_angle_label)
                self.layout.addWidget(self.rotation_angle_slider)
                angle_layout = QHBoxLayout()
                angle_layout.addWidget(QLabel("角度:"))
                angle_layout.addWidget(self.rotation_angle_input)
                self.layout.addLayout(angle_layout)

    def toggle_border(self, item, value):
        item.show_border = bool(value)
        item.update()

    def choose_font(self, item):
        font, ok = QFontDialog.getFont(item.font())
        if ok:
            item.setFont(font)

    def change_font_size(self, item, size):
        font = item.font()
        font.setPointSize(size)
        item.setFont(font)

    def choose_color(self, item, button):
        color = QColorDialog.getColor(item.defaultTextColor())
        if color.isValid():
            item.setDefaultTextColor(color)
            button.setStyleSheet(f"background-color: {color.name()};")

    def choose_bg_color(self, item, button):
        color = QColorDialog.getColor(item.background_color)
        if color.isValid():
            item.set_background_color(color)
            button.setStyleSheet(f"background-color: {color.name()};")

    def change_font_style(self, item, style, value):
        font = item.font()
        if style == 'bold':
            font.setBold(value)
        elif style == 'italic':
            font.setItalic(value)
        elif style == 'underline':
            font.setUnderline(value)
        item.setFont(font)

    def change_alignment(self, item, index):
        alignments = [Qt.AlignLeft, Qt.AlignCenter, Qt.AlignRight]
        alignment = alignments[index]
        # 创建文本块格式
        block_format = QTextBlockFormat()
        block_format.setAlignment(alignment)
        # 创建文本光标并应用格式
        cursor = item.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.mergeBlockFormat(block_format)
        item.setTextCursor(cursor)

    def update_rotation_center(self, item):
        # 更新旋转中心点的坐标显示
        center = item.transformOriginPoint()
        scene_center = item.mapToScene(center)
        self.rotation_center_coord_label.setText(f"旋转中心点坐标: ({scene_center.x():.2f}, {scene_center.y():.2f})")

    def change_rotation_center_size(self, value):
        self.rotation_center_size = value
        # 更新所有旋转句柄的大小
        for handle in self.parent.rotation_handles:
            handle.setRect(-value / 2, -value / 2, value, value)

    def change_rotation_center_coord(self):
        try:
            x = float(self.rotation_center_x.text())
            y = float(self.rotation_center_y.text())
            if self.parent.rotation_target_items:
                item = self.parent.rotation_target_items[0]
                item.setTransformOriginPoint(QPointF(x, y))
                # Move the rotation handle to the new center
                for handle in self.parent.rotation_handles:
                    handle.setPos(item.mapToScene(QPointF(x, y)))
                logging.info(f"旋转中心点已设置为: ({x}, {y})")
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的坐标值。")

    def change_rotation_angle(self, value):
        self.rotation_angle_input.setText(str(value))
        if self.parent.rotation_target_items:
            item = self.parent.rotation_target_items[0]
            item.setRotation(value)
            logging.info(f"旋转角度已设置为: {value}°")

    def change_rotation_angle_input(self):
        try:
            angle = float(self.rotation_angle_input.text())
            self.rotation_angle_slider.setValue(int(angle))
            if self.parent.rotation_target_items:
                item = self.parent.rotation_target_items[0]
                item.setRotation(angle)
                logging.info(f"旋转角度已设置为: {angle}°")
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的角度值。")

# 撤销命令类
class AddLayerCommand(QUndoCommand):
    def __init__(self, editor, layer):
        super().__init__("添加图层")
        self.editor = editor
        self.layer = layer

    def undo(self):
        self.editor.scene.removeItem(self.layer)
        self.editor.layers.remove(self.layer)
        self.editor.update_layer_list()
        self.editor.add_history(f"撤销添加图层: {self.layer.layer_name}")

    def redo(self):
        self.editor.scene.addItem(self.layer)
        self.editor.layers.append(self.layer)
        self.editor.update_layer_list()
        self.editor.add_history(f"添加图层: {self.layer.layer_name}")

class DeleteLayerCommand(QUndoCommand):
    def __init__(self, editor, layer):
        super().__init__("删除图层")
        self.editor = editor
        self.layer = layer

    def undo(self):
        self.editor.scene.addItem(self.layer)
        self.editor.layers.append(self.layer)
        self.editor.update_layer_list()
        self.editor.add_history(f"撤销删除图层: {self.layer.layer_name}")

    def redo(self):
        self.editor.scene.removeItem(self.layer)
        self.editor.layers.remove(self.layer)
        self.editor.update_layer_list()
        self.editor.add_history(f"删除图层: {self.layer.layer_name}")

class CropCommand(QUndoCommand):
    def __init__(self, editor, old_item, new_item):
        super().__init__("裁剪图层")
        self.editor = editor
        self.old_item = old_item
        self.new_item = new_item

    def undo(self):
        try:
            index = self.editor.layers.index(self.new_item)
        except ValueError:
            index = 0  # 默认插入位置
        self.editor.scene.removeItem(self.new_item)
        self.editor.scene.addItem(self.old_item)
        self.editor.layers.insert(index, self.old_item)
        self.editor.layers.remove(self.new_item)
        self.editor.update_layer_list()
        self.editor.add_history(f"撤销裁剪图层: {self.old_item.layer_name}")

    def redo(self):
        try:
            index = self.editor.layers.index(self.old_item)
        except ValueError:
            index = 0  # 默认插入位置
        self.editor.scene.removeItem(self.old_item)
        self.editor.scene.addItem(self.new_item)
        self.editor.layers.insert(index, self.new_item)
        self.editor.layers.remove(self.old_item)
        self.editor.update_layer_list()
        self.editor.add_history(f"裁剪图层: {self.new_item.layer_name}")

class MergeLayersCommand(QUndoCommand):
    def __init__(self, editor, layers):
        super().__init__("合并图层")
        self.editor = editor
        self.layers = layers
        self.merged_layer = None

    def undo(self):
        self.editor.scene.removeItem(self.merged_layer)
        for layer in self.layers:
            self.editor.scene.addItem(layer)
            self.editor.layers.append(layer)
        self.editor.update_layer_list()
        self.editor.add_history("撤销合并图层")

    def redo(self):
        for layer in self.layers:
            self.editor.scene.removeItem(layer)
            self.editor.layers.remove(layer)
        self.merged_layer = self.editor.merge_layers(self.layers)
        self.editor.scene.addItem(self.merged_layer)
        self.editor.layers.append(self.merged_layer)
        self.editor.update_layer_list()
        self.editor.add_history("合并图层")

# 主图像编辑器类
class ImageEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python 图像处理工具")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet("background-color: lightgrey;")  # 软件背景浅灰色

        # 图形视图和场景
        self.scene = QGraphicsScene()
        self.view = GraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.setCentralWidget(self.view)

        # 图层列表
        self.layers = []  # 图层列表
        self.rotation_handles = []  # 旋转中心句柄列表
        self.rotation_target_items = []  # 当前旋转目标图层
        self.init_layer_panel()

        # 属性面板
        self.property_panel = PropertyPanel(parent=self)
        self.property_dock = QDockWidget("属性", self)
        self.property_dock.setWidget(self.property_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.property_dock)

        # 操作记录
        self.undo_stack = QUndoStack(self)
        self.init_history_panel()

        # 日志面板
        self.init_log_panel()
        self.setup_logging()

        # 设置菜单
        self.create_actions()
        self.create_menus()

        # 初始化透明底图
        self.init_canvas()

        # 工具栏
        self.init_toolbar()

        # 连接信号
        self.scene.selectionChanged.connect(self.update_layer_selection)

        # Crop Overlay
        self.crop_overlay = None
        self.crop_mode = False  # 是否处于裁剪模式
        self.crop_target_item = None

        # Brush Tool
        self.brush_tool = BrushTool()
        self.brush_tool.hide()  # 默认隐藏

        # 当前绘图图层
        self.current_brush_layer = None

        # 旋转与镜像
        self.rotating = False

        # 指南线
        self.guidelines = []

        # 拖动状态
        self.dragging_item = False

        # 安装事件过滤器
        self.view.viewport().installEventFilter(self)

    def init_layer_panel(self):
        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabel("图层")
        self.layer_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.layer_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.layer_tree.itemChanged.connect(self.toggle_layer_visibility)
        self.layer_tree.itemDoubleClicked.connect(self.toggle_layer_lock)
        self.layer_tree.itemClicked.connect(self.select_layer_from_list)
        self.layer_tree.model().rowsMoved.connect(self.update_layer_order)

        # 创建图层面板
        dock = QDockWidget("图层", self)
        dock.setWidget(self.layer_tree)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def update_layer_order(self, parent, start, end, destination, row):
        # 根据列表顺序更新图层的Z值
        for index in range(self.layer_tree.topLevelItemCount()):
            tree_item = self.layer_tree.topLevelItem(index)
            layer_item = tree_item.data(0, Qt.UserRole)
            if layer_item:
                layer_item.setZValue(index)
        self.scene.update()

    def select_layer_from_list(self, tree_item, column):
        item = tree_item.data(0, Qt.UserRole)
        if item:
            # 取消当前选中
            for obj in self.scene.selectedItems():
                obj.setSelected(False)
            # 选中对应图层
            item.setSelected(True)
            self.scene.update()

    def init_log_panel(self):
        # 创建日志面板
        self.log_text_edit = QPlainTextEdit()
        self.log_text_edit.setReadOnly(True)
        dock = QDockWidget("日志", self)
        dock.setWidget(self.log_text_edit)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def setup_logging(self):
        # 设置日志输出到GUI
        handler = GuiLogger(self.log_text_edit)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    def init_history_panel(self):
        # 创建操作记录面板
        self.history_list = QListWidget()
        dock = QDockWidget("操作记录", self)
        dock.setWidget(self.history_list)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def log_message(self, message):
        self.log_text_edit.appendPlainText(message)
        logging.info(message)

    def add_history(self, action_description):
        self.history_list.addItem(action_description)
        logging.info(action_description)

    def create_actions(self):
        # 文件菜单
        self.open_act = QAction("&打开图片", self)
        self.open_act.triggered.connect(self.open_image)
        self.open_act.setShortcut(QKeySequence("Ctrl+O"))

        self.save_act = QAction("&保存图片", self)
        self.save_act.triggered.connect(self.save_image)
        self.save_act.setShortcut(QKeySequence("Ctrl+S"))

        self.save_as_size_act = QAction("保存为指定尺寸", self)
        self.save_as_size_act.triggered.connect(self.save_image_with_size)
        self.save_as_size_act.setShortcut(QKeySequence("Ctrl+Alt+S"))

        self.exit_act = QAction("退出", self)
        self.exit_act.triggered.connect(self.close)

        # 编辑菜单
        self.remove_bg_act = QAction("&去除背景", self)
        self.remove_bg_act.triggered.connect(self.remove_background)
        self.remove_bg_act.setShortcut(QKeySequence("Ctrl+Shift+R"))

        self.add_text_act = QAction("&添加文字", self)
        self.add_text_act.triggered.connect(self.add_text)
        self.add_text_act.setShortcut(QKeySequence("Ctrl+T"))

        self.add_image_act = QAction("&添加图像", self)
        self.add_image_act.triggered.connect(self.add_image)
        self.add_image_act.setShortcut(QKeySequence("Ctrl+I"))

        self.add_sticker_act = QAction("添加贴纸", self)
        self.add_sticker_act.triggered.connect(self.add_sticker)
        self.add_sticker_act.setShortcut(QKeySequence("Ctrl+Shift+S"))

        self.crop_act = QAction("裁剪图层", self)
        self.crop_act.triggered.connect(self.toggle_crop_mode)
        self.crop_act.setShortcut(QKeySequence("Ctrl+Shift+C"))

        # 视图菜单
        self.zoom_in_act = QAction("放大", self)
        self.zoom_in_act.triggered.connect(self.zoom_in)
        self.zoom_in_act.setShortcut(QKeySequence("Ctrl++"))

        self.zoom_out_act = QAction("缩小", self)
        self.zoom_out_act.triggered.connect(self.zoom_out)
        self.zoom_out_act.setShortcut(QKeySequence("Ctrl+-"))

        self.actual_size_act = QAction("实际尺寸", self)
        self.actual_size_act.triggered.connect(self.actual_size)
        self.actual_size_act.setShortcut(QKeySequence("Ctrl+1"))

        self.set_canvas_size_act = QAction("设置画布尺寸", self)
        self.set_canvas_size_act.triggered.connect(self.set_canvas_size)

        # 画布尺寸预设
        self.predefined_sizes = {
            "1:1": (1000, 1000),
            "4:3": (1600, 1200),
            "16:9": (1920, 1080),
            "9:16": (1080, 1920)  # 默认手机尺寸
        }

        # 旋转与镜像
        self.rotate_act = QAction("旋转", self)
        self.rotate_act.setCheckable(True)
        self.rotate_act.triggered.connect(self.toggle_rotation_mode)
        self.rotate_act.setShortcut(QKeySequence("Ctrl+R"))

        self.flip_horizontal_act = QAction("水平镜像", self)
        self.flip_horizontal_act.triggered.connect(lambda: self.flip_selected(horizontal=True))
        self.flip_horizontal_act.setShortcut(QKeySequence("Ctrl+Shift+H"))

        self.flip_vertical_act = QAction("垂直镜像", self)
        self.flip_vertical_act.triggered.connect(lambda: self.flip_selected(vertical=True))
        self.flip_vertical_act.setShortcut(QKeySequence("Ctrl+Shift+V"))

        # 调整功能
        self.adjust_act = QAction("调整图层", self)
        self.adjust_act.triggered.connect(self.adjust_layer)
        self.adjust_act.setShortcut(QKeySequence("Ctrl+E"))

        # 删除图层
        self.delete_layer_act = QAction("删除图层", self)
        self.delete_layer_act.triggered.connect(self.delete_selected_layer)
        self.delete_layer_act.setShortcut(QKeySequence("Delete"))

        # 自适应按钮
        self.auto_fit_act = QAction("自适应", self)
        self.auto_fit_act.triggered.connect(self.auto_fit_image)
        self.auto_fit_act.setShortcut(QKeySequence("Ctrl+Shift+F"))

        # 撤销和重做
        self.undo_act = self.undo_stack.createUndoAction(self, "撤销")
        self.undo_act.setShortcut(QKeySequence("Ctrl+Z"))
        self.redo_act = self.undo_stack.createRedoAction(self, "重做")
        self.redo_act.setShortcut(QKeySequence("Ctrl+Y"))

        # 对齐工具
        self.align_left_act = QAction("左对齐", self)
        self.align_left_act.triggered.connect(lambda: self.align_selected_items('left'))

        self.align_center_act = QAction("水平居中", self)
        self.align_center_act.triggered.connect(lambda: self.align_selected_items('hcenter'))

        self.align_right_act = QAction("右对齐", self)
        self.align_right_act.triggered.connect(lambda: self.align_selected_items('right'))

        self.align_top_act = QAction("顶部对齐", self)
        self.align_top_act.triggered.connect(lambda: self.align_selected_items('top'))

        self.align_vcenter_act = QAction("垂直居中", self)
        self.align_vcenter_act.triggered.connect(lambda: self.align_selected_items('vcenter'))

        self.align_bottom_act = QAction("底部对齐", self)
        self.align_bottom_act.triggered.connect(lambda: self.align_selected_items('bottom'))

        # 合并图层
        self.merge_layers_act = QAction("合并选中图层", self)
        self.merge_layers_act.triggered.connect(self.merge_selected_layers)
        self.merge_layers_act.setShortcut(QKeySequence("Ctrl+M"))

        self.merge_all_act = QAction("合并所有图层", self)
        self.merge_all_act.triggered.connect(self.merge_all_layers)
        self.merge_all_act.setShortcut(QKeySequence("Ctrl+Shift+M"))

    def create_menus(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("&文件")
        file_menu.addAction(self.open_act)
        file_menu.addAction(self.save_act)
        file_menu.addAction(self.save_as_size_act)  # 新增保存为指定尺寸
        file_menu.addSeparator()
        file_menu.addAction(self.exit_act)

        # 编辑菜单
        edit_menu = menubar.addMenu("&编辑")
        edit_menu.addAction(self.remove_bg_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.add_text_act)
        edit_menu.addAction(self.add_image_act)
        edit_menu.addAction(self.add_sticker_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.crop_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.rotate_act)
        edit_menu.addAction(self.flip_horizontal_act)
        edit_menu.addAction(self.flip_vertical_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.adjust_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.merge_layers_act)
        edit_menu.addAction(self.merge_all_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_layer_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.undo_act)
        edit_menu.addAction(self.redo_act)

        # 视图菜单
        view_menu = menubar.addMenu("&视图")
        view_menu.addAction(self.zoom_in_act)
        view_menu.addAction(self.zoom_out_act)
        view_menu.addAction(self.actual_size_act)
        view_menu.addSeparator()

        # 画布尺寸设置
        set_canvas_menu = view_menu.addMenu("设置画布尺寸")
        for ratio, size in self.predefined_sizes.items():
            action = QAction(ratio, self)
            action.triggered.connect(lambda checked, s=size: self.set_canvas_size_predefined(s))
            set_canvas_menu.addAction(action)
        set_canvas_menu.addSeparator()
        set_canvas_menu.addAction(self.set_canvas_size_act)

        # 对齐菜单
        align_menu = menubar.addMenu("对齐")
        align_menu.addAction(self.align_left_act)
        align_menu.addAction(self.align_center_act)
        align_menu.addAction(self.align_right_act)
        align_menu.addAction(self.align_top_act)
        align_menu.addAction(self.align_vcenter_act)
        align_menu.addAction(self.align_bottom_act)

    def init_toolbar(self):
        self.toolbar = QToolBar("工具栏", self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # 放大按钮
        self.zoom_in_btn = QPushButton("放大")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.toolbar.addWidget(self.zoom_in_btn)

        # 缩小按钮
        self.zoom_out_btn = QPushButton("缩小")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.toolbar.addWidget(self.zoom_out_btn)

        # 实际尺寸按钮
        self.actual_size_btn = QPushButton("实际尺寸")
        self.actual_size_btn.clicked.connect(self.actual_size)
        self.toolbar.addWidget(self.actual_size_btn)

        # 旋转与镜像按钮
        self.rotate_btn = QPushButton("旋转")
        self.rotate_btn.setCheckable(True)
        self.rotate_btn.clicked.connect(self.toggle_rotation_mode)
        self.toolbar.addWidget(self.rotate_btn)

        self.flip_horizontal_btn = QPushButton("水平镜像")
        self.flip_horizontal_btn.clicked.connect(lambda: self.flip_selected(horizontal=True))
        self.toolbar.addWidget(self.flip_horizontal_btn)

        self.flip_vertical_btn = QPushButton("垂直镜像")
        self.flip_vertical_btn.clicked.connect(lambda: self.flip_selected(vertical=True))
        self.toolbar.addWidget(self.flip_vertical_btn)

        # 裁剪按钮
        self.crop_btn = QPushButton("裁剪")
        self.crop_btn.setCheckable(True)
        self.crop_btn.clicked.connect(self.toggle_crop_mode)
        self.toolbar.addWidget(self.crop_btn)

        # 确认裁剪按钮
        self.confirm_crop_btn = QPushButton("确认裁剪")
        self.confirm_crop_btn.clicked.connect(self.confirm_crop)
        self.confirm_crop_btn.setVisible(False)
        self.toolbar.addWidget(self.confirm_crop_btn)

        # 取消裁剪按钮
        self.cancel_crop_btn = QPushButton("取消裁剪")
        self.cancel_crop_btn.clicked.connect(self.cancel_crop)
        self.cancel_crop_btn.setVisible(False)
        self.toolbar.addWidget(self.cancel_crop_btn)

        # 画笔工具
        self.brush_btn = QPushButton("画笔")
        self.brush_btn.setCheckable(True)
        self.brush_btn.clicked.connect(self.toggle_brush)
        self.toolbar.addWidget(self.brush_btn)

        # 调整按钮
        self.adjust_btn = QPushButton("调整")
        self.adjust_btn.clicked.connect(self.adjust_layer)
        self.toolbar.addWidget(self.adjust_btn)

        # 自适应按钮
        self.auto_fit_btn = QPushButton("自适应")
        self.auto_fit_btn.clicked.connect(self.auto_fit_image)
        self.toolbar.addWidget(self.auto_fit_btn)

        # 撤销和重做按钮
        self.undo_btn = QPushButton("撤销")
        self.undo_btn.clicked.connect(self.undo_stack.undo)
        self.toolbar.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("重做")
        self.redo_btn.clicked.connect(self.undo_stack.redo)
        self.toolbar.addWidget(self.redo_btn)

        # 状态标签
        self.status_label = QLabel("未选中图层")
        self.toolbar.addWidget(self.status_label)

    def init_canvas(self):
        # 默认画布尺寸为9:16
        self.canvas_width, self.canvas_height = self.predefined_sizes["9:16"]
        self.create_transparent_canvas()

    def create_transparent_canvas(self):
        # 清空场景
        self.scene.clear()
        self.layers = []
        self.layer_tree.clear()

        # 创建透明底图
        canvas = QPixmap(self.canvas_width, self.canvas_height)
        canvas.fill(QColor(255, 255, 255, 0))  # 完全透明
        self.base_canvas = ResizableGraphicsPixmapItem(canvas, "底图")
        self.base_canvas.setZValue(-2)  # 放在最底层
        self.scene.addItem(self.base_canvas)
        self.layers.append(self.base_canvas)
        self.add_layer_to_tree(self.base_canvas)

        # 设置画布背景颜色并添加条纹
        pattern_pixmap = QPixmap(20, 20)
        pattern_painter = QPainter(pattern_pixmap)
        pattern_painter.fillRect(0, 0, 10, 10, QColor(200, 200, 200))
        pattern_painter.fillRect(10, 10, 10, 10, QColor(200, 200, 200))
        pattern_painter.fillRect(0, 10, 10, 10, QColor(220, 220, 220))
        pattern_painter.fillRect(10, 0, 10, 10, QColor(220, 220, 220))
        pattern_painter.end()
        self.scene.setBackgroundBrush(QBrush(pattern_pixmap))

        # 设置场景尺寸
        self.scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)

        # 调整视图
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        logging.info(f"初始化底图: {self.canvas_width}x{self.canvas_height}")

    def add_layer_to_tree(self, item, parent=None):
        layer_name = item.layer_name
        tree_item = QTreeWidgetItem()
        tree_item.setText(0, layer_name)
        tree_item.setFlags(tree_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        tree_item.setCheckState(0, Qt.Checked)
        tree_item.setData(0, Qt.UserRole, item)
        # 添加锁定图标
        lock_icon_path = "lock_closed.png" if item.locked else "lock_open.png"
        if os.path.exists(lock_icon_path):
            lock_icon = QIcon(lock_icon_path)
        else:
            # 使用默认图标代替
            lock_icon = self.style().standardIcon(QApplication.style().SP_DialogCloseButton) if item.locked else self.style().standardIcon(QApplication.style().SP_DialogOpenButton)
        tree_item.setIcon(0, lock_icon)
        if parent:
            parent.addChild(tree_item)
        else:
            self.layer_tree.insertTopLevelItem(0, tree_item)

    def update_layer_list(self):
        self.layer_tree.clear()
        for item in reversed(self.layers):
            self.add_layer_to_tree(item)

    def toggle_layer_visibility(self, tree_item, column):
        item = tree_item.data(0, Qt.UserRole)
        if item and not item.locked:
            item.setVisible(tree_item.checkState(0) == Qt.Checked)
            logging.debug(f"图层可见性切换: {item.layer_name} 可见={item.isVisible()}")

    def toggle_layer_lock(self, tree_item, column):
        item = tree_item.data(0, Qt.UserRole)
        if item and (isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem)):
            item.locked = not item.locked
            if item.locked:
                # 更新锁定图标
                lock_icon_path = "lock_closed.png"
                if os.path.exists(lock_icon_path):
                    lock_icon = QIcon(lock_icon_path)
                else:
                    lock_icon = self.style().standardIcon(QApplication.style().SP_DialogCloseButton)
                tree_item.setIcon(0, lock_icon)
            else:
                lock_icon_path = "lock_open.png"
                if os.path.exists(lock_icon_path):
                    lock_icon = QIcon(lock_icon_path)
                else:
                    lock_icon = self.style().standardIcon(QApplication.style().SP_DialogOpenButton)
                tree_item.setIcon(0, lock_icon)
            # 更新边框样式
            if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
                item.update()
            # 更新列表项文本
            if item.locked:
                tree_item.setText(0, f"{item.layer_name} (锁定)")
            else:
                tree_item.setText(0, item.layer_name)
            logging.info(f"图层锁定状态切换: {item.layer_name} 锁定={item.locked}")

    def open_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)", options=options
        )
        if file_path:
            try:
                image = QPixmap(file_path)
                if image.isNull():
                    raise ValueError("无法加载图片。")
                # 更新画布尺寸为图片尺寸
                self.canvas_width, self.canvas_height = image.width(), image.height()
                self.create_transparent_canvas()

                item = ResizableGraphicsPixmapItem(image, f"图像：{os.path.basename(file_path)}")
                # 初始位置为(0,0)
                item.setPos(0, 0)
                self.scene.addItem(item)
                self.layers.append(item)
                self.add_layer_to_tree(item)
                self.undo_stack.push(AddLayerCommand(self, item))

                # 调整视图以适应整个画布
                self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
                logging.info(f"成功添加图像: {file_path}")
            except Exception as e:
                logging.error(f"无法打开图片: {e}")
                QMessageBox.critical(self, "错误", f"无法打开图片: {e}")

    def save_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "",
            "PNG 文件 (*.png);;JPEG 文件 (*.jpg *.jpeg)", options=options
        )
        if file_path:
            try:
                # 渲染场景到QImage
                image = QImage(self.canvas_width, self.canvas_height, QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                self.scene.render(painter)
                painter.end()

                # 确保保存为PNG以保留透明度
                if not file_path.lower().endswith('.png'):
                    file_path += '.png'
                image.save(file_path, "PNG")
                QMessageBox.information(self, "成功", f"图片已保存到 {file_path}")
                logging.info(f"成功保存图片到: {file_path}")
            except Exception as e:
                logging.error(f"无法保存图片: {e}")
                QMessageBox.critical(self, "错误", f"无法保存图片: {e}")

    def save_image_with_size(self):
        # 获取用户输入的尺寸
        text, ok = QInputDialog.getText(
            self, "保存为指定尺寸", "请输入目标尺寸 (宽,高):",
            text=f"{self.canvas_width},{self.canvas_height}"
        )
        if ok and text:
            try:
                width, height = map(int, text.split(','))
                if width <= 0 or height <= 0:
                    raise ValueError("尺寸必须为正整数。")
                # 计算缩放比例
                scale_x = width / self.canvas_width
                scale_y = height / self.canvas_height

                # 渲染场景到QImage
                image = QImage(width, height, QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                painter.scale(scale_x, scale_y)
                self.scene.render(painter)
                painter.end()

                # 保存图片
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存图片", "",
                    "PNG 文件 (*.png);;JPEG 文件 (*.jpg *.jpeg)", options=QFileDialog.Options()
                )
                if file_path:
                    # 确保保存为PNG以保留透明度
                    if not file_path.lower().endswith('.png'):
                        file_path += '.png'
                    image.save(file_path, "PNG")
                    QMessageBox.information(self, "成功", f"图片已保存到 {file_path}")
                    logging.info(f"成功保存指定尺寸图片到: {file_path}")
            except Exception as e:
                logging.error(f"保存指定尺寸图片失败: {e}")
                QMessageBox.critical(self, "错误", f"保存指定尺寸图片失败: {e}")

    def remove_background(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要去除背景的图像。")
            return

        for item in selected_items:
            if isinstance(item, ResizableGraphicsPixmapItem):
                if item.locked:
                    QMessageBox.warning(self, "警告", f"图层已锁定，无法编辑: {item.layer_name}")
                    continue
                try:
                    # 使用线程去除背景
                    thread = RemoveBackgroundThread(item.pixmap(), item)
                    thread.finished.connect(self.on_background_removed)
                    thread.error.connect(self.on_background_remove_error)
                    thread.start()
                    logging.info(f"启动去除背景线程，图层: {item.layer_name}")
                except Exception as e:
                    logging.error(f"背景去除失败: {e}")
                    QMessageBox.critical(self, "错误", f"背景去除失败: {e}")

    def on_background_removed(self, pixmap, item):
        try:
            # 保存操作以便撤销
            self.undo_stack.push(AddLayerCommand(self, item))
            item.setPixmap(pixmap)
            # 更新工具栏中的大小和比例信息
            new_width = pixmap.width()
            new_height = pixmap.height()
            self.status_label.setText(f"选中图层: {item.layer_name}")
            logging.info(f"成功去除背景，图层: {item.layer_name}")
            QMessageBox.information(self, "成功", f"背景已成功去除: {item.layer_name}")
        except Exception as e:
            logging.error(f"更新图层失败: {e}")
            QMessageBox.critical(self, "错误", f"更新图层失败: {e}")

    def on_background_remove_error(self, error_message):
        QMessageBox.critical(self, "错误", f"背景去除失败: {error_message}")

    def add_text(self):
        text, ok = QInputDialog.getText(self, "添加文字", "请输入要添加的文字:")
        if ok and text:
            try:
                item = ResizableGraphicsTextItem(text, f"文字：{text}")
                item.setPos(50, 50)
                self.scene.addItem(item)
                self.layers.append(item)
                self.add_layer_to_tree(item)
                self.undo_stack.push(AddLayerCommand(self, item))
                logging.info(f"成功添加文字: {text}")
            except Exception as e:
                logging.error(f"添加文字失败: {e}")
                QMessageBox.critical(self, "错误", f"添加文字失败: {e}")

    def add_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "添加图像", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)", options=options
        )
        if file_path:
            try:
                image = QPixmap(file_path)
                if image.isNull():
                    raise ValueError("无法加载图片。")
                item = ResizableGraphicsPixmapItem(image, f"图像：{os.path.basename(file_path)}")
                item.setPos(100, 100)
                self.scene.addItem(item)
                self.layers.append(item)
                self.add_layer_to_tree(item)
                self.undo_stack.push(AddLayerCommand(self, item))
                logging.info(f"成功添加图像: {file_path}")
            except Exception as e:
                logging.error(f"添加图像失败: {e}")
                QMessageBox.critical(self, "错误", f"添加图像失败: {e}")

    def add_sticker(self):
        # 贴纸可以从预设的贴纸库中选择，这里简化为添加图像
        self.add_image()

    def toggle_brush(self, checked):
        if checked:
            selected_items = self.scene.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "请选择一个图层来使用画笔。")
                self.brush_btn.setChecked(False)
                return
            self.brush_tool.show()
            self.current_brush_layer = selected_items[0]
            if self.current_brush_layer.locked:
                QMessageBox.warning(self, "警告", f"图层已锁定，无法编辑: {self.current_brush_layer.layer_name}")
                self.brush_btn.setChecked(False)
                self.brush_tool.hide()
                self.current_brush_layer = None
                return
            if isinstance(self.current_brush_layer, ResizableGraphicsTextItem):
                QMessageBox.warning(self, "警告", "文字图层不支持画笔工具。")
                self.brush_btn.setChecked(False)
                self.brush_tool.hide()
                self.current_brush_layer = None
                return
            # 设置自定义画笔光标
            self.view.setCursor(Qt.CrossCursor)
            self.view.setDragMode(QGraphicsView.NoDrag)
            logging.info(f"启用画笔工具，当前图层: {self.current_brush_layer.layer_name}")
            # 隐藏其他工具相关元素
            self.hide_tool_related_elements()
        else:
            self.brush_tool.hide()
            self.current_brush_layer = None
            self.view.setCursor(Qt.ArrowCursor)
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            logging.info("禁用画笔工具")
            # 恢复其他工具相关元素
            self.show_tool_related_elements()

    def toggle_crop_mode(self, checked):
        if checked:
            selected_items = self.scene.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "请选择一个图层来裁剪。")
                self.crop_btn.setChecked(False)
                return
            item = selected_items[0]
            if isinstance(item, ResizableGraphicsPixmapItem):
                if item.locked:
                    QMessageBox.warning(self, "警告", f"图层已锁定，无法编辑: {item.layer_name}")
                    self.crop_btn.setChecked(False)
                    return
                self.crop_mode = True
                self.crop_target_item = item
                self.view.setCursor(Qt.CrossCursor)
                logging.info(f"进入裁剪模式，图层: {item.layer_name}")
                # 显示裁剪工具栏按钮
                self.confirm_crop_btn.setVisible(True)
                self.cancel_crop_btn.setVisible(True)
                # 更新属性面板
                self.property_panel.update_properties(None)
            else:
                QMessageBox.warning(self, "警告", "请选择一个图像图层来裁剪。")
                self.crop_btn.setChecked(False)
        else:
            self.crop_mode = False
            self.view.setCursor(Qt.ArrowCursor)
            if self.crop_overlay:
                self.scene.removeItem(self.crop_overlay)
                self.crop_overlay = None
            logging.info("退出裁剪模式")
            # 隐藏裁剪工具栏按钮
            self.confirm_crop_btn.setVisible(False)
            self.cancel_crop_btn.setVisible(False)
            # 更新属性面板
            self.property_panel.update_properties(None)

    def toggle_rotation_mode(self, checked):
        if checked:
            selected_items = self.scene.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "请选择一个图层来旋转。")
                self.rotate_act.setChecked(False)
                return
            self.rotation_target_items = selected_items
            self.rotation_handles = []
            for item in selected_items:
                if item.locked:
                    continue
                # 添加旋转中心点
                rotation_handle = RotationHandle(item, self.view)
                rotation_handle.setPos(item.mapToScene(item.transformOriginPoint()))
                self.scene.addItem(rotation_handle)
                self.rotation_handles.append(rotation_handle)
                # 连接属性面板更新
                self.property_panel.update_rotation_center(item)
            self.view.setCursor(Qt.CrossCursor)
            logging.info("进入旋转模式")
            # 在属性面板中显示旋转相关控件
            self.property_panel.update_properties(None)
        else:
            for handle in self.rotation_handles:
                self.scene.removeItem(handle)
            self.rotation_handles.clear()
            self.view.setCursor(Qt.ArrowCursor)
            self.rotation_target_items = []
            logging.info("退出旋转模式")
            # 更新属性面板
            self.property_panel.update_properties(None)

    def set_rotation_angle(self, angle):
        if self.rotation_target_items:
            for item in self.rotation_target_items:
                item.setRotation(angle)
            self.property_panel.rotation_angle_slider.setValue(int(angle))
            self.property_panel.rotation_angle_input.setText(str(angle))

    def hide_tool_related_elements(self):
        # 隐藏旋转中心
        for handle in self.rotation_handles:
            handle.hide()
        # 隐藏属性面板
        self.property_panel.hide()

    def show_tool_related_elements(self):
        # 显示属性面板
        self.property_panel.show()

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonPress:
            if self.brush_tool.isVisible():
                if event.button() == Qt.LeftButton and self.current_brush_layer:
                    self.last_point = self.view.mapToScene(event.pos())
                    return True
            elif self.crop_mode:
                if event.button() == Qt.LeftButton:
                    self.crop_start_point = self.view.mapToScene(event.pos())
                    if self.crop_overlay:
                        self.scene.removeItem(self.crop_overlay)
                        self.crop_overlay = None
                    # 创建裁剪框
                    self.crop_overlay = CropOverlay(QRectF(self.crop_start_point, self.crop_start_point))
                    self.scene.addItem(self.crop_overlay)
                    return True
        elif event.type() == QEvent.MouseMove:
            if self.brush_tool.isVisible():
                if event.buttons() & Qt.LeftButton and self.current_brush_layer:
                    current_point = self.view.mapToScene(event.pos())
                    self.paint_on_layer(self.current_brush_layer, self.last_point, current_point)
                    self.last_point = current_point
                    return True
            elif self.crop_mode:
                if event.buttons() & Qt.LeftButton and self.crop_overlay:
                    current_point = self.view.mapToScene(event.pos())
                    rect = QRectF(self.crop_start_point, current_point).normalized()
                    self.crop_overlay.setRect(rect)
                    return True
        elif event.type() == QEvent.MouseButtonRelease:
            if self.crop_mode:
                return True
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        if self.rotate_btn.isChecked():
            scene_pos = self.view.mapToScene(event.pos())
            item = self.scene.itemAt(scene_pos, QTransform())
            if item and item in self.rotation_target_items:
                self.rotating = True
                self.rotation_start_pos = scene_pos
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.rotate_btn.isChecked() and self.rotating:
            current_pos = self.view.mapToScene(event.pos())
            for item in self.rotation_target_items:
                center = item.mapToScene(item.transformOriginPoint())
                angle = QLineF(center, self.rotation_start_pos).angleTo(QLineF(center, current_pos))
                item.setRotation(item.rotation() + angle)
            self.rotation_start_pos = current_pos
            self.view.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rotate_btn.isChecked() and self.rotating:
            self.rotating = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paint_on_layer(self, layer, start_point, end_point):
        if isinstance(layer, ResizableGraphicsTextItem):
            # 文字图层不支持画笔工具
            pass
        else:
            # 对图像图层进行绘制
            pixmap = layer.pixmap()
            image = pixmap.toImage()
            painter = QPainter(image)
            pen = QPen(self.brush_tool.current_color, self.brush_tool.size_slider.value(), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            if self.brush_tool.mode == 'erase':
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(pen)
            layer_point_start = layer.mapFromScene(start_point)
            layer_point_end = layer.mapFromScene(end_point)
            painter.drawLine(layer_point_start, layer_point_end)
            painter.end()
            layer.setPixmap(QPixmap.fromImage(image))

    def confirm_crop(self):
        if not self.crop_overlay or not self.crop_target_item:
            return
        try:
            rect = self.crop_overlay.rect()
            # 获取 QPixmap 并转换为 PIL Image
            pixmap = self.crop_target_item.pixmap()
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            pixmap.save(buffer, "PNG")
            input_bytes = buffer.data().data()
            input_image = Image.open(BytesIO(input_bytes)).convert("RGBA")

            # 计算裁剪区域相对于图像的位置
            crop_rect = self.crop_target_item.mapFromScene(rect).boundingRect()
            crop_x = int(crop_rect.x())
            crop_y = int(crop_rect.y())
            crop_width = int(crop_rect.width())
            crop_height = int(crop_rect.height())

            # 确保裁剪区域在图像范围内
            crop_x = max(0, crop_x)
            crop_y = max(0, crop_y)
            crop_width = min(crop_width, input_image.width - crop_x)
            crop_height = min(crop_height, input_image.height - crop_y)

            if crop_width <= 0 or crop_height <= 0:
                QMessageBox.warning(self, "警告", "裁剪区域无效。")
                return

            cropped_image = input_image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))

            # 转换回 QPixmap
            cropped_qimage = self.pil_image_to_qimage(cropped_image)
            cropped_pixmap = QPixmap.fromImage(cropped_qimage)

            # 创建新的图层，但不立即修改图层列表
            new_layer = ResizableGraphicsPixmapItem(cropped_pixmap, self.crop_target_item.layer_name)
            new_layer.setPos(rect.topLeft())
            new_layer.setRotation(self.crop_target_item.rotation())
            new_layer.setScale(self.crop_target_item.scale())
            new_layer.setTransformOriginPoint(self.crop_target_item.transformOriginPoint())

            # 在修改图层列表之前，先创建并压入撤销命令
            self.undo_stack.push(CropCommand(self, self.crop_target_item, new_layer))

            # 移除裁剪框
            self.scene.removeItem(self.crop_overlay)
            self.crop_overlay = None
            self.crop_mode = False
            self.crop_btn.setChecked(False)
            self.view.setCursor(Qt.ArrowCursor)
            logging.info(f"图层已裁剪: {new_layer.layer_name}")
            self.crop_target_item = None
            self.add_history(f"裁剪图层: {new_layer.layer_name}")

            # 更新属性面板
            self.property_panel.update_properties(None)
        except Exception as e:
            logging.error(f"裁剪图层失败: {e}")
            QMessageBox.critical(self, "错误", f"裁剪图层失败: {e}")

    def cancel_crop(self):
        if self.crop_overlay:
            self.scene.removeItem(self.crop_overlay)
            self.crop_overlay = None
        self.crop_mode = False
        self.crop_btn.setChecked(False)
        self.confirm_crop_btn.setVisible(False)
        self.cancel_crop_btn.setVisible(False)
        self.view.setCursor(Qt.ArrowCursor)
        logging.info("取消裁剪操作")

    def flip_selected(self, horizontal=False, vertical=False):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择一个图层来镜像。")
            return
        for item in selected_items:
            if (isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem)) and not item.locked:
                # 保存操作以便撤销
                self.undo_stack.push(AddLayerCommand(self, item))

                transform = item.transform()
                scale_x = -1 if horizontal else 1
                scale_y = -1 if vertical else 1
                transform.scale(scale_x, scale_y)
                item.setTransform(transform)
                logging.info(f"图层已镜像: {item.layer_name} 水平={horizontal} 垂直={vertical}")
                self.add_history(f"镜像图层: {item.layer_name}")
            else:
                QMessageBox.warning(self, "警告", f"图层 {item.layer_name} 无法镜像，可能已锁定。")

    def adjust_layer(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择一个图层来调整。")
            return
        item = selected_items[0]
        if not isinstance(item, ResizableGraphicsPixmapItem) and not isinstance(item, ResizableGraphicsTextItem):
            QMessageBox.warning(self, "警告", "请选择一个图像或文字图层来调整。")
            return
        if item.locked:
            QMessageBox.warning(self, "警告", f"图层已锁定，无法调整: {item.layer_name}")
            return

        # 打开调整对话框
        dialog = AdjustmentDialog(item, self)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            # 保存操作以便撤销
            self.undo_stack.push(AddLayerCommand(self, item))
            logging.info(f"图层已调整: {item.layer_name}")
            self.add_history(f"调整图层: {item.layer_name}")

    def zoom_in(self):
        selected_items = self.scene.selectedItems()
        if selected_items:
            for item in selected_items:
                if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
                    scale_factor = 1.1
                    item.scale_factor *= scale_factor
                    item.setScale(item.scale_factor)
        else:
            # 如果没有选中图层，放大视图
            self.view.scale(1.1, 1.1)

    def zoom_out(self):
        selected_items = self.scene.selectedItems()
        if selected_items:
            for item in selected_items:
                if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
                    scale_factor = 0.9
                    item.scale_factor *= scale_factor
                    item.setScale(item.scale_factor)
        else:
            # 如果没有选中图层，缩小视图
            self.view.scale(0.9, 0.9)

    def actual_size(self):
        self.view.resetTransform()
        logging.info("视图已重置为实际尺寸")
        self.add_history("视图重置为实际尺寸")

    def set_canvas_size_predefined(self, size):
        width, height = size
        self.canvas_width, self.canvas_height = width, height
        self.create_transparent_canvas()
        logging.info(f"画布尺寸已设置为预设: {width}x{height}")

    def set_canvas_size(self):
        text, ok = QInputDialog.getText(
            self, "设置画布尺寸", "请输入画布尺寸 (宽,高):",
            text=f"{self.canvas_width},{self.canvas_height}"
        )
        if ok and text:
            try:
                width, height = map(int, text.split(','))
                if width <= 0 or height <= 0:
                    raise ValueError("尺寸必须为正整数。")
                # 更新画布尺寸
                self.canvas_width, self.canvas_height = width, height
                self.create_transparent_canvas()
                logging.info(f"画布尺寸已设置为: {self.canvas_width}x{self.canvas_height}")
            except Exception as e:
                logging.error(f"设置画布尺寸失败: {e}")
                QMessageBox.warning(self, "警告", "请输入有效的宽和高，例如 1080,1920。")

    def delete_selected_layer(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择一个图层来删除。")
            return
        for item in selected_items:
            if item == self.base_canvas:
                QMessageBox.warning(self, "警告", "底图不可删除。")
                continue
            reply = QMessageBox.question(self, '确认删除',
                                         f"是否删除图层: {item.layer_name}?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    # 保存操作以便撤销
                    self.undo_stack.push(DeleteLayerCommand(self, item))

                    self.layers.remove(item)
                    self.scene.removeItem(item)
                    # 从列表中移除
                    self.update_layer_list()
                    self.status_label.setText("未选中图层")
                    logging.info(f"图层已删除: {item.layer_name}")
                    self.add_history(f"删除图层: {item.layer_name}")
                except Exception as e:
                    logging.error(f"删除图层失败: {e}")
                    QMessageBox.critical(self, "错误", f"删除图层失败: {e}")

    def update_layer_selection(self):
        selected_items = self.scene.selectedItems()
        if selected_items:
            item = selected_items[0]
            # 找到对应的列表项
            iterator = QTreeWidgetItemIterator(self.layer_tree)
            while iterator.value():
                tree_item = iterator.value()
                layer_item = tree_item.data(0, Qt.UserRole)
                if layer_item == item:
                    tree_item.setSelected(True)
                    # 更新工具栏信息
                    self.update_toolbar_info(item)
                    # 更新属性面板
                    self.property_panel.update_properties(item)
                    return
                iterator += 1
        else:
            self.status_label.setText("未选中图层")
            self.current_brush_layer = None
            # 清空属性面板
            self.property_panel.update_properties(None)

    def update_toolbar_info(self, item):
        if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
            self.status_label.setText(f"选中图层: {item.layer_name}")
        else:
            self.status_label.setText("未选中图层")

    def pil_image_to_qimage(self, pil_image):
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
        return qimage

    def auto_fit_image(self):
        # 调整视图以适应整个画布
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        logging.info("视图已自适应画布大小")
        self.add_history("视图自适应画布大小")

    def align_selected_items(self, alignment):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要对齐的图层。")
            return
        if alignment in ['left', 'hcenter', 'right']:
            if alignment == 'left':
                min_x = min(item.sceneBoundingRect().left() for item in selected_items)
                for item in selected_items:
                    item.setX(min_x - item.boundingRect().left())
            elif alignment == 'hcenter':
                avg_x = sum(item.sceneBoundingRect().center().x() for item in selected_items) / len(selected_items)
                for item in selected_items:
                    offset = avg_x - item.sceneBoundingRect().center().x()
                    item.setX(item.x() + offset)
            elif alignment == 'right':
                max_x = max(item.sceneBoundingRect().right() for item in selected_items)
                for item in selected_items:
                    offset = max_x - item.sceneBoundingRect().right()
                    item.setX(item.x() + offset)
        elif alignment in ['top', 'vcenter', 'bottom']:
            if alignment == 'top':
                min_y = min(item.sceneBoundingRect().top() for item in selected_items)
                for item in selected_items:
                    item.setY(min_y - item.boundingRect().top())
            elif alignment == 'vcenter':
                avg_y = sum(item.sceneBoundingRect().center().y() for item in selected_items) / len(selected_items)
                for item in selected_items:
                    offset = avg_y - item.sceneBoundingRect().center().y()
                    item.setY(item.y() + offset)
            elif alignment == 'bottom':
                max_y = max(item.sceneBoundingRect().bottom() for item in selected_items)
                for item in selected_items:
                    offset = max_y - item.sceneBoundingRect().bottom()
                    item.setY(item.y() + offset)
        logging.info(f"图层已对齐: {alignment}")
        self.add_history(f"图层对齐: {alignment}")

    def merge_selected_layers(self):
        selected_items = self.scene.selectedItems()
        if not selected_items or len(selected_items) < 2:
            QMessageBox.warning(self, "警告", "请至少选择两个图层来合并。")
            return
        # 排序图层根据Z值
        selected_items_sorted = sorted(selected_items, key=lambda item: item.zValue())
        self.undo_stack.push(MergeLayersCommand(self, selected_items_sorted))

    def merge_all_layers(self):
        if len(self.layers) < 2:
            QMessageBox.warning(self, "警告", "没有足够的图层来合并。")
            return
        # 排序图层根据Z值
        layers_sorted = sorted(self.layers, key=lambda item: item.zValue())
        self.undo_stack.push(MergeLayersCommand(self, layers_sorted))

    def merge_layers(self, layers):
        # 创建一个新的图像
        merged_image = QImage(self.canvas_width, self.canvas_height, QImage.Format_ARGB32)
        merged_image.fill(Qt.transparent)
        painter = QPainter(merged_image)
        for layer in layers:
            layer.render(painter)
        painter.end()

        # 创建新的图层
        pixmap = QPixmap.fromImage(merged_image)
        merged_layer = ResizableGraphicsPixmapItem(pixmap, "合并图层")
        merged_layer.setPos(0, 0)
        return merged_layer

    def main(self):
        app = QApplication(sys.argv)
        editor = ImageEditor()
        editor.show()
        sys.exit(app.exec_())

# 自定义图形视图
class GraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setMouseTracking(True)
        self.rotating = False
        self.rotation_start_pos = None
        self.parent = parent  # 引用父级 ImageEditor
        self.dragging = False

    def wheelEvent(self, event):
        selected_items = self.scene().selectedItems()
        if selected_items:
            # 仅对第一个选中的图层进行缩放
            item = selected_items[0]
            if isinstance(item, ResizableGraphicsPixmapItem) or isinstance(item, ResizableGraphicsTextItem):
                angle = event.angleDelta().y()
                factor = 1.25 if angle > 0 else 0.8
                item.scale_factor *= factor
                item.setScale(item.scale_factor)
                return
        # 如果没有选中图层，进行视图缩放
        if event.angleDelta().y() > 0:
            self.scale(1.25, 1.25)
        else:
            self.scale(0.8, 0.8)

    def mousePressEvent(self, event):
        if self.parent.rotate_btn.isChecked():
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, QTransform())
            if item and item in self.parent.rotation_target_items:
                self.rotating = True
                self.rotation_start_pos = scene_pos
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.parent.rotate_btn.isChecked() and self.rotating:
            current_pos = self.mapToScene(event.pos())
            for item in self.parent.rotation_target_items:
                center = item.mapToScene(item.transformOriginPoint())
                angle = QLineF(center, self.rotation_start_pos).angleTo(QLineF(center, current_pos))
                item.setRotation(item.rotation() + angle)
            self.rotation_start_pos = current_pos
            self.viewport().update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parent.rotate_btn.isChecked() and self.rotating:
            self.rotating = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.dragging:
            # Draw guidelines
            painter = QPainter(self.viewport())
            pen = QPen(Qt.black, 1, Qt.DashLine)
            painter.setPen(pen)
            rect = self.mapToScene(self.viewport().rect()).boundingRect()
            center_x = rect.center().x()
            center_y = rect.center().y()
            painter.drawLine(self.mapFromScene(QPointF(center_x, rect.top())), self.mapFromScene(QPointF(center_x, rect.bottom())))
            painter.drawLine(self.mapFromScene(QPointF(rect.left(), center_y)), self.mapFromScene(QPointF(rect.right(), center_y)))
            painter.end()

def main():
    app = QApplication(sys.argv)
    editor = ImageEditor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
