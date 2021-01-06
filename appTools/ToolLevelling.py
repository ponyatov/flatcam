# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File by:  Marius Adrian Stanciu (c)                      #
# Date:     11/12/2020                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from appObjects.FlatCAMObj import ObjectDeleted
from appTool import AppTool
from appGUI.VisPyVisuals import *
from appGUI.PlotCanvasLegacy import ShapeCollectionLegacy
from appGUI.GUIElements import RadioSet, FCButton, FCComboBox, FCLabel, FCFileSaveDialog, FCCheckBox, FCTable, \
    FCDoubleSpinner, FCSpinner, FCDetachableTab, FCZeroAxes, FCJog, FCSliderWithDoubleSpinner, RotatedToolButton, \
    FCEntry
from appEditors.AppTextEditor import AppTextEditor

from camlib import CNCjob

from copy import deepcopy
import time
import serial
import glob
import random
import sys
from io import StringIO
from datetime import datetime

import numpy as np

from shapely.ops import unary_union
from shapely.geometry import Point, MultiPoint, box
import shapely.affinity as affinity

from matplotlib.backend_bases import KeyEvent as mpl_key_event

try:
    from shapely.ops import voronoi_diagram
    VORONOI_ENABLED = True
    # from appCommon.Common import voronoi_diagram
except Exception:
    VORONOI_ENABLED = False

