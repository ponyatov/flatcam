
from PyQt6 import QtGui, QtWidgets
from appTool import AppToolEditor
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, NumericalEvalEntry, RadioSet, \
    FCSpinner, FCDoubleSpinner

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class CopyEditorTool(AppToolEditor):
    """
    Simple input for buffer distance.
    """

    def __init__(self, app, draw_app, plugin_name):
        AppToolEditor.__init__(self, app)

        self.draw_app = draw_app
        self.decimals = app.decimals
        self.plugin_name = plugin_name

        self.ui = CopyEditorUI(layout=self.layout, copy_class=self, plugin_name=plugin_name)

        self.connect_signals_at_init()
        self.set_tool_ui()

    def connect_signals_at_init(self):
        # Signals
        self.ui.clear_btn.clicked.connect(self.on_clear)

    def disconnect_signals(self):
        # Signals
        try:
            self.ui.clear_btn.clicked.disconnect()
        except (TypeError, AttributeError):
            pass

    def run(self):
        self.app.defaults.report_usage("Geo Editor CopyTool()")
        AppToolEditor.run(self)

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
        self.length = 0.0
        self.ui.mode_radio.set_value('n')
        self.ui.on_copy_mode(self.ui.mode_radio.get_value())
        self.ui.array_type_radio.set_value('linear')
        self.ui.on_array_type_radio(self.ui.array_type_radio.get_value())
        self.ui.axis_radio.set_value('X')
        self.ui.on_linear_angle_radio(self.ui.axis_radio.get_value())

        self.ui.array_dir_radio.set_value('CW')

        self.ui.placement_radio.set_value('s')
        self.ui.on_placement_radio(self.ui.placement_radio.get_value())

        self.ui.spacing_rows.set_value(0)
        self.ui.spacing_columns.set_value(0)
        self.ui.rows.set_value(1)
        self.ui.columns.set_value(1)
        self.ui.offsetx_entry.set_value(0)
        self.ui.offsety_entry.set_value(0)

    def on_tab_close(self):
        self.disconnect_signals()
        self.hide_tool()
        # self.app.ui.notebook.callback_on_close = lambda: None

    def on_clear(self):
        self.set_tool_ui()

    @property
    def length(self):
        return self.ui.project_line_entry.get_value()

    @length.setter
    def length(self, val):
        self.ui.project_line_entry.set_value(val)

    def hide_tool(self):
        self.ui.copy_frame.hide()
        self.app.ui.notebook.setCurrentWidget(self.app.ui.properties_tab)
        if self.draw_app.active_tool.name != 'select':
            self.draw_app.select_tool("select")


