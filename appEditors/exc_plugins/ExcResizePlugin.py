
from PyQt6 import QtGui, QtWidgets
from appTool import AppToolEditor
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, GLay, FCFrame, NumericalEvalEntry, \
    FCDoubleSpinner
import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class ExcResizeEditorTool(AppToolEditor):
    """
    Simple input for buffer distance.
    """

    def __init__(self, app, draw_app, plugin_name):
        AppToolEditor.__init__(self, app)

        self.draw_app = draw_app
        self.decimals = app.decimals
        self.plugin_name = plugin_name

        self.ui = ExcResizeEditorUI(layout=self.layout, resize_class=self, plugin_name=plugin_name)

        self.connect_signals_at_init()
        self.set_tool_ui()

    def connect_signals_at_init(self):
        # Signals
        self.ui.clear_btn.clicked.connect(lambda: self.ui.res_dia_entry.set_value(0.0))

    def disconnect_signals(self):
        # Signals
        try:
            self.ui.clear_btn.clicked.disconnect()
        except (TypeError, AttributeError):
            pass

    def run(self):
        self.app.defaults.report_usage("Geo Editor ToolPath()")
        super().run()

        # if the splitter us hidden, display it
        if self.app.ui.splitter.sizes()[0] == 0:
            self.app.ui.splitter.setSizes([1, 1])

        # if the Tool Tab is hidden display it, else hide it but only if the objectName is the same
        found_idx = None
        for idx in range(self.app.ui.notebook.count()):
            if self.app.ui.notebook.widget(idx).objectName() == "plugin_tab":
                found_idx = idx
                break
        # show the Tab
        if not found_idx:
            try:
                self.app.ui.notebook.addTab(self.app.ui.plugin_tab, _("Plugin"))
            except RuntimeError:
                self.app.ui.plugin_tab = QtWidgets.QWidget()
                self.app.ui.plugin_tab.setObjectName("plugin_tab")
                self.app.ui.plugin_tab_layout = QtWidgets.QVBoxLayout(self.app.ui.plugin_tab)
                self.app.ui.plugin_tab_layout.setContentsMargins(2, 2, 2, 2)

                self.app.ui.plugin_scroll_area = VerticalScrollArea()
                self.app.ui.plugin_tab_layout.addWidget(self.app.ui.plugin_scroll_area)
                self.app.ui.notebook.addTab(self.app.ui.plugin_tab, _("Plugin"))

            # focus on Tool Tab
            self.app.ui.notebook.setCurrentWidget(self.app.ui.plugin_tab)

        # self.app.ui.notebook.callback_on_close = self.on_tab_close

        self.app.ui.notebook.setTabText(2, self.plugin_name)

    def set_tool_ui(self):
        # Init appGUI
        pass

    def on_tab_close(self):
        self.disconnect_signals()
        self.hide_tool()
        # self.app.ui.notebook.callback_on_close = lambda: None

    def on_clear(self):
        self.set_tool_ui()

    def hide_tool(self):
        self.ui.tool_frame.hide()
        self.app.ui.notebook.setCurrentWidget(self.app.ui.properties_tab)
        if self.draw_app.active_tool.name != 'select':
            self.draw_app.select_tool("select")


class ExcResizeEditorUI:

    def __init__(self, layout, resize_class, plugin_name):
        self.pluginName = plugin_name
        self.ed_class = resize_class
        self.decimals = self.ed_class.app.decimals
        self.layout = layout

        # Title
        title_label = FCLabel("%s" % ('Editor ' + self.pluginName), size=16, bold=True)
        self.layout.addWidget(title_label)

        # this way I can hide/show the frame
        self.tool_frame = QtWidgets.QFrame()
        self.tool_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.tool_frame)
        self.editor_vbox = QtWidgets.QVBoxLayout()
        self.editor_vbox.setContentsMargins(0, 0, 0, 0)
        self.tool_frame.setLayout(self.editor_vbox)

        # Tool Diameter
        self.tool_lbl = FCLabel('%s' % _("Tool Diameter"), bold=True, color='blue')
        self.editor_vbox.addWidget(self.tool_lbl)
        # #############################################################################################################
        # Diameter Frame
        # #############################################################################################################
        dia_frame = FCFrame()
        self.editor_vbox.addWidget(dia_frame)

        dia_grid = GLay(v_spacing=5, h_spacing=3, c_stretch=[0, 1, 0])
        dia_frame.setLayout(dia_grid)

        # Dia Value
        self.dia_lbl = FCLabel('%s:' % _("Value"))
        self.dia_entry = NumericalEvalEntry(border_color='#0069A9')
        self.dia_entry.setDisabled(True)
        self.dia_unit = FCLabel('%s' % 'mm')

        dia_grid.addWidget(self.dia_lbl, 0, 0)
        dia_grid.addWidget(self.dia_entry, 0, 1)
        dia_grid.addWidget(self.dia_unit, 0, 2)

        # #############################################################################################################
        # Resize Frame
        # #############################################################################################################
        resize_frame = FCFrame()
        self.editor_vbox.addWidget(resize_frame)

        resize_grid = GLay(v_spacing=5, h_spacing=3, c_stretch=[0, 1, 0])
        resize_frame.setLayout(resize_grid)

        # Resize Diameter
        self.res_dia_lbl = FCLabel('%s %s:' % (_("Resize"), _("Value").lower()))
        self.res_dia_lbl.setToolTip(
            _("Diameter to resize to.")
        )
        self.res_dia_entry = FCDoubleSpinner(policy=False)
        self.res_dia_entry.set_precision(self.decimals)
        self.res_dia_entry.set_range(0.0000, 10000.0000)

        resize_grid.addWidget(self.res_dia_lbl, 0, 0)
        resize_grid.addWidget(self.res_dia_entry, 0, 1)

        self.clear_btn = QtWidgets.QToolButton()
        self.clear_btn.setIcon(QtGui.QIcon(self.ed_class.app.resource_location + '/trash32.png'))
        resize_grid.addWidget(self.clear_btn, 0, 2)

        self.resize_btn = FCButton(_("Resize"))
        self.resize_btn.setToolTip(
            _("Resize a drill or a selection of drills.")
        )
        self.resize_btn.setIcon(QtGui.QIcon(self.ed_class.app.resource_location + '/resize16.png'))
        self.editor_vbox.addWidget(self.resize_btn)

        GLay.set_common_column_size([dia_grid, resize_grid], 0)
        self.layout.addStretch(1)