import logging
import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolLevelling(AppTool, CNCjob):
    build_al_table_sig = QtCore.pyqtSignal()

    def __init__(self, app):
        self.app = app
        self.decimals = self.app.decimals

        AppTool.__init__(self, app)
        CNCjob.__init__(self, steps_per_circle=self.app.defaults["cncjob_steps_per_circle"])

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = LevelUI(layout=self.layout, app=self.app)
        self.toolName = self.ui.toolName

        # updated in the self.set_tool_ui()
        self.form_fields = {}

        self.first_click = False
        self.cursor_pos = None
        self.mouse_is_dragging = False

        # if mouse is dragging set the object True
        self.mouse_is_dragging = False

        # if mouse events are bound to local methods
        self.mouse_events_connected = False

        # event handlers references
        self.kp = None
        self.mm = None
        self.mr = None

        self.probing_gcode_text = ''
        self.grbl_probe_result = ''

        '''
        dictionary of dictionaries to store the information's for the autolevelling
        format when using Voronoi diagram:
        {
            id: {
                    'point': Shapely Point
                    'geo': Shapely Polygon from Voronoi diagram,
                    'height': float
                }
        }
        '''
        self.al_voronoi_geo_storage = {}

        '''
        list of (x, y, x) tuples to store the information's for the autolevelling
        format when using bilinear interpolation:
        [(x0, y0, z0), (x1, y1, z1), ...]
        '''
        self.al_bilinear_geo_storage = []

        self.solid_geo = None
        self.grbl_ser_port = None

        self.probing_shapes = None

        self.gcode_viewer_tab = None

        # #############################################################################################################
        # #######################################  Signals  ###########################################################
        # #############################################################################################################
        self.connect_signals_at_init()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolFollow()")
        log.debug("ToolLevelling().run() was launched ...")

        if toggle:
            # if the splitter is hidden, display it
            if self.app.ui.splitter.sizes()[0] == 0:
                self.app.ui.splitter.setSizes([1, 1])

            # if the Tool Tab is hidden display it, else hide it but only if the objectName is the same
            found_idx = None
            for idx in range(self.app.ui.notebook.count()):
                if self.app.ui.notebook.widget(idx).objectName() == "tool_tab":
                    found_idx = idx
                    break
            # show the Tab
            if not found_idx:
                self.app.ui.notebook.addTab(self.app.ui.tool_tab, _("Tool"))
                # focus on Tool Tab
                self.app.ui.notebook.setCurrentWidget(self.app.ui.tool_tab)

            try:
                if self.app.ui.tool_scroll_area.widget().objectName() == self.toolName and found_idx:
                    # if the Tool Tab is not focused, focus on it
                    if not self.app.ui.notebook.currentWidget() is self.app.ui.tool_tab:
                        # focus on Tool Tab
                        self.app.ui.notebook.setCurrentWidget(self.app.ui.tool_tab)
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

        self.app.ui.notebook.setTabText(2, _("Levelling Tool"))

    def connect_signals_at_init(self):
        self.build_al_table_sig.connect(self.build_al_table)
        self.ui.level.toggled.connect(self.on_level_changed)

        self.ui.al_mode_radio.activated_custom.connect(self.on_mode_radio)
        self.ui.al_method_radio.activated_custom.connect(self.on_method_radio)
        self.ui.al_controller_combo.currentIndexChanged.connect(self.on_controller_change)
        self.ui.plot_probing_pts_cb.stateChanged.connect(self.show_probing_geo)
        # GRBL
        self.ui.com_search_button.clicked.connect(self.on_grbl_search_ports)
        self.ui.add_bd_button.clicked.connect(self.on_grbl_add_baudrate)
        self.ui.del_bd_button.clicked.connect(self.on_grbl_delete_baudrate_grbl)
        self.ui.controller_reset_button.clicked.connect(self.on_grbl_reset)
        self.ui.com_connect_button.clicked.connect(self.on_grbl_connect)
        self.ui.grbl_send_button.clicked.connect(self.on_grbl_send_command)
        self.ui.grbl_command_entry.returnPressed.connect(self.on_grbl_send_command)

        # Jog
        self.ui.jog_wdg.jog_up_button.clicked.connect(lambda: self.on_grbl_jog(direction='yplus'))
        self.ui.jog_wdg.jog_down_button.clicked.connect(lambda: self.on_grbl_jog(direction='yminus'))
        self.ui.jog_wdg.jog_right_button.clicked.connect(lambda: self.on_grbl_jog(direction='xplus'))
        self.ui.jog_wdg.jog_left_button.clicked.connect(lambda: self.on_grbl_jog(direction='xminus'))
        self.ui.jog_wdg.jog_z_up_button.clicked.connect(lambda: self.on_grbl_jog(direction='zplus'))
        self.ui.jog_wdg.jog_z_down_button.clicked.connect(lambda: self.on_grbl_jog(direction='zminus'))
        self.ui.jog_wdg.jog_origin_button.clicked.connect(lambda: self.on_grbl_jog(direction='origin'))

        # Zero
        self.ui.zero_axs_wdg.grbl_zerox_button.clicked.connect(lambda: self.on_grbl_zero(axis='x'))
        self.ui.zero_axs_wdg.grbl_zeroy_button.clicked.connect(lambda: self.on_grbl_zero(axis='y'))
        self.ui.zero_axs_wdg.grbl_zeroz_button.clicked.connect(lambda: self.on_grbl_zero(axis='z'))
        self.ui.zero_axs_wdg.grbl_zero_all_button.clicked.connect(lambda: self.on_grbl_zero(axis='all'))
        self.ui.zero_axs_wdg.grbl_homing_button.clicked.connect(self.on_grbl_homing)

        # Sender
        self.ui.grbl_report_button.clicked.connect(lambda: self.send_grbl_command(command='?'))
        self.ui.grbl_get_param_button.clicked.connect(
            lambda: self.on_grbl_get_parameter(param=self.ui.grbl_parameter_entry.get_value()))
        self.ui.view_h_gcode_button.clicked.connect(self.on_edit_probing_gcode)
        self.ui.h_gcode_button.clicked.connect(self.on_save_probing_gcode)
        self.ui.import_heights_button.clicked.connect(self.on_import_height_map)
        self.ui.pause_resume_button.clicked.connect(self.on_grbl_pause_resume)
        self.ui.grbl_get_heightmap_button.clicked.connect(self.on_grbl_autolevel)
        self.ui.grbl_save_height_map_button.clicked.connect(self.on_grbl_heightmap_save)

        # When object selection on canvas change
        self.app.proj_selection_changed.connect(self.on_object_selection_changed)

        # Reset Tool
        self.ui.reset_button.clicked.connect(self.set_tool_ui)
        # Cleanup on Graceful exit (CTRL+ALT+X combo key)
        self.app.cleanup.connect(self.set_tool_ui)

    def set_tool_ui(self):
        self.units = self.app.defaults['units'].upper()

        # try to select in the Gerber combobox the active object
        try:
            selected_obj = self.app.collection.get_active()
            if selected_obj.kind == 'cncjob':
                current_name = selected_obj.options['name']
                self.ui.object_combo.set_value(current_name)
        except Exception:
            pass

        loaded_obj = self.app.collection.get_by_name(self.ui.object_combo.get_value())
        if loaded_obj:
            name = loaded_obj.options['name']
        else:
            name = ''

        # Shapes container for the Voronoi cells in Autolevelling
        if self.app.is_legacy is False:
            self.probing_shapes = ShapeCollection(parent=self.app.plotcanvas.view.scene, layers=1)
        else:
            self.probing_shapes = ShapeCollectionLegacy(obj=self, app=self.app, name=name + "_probing_shapes")

        self.form_fields.update({
            "tools_al_travelz":       self.ui.ptravelz_entry,
            "tools_al_probe_depth":   self.ui.pdepth_entry,
            "tools_al_probe_fr":      self.ui.feedrate_probe_entry,
            "tools_al_controller":    self.ui.al_controller_combo,
            "tools_al_method":        self.ui.al_method_radio,
            "tools_al_mode":          self.ui.al_mode_radio,
            "tools_al_rows":          self.ui.al_rows_entry,
            "tools_al_columns":       self.ui.al_columns_entry,
            "tools_al_grbl_jog_step": self.ui.jog_step_entry,
            "tools_al_grbl_jog_fr":   self.ui.jog_fr_entry,
        })

        # Fill Form fields
        self.to_form()

        self.ui.al_probe_points_table.setRowCount(0)
        self.ui.al_probe_points_table.resizeColumnsToContents()
        self.ui.al_probe_points_table.resizeRowsToContents()
        v_header = self.ui.al_probe_points_table.verticalHeader()
        v_header.hide()
        self.ui.al_probe_points_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        h_header = self.ui.al_probe_points_table.horizontalHeader()
        h_header.setMinimumSectionSize(10)
        h_header.setDefaultSectionSize(70)
        h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        h_header.resizeSection(0, 20)
        h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        self.ui.al_probe_points_table.setMinimumHeight(self.ui.al_probe_points_table.getHeight())
        self.ui.al_probe_points_table.setMaximumHeight(self.ui.al_probe_points_table.getHeight())

        # Set initial UI
        self.ui.al_rows_entry.setDisabled(True)
        self.ui.al_rows_label.setDisabled(True)
        self.ui.al_columns_entry.setDisabled(True)
        self.ui.al_columns_label.setDisabled(True)
        self.ui.al_method_lbl.setDisabled(True)
        self.ui.al_method_radio.setDisabled(True)
        self.ui.al_method_radio.set_value('v')

        target_obj = self.app.collection.get_by_name(self.ui.object_combo.get_value())
        if target_obj and target_obj.is_segmented_gcode is True:
            self.ui.al_frame.setDisabled(False)
            self.ui.al_mode_radio.set_value(target_obj.options['tools_al_mode'])
            self.on_controller_change()

            self.on_mode_radio(val=target_obj.options['tools_al_mode'])
            self.on_method_radio(val=target_obj.options['tools_al_method'])
        else:
            self.ui.al_frame.setDisabled(True)

        # Show/Hide Advanced Options
        app_mode = self.app.defaults["global_app_level"]
        self.change_level(app_mode)

        try:
            self.ui.object_combo.currentIndexChanged.disconnect()
        except (AttributeError, TypeError):
            pass
        self.ui.object_combo.currentIndexChanged.connect(self.on_object_changed)

        self.build_tool_ui()

    def on_object_changed(self):

        # load the object
        obj_name = self.ui.object_combo.currentText()

        # Get source object.
        try:
            target_obj = self.app.collection.get_by_name(obj_name)
        except Exception:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Could not retrieve object"), str(obj_name)))
            return

        if target_obj is None or target_obj.is_segmented_gcode is False:
            self.ui.al_frame.setDisabled(True)
        else:
            self.ui.al_frame.setDisabled(False)

            # Shapes container for the Voronoi cells in Autolevelling
            if self.app.is_legacy is False:
                self.probing_shapes = ShapeCollection(parent=self.app.plotcanvas.view.scene, layers=1)
            else:
                self.probing_shapes = ShapeCollectionLegacy(obj=self, app=self.app, name=obj_name + "_probing_shapes")

    def on_object_selection_changed(self, current, previous):
        try:
            sel_obj = current.indexes()[0].internalPointer().obj
            name = sel_obj.options['name']
            kind = sel_obj.kind

            if kind == 'cncjob':
                self.ui.object_combo.set_value(name)
        except IndexError:
            pass

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

        target_obj = self.app.collection.get_by_name(self.ui.object_combo.get_value())

        # if 'Roland' in target_obj.pp_excellon_name or 'Roland' in target_obj.pp_geometry_name or 'hpgl' in \
        #         target_obj.pp_geometry_name:
        #     # TODO DO NOT AUTOLEVELL
        #     pass

        if not checked:
            self.ui.level.setText('%s' % _('Beginner'))
            self.ui.level.setStyleSheet("""
                                        QToolButton
                                        {
                                            color: green;
                                        }
                                        """)

            self.ui.al_title.hide()
            self.ui.show_al_table.hide()
            self.ui.al_probe_points_table.hide()

            # Context Menu section
            # self.ui.al_probe_points_table.removeContextMenu()
        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                        QToolButton
                                        {
                                            color: red;
                                        }
                                        """)

            self.ui.al_title.show()
            self.ui.show_al_table.show()
            if self.ui.show_al_table.get_value():
                self.ui.al_probe_points_table.show()

            # Context Menu section
            # self.ui.al_probe_points_table.setupContextMenu()

    def build_tool_ui(self):
        self.ui_disconnect()

        self.build_al_table()

        self.ui_connect()

    def build_al_table(self):
        tool_idx = 0

        n = len(self.al_voronoi_geo_storage)
        self.ui.al_probe_points_table.setRowCount(n)

        for id_key, value in self.al_voronoi_geo_storage.items():
            tool_idx += 1
            row_no = tool_idx - 1

            t_id = QtWidgets.QTableWidgetItem('%d' % int(tool_idx))
            x = value['point'].x
            y = value['point'].y
            xy_coords = self.app.dec_format(x, dec=self.app.decimals), self.app.dec_format(y, dec=self.app.decimals)
            coords_item = QtWidgets.QTableWidgetItem(str(xy_coords))
            height = self.app.dec_format(value['height'], dec=self.app.decimals)
            height_item = QtWidgets.QTableWidgetItem(str(height))

            t_id.setFlags(QtCore.Qt.ItemIsEnabled)
            coords_item.setFlags(QtCore.Qt.ItemIsEnabled)
            height_item.setFlags(QtCore.Qt.ItemIsEnabled)

            self.ui.al_probe_points_table.setItem(row_no, 0, t_id)  # Tool name/id
            self.ui.al_probe_points_table.setItem(row_no, 1, coords_item)  # X-Y coords
            self.ui.al_probe_points_table.setItem(row_no, 2, height_item)  # Determined Height

        self.ui.al_probe_points_table.resizeColumnsToContents()
        self.ui.al_probe_points_table.resizeRowsToContents()

        h_header = self.ui.al_probe_points_table.horizontalHeader()
        h_header.setMinimumSectionSize(10)
        h_header.setDefaultSectionSize(70)
        h_header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        h_header.resizeSection(0, 20)
        h_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        h_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        self.ui.al_probe_points_table.setMinimumHeight(self.ui.al_probe_points_table.getHeight())
        self.ui.al_probe_points_table.setMaximumHeight(self.ui.al_probe_points_table.getHeight())

        if self.ui.al_probe_points_table.model().rowCount():
            self.ui.grbl_get_heightmap_button.setDisabled(False)
            self.ui.grbl_save_height_map_button.setDisabled(False)
            self.ui.h_gcode_button.setDisabled(False)
            self.ui.view_h_gcode_button.setDisabled(False)
        else:
            self.ui.grbl_get_heightmap_button.setDisabled(True)
            self.ui.grbl_save_height_map_button.setDisabled(True)
            self.ui.h_gcode_button.setDisabled(True)
            self.ui.view_h_gcode_button.setDisabled(True)

    def to_form(self, storage=None):
        if storage is None:
            storage = self.app.options

        for k in self.form_fields:
            for option in storage:
                if option.startswith('tools_al_'):
                    if k == option:
                        try:
                            self.form_fields[k].set_value(storage[option])
                        except Exception:
                            # it may fail for form fields found in the tools tables if there are no rows
                            pass

    def on_add_al_probepoints(self):
        # create the solid_geo

        self.solid_geo = unary_union([geo['geom'] for geo in self.gcode_parsed if geo['kind'][0] == 'C'])

        # reset al table
        self.ui.al_probe_points_table.setRowCount(0)

        # reset the al dict
        self.al_voronoi_geo_storage.clear()

        xmin, ymin, xmax, ymax = self.solid_geo.bounds

        if self.ui.al_mode_radio.get_value() == 'grid':
            width = abs(xmax - xmin)
            height = abs(ymax - ymin)
            cols = self.ui.al_columns_entry.get_value()
            rows = self.ui.al_rows_entry.get_value()

            dx = 0 if cols == 1 else width / (cols - 1)
            dy = 0 if rows == 1 else height / (rows - 1)

            points = []
            new_y = ymin
            for x in range(rows):
                new_x = xmin
                for y in range(cols):
                    formatted_point = (
                        self.app.dec_format(new_x, self.app.decimals),
                        self.app.dec_format(new_y, self.app.decimals)
                    )
                    points.append(formatted_point)
                    new_x += dx
                new_y += dy

            pt_id = 0
            vor_pts_list = []
            bl_pts_list = []
            for point in points:
                pt_id += 1
                pt = Point(point)
                vor_pts_list.append(pt)
                bl_pts_list.append((point[0], point[1], 0.0))
                new_dict = {
                    'point': pt,
                    'geo': None,
                    'height': 0.0
                }
                self.al_voronoi_geo_storage[pt_id] = deepcopy(new_dict)

            al_method = self.ui.al_method_radio.get_value()
            if al_method == 'v':
                if VORONOI_ENABLED is True:
                    self.generate_voronoi_geometry(pts=vor_pts_list)
                    # generate Probing GCode
                    self.probing_gcode_text = self.probing_gcode(storage=self.al_voronoi_geo_storage)
                else:
                    self.app.inform.emit('[ERROR_NOTCL] %s' % _("Voronoi function can not be loaded.\n"
                                                                "Shapely >= 1.8 is required"))
            else:
                self.generate_bilinear_geometry(pts=bl_pts_list)
                # generate Probing GCode
                self.probing_gcode_text = self.probing_gcode(storage=self.al_bilinear_geo_storage)

            self.build_al_table_sig.emit()
            if self.ui.plot_probing_pts_cb.get_value():
                self.show_probing_geo(state=True, reset=True)
            else:
                # clear probe shapes
                self.plot_probing_geo(None, False)

        else:
            f_probe_pt = Point([xmin, xmin])
            int_keys = [int(k) for k in self.al_voronoi_geo_storage.keys()]
            new_id = max(int_keys) + 1 if int_keys else 1
            new_dict = {
                'point': f_probe_pt,
                'geo': None,
                'height': 0.0
            }
            self.al_voronoi_geo_storage[new_id] = deepcopy(new_dict)

            radius = 0.3 if self.units == 'MM' else 0.012
            fprobe_pt_buff = f_probe_pt.buffer(radius)

            self.app.inform.emit(_("Click on canvas to add a Probe Point..."))
            self.app.defaults['global_selection_shape'] = False

            if self.app.is_legacy is False:
                self.app.plotcanvas.graph_event_disconnect('key_press', self.app.ui.keyPressEvent)
                self.app.plotcanvas.graph_event_disconnect('mouse_press', self.app.on_mouse_click_over_plot)
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.app.on_mouse_click_release_over_plot)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.app.kp)
                self.app.plotcanvas.graph_event_disconnect(self.app.mp)
                self.app.plotcanvas.graph_event_disconnect(self.app.mr)

            self.kp = self.app.plotcanvas.graph_event_connect('key_press', self.on_key_press)
            self.mr = self.app.plotcanvas.graph_event_connect('mouse_release', self.on_mouse_click_release)

            self.mouse_events_connected = True

            self.build_al_table_sig.emit()
            if self.ui.plot_probing_pts_cb.get_value():
                self.show_probing_geo(state=True, reset=True)
            else:
                # clear probe shapes
                self.plot_probing_geo(None, False)

            self.plot_probing_geo(geometry=fprobe_pt_buff, visibility=True, custom_color="#0000FFFA")

    def show_probing_geo(self, state, reset=False):

        if reset:
            self.probing_shapes.clear(update=True)

        points_geo = []
        poly_geo = []

        al_method = self.ui.al_method_radio.get_value()
        # voronoi diagram
        if al_method == 'v':
            # create the geometry
            radius = 0.1 if self.units == 'MM' else 0.004
            for pt in self.al_voronoi_geo_storage:
                if not self.al_voronoi_geo_storage[pt]['geo']:
                    continue

                p_geo = self.al_voronoi_geo_storage[pt]['point'].buffer(radius)
                s_geo = self.al_voronoi_geo_storage[pt]['geo'].buffer(0.0000001)

                points_geo.append(p_geo)
                poly_geo.append(s_geo)

            if not points_geo and not poly_geo:
                return

            self.plot_probing_geo(geometry=points_geo, visibility=state, custom_color='#000000FF')
            self.plot_probing_geo(geometry=poly_geo, visibility=state)
        # bilinear interpolation
        elif al_method == 'b':
            radius = 0.1 if self.units == 'MM' else 0.004
            for pt in self.al_bilinear_geo_storage:

                x_pt = pt[0]
                y_pt = pt[1]
                p_geo = Point([x_pt, y_pt]).buffer(radius)

                if p_geo.is_valid:
                    points_geo.append(p_geo)

            if not points_geo:
                return

            self.plot_probing_geo(geometry=points_geo, visibility=state, custom_color='#000000FF')

    def plot_probing_geo(self, geometry, visibility, custom_color=None):
        if visibility:
            if self.app.is_legacy is False:
                def random_color():
                    r_color = np.random.rand(4)
                    r_color[3] = 0.5
                    return r_color
            else:
                def random_color():
                    while True:
                        r_color = np.random.rand(4)
                        r_color[3] = 0.5

                        new_color = '#'
                        for idx in range(len(r_color)):
                            new_color += '%x' % int(r_color[idx] * 255)
                        # do it until a valid color is generated
                        # a valid color has the # symbol, another 6 chars for the color and the last 2 chars for alpha
                        # for a total of 9 chars
                        if len(new_color) == 9:
                            break
                    return new_color

            try:
                # if self.app.is_legacy is False:
                #     color = "#0000FFFE"
                # else:
                #     color = "#0000FFFE"
                # for sh in points_geo:
                #     self.add_probing_shape(shape=sh, color=color, face_color=color, visible=True)

                edge_color = "#000000FF"
                try:
                    for sh in geometry:
                        if custom_color is None:
                            self.add_probing_shape(shape=sh, color=edge_color, face_color=random_color(), visible=True)
                        else:
                            self.add_probing_shape(shape=sh, color=custom_color, face_color=custom_color, visible=True)
                except TypeError:
                    if custom_color is None:
                        self.add_probing_shape(
                            shape=geometry, color=edge_color, face_color=random_color(), visible=True)
                    else:
                        self.add_probing_shape(
                            shape=geometry, color=custom_color, face_color=custom_color, visible=True)

                self.probing_shapes.redraw()
            except (ObjectDeleted, AttributeError):
                self.probing_shapes.clear(update=True)
            except Exception as e:
                self.app.log.error("CNCJobObject.plot_probing_geo() --> %s" % str(e))
        else:
            self.probing_shapes.clear(update=True)

    def add_probing_shape(self, **kwargs):
        if self.deleted:
            raise ObjectDeleted()
        else:
            key = self.probing_shapes.add(tolerance=self.drawing_tolerance, layer=0, **kwargs)
        return key

    def generate_voronoi_geometry(self, pts):
        env = self.solid_geo.envelope
        fact = 1 if self.units == 'MM' else 0.039
        env = env.buffer(fact)

        new_pts = deepcopy(pts)
        try:
            pts_union = MultiPoint(pts)
            voronoi_union = voronoi_diagram(geom=pts_union, envelope=env)
        except Exception as e:
            self.app.log.error("CNCJobObject.generate_voronoi_geometry() --> %s" % str(e))
            for pt_index in range(len(pts)):
                new_pts[pt_index] = affinity.translate(
                    new_pts[pt_index], random.random() * 1e-09, random.random() * 1e-09)

            pts_union = MultiPoint(new_pts)
            try:
                voronoi_union = voronoi_diagram(geom=pts_union, envelope=env)
            except Exception:
                return

        new_voronoi = []
        for p in voronoi_union:
            new_voronoi.append(p.intersection(env))

        for pt_key in list(self.al_voronoi_geo_storage.keys()):
            for poly in new_voronoi:
                if self.al_voronoi_geo_storage[pt_key]['point'].within(poly):
                    self.al_voronoi_geo_storage[pt_key]['geo'] = poly

    def generate_bilinear_geometry(self, pts):
        self.al_bilinear_geo_storage = pts

    # To be called after clicking on the plot.
    def on_mouse_click_release(self, event):

        if self.app.is_legacy is False:
            event_pos = event.pos
            # event_is_dragging = event.is_dragging
            right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            # event_is_dragging = self.app.plotcanvas.is_dragging
            right_button = 3

        try:
            x = float(event_pos[0])
            y = float(event_pos[1])
        except TypeError:
            return
        event_pos = (x, y)

        # do paint single only for left mouse clicks
        if event.button == 1:
            pos = self.app.plotcanvas.translate_coords(event_pos)

            # use the snapped position as reference
            snapped_pos = self.app.geo_editor.snap(pos[0], pos[1])

            probe_pt = Point(snapped_pos)

            xxmin, yymin, xxmax, yymax = self.solid_geo.bounds
            box_geo = box(xxmin, yymin, xxmax, yymax)
            if not probe_pt.within(box_geo):
                self.app.inform.emit(_("Point is not within the object area. Choose another point."))
                return

            int_keys = [int(k) for k in self.al_voronoi_geo_storage.keys()]
            new_id = max(int_keys) + 1 if int_keys else 1
            new_dict = {
                'point': probe_pt,
                'geo': None,
                'height': 0.0
            }
            self.al_voronoi_geo_storage[new_id] = deepcopy(new_dict)

            # rebuild the al table
            self.build_al_table_sig.emit()

            radius = 0.3 if self.units == 'MM' else 0.012
            probe_pt_buff = probe_pt.buffer(radius)

            self.plot_probing_geo(geometry=probe_pt_buff, visibility=True, custom_color="#0000FFFA")

            self.app.inform.emit(_("Added a Probe Point... Click again to add another or right click to finish ..."))

        # if RMB then we exit
        elif event.button == right_button and self.mouse_is_dragging is False:
            if self.app.is_legacy is False:
                self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_mouse_click_release)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.kp)
                self.app.plotcanvas.graph_event_disconnect(self.mr)

            self.app.kp = self.app.plotcanvas.graph_event_connect('key_press', self.app.ui.keyPressEvent)
            self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press', self.app.on_mouse_click_over_plot)
            self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                  self.app.on_mouse_click_release_over_plot)

            # signal that the mouse events are disconnected from local methods
            self.mouse_events_connected = False

            # restore selection
            self.app.defaults['global_selection_shape'] = self.old_selection_state

            self.app.inform.emit(_("Finished adding Probe Points..."))

            al_method = self.ui.al_method_radio.get_value()
            if al_method == 'v':
                if VORONOI_ENABLED is True:
                    pts_list = []
                    for k in self.al_voronoi_geo_storage:
                        pts_list.append(self.al_voronoi_geo_storage[k]['point'])
                    self.generate_voronoi_geometry(pts=pts_list)

                    self.probing_gcode_text = self.probing_gcode(self.al_voronoi_geo_storage)
                else:
                    self.app.inform.emit('[ERROR_NOTCL] %s' % _("Voronoi function can not be loaded.\n"
                                                                "Shapely >= 1.8 is required"))

            # rebuild the al table
            self.build_al_table_sig.emit()

            if self.ui.plot_probing_pts_cb.get_value():
                self.show_probing_geo(state=True, reset=True)
            else:
                # clear probe shapes
                self.plot_probing_geo(None, False)

    def on_key_press(self, event):
        # events out of the self.app.collection view (it's about Project Tab) are of type int
        if type(event) is int:
            key = event
        # events from the GUI are of type QKeyEvent
        elif type(event) == QtGui.QKeyEvent:
            key = event.key()
        elif isinstance(event, mpl_key_event):  # MatPlotLib key events are trickier to interpret than the rest
            key = event.key
            key = QtGui.QKeySequence(key)

            # check for modifiers
            key_string = key.toString().lower()
            if '+' in key_string:
                mod, __, key_text = key_string.rpartition('+')
                if mod.lower() == 'ctrl':
                    # modifiers = QtCore.Qt.ControlModifier
                    pass
                elif mod.lower() == 'alt':
                    # modifiers = QtCore.Qt.AltModifier
                    pass
                elif mod.lower() == 'shift':
                    # modifiers = QtCore.Qt.ShiftModifier
                    pass
                else:
                    # modifiers = QtCore.Qt.NoModifier
                    pass
                key = QtGui.QKeySequence(key_text)
        # events from Vispy are of type KeyEvent
        else:
            key = event.key

        # Escape = Deselect All
        if key == QtCore.Qt.Key_Escape or key == 'Escape':
            if self.mouse_events_connected is True:
                self.mouse_events_connected = False
                if self.app.is_legacy is False:
                    self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
                    self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_mouse_click_release)
                else:
                    self.app.plotcanvas.graph_event_disconnect(self.kp)
                    self.app.plotcanvas.graph_event_disconnect(self.mr)

                self.app.kp = self.app.plotcanvas.graph_event_connect('key_press', self.app.ui.keyPressEvent)
                self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press', self.app.on_mouse_click_over_plot)
                self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                      self.app.on_mouse_click_release_over_plot)

        # Grid toggle
        if key == QtCore.Qt.Key_G or key == 'G':
            self.app.ui.grid_snap_btn.trigger()

        # Jump to coords
        if key == QtCore.Qt.Key_J or key == 'J':
            self.app.on_jump_to()

    def autolevell_gcode(self):
        pass

    def autolevell_gcode_line(self, gcode_line):
        al_method = self.ui.al_method_radio.get_value()

        coords = ()

        if al_method == 'v':
            self.autolevell_voronoi(gcode_line, coords)
        elif al_method == 'b':
            self.autolevell_bilinear(gcode_line, coords)

    def autolevell_bilinear(self, gcode_line, coords):
        pass

    def autolevell_voronoi(self, gcode_line, coords):
        pass

    def on_show_al_table(self, state):
        self.ui.al_probe_points_table.show() if state else self.ui.al_probe_points_table.hide()

    def on_mode_radio(self, val):
        # reset al table
        self.ui.al_probe_points_table.setRowCount(0)

        # reset the al dict
        self.al_voronoi_geo_storage.clear()

        # reset Voronoi Shapes
        self.probing_shapes.clear(update=True)

        # build AL table
        self.build_al_table()

        if val == "manual":
            self.ui.al_rows_entry.setDisabled(True)
            self.ui.al_rows_label.setDisabled(True)
            self.ui.al_columns_entry.setDisabled(True)
            self.ui.al_columns_label.setDisabled(True)
            self.ui.al_method_lbl.setDisabled(True)
            self.ui.al_method_radio.setDisabled(True)
            self.ui.al_method_radio.set_value('v')
        else:
            self.ui.al_rows_entry.setDisabled(False)
            self.ui.al_rows_label.setDisabled(False)
            self.ui.al_columns_entry.setDisabled(False)
            self.ui.al_columns_label.setDisabled(False)
            self.ui.al_method_lbl.setDisabled(False)
            self.ui.al_method_radio.setDisabled(False)
            self.ui.al_method_radio.set_value(self.app.defaults['tools_al_method'])

    def on_method_radio(self, val):
        if val == 'b':
            self.ui.al_columns_entry.setMinimum(2)
            self.ui.al_rows_entry.setMinimum(2)
        else:
            self.ui.al_columns_entry.setMinimum(1)
            self.ui.al_rows_entry.setMinimum(1)

    def on_controller_change(self):
        if self.ui.al_controller_combo.get_value() == 'GRBL':
            self.ui.h_gcode_button.hide()
            self.ui.view_h_gcode_button.hide()

            self.ui.import_heights_button.hide()
            self.ui.grbl_frame.show()
            self.on_grbl_search_ports(muted=True)
        else:
            self.ui.h_gcode_button.show()
            self.ui.view_h_gcode_button.show()

            self.ui.import_heights_button.show()
            self.ui.grbl_frame.hide()

        # if the is empty then there is a chance that we've added probe points but the GRBL controller was selected
        # therefore no Probing GCode was genrated (it is different for GRBL on how it gets it's Probing GCode
        if not self.probing_gcode_text or self.probing_gcode_text == '':
            # generate Probing GCode
            al_method = self.ui.al_method_radio.get_value()
            storage = self.al_voronoi_geo_storage if al_method == 'v' else self.al_bilinear_geo_storage
            self.probing_gcode_text = self.probing_gcode(storage=storage)

    @staticmethod
    def on_grbl_list_serial_ports():
        """
        Lists serial port names.
        From here: https://stackoverflow.com/questions/12090503/listing-available-com-ports-with-python

        :raises EnvironmentError:   On unsupported or unknown platforms
        :returns:                   A list of the serial ports available on the system
        """

        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        s = serial.Serial()

        for port in ports:
            s.port = port

            try:
                s.open()
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                # result.append(port + " (in use)")
                pass

        return result

    def on_grbl_search_ports(self, muted=None):
        port_list = self.on_grbl_list_serial_ports()
        self.ui.com_list_combo.clear()
        self.ui.com_list_combo.addItems(port_list)
        if muted is not True:
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("COM list updated ..."))

    def on_grbl_connect(self):
        port_name = self.ui.com_list_combo.currentText()
        if " (" in port_name:
            port_name = port_name.rpartition(" (")[0]

        baudrate = int(self.ui.baudrates_list_combo.currentText())

        try:
            self.grbl_ser_port = serial.serial_for_url(port_name, baudrate,
                                                       bytesize=serial.EIGHTBITS,
                                                       parity=serial.PARITY_NONE,
                                                       stopbits=serial.STOPBITS_ONE,
                                                       timeout=0.1,
                                                       xonxoff=False,
                                                       rtscts=False)

            # Toggle DTR to reset the controller loaded with GRBL (Arduino, ESP32, etc)
            try:
                self.grbl_ser_port.dtr = False
            except IOError:
                pass

            self.grbl_ser_port.reset_input_buffer()

            try:
                self.grbl_ser_port.dtr = True
            except IOError:
                pass

            answer = self.on_grbl_wake()
            answer = ['ok']   # FIXME: hack for development without a GRBL controller connected
            for line in answer:
                if 'ok' in line.lower():
                    self.ui.com_connect_button.setStyleSheet("QPushButton {background-color: seagreen;}")
                    self.ui.com_connect_button.setText(_("Connected"))
                    self.ui.controller_reset_button.setDisabled(False)

                    for idx in range(self.ui.al_toolbar.count()):
                        if self.ui.al_toolbar.tabText(idx) == _("Connect"):
                            self.ui.al_toolbar.tabBar.setTabTextColor(idx, QtGui.QColor('seagreen'))
                        if self.ui.al_toolbar.tabText(idx) == _("Control"):
                            self.ui.al_toolbar.tabBar.setTabEnabled(idx, True)
                        if self.ui.al_toolbar.tabText(idx) == _("Sender"):
                            self.ui.al_toolbar.tabBar.setTabEnabled(idx, True)

                    self.app.inform.emit("%s: %s" % (_("Port connected"), port_name))
                    return

            self.grbl_ser_port.close()
            self.app.inform.emit("[ERROR_NOTCL] %s: %s" % (_("Could not connect to GRBL on port"), port_name))

        except serial.SerialException:
            self.grbl_ser_port = serial.Serial()
            self.grbl_ser_port.port = port_name
            self.grbl_ser_port.close()
            self.ui.com_connect_button.setStyleSheet("QPushButton {background-color: red;}")
            self.ui.com_connect_button.setText(_("Disconnected"))
            self.ui.controller_reset_button.setDisabled(True)

            for idx in range(self.ui.al_toolbar.count()):
                if self.ui.al_toolbar.tabText(idx) == _("Connect"):
                    self.ui.al_toolbar.tabBar.setTabTextColor(idx, QtGui.QColor('red'))
                if self.ui.al_toolbar.tabText(idx) == _("Control"):
                    self.ui.al_toolbar.tabBar.setTabEnabled(idx, False)
                if self.ui.al_toolbar.tabText(idx) == _("Sender"):
                    self.ui.al_toolbar.tabBar.setTabEnabled(idx, False)
            self.app.inform.emit("%s: %s" % (_("Port is connected. Disconnecting"), port_name))
        except Exception:
            self.app.inform.emit("[ERROR_NOTCL] %s: %s" % (_("Could not connect to port"), port_name))

    def on_grbl_add_baudrate(self):
        new_bd = str(self.ui.new_baudrate_entry.get_value())
        if int(new_bd) >= 40 and new_bd not in self.ui.baudrates_list_combo.model().stringList():
            self.ui.baudrates_list_combo.addItem(new_bd)
            self.ui.baudrates_list_combo.setCurrentText(new_bd)

    def on_grbl_delete_baudrate_grbl(self):
        current_idx = self.ui.baudrates_list_combo.currentIndex()
        self.ui.baudrates_list_combo.removeItem(current_idx)

    def on_grbl_wake(self):
        # Wake up grbl
        self.grbl_ser_port.write("\r\n\r\n".encode('utf-8'))
        # Wait for GRBL controller to initialize
        time.sleep(1)

        grbl_out = deepcopy(self.grbl_ser_port.readlines())
        self.grbl_ser_port.reset_input_buffer()

        return grbl_out

    def on_grbl_send_command(self):
        cmd = self.ui.grbl_command_entry.get_value()

        # show the Shell Dock
        self.app.ui.shell_dock.show()

        def worker_task():
            with self.app.proc_container.new('%s...' % _("Sending")):
                self.send_grbl_command(command=cmd)

        self.app.worker_task.emit({'fcn': worker_task, 'params': []})

    def send_grbl_command(self, command, echo=True):
        """

        :param command: GCode command
        :type command:  str
        :param echo:    if to send a '\n' char after
        :type echo:     bool
        :return:        the text returned by the GRBL controller after each command
        :rtype:         str
        """
        cmd = command.strip()
        if echo:
            self.app.inform_shell[str, bool].emit(cmd, False)

        # Send Gcode command to GRBL
        snd = cmd + '\n'
        self.grbl_ser_port.write(snd.encode('utf-8'))
        grbl_out = self.grbl_ser_port.readlines()
        if not grbl_out:
            self.app.inform_shell[str, bool].emit('\t\t\t: No answer\n', False)

        result = ''
        for line in grbl_out:
            if echo:
                try:
                    self.app.inform_shell.emit('\t\t\t: ' + line.decode('utf-8').strip().upper())
                except Exception as e:
                    self.app.log.error("CNCJobObject.send_grbl_command() --> %s" % str(e))
            if 'ok' in line:
                result = grbl_out

        return result

    def send_grbl_block(self, command, echo=True):
        stripped_cmd = command.strip()

        for grbl_line in stripped_cmd.split('\n'):
            if echo:
                self.app.inform_shell[str, bool].emit(grbl_line, False)

            # Send Gcode block to GRBL
            snd = grbl_line + '\n'
            self.grbl_ser_port.write(snd.encode('utf-8'))
            grbl_out = self.grbl_ser_port.readlines()

            for line in grbl_out:
                if echo:
                    try:
                        self.app.inform_shell.emit(' : ' + line.decode('utf-8').strip().upper())
                    except Exception as e:
                        self.app.log.error("CNCJobObject.send_grbl_block() --> %s" % str(e))

    def on_grbl_get_parameter(self, param):
        if '$' in param:
            param = param.replace('$', '')

        snd = '$$\n'
        self.grbl_ser_port.write(snd.encode('utf-8'))
        grbl_out = self.grbl_ser_port.readlines()
        for line in grbl_out:
            decoded_line = line.decode('utf-8')
            par = '$%s' % str(param)
            if par in decoded_line:
                result = float(decoded_line.rpartition('=')[2])
                self.app.shell_message("GRBL Parameter: %s = %s" % (str(param), str(result)), show=True)
                return result

    def on_grbl_jog(self, direction=None):
        if direction is None:
            return
        cmd = ''

        step = self.ui.jog_step_entry.get_value(),
        feedrate = self.ui.jog_fr_entry.get_value()
        travelz = float(self.app.defaults["tools_al_grbl_travelz"])

        if direction == 'xplus':
            cmd = "$J=G91 %s X%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))
        if direction == 'xminus':
            cmd = "$J=G91 %s X-%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))
        if direction == 'yplus':
            cmd = "$J=G91 %s Y%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))
        if direction == 'yminus':
            cmd = "$J=G91 %s Y-%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))

        if direction == 'zplus':
            cmd = "$J=G91 %s Z%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))
        if direction == 'zminus':
            cmd = "$J=G91 %s Z-%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(step), str(feedrate))

        if direction == 'origin':
            cmd = "$J=G90 %s Z%s F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(travelz), str(feedrate))
            self.send_grbl_command(command=cmd, echo=False)
            cmd = "$J=G90 %s X0.0 Y0.0 F%s" % ({'IN': 'G20', 'MM': 'G21'}[self.units], str(feedrate))
            self.send_grbl_command(command=cmd, echo=False)
            return

        self.send_grbl_command(command=cmd, echo=False)

    def on_grbl_zero(self, axis):
        current_mode = self.on_grbl_get_parameter('10')
        if current_mode is None:
            return

        cmd = '$10=0'
        self.send_grbl_command(command=cmd, echo=False)

        if axis == 'x':
            cmd = 'G10 L2 P1 X0'
        elif axis == 'y':
            cmd = 'G10 L2 P1 Y0'
        elif axis == 'z':
            cmd = 'G10 L2 P1 Z0'
        else:
            # all
            cmd = 'G10 L2 P1 X0 Y0 Z0'
        self.send_grbl_command(command=cmd, echo=False)

        # restore previous mode
        cmd = '$10=%d' % int(current_mode)
        self.send_grbl_command(command=cmd, echo=False)

    def on_grbl_homing(self):
        cmd = '$H'
        self.app.inform.emit("%s" % _("GRBL is doing a home cycle."))
        self.on_grbl_wake()
        self.send_grbl_command(command=cmd)

    def on_grbl_reset(self):
        cmd = '\x18'
        self.app.inform.emit("%s" % _("GRBL software reset was sent."))
        self.on_grbl_wake()
        self.send_grbl_command(command=cmd)

    def on_grbl_pause_resume(self, checked):
        if checked is False:
            cmd = '~'
            self.send_grbl_command(command=cmd)
            self.app.inform.emit("%s" % _("GRBL resumed."))
        else:
            cmd = '!'
            self.send_grbl_command(command=cmd)
            self.app.inform.emit("%s" % _("GRBL paused."))

    def probing_gcode(self, storage):
        """
        :param storage:         either a dict of dicts (voronoi) or a list of tuples (bilinear)
        :return:                Probing GCode
        :rtype:                 str
        """

        target_obj = self.app.collection.get_by_name(self.ui.object_combo.get_value())

        p_gcode = ''
        header = ''
        time_str = "{:%A, %d %B %Y at %H:%M}".format(datetime.now())

        coords = []
        al_method = self.ui.al_method_radio.get_value()
        if al_method == 'v':
            for id_key, value in storage.items():
                x = value['point'].x
                y = value['point'].y
                coords.append(
                    (
                        self.app.dec_format(x, dec=self.app.decimals),
                        self.app.dec_format(y, dec=self.app.decimals)
                    )
                )
        else:
            for pt in storage:
                x = pt[0]
                y = pt[1]
                coords.append(
                    (
                        self.app.dec_format(x, dec=self.app.decimals),
                        self.app.dec_format(y, dec=self.app.decimals)
                    )
                )

        pr_travel = self.ui.ptravelz_entry.get_value()
        probe_fr = self.ui.feedrate_probe_entry.get_value()
        pr_depth = self.ui.pdepth_entry.get_value()
        controller = self.ui.al_controller_combo.get_value()

        header += '(G-CODE GENERATED BY FLATCAM v%s - www.flatcam.org - Version Date: %s)\n' % \
                  (str(self.app.version), str(self.app.version_date)) + '\n'

        header += '(This is a autolevelling probing GCode.)\n' \
                  '(Make sure that before you start the job you first do a zero for all axis.)\n\n'

        header += '(Name: ' + str(target_obj.options['name']) + ')\n'
        header += '(Type: ' + "Autolevelling Probing GCode " + ')\n'

        header += '(Units: ' + self.units.upper() + ')\n'
        header += '(Created on ' + time_str + ')\n'

        # commands
        if controller == 'MACH3':
            probing_command = 'G31'
            # probing_var = '#2002'
            openfile_command = 'M40'
            closefile_command = 'M41'
        elif controller == 'MACH4':
            probing_command = 'G31'
            # probing_var = '#5063'
            openfile_command = 'M40'
            closefile_command = 'M41'
        elif controller == 'LinuxCNC':
            probing_command = 'G38.2'
            # probing_var = '#5422'
            openfile_command = '(PROBEOPEN a_probing_points_file.txt)'
            closefile_command = '(PROBECLOSE)'
        elif controller == 'GRBL':
            # do nothing here because the Probing GCode for GRBL is obtained differently
            return
        else:
            self.app.log.debug("CNCJobObject.probing_gcode() -> controller not supported")
            return

        # #############################################################################################################
        # ########################### GCODE construction ##############################################################
        # #############################################################################################################

        # header
        p_gcode += header + '\n'
        # supplementary message for LinuxCNC
        if controller == 'LinuxCNC':
            p_gcode += "The file with the stored probing points can be found\n" \
                       "in the configuration folder for LinuxCNC.\n" \
                       "The name of the file is: a_probing_points_file.txt.\n"
        # units
        p_gcode += 'G21\n' if self.units == 'MM' else 'G20\n'
        # reference mode = absolute
        p_gcode += 'G90\n'
        # open a new file
        p_gcode += openfile_command + '\n'
        # move to safe height (probe travel Z)
        p_gcode += 'G0 Z%s\n' % str(self.app.dec_format(pr_travel, target_obj.coords_decimals))

        # probing points
        for idx, xy_tuple in enumerate(coords, 1):  # index starts from 1
            x = xy_tuple[0]
            y = xy_tuple[1]
            # move to probing point
            p_gcode += "G0 X%sY%s\n" % (
                str(self.app.dec_format(x, target_obj.coords_decimals)),
                str(self.app.dec_format(y, target_obj.coords_decimals))
            )
            # do the probing
            p_gcode += "%s Z%s F%s\n" % (
                probing_command,
                str(self.app.dec_format(pr_depth, target_obj.coords_decimals)),
                str(self.app.dec_format(probe_fr, target_obj.fr_decimals)),
            )
            # store in a global numeric variable the value of the detected probe Z
            # I offset the global numeric variable by 500 so it does not conflict with something else
            # temp_var = int(idx + 500)
            # p_gcode += "#%d = %s\n" % (temp_var, probing_var)

            # move to safe height (probe travel Z)
            p_gcode += 'G0 Z%s\n' % str(self.app.dec_format(pr_travel, target_obj.coords_decimals))

        # close the file
        p_gcode += closefile_command + '\n'
        # finish the GCode
        p_gcode += 'M2'

        return p_gcode

    def on_save_probing_gcode(self):
        lines = StringIO(self.probing_gcode_text)

        _filter_ = self.app.defaults['cncjob_save_filters']
        name = "probing_gcode"
        try:
            dir_file_to_save = self.app.get_last_save_folder() + '/' + str(name)
            filename, _f = FCFileSaveDialog.get_saved_filename(
                caption=_("Export Code ..."),
                directory=dir_file_to_save,
                ext_filter=_filter_
            )
        except TypeError:
            filename, _f = FCFileSaveDialog.get_saved_filename(
                caption=_("Export Code ..."),
                ext_filter=_filter_)

        if filename == '':
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("Export cancelled ..."))
            return
        else:
            try:
                force_windows_line_endings = self.app.defaults['cncjob_line_ending']
                if force_windows_line_endings and sys.platform != 'win32':
                    with open(filename, 'w', newline='\r\n') as f:
                        for line in lines:
                            f.write(line)
                else:
                    with open(filename, 'w') as f:
                        for line in lines:
                            f.write(line)
            except FileNotFoundError:
                self.app.inform.emit('[WARNING_NOTCL] %s' % _("No such file or directory"))
                return
            except PermissionError:
                self.app.inform.emit(
                    '[WARNING] %s' % _("Permission denied, saving not possible.\n"
                                       "Most likely another app is holding the file open and not accessible.")
                )
                return 'fail'

    def on_edit_probing_gcode(self):
        self.app.proc_container.view.set_busy('%s...' % _("Loading"))

        gco = self.probing_gcode_text
        if gco is None or gco == '':
            self.app.inform.emit('[WARNING_NOTCL] %s...' % _('There is nothing to view'))
            return

        self.gcode_viewer_tab = AppTextEditor(app=self.app, plain_text=True)

        # add the tab if it was closed
        self.app.ui.plot_tab_area.addTab(self.gcode_viewer_tab, '%s' % _("Code Viewer"))
        self.gcode_viewer_tab.setObjectName('code_viewer_tab')

        # delete the absolute and relative position and messages in the infobar
        self.app.ui.position_label.setText("")
        self.app.ui.rel_position_label.setText("")

        self.gcode_viewer_tab.code_editor.completer_enable = False
        self.gcode_viewer_tab.buttonRun.hide()

        # Switch plot_area to CNCJob tab
        self.app.ui.plot_tab_area.setCurrentWidget(self.gcode_viewer_tab)

        self.gcode_viewer_tab.t_frame.hide()
        # then append the text from GCode to the text editor
        try:
            self.gcode_viewer_tab.load_text(gco, move_to_start=True, clear_text=True)
        except Exception as e:
            self.app.log.error('FlatCAMCNCJob.on_edit_probing_gcode() -->%s' % str(e))
            return

        self.gcode_viewer_tab.t_frame.show()
        self.app.proc_container.view.set_idle()

        self.gcode_viewer_tab.buttonSave.hide()
        self.gcode_viewer_tab.buttonOpen.hide()
        self.gcode_viewer_tab.buttonPrint.hide()
        self.gcode_viewer_tab.buttonPreview.hide()
        self.gcode_viewer_tab.buttonReplace.hide()
        self.gcode_viewer_tab.sel_all_cb.hide()
        self.gcode_viewer_tab.entryReplace.hide()

        self.gcode_viewer_tab.button_update_code.show()

        # self.gcode_viewer_tab.code_editor.setReadOnly(True)

        self.gcode_viewer_tab.button_update_code.clicked.connect(self.on_update_probing_gcode)

        self.app.inform.emit('[success] %s...' % _('Loaded Machine Code into Code Viewer'))

    def on_update_probing_gcode(self):
        self.probing_gcode_text = self.gcode_viewer_tab.code_editor.toPlainText()

    def on_import_height_map(self):
        """
        Import the height map file into the app
        :return:
        :rtype:
        """

        _filter_ = "Text File .txt (*.txt);;All Files (*.*)"
        try:
            filename, _f = QtWidgets.QFileDialog.getOpenFileName(caption=_("Import Height Map"),
                                                                 directory=self.app.get_last_folder(),
                                                                 filter=_filter_)
        except TypeError:
            filename, _f = QtWidgets.QFileDialog.getOpenFileName(caption=_("Import Height Map"),
                                                                 filter=_filter_)

        filename = str(filename)

        if filename == '':
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("Cancelled."))
        else:
            self.app.worker_task.emit({'fcn': self.import_height_map, 'params': [filename]})

    def import_height_map(self, filename):
        """

        :param filename:
        :type filename:
        :return:
        :rtype:
        """

        try:
            if filename:
                with open(filename, 'r') as f:
                    stream = f.readlines()
            else:
                return
        except IOError:
            self.app.log.error("Failed to open height map file: %s" % filename)
            self.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Failed to open height map file"), filename))
            return

        idx = 0
        if stream is not None and stream != '':
            for line in stream:
                if line != '':
                    idx += 1
                    line = line.replace(' ', ',').replace('\n', '').split(',')
                    if idx not in self.al_voronoi_geo_storage:
                        self.al_voronoi_geo_storage[idx] = {}
                    self.al_voronoi_geo_storage[idx]['height'] = float(line[2])
                    if 'point' not in self.al_voronoi_geo_storage[idx]:
                        x = float(line[0])
                        y = float(line[1])
                        self.al_voronoi_geo_storage[idx]['point'] = Point((x, y))

            self.build_al_table_sig.emit()

    def on_grbl_autolevel(self):
        # show the Shell Dock
        self.app.ui.shell_dock.show()

        def worker_task():
            with self.app.proc_container.new('%s...' % _("Sending")):
                self.grbl_probe_result = ''
                pr_travelz = str(self.ui.ptravelz_entry.get_value())
                probe_fr = str(self.ui.feedrate_probe_entry.get_value())
                pr_depth = str(self.ui.pdepth_entry.get_value())

                cmd = 'G21\n'
                self.send_grbl_command(command=cmd)
                cmd = 'G90\n'
                self.send_grbl_command(command=cmd)

                for pt_key in self.al_voronoi_geo_storage:
                    x = str(self.al_voronoi_geo_storage[pt_key]['point'].x)
                    y = str(self.al_voronoi_geo_storage[pt_key]['point'].y)

                    cmd = 'G0 Z%s\n' % pr_travelz
                    self.send_grbl_command(command=cmd)
                    cmd = 'G0 X%s Y%s\n' % (x, y)
                    self.send_grbl_command(command=cmd)
                    cmd = 'G38.2 Z%s F%s' % (pr_depth, probe_fr)
                    output = self.send_grbl_command(command=cmd)

                    self.grbl_probe_result += output + '\n'

                cmd = 'M2\n'
                self.send_grbl_command(command=cmd)
                self.app.inform.emit('%s' % _("Finished probing. Doing the autolevelling."))

                # apply autolevel here
                self.on_grbl_apply_autolevel()

        self.app.inform.emit('%s' % _("Sending probing GCode to the GRBL controller."))
        self.app.worker_task.emit({'fcn': worker_task, 'params': []})

    def on_grbl_heightmap_save(self):
        if self.grbl_probe_result != '':
            _filter_ = "Text File .txt (*.txt);;All Files (*.*)"
            name = "probing_gcode"
            try:
                dir_file_to_save = self.app.get_last_save_folder() + '/' + str(name)
                filename, _f = FCFileSaveDialog.get_saved_filename(
                    caption=_("Export Code ..."),
                    directory=dir_file_to_save,
                    ext_filter=_filter_
                )
            except TypeError:
                filename, _f = FCFileSaveDialog.get_saved_filename(
                    caption=_("Export Code ..."),
                    ext_filter=_filter_)

            if filename == '':
                self.app.inform.emit('[WARNING_NOTCL] %s' % _("Export cancelled ..."))
                return
            else:
                try:
                    force_windows_line_endings = self.app.defaults['cncjob_line_ending']
                    if force_windows_line_endings and sys.platform != 'win32':
                        with open(filename, 'w', newline='\r\n') as f:
                            for line in self.grbl_probe_result:
                                f.write(line)
                    else:
                        with open(filename, 'w') as f:
                            for line in self.grbl_probe_result:
                                f.write(line)
                except FileNotFoundError:
                    self.app.inform.emit('[WARNING_NOTCL] %s' % _("No such file or directory"))
                    return
                except PermissionError:
                    self.app.inform.emit(
                        '[WARNING] %s' % _("Permission denied, saving not possible.\n"
                                           "Most likely another app is holding the file open and not accessible.")
                    )
                    return 'fail'
        else:
            self.app.inform.emit('[ERROR_NOTCL] %s' % _("Empty GRBL heightmap."))

    def on_grbl_apply_autolevel(self):
        # TODO here we call the autolevell method
        self.app.inform.emit('%s' % _("Finished autolevelling."))

    def ui_connect(self):
        self.ui.al_add_button.clicked.connect(self.on_add_al_probepoints)
        self.ui.show_al_table.stateChanged.connect(self.on_show_al_table)

    def ui_disconnect(self):
        try:
            self.ui.al_add_button.clicked.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.show_al_table.stateChanged.disconnect()
        except (TypeError, AttributeError):
            pass

    def reset_fields(self):
        self.object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))


class LevelUI:
    toolName = _("Levelling Tool")

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

        # ## Title
        title_label = FCLabel("%s" % self.toolName)
        title_label.setStyleSheet("""
                                QLabel
                                {
                                    font-size: 16px;
                                    font-weight: bold;
                                }
                                """)
        title_label.setToolTip(
            _("Generate CNC Code with auto-levelled paths.")
        )

        self.title_box.addWidget(title_label)

        # App Level label
        self.level = QtWidgets.QToolButton()
        self.level.setToolTip(
            _(
                "BASIC is suitable for a beginner. Many parameters\n"
                "are hidden from the user in this mode.\n"
                "ADVANCED mode will make available all parameters.\n\n"
                "To change the application LEVEL, go to:\n"
                "Edit -> Preferences -> General and check:\n"
                "'APP. LEVEL' radio button."
            )
        )
        # self.level.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.level.setCheckable(True)
        self.title_box.addWidget(self.level)

        self.obj_combo_label = FCLabel('<b>%s</b>:' % _("CNCjob"))
        self.obj_combo_label.setToolTip(
            _("Source object.")
        )

        self.tools_box.addWidget(self.obj_combo_label)

        # #############################################################################################################
        # ################################ The object to be Autolevelled ##############################################
        # #############################################################################################################
        self.object_combo = FCComboBox()
        self.object_combo.setModel(self.app.collection)
        self.object_combo.setRootModelIndex(self.app.collection.index(3, 0, QtCore.QModelIndex()))
        # self.object_combo.setCurrentIndex(1)
        self.object_combo.is_last = True

        self.tools_box.addWidget(self.object_combo)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.tools_box.addWidget(separator_line)

        # Autolevelling
        self.al_frame = QtWidgets.QFrame()
        self.al_frame.setContentsMargins(0, 0, 0, 0)
        self.tools_box.addWidget(self.al_frame)

        self.al_box = QtWidgets.QVBoxLayout()
        self.al_box.setContentsMargins(0, 0, 0, 0)
        self.al_frame.setLayout(self.al_box)

        grid0 = QtWidgets.QGridLayout()
        grid0.setColumnStretch(0, 0)
        grid0.setColumnStretch(1, 1)
        self.al_box.addLayout(grid0)

        self.al_title = FCLabel('<b>%s</b>' % _("Probe Points Table"))
        self.al_title.setToolTip(_("Generate GCode that will obtain the height map"))

        self.show_al_table = FCCheckBox(_("Show"))
        self.show_al_table.setToolTip(_("Toggle the display of the Probe Points table."))
        self.show_al_table.setChecked(True)

        hor_lay = QtWidgets.QHBoxLayout()
        hor_lay.addWidget(self.al_title)
        hor_lay.addStretch()
        hor_lay.addWidget(self.show_al_table, alignment=QtCore.Qt.AlignRight)

        grid0.addLayout(hor_lay, 0, 0, 1, 2)

        self.al_probe_points_table = FCTable()
        self.al_probe_points_table.setColumnCount(3)
        self.al_probe_points_table.setColumnWidth(0, 20)
        self.al_probe_points_table.setHorizontalHeaderLabels(['#', _('X-Y Coordinates'), _('Height')])

        grid0.addWidget(self.al_probe_points_table, 1, 0, 1, 2)

        self.plot_probing_pts_cb = FCCheckBox(_("Plot probing points"))
        self.plot_probing_pts_cb.setToolTip(
            _("Plot the probing points in the table.\n"
              "If a Voronoi method is used then\n"
              "the Voronoi areas are also plotted.")
        )
        grid0.addWidget(self.plot_probing_pts_cb, 3, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        grid0.addWidget(separator_line, 5, 0, 1, 2)

        # #############################################################################################################
        # ############### Probe GCode Generation ######################################################################
        # #############################################################################################################

        self.probe_gc_label = FCLabel('<b>%s</b>:' % _("Parameters"))
        self.probe_gc_label.setToolTip(
            _("Will create a GCode which will be sent to the controller,\n"
              "either through a file or directly, with the intent to get the height map\n"
              "that is to modify the original GCode to level the cutting height.")
        )
        grid0.addWidget(self.probe_gc_label, 7, 0, 1, 2)

        # Travel Z Probe
        self.ptravelz_label = FCLabel('%s:' % _("Probe Z travel"))
        self.ptravelz_label.setToolTip(
            _("The safe Z for probe travelling between probe points.")
        )
        self.ptravelz_entry = FCDoubleSpinner()
        self.ptravelz_entry.set_precision(self.decimals)
        self.ptravelz_entry.set_range(0.0000, 10000.0000)

        grid0.addWidget(self.ptravelz_label, 9, 0)
        grid0.addWidget(self.ptravelz_entry, 9, 1)

        # Probe depth
        self.pdepth_label = FCLabel('%s:' % _("Probe Z depth"))
        self.pdepth_label.setToolTip(
            _("The maximum depth that the probe is allowed\n"
              "to probe. Negative value, in current units.")
        )
        self.pdepth_entry = FCDoubleSpinner()
        self.pdepth_entry.set_precision(self.decimals)
        self.pdepth_entry.set_range(-910000.0000, 0.0000)

        grid0.addWidget(self.pdepth_label, 11, 0)
        grid0.addWidget(self.pdepth_entry, 11, 1)

        # Probe feedrate
        self.feedrate_probe_label = FCLabel('%s:' % _("Probe Feedrate"))
        self.feedrate_probe_label.setToolTip(
           _("The feedrate used while the probe is probing.")
        )
        self.feedrate_probe_entry = FCDoubleSpinner()
        self.feedrate_probe_entry.set_precision(self.decimals)
        self.feedrate_probe_entry.set_range(0, 910000.0000)

        grid0.addWidget(self.feedrate_probe_label, 13, 0)
        grid0.addWidget(self.feedrate_probe_entry, 13, 1)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        grid0.addWidget(separator_line, 15, 0, 1, 2)

        # AUTOLEVELL MODE
        al_mode_lbl = FCLabel('<b>%s</b>:' % _("Mode"))
        al_mode_lbl.setToolTip(_("Choose a mode for height map generation.\n"
                                 "- Manual: will pick a selection of probe points by clicking on canvas\n"
                                 "- Grid: will automatically generate a grid of probe points"))

        self.al_mode_radio = RadioSet(
            [
                {'label': _('Manual'), 'value': 'manual'},
                {'label': _('Grid'), 'value': 'grid'}
            ])
        grid0.addWidget(al_mode_lbl, 16, 0)
        grid0.addWidget(self.al_mode_radio, 16, 1)

        # AUTOLEVELL METHOD
        self.al_method_lbl = FCLabel('%s:' % _("Method"))
        self.al_method_lbl.setToolTip(_("Choose a method for approximation of heights from autolevelling data.\n"
                                        "- Voronoi: will generate a Voronoi diagram\n"
                                        "- Bilinear: will use bilinear interpolation. Usable only for grid mode."))

        self.al_method_radio = RadioSet(
            [
                {'label': _('Voronoi'), 'value': 'v'},
                {'label': _('Bilinear'), 'value': 'b'}
            ])
        self.al_method_lbl.setDisabled(True)
        self.al_method_radio.setDisabled(True)
        self.al_method_radio.set_value('v')

        grid0.addWidget(self.al_method_lbl, 17, 0)
        grid0.addWidget(self.al_method_radio, 17, 1)

        # ## Columns
        self.al_columns_entry = FCSpinner()
        self.al_columns_entry.setMinimum(2)

        self.al_columns_label = FCLabel('%s:' % _("Columns"))
        self.al_columns_label.setToolTip(
            _("The number of grid columns.")
        )
        grid0.addWidget(self.al_columns_label, 19, 0)
        grid0.addWidget(self.al_columns_entry, 19, 1)

        # ## Rows
        self.al_rows_entry = FCSpinner()
        self.al_rows_entry.setMinimum(2)

        self.al_rows_label = FCLabel('%s:' % _("Rows"))
        self.al_rows_label.setToolTip(
            _("The number of grid rows.")
        )
        grid0.addWidget(self.al_rows_label, 21, 0)
        grid0.addWidget(self.al_rows_entry, 21, 1)

        self.al_add_button = FCButton(_("Add Probe Points"))
        grid0.addWidget(self.al_add_button, 23, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        grid0.addWidget(separator_line, 25, 0, 1, 2)

        self.al_controller_label = FCLabel('<b>%s</b>:' % _("Controller"))
        self.al_controller_label.setToolTip(
            _("The kind of controller for which to generate\n"
              "height map gcode.")
        )

        self.al_controller_combo = FCComboBox()
        self.al_controller_combo.addItems(["MACH3", "MACH4", "LinuxCNC", "GRBL"])
        grid0.addWidget(self.al_controller_label, 27, 0)
        grid0.addWidget(self.al_controller_combo, 27, 1)

        # #############################################################################################################
        # ########################## GRBL frame #######################################################################
        # #############################################################################################################
        self.grbl_frame = QtWidgets.QFrame()
        self.grbl_frame.setContentsMargins(0, 0, 0, 0)
        grid0.addWidget(self.grbl_frame, 29, 0, 1, 2)

        self.grbl_box = QtWidgets.QVBoxLayout()
        self.grbl_box.setContentsMargins(0, 0, 0, 0)
        self.grbl_frame.setLayout(self.grbl_box)

        # #############################################################################################################
        # ########################## GRBL TOOLBAR #####################################################################
        # #############################################################################################################
        self.al_toolbar = FCDetachableTab(protect=True)
        self.al_toolbar.setTabsClosable(False)
        self.al_toolbar.useOldIndex(True)
        self.al_toolbar.set_detachable(val=False)
        self.grbl_box.addWidget(self.al_toolbar)

        # GRBL Connect TAB
        self.gr_conn_tab = QtWidgets.QWidget()
        self.gr_conn_tab.setObjectName("connect_tab")
        self.gr_conn_tab_layout = QtWidgets.QVBoxLayout(self.gr_conn_tab)
        self.gr_conn_tab_layout.setContentsMargins(2, 2, 2, 2)
        # self.gr_conn_scroll_area = VerticalScrollArea()
        # self.gr_conn_tab_layout.addWidget(self.gr_conn_scroll_area)
        self.al_toolbar.addTab(self.gr_conn_tab, _("Connect"))

        # GRBL Control TAB
        self.gr_ctrl_tab = QtWidgets.QWidget()
        self.gr_ctrl_tab.setObjectName("connect_tab")
        self.gr_ctrl_tab_layout = QtWidgets.QVBoxLayout(self.gr_ctrl_tab)
        self.gr_ctrl_tab_layout.setContentsMargins(2, 2, 2, 2)

        # self.gr_ctrl_scroll_area = VerticalScrollArea()
        # self.gr_ctrl_tab_layout.addWidget(self.gr_ctrl_scroll_area)
        self.al_toolbar.addTab(self.gr_ctrl_tab, _("Control"))

        # GRBL Sender TAB
        self.gr_send_tab = QtWidgets.QWidget()
        self.gr_send_tab.setObjectName("connect_tab")
        self.gr_send_tab_layout = QtWidgets.QVBoxLayout(self.gr_send_tab)
        self.gr_send_tab_layout.setContentsMargins(2, 2, 2, 2)

        # self.gr_send_scroll_area = VerticalScrollArea()
        # self.gr_send_tab_layout.addWidget(self.gr_send_scroll_area)
        self.al_toolbar.addTab(self.gr_send_tab, _("Sender"))

        for idx in range(self.al_toolbar.count()):
            if self.al_toolbar.tabText(idx) == _("Connect"):
                self.al_toolbar.tabBar.setTabTextColor(idx, QtGui.QColor('red'))
            if self.al_toolbar.tabText(idx) == _("Control"):
                self.al_toolbar.tabBar.setTabEnabled(idx, False)
            if self.al_toolbar.tabText(idx) == _("Sender"):
                self.al_toolbar.tabBar.setTabEnabled(idx, False)
        # #############################################################################################################

        # #############################################################################################################
        # GRBL CONNECT
        # #############################################################################################################
        grbl_conn_grid = QtWidgets.QGridLayout()
        grbl_conn_grid.setColumnStretch(0, 0)
        grbl_conn_grid.setColumnStretch(1, 1)
        grbl_conn_grid.setColumnStretch(2, 0)
        self.gr_conn_tab_layout.addLayout(grbl_conn_grid)

        # COM list
        self.com_list_label = FCLabel('%s:' % _("COM list"))
        self.com_list_label.setToolTip(
            _("Lists the available serial ports.")
        )

        self.com_list_combo = FCComboBox()
        self.com_search_button = FCButton(_("Search"))
        self.com_search_button.setToolTip(
            _("Search for the available serial ports.")
        )
        grbl_conn_grid.addWidget(self.com_list_label, 2, 0)
        grbl_conn_grid.addWidget(self.com_list_combo, 2, 1)
        grbl_conn_grid.addWidget(self.com_search_button, 2, 2)

        # BAUDRATES list
        self.baudrates_list_label = FCLabel('%s:' % _("Baud rates"))
        self.baudrates_list_label.setToolTip(
            _("Lists the available serial ports.")
        )

        self.baudrates_list_combo = FCComboBox()
        cbmodel = QtCore.QStringListModel()
        self.baudrates_list_combo.setModel(cbmodel)
        self.baudrates_list_combo.addItems(
            ['9600', '19200', '38400', '57600', '115200', '230400', '460800', '500000', '576000', '921600', '1000000',
             '1152000', '1500000', '2000000'])
        self.baudrates_list_combo.setCurrentText('115200')

        grbl_conn_grid.addWidget(self.baudrates_list_label, 4, 0)
        grbl_conn_grid.addWidget(self.baudrates_list_combo, 4, 1)

        # New baudrate
        self.new_bd_label = FCLabel('%s:' % _("New"))
        self.new_bd_label.setToolTip(
            _("New, custom baudrate.")
        )

        self.new_baudrate_entry = FCSpinner()
        self.new_baudrate_entry.set_range(40, 9999999)

        self.add_bd_button = FCButton(_("Add"))
        self.add_bd_button.setToolTip(
            _("Add the specified custom baudrate to the list.")
        )
        grbl_conn_grid.addWidget(self.new_bd_label, 6, 0)
        grbl_conn_grid.addWidget(self.new_baudrate_entry, 6, 1)
        grbl_conn_grid.addWidget(self.add_bd_button, 6, 2)

        self.del_bd_button = FCButton(_("Delete selected baudrate"))
        grbl_conn_grid.addWidget(self.del_bd_button, 8, 0, 1, 3)

        ctrl_hlay = QtWidgets.QHBoxLayout()
        self.controller_reset_button = FCButton(_("Reset"))
        self.controller_reset_button.setToolTip(
            _("Software reset of the controller.")
        )
        self.controller_reset_button.setDisabled(True)
        ctrl_hlay.addWidget(self.controller_reset_button)

        self.com_connect_button = FCButton()
        self.com_connect_button.setText(_("Disconnected"))
        self.com_connect_button.setToolTip(
            _("Connect to the selected port with the selected baud rate.")
        )
        self.com_connect_button.setStyleSheet("QPushButton {background-color: red;}")
        ctrl_hlay.addWidget(self.com_connect_button)

        grbl_conn_grid.addWidget(FCLabel(""), 9, 0, 1, 3)
        grbl_conn_grid.setRowStretch(9, 1)
        grbl_conn_grid.addLayout(ctrl_hlay, 10, 0, 1, 3)

        # #############################################################################################################
        # GRBL CONTROL
        # #############################################################################################################
        grbl_ctrl_grid = QtWidgets.QGridLayout()
        grbl_ctrl_grid.setColumnStretch(0, 0)
        grbl_ctrl_grid.setColumnStretch(1, 1)
        grbl_ctrl_grid.setColumnStretch(2, 0)
        self.gr_ctrl_tab_layout.addLayout(grbl_ctrl_grid)

        grbl_ctrl2_grid = QtWidgets.QGridLayout()
        grbl_ctrl2_grid.setColumnStretch(0, 0)
        grbl_ctrl2_grid.setColumnStretch(1, 1)
        self.gr_ctrl_tab_layout.addLayout(grbl_ctrl2_grid)

        self.gr_ctrl_tab_layout.addStretch(1)

        jog_title_label = FCLabel(_("Jog"))
        jog_title_label.setStyleSheet("""
                                FCLabel
                                {
                                    font-weight: bold;
                                }
                                """)

        zero_title_label = FCLabel(_("Zero Axes"))
        zero_title_label.setStyleSheet("""
                                FCLabel
                                {
                                    font-weight: bold;
                                }
                                """)

        grbl_ctrl_grid.addWidget(jog_title_label, 0, 0)
        grbl_ctrl_grid.addWidget(zero_title_label, 0, 2)

        self.jog_wdg = FCJog(self.app)
        self.jog_wdg.setStyleSheet("""
                            FCJog
                            {
                                border: 1px solid lightgray;
                                border-radius: 5px;
                            }
                            """)

        self.zero_axs_wdg = FCZeroAxes(self.app)
        self.zero_axs_wdg.setStyleSheet("""
                            FCZeroAxes
                            {
                                border: 1px solid lightgray;
                                border-radius: 5px
                            }
                            """)
        grbl_ctrl_grid.addWidget(self.jog_wdg, 2, 0)
        grbl_ctrl_grid.addWidget(self.zero_axs_wdg, 2, 2)

        self.pause_resume_button = RotatedToolButton()
        self.pause_resume_button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.pause_resume_button.setText(_("Pause/Resume"))
        self.pause_resume_button.setCheckable(True)
        self.pause_resume_button.setStyleSheet("""
                            RotatedToolButton:checked
                            {
                                background-color: red;
                                color: white;
                                border: none;
                            }
                            """)

        pause_frame = QtWidgets.QFrame()
        pause_frame.setContentsMargins(0, 0, 0, 0)
        pause_frame.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        pause_hlay = QtWidgets.QHBoxLayout()
        pause_hlay.setContentsMargins(0, 0, 0, 0)

        pause_hlay.addWidget(self.pause_resume_button)
        pause_frame.setLayout(pause_hlay)
        grbl_ctrl_grid.addWidget(pause_frame, 2, 1)

        # JOG Step
        self.jog_step_label = FCLabel('%s:' % _("Step"))
        self.jog_step_label.setToolTip(
            _("Each jog action will move the axes with this value.")
        )

        self.jog_step_entry = FCSliderWithDoubleSpinner()
        self.jog_step_entry.set_precision(self.decimals)
        self.jog_step_entry.setSingleStep(0.1)
        self.jog_step_entry.set_range(0, 500)

        grbl_ctrl2_grid.addWidget(self.jog_step_label, 0, 0)
        grbl_ctrl2_grid.addWidget(self.jog_step_entry, 0, 1)

        # JOG Feedrate
        self.jog_fr_label = FCLabel('%s:' % _("Feedrate"))
        self.jog_fr_label.setToolTip(
            _("Feedrate when jogging.")
        )

        self.jog_fr_entry = FCSliderWithDoubleSpinner()
        self.jog_fr_entry.set_precision(self.decimals)
        self.jog_fr_entry.setSingleStep(10)
        self.jog_fr_entry.set_range(0, 10000)

        grbl_ctrl2_grid.addWidget(self.jog_fr_label, 1, 0)
        grbl_ctrl2_grid.addWidget(self.jog_fr_entry, 1, 1)

        # #############################################################################################################
        # GRBL SENDER
        # #############################################################################################################
        grbl_send_grid = QtWidgets.QGridLayout()
        grbl_send_grid.setColumnStretch(0, 1)
        grbl_send_grid.setColumnStretch(1, 0)
        self.gr_send_tab_layout.addLayout(grbl_send_grid)

        # Send CUSTOM COMMAND
        self.grbl_command_label = FCLabel('%s:' % _("Send Command"))
        self.grbl_command_label.setToolTip(
            _("Send a custom command to GRBL.")
        )
        grbl_send_grid.addWidget(self.grbl_command_label, 2, 0, 1, 2)

        self.grbl_command_entry = FCEntry()
        self.grbl_command_entry.setPlaceholderText(_("Type GRBL command ..."))

        self.grbl_send_button = QtWidgets.QToolButton()
        self.grbl_send_button.setText(_("Send"))
        self.grbl_send_button.setToolTip(
            _("Send a custom command to GRBL.")
        )
        grbl_send_grid.addWidget(self.grbl_command_entry, 4, 0)
        grbl_send_grid.addWidget(self.grbl_send_button, 4, 1)

        # Get Parameter
        self.grbl_get_param_label = FCLabel('%s:' % _("Get Config parameter"))
        self.grbl_get_param_label.setToolTip(
            _("A GRBL configuration parameter.")
        )
        grbl_send_grid.addWidget(self.grbl_get_param_label, 6, 0, 1, 2)

        self.grbl_parameter_entry = FCEntry()
        self.grbl_parameter_entry.setPlaceholderText(_("Type GRBL parameter ..."))

        self.grbl_get_param_button = QtWidgets.QToolButton()
        self.grbl_get_param_button.setText(_("Get"))
        self.grbl_get_param_button.setToolTip(
            _("Get the value of a specified GRBL parameter.")
        )
        grbl_send_grid.addWidget(self.grbl_parameter_entry, 8, 0)
        grbl_send_grid.addWidget(self.grbl_get_param_button, 8, 1)

        grbl_send_grid.setRowStretch(9, 1)

        # GET Report
        self.grbl_report_button = FCButton(_("Get Report"))
        self.grbl_report_button.setToolTip(
            _("Print in shell the GRBL report.")
        )
        grbl_send_grid.addWidget(self.grbl_report_button, 10, 0, 1, 2)

        hm_lay = QtWidgets.QHBoxLayout()
        # GET HEIGHT MAP
        self.grbl_get_heightmap_button = FCButton(_("Apply AutoLevelling"))
        self.grbl_get_heightmap_button.setToolTip(
            _("Will send the probing GCode to the GRBL controller,\n"
              "wait for the Z probing data and then apply this data\n"
              "over the original GCode therefore doing autolevelling.")
        )
        hm_lay.addWidget(self.grbl_get_heightmap_button, stretch=1)

        self.grbl_save_height_map_button = QtWidgets.QToolButton()
        self.grbl_save_height_map_button.setIcon(QtGui.QIcon(self.app.resource_location + '/save_as.png'))
        self.grbl_save_height_map_button.setToolTip(
            _("Will save the GRBL height map.")
        )
        hm_lay.addWidget(self.grbl_save_height_map_button, stretch=0, alignment=Qt.AlignRight)

        grbl_send_grid.addLayout(hm_lay, 12, 0, 1, 2)

        self.grbl_frame.hide()
        # #############################################################################################################

        height_lay = QtWidgets.QHBoxLayout()
        self.h_gcode_button = FCButton(_("Save Probing GCode"))
        self.h_gcode_button.setToolTip(
            _("Will save the probing GCode.")
        )
        self.h_gcode_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)

        height_lay.addWidget(self.h_gcode_button)
        self.view_h_gcode_button = QtWidgets.QToolButton()
        self.view_h_gcode_button.setIcon(QtGui.QIcon(self.app.resource_location + '/edit_file32.png'))
        # self.view_h_gcode_button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.view_h_gcode_button.setToolTip(
            _("View/Edit the probing GCode.")
        )
        # height_lay.addStretch()
        height_lay.addWidget(self.view_h_gcode_button)

        grid0.addLayout(height_lay, 31, 0, 1, 2)

        self.import_heights_button = FCButton(_("Import Height Map"))
        self.import_heights_button.setToolTip(
            _("Import the file that has the Z heights\n"
              "obtained through probing and then apply this data\n"
              "over the original GCode therefore\n"
              "doing autolevelling.")
        )
        grid0.addWidget(self.import_heights_button, 33, 0, 1, 2)

        self.h_gcode_button.hide()
        self.import_heights_button.hide()

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        grid0.addWidget(separator_line, 35, 0, 1, 2)

        self.tools_box.addStretch(1)

        # ## Reset Tool
        self.reset_button = FCButton(_("Reset Tool"))
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
        self.tools_box.addWidget(self.reset_button)
        # ############################ FINISHED GUI ###################################
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