# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 1/10/2020                                          #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui

from appTool import AppTool
from appGUI.GUIElements import RadioSet, FCDoubleSpinner, FCCheckBox, FCComboBox, FCLabel, FCTable, \
    VerticalScrollArea, FCGridLayout

from shapely.geometry import Point, MultiPolygon, Polygon, box

from copy import deepcopy

import logging
import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolExtract(AppTool):

    def __init__(self, app):
        AppTool.__init__(self, app)

        self.app = app
        self.decimals = self.app.decimals

        # store here the old object name
        self.old_name = ''

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = ExtractUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

    def on_object_combo_changed(self):
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

            self.old_name = grb_obj.options['name']

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='Alt+I', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("Extract Drills()")

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

        AppTool.run(self)
        self.set_tool_ui()
        self.build_tool_ui()

        self.app.ui.notebook.setTabText(2, _("Extract"))

    def connect_signals_at_init(self):
        # ## Signals
        self.ui.hole_size_radio.activated_custom.connect(self.on_hole_size_toggle)

        self.ui.circular_cb.stateChanged.connect(
            lambda state:
            self.ui.circular_ring_entry.setDisabled(False) if state else self.ui.circular_ring_entry.setDisabled(True)
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

        self.ui.e_drills_button.clicked.connect(self.on_extract_drills_click)
        self.ui.e_sm_button.clicked.connect(self.on_extract_soldermask_click)
        self.ui.e_cut_button.clicked.connect(self.on_extract_cutout_click)
        self.ui.reset_button.clicked.connect(self.set_tool_ui)

        self.ui.circular_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.oblong_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.square_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.rectangular_cb.stateChanged.connect(self.build_tool_ui)
        self.ui.other_cb.stateChanged.connect(self.build_tool_ui)

        self.ui.gerber_object_combo.currentIndexChanged.connect(self.on_object_combo_changed)
        self.ui.gerber_object_combo.currentIndexChanged.connect(self.build_tool_ui)

    def set_tool_ui(self):
        self.clear_ui(self.layout)
        self.ui = ExtractUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        self.reset_fields()

        self.ui_disconnect()
        self.ui_connect()
        self.ui.hole_size_radio.set_value(self.app.defaults["tools_extract_hole_type"])

        self.ui.dia_entry.set_value(float(self.app.defaults["tools_extract_hole_fixed_dia"]))

        self.ui.circular_ring_entry.set_value(float(self.app.defaults["tools_extract_circular_ring"]))
        self.ui.oblong_ring_entry.set_value(float(self.app.defaults["tools_extract_oblong_ring"]))
        self.ui.square_ring_entry.set_value(float(self.app.defaults["tools_extract_square_ring"]))
        self.ui.rectangular_ring_entry.set_value(float(self.app.defaults["tools_extract_rectangular_ring"]))
        self.ui.other_ring_entry.set_value(float(self.app.defaults["tools_extract_others_ring"]))

        self.ui.circular_cb.set_value(self.app.defaults["tools_extract_circular"])
        self.ui.oblong_cb.set_value(self.app.defaults["tools_extract_oblong"])
        self.ui.square_cb.set_value(self.app.defaults["tools_extract_square"])
        self.ui.rectangular_cb.set_value(self.app.defaults["tools_extract_rectangular"])
        self.ui.other_cb.set_value(self.app.defaults["tools_extract_others"])

        self.ui.factor_entry.set_value(float(self.app.defaults["tools_extract_hole_prop_factor"]))

        # Extract Soldermask
        self.ui.clearance_entry.set_value(float(self.app.defaults["tools_extract_sm_clearance"]))

        # Extract Cutout
        self.ui.margin_cut_entry.set_value(float(self.app.defaults["tools_extract_cut_margin"]))
        self.ui.thick_cut_entry.set_value(float(self.app.defaults["tools_extract_cut_thickness"]))

        # SELECT THE CURRENT OBJECT
        obj = self.app.collection.get_active()
        if obj and obj.kind == 'gerber':
            obj_name = obj.options['name']
            self.ui.gerber_object_combo.set_value(obj_name)

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

        self.ui_connect()

    def ui_connect(self):
        self.ui.all_cb.stateChanged.connect(self.on_select_all)

        # Mark Checkboxes
        for row in range(self.ui.apertures_table.rowCount()):
            try:
                self.ui.apertures_table.cellWidget(row, 3).clicked.disconnect()
            except (TypeError, AttributeError):
                pass
            self.ui.apertures_table.cellWidget(row, 3).clicked.connect(self.on_mark_cb_click_table)

    def ui_disconnect(self):
        try:
            self.ui.all_cb.stateChanged.disconnect()
        except (AttributeError, TypeError):
            pass

        # Mark Checkboxes
        for row in range(self.ui.apertures_table.rowCount()):
            try:
                self.ui.apertures_table.cellWidget(row, 3).clicked.disconnect()
            except (TypeError, AttributeError):
                pass

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

    def on_extract_drills_click(self):
        drill_dia = self.ui.dia_entry.get_value()
        circ_r_val = self.ui.circular_ring_entry.get_value()
        oblong_r_val = self.ui.oblong_ring_entry.get_value()
        square_r_val = self.ui.square_ring_entry.get_value()
        rect_r_val = self.ui.rectangular_ring_entry.get_value()
        other_r_val = self.ui.other_ring_entry.get_value()

        prop_factor = self.ui.factor_entry.get_value() / 100.0

        tools = {}

        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            fcobj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Gerber object loaded ..."))
            return

        outname = fcobj.options['name'].rpartition('.')[0]

        mode = self.ui.hole_size_radio.get_value()

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        if mode == 'fixed':
            tools = {
                1: {
                    "tooldia": drill_dia,
                    "drills": [],
                    "slots": []
                }
            }

            for apid, apid_value in fcobj.tools.items():
                if apid in sel_apid:
                    ap_type = apid_value['type']

                    if ap_type == 'C' and self.ui.circular_cb.get_value() is False:
                        continue
                    elif ap_type == 'O' and self.ui.oblong_cb.get_value() is False:
                        continue
                    elif ap_type == 'R':
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        # if the height == width (float numbers so the reason for the following)
                        if round(width, self.decimals) == round(height, self.decimals):
                            if self.ui.square_cb.get_value() is False:
                                continue
                        elif self.ui.rectangular_cb.get_value() is False:
                            continue
                    elif ap_type not in ['C', 'R', 'O'] and self.ui.other_cb.get_value() is False:
                        continue

                    for geo_el in apid_value['geometry']:
                        if 'follow' in geo_el and isinstance(geo_el['follow'], Point):
                            tools[1]["drills"].append(geo_el['follow'])
                            if 'solid_geometry' not in tools[1]:
                                tools[1]['solid_geometry'] = [geo_el['follow']]
                            else:
                                tools[1]['solid_geometry'].append(geo_el['follow'])
            if 'solid_geometry' not in tools[1] or not tools[1]['solid_geometry']:
                self.app.inform.emit('[WARNING_NOTCL] %s' % _("No drills extracted. Try different parameters."))
                return
        elif mode == 'ring':
            drills_found = set()
            for apid, apid_value in fcobj.tools.items():
                if apid in sel_apid:
                    ap_type = apid_value['type']

                    dia = None
                    if ap_type == 'C' and self.ui.circular_cb.get_value():
                        dia = float(apid_value['size']) - (2 * circ_r_val)
                    elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])
                        if width > height:
                            dia = float(apid_value['height']) - (2 * oblong_r_val)
                        else:
                            dia = float(apid_value['width']) - (2 * oblong_r_val)
                    elif ap_type == 'R':
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        # if the height == width (float numbers so the reason for the following)
                        if abs(float('%.*f' % (self.decimals, width)) - float('%.*f' % (self.decimals, height))) < \
                                (10 ** -self.decimals):
                            if self.ui.square_cb.get_value():
                                dia = float(apid_value['height']) - (2 * square_r_val)
                        elif self.ui.rectangular_cb.get_value():
                            if width > height:
                                dia = float(apid_value['height']) - (2 * rect_r_val)
                            else:
                                dia = float(apid_value['width']) - (2 * rect_r_val)
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

                    # if dia is None then none of the above applied so we skip the following
                    if dia is None:
                        continue

                    tool_in_drills = False
                    for tool, tool_val in tools.items():
                        if abs(float('%.*f' % (
                                self.decimals,
                                tool_val["tooldia"])) - float('%.*f' % (self.decimals, dia))) < (10 ** -self.decimals):
                            tool_in_drills = tool

                    if tool_in_drills is False:
                        if tools:
                            new_tool = max([int(t) for t in tools]) + 1
                            tool_in_drills = new_tool
                        else:
                            tool_in_drills = 1

                    for geo_el in apid_value['geometry']:
                        if 'follow' in geo_el and isinstance(geo_el['follow'], Point):
                            if tool_in_drills not in tools:
                                tools[tool_in_drills] = {
                                    "tooldia": dia,
                                    "drills": [],
                                    "slots": []
                                }

                            tools[tool_in_drills]['drills'].append(geo_el['follow'])

                            if 'solid_geometry' not in tools[tool_in_drills]:
                                tools[tool_in_drills]['solid_geometry'] = [geo_el['follow']]
                            else:
                                tools[tool_in_drills]['solid_geometry'].append(geo_el['follow'])

                    if tool_in_drills in tools:
                        if 'solid_geometry' not in tools[tool_in_drills] or not tools[tool_in_drills]['solid_geometry']:
                            drills_found.add(False)
                        else:
                            drills_found.add(True)

            if True not in drills_found:
                self.app.inform.emit('[WARNING_NOTCL] %s' % _("No drills extracted. Try different parameters."))
                return
        else:
            drills_found = set()
            for apid, apid_value in fcobj.tools.items():
                if apid in sel_apid:
                    ap_type = apid_value['type']

                    dia = None
                    if ap_type == 'C' and self.ui.circular_cb.get_value():
                        dia = float(apid_value['size']) * prop_factor
                    elif ap_type == 'O' and self.ui.oblong_cb.get_value():
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])
                        if width > height:
                            dia = float(apid_value['height']) * prop_factor
                        else:
                            dia = float(apid_value['width']) * prop_factor
                    elif ap_type == 'R':
                        width = float(apid_value['width'])
                        height = float(apid_value['height'])

                        # if the height == width (float numbers so the reason for the following)
                        if abs(float('%.*f' % (self.decimals, width)) - float('%.*f' % (self.decimals, height))) < \
                                (10 ** -self.decimals):
                            if self.ui.square_cb.get_value():
                                dia = float(apid_value['height']) * prop_factor
                        elif self.ui.rectangular_cb.get_value():
                            if width > height:
                                dia = float(apid_value['height']) * prop_factor
                            else:
                                dia = float(apid_value['width']) * prop_factor
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

                    # if dia is None then none of the above applied so we skip the following
                    if dia is None:
                        continue

                    tool_in_drills = False
                    for tool, tool_val in tools.items():
                        if abs(float('%.*f' % (
                                self.decimals,
                                tool_val["tooldia"])) - float('%.*f' % (self.decimals, dia))) < (10 ** -self.decimals):
                            tool_in_drills = tool

                    if tool_in_drills is False:
                        if tools:
                            new_tool = max([int(t) for t in tools]) + 1
                            tool_in_drills = new_tool
                        else:
                            tool_in_drills = 1

                    for geo_el in apid_value['geometry']:
                        if 'follow' in geo_el and isinstance(geo_el['follow'], Point):
                            if tool_in_drills not in tools:
                                tools[tool_in_drills] = {
                                    "tooldia": dia,
                                    "drills": [],
                                    "slots": []
                                }

                            tools[tool_in_drills]['drills'].append(geo_el['follow'])

                            if 'solid_geometry' not in tools[tool_in_drills]:
                                tools[tool_in_drills]['solid_geometry'] = [geo_el['follow']]
                            else:
                                tools[tool_in_drills]['solid_geometry'].append(geo_el['follow'])

                    if tool_in_drills in tools:
                        if 'solid_geometry' not in tools[tool_in_drills] or not tools[tool_in_drills]['solid_geometry']:
                            drills_found.add(False)
                        else:
                            drills_found.add(True)

            if True not in drills_found:
                self.app.inform.emit('[WARNING_NOTCL] %s' % _("No drills extracted. Try different parameters."))
                return

        def obj_init(obj_inst, app_inst):
            obj_inst.tools = deepcopy(tools)
            obj_inst.create_geometry()
            obj_inst.source_file = app_inst.f_handlers.export_excellon(obj_name=outname, local_use=obj_inst,
                                                                       filename=None,
                                                                       use_thread=False)

        with self.app.proc_container.new('%s...' % _("Working")):
            try:
                self.app.app_obj.new_object("excellon", outname, obj_init)
            except Exception as e:
                log.error("Error on Extracted Excellon object creation: %s" % str(e))
                return

    def on_extract_soldermask_click(self):

        clearance = self.ui.clearance_entry.get_value()

        circ = self.ui.circular_cb.get_value()
        oblong = self.ui.oblong_cb.get_value()
        square = self.ui.square_cb.get_value()
        rect = self.ui.rectangular_cb.get_value()
        other = self.ui.other_cb.get_value()

        allowed_apertures = []
        if circ:
            allowed_apertures.append('C')
        if oblong:
            allowed_apertures.append('O')
        if square or rect:
            allowed_apertures.append('R')
        if other:
            allowed_apertures.append('ELSE')

        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            obj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Gerber object loaded ..."))
            return

        outname = '%s_esm' % obj.options['name'].rpartition('.')[0]

        new_apertures = deepcopy(obj.tools)
        new_solid_geometry = []
        new_follow_geometry = []

        # selected codes in the apertures UI table
        sel_apid = []
        for it in self.ui.apertures_table.selectedItems():
            sel_apid.append(int(it.text()))

        for apid, apid_value in obj.tools.items():
            if apid in sel_apid:
                ap_type = apid_value['type']

                if ap_type not in allowed_apertures:
                    new_apertures.pop(apid, None)
                    continue

                if ap_type == 'R':
                    width = float(apid_value['width'])
                    height = float(apid_value['height'])

                    # if the height == width (float numbers so the reason for the following)
                    if round(width, self.decimals) == round(height, self.decimals):
                        if square is False:
                            new_apertures.pop(apid, None)
                            continue
                    elif rect is False:
                        new_apertures.pop(apid, None)
                        continue

                if 'geometry' in apid_value:
                    new_aper_geo = []
                    for geo_el in apid_value['geometry']:
                        if 'follow' in geo_el:
                            if isinstance(geo_el['follow'], Point) and ('clear' not in geo_el or not geo_el['clear']):
                                new_follow_geometry.append(geo_el['follow'])
                                if 'solid' in geo_el:
                                    buffered_solid = geo_el['solid'].buffer(clearance)
                                    new_solid_geometry.append(buffered_solid)

                                    new_geo_el = {
                                        'solid': buffered_solid,
                                        'follow': geo_el['follow']
                                    }
                                    new_aper_geo.append(deepcopy(new_geo_el))
                    new_apertures[apid]['geometry'] = deepcopy(new_aper_geo)

        has_geometry = False
        for apid in list(new_apertures.keys()):
            if 'geometry' in new_apertures[apid]:
                if new_apertures[apid]['geometry']:
                    has_geometry = True
                else:
                    new_apertures.pop(apid, None)

        if not has_geometry:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Failed."), _("No soldermask extracted.")))
            return

        def obj_init(new_obj, app_obj):
            new_obj.multitool = False
            new_obj.multigeo = False
            new_obj.follow = False
            new_obj.tools = deepcopy(new_apertures)
            new_obj.solid_geometry = deepcopy(new_solid_geometry)
            new_obj.follow_geometry = deepcopy(new_follow_geometry)

            try:
                new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                       local_use=new_obj, use_thread=False)
            except (AttributeError, TypeError):
                pass

        with self.app.proc_container.new('%s...' % _("Working")):
            try:
                self.app.app_obj.new_object("gerber", outname, obj_init)
            except Exception as e:
                log.error("Error on Extracted Soldermask Gerber object creation: %s" % str(e))
                return

    def on_extract_cutout_click(self):
        margin = self.ui.margin_cut_entry.get_value()
        thickness = self.ui.thick_cut_entry.get_value()

        buff_radius = thickness / 2.0

        selection_index = self.ui.gerber_object_combo.currentIndex()
        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())

        try:
            obj = model_index.internalPointer().obj
        except Exception:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Gerber object loaded ..."))
            return

        outname = '%s_ecut' % obj.options['name'].rpartition('.')[0]

        cut_solid_geometry = obj.solid_geometry
        if isinstance(obj.solid_geometry, list):
            cut_solid_geometry = MultiPolygon(obj.solid_geometry)

        if isinstance(cut_solid_geometry, (MultiPolygon, Polygon)):
            x0, y0, x1, y1 = cut_solid_geometry.bounds
            object_geo = box(x0, y0, x1, y1)
        else:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Failed."), _("No cutout extracted.")))
            return

        try:
            geo_buf = object_geo.buffer(margin)
            new_geo_follow = geo_buf.exterior
            new_geo_solid = new_geo_follow.buffer(buff_radius)
        except Exception as e:
            log.error("ToolExtrct.on_extrct_cutout_click() -> %s" % str(e))
            self.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Failed."), _("No cutout extracted.")))
            return

        if not new_geo_solid.is_valid or new_geo_solid.is_empty:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Failed."), _("No cutout extracted.")))
            return

        new_apertures = {
            10: {
                'type': 'C',
                'size': thickness,
                'geometry': [
                    {
                        'solid': deepcopy(new_geo_solid),
                        'follow': deepcopy(new_geo_follow)
                    }
                ]
            }
        }

        def obj_init(new_obj, app_obj):
            new_obj.multitool = False
            new_obj.multigeo = False
            new_obj.follow = False
            new_obj.tools = deepcopy(new_apertures)
            new_obj.solid_geometry = [deepcopy(new_geo_solid)]
            new_obj.follow_geometry = [deepcopy(new_geo_follow)]

            try:
                new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None,
                                                                       local_use=new_obj, use_thread=False)
            except (AttributeError, TypeError):
                pass

        with self.app.proc_container.new('%s...' % _("Working")):
            try:
                self.app.app_obj.new_object("gerber", outname, obj_init)
            except Exception as e:
                log.error("Error on Extracted Cutout Gerber object creation: %s" % str(e))
                return

    def on_hole_size_toggle(self, val):
        if val == "fixed":
            self.ui.fixed_label.setVisible(True)
            self.ui.dia_entry.setVisible(True)
            self.ui.dia_label.setVisible(True)

            self.ui.ring_frame.setVisible(False)

            self.ui.prop_label.setVisible(False)
            self.ui.factor_label.setVisible(False)
            self.ui.factor_entry.setVisible(False)
        elif val == "ring":
            self.ui.fixed_label.setVisible(False)
            self.ui.dia_entry.setVisible(False)
            self.ui.dia_label.setVisible(False)

            self.ui.ring_frame.setVisible(True)

            self.ui.prop_label.setVisible(False)
            self.ui.factor_label.setVisible(False)
            self.ui.factor_entry.setVisible(False)
        elif val == "prop":
            self.ui.fixed_label.setVisible(False)
            self.ui.dia_entry.setVisible(False)
            self.ui.dia_label.setVisible(False)

            self.ui.ring_frame.setVisible(False)

            self.ui.prop_label.setVisible(True)
            self.ui.factor_label.setVisible(True)
            self.ui.factor_entry.setVisible(True)

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

        if self.ui.apertures_table.cellWidget(cw_row, 3).isChecked():
            # self.plot_aperture(color='#2d4606bf', marked_aperture=aperture, visible=True)
            grb_obj.plot_aperture(color=self.app.defaults['global_sel_draw_color'] + 'AA',
                                  marked_aperture=aperture, visible=True, run_thread=True)
        else:
            grb_obj.clear_plot_apertures(aperture=aperture)

    def reset_fields(self):
        self.ui.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.ui.gerber_object_combo.setCurrentIndex(0)


