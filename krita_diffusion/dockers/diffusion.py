from krita import Krita, DockWidget, Selection
from PyQt5.QtCore import Qt, qDebug, pyqtSignal, QObject
from PyQt5 import QtWidgets
import tempfile
import urllib.request
import os
import uuid
import base64
import json
from typing import Tuple


class KritaDiffusionDocker(DockWidget):
    name = "KritaDiffusion"
    initialized = False

    @classmethod
    def initialize(cls):
        if cls.initialized:
            return

        cls.initialized = True

        Krita.instance().action('edit_undo').triggered.connect(refresh_projection)
        Krita.instance().action('edit_redo').triggered.connect(refresh_projection)

    def __init__(self):
        super().__init__()

        self.txt2img_dialogue = None
        self.img2img_dialogue = None
        self.inpainting_dialogue = None

        self.setWindowTitle("Krita Diffusion")

        # Widgets
        main = QtWidgets.QWidget(self)
        self.btn_txt2img = QtWidgets.QPushButton('txt2img')
        self.btn_img2img = QtWidgets.QPushButton('img2img')
        self.btn_inpainting = QtWidgets.QPushButton('inpaint')

        # TODO: make configurable
        self.txt2img_url = 'http://localhost:8000/txt2img'
        self.img2img_url = 'http://localhost:8000/img2img'
        self.inpainting_url = 'http://localhost:8000/inpainting'

        # Layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.addWidget(self.btn_txt2img)
        self.layout.addWidget(self.btn_img2img)
        self.layout.addWidget(self.btn_inpainting)
        main.setLayout(self.layout)
        self.setWidget(main)

        # signals
        self.btn_txt2img.clicked.connect(self.txt2img)
        self.btn_img2img.clicked.connect(self.img2img)
        self.btn_inpainting.clicked.connect(self.inpainting)

    def txt2img(self):
        KritaDiffusionDocker.initialize()

        inst = Krita.instance()
        active_doc = inst.activeDocument()
        selection = active_doc.selection()

        if not is_selection_valid(selection):
            QtWidgets.QMessageBox.error(None, f"Error", "No active selection")
            return

        if self.txt2img_dialogue is None:
            self.txt2img_dialogue = InputDialog({
                'prompt': MultilineInputValue(placeholder='A snake in a grass', label='Prompt'),
                'sampling_steps': TextInputValue(value=str(25), label='Steps'),
                'cfg': TextInputValue(value=str(7), label='CFG'),
                'seed': TextInputValue(value=str(-1), label='Seed'),
            })

        # TODO: set main window to MyDockerWidget
        if not self.txt2img_dialogue.exec_():
            return

        body = self.txt2img_dialogue.get_values()
        body.update({
            'plms': True,
            'fixed_code_sampling': False,
            'width': selection.width(),
            'height': selection.height()
        })

        with post_data(self.txt2img_url, body) as response:
            if response.status != 200:
                QtWidgets.QMessageBox.error(None, f"Server responded with error {response.status}",
                                            response.read().decode('utf-8'))
                return

            response_json = json.loads(response.read())
            base64_response_image = response_json['base64_image']
            if not import_base64_string_to_selection(selection, base64_response_image):
                QtWidgets.QMessageBox.error(None, f"Error", "Can't paste image")

    def img2img(self):
        KritaDiffusionDocker.initialize()

        inst = Krita.instance()
        active_doc = inst.activeDocument()
        selection = active_doc.selection()

        if not is_selection_valid(selection):
            QtWidgets.QMessageBox.error(None, f"Error", "No active selection")
            return

        if self.img2img_dialogue is None:
            self.img2img_dialogue = InputDialog({
                'prompt': MultilineInputValue(placeholder='A snake in a grass', label='Prompt'),
                'sampling_steps': TextInputValue(value=str(25), label='Steps'),
                'cfg': TextInputValue(value=str(7), label='CFG'),
                'denoising_strength': TextInputValue(value=str(0.75), label='Denoising strength'),
                'seed': TextInputValue(value=str(-1), label='Seed'),
            })

        base64_request_image = export_selection_to_base64_string()
        body = {
            'plms': True,
            'fixed_code_sampling': False,
            'width': selection.width(),
            'height': selection.height(),
            'base64_image': base64_request_image
        }

        if not self.img2img_dialogue.exec_():
            return

        body.update(self.img2img_dialogue.get_values())

        with post_data(self.img2img_url, body) as response:
            if response.status != 200:
                QtWidgets.QMessageBox.error(None, f"Server responded with error {response.status}",
                                            response.read().decode('utf-8'))
                return

            response_json = json.loads(response.read())
            base64_response_image = response_json['base64_image']
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_file.write(base64.b64decode(base64_response_image.encode('utf8')))

            import_to_selection(selection, tmp_file.name)
            os.remove(tmp_file.name)

    def inpainting(self):
        KritaDiffusionDocker.initialize()

        inst = Krita.instance()
        active_doc = inst.activeDocument()
        selection = active_doc.selection()

        if not is_selection_valid(selection):
            QtWidgets.QMessageBox.error(None, f"Error", "No active selection")
            return

        if self.inpainting_dialogue is None:
            self.inpainting_dialogue = InputDialog({
                'prompt': MultilineInputValue(placeholder='A snake in a grass', label='Prompt'),
                'sampling_steps': TextInputValue(value=str(25), label='Steps'),
                'cfg': TextInputValue(value=str(7), label='CFG'),
                'seed': TextInputValue(value=str(-1), label='Seed'),
            })

        base64_request_image = export_selection_to_base64_string(extension='.png')
        body = {
            'width': selection.width(),
            'height': selection.height(),
            'base64_image': base64_request_image
        }

        if not self.inpainting_dialogue.exec_():
            return

        body.update(self.inpainting_dialogue.get_values())

        with post_data(self.inpainting_url, body) as response:
            if response.status != 200:
                QtWidgets.QMessageBox.error(None, f"Server responded with error {response.status}",
                                            response.read().decode('utf-8'))
                return

            response_json = json.loads(response.read())
            base64_response_image = response_json['base64_image']
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tmp_file.write(base64.b64decode(base64_response_image.encode('utf8')))

            import_to_selection(selection, tmp_file.name)
            os.remove(tmp_file.name)

    def canvasChanged(self, canvas):
        pass


