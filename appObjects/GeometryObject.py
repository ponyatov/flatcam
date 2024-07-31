# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
# ##########################################################

# ##########################################################
# File modified by: Marius Stanciu                         #
# ##########################################################

from PyQt6 import QtWidgets, QtCore
from appObjects.AppObjectTemplate import FlatCAMObj, ObjectDeleted
from appGUI.GUIElements import FCCheckBox
from appGUI.ObjectUI import GeometryObjectUI

from shapely import MultiLineString, LinearRing, Polygon, MultiPolygon, LineString
from shapely.affinity import scale, translate
from shapely.ops import unary_union

from camlib import Geometry, flatten_shapely_geometry

import re
import ezdxf
import numpy as np
import traceback
from copy import deepcopy
from collections import defaultdict
from functools import reduce

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class GeometryObject(FlatCAMObj, Geometry):
    """
    Geometric object not associated with a specific
    format.
    """
    optionChanged = QtCore.pyqtSignal(str)
    builduiSig = QtCore.pyqtSignal()
    launch_job = QtCore.pyqtSignal()

    ui_type = GeometryObjectUI

    def __init__(self, name):
        self.decimals = self.app.decimals

        self.circle_steps = int(self.app.options["geometry_circle_steps"])

        FlatCAMObj.__init__(self, name)
        Geometry.__init__(self, geo_steps_per_circle=self.circle_steps)

        self.kind = "geometry"

        self.obj_options.update({
            "plot": True,
            "multicolored": False,

            "tools_mill_cutz": -0.002,
            "tools_mill_vtipdia": 0.1,
            "tools_mill_vtipangle": 30,
            "tools_mill_travelz": 0.1,
            "tools_mill_feedrate": 5.0,
            "tools_mill_feedrate_z": 5.0,
            "tools_mill_feedrate_rapid": 5.0,
            "tools_mill_spindlespeed": 0,
            "tools_mill_dwell": True,
            "tools_mill_dwelltime": 1000,
            "tools_mill_multidepth": False,
            "tools_mill_depthperpass": 0.002,
            "tools_mill_extracut": False,
            "tools_mill_extracut_length": 0.1,
            "tools_mill_endz": 2.0,
            "tools_mill_endxy": '',
            "tools_mill_area_exclusion": False,
            "tools_mill_area_shape": "polygon",
            "tools_mill_area_strategy": "over",
            "tools_mill_area_overz": 1.0,

            "tools_mill_startz": None,
            "tools_mill_toolchange": False,
            "tools_mill_toolchangez": 1.0,
            "tools_mill_toolchangexy": "0.0, 0.0",
            "tools_mill_ppname_g": 'default',
            "tools_mill_z_p_depth": -0.02,
            "tools_mill_feedrate_probe": 3.0,
        })

        if "tools_mill_tooldia" not in self.obj_options:
            if isinstance(self.app.options["tools_mill_tooldia"], float):
                self.obj_options["tools_mill_tooldia"] = self.app.options["tools_mill_tooldia"]
            else:
                try:
                    tools_string = self.app.options["tools_mill_tooldia"].split(",")
                    tools_diameters = [eval(a) for a in tools_string if a != '']
                    self.obj_options["tools_mill_tooldia"] = tools_diameters[0] if tools_diameters else 0.0
                except Exception as e:
                    self.app.log.error("FlatCAMObj.GeometryObject.init() --> %s" % str(e))

        self.obj_options["tools_mill_startz"] = self.app.options["tools_mill_startz"]

        # this will hold the tool unique ID that is useful when having multiple tools with same diameter
        self.tooluid = 0

        '''
            self.tools = {}
            This is a dictionary. Each dict key is associated with a tool used in geo_tools_table. The key is the 
            tool_id of the tools and the value is another dict that will hold the data under the following form:
                {tooluid:   {
                            'tooldia': 1,
                            'data': self.default_tool_data,
                            'solid_geometry': []
                            }
                }
        '''
        self.tools = {}

        # this dict is to store those elements (tools) of self.tools that are selected in the self.geo_tools_table
        # those elements are the ones used for generating GCode
        self.sel_tools = {}

        self.offset_item_options = ["Path", "In", "Out", "Custom"]
        self.job_item_options = [_('Roughing'), _('Finishing'), _('Isolation'), _('Polishing')]
        self.tool_type_item_options = ["C1", "C2", "C3", "C4", "B", "V", "L"]

        # flag to store if the V-Shape tool is selected in self.ui.geo_tools_table
        self.v_tool_type = None

        # flag to store if the Geometry is type 'multi-geometry' meaning that each tool has its own geometry
        # the default value is False
        self.multigeo = False

        # flag to store if the geometry is part of a special group of geometries that can't be processed by the default
        # engine of FlatCAM. Most likely are generated by some tools and are special cases of geometries.
        self.special_group = None

        # self.old_pp_state = self.app.options["tools_mill_multidepth"]
        # self.old_toolchangeg_state = self.app.options["tools_mill_toolchange"]
        self.units_found = self.app.app_units

        # this variable can be updated by the Object that generates the geometry
        self.tool_type = 'C1'

        # save here the old value for the Cut Z before it is changed by selecting a V-shape type tool in the tool table
        self.old_cutz = self.app.options["tools_mill_cutz"]

        self.fill_color = self.app.options['geometry_plot_line']
        self.outline_color = self.app.options['geometry_plot_line']
        self.alpha_level = 'FF'

        self.param_fields = {}

        # store here the state of the exclusion checkbox state to be restored after building the UI
        self.exclusion_area_cb_is_checked = self.app.options["tools_mill_area_exclusion"]

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from predecessors.
        self.ser_attrs += ['obj_options', 'kind', 'multigeo', 'fill_color', 'outline_color', 'alpha_level']

    def build_ui(self):
        try:
            self.ui_disconnect()
        except RuntimeError:
            return

        FlatCAMObj.build_ui(self)

        self.units = self.app.app_units

        row_idx = 0

        n = len(self.tools)
        self.ui.geo_tools_table.setRowCount(n)

        for tooluid_key, tooluid_value in self.tools.items():

            # -------------------- ID ------------------------------------------ #
            tool_id = QtWidgets.QTableWidgetItem('%d' % int(row_idx + 1))
            tool_id.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 0, tool_id)  # Tool name/id

            # Make sure that the tool diameter when in MM is with no more than 2 decimals.
            # There are no tool bits in MM with more than 3 decimals diameter.
            # For INCH the decimals should be no more than 3. There are no tools under 10mils.

            # -------------------- DIAMETER ------------------------------------- #
            dia_item = QtWidgets.QTableWidgetItem('%.*f' % (self.decimals, float(tooluid_value['tooldia'])))
            dia_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 1, dia_item)  # Diameter

            # -------------------- OFFSET   ------------------------------------- #
            try:
                offset_item_txt = self.offset_item_options[tooluid_value['data']['tools_mill_offset_type']]
            except TypeError:
                offset_item_txt = tooluid_value['data']['tools_mill_offset_type']
            except KeyError:
                # for older loaded projects
                offset_item_txt = self.app.options['tools_mill_offset_type']
            offset_item = QtWidgets.QTableWidgetItem(offset_item_txt)
            offset_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 2, offset_item)  # Offset Type

            # -------------------- JOB     ------------------------------------- #
            try:
                job_item_txt = self.job_item_options[tooluid_value['data']['tools_mill_job_type']]
            except TypeError:
                job_item_txt = tooluid_value['data']['tools_mill_job_type']
            except KeyError:
                # for older loaded projects
                job_item_txt = self.app.options['tools_mill_job_type']
            job_item = QtWidgets.QTableWidgetItem(job_item_txt)
            job_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 3, job_item)  # Job Type

            # -------------------- TOOL SHAPE ------------------------------------- #
            try:
                tool_shape_item_txt = self.tool_type_item_options[tooluid_value['data']['tools_mill_tool_shape']]
            except TypeError:
                tool_shape_item_txt = tooluid_value['data']['tools_mill_tool_shape']
            except KeyError:
                # for older loaded projects
                tool_shape_item_txt = self.app.options['tools_mill_tool_shape']
            tool_shape_item = QtWidgets.QTableWidgetItem(tool_shape_item_txt)
            tool_shape_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 4, tool_shape_item)  # Tool Shape

            # -------------------- TOOL UID   ------------------------------------- #
            tool_uid_item = QtWidgets.QTableWidgetItem(str(tooluid_key))
            # ## REMEMBER: THIS COLUMN IS HIDDEN IN OBJECTUI.PY ###
            self.ui.geo_tools_table.setItem(row_idx, 5, tool_uid_item)  # Tool unique ID

            # -------------------- PLOT       ------------------------------------- #
            empty_plot_item = QtWidgets.QTableWidgetItem('')
            empty_plot_item.setFlags(~QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.geo_tools_table.setItem(row_idx, 6, empty_plot_item)
            plot_item = FCCheckBox()
            plot_item.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
            if self.ui.plot_cb.isChecked():
                plot_item.setChecked(True)
            self.ui.geo_tools_table.setCellWidget(row_idx, 6, plot_item)

            row_idx += 1

        for row in range(row_idx):
            self.ui.geo_tools_table.item(row, 0).setFlags(
                self.ui.geo_tools_table.item(row, 0).flags() ^ QtCore.Qt.ItemFlag.ItemIsSelectable)

        self.ui.geo_tools_table.resizeColumnsToContents()
        self.ui.geo_tools_table.resizeRowsToContents()

        vertical_header = self.ui.geo_tools_table.verticalHeader()
        # vertical_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        vertical_header.hide()
        self.ui.geo_tools_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        horizontal_header = self.ui.geo_tools_table.horizontalHeader()
        horizontal_header.setMinimumSectionSize(10)
        horizontal_header.setDefaultSectionSize(70)
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        horizontal_header.resizeSection(0, 20)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Fixed)
        horizontal_header.resizeSection(4, 40)
        horizontal_header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Fixed)
        horizontal_header.resizeSection(6, 17)
        # horizontal_header.setStretchLastSection(True)
        self.ui.geo_tools_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.ui.geo_tools_table.setColumnWidth(0, 20)
        self.ui.geo_tools_table.setColumnWidth(4, 40)
        self.ui.geo_tools_table.setColumnWidth(6, 17)

        # self.ui.geo_tools_table.setSortingEnabled(True)

        self.ui.geo_tools_table.setMinimumHeight(self.ui.geo_tools_table.getHeight())
        self.ui.geo_tools_table.setMaximumHeight(self.ui.geo_tools_table.getHeight())

        # select only the first tool / row
        selected_row = 0
        try:
            self.select_tools_table_row(selected_row, clearsel=True)
        except Exception as e:
            # when the tools table is empty there will be this error but once the table is populated it will go away
            self.app.log.error('GeometryObject.build_ui() -> %s' % str(e))

        # disable the Plot column in Tool Table if the geometry is SingleGeo as it is not needed
        # and can create some problems
        if self.multigeo is False:
            self.ui.geo_tools_table.setColumnHidden(6, True)
        else:
            self.ui.geo_tools_table.setColumnHidden(6, False)

        self.ui_connect()

    def set_ui(self, ui):
        # this one adds the 'name' key and the self.ui.name_entry widget in the self.form_fields dict
        FlatCAMObj.set_ui(self, ui)

        self.app.log.debug("GeometryObject.set_ui()")

        assert isinstance(self.ui, GeometryObjectUI), \
            "Expected a GeometryObjectUI, got %s" % type(self.ui)

        self.units = self.app.app_units.upper()
        self.units_found = self.app.app_units

        self.form_fields.update({
            "plot": self.ui.plot_cb,
            "multicolored": self.ui.multicolored_cb,
        })

        # Fill form fields only on object create
        self.to_form()

        # store here the default data for Geometry Data
        self.default_data = {}

        # fill in self.default_data values from self.obj_options
        self.default_data.update(self.obj_options)

        if isinstance(self.obj_options["tools_mill_tooldia"], float):
            tools_list = [self.obj_options["tools_mill_tooldia"]]
        else:
            try:
                temp_tools = self.obj_options["tools_mill_tooldia"].split(",")
                tools_list = [
                    float(eval(dia)) for dia in temp_tools if dia != ''
                ]
            except Exception as e:
                self.app.log.error("GeometryObject.set_ui() -> At least one tool diameter needed. "
                                   "Verify in Edit -> Preferences -> Geometry General -> Tool dia. %s" % str(e))
                return

        self.tooluid += 1

        if not self.tools:
            for toold in tools_list:
                new_data = deepcopy(self.default_data)
                self.tools.update({
                    self.tooluid: {
                        'tooldia': self.app.dec_format(float(toold), self.decimals),
                        'data': new_data,
                        'solid_geometry': self.solid_geometry
                    }
                })
                self.tooluid += 1
        else:
            # if self.tools is not empty then it can safely be assumed that it comes from an opened project.
            # Because of the serialization the self.tools list on project save, the dict keys (members of self.tools
            # are each a dict) are turned into strings, so we rebuild the self.tools elements so the keys are
            # again float type; dicts don't like having keys changed when iterated through therefore the need for the
            # following convoluted way of changing the keys from string to float type
            temp_tools = {}
            for tool_uid_key in self.tools:
                val = deepcopy(self.tools[int(tool_uid_key)])
                new_key = deepcopy(int(tool_uid_key))
                temp_tools[new_key] = val

            self.tools.clear()
            self.tools = deepcopy(temp_tools)

        if not isinstance(self.ui, GeometryObjectUI):
            self.app.log.debug("Expected a GeometryObjectUI, got %s" % type(self.ui))
            return

        # #############################################################################################################
        # ##################################### Setting Values#########################################################
        # #############################################################################################################
        self.ui.vertex_points_entry.set_value(0)
        self.ui.geo_tol_entry.set_value(10 ** -self.decimals)

        # #############################################################################################################
        # ################################ Signals Connection #########################################################
        # #############################################################################################################
        self.ui.level.toggled.connect(self.on_level_changed)

        # Plot state signals
        # self.ui.plot_cb.stateChanged.connect(self.on_plot_cb_click)
        self.ui.multicolored_cb.stateChanged.connect(self.on_multicolored_cb_click)

        # Editor Signal
        self.ui.editor_button.clicked.connect(self.app.on_editing_start)

        # Properties
        self.ui.info_button.toggled.connect(self.on_properties)
        self.calculations_finished.connect(self.update_area_chull)
        self.ui.treeWidget.itemExpanded.connect(self.on_properties_expanded)
        self.ui.treeWidget.itemCollapsed.connect(self.on_properties_expanded)

        # # Buttons Signals
        self.ui.paint_tool_button.clicked.connect(lambda: self.app.paint_tool.run(toggle=True))
        self.ui.generate_ncc_button.clicked.connect(lambda: self.app.ncclear_tool.run(toggle=True))
        self.ui.milling_button.clicked.connect(self.on_milling_button_clicked)

        self.ui.util_button.clicked.connect(lambda st: self.ui.util_frame.show() if st else self.ui.util_frame.hide())
        self.ui.vertex_points_btn.clicked.connect(self.on_calculate_vertex_points)
        self.ui.simplification_btn.clicked.connect(self.on_simplify_geometry)

        self.set_offset_values()

        self.ui.geo_tools_table.itemSelectionChanged.connect(self.on_row_changed)
        self.ui.geo_tools_table.horizontalHeader().sectionClicked.connect(self.table_toggle_all)
        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.change_level(app_mode)

    def on_row_changed(self):
        pass

    def table_toggle_all(self):
        """
        Will toggle the selection of all rows in the table

        :return:
        """
        sel_model = self.ui.geo_tools_table.selectionModel()
        sel_indexes = sel_model.selectedIndexes()

        # it will iterate over all indexes which means all items in all columns too, but I'm interested only on rows
        sel_rows = set()
        for idx in sel_indexes:
            sel_rows.add(idx.row())

        if sel_rows:
            self.ui.geo_tools_table.clearSelection()
        else:
            self.ui.geo_tools_table.selectAll()

    def set_offset_values(self):
        xmin, ymin, xmax, ymax = self.bounds()
        center_coords = (
            self.app.dec_format((xmin + abs((xmax - xmin) / 2)), self.decimals),
            self.app.dec_format((ymin + abs((ymax - ymin) / 2)), self.decimals)
        )
        self.ui.offsetvector_entry.set_value(str(center_coords))

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

        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                                QToolButton
                                                {
                                                    color: red;
                                                }
                                                """)

    def on_properties(self, state):
        if state:
            self.ui.info_frame.show()
        else:
            self.ui.info_frame.hide()
            return

        self.ui.treeWidget.clear()
        self.add_properties_items(obj=self, treeWidget=self.ui.treeWidget)
        self.ui.treeWidget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                         QtWidgets.QSizePolicy.Policy.MinimumExpanding)
        # make sure that the FCTree widget columns are resized to content
        self.ui.treeWidget.resize_sig.emit()

    def on_properties_expanded(self):
        for col in range(self.treeWidget.columnCount()):
            self.ui.treeWidget.resizeColumnToContents(col)

    def on_milling_button_clicked(self):
        self.app.milling_tool.run(toggle=True)

    def on_calculate_vertex_points(self):
        self.app.log.debug("GeometryObject.on_calculate_vertex_points()")

        vertex_points = 0

        for tool in self.tools:
            geometry = self.tools[tool]['solid_geometry']
            flattened_geo = self.flatten_list(obj_list=geometry)
            for geo in flattened_geo:
                if geo.geom_type == 'Polygon':
                    vertex_points += len(list(geo.exterior.coords))
                    for inter in geo.interiors:
                        vertex_points += len(list(inter.coords))
                if geo.geom_type in ['LineString', 'LinearRing']:
                    vertex_points += len(list(geo.coords))

        self.ui.vertex_points_entry.set_value(vertex_points)
        self.app.inform.emit('[success] %s' % _("Vertex points calculated."))

    def on_simplify_geometry(self):
        self.app.log.debug("GeometryObject.on_simplify_geometry()")

        tol = self.ui.geo_tol_entry.get_value()

        def task_job():
            with self.app.proc_container.new('%s...' % _("Simplify")):
                for tool in self.tools:
                    new_tool_geo = []
                    geometry = self.tools[tool]['solid_geometry']
                    flattened_geo = self.flatten_list(obj_list=geometry)
                    for geo in flattened_geo:
                        new_tool_geo.append(geo.simplify(tolerance=tol))
                    self.tools[tool]['solid_geometry'] = deepcopy(new_tool_geo)

                # update the solid_geometry
                total_geo = []
                for tool in self.tools:
                    total_geo += self.tools[tool]['solid_geometry']

                self.solid_geometry = unary_union(total_geo)

                # plot the new geometry
                self.app.plot_all()

                # update the vertex points number
                self.on_calculate_vertex_points()

                self.app.inform.emit('[success] %s' % _("Done."))

        self.app.worker_task.emit({'fcn': task_job, 'params': []})

    def ui_connect(self):
        for row in range(self.ui.geo_tools_table.rowCount()):
            self.ui.geo_tools_table.cellWidget(row, 6).clicked.connect(self.on_plot_cb_click_table)

        self.ui.plot_cb.stateChanged.connect(self.on_plot_cb_click)

    def ui_disconnect(self):
        for row in range(self.ui.geo_tools_table.rowCount()):
            try:
                self.ui.geo_tools_table.cellWidget(row, 6).clicked.disconnect()
            except (TypeError, AttributeError):
                pass

        try:
            self.ui.plot_cb.stateChanged.disconnect()
        except (TypeError, AttributeError):
            pass

    def select_tools_table_row(self, row, clearsel=None):
        if clearsel:
            self.ui.geo_tools_table.clearSelection()

        if self.ui.geo_tools_table.rowCount() > 0:
            # self.ui.geo_tools_table.item(row, 0).setSelected(True)
            self.ui.geo_tools_table.setCurrentItem(self.ui.geo_tools_table.item(row, 0))

    def export_dxf(self):
        dwg = None
        dxf_format = self.app.options['geometry_dxf_format']

        try:
            dwg = ezdxf.new(dxf_format)
            msp = dwg.modelspace()

            # add units
            dwg.units = ezdxf.InsertUnits(4) if self.app.app_units.lower() == 'mm' else ezdxf.InsertUnits(1)
            dwg.header['$MEASUREMENT'] = 1 if self.app.app_units.lower() == 'mm' else 0

            def g2dxf(dxf_space, geo_obj):
                if isinstance(geo_obj, MultiPolygon):
                    for poly in geo_obj.geoms:
                        ext_points = list(poly.exterior.coords)
                        dxf_space.add_lwpolyline(ext_points)
                        for interior in poly.interiors:
                            dxf_space.add_lwpolyline(list(interior.coords))
                if isinstance(geo_obj, Polygon):
                    ext_points = list(geo_obj.exterior.coords)
                    dxf_space.add_lwpolyline(ext_points)
                    for interior in geo_obj.interiors:
                        dxf_space.add_lwpolyline(list(interior.coords))
                if isinstance(geo_obj, MultiLineString):
                    for line in geo_obj.geoms:
                        dxf_space.add_lwpolyline(list(line.coords))
                if isinstance(geo_obj, LineString) or isinstance(geo_obj, LinearRing):
                    dxf_space.add_lwpolyline(list(geo_obj.coords))

            multigeo_solid = []
            if self.multigeo:
                for tool in self.tools:
                    w_geo_list = list(self.tools[tool]['solid_geometry'].geoms) if \
                        isinstance(self.tools[tool]['solid_geometry'], (MultiPolygon, MultiLineString)) else \
                        self.tools[tool]['solid_geometry']
                    multigeo_solid += w_geo_list
            else:
                multigeo_solid = self.solid_geometry

            w_geo = multigeo_solid.geoms \
                if isinstance(multigeo_solid, (MultiPolygon, MultiLineString)) else multigeo_solid
            for geo in w_geo:
                if isinstance(geo, list):
                    for g in geo:
                        g2dxf(msp, g)
                else:
                    g2dxf(msp, geo)

                # points = GeometryObject.get_pts(geo)
                # msp.add_lwpolyline(points)
        except Exception as e:
            self.app.log.error(str(e))

        return dwg

    def mtool_gen_cncjob(self, outname=None, tools_dict=None, seg_x=None, seg_y=None,
                         plot=True, use_thread=True):
        """
        Creates a multi-tool CNCJob out of this Geometry object.
        The actual work is done by the target CNCJobObject object's
        `generate_from_geometry_2()` method.

        :param outname:
        :param tools_dict:      a dictionary that holds the whole data needed to create the Gcode
                                (including the solid_geometry)
        :param seg_x:            number of segments on the X axis, for auto-levelling
        :param seg_y:            number of segments on the Y axis, for auto-levelling
        :param plot:            if True the generated object will be plotted; if False will not be plotted
        :param use_thread:      if True use threading
        :return:                None
        """

        # use the name of the first tool selected in self.geo_tools_table which has the diameter passed as tool_dia
        outname = "%s_%s" % (self.obj_options["name"], 'cnc') if outname is None else outname

        tools_dict = self.sel_tools if tools_dict is None else tools_dict
        seg_x = seg_x if seg_x is not None else float(self.app.options['geometry_seg_x'])
        seg_y = seg_y if seg_y is not None else float(self.app.options['geometry_seg_y'])

        try:
            xmin = self.obj_options['xmin']
            ymin = self.obj_options['ymin']
            xmax = self.obj_options['xmax']
            ymax = self.obj_options['ymax']
        except Exception as e:
            self.app.log.error("FlatCAMObj.GeometryObject.mtool_gen_cncjob() --> %s\n" % str(e))

            msg = '[ERROR] %s' % _("An internal error has occurred. See shell.\n")
            msg += '%s' % str(e)
            msg += traceback.format_exc()
            self.app.inform.emit(msg)
            return

        # force everything as MULTI-GEO
        # self.multigeo = True

        # Object initialization function for app.app_obj.new_object()
        # RUNNING ON SEPARATE THREAD!
        def job_init_single_geometry(job_obj, app_obj):
            self.app.log.debug("Creating a CNCJob out of a single-geometry")
            assert job_obj.kind == 'cncjob', "Initializer expected a CNCJobObject, got %s" % type(job_obj)

            job_obj.obj_options['xmin'] = xmin
            job_obj.obj_options['ymin'] = ymin
            job_obj.obj_options['xmax'] = xmax
            job_obj.obj_options['ymax'] = ymax

            # count the tools
            tool_cnt = 0

            # dia_cnc_dict = {}

            # this turn on the FlatCAMCNCJob plot for multiple tools
            job_obj.multitool = True
            job_obj.multigeo = False
            job_obj.tools.clear()

            job_obj.seg_x = seg_x if seg_x else float(self.app.options["geometry_seg_x"])
            job_obj.seg_y = seg_y if seg_y else float(self.app.options["geometry_seg_y"])

            job_obj.z_p_depth = float(self.app.options["tools_mill_z_p_depth"])
            job_obj.feedrate_probe = float(self.app.options["tools_mill_feedrate_probe"])

            total_gcode = ''
            for tool_uid_key in list(tools_dict.keys()):
                tool_cnt += 1

                dia_cnc_dict = deepcopy(tools_dict[tool_uid_key])
                tooldia_val = app_obj.dec_format(float(tools_dict[tool_uid_key]['tooldia']), self.decimals)
                dia_cnc_dict.update({
                    'tooldia': tooldia_val
                })

                if dia_cnc_dict['data']['tools_mill_offset_type'] == 'in':
                    tool_offset = -dia_cnc_dict['tooldia'] / 2
                elif dia_cnc_dict['data']['tools_mill_offset_type'].lower() == 'out':
                    tool_offset = dia_cnc_dict['tooldia'] / 2
                elif dia_cnc_dict['data']['tools_mill_offset_type'].lower() == 'custom':
                    try:
                        offset_value = float(self.ui.tool_offset_entry.get_value())
                    except ValueError:
                        # try to convert comma to decimal point. if it's still not working error message and return
                        try:
                            offset_value = float(self.ui.tool_offset_entry.get_value().replace(',', '.'))
                        except ValueError:
                            app_obj.inform.emit('[ERROR_NOTCL] %s' % _("Wrong value format entered, use a number."))
                            return
                    if offset_value:
                        tool_offset = float(offset_value)
                    else:
                        app_obj.inform.emit(
                            '[WARNING] %s' % _("Tool Offset is selected in Tool Table but no value is provided.\n"
                                               "Add a Tool Offset or change the Offset Type.")
                        )
                        return
                else:
                    tool_offset = 0.0

                dia_cnc_dict['data']['tools_mill_offset_type'] = tool_offset

                z_cut = tools_dict[tool_uid_key]['data']["tools_mill_cutz"]
                z_move = tools_dict[tool_uid_key]['data']["tools_mill_travelz"]
                feedrate = tools_dict[tool_uid_key]['data']["tools_mill_feedrate"]
                feedrate_z = tools_dict[tool_uid_key]['data']["tools_mill_feedrate_z"]
                feedrate_rapid = tools_dict[tool_uid_key]['data']["tools_mill_feedrate_rapid"]
                multidepth = tools_dict[tool_uid_key]['data']["tools_mill_multidepth"]
                extracut = tools_dict[tool_uid_key]['data']["tools_mill_extracut"]
                extracut_length = tools_dict[tool_uid_key]['data']["tools_mill_extracut_length"]
                depthpercut = tools_dict[tool_uid_key]['data']["tools_mill_depthperpass"]
                toolchange = tools_dict[tool_uid_key]['data']["tools_mill_toolchange"]
                toolchangez = tools_dict[tool_uid_key]['data']["tools_mill_toolchangez"]
                toolchangexy = tools_dict[tool_uid_key]['data']["tools_mill_toolchangexy"]
                startz = tools_dict[tool_uid_key]['data']["tools_mill_startz"]
                endz = tools_dict[tool_uid_key]['data']["tools_mill_endz"]
                endxy = self.obj_options["tools_mill_endxy"]
                spindlespeed = tools_dict[tool_uid_key]['data']["tools_mill_spindlespeed"]
                dwell = tools_dict[tool_uid_key]['data']["tools_mill_dwell"]
                dwelltime = tools_dict[tool_uid_key]['data']["tools_mill_dwelltime"]
                pp_geometry_name = tools_dict[tool_uid_key]['data']["tools_mill_ppname_g"]

                spindledir = self.app.options['tools_mill_spindledir']
                tool_solid_geometry = self.solid_geometry

                job_obj.coords_decimals = self.app.options["cncjob_coords_decimals"]
                job_obj.fr_decimals = self.app.options["cncjob_fr_decimals"]

                # Propagate options
                job_obj.obj_options["tooldia"] = tooldia_val
                job_obj.obj_options['type'] = 'Geometry'
                job_obj.obj_options['tool_dia'] = tooldia_val

                tool_lst = list(tools_dict.keys())
                is_first = True if tool_uid_key == tool_lst[0] else False

                # it seems that the tolerance needs to be a lot lower value than 0.01, and it was hardcoded initially
                # to a value of 0.0005 which is 20 times less than 0.01
                tol = float(self.app.options['global_tolerance']) / 20
                res, start_gcode = job_obj.generate_from_geometry_2(
                    self, tooldia=tooldia_val, offset=tool_offset, tolerance=tol,
                    z_cut=z_cut, z_move=z_move,
                    feedrate=feedrate, feedrate_z=feedrate_z, feedrate_rapid=feedrate_rapid,
                    spindlespeed=spindlespeed, spindle_dir=spindledir, dwell=dwell, dwelltime=dwelltime,
                    multidepth=multidepth, depthpercut=depthpercut,
                    extracut=extracut, extracut_length=extracut_length, startz=startz, endz=endz, endxy=endxy,
                    toolchange=toolchange, toolchangez=toolchangez, toolchangexy=toolchangexy,
                    pp_geometry_name=pp_geometry_name,
                    tool_no=tool_cnt, is_first=is_first)

                if res == 'fail':
                    self.app.log.debug("GeometryObject.mtool_gen_cncjob() --> generate_from_geometry2() failed")
                    return 'fail'

                dia_cnc_dict['gcode'] = res
                if start_gcode != '':
                    job_obj.gc_start = start_gcode

                total_gcode += res

                self.app.inform.emit('[success] %s' % _("G-Code parsing in progress..."))
                dia_cnc_dict['gcode_parsed'] = job_obj.gcode_parse(tool_data=tools_dict[tool_uid_key]['data'])
                app_obj.inform.emit('[success] %s' % _("G-Code parsing finished..."))

                # commented this; there is no need for the actual GCode geometry - the original one will serve as well
                # for bounding box values
                # dia_cnc_dict['solid_geometry'] = unary_union([geo['geom'] for geo in dia_cnc_dict['gcode_parsed']])
                try:
                    dia_cnc_dict['solid_geometry'] = tool_solid_geometry
                    app_obj.inform.emit('[success] %s...' % _("Finished G-Code processing"))
                except Exception as er:
                    app_obj.inform.emit('[ERROR] %s: %s' % (_("G-Code processing failed with error"), str(er)))

                job_obj.tools.update({
                    tool_uid_key: deepcopy(dia_cnc_dict)
                })
                dia_cnc_dict.clear()

            job_obj.source_file = job_obj.gc_start + total_gcode

        # Object initialization function for app.app_obj.new_object()
        # RUNNING ON SEPARATE THREAD!
        def job_init_multi_geometry(job_obj, app_obj):
            self.app.log.debug("Creating a CNCJob out of a multi-geometry")
            assert job_obj.kind == 'cncjob', "Initializer expected a CNCJobObject, got %s" % type(job_obj)

            job_obj.obj_options['xmin'] = xmin
            job_obj.obj_options['ymin'] = ymin
            job_obj.obj_options['xmax'] = xmax
            job_obj.obj_options['ymax'] = ymax

            # count the tools
            tool_cnt = 0

            # dia_cnc_dict = {}

            # this turn on the FlatCAMCNCJob plot for multiple tools
            job_obj.multitool = True
            job_obj.multigeo = True
            job_obj.tools.clear()

            job_obj.seg_x = seg_x if seg_x else float(self.app.options["geometry_seg_x"])
            job_obj.seg_y = seg_y if seg_y else float(self.app.options["geometry_seg_y"])

            job_obj.z_p_depth = float(self.app.options["tools_mill_z_p_depth"])
            job_obj.feedrate_probe = float(self.app.options["tools_mill_feedrate_probe"])

            # make sure that trying to make a CNCJob from an empty file is not creating an app crash
            if not self.solid_geometry:
                a = 0
                for tooluid_key in self.tools:
                    if self.tools[tooluid_key]['solid_geometry'] is None:
                        a += 1
                if a == len(self.tools):
                    app_obj.inform.emit('[ERROR_NOTCL] %s...' % _('Cancelled. Empty file, it has no geometry'))
                    return 'fail'

            total_gcode = ''
            for tooluid_key in list(tools_dict.keys()):
                tool_cnt += 1
                dia_cnc_dict = deepcopy(tools_dict[tooluid_key])
                tooldia_val = app_obj.dec_format(float(tools_dict[tooluid_key]['tooldia']), self.decimals)
                dia_cnc_dict.update({
                    'tooldia': tooldia_val
                })
                if "optimization_type" not in tools_dict[tooluid_key]['data']:
                    optimization_type = self.app.options["tools_mill_optimization_type"]
                    tools_dict[tooluid_key]['data']["tools_mill_optimization_type"] = optimization_type

                # find the tool_dia associated with the tooluid_key
                # search in the self.tools for the sel_tool_dia and when found see what tooluid has
                # on the found tooluid in self.tools we also have the solid_geometry that interest us
                # for k, v in self.tools.items():
                #     if float('%.*f' % (self.decimals, float(v['tooldia']))) == tooldia_val:
                #         current_uid = int(k)
                #         break

                if dia_cnc_dict['data']['tools_mill_offset_type'].lower() == 'in':
                    tool_offset = -tooldia_val / 2
                elif dia_cnc_dict['data']['tools_mill_offset_type'].lower() == 'out':
                    tool_offset = tooldia_val / 2
                elif dia_cnc_dict['data']['tools_mill_offset_type'].lower() == 'custom':
                    offset_value = float(self.ui.tool_offset_entry.get_value())
                    if offset_value:
                        tool_offset = float(offset_value)
                    else:
                        self.app.inform.emit('[WARNING] %s' %
                                             _("Tool Offset is selected in Tool Table but "
                                               "no value is provided.\n"
                                               "Add a Tool Offset or change the Offset Type."))
                        return
                else:
                    tool_offset = 0.0

                dia_cnc_dict['data']['tools_mill_offset_type'] = tool_offset

                # z_cut = tools_dict[tooluid_key]['data']["cutz"]
                # z_move = tools_dict[tooluid_key]['data']["travelz"]
                # feedrate = tools_dict[tooluid_key]['data']["feedrate"]
                # feedrate_z = tools_dict[tooluid_key]['data']["feedrate_z"]
                # feedrate_rapid = tools_dict[tooluid_key]['data']["feedrate_rapid"]
                # multidepth = tools_dict[tooluid_key]['data']["multidepth"]
                # extracut = tools_dict[tooluid_key]['data']["extracut"]
                # extracut_length = tools_dict[tooluid_key]['data']["extracut_length"]
                # depthpercut = tools_dict[tooluid_key]['data']["depthperpass"]
                # toolchange = tools_dict[tooluid_key]['data']["toolchange"]
                # toolchangez = tools_dict[tooluid_key]['data']["toolchangez"]
                # toolchangexy = tools_dict[tooluid_key]['data']["toolchangexy"]
                # startz = tools_dict[tooluid_key]['data']["startz"]
                # endz = tools_dict[tooluid_key]['data']["endz"]
                # endxy = self.obj_options["endxy"]
                # spindlespeed = tools_dict[tooluid_key]['data']["spindlespeed"]
                # dwell = tools_dict[tooluid_key]['data']["dwell"]
                # dwelltime = tools_dict[tooluid_key]['data']["dwelltime"]
                # pp_geometry_name = tools_dict[tooluid_key]['data']["ppname_g"]
                #
                # spindledir = self.app.options['geometry_spindledir']
                tool_solid_geometry = self.tools[tooluid_key]['solid_geometry']

                job_obj.coords_decimals = self.app.options["cncjob_coords_decimals"]
                job_obj.fr_decimals = self.app.options["cncjob_fr_decimals"]

                # Propagate options
                job_obj.obj_options["tooldia"] = tooldia_val
                job_obj.obj_options['type'] = 'Geometry'
                job_obj.obj_options['tool_dia'] = tooldia_val

                # it seems that the tolerance needs to be a lot lower value than 0.01, and it was hardcoded initially
                # to a value of 0.0005 which is 20 times less than 0.01
                tol = float(self.app.options['global_tolerance']) / 20

                tool_lst = list(tools_dict.keys())
                is_first = True if tooluid_key == tool_lst[0] else False
                is_last = True if tooluid_key == tool_lst[-1] else False
                res, start_gcode = job_obj.geometry_tool_gcode_gen(tooluid_key, tools_dict, first_pt=(0, 0),
                                                                   tolerance=tol,
                                                                   is_first=is_first, is_last=is_last,
                                                                   toolchange=True)
                if res == 'fail':
                    self.app.log.debug("GeometryObject.mtool_gen_cncjob() --> generate_from_geometry2() failed")
                    return 'fail'
                else:
                    dia_cnc_dict['gcode'] = res
                total_gcode += res

                if start_gcode != '':
                    job_obj.gc_start = start_gcode

                app_obj.inform.emit('[success] %s' % _("G-Code parsing in progress..."))
                dia_cnc_dict['gcode_parsed'] = job_obj.gcode_parse(tool_data=tools_dict[tooluid_key]['data'])
                app_obj.inform.emit('[success] %s' % _("G-Code parsing finished..."))

                # commented this; there is no need for the actual GCode geometry - the original one will serve as well
                # for bounding box values
                # geo_for_bound_values = unary_union([
                #     geo['geom'] for geo in dia_cnc_dict['gcode_parsed'] if geo['geom'].is_valid is True
                # ])
                try:
                    dia_cnc_dict['solid_geometry'] = deepcopy(tool_solid_geometry)
                    app_obj.inform.emit('[success] %s...' % _("Finished G-Code processing"))
                except Exception as ee:
                    app_obj.inform.emit('[ERROR] %s: %s' % (_("G-Code processing failed with error"), str(ee)))

                job_obj.tools.update({
                    tooluid_key: deepcopy(dia_cnc_dict)
                })
                dia_cnc_dict.clear()

            job_obj.source_file = total_gcode

        if use_thread:
            # To be run in separate thread
            def job_thread(a_obj):
                if self.multigeo is False:
                    with self.app.proc_container.new('%s...' % _("Generating")):
                        ret_val = a_obj.app_obj.new_object("cncjob", outname, job_init_single_geometry, plot=plot)
                        if ret_val != 'fail':
                            a_obj.inform.emit('[success] %s: %s' % (_("CNCjob created"), outname))
                else:
                    with self.app.proc_container.new('%s...' % _("Generating")):
                        ret_val = a_obj.app_obj.new_object("cncjob", outname, job_init_multi_geometry, plot=plot)
                        if ret_val != 'fail':
                            a_obj.inform.emit('[success] %s: %s' % (_("CNCjob created"), outname))

            # Create a promise with the name
            self.app.collection.promise(outname)
            # Send to worker
            self.app.worker_task.emit({'fcn': job_thread, 'params': [self.app]})
        else:
            if self.solid_geometry:
                self.app.app_obj.new_object("cncjob", outname, job_init_single_geometry, plot=plot)
            else:
                self.app.app_obj.new_object("cncjob", outname, job_init_multi_geometry, plot=plot)

    def generatecncjob(self, outname=None, dia=None, offset=None, z_cut=None, z_move=None, feedrate=None,
                       feedrate_z=None, feedrate_rapid=None, spindlespeed=None, dwell=None, dwelltime=None,
                       las_min_pwr=0.0,
                       multidepth=None, dpp=None, toolchange=None, toolchangez=None, toolchangexy=None,
                       extracut=None, extracut_length=None, startz=None, endz=None, endxy=None, pp=None,
                       seg_x=None, seg_y=None, use_thread=True, plot=True, **args):
        """
        Only used by the TCL Command Cncjob.
        Creates a CNCJob out of this Geometry object. The actual
        work is done by the target camlib.CNCjob
        `generate_from_geometry_2()` method.

        :param outname:         Name of the new object
        :param dia:             Tool diameter
        :param offset:
        :param z_cut:           Cut depth (negative value)
        :param z_move:          Height of the tool when travelling (not cutting)
        :param feedrate:        Feed rate while cutting on X - Y plane
        :param feedrate_z:      Feed rate while cutting on Z plane
        :param feedrate_rapid:  Feed rate while moving with rapids
        :param spindlespeed:    Spindle speed (RPM)
        :param dwell:
        :param dwelltime:
        :param las_min_pwr:     Float. Set the power for a laser (when used due of a preprocessor) when not cutting
        :param multidepth:      Bool: If True use the `dpp` parameter
        :param dpp:             Depth for each pass when multidepth parameter is True. Positive value.
        :param toolchange:
        :param toolchangez:
        :param toolchangexy:    A sequence ox X,Y coordinates: a 2-length tuple or a string.
                                Coordinates in X,Y plane for the Toolchange event
        :param extracut:
        :param extracut_length:
        :param startz:
        :param endz:
        :param endxy:           A sequence ox X,Y coordinates: a 2-length tuple or a string.
                                Coordinates in X, Y plane for the last move after ending the job.
        :param pp:              Name of the preprocessor
        :param seg_x:
        :param seg_y:
        :param use_thread:
        :param plot:
        :return: None
        """

        self.app.log.debug("FlatCAMGeometry.GeometryObject.generatecncjob()")

        tooldia = dia if dia else float(self.obj_options["tools_mill_tooldia"])
        outname = outname if outname is not None else self.obj_options["name"]

        z_cut = z_cut if z_cut is not None else float(self.obj_options["tools_mill_cutz"])
        z_move = z_move if z_move is not None else float(self.obj_options["tools_mill_travelz"])

        feedrate = feedrate if feedrate is not None else float(self.obj_options["tools_mill_feedrate"])
        feedrate_z = feedrate_z if feedrate_z is not None else float(self.obj_options["tools_mill_feedrate_z"])
        feedrate_rapid = feedrate_rapid if feedrate_rapid is not None else float(self.obj_options[
                                                                                     "tools_mill_feedrate_rapid"])

        multidepth = multidepth if multidepth is not None else self.obj_options["tools_mill_multidepth"]
        depthperpass = dpp if dpp is not None else float(self.obj_options["tools_mill_depthperpass"])

        seg_x = seg_x if seg_x is not None else float(self.app.options['geometry_seg_x'])
        seg_y = seg_y if seg_y is not None else float(self.app.options['geometry_seg_y'])

        extracut = extracut if extracut is not None else float(self.obj_options["tools_mill_extracut"])
        extracut_length = extracut_length if extracut_length is not None else float(self.obj_options[
                                                                                        "tools_mill_extracut_length"])

        startz = startz if startz is not None else self.obj_options["tools_mill_startz"]
        endz = endz if endz is not None else float(self.obj_options["tools_mill_endz"])

        endxy = endxy if endxy else self.obj_options["tools_mill_endxy"]
        if isinstance(endxy, str):
            endxy = re.sub(r'[()\[\]]', '', endxy)
            if endxy and endxy != '':
                endxy = [float(eval(a)) for a in endxy.split(",")]

        toolchangez = toolchangez if toolchangez else float(self.obj_options["tools_mill_toolchangez"])

        toolchangexy = toolchangexy if toolchangexy else self.obj_options["tools_mill_toolchangexy"]
        if isinstance(toolchangexy, str):
            toolchangexy = re.sub(r'[()\[\]]', '', toolchangexy)
            if toolchangexy and toolchangexy != '':
                toolchangexy = [float(eval(a)) for a in toolchangexy.split(",")]

        toolchange = toolchange if toolchange else self.obj_options["tools_mill_toolchange"]

        offset = offset if offset else 0.0

        # int or None.
        spindlespeed = spindlespeed if spindlespeed else self.obj_options['tools_mill_spindlespeed']
        las_min_pwr = las_min_pwr if las_min_pwr else self.obj_options['tools_mill_min_power']
        dwell = dwell if dwell else self.obj_options["tools_mill_dwell"]
        dwelltime = dwelltime if dwelltime else float(self.obj_options["tools_mill_dwelltime"])

        ppname_g = pp if pp else self.obj_options["tools_mill_ppname_g"]

        # Object initialization function for app.app_obj.new_object()
        # RUNNING ON SEPARATE THREAD!
        def job_init(job_obj, app_obj):
            assert job_obj.kind == 'cncjob', "Initializer expected a CNCJobObject, got %s" % type(job_obj)

            # Propagate options
            job_obj.obj_options["tooldia"] = tooldia
            job_obj.obj_options["tools_mill_tooldia"] = tooldia

            job_obj.coords_decimals = self.app.options["cncjob_coords_decimals"]
            job_obj.fr_decimals = self.app.options["cncjob_fr_decimals"]

            job_obj.obj_options['type'] = 'Geometry'
            job_obj.obj_options['tool_dia'] = tooldia

            job_obj.seg_x = seg_x
            job_obj.seg_y = seg_y

            job_obj.z_p_depth = float(self.obj_options["tools_mill_z_p_depth"])
            job_obj.feedrate_probe = float(self.obj_options["tools_mill_feedrate_probe"])

            job_obj.obj_options['xmin'] = self.obj_options['xmin']
            job_obj.obj_options['ymin'] = self.obj_options['ymin']
            job_obj.obj_options['xmax'] = self.obj_options['xmax']
            job_obj.obj_options['ymax'] = self.obj_options['ymax']

            # it seems that the tolerance needs to be a lot lower value than 0.01, and it was hardcoded initially
            # to a value of 0.0005 which is 20 times less than 0.01
            tol = float(self.app.options['global_tolerance']) / 20
            res, start_gcode = job_obj.generate_from_geometry_2(
                self, tooldia=tooldia, offset=offset, tolerance=tol, z_cut=z_cut, z_move=z_move, feedrate=feedrate,
                feedrate_z=feedrate_z, feedrate_rapid=feedrate_rapid, spindlespeed=spindlespeed, dwell=dwell,
                dwelltime=dwelltime, laser_min_power=las_min_pwr, multidepth=multidepth, depthpercut=depthperpass,
                toolchange=toolchange,
                toolchangez=toolchangez, toolchangexy=toolchangexy, extracut=extracut, extracut_length=extracut_length,
                startz=startz, endz=endz, endxy=endxy, pp_geometry_name=ppname_g, is_first=True)

            if start_gcode != '':
                job_obj.gc_start = start_gcode

            job_obj.source_file = start_gcode + res
            job_obj.gcode_parse()
            app_obj.inform.emit('[success] %s...' % _("Finished G-Code processing"))

        if use_thread:
            # To be run in separate thread
            def job_thread(app_obj):
                with self.app.proc_container.new('%s...' % _("Generating")):
                    app_obj.app_obj.new_object("cncjob", outname, job_init, plot=plot)
                    app_obj.inform.emit('[success] %s: %s' % (_("CNCjob created"), outname))

            # Create a promise with the name
            self.app.collection.promise(outname)
            # Send to worker
            self.app.worker_task.emit({'fcn': job_thread, 'params': [self.app]})
        else:
            self.app.app_obj.new_object("cncjob", outname, job_init, plot=plot)

    def scale(self, xfactor, yfactor=None, point=None):
        """
        Scales all geometry by a given factor.

        :param xfactor:     Factor by which to scale the object's geometry/
        :type xfactor:      float
        :param yfactor:     Factor by which to scale the object's geometry/
        :type yfactor:      float
        :param point:       Point around which to scale
        :return: None
        """
        self.app.log.debug("FlatCAMObj.GeometryObject.scale()")

        try:
            xfactor = float(xfactor)
        except Exception:
            self.app.inform.emit('[ERROR_NOTCL] %s' % _("Scale factor has to be a number: integer or float."))
            return

        if yfactor is None:
            yfactor = xfactor
        else:
            try:
                yfactor = float(yfactor)
            except Exception:
                self.app.inform.emit('[ERROR_NOTCL] %s' % _("Scale factor has to be a number: integer or float."))
                return

        if xfactor == 1 and yfactor == 1:
            return

        if point is None:
            px = 0
            py = 0
        else:
            px, py = point

        self.geo_len = 0
        self.old_disp_number = 0
        self.el_count = 0

        def scale_recursion(geom):
            if type(geom) is list:
                geoms = []
                for local_geom in geom:
                    geoms.append(scale_recursion(local_geom))
                return geoms
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 100]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return scale(geom, xfactor, yfactor, origin=(px, py))
                except AttributeError:
                    return geom

        if self.multigeo is True:
            for tool in self.tools:
                # variables to display the percentage of work done
                self.geo_len = 0
                try:
                    self.geo_len = len(self.tools[tool]['solid_geometry'])
                except TypeError:
                    self.geo_len = 1
                self.old_disp_number = 0
                self.el_count = 0

                self.tools[tool]['solid_geometry'] = scale_recursion(self.tools[tool]['solid_geometry'])

        try:
            # variables to display the percentage of work done
            self.geo_len = 0
            try:
                self.geo_len = len(self.solid_geometry)
            except TypeError:
                self.geo_len = 1
            self.old_disp_number = 0
            self.el_count = 0

            self.solid_geometry = scale_recursion(self.solid_geometry)
        except AttributeError:
            self.solid_geometry = []
            return

        self.app.proc_container.new_text = ''
        self.app.inform.emit('[success] %s' % _("Done."))

    def offset(self, vect):
        """
        Offsets all geometry by a given vector/

        :param vect: (x, y) vector by which to offset the object's geometry.
        :type vect: tuple
        :return: None
        """
        self.app.log.debug("FlatCAMObj.GeometryObject.offset()")

        try:
            dx, dy = vect
        except TypeError:
            self.app.inform.emit('[ERROR_NOTCL] %s' %
                                 _("An (x,y) pair of values are needed. "
                                   "Probable you entered only one value in the Offset field.")
                                 )
            return

        if dx == 0 and dy == 0:
            return

        self.geo_len = 0
        self.old_disp_number = 0
        self.el_count = 0

        def translate_recursion(geom):
            if type(geom) is list:
                geoms = []
                for local_geom in geom:
                    geoms.append(translate_recursion(local_geom))
                return geoms
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 100]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return translate(geom, xoff=dx, yoff=dy)
                except AttributeError:
                    return geom

        if self.multigeo is True:
            for tool in self.tools:
                # variables to display the percentage of work done
                self.geo_len = 0
                try:
                    source_geo = self.tools[tool]['solid_geometry']
                    work_geo = source_geo.geoms if isinstance(source_geo, (MultiPolygon, MultiLineString)) else \
                        source_geo
                    self.geo_len = len(work_geo)
                except TypeError:
                    self.geo_len = 1
                self.old_disp_number = 0
                self.el_count = 0

                self.tools[tool]['solid_geometry'] = translate_recursion(self.tools[tool]['solid_geometry'])

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            source_geo = self.solid_geometry
            work_geo = source_geo.geoms if isinstance(source_geo, (MultiPolygon, MultiLineString)) else \
                source_geo
            self.geo_len = len(work_geo)
        except TypeError:
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        self.solid_geometry = translate_recursion(self.solid_geometry)

        self.app.proc_container.new_text = ''
        self.app.inform.emit('[success] %s' % _("Done."))

    def convert_units(self, units):
        self.app.log.debug("FlatCAMObj.GeometryObject.convert_units()")

        self.ui_disconnect()

        factor = Geometry.convert_units(self, units)

        self.obj_options['cutz'] = float(self.obj_options['cutz']) * factor
        self.obj_options['depthperpass'] = float(self.obj_options['depthperpass']) * factor
        self.obj_options['travelz'] = float(self.obj_options['travelz']) * factor
        self.obj_options['feedrate'] = float(self.obj_options['feedrate']) * factor
        self.obj_options['feedrate_z'] = float(self.obj_options['feedrate_z']) * factor
        self.obj_options['feedrate_rapid'] = float(self.obj_options['feedrate_rapid']) * factor
        self.obj_options['endz'] = float(self.obj_options['endz']) * factor
        # self.obj_options['tools_mill_tooldia'] *= factor
        # self.obj_options['painttooldia'] *= factor
        # self.obj_options['paintmargin'] *= factor
        # self.obj_options['paintoverlap'] *= factor

        self.obj_options["toolchangez"] = float(self.obj_options["toolchangez"]) * factor

        if self.app.options["tools_mill_toolchangexy"] == '':
            self.obj_options['toolchangexy'] = "0.0, 0.0"
        else:
            coords_xy = [float(eval(coord)) for coord in self.app.options["tools_mill_toolchangexy"].split(",")]
            if len(coords_xy) < 2:
                self.app.inform.emit('[ERROR] %s' %
                                     _("The Toolchange X,Y field in Edit -> Preferences "
                                       "has to be in the format (x, y)\n"
                                       "but now there is only one value, not two.")
                                     )
                return 'fail'
            coords_xy[0] *= factor
            coords_xy[1] *= factor
            self.obj_options['toolchangexy'] = "%f, %f" % (coords_xy[0], coords_xy[1])

        if self.obj_options['startz'] is not None:
            self.obj_options['startz'] = float(self.obj_options['startz']) * factor

        param_list = ['cutz', 'depthperpass', 'travelz', 'feedrate', 'feedrate_z', 'feedrate_rapid',
                      'endz', 'toolchangez']

        if isinstance(self, GeometryObject):
            temp_tools_dict = {}
            tool_dia_copy = {}
            data_copy = {}
            for tooluid_key, tooluid_value in self.tools.items():
                for dia_key, dia_value in tooluid_value.items():
                    if dia_key == 'tooldia':
                        dia_value *= factor
                        dia_value = float('%.*f' % (self.decimals, dia_value))
                        tool_dia_copy[dia_key] = dia_value
                    if dia_key == 'offset':
                        tool_dia_copy[dia_key] = dia_value
                    if dia_key == 'offset_value':
                        dia_value *= factor
                        tool_dia_copy[dia_key] = dia_value

                        # convert the value in the Custom Tool Offset entry in UI
                        custom_offset = None
                        try:
                            custom_offset = float(self.ui.tool_offset_entry.get_value())
                        except ValueError:
                            # try to convert comma to decimal point. if it's still not working error message and return
                            try:
                                custom_offset = float(self.ui.tool_offset_entry.get_value().replace(',', '.'))
                            except ValueError:
                                self.app.inform.emit('[ERROR_NOTCL] %s' %
                                                     _("Wrong value format entered, use a number."))
                                return
                        except TypeError:
                            pass

                        if custom_offset:
                            custom_offset *= factor
                            self.ui.tool_offset_entry.set_value(custom_offset)

                    if dia_key == 'tool_type':
                        tool_dia_copy[dia_key] = dia_value
                    if dia_key == 'data':
                        for data_key, data_value in dia_value.items():
                            # convert the form fields that are convertible
                            for param in param_list:
                                if data_key == param and data_value is not None:
                                    data_copy[data_key] = data_value * factor
                            # copy the other dict entries that are not convertible
                            if data_key not in param_list:
                                data_copy[data_key] = data_value
                        tool_dia_copy[dia_key] = deepcopy(data_copy)
                        data_copy.clear()

                temp_tools_dict.update({
                    tooluid_key: deepcopy(tool_dia_copy)
                })
                tool_dia_copy.clear()

            self.tools.clear()
            self.tools = deepcopy(temp_tools_dict)

        return factor

    def plot_element(self, element, color=None, visible=None):

        if color is None:
            color = '#FF0000FF'

        visible = visible if visible else self.obj_options['plot']
        try:
            if isinstance(element, (MultiPolygon, MultiLineString)):
                for sub_el in element.geoms:
                    self.plot_element(sub_el, color=color)
            else:
                for sub_el in element:
                    self.plot_element(sub_el, color=color)
        except TypeError:  # Element is not iterable...
            # if self.app.use_3d_engine:
            self.add_shape(shape=element, color=color, visible=visible, layer=0)

    def plot(self, visible=None, kind=None, plot_tool=None):
        """
        Plot the object.

        :param visible:     Controls if the added shape is visible of not
        :param kind:        added so there is no error when a project is loaded, and it has both geometry and CNCJob,
                            because CNCJob require the 'kind' parameter. Perhaps the FlatCAMObj.plot()
                            has to be rewritten
        :param plot_tool:   plot a specific tool for multigeo objects
        :return:
        """

        # Does all the required setup and returns False
        # if the 'ptint' option is set to False.
        if not FlatCAMObj.plot(self):
            return

        if self.app.use_3d_engine:
            def random_color():
                r_color = np.random.rand(4)
                r_color[3] = 1
                return r_color
        else:
            def random_color():
                while True:
                    r_color = np.random.rand(4)
                    r_color[3] = 1

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
            # plot solid geometries found as members of self.tools attribute dict
            # for MultiGeo
            if self.multigeo is True:  # geo multi tool usage
                if plot_tool is None:
                    for tooluid_key in self.tools:
                        solid_geometry = self.tools[tooluid_key]['solid_geometry']
                        if 'override_color' in self.tools[tooluid_key]['data']:
                            color = self.tools[tooluid_key]['data']['override_color']
                        else:
                            color = random_color() if self.obj_options['multicolored'] else \
                                self.app.options["geometry_plot_line"]

                        self.plot_element(solid_geometry, visible=visible, color=color)
                else:
                    solid_geometry = self.tools[plot_tool]['solid_geometry']
                    if 'override_color' in self.tools[plot_tool]['data']:
                        color = self.tools[plot_tool]['data']['override_color']
                    else:
                        color = random_color() if self.obj_options['multicolored'] else \
                            self.app.options["geometry_plot_line"]

                    self.plot_element(solid_geometry, visible=visible, color=color)
            else:
                # plot solid geometry that may be a direct attribute of the geometry object
                # for SingleGeo
                if self.solid_geometry:
                    solid_geometry = self.solid_geometry
                    color = self.app.options["geometry_plot_line"]

                    self.plot_element(solid_geometry, visible=visible, color=color)

            # self.plot_element(self.solid_geometry, visible=self.obj_options['plot'])

            self.shapes.redraw()

        except (ObjectDeleted, AttributeError):
            self.shapes.clear(update=True)

    def on_plot_cb_click(self):
        if self.muted_ui:
            return

        self.read_form_item('plot')
        self.plot()

        self.ui_disconnect()
        cb_flag = self.ui.plot_cb.isChecked()
        for row in range(self.ui.geo_tools_table.rowCount()):
            table_cb = self.ui.geo_tools_table.cellWidget(row, 6)
            if cb_flag:
                table_cb.setChecked(True)
            else:
                table_cb.setChecked(False)
        self.ui_connect()

    def on_plot_cb_click_table(self):
        # self.ui.cnc_tools_table.cellWidget(row, 2).widget().setCheckState(QtCore.Qt.Unchecked)
        self.ui_disconnect()
        # cw = self.sender()
        # cw_index = self.ui.geo_tools_table.indexAt(cw.pos())
        # cw_row = cw_index.row()
        check_row = 0

        self.shapes.clear(update=True)

        for tooluid_key in self.tools:
            solid_geometry = self.tools[tooluid_key]['solid_geometry']

            # find the geo_plugin_table row associated with the tooluid_key
            for row in range(self.ui.geo_tools_table.rowCount()):
                tooluid_item = int(self.ui.geo_tools_table.item(row, 5).text())
                if tooluid_item == int(tooluid_key):
                    check_row = row
                    break

            if self.ui.geo_tools_table.cellWidget(check_row, 6).isChecked():
                try:
                    color = self.tools[tooluid_key]['data']['override_color']
                    self.plot_element(element=solid_geometry, visible=True, color=color)
                except KeyError:
                    self.plot_element(element=solid_geometry, visible=True)
        self.shapes.redraw()

        # make sure that the general plot is disabled if one of the row plots are disabled and
        # if all the row plots are enabled also enable the general plot checkbox
        cb_cnt = 0
        total_row = self.ui.geo_tools_table.rowCount()
        for row in range(total_row):
            if self.ui.geo_tools_table.cellWidget(row, 6).isChecked():
                cb_cnt += 1
            else:
                cb_cnt -= 1
        if cb_cnt < total_row:
            self.ui.plot_cb.setChecked(False)
        else:
            self.ui.plot_cb.setChecked(True)
        self.ui_connect()

    def on_multicolored_cb_click(self):
        if self.muted_ui:
            return
        self.read_form_item('multicolored')
        self.plot()

    @staticmethod
    def merge(geo_list, geo_final, multi_geo=None, fuse_tools=None, log=None):
        """
        Merges the geometry of objects in grb_list into the geometry of geo_final.

        :param geo_list:    List of GerberObject Objects to join.
        :param geo_final:   Destination GerberObject object.
        :param multi_geo:   if the merged geometry objects are of type MultiGeo
        :param fuse_tools:  If True will try to fuse tools of the same type for the Geometry objects
        :param log:         A logging object
        :return: None
        """

        if geo_final.solid_geometry is None:
            geo_final.solid_geometry = []

        geo_final.solid_geometry = flatten_shapely_geometry(geo_final.solid_geometry)
        new_solid_geometry = []
        new_options = {}
        new_tools = {}

        for geo_obj in geo_list:
            for option in geo_obj.obj_options:
                if option != 'name':
                    try:
                        new_options[option] = deepcopy(geo_obj.obj_options[option])
                    except Exception as e:
                        if log:
                            log.error("Failed to copy option %s. Error: %s" % (str(option), str(e)))

            # Expand lists
            if type(geo_obj) is list:
                GeometryObject.merge(geo_list=geo_obj, geo_final=geo_final, log=log)
            # If not list, just append
            else:
                if multi_geo is None or multi_geo is False:
                    geo_final.multigeo = False
                else:
                    geo_final.multigeo = True

                try:
                    new_solid_geometry += deepcopy(geo_obj.solid_geometry.geoms)
                except Exception as e:
                    new_solid_geometry.append(geo_obj.solid_geometry)
                    if log:
                        log.error("GeometryObject.merge() --> %s" % str(e))

                # find the tool_uid maximum value in the geo_final
                try:
                    max_uid = max([int(i) for i in new_tools.keys()])
                except ValueError:
                    max_uid = 0

                # add and merge tools. If what we try to merge as Geometry is Excellon's and/or Gerber's then don't try
                # to merge the obj.tools as it is likely there is none to merge.
                if geo_obj.kind != 'gerber' and geo_obj.kind != 'excellon':
                    for tool_uid in geo_obj.tools:
                        max_uid += 1
                        new_tools[max_uid] = deepcopy(geo_obj.tools[tool_uid])

        geo_final.obj_options.update(new_options)
        geo_final.solid_geometry = new_solid_geometry

        if new_tools and fuse_tools is True:
            # merge the geometries of the tools that share the same tool diameter and the same tool_type
            # and the same type
            final_tools = {}
            same_dia = defaultdict(list)
            same_type = defaultdict(list)
            same_tool_type = defaultdict(list)

            # find tools that have the same diameter and group them by diameter
            for k, v in new_tools.items():
                same_dia[v['tooldia']].append(k)

            # find tools that have the same type (job) and group them by type
            for k, v in new_tools.items():
                same_type[v['data']['tools_mill_job_type']].append(k)

            # find tools that have the same tool_type and group them by tool_type
            for k, v in new_tools.items():
                same_tool_type[v['data']['tools_mill_tool_shape']].append(k)

            # find the intersections in the above groups
            intersect_list = []
            for dia, dia_list in same_dia.items():
                for ty, type_list in same_type.items():
                    for t_ty, tool_type_list in same_tool_type.items():
                        intersection = reduce(np.intersect1d, (dia_list, type_list, tool_type_list)).tolist()
                        # intersection = list(set(dia_list) & set(type_list) & set(tool_type_list))
                        if intersection:
                            intersect_list.append(intersection)

            new_tool_nr = 1
            for i_lst in intersect_list:
                new_solid_geo = []
                last_tool = None
                for old_tool in i_lst:
                    new_solid_geo += new_tools[old_tool]['solid_geometry']
                    last_tool = old_tool

                if new_solid_geo and last_tool:
                    final_tools[new_tool_nr] = \
                        {
                            k: deepcopy(new_tools[last_tool][k]) for k in new_tools[last_tool] if k != 'solid_geometry'
                        }
                    final_tools[new_tool_nr]['solid_geometry'] = deepcopy(new_solid_geo)
                    new_tool_nr += 1
        else:
            final_tools = new_tools

        # if not final_tools:
        #     return 'fail'
        geo_final.tools = final_tools

    @staticmethod
    def get_pts(o):
        """
        Returns a list of all points in the object, where
        the object can be a MultiPolygon, Polygon, Not a polygon, or a list
        of such. Search is done recursively.

        :param: geometric object
        :return: List of points
        :rtype: list
        """
        pts = []

        # Iterable: descend into each item.
        try:
            for sub_o in o:
                pts += GeometryObject.get_pts(sub_o)

        # Non-iterable
        except TypeError:
            if o is not None:
                if isinstance(o, MultiPolygon):
                    for poly in o.geoms:
                        pts += GeometryObject.get_pts(poly)
                # ## Descend into .exterior and .interiors
                elif isinstance(o, Polygon):
                    pts += GeometryObject.get_pts(o.exterior)
                    for i in o.interiors:
                        pts += GeometryObject.get_pts(i)
                elif isinstance(o, MultiLineString):
                    for line in o.geoms:
                        pts += GeometryObject.get_pts(line)
                # ## Has .coords: list them.
                else:
                    pts += list(o.coords)
            else:
                return
        return pts