class ExtractUI:

    pluginName = _("Extract")

    def __init__(self, layout, app):
        self.app = app
        self.decimals = self.app.decimals
        self.layout = layout

        # ## Title
        title_label = FCLabel("%s" % self.pluginName)
        title_label.setStyleSheet("""
                                QLabel
                                {
                                    font-size: 16px;
                                    font-weight: bold;
                                }
                                """)
        self.layout.addWidget(title_label)

        self.layout.addWidget(FCLabel(""))

        # ## Grid Layout
        grid_lay = FCGridLayout(v_spacing=5, h_spacing=3)
        self.layout.addLayout(grid_lay)
        grid_lay.setColumnStretch(0, 1)
        grid_lay.setColumnStretch(1, 0)

        # ## Gerber Object
        self.gerber_object_combo = FCComboBox()
        self.gerber_object_combo.setModel(self.app.collection)
        self.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.gerber_object_combo.is_last = True
        self.gerber_object_combo.obj_type = "Gerber"

        self.grb_label = FCLabel("<b>%s:</b>" % _("GERBER"))
        self.grb_label.setToolTip('%s.' % _("Gerber object from which to extract drill holes or soldermask."))

        # grid_lay.addRow("Bottom Layer:", self.object_combo)
        grid_lay.addWidget(self.grb_label, 0, 0, 1, 2)
        grid_lay.addWidget(self.gerber_object_combo, 2, 0, 1, 2)

        self.padt_label = FCLabel("<b>%s</b>" % _("Processed Pads Type"))
        self.padt_label.setToolTip(
            _("The type of pads shape to be processed.\n"
              "If the PCB has many SMD pads with rectangular pads,\n"
              "disable the Rectangular aperture.")
        )

        grid_lay.addWidget(self.padt_label, 4, 0, 1, 2)

        pad_all_grid = FCGridLayout(v_spacing=5, h_spacing=3)
        pad_all_grid.setColumnStretch(0, 0)
        pad_all_grid.setColumnStretch(1, 1)
        grid_lay.addLayout(pad_all_grid, 5, 0, 1, 2)

        pad_grid = FCGridLayout(v_spacing=5, h_spacing=3)
        pad_grid.setColumnStretch(0, 0)
        pad_all_grid.addLayout(pad_grid, 0, 0)

        # All Aperture Selection
        self.all_cb = FCCheckBox('%s' % _("All"))
        self.all_cb.setToolTip(
            _("Process all Pads.")
        )

        pad_grid.addWidget(self.all_cb, 0, 0)

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

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.apertures_table.setSizePolicy(sizePolicy)
        self.apertures_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid_lay.addWidget(separator_line, 20, 0, 1, 2)

        # ## Grid Layout
        grid1 = FCGridLayout(v_spacing=5, h_spacing=3)
        self.layout.addLayout(grid1)
        grid1.setColumnStretch(0, 0)
        grid1.setColumnStretch(1, 1)

        # grid1.addWidget(FCLabel(""), 0, 0, 1, 2)

        self.extract_drills_label = FCLabel('<span style="color:brown;"><b>%s</b></span>' % _("Extract Drills").upper())
        self.extract_drills_label.setToolTip(
            _("Extract an Excellon object from the Gerber pads."))
        grid1.addWidget(self.extract_drills_label, 1, 0, 1, 2)

        self.method_label = FCLabel('%s:' % _("Method"))
        self.method_label.setToolTip(
            _("The method for processing pads. Can be:\n"
              "- Fixed Diameter -> all holes will have a set size\n"
              "- Fixed Annular Ring -> all holes will have a set annular ring\n"
              "- Proportional -> each hole size will be a fraction of the pad size"))
        grid1.addWidget(self.method_label, 2, 0, 1, 2)

        # ## Holes Size
        self.hole_size_radio = RadioSet(
            [
                {'label': _("Fixed Diameter"), 'value': 'fixed'},
                {'label': _("Proportional"), 'value': 'prop'},
                {'label': _("Fixed Annular Ring"), 'value': 'ring'}
            ],
            orientation='vertical',
            stretch=False)

        grid1.addWidget(self.hole_size_radio, 3, 0, 1, 2)

        # grid_lay1.addWidget(FCLabel(''))

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid1.addWidget(separator_line, 5, 0, 1, 2)

        self.ring_frame = QtWidgets.QFrame()
        self.ring_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.ring_frame)

        self.ring_box = QtWidgets.QVBoxLayout()
        self.ring_box.setContentsMargins(0, 0, 0, 0)
        self.ring_frame.setLayout(self.ring_box)

        # ## Grid Layout
        grid2 = FCGridLayout(v_spacing=5, h_spacing=3)
        grid2.setColumnStretch(0, 0)
        grid2.setColumnStretch(1, 1)
        self.ring_box.addLayout(grid2)

        # Annular Ring value
        self.ring_label = FCLabel('<b>%s</b>' % _("Fixed Annular Ring"))
        self.ring_label.setToolTip(
            _("The size of annular ring.\n"
              "The copper sliver between the hole exterior\n"
              "and the margin of the copper pad.")
        )
        grid2.addWidget(self.ring_label, 0, 0, 1, 2)

        # Circular Annular Ring Value
        self.circular_ring_label = FCLabel('%s:' % _("Circular"))
        self.circular_ring_label.setToolTip(
            _("The size of annular ring for circular pads.")
        )

        self.circular_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.circular_ring_entry.set_precision(self.decimals)
        self.circular_ring_entry.set_range(0.0000, 10000.0000)

        grid2.addWidget(self.circular_ring_label, 1, 0)
        grid2.addWidget(self.circular_ring_entry, 1, 1)

        # Oblong Annular Ring Value
        self.oblong_ring_label = FCLabel('%s:' % _("Oblong"))
        self.oblong_ring_label.setToolTip(
            _("The size of annular ring for oblong pads.")
        )

        self.oblong_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.oblong_ring_entry.set_precision(self.decimals)
        self.oblong_ring_entry.set_range(0.0000, 10000.0000)

        grid2.addWidget(self.oblong_ring_label, 2, 0)
        grid2.addWidget(self.oblong_ring_entry, 2, 1)

        # Square Annular Ring Value
        self.square_ring_label = FCLabel('%s:' % _("Square"))
        self.square_ring_label.setToolTip(
            _("The size of annular ring for square pads.")
        )

        self.square_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.square_ring_entry.set_precision(self.decimals)
        self.square_ring_entry.set_range(0.0000, 10000.0000)

        grid2.addWidget(self.square_ring_label, 3, 0)
        grid2.addWidget(self.square_ring_entry, 3, 1)

        # Rectangular Annular Ring Value
        self.rectangular_ring_label = FCLabel('%s:' % _("Rectangular"))
        self.rectangular_ring_label.setToolTip(
            _("The size of annular ring for rectangular pads.")
        )

        self.rectangular_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.rectangular_ring_entry.set_precision(self.decimals)
        self.rectangular_ring_entry.set_range(0.0000, 10000.0000)

        grid2.addWidget(self.rectangular_ring_label, 4, 0)
        grid2.addWidget(self.rectangular_ring_entry, 4, 1)

        # Others Annular Ring Value
        self.other_ring_label = FCLabel('%s:' % _("Others"))
        self.other_ring_label.setToolTip(
            _("The size of annular ring for other pads.")
        )

        self.other_ring_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.other_ring_entry.set_precision(self.decimals)
        self.other_ring_entry.set_range(0.0000, 10000.0000)

        grid2.addWidget(self.other_ring_label, 5, 0)
        grid2.addWidget(self.other_ring_entry, 5, 1)

        grid3 = FCGridLayout(v_spacing=5, h_spacing=3)
        self.layout.addLayout(grid3)
        grid3.setColumnStretch(0, 0)
        grid3.setColumnStretch(1, 1)

        # Fixed Diameter
        self.fixed_label = FCLabel('<b>%s</b>' % _("Fixed Diameter"))
        grid3.addWidget(self.fixed_label, 2, 0, 1, 2)

        # Diameter value
        self.dia_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.dia_entry.set_precision(self.decimals)
        self.dia_entry.set_range(0.0000, 10000.0000)

        self.dia_label = FCLabel('%s:' % _("Value"))
        self.dia_label.setToolTip(
            _("Fixed hole diameter.")
        )

        grid3.addWidget(self.dia_label, 4, 0)
        grid3.addWidget(self.dia_entry, 4, 1)

        # Proportional Diameter
        self.prop_label = FCLabel('<b>%s</b>' % _("Proportional Diameter"))
        grid3.addWidget(self.prop_label, 6, 0, 1, 2)

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

        grid3.addWidget(self.factor_label, 8, 0)
        grid3.addWidget(self.factor_entry, 8, 1)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid3.addWidget(separator_line, 10, 0, 1, 2)

        # Extract drills from Gerber apertures flashes (pads)
        self.e_drills_button = QtWidgets.QPushButton(_("Extract Drills"))
        self.e_drills_button.setIcon(QtGui.QIcon(self.app.resource_location + '/drill16.png'))
        self.e_drills_button.setToolTip(
            _("Extract drills from a given Gerber file.")
        )
        self.e_drills_button.setStyleSheet("""
                                        QPushButton
                                        {
                                            font-weight: bold;
                                        }
                                        """)
        grid3.addWidget(self.e_drills_button, 12, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid3.addWidget(separator_line, 14, 0, 1, 2)

        # grid3.addWidget(FCLabel(""), 16, 0, 1, 2)

        # EXTRACT SOLDERMASK
        self.extract_sm_label = FCLabel('<span style="color:purple;"><b>%s</b></span>' % _("Extract Soldermask").upper())
        self.extract_sm_label.setToolTip(
            _("Extract soldermask from a given Gerber file."))
        grid3.addWidget(self.extract_sm_label, 18, 0, 1, 2)
        
        # CLEARANCE
        self.clearance_label = FCLabel('%s:' % _("Clearance"))
        self.clearance_label.setToolTip(
            _("This set how much the soldermask extends\n"
              "beyond the margin of the pads.")
        )
        self.clearance_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.clearance_entry.set_range(0.0000, 10000.0000)
        self.clearance_entry.set_precision(self.decimals)
        self.clearance_entry.setSingleStep(0.1)

        grid3.addWidget(self.clearance_label, 20, 0)
        grid3.addWidget(self.clearance_entry, 20, 1)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid3.addWidget(separator_line, 22, 0, 1, 2)

        # Extract solderemask from Gerber apertures flashes (pads)
        self.e_sm_button = QtWidgets.QPushButton(_("Extract Soldermask"))
        self.e_sm_button.setIcon(QtGui.QIcon(self.app.resource_location + '/extract32.png'))
        self.e_sm_button.setToolTip(
            _("Extract soldermask from a given Gerber file.")
        )
        self.e_sm_button.setStyleSheet("""
                                        QPushButton
                                        {
                                            font-weight: bold;
                                        }
                                        """)
        grid3.addWidget(self.e_sm_button, 24, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid3.addWidget(separator_line, 25, 0, 1, 2)

        # EXTRACT CUTOUT
        self.extract_cut_label = FCLabel('<span style="color:green;"><b>%s</b></span>' % _("Extract Cutout").upper())
        self.extract_cut_label.setToolTip(
            _("Extract a cutout from a given Gerber file."))
        grid3.addWidget(self.extract_cut_label, 26, 0, 1, 2)

        # Margin
        self.margin_cut_label = FCLabel('%s:' % _("Margin"))
        self.margin_cut_label.setToolTip(
            _("Margin over bounds. A positive value here\n"
              "will make the cutout of the PCB further from\n"
              "the actual PCB border")
        )
        self.margin_cut_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.margin_cut_entry.set_range(-10000.0000, 10000.0000)
        self.margin_cut_entry.set_precision(self.decimals)
        self.margin_cut_entry.setSingleStep(0.1)

        grid3.addWidget(self.margin_cut_label, 28, 0)
        grid3.addWidget(self.margin_cut_entry, 28, 1)

        # Thickness
        self.thick_cut_label = FCLabel('%s:' % _("Thickness"))
        self.thick_cut_label.setToolTip(
            _("The thickness of the line that makes the cutout geometry.")
        )
        self.thick_cut_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.thick_cut_entry.set_range(0.0000, 10000.0000)
        self.thick_cut_entry.set_precision(self.decimals)
        self.thick_cut_entry.setSingleStep(0.1)

        grid3.addWidget(self.thick_cut_label, 30, 0)
        grid3.addWidget(self.thick_cut_entry, 30, 1)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid3.addWidget(separator_line, 32, 0, 1, 2)

        # Extract cutout from Gerber apertures flashes (pads)
        self.e_cut_button = QtWidgets.QPushButton(_("Extract Cutout"))
        self.e_cut_button.setIcon(QtGui.QIcon(self.app.resource_location + '/extract32.png'))
        self.e_cut_button.setToolTip(
            _("Extract a cutout from a given Gerber file.")
        )
        self.e_cut_button.setStyleSheet("""
                                               QPushButton
                                               {
                                                   font-weight: bold;
                                               }
                                               """)
        grid3.addWidget(self.e_cut_button, 34, 0, 1, 2)

        self.layout.addStretch()

        # ## Reset Tool
        self.reset_button = QtWidgets.QPushButton(_("Reset Tool"))
        self.reset_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reset32.png'))
        self.reset_button.setToolTip(
            _("Will reset the tool parameters.")
        )
        self.reset_button.setStyleSheet("""
                                QPushButton
                                {
                                    font-weight: bold;
                                }
                                """)
        self.layout.addWidget(self.reset_button)

        self.circular_ring_entry.setEnabled(False)
        self.oblong_ring_entry.setEnabled(False)
        self.square_ring_entry.setEnabled(False)
        self.rectangular_ring_entry.setEnabled(False)
        self.other_ring_entry.setEnabled(False)

        self.dia_entry.setVisible(False)
        self.dia_label.setVisible(False)
        self.factor_label.setVisible(False)
        self.factor_entry.setVisible(False)

        self.ring_frame.setVisible(False)
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