def is_selection_valid(selection: Selection) -> bool:
    bad_selection_message = "Nothing selected"
    if selection:
        if selection.width() == 0 or selection.height() == 0:
            QtWidgets.QMessageBox.warning(None, "Warning", bad_selection_message)
            return False
    else:
        QtWidgets.QMessageBox.warning(None, "Warning", bad_selection_message)
        return False

    return True


def get_all_sub_nodes(node):
    for subnode in node.childNodes():
        yield subnode

        for subsub in get_all_sub_nodes(subnode):
            yield subsub


def get_selection_onscreen_extents(selection: Selection) -> Tuple[float, float, float, float]:
    x = max(0, selection.x())
    y = max(0, selection.y())
    width = selection.width() + min(0, selection.x())
    height = selection.height() + min(0, selection.y())
    return x, y, width, height


def add_new_node():
    inst = Krita.instance()
    active_doc = inst.activeDocument()
    nodes_before = list(get_all_sub_nodes(active_doc.rootNode()))
    inst.action('add_new_paint_layer').trigger()
    active_doc.waitForDone()
    nodes_after = list(get_all_sub_nodes(active_doc.rootNode()))
    new_nodes = list([node for node in nodes_after if node not in nodes_before])
    assert len(new_nodes) == 1, 'add_new_paint_layer should have add a single node'
    the_new_node = new_nodes[0]
    return the_new_node


def import_base64_string_to_selection(selection, base64_string: str, extension='.jpg') -> bool:
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
            tmp_file.write(base64.b64decode(base64_string.encode('utf8')))
        result = import_to_selection(selection, tmp_file.name)
        os.remove(tmp_file.name)
        return result
    except Exception as e:
        print(e)
        return False