class CopyEditorUI:

    def __init__(self, layout, copy_class, plugin_name):
        self.pluginName = plugin_name
        self.copy_class = copy_class
        self.decimals = self.copy_class.app.decimals
        self.layout = layout
        self.app = self.copy_class.app

        # Title
        title_label = FCLabel("%s" % ('Editor ' + self.pluginName), size=16, bold=True)
        self.layout.addWidget(title_label)

        # this way I can hide/show the frame
        self.copy_frame = QtWidgets.QFrame()
        self.copy_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.copy_frame)
        self.copy_tool_box = QtWidgets.QVBoxLayout()
        self.copy_tool_box.setContentsMargins(0, 0, 0, 0)
        self.copy_frame.setLayout(self.copy_tool_box)

        # Grid Layout
        grid0 = GLay(v_spacing=5, h_spacing=3)
        self.copy_tool_box.addLayout(grid0)

        # Project distance
        self.project_line_lbl = FCLabel('%s:' % _("Projection"))
        self.project_line_lbl.setToolTip(
            _("Length of the current segment/move.")
        )
        self.project_line_entry = NumericalEvalEntry(border_color='#0069A9')
        grid0.addWidget(self.project_line_lbl, 0, 0)
        grid0.addWidget(self.project_line_entry, 0, 1)

        self.clear_btn = FCButton(_("Clear"))
        grid0.addWidget(self.clear_btn, 2, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid0.addWidget(separator_line, 4, 0, 1, 2)

        # Type of Array
        self.mode_label = FCLabel('%s:' % _("Mode"), bold=True)
        self.mode_label.setToolTip(
            _("Single copy or special (array of copies)")
        )
        self.mode_radio = RadioSet([
            {'label': _('Single'), 'value': 'n'},
            {'label': _('Array'), 'value': 'a'}
        ])

        grid0.addWidget(self.mode_label, 6, 0)
        grid0.addWidget(self.mode_radio, 6, 1)

        # #############################################################################################################
        # ######################################## Add Array ##########################################################
        # #############################################################################################################
        # add a frame and inside add a grid box layout.
        self.array_frame = FCFrame()
        # self.array_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.array_frame)

        self.array_grid = GLay(v_spacing=5, h_spacing=3)
        # self.array_grid.setContentsMargins(0, 0, 0, 0)
        self.array_frame.setLayout(self.array_grid)

        # Set the number of items in the array
        self.array_size_label = FCLabel('%s:' % _('Size'))
        self.array_size_label.setToolTip(_("Specify how many items to be in the array."))

        self.array_size_entry = FCSpinner(policy=False)
        self.array_size_entry.set_range(1, 100000)

        self.array_grid.addWidget(self.array_size_label, 2, 0)
        self.array_grid.addWidget(self.array_size_entry, 2, 1)

        # Array Type
        array_type_lbl = FCLabel('%s:' % _("Type"))
        array_type_lbl.setToolTip(
            _("Select the type of array to create.\n"
              "It can be Linear X(Y) or Circular")
        )

        self.array_type_radio = RadioSet([
            {'label': _('Linear'), 'value': 'linear'},
            {'label': _('2D'), 'value': '2D'},
            {'label': _('Circular'), 'value': 'circular'}
        ])

        self.array_grid.addWidget(array_type_lbl, 4, 0)
        self.array_grid.addWidget(self.array_type_radio, 4, 1)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.array_grid.addWidget(separator_line, 6, 0, 1, 2)

        # #############################################################################################################
        # ############################ LINEAR Array ###################################################################
        # #############################################################################################################
        self.array_linear_frame = QtWidgets.QFrame()
        self.array_linear_frame.setContentsMargins(0, 0, 0, 0)
        self.array_grid.addWidget(self.array_linear_frame, 8, 0, 1, 2)

        self.lin_grid = GLay(v_spacing=5, h_spacing=3)
        self.lin_grid.setContentsMargins(0, 0, 0, 0)
        self.array_linear_frame.setLayout(self.lin_grid)

        # Linear Drill Array direction
        self.axis_label = FCLabel('%s:' % _('Direction'))
        self.axis_label.setToolTip(
            _("Direction on which the linear array is oriented:\n"
              "- 'X' - horizontal axis \n"
              "- 'Y' - vertical axis or \n"
              "- 'Angle' - a custom angle for the array inclination")
        )

        self.axis_radio = RadioSet([
            {'label': _('X'), 'value': 'X'},
            {'label': _('Y'), 'value': 'Y'},
            {'label': _('Angle'), 'value': 'A'}
        ])

        self.lin_grid.addWidget(self.axis_label, 0, 0)
        self.lin_grid.addWidget(self.axis_radio, 0, 1)

        # Linear Array pitch distance
        self.pitch_label = FCLabel('%s:' % _('Pitch'))
        self.pitch_label.setToolTip(
            _("Pitch = Distance between elements of the array.")
        )

        self.pitch_entry = FCDoubleSpinner(policy=False)
        self.pitch_entry.set_precision(self.decimals)
        self.pitch_entry.set_range(0.0000, 10000.0000)

        self.lin_grid.addWidget(self.pitch_label, 2, 0)
        self.lin_grid.addWidget(self.pitch_entry, 2, 1)

        # Linear Array angle
        self.linear_angle_label = FCLabel('%s:' % _('Angle'))
        self.linear_angle_label.setToolTip(
            _("Angle at which the linear array is placed.\n"
              "The precision is of max 2 decimals.\n"
              "Min value is: -360.00 degrees.\n"
              "Max value is: 360.00 degrees.")
        )

        self.linear_angle_spinner = FCDoubleSpinner(policy=False)
        self.linear_angle_spinner.set_precision(self.decimals)
        self.linear_angle_spinner.setSingleStep(1.0)
        self.linear_angle_spinner.setRange(-360.00, 360.00)

        self.lin_grid.addWidget(self.linear_angle_label, 4, 0)
        self.lin_grid.addWidget(self.linear_angle_spinner, 4, 1)

        # #############################################################################################################
        # ################################ 2D Array ###################################################################
        # #############################################################################################################
        self.two_dim_array_frame = QtWidgets.QFrame()
        self.two_dim_array_frame.setContentsMargins(0, 0, 0, 0)
        self.array_grid.addWidget(self.two_dim_array_frame, 10, 0, 1, 2)

        self.dd_grid = GLay(v_spacing=5, h_spacing=3)
        self.dd_grid.setContentsMargins(0, 0, 0, 0)
        self.two_dim_array_frame.setLayout(self.dd_grid)

        # 2D placement
        self.place_label = FCLabel('%s:' % _('Placement'))
        self.place_label.setToolTip(
            _("Placement of array items:\n"
              "'Spacing' - define space between rows and columns \n"
              "'Offset' - each row (and column) will be placed at a multiple of a value, from origin")
        )

        self.placement_radio = RadioSet([
            {'label': _('Spacing'), 'value': 's'},
            {'label': _('Offset'), 'value': 'o'}
        ])

        self.dd_grid.addWidget(self.place_label, 0, 0)
        self.dd_grid.addWidget(self.placement_radio, 0, 1)

        # Rows
        self.rows = FCSpinner(callback=self.confirmation_message_int)
        self.rows.set_range(0, 10000)

        self.rows_label = FCLabel('%s:' % _("Rows"))
        self.rows_label.setToolTip(
            _("Number of rows")
        )
        self.dd_grid.addWidget(self.rows_label, 2, 0)
        self.dd_grid.addWidget(self.rows, 2, 1)

        # Columns
        self.columns = FCSpinner(callback=self.confirmation_message_int)
        self.columns.set_range(0, 10000)

        self.columns_label = FCLabel('%s:' % _("Columns"))
        self.columns_label.setToolTip(
            _("Number of columns")
        )
        self.dd_grid.addWidget(self.columns_label, 4, 0)
        self.dd_grid.addWidget(self.columns, 4, 1)

        # ------------------------------------------------
        # ##############  Spacing Frame  #################
        # ------------------------------------------------
        self.spacing_frame = QtWidgets.QFrame()
        self.spacing_frame.setContentsMargins(0, 0, 0, 0)
        self.dd_grid.addWidget(self.spacing_frame, 6, 0, 1, 2)

        self.s_grid = GLay(v_spacing=5, h_spacing=3)
        self.s_grid.setContentsMargins(0, 0, 0, 0)
        self.spacing_frame.setLayout(self.s_grid)

        # Spacing Rows
        self.spacing_rows = FCDoubleSpinner(callback=self.confirmation_message)
        self.spacing_rows.set_range(0, 9999)
        self.spacing_rows.set_precision(4)

        self.spacing_rows_label = FCLabel('%s:' % _("Spacing rows"))
        self.spacing_rows_label.setToolTip(
            _("Spacing between rows.\n"
              "In current units.")
        )
        self.s_grid.addWidget(self.spacing_rows_label, 0, 0)
        self.s_grid.addWidget(self.spacing_rows, 0, 1)

        # Spacing Columns
        self.spacing_columns = FCDoubleSpinner(callback=self.confirmation_message)
        self.spacing_columns.set_range(0, 9999)
        self.spacing_columns.set_precision(4)

        self.spacing_columns_label = FCLabel('%s:' % _("Spacing cols"))
        self.spacing_columns_label.setToolTip(
            _("Spacing between columns.\n"
              "In current units.")
        )
        self.s_grid.addWidget(self.spacing_columns_label, 2, 0)
        self.s_grid.addWidget(self.spacing_columns, 2, 1)

        # ------------------------------------------------
        # ##############  Offset Frame  ##################
        # ------------------------------------------------
        self.offset_frame = QtWidgets.QFrame()
        self.offset_frame.setContentsMargins(0, 0, 0, 0)
        self.dd_grid.addWidget(self.offset_frame, 8, 0, 1, 2)

        self.o_grid = GLay(v_spacing=5, h_spacing=3)
        self.o_grid.setContentsMargins(0, 0, 0, 0)
        self.offset_frame.setLayout(self.o_grid)

        # Offset X Value
        self.offsetx_label = FCLabel('%s X:' % _("Offset"))
        self.offsetx_label.setToolTip(
            _("'Offset' - each row (and column) will be placed at a multiple of a value, from origin")
        )

        self.offsetx_entry = FCDoubleSpinner(policy=False)
        self.offsetx_entry.set_precision(self.decimals)
        self.offsetx_entry.set_range(0.0000, 10000.0000)

        self.o_grid.addWidget(self.offsetx_label, 0, 0)
        self.o_grid.addWidget(self.offsetx_entry, 0, 1)

        # Offset Y Value
        self.offsety_label = FCLabel('%s Y:' % _("Offset"))
        self.offsety_label.setToolTip(
            _("'Offset' - each row (and column) will be placed at a multiple of a value, from origin")
        )

        self.offsety_entry = FCDoubleSpinner(policy=False)
        self.offsety_entry.set_precision(self.decimals)
        self.offsety_entry.set_range(0.0000, 10000.0000)

        self.o_grid.addWidget(self.offsety_label, 2, 0)
        self.o_grid.addWidget(self.offsety_entry, 2, 1)

        # #############################################################################################################
        # ############################ CIRCULAR Array #################################################################
        # #############################################################################################################
        self.array_circular_frame = QtWidgets.QFrame()
        self.array_circular_frame.setContentsMargins(0, 0, 0, 0)
        self.array_grid.addWidget(self.array_circular_frame, 12, 0, 1, 2)

        self.circ_grid = GLay(v_spacing=5, h_spacing=3)
        self.circ_grid.setContentsMargins(0, 0, 0, 0)
        self.array_circular_frame.setLayout(self.circ_grid)

        # Array Direction
        self.array_dir_lbl = FCLabel('%s:' % _('Direction'))
        self.array_dir_lbl.setToolTip(
            _("Direction for circular array.\n"
              "Can be CW = clockwise or CCW = counter clockwise."))

        self.array_dir_radio = RadioSet([
            {'label': _('CW'), 'value': 'CW'},
            {'label': _('CCW'), 'value': 'CCW'}])

        self.circ_grid.addWidget(self.array_dir_lbl, 0, 0)
        self.circ_grid.addWidget(self.array_dir_radio, 0, 1)

        # Array Angle
        self.array_angle_lbl = FCLabel('%s:' % _('Angle'))
        self.array_angle_lbl.setToolTip(_("Angle at which each element in circular array is placed."))

        self.angle_entry = FCDoubleSpinner(policy=False)
        self.angle_entry.set_precision(self.decimals)
        self.angle_entry.setSingleStep(1.0)
        self.angle_entry.setRange(-360.00, 360.00)

        self.circ_grid.addWidget(self.array_angle_lbl, 2, 0)
        self.circ_grid.addWidget(self.angle_entry, 2, 1)

        # Buttons
        self.add_button = FCButton(_("Add"))
        self.add_button.setIcon(QtGui.QIcon(self.app.resource_location + '/plus16.png'))
        self.layout.addWidget(self.add_button)

        GLay.set_common_column_size([
            grid0, self.array_grid, self.lin_grid, self.dd_grid, self.circ_grid, self.s_grid, self.o_grid
        ], 0)

        self.layout.addStretch(1)

        # Signals
        self.mode_radio.activated_custom.connect(self.on_copy_mode)
        self.array_type_radio.activated_custom.connect(self.on_array_type_radio)
        self.axis_radio.activated_custom.connect(self.on_linear_angle_radio)
        self.placement_radio.activated_custom.connect(self.on_placement_radio)

    def confirmation_message(self, accepted, minval, maxval):
        if accepted is False:
            self.app.inform[str, bool].emit('[WARNING_NOTCL] %s: [%.*f, %.*f]' % (_("Edited value is out of range"),
                                                                                  self.decimals,
                                                                                  minval,
                                                                                  self.decimals,
                                                                                  maxval), False)

    def confirmation_message_int(self, accepted, minval, maxval):
        if accepted is False:
            self.app.inform[str, bool].emit('[WARNING_NOTCL] %s: [%d, %d]' %
                                            (_("Edited value is out of range"), minval, maxval), False)

    def on_copy_mode(self, val):
        if val == 'n':
            self.array_frame.hide()
            self.app.inform.emit(_("Click on reference location ..."))
        else:
            self.array_frame.show()

    def on_array_type_radio(self, val):
        if val == '2D':
            self.array_circular_frame.hide()
            self.array_linear_frame.hide()
            self.two_dim_array_frame.show()
            if self.placement_radio.get_value() == 's':
                self.spacing_frame.show()
                self.offset_frame.hide()
            else:
                self.spacing_frame.hide()
                self.offset_frame.show()

            self.array_size_entry.setDisabled(True)
            self.on_rows_cols_value_changed()

            self.rows.valueChanged.connect(self.on_rows_cols_value_changed)
            self.columns.valueChanged.connect(self.on_rows_cols_value_changed)

            self.app.inform.emit(_("Click on reference location ..."))
        else:
            if val == 'linear':
                self.array_circular_frame.hide()
                self.array_linear_frame.show()
                self.two_dim_array_frame.hide()
                self.spacing_frame.hide()
                self.offset_frame.hide()

                self.app.inform.emit(_("Click on reference location ..."))
            else:   # 'circular'
                self.array_circular_frame.show()
                self.array_linear_frame.hide()
                self.two_dim_array_frame.hide()
                self.spacing_frame.hide()
                self.offset_frame.hide()

                self.app.inform.emit(_("Click on the circular array Center position"))

            self.array_size_entry.setDisabled(False)
            try:
                self.rows.valueChanged.disconnect()
            except (TypeError, AttributeError):
                pass

            try:
                self.columns.valueChanged.disconnect()
            except (TypeError, AttributeError):
                pass

    def on_rows_cols_value_changed(self):
        new_size = self.rows.get_value() * self.columns.get_value()
        if new_size == 0:
            new_size = 1
        self.array_size_entry.set_value(new_size)

    def on_linear_angle_radio(self, val):
        if val == 'A':
            self.linear_angle_spinner.show()
            self.linear_angle_label.show()
        else:
            self.linear_angle_spinner.hide()
            self.linear_angle_label.hide()

    def on_placement_radio(self, val):
        if val == 's':
            self.spacing_frame.show()
            self.offset_frame.hide()
        else:
            self.spacing_frame.hide()
            self.offset_frame.show()
