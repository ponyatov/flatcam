# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 1/24/2020                                          #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCComboBox, FCCheckBox, \
    RadioSet, FCDoubleSpinner, FCTable

from matplotlib.backend_bases import KeyEvent as mpl_key_event

import logging
from copy import deepcopy

from shapely import Point, MultiPolygon
from shapely.ops import unary_union

import gettext
import appTranslation as fcTranslate
import builtins

from appParsers.ParseGerber import Gerber
from camlib import Geometry

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolPunchGerber(AppTool, Gerber):

    def __init__(self, app):
        AppTool.__init__(self, app)
        Geometry.__init__(self, geo_steps_per_circle=self.app.options["geometry_circle_steps"])

        self.app = app
        self.decimals = self.app.decimals
        self.units = self.app.app_units

        # store here the old object name
        self.old_name = ''

        # Target Gerber object
        self.grb_obj = None

        self.mm = None
        self.mp = None
        self.mr = None
        self.kp = None
        
        # store here if the grid snapping is active
        self.grid_status_memory = False

        self.poly_sel_disconnect_flag = False

        # dict to store the pads selected for displaying; key is the shape added to be plotted and value is the poly
        self.poly_dict = {}

        # list of dicts to store the selection result in the manual selection
        self.manual_pads = []

        # remember to restore this if we want the selection shape to work
        self.old_selection_status = None

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = PunchUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

    def on_object_combo_changed(self):
        punch_plugin_found = False
        for idx in range(self.app.ui.notebook.count()):
            if self.app.ui.notebook.tabText(idx) == _("Punch Gerber"):
                punch_plugin_found = True
                break

        if punch_plugin_found is False:
            return

        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            grb_obj = model_index.internalPointer().obj
        except Exception:
            return

        if self.old_name != '':
            old_obj = self.app.collection.get_by_name(self.old_name)
            if old_obj:
                old_obj.clear_plot_apertures()
                old_obj.mark_shapes.enabled = False

        # enable mark shapes
        if grb_obj:
            grb_obj.mark_shapes.enabled = True

            # create storage for shapes
            for ap_code in grb_obj.tools:
                grb_obj.mark_shapes_storage[ap_code] = []

            self.old_name = grb_obj.obj_options['name']

        self.build_tool_ui()

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolPunchGerber()")

        if toggle:
            # if the splitter is hidden, display it
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

            try:
                if self.app.ui.plugin_scroll_area.widget().objectName() == self.pluginName and found_idx:
                    # if the Tool Tab is not focused, focus on it
                    if not self.app.ui.notebook.currentWidget() is self.app.ui.plugin_tab:
                        # focus on Tool Tab
                        self.app.ui.notebook.setCurrentWidget(self.app.ui.plugin_tab)
                    else:
                        # else remove the Tool Tab
                        self.app.ui.notebook.setCurrentWidget(self.app.ui.properties_tab)
                        self.app.ui.notebook.removeTab(2)

                        # if there are no objects loaded in the app then hide the Notebook widget
                        if not self.app.collection.get_list():
                            self.app.ui.splitter.setSizes([0, 1])
            except AttributeError:
                pass
        else:
            if self.app.ui.splitter.sizes()[0] == 0:
                self.app.ui.splitter.setSizes([1, 1])

        super().run()

        self.set_tool_ui()
        self.build_tool_ui()

        # trigger this once at plugin launch
        self.on_object_combo_changed()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='Alt+H', **kwargs)

    def connect_signals_at_init(self):
        self.ui.level.toggled.connect(self.on_level_changed)
        self.ui.method_punch.activated_custom.connect(self.on_method)
        self.ui.reset_button.clicked.connect(self.set_tool_ui)
        self.ui.punch_object_button.clicked.connect(self.on_punch_object_click)

        self.ui.circular_cb.stateChanged.connect(
            lambda state:
                self.ui.circular_ring_entry.setDisabled(False) if state else
                self.ui.circular_ring_entry.setDisabled(True)
        )

        self.ui.oblong_cb.stateChanged.connect(
            lambda state:
            self.ui.oblong_ring_entry.setDisabled(False) if state else self.ui.oblong_ring_entry.setDisabled(True)
        )

        self.ui.square_cb.stateChanged.connect(
            lambda state:
            self.ui.square_ring_entry.setDisabled(False) if state else self.ui.square_ring_entry.setDisabled(True)
        )

        self.ui.rectangular_cb.stateChanged.connect(
            lambda state:
            self.ui.rectangular_ring_entry.setDisabled(False) if state else
            self.ui.rectangular_ring_entry.setDisabled(True)
        )

        self.ui.other_cb.stateChanged.connect(
            lambda state:
            self.ui.other_ring_entry.setDisabled(False) if state else self.ui.other_ring_entry.setDisabled(True)
        )

        self.ui.circular_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.oblong_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.square_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.rectangular_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.other_cb.stateChanged.connect(self.build_tool_ui)

        self.ui.gerber_object_combo.currentIndexChanged.connect(self.on_object_combo_changed)

        self.ui.punch_type_radio.activated_custom.connect(self.on_punch_type)
        self.ui.sel_all_btn.clicked.connect(self.on_manual_sel_all)
        self.ui.clear_all_btn.clicked.connect(self.on_manual_clear_all)

    def set_tool_ui(self):
        self.clear_ui(self.layout)
        self.ui = PunchUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        self.reset_fields()

        self.ui_disconnect()
        self.ui_connect()
        self.ui.method_punch.set_value(self.app.options["tools_punch_hole_type"])
        self.ui.select_all_cb.set_value(False)

        self.ui.dia_entry.set_value(float(self.app.options["tools_punch_hole_fixed_dia"]))

        self.ui.circular_ring_entry.set_value(float(self.app.options["tools_punch_circular_ring"]))
        self.ui.oblong_ring_entry.set_value(float(self.app.options["tools_punch_oblong_ring"]))
        self.ui.square_ring_entry.set_value(float(self.app.options["tools_punch_square_ring"]))
        self.ui.rectangular_ring_entry.set_value(float(self.app.options["tools_punch_rectangular_ring"]))
        self.ui.other_ring_entry.set_value(float(self.app.options["tools_punch_others_ring"]))

        self.ui.circular_cb.set_value(self.app.options["tools_punch_circular"])
        self.ui.oblong_cb.set_value(self.app.options["tools_punch_oblong"])
        self.ui.square_cb.set_value(self.app.options["tools_punch_square"])
        self.ui.rectangular_cb.set_value(self.app.options["tools_punch_rectangular"])
        self.ui.other_cb.set_value(self.app.options["tools_punch_others"])

        self.ui.factor_entry.set_value(float(self.app.options["tools_punch_hole_prop_factor"]))

        self.ui.punch_type_radio.set_value("a")
        self.old_selection_status = None

        # list of dicts to store the selection result in the manual selection
        self.manual_pads = []

        # SELECT THE CURRENT OBJECT
        obj = self.app.collection.get_active()
        if obj:
            if obj.kind == 'gerber':
                obj_name = obj.obj_options['name']
                self.ui.gerber_object_combo.set_value(obj_name)
        else:
            # take first available Gerber file, if any
            available_gerber_list = [o for o in self.app.collection.get_list() if o.kind == 'gerber']
            if available_gerber_list:
                obj_name = available_gerber_list[0].obj_options['name']
                self.ui.gerber_object_combo.set_value(obj_name)

        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.change_level(app_mode)

        self.app.ui.notebook.setTabText(2, _("Punch Gerber"))

    def build_tool_ui(self):
        self.ui_disconnect()

        # reset table
        # self.ui.apertures_table.clear()   # this deletes the headers/tooltips too ... not nice!
        self.ui.apertures_table.setRowCount(0)

        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())
        obj = None

        try:
            obj = model_index.internalPointer().obj
            sort = [int(k) for k in obj.tools.keys()]
            sorted_apertures = sorted(sort)
        except Exception:
            # no object loaded
            sorted_apertures = []

        # n = len(sorted_apertures)
        # calculate how many rows to add
        n = 0
        for ap_code in sorted_apertures:
            ap_type = obj.tools[ap_code]['type']

            if ap_type == 'C' and self.ui.circular_cb.get_value() is True:
                n += 1
            if ap_type == 'R':
                if self.ui.square_cb.get_value() is True:
                    n += 1
                elif self.ui.rectangular_cb.get_value() is True:
                    n += 1
            if ap_type == 'O' and self.ui.oblong_cb.get_value() is True:
                n += 1
            if ap_type not in ['C', 'R', 'O'] and self.ui.other_cb.get_value() is True:
                n += 1

        self.ui.apertures_table.setRowCount(n)

        row = 0
        for ap_code in sorted_apertures:
            ap_type = obj.tools[ap_code]['type']
            if ap_type == 'C':
                if self.ui.circular_cb.get_value() is False:
                    continue
            elif ap_type == 'R':
                if self.ui.square_cb.get_value() is True:
                    pass
                elif self.ui.rectangular_cb.get_value() is True:
                    pass
                else:
                    continue
            elif ap_type == 'O':
                if self.ui.oblong_cb.get_value() is False:
                    continue
            elif self.ui.other_cb.get_value() is True:
                pass
            else:
                continue

            # Aperture CODE
            ap_code_item = QtWidgets.QTableWidgetItem(str(ap_code))
            ap_code_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

            # Aperture TYPE
            ap_type_item = QtWidgets.QTableWidgetItem(str(ap_type))
            ap_type_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)

            # Aperture SIZE
            try:
                if obj.tools[ap_code]['size'] is not None:
                    size_val = self.app.dec_format(float(obj.tools[ap_code]['size']), self.decimals)
                    ap_size_item = QtWidgets.QTableWidgetItem(str(size_val))
                else:
                    ap_size_item = QtWidgets.QTableWidgetItem('')
            except KeyError:
                ap_size_item = QtWidgets.QTableWidgetItem('')
            ap_size_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)

            # Aperture MARK Item
            mark_item = FCCheckBox()
            mark_item.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
            # Empty PLOT ITEM
            empty_plot_item = QtWidgets.QTableWidgetItem('')
            empty_plot_item.setFlags(~QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            empty_plot_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)

            self.ui.apertures_table.setItem(row, 0, ap_code_item)  # Aperture Code
            self.ui.apertures_table.setItem(row, 1, ap_type_item)  # Aperture Type
            self.ui.apertures_table.setItem(row, 2, ap_size_item)  # Aperture Dimensions
            self.ui.apertures_table.setItem(row, 3, empty_plot_item)
            self.ui.apertures_table.setCellWidget(row, 3, mark_item)
            # increment row
            row += 1

        self.ui.apertures_table.selectColumn(0)
        self.ui.apertures_table.resizeColumnsToContents()
        self.ui.apertures_table.resizeRowsToContents()

        vertical_header = self.ui.apertures_table.verticalHeader()
        vertical_header.hide()
        # self.ui.apertures_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        horizontal_header = self.ui.apertures_table.horizontalHeader()
        horizontal_header.setMinimumSectionSize(10)
        horizontal_header.setDefaultSectionSize(70)
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
        horizontal_header.resizeSection(3, 17)
        self.ui.apertures_table.setColumnWidth(3, 17)

        self.ui.apertures_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ui.apertures_table.setSortingEnabled(False)
        # self.ui.apertures_table.setMinimumHeight(self.ui.apertures_table.getHeight())
        # self.ui.apertures_table.setMaximumHeight(self.ui.apertures_table.getHeight())

        # make sure you clear the Gerber aperture markings when the table is rebuilt
        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())
        try:
            grb_obj = model_index.internalPointer().obj
        except Exception:
            self.ui_connect()
            return
        grb_obj.clear_plot_apertures()

        self.ui_connect()

    def change_level(self, level):
        """

        :param level:   application level: either 'b' or 'a'
        :type level:    str
        :return:
        """

        if level == 'a':
            self.ui.level.setChecked(True)
        else:
            self.ui.level.setChecked(False)
        self.on_level_changed(self.ui.level.isChecked())

    def on_level_changed(self, checked):
        if not checked:
            self.ui.level.setText('%s' % _('Beginner'))
            self.ui.level.setStyleSheet("""
                                        QToolButton
                                        {
                                            color: green;
                                        }
                                        """)

            # Add Tool section
            self.ui.sel_label.hide()
            self.ui.s_frame.hide()
        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                        QToolButton
                                        {
                                            color: red;
                                        }
                                        """)

            # Add Tool section
            self.ui.sel_label.show()
            self.ui.s_frame.show()

    def on_select_all(self, state):
        self.ui_disconnect()
        if state:
            self.ui.circular_cb.setChecked(True)
            self.ui.oblong_cb.setChecked(True)
            self.ui.square_cb.setChecked(True)
            self.ui.rectangular_cb.setChecked(True)
            self.ui.other_cb.setChecked(True)
        else:
            self.ui.circular_cb.setChecked(False)
            self.ui.oblong_cb.setChecked(False)
            self.ui.square_cb.setChecked(False)
            self.ui.rectangular_cb.setChecked(False)
            self.ui.other_cb.setChecked(False)

            # get the Gerber file who is the source of the punched Gerber
            selection_index = self.ui.gerber_object_combo.currentIndex()
            model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

            try:
                grb_obj = model_index.internalPointer().obj
            except Exception:
                return

            grb_obj.clear_plot_apertures()

        self.ui_connect()

    def on_method(self, val):
        self.ui.exc_label.hide()
        self.ui.exc_combo.hide()
        self.ui.fixed_label.hide()
        self.ui.dia_label.hide()
        self.ui.dia_entry.hide()
        self.ui.ring_frame.hide()
        self.ui.prop_label.hide()
        self.ui.factor_label.hide()
        self.ui.factor_entry.hide()

        if val == 'exc':
            self.ui.exc_label.show()
            self.ui.exc_combo.show()
        elif val == 'fixed':
            self.ui.fixed_label.show()
            self.ui.dia_label.show()
            self.ui.dia_entry.show()
        elif val == 'ring':
            self.ui.ring_frame.show()
        elif val == 'prop':
            self.ui.prop_label.show()
            self.ui.factor_label.show()
            self.ui.factor_entry.show()

    def on_punch_type(self, val):
        if val == 'm':
            self.ui.sel_all_btn.show()
            self.ui.clear_all_btn.show()
        else:
            self.ui.sel_all_btn.hide()
            self.ui.clear_all_btn.hide()

    def ui_connect(self):
        self.ui.select_all_cb.stateChanged.connect(self.on_select_all)

        # Mark Checkboxes
        for row in range(self.ui.apertures_table.rowCount()):
            try:
                wdg = self.ui.apertures_table.cellWidget(row, 3)
                assert isinstance(wdg, FCCheckBox)
                wdg.clicked.disconnect()
            except (TypeError, AttributeError):
                pass
            wdg = self.ui.apertures_table.cellWidget(row, 3)
            assert isinstance(wdg, FCCheckBox)
            wdg.clicked.connect(self.on_mark_cb_click_table)

    def ui_disconnect(self):
        try:
            self.ui.select_all_cb.stateChanged.disconnect()
        except (AttributeError, TypeError):
            pass

        # Mark Checkboxes
        for row in range(self.ui.apertures_table.rowCount()):
            try:
                wdg = self.ui.apertures_table.cellWidget(row, 3)
                assert isinstance(wdg, FCCheckBox)
                wdg.clicked.disconnect()
            except (TypeError, AttributeError):
                pass

    def on_punch_object_click(self):
        punch_type = self.ui.punch_type_radio.get_value()
        punch_method = self.ui.method_punch.get_value()

        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            self.grb_obj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return

        if self.grb_obj is None:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return

        name = self.grb_obj.obj_options['name'].rpartition('.')[0]
        if name == '':
            name = self.grb_obj.obj_options['name']
        outname = name + "_punched"

        if punch_type == 'a':
            if punch_method == 'exc':
                self.on_excellon_method(self.grb_obj, outname)
            elif punch_method == 'fixed':
                self.on_fixed_method(self.grb_obj, outname)
            elif punch_method == 'ring':
                self.on_ring_method(self.grb_obj, outname)
            elif punch_method == 'prop':
                self.on_proportional_method(self.grb_obj, outname)
            self.clear_aperture_marking()
        else:
            if punch_method == 'exc':
                # get the Excellon file whose geometry will create the punch holes
                selection_index = self.ui.exc_combo.currentIndex()
                model_index = self.app.collection.index(selection_index, 0, self.ui.exc_combo.rootModelIndex())

                try:
                    model_index.internalPointer().obj
                except Exception:
                    self.app.inform.emit('[ERROR_NOTCL] %s' % _("There is no Excellon object loaded ..."))
                    return

            # disengage the grid snapping since it may be hard to click on polygons with grid snapping on
            if self.app.ui.grid_snap_btn.isChecked():
                self.grid_status_memory = True
                self.app.ui.grid_snap_btn.trigger()
            else:
                self.grid_status_memory = False

            self.app.inform.emit('[WARNING_NOTCL] %s' % _("Click on a pad to select it."))

            self.mr = self.app.plotcanvas.graph_event_connect('mouse_release', self.on_single_poly_mouse_release)
            self.kp = self.app.plotcanvas.graph_event_connect('key_press', self.on_key_press)

            if self.app.use_3d_engine:
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.app.on_mouse_click_release_over_plot)
                self.app.plotcanvas.graph_event_disconnect('mouse_press', self.app.on_mouse_click_over_plot)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.app.mr)
                self.app.plotcanvas.graph_event_disconnect(self.app.mp)

            # disconnect flags
            self.poly_sel_disconnect_flag = True
            self.app.ui.notebook.setDisabled(True)

            # disable the canvas mouse dragging seelction shape
            self.old_selection_status = deepcopy(self.app.options['global_selection_shape'])
            self.app.options['global_selection_shape'] = False

    def on_excellon_method(self, grb_obj, outname):
        # get the Excellon file whose geometry will create the punch holes
        selection_index = self.ui.exc_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.exc_combo.rootModelIndex())

        try:
            exc_obj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Excellon object loaded ..."))
            return

        new_options = {}
        for opt in grb_obj.obj_options:
            new_options[opt] = deepcopy(grb_obj.obj_options[opt])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # this is the punching geometry
        exc_solid_geometry = MultiPolygon(exc_obj.solid_geometry)

        # this is the target geometry
        grb_solid_geometry = []
        target_geometry = []
        for apid in grb_obj.tools:
            if 'geometry' in grb_obj.tools[apid]:
                for el_geo in grb_obj.tools[apid]['geometry']:
                    if 'solid' in el_geo:
                        if apid in sel_apid:
                            target_geometry.append(el_geo['solid'])
                        else:
                            grb_solid_geometry.append(el_geo['solid'])

        target_geometry = MultiPolygon(target_geometry).buffer(0)

        # create the punched Gerber solid_geometry
        punched_target_geometry = target_geometry.difference(exc_solid_geometry)

        # add together the punched geometry and the not affected geometry
        punched_solid_geometry = []
        try:
            for geo in punched_target_geometry.geoms:
                punched_solid_geometry.append(geo)
        except AttributeError:
            punched_solid_geometry.append(punched_target_geometry)
        for geo in grb_solid_geometry:
            punched_solid_geometry.append(geo)
        punched_solid_geometry = unary_union(punched_solid_geometry)

        # update the gerber apertures to include the clear geometry, so it can be exported successfully
        new_apertures = deepcopy(grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # store here the clear geometry, the key is the drill size
        holes_apertures = {}

        for apid, val in new_apertures_items:
            if apid in sel_apid:
                for elem in val['geometry']:
                    # make it work only for Gerber Flashes who are Points in 'follow'
                    if 'solid' in elem and isinstance(elem['follow'], Point):
                        for tool in exc_obj.tools:
                            clear_apid_size = exc_obj.tools[tool]['tooldia']

                            if 'drills' in exc_obj.tools[tool]:
                                for drill_pt in exc_obj.tools[tool]['drills']:
                                    # since there may be drills that do not drill into a pad we test only for
                                    # drills in a pad
                                    if drill_pt.within(elem['solid']):
                                        geo_elem = {'clear': drill_pt}

                                        if clear_apid_size not in holes_apertures:
                                            holes_apertures[clear_apid_size] = {
                                                'type': 'C',
                                                'size': clear_apid_size,
                                                'geometry': []
                                            }

                                        holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(grb_obj.fill_color)
            new_obj.outline_color = deepcopy(grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_excellon_manual_method(self, outname):
        # get the Excellon file whose geometry will create the punch holes
        selection_index = self.ui.exc_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.exc_combo.rootModelIndex())

        try:
            exc_obj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Excellon object loaded ..."))
            return

        new_options = {}
        for opt in self.grb_obj.obj_options:
            new_options[opt] = deepcopy(self.grb_obj.obj_options[opt])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # this is the punching geometry
        exc_solid_geometry = MultiPolygon(exc_obj.solid_geometry)
        fin_exc_geo = []
        for sel_geo in self.manual_pads:
            apid = sel_geo['apid']
            idx = sel_geo['idx']
            for exc_geo in exc_solid_geometry.geoms:
                if exc_geo.within(self.grb_obj.tools[apid]['geometry'][idx]['solid']) and \
                        isinstance(self.grb_obj.tools[apid]['geometry'][idx]['follow'], Point):
                    fin_exc_geo.append(exc_geo)
        exc_solid_geometry = MultiPolygon(fin_exc_geo)

        # this is the target geometry
        grb_solid_geometry = []
        target_geometry = []
        for apid in self.grb_obj.tools:
            if 'geometry' in self.grb_obj.tools[apid]:
                for el_geo in self.grb_obj.tools[apid]['geometry']:
                    if 'solid' in el_geo:
                        if apid in sel_apid:
                            target_geometry.append(el_geo['solid'])
                        else:
                            grb_solid_geometry.append(el_geo['solid'])

        target_geometry = MultiPolygon(target_geometry).buffer(0)

        # create the punched Gerber solid_geometry
        punched_target_geometry = target_geometry.difference(exc_solid_geometry)

        # add together the punched geometry and the not affected geometry
        punched_solid_geometry = []
        try:
            for geo in punched_target_geometry.geoms:
                punched_solid_geometry.append(geo)
        except AttributeError:
            punched_solid_geometry.append(punched_target_geometry)
        for geo in grb_solid_geometry:
            punched_solid_geometry.append(geo)
        punched_solid_geometry = unary_union(punched_solid_geometry)

        # update the gerber apertures to include the clear geometry, so it can be exported successfully
        new_apertures = deepcopy(self.grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        sel_pad_geo_list = []
        for pad_elem in self.manual_pads:
            apid = pad_elem['apid']
            idx = pad_elem['idx']
            sel_geo = self.grb_obj.tools[apid]['geometry'][idx]['solid']
            sel_pad_geo_list.append(sel_geo)

        # store here the clear geometry, the key is the drill size
        holes_apertures = {}

        for apid, val in new_apertures_items:
            for elem in val['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    for tool in exc_obj.tools:
                        clear_apid_size = exc_obj.tools[tool]['tooldia']

                        if 'drills' in exc_obj.tools[tool]:
                            for drill_pt in exc_obj.tools[tool]['drills']:
                                # since there may be drills that do not drill into a pad we test only for
                                # drills in a pad
                                for sel_pad_geo in sel_pad_geo_list:
                                    if drill_pt.within(elem['solid']) and drill_pt.within(sel_pad_geo):
                                        geo_elem = {'clear': drill_pt}

                                        if clear_apid_size not in holes_apertures:
                                            holes_apertures[clear_apid_size] = {
                                                'type': 'C',
                                                'size': clear_apid_size,
                                                'geometry': []
                                            }

                                        holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(self.grb_obj.fill_color)
            new_obj.outline_color = deepcopy(self.grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_fixed_method(self, grb_obj, outname):
        punch_size = float(self.ui.dia_entry.get_value())
        if punch_size == 0.0:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("The value of the fixed diameter is 0.0. Aborting."))
            return 'fail'

        fail_msg = _("Failed. Punch hole size is bigger than"
                     " some of the apertures in the Gerber object.")

        new_options = {}
        for opt in grb_obj.obj_options:
            new_options[opt] = deepcopy(grb_obj.obj_options[opt])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        punching_geo = []
        for apid in grb_obj.tools:
            if apid in sel_apid:
                if grb_obj.tools[apid]['type'] == 'C' and self.ui.circular_cb.get_value():
                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                if punch_size >= float(grb_obj.tools[apid]['size']):
                                    self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                                    return 'fail'
                                punching_geo.append(elem['follow'].buffer(punch_size / 2))
                elif grb_obj.tools[apid]['type'] == 'R':

                    if round(float(grb_obj.tools[apid]['width']), self.decimals) == \
                            round(float(grb_obj.tools[apid]['height']), self.decimals) and \
                            self.ui.square_cb.get_value():
                        for elem in grb_obj.tools[apid]['geometry']:
                            if 'follow' in elem:
                                if isinstance(elem['follow'], Point):
                                    if punch_size >= float(grb_obj.tools[apid]['width']) or \
                                            punch_size >= float(grb_obj.tools[apid]['height']):
                                        self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                                        return 'fail'
                                    punching_geo.append(elem['follow'].buffer(punch_size / 2))
                    elif round(float(grb_obj.tools[apid]['width']), self.decimals) != \
                            round(float(grb_obj.tools[apid]['height']), self.decimals) and \
                            self.ui.rectangular_cb.get_value():
                        for elem in grb_obj.tools[apid]['geometry']:
                            if 'follow' in elem:
                                if isinstance(elem['follow'], Point):
                                    if punch_size >= float(grb_obj.tools[apid]['width']) or \
                                            punch_size >= float(grb_obj.tools[apid]['height']):
                                        self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                                        return 'fail'
                                    punching_geo.append(elem['follow'].buffer(punch_size / 2))
                elif grb_obj.tools[apid]['type'] == 'O' and self.ui.oblong_cb.get_value():
                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                if punch_size >= float(grb_obj.tools[apid]['size']):
                                    self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                                    return 'fail'
                                punching_geo.append(elem['follow'].buffer(punch_size / 2))
                elif grb_obj.tools[apid]['type'] not in ['C', 'R', 'O'] and self.ui.other_cb.get_value():
                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                if punch_size >= float(grb_obj.tools[apid]['size']):
                                    self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                                    return 'fail'
                                punching_geo.append(elem['follow'].buffer(punch_size / 2))

        punching_geo = MultiPolygon(punching_geo)
        if isinstance(grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(grb_obj.solid_geometry)
        else:
            temp_solid_geometry = grb_obj.solid_geometry
        punched_solid_geometry = temp_solid_geometry.difference(punching_geo)

        if punched_solid_geometry == temp_solid_geometry:
            msg = '[WARNING_NOTCL] %s' % \
                  _("Failed. The new object geometry is the same as the one in the source object geometry...")
            self.app.inform.emit(msg)
            return 'fail'

        # update the gerber apertures to include the clear geometry, so it can be exported successfully
        new_apertures = deepcopy(grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # store here the clear geometry, the key is the drill size
        holes_apertures = {}

        for apid, val in new_apertures_items:
            for elem in val['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    for geo in punching_geo.geoms:
                        clear_apid_size = punch_size

                        # since there may be drills that do not drill into a pad we test only for drills in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(grb_obj.fill_color)
            new_obj.outline_color = deepcopy(grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_fixed_manual_method(self, outname):
        punch_size = float(self.ui.dia_entry.get_value())
        if punch_size == 0.0:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("The value of the fixed diameter is 0.0. Aborting."))
            return 'fail'

        fail_msg = _("Failed. Punch hole size is bigger than"
                     " some of the apertures in the Gerber object.")

        new_options = {}
        for opt in self.grb_obj.obj_options:
            new_options[opt] = deepcopy(self.grb_obj.obj_options[opt])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # this is the punching geometry
        punching_geo = []
        for apid in self.grb_obj.tools:
            for pad_elem in self.manual_pads:
                pad_apid = pad_elem['apid']
                pad_idx = pad_elem['idx']
                if pad_apid == apid:
                    if 'size' in self.grb_obj.tools[apid]:
                        if punch_size >= float(self.grb_obj.tools[apid]['size']):
                            self.app.inform.emit('[ERROR_NOTCL] %s' % fail_msg)
                            return 'fail'
                    pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                    punching_geo.append(pad_point.buffer(punch_size / 2))

        punching_geo = MultiPolygon(punching_geo)
        if isinstance(self.grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(self.grb_obj.solid_geometry)
        else:
            temp_solid_geometry = self.grb_obj.solid_geometry
        punched_solid_geometry = temp_solid_geometry.difference(punching_geo)

        if punched_solid_geometry == temp_solid_geometry:
            msg = '[WARNING_NOTCL] %s' % \
                  _("Failed. The new object geometry is the same as the one in the source object geometry...")
            self.app.inform.emit(msg)
            return 'fail'

        # update the gerber apertures to include the clear geometry, so it can be exported successfully
        new_apertures = deepcopy(self.grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # store here the clear geometry, the key is the drill size
        holes_apertures = {}

        for apid, val in new_apertures_items:
            for elem in val['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    for geo in punching_geo:
                        clear_apid_size = punch_size

                        # since there may be drills that do not drill into a pad we test only for drills in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(self.grb_obj.fill_color)
            new_obj.outline_color = deepcopy(self.grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_ring_method(self, grb_obj, outname):
        circ_r_val = self.ui.circular_ring_entry.get_value()
        oblong_r_val = self.ui.oblong_ring_entry.get_value()
        square_r_val = self.ui.square_ring_entry.get_value()
        rect_r_val = self.ui.rectangular_ring_entry.get_value()
        other_r_val = self.ui.other_ring_entry.get_value()
        dia = None

        new_options = {}
        for opt in grb_obj.obj_options:
            new_options[opt] = deepcopy(grb_obj.obj_options[opt])

        if isinstance(grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(grb_obj.solid_geometry)
        else:
            temp_solid_geometry = grb_obj.solid_geometry

        punched_solid_geometry = temp_solid_geometry

        new_apertures = deepcopy(grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # store here the clear geometry, the key is the new aperture size
        holes_apertures = {}

        for apid, apid_value in grb_obj.tools.items():
            ap_type = apid_value['type']
            punching_geo = []

            if apid in sel_apid:
                if ap_type == 'C' and self.ui.circular_cb.get_value():
                    dia = float(apid_value['size']) - (2 * circ_r_val)
                    for elem in apid_value['geometry']:
                        if 'follow' in elem and isinstance(elem['follow'], Point):
                            punching_geo.append(elem['follow'].buffer(dia / 2))
                elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                    width = float(apid_value['width'])
                    height = float(apid_value['height'])

                    if width > height:
                        dia = float(apid_value['height']) - (2 * oblong_r_val)
                    else:
                        dia = float(apid_value['width']) - (2 * oblong_r_val)

                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                punching_geo.append(elem['follow'].buffer(dia / 2))
                elif ap_type == 'R':
                    width = float(apid_value['width'])
                    height = float(apid_value['height'])

                    # if the height == width (float numbers so the reason for the following)
                    if round(width, self.decimals) == round(height, self.decimals):
                        if self.ui.square_cb.get_value():
                            dia = float(apid_value['height']) - (2 * square_r_val)

                            for elem in grb_obj.tools[apid]['geometry']:
                                if 'follow' in elem:
                                    if isinstance(elem['follow'], Point):
                                        punching_geo.append(elem['follow'].buffer(dia / 2))
                    elif self.ui.rectangular_cb.get_value():
                        if width > height:
                            dia = float(apid_value['height']) - (2 * rect_r_val)
                        else:
                            dia = float(apid_value['width']) - (2 * rect_r_val)

                        for elem in grb_obj.tools[apid]['geometry']:
                            if 'follow' in elem:
                                if isinstance(elem['follow'], Point):
                                    punching_geo.append(elem['follow'].buffer(dia / 2))
                elif self.ui.other_cb.get_value():
                    try:
                        dia = float(apid_value['size']) - (2 * other_r_val)
                    except KeyError:
                        if ap_type == 'AM':
                            pol = apid_value['geometry'][0]['solid']
                            x0, y0, x1, y1 = pol.bounds
                            dx = x1 - x0
                            dy = y1 - y0
                            if dx <= dy:
                                dia = dx - (2 * other_r_val)
                            else:
                                dia = dy - (2 * other_r_val)

                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                punching_geo.append(elem['follow'].buffer(dia / 2))

            # if dia is None then none of the above applied, so we skip the following
            if dia is None:
                continue

            punching_geo = MultiPolygon(punching_geo)

            if punching_geo is None or punching_geo.is_empty:
                continue

            punched_solid_geometry = punched_solid_geometry.difference(punching_geo)

            # update the gerber apertures to include the clear geometry, so it can be exported successfully
            for elem in apid_value['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    clear_apid_size = dia
                    for geo in punching_geo.geoms:

                        # since there may be drills that do not drill into a pad we test only for geos in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(grb_obj.fill_color)
            new_obj.outline_color = deepcopy(grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_ring_manual_method(self, outname):
        circ_r_val = self.ui.circular_ring_entry.get_value()
        oblong_r_val = self.ui.oblong_ring_entry.get_value()
        square_r_val = self.ui.square_ring_entry.get_value()
        rect_r_val = self.ui.rectangular_ring_entry.get_value()
        other_r_val = self.ui.other_ring_entry.get_value()
        dia = None

        new_options = {}
        for opt in self.grb_obj.obj_options:
            new_options[opt] = deepcopy(self.grb_obj.obj_options[opt])

        if isinstance(self.grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(self.grb_obj.solid_geometry)
        else:
            temp_solid_geometry = self.grb_obj.solid_geometry

        punched_solid_geometry = temp_solid_geometry

        new_apertures = deepcopy(self.grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # store here the clear geometry, the key is the new aperture size
        holes_apertures = {}

        for apid, apid_value in self.grb_obj.tools.items():
            ap_type = apid_value['type']
            punching_geo = []

            for pad_elem in self.manual_pads:
                pad_apid = pad_elem['apid']
                pad_idx = pad_elem['idx']

                if pad_apid == apid:
                    if ap_type == 'C':
                        dia = float(apid_value['size']) - (2 * circ_r_val)
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))
                    elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        if width > height:
                            dia = float(apid_value['height']) - (2 * oblong_r_val)
                        else:
                            dia = float(apid_value['width']) - (2 * oblong_r_val)
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))
                    elif ap_type == 'R':
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        # if the height == width (float numbers so the reason for the following)
                        if round(width, self.decimals) == round(height, self.decimals):
                            if self.ui.square_cb.get_value():
                                dia = float(apid_value['height']) - (2 * square_r_val)
                                pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                                punching_geo.append(pad_point.buffer(dia / 2))
                        elif self.ui.rectangular_cb.get_value():
                            if width > height:
                                dia = float(apid_value['height']) - (2 * rect_r_val)
                            else:
                                dia = float(apid_value['width']) - (2 * rect_r_val)
                            pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                            punching_geo.append(pad_point.buffer(dia / 2))
                    elif self.ui.other_cb.get_value():
                        try:
                            dia = float(apid_value['size']) - (2 * other_r_val)
                        except KeyError:
                            if ap_type == 'AM':
                                pol = apid_value['geometry'][0]['solid']
                                x0, y0, x1, y1 = pol.bounds
                                dx = x1 - x0
                                dy = y1 - y0
                                if dx <= dy:
                                    dia = dx - (2 * other_r_val)
                                else:
                                    dia = dy - (2 * other_r_val)
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))

            # if dia is None then none of the above applied, so we skip the following
            if dia is None:
                continue

            punching_geo = MultiPolygon(punching_geo)

            if punching_geo is None or punching_geo.is_empty:
                continue

            punched_solid_geometry = punched_solid_geometry.difference(punching_geo)

            # update the gerber apertures to include the clear geometry, so it can be exported successfully
            for elem in apid_value['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    clear_apid_size = dia
                    for geo in punching_geo.geoms:

                        # since there may be drills that do not drill into a pad we test only for geos in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(self.grb_obj.fill_color)
            new_obj.outline_color = deepcopy(self.grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_proportional_method(self, grb_obj, outname):
        prop_factor = self.ui.factor_entry.get_value() / 100.0
        dia = None
        new_options = {}
        for opt in grb_obj.obj_options:
            new_options[opt] = deepcopy(grb_obj.obj_options[opt])

        if isinstance(grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(grb_obj.solid_geometry)
        else:
            temp_solid_geometry = grb_obj.solid_geometry

        punched_solid_geometry = temp_solid_geometry

        new_apertures = deepcopy(grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # store here the clear geometry, the key is the new aperture size
        holes_apertures = {}

        for apid, apid_value in grb_obj.tools.items():
            ap_type = apid_value['type']
            punching_geo = []

            if apid in sel_apid:
                if ap_type == 'C' and self.ui.circular_cb.get_value():
                    dia = float(apid_value['size']) * prop_factor
                    for elem in apid_value['geometry']:
                        if 'follow' in elem and isinstance(elem['follow'], Point):
                            punching_geo.append(elem['follow'].buffer(dia / 2))
                elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                    width = float(apid_value['width'])
                    height = float(apid_value['height'])

                    if width > height:
                        dia = float(apid_value['height']) * prop_factor
                    else:
                        dia = float(apid_value['width']) * prop_factor

                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                punching_geo.append(elem['follow'].buffer(dia / 2))
                elif ap_type == 'R':
                    width = float(apid_value['width'])
                    height = float(apid_value['height'])

                    # if the height == width (float numbers so the reason for the following)
                    if round(width, self.decimals) == round(height, self.decimals):
                        if self.ui.square_cb.get_value():
                            dia = float(apid_value['height']) * prop_factor

                            for elem in grb_obj.tools[apid]['geometry']:
                                if 'follow' in elem:
                                    if isinstance(elem['follow'], Point):
                                        punching_geo.append(elem['follow'].buffer(dia / 2))
                    elif self.ui.rectangular_cb.get_value():
                        if width > height:
                            dia = float(apid_value['height']) * prop_factor
                        else:
                            dia = float(apid_value['width']) * prop_factor

                        for elem in grb_obj.tools[apid]['geometry']:
                            if 'follow' in elem:
                                if isinstance(elem['follow'], Point):
                                    punching_geo.append(elem['follow'].buffer(dia / 2))
                elif self.ui.other_cb.get_value():
                    try:
                        dia = float(apid_value['size']) * prop_factor
                    except KeyError:
                        if ap_type == 'AM':
                            pol = apid_value['geometry'][0]['solid']
                            x0, y0, x1, y1 = pol.bounds
                            dx = x1 - x0
                            dy = y1 - y0
                            if dx <= dy:
                                dia = dx * prop_factor
                            else:
                                dia = dy * prop_factor

                    for elem in grb_obj.tools[apid]['geometry']:
                        if 'follow' in elem:
                            if isinstance(elem['follow'], Point):
                                punching_geo.append(elem['follow'].buffer(dia / 2))

            # if dia is None then none of the above applied, so we skip the following
            if dia is None:
                continue

            punching_geo = MultiPolygon(punching_geo)

            if punching_geo is None or punching_geo.is_empty:
                continue

            punched_solid_geometry = punched_solid_geometry.difference(punching_geo)

            # update the gerber apertures to include the clear geometry, so it can be exported successfully
            for elem in apid_value['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    clear_apid_size = dia
                    for geo in punching_geo.geoms:

                        # since there may be drills that do not drill into a pad we test only for geos in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(grb_obj.fill_color)
            new_obj.outline_color = deepcopy(grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def on_proportional_manual_method(self, outname):
        prop_factor = self.ui.factor_entry.get_value() / 100.0
        dia = None
        new_options = {}
        for opt in self.grb_obj.obj_options:
            new_options[opt] = deepcopy(self.grb_obj.obj_options[opt])

        if isinstance(self.grb_obj.solid_geometry, list):
            temp_solid_geometry = MultiPolygon(self.grb_obj.solid_geometry)
        else:
            temp_solid_geometry = self.grb_obj.solid_geometry

        punched_solid_geometry = temp_solid_geometry

        new_apertures = deepcopy(self.grb_obj.tools)
        new_apertures_items = new_apertures.items()

        # find maximum aperture id
        new_apid = max([int(x) for x, __ in new_apertures_items])

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        # store here the clear geometry, the key is the new aperture size
        holes_apertures = {}

        for apid, apid_value in self.grb_obj.tools.items():
            ap_type = apid_value['type']
            punching_geo = []

            for pad_elem in self.manual_pads:
                pad_apid = pad_elem['apid']
                pad_idx = pad_elem['idx']

                if pad_apid == apid:

                    if ap_type == 'C' and self.ui.circular_cb.get_value():
                        dia = float(apid_value['size']) * prop_factor
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))
                    elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        if width > height:
                            dia = float(apid_value['height']) * prop_factor
                        else:
                            dia = float(apid_value['width']) * prop_factor
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))
                    elif ap_type == 'R':
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        # if the height == width (float numbers so the reason for the following)
                        if round(width, self.decimals) == round(height, self.decimals):
                            if self.ui.square_cb.get_value():
                                dia = float(apid_value['height']) * prop_factor
                                pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                                punching_geo.append(pad_point.buffer(dia / 2))
                        elif self.ui.rectangular_cb.get_value():
                            if width > height:
                                dia = float(apid_value['height']) * prop_factor
                            else:
                                dia = float(apid_value['width']) * prop_factor
                            pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                            punching_geo.append(pad_point.buffer(dia / 2))
                    elif self.ui.other_cb.get_value():
                        try:
                            dia = float(apid_value['size']) * prop_factor
                        except KeyError:
                            if ap_type == 'AM':
                                pol = apid_value['geometry'][0]['solid']
                                x0, y0, x1, y1 = pol.bounds
                                dx = x1 - x0
                                dy = y1 - y0
                                if dx <= dy:
                                    dia = dx * prop_factor
                                else:
                                    dia = dy * prop_factor
                        pad_point = self.grb_obj.tools[apid]['geometry'][pad_idx]['follow']
                        punching_geo.append(pad_point.buffer(dia / 2))

            # if dia is None then none of the above applied, so we skip the following
            if dia is None:
                continue

            punching_geo = MultiPolygon(punching_geo)

            if punching_geo is None or punching_geo.is_empty:
                continue

            punched_solid_geometry = punched_solid_geometry.difference(punching_geo)

            # update the gerber apertures to include the clear geometry, so it can be exported successfully
            for elem in apid_value['geometry']:
                # make it work only for Gerber Flashes who are Points in 'follow'
                if 'solid' in elem and isinstance(elem['follow'], Point):
                    clear_apid_size = dia
                    for geo in punching_geo.geoms:

                        # since there may be drills that do not drill into a pad we test only for geos in a pad
                        if geo.within(elem['solid']):
                            geo_elem = {'clear': geo.centroid}

                            if clear_apid_size not in holes_apertures:
                                holes_apertures[clear_apid_size] = {
                                    'type': 'C',
                                    'size': clear_apid_size,
                                    'geometry': []
                                }

                            holes_apertures[clear_apid_size]['geometry'].append(deepcopy(geo_elem))

        # add the clear geometry to new apertures; it's easier than to test if there are apertures with the same
        # size and add there the clear geometry
        for hole_size, ap_val in holes_apertures.items():
            new_apid += 1
            new_apertures[new_apid] = deepcopy(ap_val)

        def init_func(new_obj, app_obj):
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(self.grb_obj.fill_color)
            new_obj.outline_color = deepcopy(self.grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(punched_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                   local_use=new_obj, use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func, autoselected=False)

    def find_pad(self, point):
        pt = Point(point) if type(point) is tuple else point
        results = []

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        for apid, apid_value in self.grb_obj.tools.items():
            if apid in sel_apid:
                for idx, elem in enumerate(apid_value['geometry']):
                    if 'follow' in elem and isinstance(elem['follow'], Point):
                        try:
                            pad = elem['solid']
                        except KeyError:
                            continue
                        if pt.within(pad):
                            new_elem = {
                                'apid': apid,
                                'idx': idx
                            }
                            results.append(deepcopy(new_elem))
        return results

    def on_manual_punch(self):
        """

        :return:
        """

        punch_method = self.ui.method_punch.get_value()

        '''
        self.manual_pads it's a list of dicts that store the result of manual pad selection
        Each dictionary is in the format:
        {
            'apid': aperture in the target Gerber object apertures dict,
            'idx': index of the selected geo dict in the self.grb_obj.tools[apid]['geometry] list of geo_dicts
        }
        

        Each geo_dict in the obj.tools[apid]['geometry'] list has possible keys:
        {
            'solid': Shapely Polygon,
            'follow': Shapely Point or LineString,
            'clear': Shapely Polygon
        }
        '''
        name = self.grb_obj.obj_options['name'].rpartition('.')[0]
        if name == '':
            name = self.grb_obj.obj_options['name']
        outname = name + "_punched"

        if punch_method == 'exc':
            self.on_excellon_manual_method(outname)
        elif punch_method == 'fixed':
            self.on_fixed_manual_method(outname)
        elif punch_method == 'ring':
            self.on_ring_manual_method(outname)
        elif punch_method == 'prop':
            self.on_proportional_manual_method(outname)

    # To be called after clicking on the plot.
    def on_single_poly_mouse_release(self, event):
        if self.app.use_3d_engine:
            event_pos = event.pos
            right_button = 2
            event_is_dragging = self.app.event_is_dragging
        else:
            event_pos = (event.xdata, event.ydata)
            right_button = 3
            event_is_dragging = self.app.ui.popMenu.mouse_is_panning

        try:
            x = float(event_pos[0])
            y = float(event_pos[1])
        except TypeError:
            return

        event_pos = (x, y)
        curr_pos = self.app.plotcanvas.translate_coords(event_pos)

        # do paint single only for left mouse clicks
        if event.button == 1:
            pads = self.find_pad(point=(curr_pos[0], curr_pos[1]))

            def test_pad(a, b):
                return True if a['apid'] == b['apid'] and a['idx'] == b['idx'] else False

            if self.manual_pads:
                tmp_lst = deepcopy(self.manual_pads)
                tmp_pads = deepcopy(pads)
                for old_pad in self.manual_pads:
                    for pad in pads:
                        if test_pad(old_pad, pad):
                            tmp_lst.remove(old_pad)
                            tmp_pads.remove(pad)

                self.manual_pads = [x for x in tmp_lst if x is not None] + tmp_pads
            else:
                self.manual_pads += pads

            if self.manual_pads:
                for el in pads:
                    apid = el['apid']
                    idx = el['idx']
                    clicked_poly = self.grb_obj.tools[apid]['geometry'][idx]['solid']
                    if clicked_poly not in self.poly_dict.values():
                        shape_id = self.app.tool_shapes.add(
                            tolerance=self.grb_obj.drawing_tolerance, layer=0, shape=clicked_poly,
                            color=self.app.options['global_sel_draw_color'] + 'FF',
                            face_color=self.app.options['global_sel_draw_color'] + 'FF', visible=True)
                        self.poly_dict[shape_id] = clicked_poly
                        self.app.inform.emit(
                            '%s: %d. %s' % (_("Added pad"), int(len(self.poly_dict)),
                                            _("Click to add next pad or right click to start."))
                        )
                    else:
                        try:
                            for k, v in list(self.poly_dict.items()):
                                if v == clicked_poly:
                                    self.app.tool_shapes.remove(k)
                                    self.poly_dict.pop(k)
                                    break
                        except TypeError:
                            return
                        self.app.inform.emit(
                            '%s. %s' % (_("Removed pad"),
                                        _("Click to add/remove next pad or right click to start."))
                        )

                    self.app.tool_shapes.redraw()
            else:
                self.app.inform.emit(_("No pad detected under click position."))

        elif event.button == right_button and event_is_dragging is False:
            # restore the Grid snapping if it was active before
            if self.grid_status_memory is True:
                self.app.ui.grid_snap_btn.trigger()

            if self.app.use_3d_engine:
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_single_poly_mouse_release)
                self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.mr)
                self.app.plotcanvas.graph_event_disconnect(self.kp)

            self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press',
                                                                  self.app.on_mouse_click_over_plot)
            self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                  self.app.on_mouse_click_release_over_plot)

            # disconnect flags
            self.poly_sel_disconnect_flag = False

            # restore the selection shape
            self.app.options['global_selection_shape'] = self.old_selection_status

            self.app.tool_shapes.clear(update=True)

            self.on_manual_punch()
            self.clear_aperture_marking()
            self.app.ui.notebook.setDisabled(False)

            # initialize the work variables
            self.manual_pads = []
            if self.poly_dict:
                self.poly_dict.clear()
            else:
                self.app.inform.emit('[ERROR_NOTCL] %s' % _("List of single polygons is empty. Aborting."))

    def on_key_press(self, event):
        # modifiers = QtWidgets.QApplication.keyboardModifiers()
        # matplotlib_key_flag = False

        # events out of the self.app.collection view (it's about Project Tab) are of type int
        if type(event) is int:
            key = event
        # events from the GUI are of type QKeyEvent
        elif type(event) == QtGui.QKeyEvent:
            key = event.key()
        elif isinstance(event, mpl_key_event):  # MatPlotLib key events are trickier to interpret than the rest
            # matplotlib_key_flag = True

            key = event.key
            key = QtGui.QKeySequence(key)

            # check for modifiers
            key_string = key.toString().lower()
            if '+' in key_string:
                mod, __, key_text = key_string.rpartition('+')
                if mod.lower() == 'ctrl':
                    # modifiers = QtCore.Qt.KeyboardModifier.ControlModifier
                    pass
                elif mod.lower() == 'alt':
                    # modifiers = QtCore.Qt.KeyboardModifier.AltModifier
                    pass
                elif mod.lower() == 'shift':
                    # modifiers = QtCore.Qt.KeyboardModifier.
                    pass
                else:
                    # modifiers = QtCore.Qt.KeyboardModifier.NoModifier
                    pass
                key = QtGui.QKeySequence(key_text)

        # events from Vispy are of type KeyEvent
        else:
            key = event.key

        if key == QtCore.Qt.Key.Key_Escape or key == 'Escape':
            if self.poly_sel_disconnect_flag is False:
                try:
                    # restore the Grid snapping if it was active before
                    if self.grid_status_memory is True:
                        self.app.ui.grid_snap_btn.trigger()

                    if self.app.use_3d_engine:
                        self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_single_poly_mouse_release)
                        self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
                    else:
                        self.app.plotcanvas.graph_event_disconnect(self.mr)
                        self.app.plotcanvas.graph_event_disconnect(self.kp)

                    self.app.tool_shapes.clear(update=True)
                except Exception as e:
                    self.app.log.error("ToolPaint.on_key_press() _2 --> %s" % str(e))

                self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                      self.app.on_mouse_click_release_over_plot)
                self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press',
                                                                      self.app.on_mouse_click_over_plot)
                # restore the selection shape
                if self.old_selection_status is not None:
                    self.app.options['global_selection_shape'] = self.old_selection_status

            self.app.ui.notebook.setDisabled(False)
            self.poly_dict.clear()
            self.clear_aperture_marking()
            self.delete_moving_selection_shape()
            self.delete_tool_selection_shape()

    def on_mark_cb_click_table(self):
        """
        Will mark aperture geometries on canvas or delete the markings depending on the checkbox state
        :return:
        """

        try:
            cw = self.sender()
            cw_index = self.ui.apertures_table.indexAt(cw.pos())
            cw_row = cw_index.row()
        except AttributeError:
            cw_row = 0
        except TypeError:
            return

        try:
            aperture = int(self.ui.apertures_table.item(cw_row, 0).text())
        except AttributeError:
            return

        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            grb_obj = model_index.internalPointer().obj
        except Exception:
            return

        wdg = self.ui.apertures_table.cellWidget(cw_row, 3)
        assert isinstance(wdg, FCCheckBox)
        if wdg.isChecked():
            # self.plot_aperture(color='#2d4606bf', marked_aperture=aperture, visible=True)
            # color = '#e32b0760'
            color = self.app.options['global_sel_draw_color']
            color = (color + 'AA') if len(color) == 7 else (color[:-2] + 'AA')
            grb_obj.plot_aperture(color=color,  marked_aperture=aperture, visible=True, run_thread=True)
        else:
            grb_obj.clear_plot_apertures(aperture=aperture)

    def on_manual_sel_all(self):
        if self.ui.punch_type_radio.get_value() != 'm':
            return

        # get the Gerber file who is the source of the punched Gerber
        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            self.grb_obj = model_index.internalPointer().obj
        except Exception:
            return

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        self.manual_pads = []
        for apid, apid_value in self.grb_obj.tools.items():
            if apid in sel_apid:
                for idx, elem in enumerate(apid_value['geometry']):
                    if 'follow' in elem and isinstance(elem['follow'], Point):
                        if 'solid' in elem:
                            sol_geo = elem['solid']
                            if sol_geo not in self.poly_dict.values():
                                new_elem = {
                                    'apid': apid,
                                    'idx': idx
                                }
                                self.manual_pads.append(deepcopy(new_elem))

                                sel_color = self.app.options['global_sel_draw_color'] + 'FF' if \
                                    len(self.app.options['global_sel_draw_color']) == 7 else \
                                    self.app.options['global_sel_draw_color']
                                shape_id = self.app.tool_shapes.add(
                                    tolerance=self.grb_obj.drawing_tolerance, layer=0, shape=sol_geo,
                                    color=sel_color, face_color=sel_color, visible=True)
                                self.poly_dict[shape_id] = sol_geo
        self.app.tool_shapes.redraw()
        self.app.inform.emit(_("All selectable pads are selected."))

    def on_manual_clear_all(self):
        if self.ui.punch_type_radio.get_value() != 'm':
            return

        try:
            for k in list(self.poly_dict.keys()):
                self.app.tool_shapes.remove(k)
            self.poly_dict.clear()
        except TypeError:
            return

        self.manual_pads = []
        self.poly_dict.clear()

        self.app.tool_shapes.redraw()
        self.app.inform.emit(_("Selection cleared."))

    def clear_aperture_marking(self):
        """
        Will clear all aperture markings after creating an Excellon object with extracted drill holes

        :return:
        :rtype:
        """

        for row in range(self.ui.apertures_table.rowCount()):
            wdg = self.ui.apertures_table.cellWidget(row, 3)
            assert isinstance(wdg, FCCheckBox)
            wdg.set_value(False)

    def on_plugin_cleanup(self):
        self.reset_fields()

    def reset_fields(self):
        self.ui.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.ui.exc_combo.setRootModelIndex(self.app.collection.index(1, 0, QtCore.QModelIndex()))
        self.clear_aperture_marking()

        self.ui_disconnect()


class PunchUI:

    pluginName = _("Punch Gerber")

    def __init__(self, layout, app):
        self.app = app
        self.decimals = self.app.decimals
        self.layout = layout

        self.tools_frame = QtWidgets.QFrame()
        self.tools_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.tools_frame)
        self.tools_box = QtWidgets.QVBoxLayout()
        self.tools_box.setContentsMargins(0, 0, 0, 0)
        self.tools_frame.setLayout(self.tools_box)

        self.title_box = QtWidgets.QHBoxLayout()
        self.tools_box.addLayout(self.title_box)

        self.title_box = QtWidgets.QHBoxLayout()
        self.tools_box.addLayout(self.title_box)

        # ## Title
        title_label = FCLabel("%s" % self.pluginName, size=16, bold=True)
        self.title_box.addWidget(title_label)

        # App Level label
        self.level = QtWidgets.QToolButton()
        self.level.setToolTip(
            _(
                "Beginner Mode - many parameters are hidden.\n"
                "Advanced Mode - full control.\n"
                "Permanent change is done in 'Preferences' menu."
            )
        )
        self.level.setCheckable(True)
        self.title_box.addWidget(self.level)

        # #############################################################################################################
        # Source Object Frame
        # #############################################################################################################
        self.obj_combo_label = FCLabel('%s' % _("Source Object"), color='darkorange', bold=True)
        self.obj_combo_label.setToolTip('%s.' % _("Gerber into which to punch holes"))
        self.tools_box.addWidget(self.obj_combo_label)

        # Grid Layout
        grid0 = GLay(v_spacing=5, h_spacing=3)
        self.tools_box.addLayout(grid0)

        # ## Gerber Object
        self.gerber_object_combo = FCComboBox()
        self.gerber_object_combo.setModel(self.app.collection)
        self.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.gerber_object_combo.is_last = False
        self.gerber_object_combo.obj_type = "Gerber"

        grid0.addWidget(self.gerber_object_combo, 0, 0, 1, 2)

        self.padt_label = FCLabel('%s' % _("Processed Pads Type"), color='blue', bold=True)
        self.padt_label.setToolTip(
            _("The type of pads shape to be processed.\n"
              "If the PCB has many SMD pads with rectangular pads,\n"
              "disable the Rectangular aperture.")
        )

        self.tools_box.addWidget(self.padt_label)

        # #############################################################################################################
        # Processed Pads Frame
        # #############################################################################################################
        tt_frame = FCFrame()
        self.tools_box.addWidget(tt_frame)

        pad_all_grid = GLay(v_spacing=5, h_spacing=3)
        tt_frame.setLayout(pad_all_grid)

        pad_grid = GLay(v_spacing=5, h_spacing=3, c_stretch=[0])
        pad_all_grid.addLayout(pad_grid, 0, 0)

        # Select all
        self.select_all_cb = FCCheckBox('%s' % _("All"))
        self.select_all_cb.setToolTip(
            _("Process all Pads.")
        )
        pad_grid.addWidget(self.select_all_cb, 0, 0)

        # Circular Aperture Selection
        self.circular_cb = FCCheckBox('%s' % _("Circular"))
        self.circular_cb.setToolTip(
            _("Process Circular Pads.")
        )

        pad_grid.addWidget(self.circular_cb, 1, 0)

        # Oblong Aperture Selection
        self.oblong_cb = FCCheckBox('%s' % _("Oblong"))
        self.oblong_cb.setToolTip(
            _("Process Oblong Pads.")
        )

        pad_grid.addWidget(self.oblong_cb, 2, 0)

        # Square Aperture Selection
        self.square_cb = FCCheckBox('%s' % _("Square"))
        self.square_cb.setToolTip(
            _("Process Square Pads.")
        )

        pad_grid.addWidget(self.square_cb, 3, 0)

        # Rectangular Aperture Selection
        self.rectangular_cb = FCCheckBox('%s' % _("Rectangular"))
        self.rectangular_cb.setToolTip(
            _("Process Rectangular Pads.")
        )

        pad_grid.addWidget(self.rectangular_cb, 4, 0)

        # Others type of Apertures Selection
        self.other_cb = FCCheckBox('%s' % _("Others"))
        self.other_cb.setToolTip(
            _("Process pads not in the categories above.")
        )

        pad_grid.addWidget(self.other_cb, 5, 0)

        # Aperture Table
        self.apertures_table = FCTable()
        pad_all_grid.addWidget(self.apertures_table, 0, 1)

        self.apertures_table.setColumnCount(4)
        self.apertures_table.setHorizontalHeaderLabels([_('Code'), _('Type'), _('Size'), 'M'])
        self.apertures_table.setSortingEnabled(False)
        self.apertures_table.setRowCount(0)
        self.apertures_table.resizeColumnsToContents()
        self.apertures_table.resizeRowsToContents()

        self.apertures_table.horizontalHeaderItem(0).setToolTip(
            _("Aperture Code"))
        self.apertures_table.horizontalHeaderItem(1).setToolTip(
            _("Type of aperture: circular, rectangle, macros etc"))
        self.apertures_table.horizontalHeaderItem(2).setToolTip(
            _("Aperture Size:"))
        self.apertures_table.horizontalHeaderItem(3).setToolTip(
            _("Mark the aperture instances on canvas."))

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.apertures_table.setSizePolicy(sizePolicy)
        self.apertures_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)

        # #############################################################################################################
        # Method Frame
        # #############################################################################################################
        self.method_label = FCLabel('%s' % _("Method"), color='red', bold=True)
        self.method_label.setToolTip(
            _("The punch hole source can be:\n"
              "- Excellon Object-> the Excellon object drills center will serve as reference.\n"
              "- Fixed Diameter -> will try to use the pads center as reference adding fixed diameter holes.\n"
              "- Fixed Annular Ring -> will try to keep a set annular ring.\n"
              "- Proportional -> will make a Gerber punch hole having the diameter a percentage of the pad diameter.")
        )
        self.tools_box.addWidget(self.method_label)

        m_frame = FCFrame()
        self.tools_box.addWidget(m_frame)

        # Grid Layout
        grid1 = GLay(v_spacing=5, h_spacing=3)
        m_frame.setLayout(grid1)

        self.method_punch = RadioSet(
            [
                {'label': _('Excellon'), 'value': 'exc'},
                {'label': _("Fixed Diameter"), 'value': 'fixed'},
                {'label': _("Proportional"), 'value': 'prop'},
                {'label': _("Fixed Annular Ring"), 'value': 'ring'}
            ],
            orientation='vertical',
            compact=True)
        grid1.addWidget(self.method_punch, 0, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid1.addWidget(separator_line, 2, 0, 1, 2)

        self.exc_label = FCLabel('%s' % _("Excellon"), bold=True)
        self.exc_label.setToolTip(
            _("Remove the geometry of Excellon from the Gerber to create the holes in pads.")
        )

        self.exc_combo = FCComboBox()
        self.exc_combo.setModel(self.app.collection)
        self.exc_combo.setRootModelIndex(self.app.collection.index(1, 0, QtCore.QModelIndex()))
        self.exc_combo.is_last = True
        self.exc_combo.obj_type = "Excellon"

        grid1.addWidget(self.exc_label, 4, 0, 1, 2)
        grid1.addWidget(self.exc_combo, 6, 0, 1, 2)

        # Fixed Dia
        self.fixed_label = FCLabel('%s' % _("Fixed Diameter"), bold=True)
        grid1.addWidget(self.fixed_label, 8, 0, 1, 2)

        # Diameter value
        self.dia_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.dia_entry.set_precision(self.decimals)
        self.dia_entry.set_range(0.0000, 10000.0000)

        self.dia_label = FCLabel('%s:' % _("Value"))
        self.dia_label.setToolTip(
            _("Fixed hole diameter.")
        )

        grid1.addWidget(self.dia_label, 10, 0)
        grid1.addWidget(self.dia_entry, 10, 1)

        # #############################################################################################################
        # RING FRAME
        # #############################################################################################################
        self.ring_frame = QtWidgets.QFrame()
        self.ring_frame.setContentsMargins(0, 0, 0, 0)
        grid1.addWidget(self.ring_frame, 12, 0, 1, 2)

        self.ring_box = QtWidgets.QVBoxLayout()
        self.ring_box.setContentsMargins(0, 0, 0, 0)
        self.ring_frame.setLayout(self.ring_box)

        # Annular Ring value
        self.ring_label = FCLabel('%s' % _("Fixed Annular Ring"), bold=True)
        self.ring_label.setToolTip(
            _("The size of annular ring.\n"
              "The copper sliver between the hole exterior\n"
              "and the margin of the copper pad.")
        )
        self.ring_box.addWidget(self.ring_label)

        # ## Grid Layout
        self.grid1 = GLay(v_spacing=5, h_spacing=3)
        self.ring_box.addLayout(self.grid1)

        # Circular Annular Ring Value
        self.circular_ring_label = FCLabel('%s:' % _("Circular"))
        self.circular_ring_label.setToolTip(
            _("The size of annular ring for circular pads.")
        )

        self.circular_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.circular_ring_entry.set_precision(self.decimals)
        self.circular_ring_entry.set_range(0.0000, 10000.0000)

        self.grid1.addWidget(self.circular_ring_label, 3, 0)
        self.grid1.addWidget(self.circular_ring_entry, 3, 1)

        # Oblong Annular Ring Value
        self.oblong_ring_label = FCLabel('%s:' % _("Oblong"))
        self.oblong_ring_label.setToolTip(
            _("The size of annular ring for oblong pads.")
        )

        self.oblong_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.oblong_ring_entry.set_precision(self.decimals)
        self.oblong_ring_entry.set_range(0.0000, 10000.0000)

        self.grid1.addWidget(self.oblong_ring_label, 4, 0)
        self.grid1.addWidget(self.oblong_ring_entry, 4, 1)

        # Square Annular Ring Value
        self.square_ring_label = FCLabel('%s:' % _("Square"))
        self.square_ring_label.setToolTip(
            _("The size of annular ring for square pads.")
        )

        self.square_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.square_ring_entry.set_precision(self.decimals)
        self.square_ring_entry.set_range(0.0000, 10000.0000)

        self.grid1.addWidget(self.square_ring_label, 5, 0)
        self.grid1.addWidget(self.square_ring_entry, 5, 1)

        # Rectangular Annular Ring Value
        self.rectangular_ring_label = FCLabel('%s:' % _("Rectangular"))
        self.rectangular_ring_label.setToolTip(
            _("The size of annular ring for rectangular pads.")
        )

        self.rectangular_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.rectangular_ring_entry.set_precision(self.decimals)
        self.rectangular_ring_entry.set_range(0.0000, 10000.0000)

        self.grid1.addWidget(self.rectangular_ring_label, 6, 0)
        self.grid1.addWidget(self.rectangular_ring_entry, 6, 1)

        # Others Annular Ring Value
        self.other_ring_label = FCLabel('%s:' % _("Others"))
        self.other_ring_label.setToolTip(
            _("The size of annular ring for other pads.")
        )

        self.other_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.other_ring_entry.set_precision(self.decimals)
        self.other_ring_entry.set_range(0.0000, 10000.0000)

        self.grid1.addWidget(self.other_ring_label, 7, 0)
        self.grid1.addWidget(self.other_ring_entry, 7, 1)
        # #############################################################################################################

        # Proportional value
        self.prop_label = FCLabel('%s' % _("Proportional Diameter"), bold=True)
        grid1.addWidget(self.prop_label, 14, 0, 1, 2)

        # Diameter value
        self.factor_entry = FCDoubleSpinner(callback=self.confirmation_message, suffix='%')
        self.factor_entry.set_precision(self.decimals)
        self.factor_entry.set_range(0.0000, 100.0000)
        self.factor_entry.setSingleStep(0.1)

        self.factor_label = FCLabel('%s:' % _("Value"))
        self.factor_label.setToolTip(
            _("Proportional Diameter.\n"
              "The hole diameter will be a fraction of the pad size.")
        )

        grid1.addWidget(self.factor_label, 16, 0)
        grid1.addWidget(self.factor_entry, 16, 1)

        # #############################################################################################################
        # Selection Frame
        # #############################################################################################################
        # Selection
        self.sel_label = FCLabel('%s' % _("Selection"), color='green', bold=True)
        self.tools_box.addWidget(self.sel_label)

        self.s_frame = FCFrame()
        self.tools_box.addWidget(self.s_frame)

        # Grid Layout
        grid2 = GLay(v_spacing=5, h_spacing=3)
        self.s_frame.setLayout(grid2)

        # Type of doing the punch
        self.punch_type_label = FCLabel('%s:' % _("Type"))
        self.punch_type_label.setToolTip(
            _("When the manual type is chosen, the pads to be punched\n"
              "are selected on the canvas but only those that\n"
              "are in the processed pads.")
        )

        self.punch_type_radio = RadioSet([
            {"label": _("Automatic"), "value": "a"},
            {"label": _("Manual"), "value": "m"},
        ])

        grid2.addWidget(self.punch_type_label, 0, 0)
        grid2.addWidget(self.punch_type_radio, 0, 1)

        sel_hlay = QtWidgets.QHBoxLayout()
        self.sel_all_btn = FCButton(_("Select All"))
        self.sel_all_btn.setIcon(QtGui.QIcon(self.app.resource_location + '/select_all.png'))

        self.sel_all_btn.setToolTip(
            _("Select all available.")
        )
        self.clear_all_btn = FCButton(_("Deselect All"))
        self.clear_all_btn.setIcon(QtGui.QIcon(self.app.resource_location + '/deselect_all32.png'))

        self.clear_all_btn.setToolTip(
            _("Clear the selection.")
        )
        sel_hlay.addWidget(self.sel_all_btn)
        sel_hlay.addWidget(self.clear_all_btn)
        grid2.addLayout(sel_hlay, 2, 0, 1, 2)

        # Buttons
        self.punch_object_button = FCButton(_("Punch Gerber"), bold=True)
        self.punch_object_button.setIcon(QtGui.QIcon(self.app.resource_location + '/punch32.png'))
        self.punch_object_button.setToolTip(
            _("Create a Gerber object from the selected object, within\n"
              "the specified box.")
        )
        self.tools_box.addWidget(self.punch_object_button)

        self.layout.addStretch(1)

        # ## Reset Tool
        self.reset_button = FCButton(_("Reset Tool"), bold=True)
        self.reset_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reset32.png'))
        self.reset_button.setToolTip(
            _("Will reset the tool parameters.")
        )
        self.layout.addWidget(self.reset_button)

        self.circular_ring_entry.setEnabled(False)
        self.oblong_ring_entry.setEnabled(False)
        self.square_ring_entry.setEnabled(False)
        self.rectangular_ring_entry.setEnabled(False)
        self.other_ring_entry.setEnabled(False)

        self.dia_entry.hide()
        self.dia_label.hide()
        self.factor_label.hide()
        self.factor_entry.hide()

        # #################################### FINSIHED GUI ###########################
        # #############################################################################

    def confirmation_message(self, accepted, minval, maxval):
        if accepted is False:
            self.app.inform[str, bool].emit('[WARNING_NOTCL] %s: [%.*f, %.*f]' % (_("Edited value is out of range"),
                                                                                  self.decimals,
                                                                                  minval,
                                                                                  self.decimals,
                                                                                  maxval), False)
        else:
            self.app.inform[str, bool].emit('[success] %s' % _("Edited value is within limits."), False)

    def confirmation_message_int(self, accepted, minval, maxval):
        if accepted is False:
            self.app.inform[str, bool].emit('[WARNING_NOTCL] %s: [%d, %d]' %
                                            (_("Edited value is out of range"), minval, maxval), False)
        else:
            self.app.inform[str, bool].emit('[success] %s' % _("Edited value is within limits."), False)