def import_to_selection(selection, filename) -> bool:
    inst = Krita.instance()
    active_doc = inst.activeDocument()

    import_doc = inst.openDocument(filename)

    if import_doc is None:
        return False

    import_doc.setBatchmode(True)
    import_doc_selection = Selection()
    import_doc_selection.select(0, 0, import_doc.width(), import_doc.height(), 255)
    import_doc_selection.copy(import_doc.topLevelNodes()[0])
    import_doc.close()

    import_doc_selection.clear()
    import_doc_selection.select(0, 0, selection.width() + selection.x(), selection.height() + selection.y(), 255)
    new_node = add_new_node()
    import_doc_selection.paste(new_node, selection.x(), selection.y())
    new_node.mergeDown()
    active_doc.refreshProjection()
    return True


def export_selection_to_base64_string(extension='.jpg') -> str:
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
        pass

    if not export_selection(tmp_file.name):
        return None

    with open(tmp_file.name, "rb") as image_file:
        encoded_image_string = base64.b64encode(image_file.read()).decode('utf-8')

    os.remove(tmp_file.name)
    return encoded_image_string


def export_selection(filename) -> bool:
    inst = Krita.instance()
    active_doc = inst.activeDocument()
    selection = active_doc.selection()
    if not is_selection_valid(selection):
        return False

    pixel_data = active_doc.pixelData(selection.x(), selection.y(), selection.width(), selection.height())

    export_doc = inst.createDocument(selection.width(), selection.height(), str(uuid.uuid4()), active_doc.colorModel(),
                                     active_doc.colorDepth(), active_doc.colorProfile(), active_doc.resolution())
    export_doc.setBatchmode(True)
    export_doc_layer = export_doc.topLevelNodes()[0]
    export_doc_layer.setOpacity(255)
    export_doc_layer.setPixelData(pixel_data, 0, 0, export_doc.width(), export_doc.height())
    export_doc.saveAs(filename)
    export_doc.close()
    return True


class InputValue:
    def __init__(self, value=None, label=''):
        self.value = value
        self.label = label

    def construct_widget(self):
        raise NotImplementedError

    def get_value(self, widget):
        raise NotImplementedError


class MultilineInputValue(InputValue):
    def __init__(self, value=None, label='', placeholder=None):
        super().__init__(value=value, label=label)
        self.placeholder = placeholder

    def construct_widget(self):
        widget = QtWidgets.QTextEdit()
        if self.placeholder is not None:
            widget.setPlaceholderText(self.placeholder)
        if self.value is not None:
            widget.setText(self.value)
        return widget

    def get_value(self, widget):
        return widget.toPlainText()


class TextInputValue(InputValue):
    def __init__(self, value=None, label='', placeholder=None):
        super().__init__(value=value, label=label)
        self.placeholder = placeholder

    def construct_widget(self):
        widget = QtWidgets.QLineEdit()
        if self.placeholder is not None:
            widget.setPlaceholderText(self.placeholder)
        if self.value is not None:
            widget.setText(self.value)
        return widget

    def get_value(self, widget):
        return widget.displayText()


class InputDialog(QtWidgets.QDialog):
    def __init__(self, inputs_dict):
        super().__init__()

        self.inputs_dict = inputs_dict

        self.setWindowTitle("Parameters")

        self.layout = QtWidgets.QFormLayout()
        self.inputs = {}
        for field, inp in self.inputs_dict.items():
            widget = inp.construct_widget()
            self.layout.addRow(inp.label, widget)
            self.inputs[field] = (inp, widget)

        q_btn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

        self.buttonBox = QtWidgets.QDialogButtonBox(q_btn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)

    def get_values(self):
        result = {}
        for field, inp_widget in self.inputs.items():
            inp, widget = inp_widget
            result[field] = inp.get_value(widget)
        return result


def post_data(url: str, data: dict):
    req = urllib.request.Request(url)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    response = urllib.request.urlopen(req, json.dumps(data).encode('utf-8'))
    return response


def refresh_projection():
    Krita.instance().activeDocument().waitForDone()
    Krita.instance().activeDocument().refreshProjection()
