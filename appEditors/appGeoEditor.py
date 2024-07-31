# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
# ##########################################################

# ##########################################################
# File Modified: Marius Adrian Stanciu (c)                 #
# Date: 3/10/2019                                          #
# ##########################################################

from PyQt6 import QtGui, QtCore, QtWidgets
from PyQt6.QtCore import Qt
# import inspect
import math

from camlib import distance, arc, three_point_circle, Geometry, AppRTreeStorage, flatten_shapely_geometry
from appGUI.GUIElements import FCLabel, GLay, FCDoubleSpinner, FCTree, FCButton, FCFrame, FCCheckBox, FCEntry, \
    FCTextEdit
from appGUI.VisPyVisuals import ShapeCollection

from appEditors.geo_plugins.GeoBufferPlugin import BufferSelectionTool
from appEditors.geo_plugins.GeoPaintPlugin import PaintOptionsTool
from appEditors.geo_plugins.GeoTextPlugin import TextInputTool
from appEditors.geo_plugins.GeoTransformationPlugin import TransformEditorTool
from appEditors.geo_plugins.GeoPathPlugin import PathEditorTool
from appEditors.geo_plugins.GeoSimplificationPlugin import SimplificationTool
from appEditors.geo_plugins.GeoRectanglePlugin import RectangleEditorTool
from appEditors.geo_plugins.GeoCirclePlugin import CircleEditorTool
from appEditors.geo_plugins.GeoCopyPlugin import CopyEditorTool

from vispy.geometry import Rect

from shapely import LineString, LinearRing, MultiLineString, Polygon, MultiPolygon, Point, box
from shapely.geometry import base
from shapely.ops import unary_union, linemerge
from shapely.affinity import translate, scale, skew, rotate
from shapely.geometry.polygon import orient
from shapely.geometry.base import BaseGeometry

import numpy as np
from numpy.linalg import norm as numpy_norm
import logging

from rtree import index as rtindex

from copy import deepcopy
# from vispy.io import read_png

from typing import Union

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class AppGeoEditor(QtCore.QObject):
    # will emit the name of the object that was just selected

    item_selected = QtCore.pyqtSignal(str)

    transform_complete = QtCore.pyqtSignal()

    build_ui_sig = QtCore.pyqtSignal()
    clear_tree_sig = QtCore.pyqtSignal()

    draw_shape_idx = -1

    def __init__(self, app, disabled=False):
        # assert isinstance(app, FlatCAMApp.App), \
        #     "Expected the app to be a FlatCAMApp.App, got %s" % type(app)

        super(AppGeoEditor, self).__init__()

        self.app = app
        self.canvas = app.plotcanvas
        self.decimals = app.decimals
        self.units = self.app.app_units

        # #############################################################################################################
        # Geometry Editor UI
        # #############################################################################################################
        self.ui = AppGeoEditorUI(app=self.app)
        if disabled:
            self.ui.geo_frame.setDisabled(True)

        # when True the Editor can't do selection due of an ongoing process
        self.interdict_selection = False

        # ## Toolbar events and properties
        self.tools = {}

        # # ## Data
        self.active_tool = None

        self.storage = self.make_storage()
        self.utility = []

        # VisPy visuals
        self.fcgeometry = None
        if self.app.use_3d_engine:
            self.shapes = self.app.plotcanvas.new_shape_collection(layers=1)
            self.sel_shapes = self.app.plotcanvas.new_shape_collection(layers=1)
            self.tool_shape = self.app.plotcanvas.new_shape_collection(layers=1)
        else:
            from appGUI.PlotCanvasLegacy import ShapeCollectionLegacy
            self.shapes = ShapeCollectionLegacy(obj=self, app=self.app, name='shapes_geo_editor')
            self.sel_shapes = ShapeCollectionLegacy(obj=self, app=self.app, name='sel_shapes_geo_editor')
            self.tool_shape = ShapeCollectionLegacy(obj=self, app=self.app, name='tool_shapes_geo_editor')

        # Remove from scene
        self.shapes.enabled = False
        self.sel_shapes.enabled = False
        self.tool_shape.enabled = False

        # List of selected shapes.
        self.selected = []

        self.flat_geo = []

        self.move_timer = QtCore.QTimer()
        self.move_timer.setSingleShot(True)

        # this var will store the state of the toolbar before starting the editor
        self.toolbar_old_state = False

        self.key = None  # Currently, pressed key
        self.geo_key_modifiers = None
        self.x = None  # Current mouse cursor pos
        self.y = None

        # if we edit a multigeo geometry store here the tool number
        self.multigeo_tool = None

        # Current snapped mouse pos
        self.snap_x = None
        self.snap_y = None
        self.pos = None

        # signal that there is an action active like polygon or path
        self.in_action = False

        self.units = None

        # this will flag if the Editor "tools" are launched from key shortcuts (True) or from menu toolbar (False)
        self.launched_from_shortcuts = False

        self.editor_options = {
            "global_gridx": 0.1,
            "global_gridy": 0.1,
            "global_snap_max": 0.05,
            "grid_snap": True,
            "corner_snap": False,
            "grid_gap_link": True
        }
        self.editor_options.update(self.app.options)

        for option in self.editor_options:
            if option in self.app.options:
                self.editor_options[option] = self.app.options[option]

        self.app.ui.grid_gap_x_entry.setText(str(self.editor_options["global_gridx"]))
        self.app.ui.grid_gap_y_entry.setText(str(self.editor_options["global_gridy"]))
        self.app.ui.snap_max_dist_entry.setText(str(self.editor_options["global_snap_max"]))
        self.app.ui.grid_gap_link_cb.setChecked(True)

        self.rtree_index = rtindex.Index()

        self.app.ui.grid_gap_x_entry.setValidator(QtGui.QDoubleValidator())
        self.app.ui.grid_gap_y_entry.setValidator(QtGui.QDoubleValidator())
        self.app.ui.snap_max_dist_entry.setValidator(QtGui.QDoubleValidator())

        # if using Paint store here the tool diameter used
        self.paint_tooldia = None

        self.paint_tool = PaintOptionsTool(self.app, self)
        self.transform_tool = TransformEditorTool(self.app, self)

        # #############################################################################################################
        # ####################### GEOMETRY Editor Signals #############################################################
        # #############################################################################################################
        self.build_ui_sig.connect(self.build_ui)

        self.app.ui.grid_gap_x_entry.textChanged.connect(self.on_gridx_val_changed)
        self.app.ui.grid_gap_y_entry.textChanged.connect(self.on_gridy_val_changed)
        self.app.ui.snap_max_dist_entry.textChanged.connect(
            lambda: self.entry2option("snap_max", self.app.ui.snap_max_dist_entry))

        self.app.ui.grid_snap_btn.triggered.connect(lambda: self.on_grid_toggled())
        self.app.ui.corner_snap_btn.setCheckable(True)
        self.app.ui.corner_snap_btn.triggered.connect(lambda: self.toolbar_tool_toggle("corner_snap"))

        self.app.pool_recreated.connect(self.pool_recreated)

        # connect the toolbar signals
        self.connect_geo_toolbar_signals()

        # connect Geometry Editor Menu signals
        self.app.ui.geo_add_circle_menuitem.triggered.connect(lambda: self.select_tool('circle'))
        self.app.ui.geo_add_arc_menuitem.triggered.connect(lambda: self.select_tool('arc'))
        self.app.ui.geo_add_rectangle_menuitem.triggered.connect(lambda: self.select_tool('rectangle'))
        self.app.ui.geo_add_polygon_menuitem.triggered.connect(lambda: self.select_tool('polygon'))
        self.app.ui.geo_add_path_menuitem.triggered.connect(lambda: self.select_tool('path'))
        self.app.ui.geo_add_text_menuitem.triggered.connect(lambda: self.select_tool('text'))
        self.app.ui.geo_paint_menuitem.triggered.connect(lambda: self.select_tool("paint"))
        self.app.ui.geo_buffer_menuitem.triggered.connect(lambda: self.select_tool("buffer"))
        self.app.ui.geo_simplification_menuitem.triggered.connect(lambda: self.select_tool("simplification"))
        self.app.ui.geo_transform_menuitem.triggered.connect(self.transform_tool.run)

        self.app.ui.geo_delete_menuitem.triggered.connect(self.on_delete_btn)
        self.app.ui.geo_union_menuitem.triggered.connect(self.union)
        self.app.ui.geo_intersection_menuitem.triggered.connect(self.intersection)
        self.app.ui.geo_subtract_menuitem.triggered.connect(self.subtract)
        self.app.ui.geo_subtract_alt_menuitem.triggered.connect(self.subtract_2)

        self.app.ui.geo_cutpath_menuitem.triggered.connect(self.cutpath)
        self.app.ui.geo_copy_menuitem.triggered.connect(lambda: self.select_tool('copy'))

        self.app.ui.geo_union_btn.triggered.connect(self.union)
        self.app.ui.geo_intersection_btn.triggered.connect(self.intersection)
        self.app.ui.geo_subtract_btn.triggered.connect(self.subtract)
        self.app.ui.geo_alt_subtract_btn.triggered.connect(self.subtract_2)

        self.app.ui.geo_cutpath_btn.triggered.connect(self.cutpath)
        self.app.ui.geo_delete_btn.triggered.connect(self.on_delete_btn)

        self.app.ui.geo_move_menuitem.triggered.connect(self.on_move)
        self.app.ui.geo_cornersnap_menuitem.triggered.connect(self.on_corner_snap)

        self.transform_complete.connect(self.on_transform_complete)

        self.ui.change_orientation_btn.clicked.connect(self.on_change_orientation)

        self.ui.tw.customContextMenuRequested.connect(self.on_menu_request)

        self.clear_tree_sig.connect(self.on_clear_tree)

        # Event signals disconnect id holders
        self.mp = None
        self.mm = None
        self.mr = None

        self.app.log.debug("Initialization of the Geometry Editor is finished ...")

    def make_callback(self, thetool):
        def f():
            self.on_tool_select(thetool)

        return f

    def connect_geo_toolbar_signals(self):
        self.tools.update({
            "select": {"button": self.app.ui.geo_select_btn, "constructor": FCSelect},
            "arc": {"button": self.app.ui.geo_add_arc_btn, "constructor": FCArc},
            "circle": {"button": self.app.ui.geo_add_circle_btn, "constructor": FCCircle},
            "path": {"button": self.app.ui.geo_add_path_btn, "constructor": FCPath},
            "rectangle": {"button": self.app.ui.geo_add_rectangle_btn, "constructor": FCRectangle},
            "polygon": {"button": self.app.ui.geo_add_polygon_btn, "constructor": FCPolygon},
            "text": {"button": self.app.ui.geo_add_text_btn, "constructor": FCText},
            "buffer": {"button": self.app.ui.geo_add_buffer_btn, "constructor": FCBuffer},
            "simplification": {"button": self.app.ui.geo_add_simplification_btn, "constructor": FCSimplification},
            "paint": {"button": self.app.ui.geo_add_paint_btn, "constructor": FCPaint},
            "eraser": {"button": self.app.ui.geo_eraser_btn, "constructor": FCEraser},
            "move": {"button": self.app.ui.geo_move_btn, "constructor": FCMove},
            "transform": {"button": self.app.ui.geo_transform_btn, "constructor": FCTransform},
            "copy": {"button": self.app.ui.geo_copy_btn, "constructor": FCCopy},
            "explode": {"button": self.app.ui.geo_explode_btn, "constructor": FCExplode}
        })

        for tool in self.tools:
            self.tools[tool]["button"].triggered.connect(self.make_callback(tool))  # Events
            self.tools[tool]["button"].setCheckable(True)  # Checkable

    def pool_recreated(self, pool):
        self.shapes.pool = pool
        self.sel_shapes.pool = pool
        self.tool_shape.pool = pool

    def on_transform_complete(self):
        self.delete_selected()
        self.plot_all()

    def entry2option(self, opt, entry):
        """

        :param opt:     An option from the self.editor_options dictionary
        :param entry:   A GUI element which text value is used
        :return:
        """
        try:
            text_value = entry.text()
            if ',' in text_value:
                text_value = text_value.replace(',', '.')
            self.editor_options[opt] = float(text_value)
        except Exception as e:
            entry.set_value(self.app.options[opt])
            self.app.log.error("AppGeoEditor.__init__().entry2option() --> %s" % str(e))
            return

    def grid_changed(self, goption, gentry):
        """

        :param goption:     String. Can be either 'global_gridx' or 'global_gridy'
        :param gentry:      A GUI element which text value is read and used
        :return:
        """
        if goption not in ['global_gridx', 'global_gridy']:
            return

        self.entry2option(opt=goption, entry=gentry)
        # if the grid link is checked copy the value in the GridX field to GridY
        try:
            text_value = gentry.text()
            if ',' in text_value:
                text_value = text_value.replace(',', '.')
            val = float(text_value)
        except ValueError:
            return

        if self.app.ui.grid_gap_link_cb.isChecked():
            self.app.ui.grid_gap_y_entry.set_value(val, decimals=self.decimals)

    def on_gridx_val_changed(self):
        self.grid_changed("global_gridx", self.app.ui.grid_gap_x_entry)
        # try:
        #     self.app.options["global_gridx"] =  float(self.app.ui.grid_gap_x_entry.get_value())
        # except ValueError:
        #     return

    def on_gridy_val_changed(self):
        self.entry2option("global_gridy", self.app.ui.grid_gap_y_entry)

    def set_editor_ui(self):
        # updated units
        self.units = self.app.app_units.upper()
        self.decimals = self.app.decimals

        self.ui.geo_coords_entry.setText('')
        self.ui.is_ccw_entry.set_value('None')
        self.ui.is_ring_entry.set_value('None')
        self.ui.is_simple_entry.set_value('None')
        self.ui.is_empty_entry.set_value('None')
        self.ui.is_valid_entry.set_value('None')
        self.ui.geo_vertex_entry.set_value(0.0)
        self.ui.geo_zoom.set_value(False)

        self.ui.param_button.setChecked(self.app.options['geometry_editor_parameters'])

        # Remove anything else in the GUI Selected Tab
        self.app.ui.properties_scroll_area.takeWidget()
        # Put ourselves in the appGUI Properties Tab
        self.app.ui.properties_scroll_area.setWidget(self.ui.geo_edit_widget)
        # Switch notebook to Properties page
        self.app.ui.notebook.setCurrentWidget(self.app.ui.properties_tab)

        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.ui.change_level(app_mode)

    def build_ui(self):
        """
        Build the appGUI in the Properties Tab for this editor

        :return:
        """

        iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.geo_parent)
        to_delete = []
        while iterator.value():
            item = iterator.value()
            to_delete.append(item)
            iterator += 1
        for it in to_delete:
            self.ui.geo_parent.removeChild(it)
        # self.ui.tw.selectionModel().clearSelection()

        for elem in self.storage.get_objects():
            geo_type = type(elem.geo)

            if geo_type is MultiLineString:
                el_type = _('Multi-Line')
            elif geo_type is MultiPolygon:
                el_type = _('Multi-Polygon')
            else:
                el_type = elem.data['type']

            self.ui.tw.addParentEditable(
                self.ui.geo_parent,
                [
                    str(id(elem)),
                    '%s' % el_type,
                    _("Geo Elem")
                ],
                font=self.ui.geo_font,
                font_items=2,
                # color=QtGui.QColor("#FF0000"),
                editable=True
            )

        self.ui.tw.resize_sig.emit()

    def on_geo_elem_selected(self):
        pass

    def update_ui(self, current_item: QtWidgets.QTreeWidgetItem = None):
        self.selected = []
        last_obj_shape = None
        last_id = None

        if current_item:
            last_id = current_item.text(0)
            for obj_shape in self.storage.get_objects():
                try:
                    if id(obj_shape) == int(last_id):
                        # self.selected.append(obj_shape)
                        last_obj_shape = obj_shape
                except ValueError:
                    pass
        else:
            selected_tree_items = self.ui.tw.selectedItems()
            for sel in selected_tree_items:
                for obj_shape in self.storage.get_objects():
                    try:
                        if id(obj_shape) == int(sel.text(0)):
                            # self.selected.append(obj_shape)
                            last_obj_shape = obj_shape
                            last_id = sel.text(0)
                    except ValueError:
                        pass

        if last_obj_shape:
            last_sel_geo = last_obj_shape.geo

            self.ui.is_valid_entry.set_value(last_sel_geo.is_valid)
            self.ui.is_empty_entry.set_value(last_sel_geo.is_empty)

            if last_sel_geo.geom_type == 'MultiLineString':
                length = last_sel_geo.length
                self.ui.is_simple_entry.set_value(last_sel_geo.is_simple)
                self.ui.is_ring_entry.set_value(last_sel_geo.is_ring)
                self.ui.is_ccw_entry.set_value('None')

                coords = ''
                vertex_nr = 0
                for idx, line in enumerate(last_sel_geo.geoms):
                    line_coords = list(line.coords)
                    vertex_nr += len(line_coords)
                    coords += 'Line %s\n' % str(idx)
                    coords += str(line_coords) + '\n'
            elif last_sel_geo.geom_type == 'MultiPolygon':
                length = 0.0
                self.ui.is_simple_entry.set_value('None')
                self.ui.is_ring_entry.set_value('None')
                self.ui.is_ccw_entry.set_value('None')

                coords = ''
                vertex_nr = 0
                for idx, poly in enumerate(last_sel_geo.geoms):
                    poly_coords = list(poly.exterior.coords) + [list(i.coords) for i in poly.interiors]
                    vertex_nr += len(poly_coords)

                    coords += 'Polygon %s\n' % str(idx)
                    coords += str(poly_coords) + '\n'
            elif last_sel_geo.geom_type in ['LinearRing', 'LineString']:
                length = last_sel_geo.length
                coords = list(last_sel_geo.coords)
                vertex_nr = len(coords)
                self.ui.is_simple_entry.set_value(last_sel_geo.is_simple)
                self.ui.is_ring_entry.set_value(last_sel_geo.is_ring)
                if last_sel_geo.geom_type == 'LinearRing':
                    self.ui.is_ccw_entry.set_value(last_sel_geo.is_ccw)
            elif last_sel_geo.geom_type == 'Polygon':
                length = last_sel_geo.exterior.length
                coords = list(last_sel_geo.exterior.coords)
                vertex_nr = len(coords)
                self.ui.is_simple_entry.set_value(last_sel_geo.is_simple)
                self.ui.is_ring_entry.set_value(last_sel_geo.is_ring)
                if last_sel_geo.exterior.geom_type == 'LinearRing':
                    self.ui.is_ccw_entry.set_value(last_sel_geo.exterior.is_ccw)
            else:
                length = 0.0
                coords = 'None'
                vertex_nr = 0

            if self.ui.geo_zoom.get_value():
                xmin, ymin, xmax, ymax = last_sel_geo.bounds
                if xmin == xmax and ymin != ymax:
                    xmin = ymin
                    xmax = ymax
                elif xmin != xmax and ymin == ymax:
                    ymin = xmin
                    ymax = xmax

                if self.app.use_3d_engine:
                    rect = Rect(xmin, ymin, xmax, ymax)
                    rect.left, rect.right = xmin, xmax
                    rect.bottom, rect.top = ymin, ymax

                    # Lock updates in other threads
                    assert isinstance(self.shapes, ShapeCollection)
                    self.shapes.lock_updates()

                    assert isinstance(self.sel_shapes, ShapeCollection)
                    self.sel_shapes.lock_updates()

                    # adjust the view camera to be slightly bigger than the bounds so the shape collection can be
                    # seen clearly otherwise the shape collection boundary will have no border
                    dx = rect.right - rect.left
                    dy = rect.top - rect.bottom
                    x_factor = dx * 0.02
                    y_factor = dy * 0.02

                    rect.left -= x_factor
                    rect.bottom -= y_factor
                    rect.right += x_factor
                    rect.top += y_factor

                    self.app.plotcanvas.view.camera.rect = rect
                    self.shapes.unlock_updates()
                    self.sel_shapes.unlock_updates()
                else:
                    width = xmax - xmin
                    height = ymax - ymin
                    xmin -= 0.05 * width
                    xmax += 0.05 * width
                    ymin -= 0.05 * height
                    ymax += 0.05 * height
                    self.app.plotcanvas.adjust_axes(xmin, ymin, xmax, ymax)

            self.ui.geo_len_entry.set_value(length, decimals=self.decimals)
            self.ui.geo_coords_entry.setText(str(coords))
            self.ui.geo_vertex_entry.set_value(vertex_nr)

            self.app.inform.emit('%s: %s' % (_("Last selected shape ID"), str(last_id)))

    def on_tree_geo_click(self, current_item, prev_item):
        try:
            self.update_ui(current_item=current_item)
            # self.plot_all()
        except Exception as e:
            self.app.log.error("APpGeoEditor.on_tree_selection_change() -> %s" % str(e))

    def on_tree_selection(self):
        selected_items = self.ui.tw.selectedItems()

        if len(selected_items) == 0:
            self.ui.is_valid_entry.set_value("None")
            self.ui.is_empty_entry.set_value("None")
            self.ui.is_simple_entry.set_value("None")
            self.ui.is_ring_entry.set_value("None")
            self.ui.is_ccw_entry.set_value("None")
            self.ui.geo_len_entry.set_value("None")
            self.ui.geo_coords_entry.setText("None")
            self.ui.geo_vertex_entry.set_value("")

        if len(selected_items) >= 1:
            total_selected_shapes = []

            for sel in selected_items:
                for obj_shape in self.storage.get_objects():
                    try:
                        if id(obj_shape) == int(sel.text(0)):
                            total_selected_shapes.append(obj_shape)
                    except ValueError:
                        pass

            self.selected = total_selected_shapes
            self.plot_all()

            total_geos = flatten_shapely_geometry([s.geo for s in total_selected_shapes])
            total_vtx = 0
            for geo in total_geos:
                try:
                    total_vtx += len(geo.coords)
                except AttributeError:
                    pass
            self.ui.geo_all_vertex_entry.set_value(str(total_vtx))

    def on_change_orientation(self):
        self.app.log.debug("AppGeoEditor.on_change_orientation()")

        selected_tree_items = self.ui.tw.selectedItems()
        processed_shapes = []
        new_shapes = []

        def task_job():
            with self.app.proc_container.new('%s...' % _("Working")):
                for sel in selected_tree_items:
                    for obj_shape in self.storage.get_objects():
                        try:
                            if id(obj_shape) == int(sel.text(0)):
                                old_geo = obj_shape.geo
                                if old_geo.geom_type == 'LineaRing':
                                    processed_shapes.append(obj_shape)
                                    new_shapes.append(LinearRing(list(old_geo.coords)[::-1]))
                                elif old_geo.geom_type == 'LineString':
                                    processed_shapes.append(obj_shape)
                                    new_shapes.append(LineString(list(old_geo.coords)[::-1]))
                                elif old_geo.geom_type == 'Polygon':
                                    processed_shapes.append(obj_shape)
                                    if old_geo.exterior.is_ccw is True:
                                        new_shapes.append(deepcopy(orient(old_geo, -1)))
                                    else:
                                        new_shapes.append(deepcopy(orient(old_geo, 1)))
                        except ValueError:
                            pass

                self.delete_shape(processed_shapes)

                for geo in new_shapes:
                    self.add_shape(DrawToolShape(geo), build_ui=False)

                self.build_ui_sig.emit()

        self.app.worker_task.emit({'fcn': task_job, 'params': []})

    def on_menu_request(self, pos):
        menu = QtWidgets.QMenu()

        delete_action = menu.addAction(QtGui.QIcon(self.app.resource_location + '/delete32.png'), _("Delete"))
        delete_action.triggered.connect(self.delete_selected)

        menu.addSeparator()

        orientation_change = menu.addAction(QtGui.QIcon(self.app.resource_location + '/orientation32.png'),
                                            _("Change"))
        orientation_change.triggered.connect(self.on_change_orientation)

        if not self.ui.tw.selectedItems():
            delete_action.setDisabled(True)
            orientation_change.setDisabled(True)

        menu.exec(self.ui.tw.viewport().mapToGlobal(pos))

    def activate(self):
        # adjust the status of the menu entries related to the editor
        self.app.ui.menueditedit.setDisabled(True)
        self.app.ui.menueditok.setDisabled(False)

        # adjust the visibility of some of the canvas context menu
        self.app.ui.popmenu_edit.setVisible(False)
        self.app.ui.popmenu_save.setVisible(True)

        self.connect_canvas_event_handlers()

        # initialize working objects
        self.storage = self.make_storage()
        self.utility = []
        self.selected = []

        self.shapes.enabled = True
        self.sel_shapes.enabled = True
        self.tool_shape.enabled = True
        self.app.app_cursor.enabled = True

        self.app.ui.corner_snap_btn.setVisible(True)
        self.app.ui.snap_magnet.setVisible(True)

        self.app.ui.geo_editor_menu.setDisabled(False)
        self.app.ui.geo_editor_menu.menuAction().setVisible(True)

        self.app.ui.editor_exit_btn_ret_action.setVisible(True)
        self.app.ui.editor_start_btn.setVisible(False)
        self.app.ui.g_editor_cmenu.setEnabled(True)

        self.app.ui.geo_edit_toolbar.setDisabled(False)
        self.app.ui.geo_edit_toolbar.setVisible(True)

        self.app.ui.status_toolbar.setDisabled(False)

        self.app.ui.pop_menucolor.menuAction().setVisible(False)
        self.app.ui.popmenu_numeric_move.setVisible(False)
        self.app.ui.popmenu_move2origin.setVisible(False)

        self.app.ui.popmenu_disable.setVisible(False)
        self.app.ui.cmenu_newmenu.menuAction().setVisible(False)
        self.app.ui.popmenu_properties.setVisible(False)
        self.app.ui.g_editor_cmenu.menuAction().setVisible(True)

        # prevent the user to change anything in the Properties Tab while the Geo Editor is active
        # sel_tab_widget_list = self.app.ui.properties_tab.findChildren(QtWidgets.QWidget)
        # for w in sel_tab_widget_list:
        #     w.setEnabled(False)

        self.item_selected.connect(self.on_geo_elem_selected)

        # ## appGUI Events
        self.ui.tw.currentItemChanged.connect(self.on_tree_geo_click)
        self.ui.tw.itemSelectionChanged.connect(self.on_tree_selection)

        # self.ui.tw.keyPressed.connect(self.app.ui.keyPressEvent)
        # self.ui.tw.customContextMenuRequested.connect(self.on_menu_request)

        self.ui.geo_frame.show()

        self.app.log.debug("Finished activating the Geometry Editor...")

    def deactivate(self):
        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        # adjust the status of the menu entries related to the editor
        self.app.ui.menueditedit.setDisabled(False)
        self.app.ui.menueditok.setDisabled(True)

        # adjust the visibility of some of the canvas context menu
        self.app.ui.popmenu_edit.setVisible(True)
        self.app.ui.popmenu_save.setVisible(False)

        self.disconnect_canvas_event_handlers()
        self.storage = self.make_storage()

        self.clear()
        self.app.ui.geo_edit_toolbar.setDisabled(True)

        self.app.ui.corner_snap_btn.setVisible(False)
        self.app.ui.snap_magnet.setVisible(False)

        # set the Editor Toolbar visibility to what was before entering the Editor
        self.app.ui.geo_edit_toolbar.setVisible(False) if self.toolbar_old_state is False \
            else self.app.ui.geo_edit_toolbar.setVisible(True)

        # Disable visuals
        self.shapes.enabled = False
        self.sel_shapes.enabled = False
        self.tool_shape.enabled = False

        # disable text cursor (for FCPath)
        if self.app.use_3d_engine:
            self.app.plotcanvas.text_cursor.parent = None
            self.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        self.app.ui.geo_editor_menu.setDisabled(True)
        self.app.ui.geo_editor_menu.menuAction().setVisible(False)

        self.app.ui.editor_exit_btn_ret_action.setVisible(False)
        self.app.ui.editor_start_btn.setVisible(True)

        self.app.ui.g_editor_cmenu.setEnabled(False)
        self.app.ui.e_editor_cmenu.setEnabled(False)

        self.app.ui.pop_menucolor.menuAction().setVisible(True)
        self.app.ui.popmenu_numeric_move.setVisible(True)
        self.app.ui.popmenu_move2origin.setVisible(True)

        self.app.ui.popmenu_disable.setVisible(True)
        self.app.ui.cmenu_newmenu.menuAction().setVisible(True)
        self.app.ui.popmenu_properties.setVisible(True)
        self.app.ui.grb_editor_cmenu.menuAction().setVisible(False)
        self.app.ui.e_editor_cmenu.menuAction().setVisible(False)
        self.app.ui.g_editor_cmenu.menuAction().setVisible(False)

        try:
            self.item_selected.disconnect()
        except (AttributeError, TypeError, RuntimeError):
            pass

        try:
            # ## appGUI Events
            self.ui.tw.currentItemChanged.disconnect(self.on_tree_geo_click)
            # self.ui.tw.keyPressed.connect(self.app.ui.keyPressEvent)
            # self.ui.tw.customContextMenuRequested.connect(self.on_menu_request)
        except (AttributeError, TypeError, RuntimeError):
            pass

        try:
            self.ui.tw.itemSelectionChanged.disconnect(self.on_tree_selection)
        except (AttributeError, TypeError, RuntimeError):
            pass

        # try:
        #     # re-enable all the widgets in the Selected Tab that were disabled after entering in Edit Geometry Mode
        #     sel_tab_widget_list = self.app.ui.properties_tab.findChildren(QtWidgets.QWidget)
        #     for w in sel_tab_widget_list:
        #         w.setEnabled(True)
        # except Exception as e:
        #     self.app.log.error("AppGeoEditor.deactivate() --> %s" % str(e))

        # Show original geometry
        try:
            if self.fcgeometry:
                self.fcgeometry.visible = True

            # clear the Tree
            self.clear_tree_sig.emit()
        except Exception as err:
            self.app.log.error("AppGeoEditor.deactivate() --> %s" % str(err))

        # hide the UI
        self.ui.geo_frame.hide()

        self.app.log.debug("Finished deactivating the Geometry Editor...")

    def connect_canvas_event_handlers(self):
        # Canvas events

        # first connect to new, then disconnect the old handlers
        # don't ask why but if there is nothing connected I've seen issues
        self.mp = self.canvas.graph_event_connect('mouse_press', self.on_canvas_click)
        self.mm = self.canvas.graph_event_connect('mouse_move', self.on_canvas_move)
        self.mr = self.canvas.graph_event_connect('mouse_release', self.on_canvas_click_release)

        if self.app.use_3d_engine:
            # make sure that the shortcuts key and mouse events will no longer be linked to the methods from FlatCAMApp
            # but those from AppGeoEditor
            self.app.plotcanvas.graph_event_disconnect('mouse_press', self.app.on_mouse_click_over_plot)
            self.app.plotcanvas.graph_event_disconnect('mouse_move', self.app.on_mouse_move_over_plot)
            self.app.plotcanvas.graph_event_disconnect('mouse_release', self.app.on_mouse_click_release_over_plot)
            self.app.plotcanvas.graph_event_disconnect('mouse_double_click', self.app.on_mouse_double_click_over_plot)
        else:

            self.app.plotcanvas.graph_event_disconnect(self.app.mp)
            self.app.plotcanvas.graph_event_disconnect(self.app.mm)
            self.app.plotcanvas.graph_event_disconnect(self.app.mr)
            self.app.plotcanvas.graph_event_disconnect(self.app.mdc)

        # self.app.collection.view.clicked.disconnect()
        self.app.ui.popmenu_copy.triggered.disconnect()
        self.app.ui.popmenu_delete.triggered.disconnect()
        self.app.ui.popmenu_move.triggered.disconnect()

        self.app.ui.popmenu_copy.triggered.connect(lambda: self.select_tool('copy'))
        self.app.ui.popmenu_delete.triggered.connect(self.on_delete_btn)
        self.app.ui.popmenu_move.triggered.connect(lambda: self.select_tool('move'))

        # Geometry Editor
        self.app.ui.draw_line.triggered.connect(self.draw_tool_path)
        self.app.ui.draw_rect.triggered.connect(self.draw_tool_rectangle)

        self.app.ui.draw_circle.triggered.connect(lambda: self.select_tool('circle'))
        self.app.ui.draw_poly.triggered.connect(lambda: self.select_tool('polygon'))
        self.app.ui.draw_arc.triggered.connect(lambda: self.select_tool('arc'))

        self.app.ui.draw_text.triggered.connect(lambda: self.select_tool('text'))
        self.app.ui.draw_simplification.triggered.connect(lambda: self.select_tool('simplification'))
        self.app.ui.draw_buffer.triggered.connect(lambda: self.select_tool('buffer'))
        self.app.ui.draw_paint.triggered.connect(lambda: self.select_tool('paint'))
        self.app.ui.draw_eraser.triggered.connect(lambda: self.select_tool('eraser'))

        self.app.ui.draw_union.triggered.connect(self.union)
        self.app.ui.draw_intersect.triggered.connect(self.intersection)
        self.app.ui.draw_substract.triggered.connect(self.subtract)
        self.app.ui.draw_substract_alt.triggered.connect(self.subtract_2)

        self.app.ui.draw_cut.triggered.connect(self.cutpath)
        self.app.ui.draw_transform.triggered.connect(lambda: self.select_tool('transform'))

        self.app.ui.draw_move.triggered.connect(self.on_move)

    def disconnect_canvas_event_handlers(self):
        # we restore the key and mouse control to FlatCAMApp method
        # first connect to new, then disconnect the old handlers
        # don't ask why but if there is nothing connected I've seen issues
        self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press', self.app.on_mouse_click_over_plot)
        self.app.mm = self.app.plotcanvas.graph_event_connect('mouse_move', self.app.on_mouse_move_over_plot)
        self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                              self.app.on_mouse_click_release_over_plot)
        self.app.mdc = self.app.plotcanvas.graph_event_connect('mouse_double_click',
                                                               self.app.on_mouse_double_click_over_plot)
        # self.app.collection.view.clicked.connect(self.app.collection.on_mouse_down)

        if self.app.use_3d_engine:
            self.canvas.graph_event_disconnect('mouse_press', self.on_canvas_click)
            self.canvas.graph_event_disconnect('mouse_move', self.on_canvas_move)
            self.canvas.graph_event_disconnect('mouse_release', self.on_canvas_click_release)
        else:
            self.canvas.graph_event_disconnect(self.mp)
            self.canvas.graph_event_disconnect(self.mm)
            self.canvas.graph_event_disconnect(self.mr)

        try:
            self.app.ui.popmenu_copy.triggered.disconnect()
        except (TypeError, AttributeError):
            pass
        try:
            self.app.ui.popmenu_delete.triggered.disconnect()
        except (TypeError, AttributeError):
            pass
        try:
            self.app.ui.popmenu_move.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        self.app.ui.popmenu_copy.triggered.connect(self.app.on_copy_command)
        self.app.ui.popmenu_delete.triggered.connect(self.app.on_delete)
        self.app.ui.popmenu_move.triggered.connect(self.app.obj_move)

        # Geometry Editor
        try:
            self.app.ui.draw_line.triggered.disconnect(self.draw_tool_path)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_rect.triggered.disconnect(self.draw_tool_rectangle)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_cut.triggered.disconnect(self.cutpath)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_move.triggered.disconnect(self.on_move)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_circle.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_poly.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_arc.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_text.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_simplification.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_buffer.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_paint.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_eraser.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_union.triggered.disconnect(self.union)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_intersect.triggered.disconnect(self.intersection)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_substract.triggered.disconnect(self.subtract)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_substract_alt.triggered.disconnect(self.subtract_2)
        except (TypeError, AttributeError):
            pass

        try:
            self.app.ui.draw_transform.triggered.disconnect()
        except (TypeError, AttributeError):
            pass

        try:
            self.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass

    def on_clear_tree(self):
        self.ui.tw.clearSelection()
        self.ui.tw.clear()
        self.ui.geo_parent = self.ui.tw.invisibleRootItem()

    def add_shape(self, shape, build_ui=True):
        """
        Adds a shape to the shape storage.

        :param shape:       Shape to be added.
        :type shape:        DrawToolShape, list
        :param build_ui:    If to trigger a build of the UI
        :type build_ui:     bool
        :return:            None
        """
        ret = []

        if shape is None:
            return

        # List of DrawToolShape?
        # if isinstance(shape, list):
        #     for subshape in shape:
        #         self.add_shape(subshape)
        #     return

        try:
            w_geo = shape.geoms if isinstance(shape, (MultiPolygon, MultiLineString)) else shape
            for subshape in w_geo:
                ret_shape = self.add_shape(subshape)
                ret.append(ret_shape)
            return
        except TypeError:
            pass

        if not isinstance(shape, DrawToolShape):
            shape = DrawToolShape(shape)
            ret.append(shape)

        # assert isinstance(shape, DrawToolShape), "Expected a DrawToolShape, got %s" % type(shape)
        assert shape.geo is not None, "Shape object has empty geometry (None)"
        assert (isinstance(shape.geo, list) and len(shape.geo) > 0) or not isinstance(shape.geo, list), \
            "Shape objects has empty geometry ([])"

        if isinstance(shape, DrawToolUtilityShape):
            self.utility.append(shape)
        else:
            geometry = shape.geo
            if geometry and geometry.is_valid and not geometry.is_empty and geometry.geom_type != 'Point':
                try:
                    self.storage.insert(shape)
                except Exception as err:
                    self.app.inform_shell.emit('%s\n%s' % (_("Error on inserting shapes into storage."), str(err)))
                if build_ui is True:
                    self.build_ui_sig.emit()  # Build UI

        return ret

    def delete_utility_geometry(self):
        """
        Will delete the shapes in the utility shapes storage.

        :return:    None
        """

        # for_deletion = [shape for shape in self.shape_buffer if shape.utility]
        # for_deletion = [shape for shape in self.storage.get_objects() if shape.utility]
        for_deletion = [shape for shape in self.utility]
        for shape in for_deletion:
            self.delete_shape(shape)

        self.tool_shape.clear(update=True)
        self.tool_shape.redraw()

    def toolbar_tool_toggle(self, key):
        """
        It is used as a slot by the Snap buttons.

        :param key:     Key in the self.editor_options dictionary that is to be updated
        :return:        Boolean. Status of the checkbox that toggled the Editor Tool
        """
        cb_widget = self.sender()
        assert isinstance(cb_widget, QtGui.QAction), "Expected a QAction got %s" % type(cb_widget)
        self.editor_options[key] = cb_widget.isChecked()

        return 1 if self.editor_options[key] is True else 0

    def clear(self):
        """
        Will clear the storage for the Editor shapes, the selected shapes storage and plot_all. Clean up method.

        :return:    None
        """
        self.active_tool = None
        # self.shape_buffer = []
        self.selected = []
        self.shapes.clear(update=True)
        self.sel_shapes.clear(update=True)
        self.tool_shape.clear(update=True)

        # self.storage = AppGeoEditor.make_storage()
        self.plot_all()

    def on_tool_select(self, tool):
        """
        Behavior of the toolbar. Tool initialization.

        :rtype : None
        """
        self.app.log.debug("on_tool_select('%s')" % tool)

        # This is to make the group behave as radio group
        if tool in self.tools:
            if self.tools[tool]["button"].isChecked():
                self.app.log.debug("%s is checked." % tool)
                for t in self.tools:
                    if t != tool:
                        self.tools[t]["button"].setChecked(False)

                self.active_tool = self.tools[tool]["constructor"](self)
            else:
                self.app.log.debug("%s is NOT checked." % tool)
                for t in self.tools:
                    self.tools[t]["button"].setChecked(False)

                self.select_tool('select')
                self.active_tool = FCSelect(self)

    def draw_tool_path(self):
        self.select_tool('path')
        return

    def draw_tool_rectangle(self):
        self.select_tool('rectangle')
        return

    def on_grid_toggled(self):
        self.toolbar_tool_toggle("grid_snap")

        # make sure that the cursor shape is enabled/disabled, too
        if self.editor_options['grid_snap'] is True:
            self.app.options['global_grid_snap'] = True
            self.app.inform[str, bool].emit(_("Grid Snap enabled."), False)
            self.app.app_cursor.enabled = True
        else:
            self.app.options['global_grid_snap'] = False
            self.app.inform[str, bool].emit(_("Grid Snap disabled."), False)
            self.app.app_cursor.enabled = False

    def on_canvas_click(self, event):
        """
        event.x and .y have canvas coordinates
        event.xdaya and .ydata have plot coordinates

        :param event: Event object dispatched by Matplotlib
        :return: None
        """
        if self.app.use_3d_engine:
            event_pos = event.pos
        else:
            event_pos = (event.xdata, event.ydata)

        self.pos = self.canvas.translate_coords(event_pos)

        if self.app.grid_status():
            self.pos = self.app.geo_editor.snap(self.pos[0], self.pos[1])
        else:
            self.pos = (self.pos[0], self.pos[1])

        if event.button == 1:
            self.app.ui.rel_position_label.setText("<b>Dx</b>: %.4f&nbsp;&nbsp;  <b>Dy</b>: "
                                                   "%.4f&nbsp;&nbsp;&nbsp;&nbsp;" % (0, 0))

            # update mouse position with the clicked position
            self.snap_x = self.pos[0]
            self.snap_y = self.pos[1]

            modifiers = QtWidgets.QApplication.keyboardModifiers()
            # If the SHIFT key is pressed when LMB is clicked then the coordinates are copied to clipboard
            if modifiers == QtCore.Qt.KeyboardModifier.ShiftModifier:
                if self.active_tool is not None \
                        and self.active_tool.name != 'rectangle' \
                        and self.active_tool.name != 'path':
                    self.app.clipboard.setText(
                        self.app.options["global_point_clipboard_format"] %
                        (self.decimals, self.pos[0], self.decimals, self.pos[1])
                    )
                    return

            # Selection with left mouse button
            if self.active_tool is not None:

                # Dispatch event to active_tool
                self.active_tool.click(self.snap(self.pos[0], self.pos[1]))

                # If it is a shape generating tool
                if isinstance(self.active_tool, FCShapeTool) and self.active_tool.complete:
                    self.on_shape_complete()

                    if isinstance(self.active_tool, (FCText, FCMove)):
                        self.select_tool("select")
                    else:
                        self.select_tool(self.active_tool.name)
            else:
                self.app.log.debug("No active tool to respond to click!")

    def on_canvas_click_release(self, event):
        if self.app.use_3d_engine:
            event_pos = event.pos
            # event_is_dragging = event.is_dragging
            right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            # event_is_dragging = self.app.plotcanvas.is_dragging
            right_button = 3

        pos_canvas = self.canvas.translate_coords(event_pos)

        if self.app.grid_status():
            pos = self.snap(pos_canvas[0], pos_canvas[1])
        else:
            pos = (pos_canvas[0], pos_canvas[1])

        # if the released mouse button was RMB then test if it was a panning motion or not, if not it was a context
        # canvas menu
        try:
            # if the released mouse button was LMB then test if we had a right-to-left selection or a left-to-right
            # selection and then select a type of selection ("enclosing" or "touching")
            if event.button == 1:  # left click
                if self.app.selection_type is not None:
                    self.draw_selection_area_handler(self.pos, pos, self.app.selection_type)
                    self.app.selection_type = None
                elif isinstance(self.active_tool, FCSelect):
                    # Dispatch event to active_tool
                    # msg = self.active_tool.click(self.snap(event.xdata, event.ydata))
                    self.active_tool.click_release((self.pos[0], self.pos[1]))
                    # self.app.inform.emit(msg)
                    self.plot_all()
            elif event.button == right_button:  # right click
                if self.app.ui.popMenu.mouse_is_panning is False:
                    if self.in_action is False:
                        try:
                            QtGui.QGuiApplication.restoreOverrideCursor()
                        except Exception:
                            pass

                        if self.active_tool.complete is False and not isinstance(self.active_tool, FCSelect):
                            self.active_tool.complete = True
                            self.in_action = False
                            self.delete_utility_geometry()
                            self.active_tool.clean_up()
                            self.app.inform.emit('[success] %s' % _("Done."))
                            self.select_tool('select')
                        else:
                            self.app.cursor = QtGui.QCursor()
                            self.app.populate_cmenu_grids()
                            self.app.ui.popMenu.popup(self.app.cursor.pos())
                    else:
                        # if right click on canvas and the active tool need to be finished (like Path or Polygon)
                        # right mouse click will finish the action
                        if isinstance(self.active_tool, FCShapeTool):
                            self.active_tool.click(self.snap(self.x, self.y))
                            self.active_tool.make()
                            if self.active_tool.complete:
                                self.on_shape_complete()
                                self.app.inform.emit('[success] %s' % _("Done."))
                                self.select_tool(self.active_tool.name)
        except Exception as e:
            self.app.log.error("FLatCAMGeoEditor.on_canvas_click_release() --> Error: %s" % str(e))
            return

    def on_canvas_move(self, event):
        """
        Called on 'mouse_move' event.
        "event.pos" have canvas screen coordinates

        :param event: Event object dispatched by VisPy SceneCavas
        :return: None
        """
        if self.app.use_3d_engine:
            event_pos = event.pos
            event_is_dragging = event.is_dragging
            right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            event_is_dragging = self.app.plotcanvas.is_dragging
            right_button = 3

        pos = self.canvas.translate_coords(event_pos)
        event.xdata, event.ydata = pos[0], pos[1]

        self.x = event.xdata
        self.y = event.ydata

        self.app.ui.popMenu.mouse_is_panning = False

        # if the RMB is clicked and mouse is moving over plot then 'panning_action' is True
        if event.button == right_button:
            if event_is_dragging:
                self.app.ui.popMenu.mouse_is_panning = True
                # return
            else:
                self.app.ui.popMenu.mouse_is_panning = False

        if self.active_tool is None:
            return

        try:
            x = float(event.xdata)
            y = float(event.ydata)
        except TypeError:
            return

        # ### Snap coordinates ###
        if self.app.grid_status():
            x, y = self.snap(x, y)

            # Update cursor
            self.app.app_cursor.set_data(np.asarray([(x, y)]), symbol='++', edge_color=self.app.plotcanvas.cursor_color,
                                         edge_width=self.app.options["global_cursor_width"],
                                         size=self.app.options["global_cursor_size"])

        self.snap_x = x
        self.snap_y = y
        self.app.mouse_pos = [x, y]

        if self.pos is None:
            self.pos = (0, 0)
        self.app.dx = x - self.pos[0]
        self.app.dy = y - self.pos[1]

        # # update the position label in the infobar since the APP mouse event handlers are disconnected
        # self.app.ui.position_label.setText("&nbsp;<b>X</b>: %.4f&nbsp;&nbsp;   "
        #                                    "<b>Y</b>: %.4f&nbsp;" % (x, y))
        # #
        # # # update the reference position label in the infobar since the APP mouse event handlers are disconnected
        # self.app.ui.rel_position_label.setText("<b>Dx</b>: %.4f&nbsp;&nbsp;  <b>Dy</b>: "
        #                                        "%.4f&nbsp;&nbsp;&nbsp;&nbsp;" % (self.app.dx, self.app.dy))

        if self.active_tool.name == 'path':
            modifier = QtWidgets.QApplication.keyboardModifiers()
            if modifier == Qt.KeyboardModifier.ShiftModifier:
                cl_x = self.active_tool.close_x
                cl_y = self.active_tool.close_y
                shift_dx = cl_x - self.pos[0]
                shift_dy = cl_y - self.pos[1]
                self.app.ui.update_location_labels(shift_dx, shift_dy, cl_x, cl_y)
            else:
                self.app.ui.update_location_labels(self.app.dx, self.app.dy, x, y)
        else:
            self.app.ui.update_location_labels(self.app.dx, self.app.dy, x, y)

        # units = self.app.app_units.lower()
        # self.app.plotcanvas.text_hud.text = \
        #     'Dx:\t{:<.4f} [{:s}]\nDy:\t{:<.4f} [{:s}]\n\nX:  \t{:<.4f} [{:s}]\nY:  \t{:<.4f} [{:s}]'.format(
        #         self.app.dx, units, self.app.dy, units, x, units, y, units)
        self.app.plotcanvas.on_update_text_hud(self.app.dx, self.app.dy, x, y)

        if event.button == 1 and event_is_dragging and isinstance(self.active_tool, FCEraser):
            pass
        else:
            self.update_utility_geometry(data=(x, y))
            if self.active_tool.name in ['path', 'polygon', 'move', 'circle', 'arc', 'rectangle', 'copy']:
                try:
                    self.active_tool.draw_cursor_data(pos=(x, y))
                except AttributeError:
                    # this can happen if the method is not implemented yet for the active_tool
                    pass

        # ### Selection area on canvas section ###
        dx = pos[0] - self.pos[0]
        if event_is_dragging and event.button == 1:
            self.app.delete_selection_shape()
            if dx < 0:
                self.app.draw_moving_selection_shape((self.pos[0], self.pos[1]), (x, y),
                                                     color=self.app.options["global_alt_sel_line"],
                                                     face_color=self.app.options['global_alt_sel_fill'])
                self.app.selection_type = False
            else:
                self.app.draw_moving_selection_shape((self.pos[0], self.pos[1]), (x, y))
                self.app.selection_type = True
        else:
            self.app.selection_type = None

    def update_utility_geometry(self, data):
        # ### Utility geometry (animated) ###
        geo = self.active_tool.utility_geometry(data=data)
        if isinstance(geo, DrawToolShape) and geo.geo is not None:
            # Remove any previous utility shape
            self.tool_shape.clear(update=True)
            self.draw_utility_geometry(geo=geo)

    def draw_selection_area_handler(self, start_pos, end_pos, sel_type):
        """

        :param start_pos: mouse position when the selection LMB click was done
        :param end_pos: mouse position when the left mouse button is released
        :param sel_type: if True it's a left to right selection (enclosure), if False it's a 'touch' selection
        :return:
        """
        poly_selection = Polygon([start_pos, (end_pos[0], start_pos[1]), end_pos, (start_pos[0], end_pos[1])])

        key_modifier = QtWidgets.QApplication.keyboardModifiers()

        if key_modifier == QtCore.Qt.KeyboardModifier.ShiftModifier:
            mod_key = 'Shift'
        elif key_modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
            mod_key = 'Control'
        else:
            mod_key = None

        self.app.delete_selection_shape()

        sel_objects_list = []
        for obj in self.storage.get_objects():
            if (sel_type is True and poly_selection.contains(obj.geo)) or (sel_type is False and
                                                                           poly_selection.intersects(obj.geo)):
                sel_objects_list.append(obj)

        if mod_key == self.app.options["global_mselect_key"]:
            for obj in sel_objects_list:
                if obj in self.selected:
                    self.selected.remove(obj)
                else:
                    # add the object to the selected shapes
                    self.selected.append(obj)
        else:
            self.selected = []
            self.selected = sel_objects_list

        # #############################################################################################################
        # #########  if selection is done on canvas update the Tree in Selected Tab with the selection  ###############
        # #############################################################################################################
        try:
            self.ui.tw.currentItemChanged.disconnect(self.on_tree_geo_click)
        except (AttributeError, TypeError):
            pass

        self.ui.tw.selectionModel().clearSelection()
        for sel_shape in self.selected:
            iterator = QtWidgets.QTreeWidgetItemIterator(self.ui.tw)
            while iterator.value():
                item = iterator.value()
                try:
                    if int(item.text(0)) == id(sel_shape):
                        item.setSelected(True)
                except ValueError:
                    pass

                iterator += 1

        # #############################################################################################################
        # ###################  calculate vertex numbers for all selected shapes  ######################################
        # #############################################################################################################
        vertex_nr = 0
        for sha in sel_objects_list:
            sha_geo_solid = sha.geo
            if sha_geo_solid.geom_type == 'Polygon':
                sha_geo_solid_coords = list(sha_geo_solid.exterior.coords)
            elif sha_geo_solid.geom_type in ['LinearRing', 'LineString']:
                sha_geo_solid_coords = list(sha_geo_solid.coords)
            else:
                sha_geo_solid_coords = []

            vertex_nr += len(sha_geo_solid_coords)

        self.ui.geo_vertex_entry.set_value(vertex_nr)

        self.ui.tw.currentItemChanged.connect(self.on_tree_geo_click)

        self.plot_all()

    def draw_utility_geometry(self, geo):
        # Add the new utility shape
        try:
            # this case is for the Font Parse
            w_geo = list(geo.geo.geoms) if isinstance(geo.geo, (MultiPolygon, MultiLineString)) else list(geo.geo)
            for el in w_geo:
                if type(el) == MultiPolygon:
                    for poly in el.geoms:
                        self.tool_shape.add(
                            shape=poly,
                            color=self.get_draw_color(),
                            update=False,
                            layer=0,
                            tolerance=None
                        )
                elif type(el) == MultiLineString:
                    for linestring in el.geoms:
                        self.tool_shape.add(
                            shape=linestring,
                            color=self.get_draw_color(),
                            update=False,
                            layer=0,
                            tolerance=None
                        )
                else:
                    self.tool_shape.add(
                        shape=el,
                        color=(self.get_draw_color()),
                        update=False,
                        layer=0,
                        tolerance=None
                    )
        except TypeError:
            self.tool_shape.add(
                shape=geo.geo, color=self.get_draw_color(),
                update=False, layer=0, tolerance=None)
        except AttributeError:
            pass

        self.tool_shape.redraw()

    def get_draw_color(self):
        orig_color = self.app.options["global_draw_color"]

        if self.app.options['global_theme'] in ['default', 'light']:
            return orig_color

        # in the "dark" theme we invert the color
        lowered_color = orig_color.lower()
        group1 = "#0123456789abcdef"
        group2 = "#fedcba9876543210"
        # create color dict
        color_dict = {group1[i]: group2[i] for i in range(len(group1))}
        new_color = ''.join([color_dict[j] for j in lowered_color])
        return new_color

    def get_sel_color(self):
        return self.app.options['global_sel_draw_color']

    def on_delete_btn(self):
        self.delete_selected()
        # self.plot_all()

    def delete_selected(self):
        self.delete_shape(self.selected)

        self.build_ui()
        self.plot_all()

        self.selected.clear()
        self.sel_shapes.clear(update=True)
        self.sel_shapes.redraw()

    def delete_shape(self, shapes):
        """
        Deletes shape(shapes) from the storage, selection and utility
        """
        w_shapes = [shapes] if not isinstance(shapes, list) else shapes

        for shape in w_shapes:
            # remove from Utility
            if shape in self.utility:
                self.utility.remove(shape)

        for shape in w_shapes:
            # remove from Selection
            if shape in self.selected:
                self.selected.remove(shape)

        for shape in w_shapes:
            # remove from Storage
            self.storage.remove(shape)

    def on_move(self):
        # if not self.selected:
        #     self.app.inform.emit(_("[WARNING_NOTCL] Move cancelled. No shape selected."))
        #     return
        self.app.ui.geo_move_btn.setChecked(True)
        self.on_tool_select('move')

    def on_move_click(self):
        try:
            x, y = self.snap(self.x, self.y)
        except TypeError:
            return
        self.on_move()
        self.active_tool.set_origin((x, y))

    def on_copy_click(self):
        if not self.selected:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Cancelled."), _("No shape selected.")))
            return

        self.app.ui.geo_copy_btn.setChecked(True)
        self.app.geo_editor.on_tool_select('copy')
        self.app.geo_editor.active_tool.set_origin(self.app.geo_editor.snap(
            self.app.geo_editor.x, self.app.geo_editor.y))
        self.app.inform.emit(_("Click on target point."))

    def on_corner_snap(self):
        self.app.ui.corner_snap_btn.trigger()

    def get_selected(self):
        """
        Returns list of shapes that are selected in the editor.

        :return: List of shapes.
        """
        # return [shape for shape in self.shape_buffer if shape["selected"]]
        return self.selected

    def plot_shape(self, storage, geometry=None, color='#000000FF', linewidth=1, layer=0):
        """
        Plots a geometric object or list of objects without rendering. Plotted objects
        are returned as a list. This allows for efficient/animated rendering.

        :param geometry:    Geometry to be plotted (Any "Shapely.geom" kind or list of such)
        :param color:       Shape color
        :param linewidth:   Width of lines in # of pixels.
        :return:            List of plotted elements.
        """
        plot_elements = []
        if geometry is None:
            geometry = self.active_tool.geometry

        try:
            w_geo = geometry.geoms if isinstance(geometry, (MultiPolygon, MultiLineString)) else geometry
            for geo in w_geo:
                plot_elements += self.plot_shape(geometry=geo, color=color, linewidth=linewidth)
        # Non-iterable
        except TypeError:

            # DrawToolShape
            if isinstance(geometry, DrawToolShape):
                plot_elements += self.plot_shape(geometry=geometry.geo, color=color, linewidth=linewidth)

            # Polygon: Descend into exterior and each interior.
            # if isinstance(geometry, Polygon):
            #     plot_elements += self.plot_shape(geometry=geometry.exterior, color=color, linewidth=linewidth)
            #     plot_elements += self.plot_shape(geometry=geometry.interiors, color=color, linewidth=linewidth)

            if isinstance(geometry, Polygon):
                plot_elements.append(storage.add(shape=geometry, color=color, face_color=color[:-2] + '50',
                                                 layer=layer, tolerance=self.fcgeometry.drawing_tolerance,
                                                 linewidth=linewidth))
            if isinstance(geometry, (LineString, LinearRing)):
                plot_elements.append(storage.add(shape=geometry, color=color, layer=layer,
                                                 tolerance=self.fcgeometry.drawing_tolerance, linewidth=linewidth))

            if type(geometry) == Point:
                pass

        return plot_elements

    def plot_all(self):
        """
        Plots all shapes in the editor.

        :return: None
        """
        # self.app.log.debug(str(inspect.stack()[1][3]) + " --> AppGeoEditor.plot_all()")

        orig_draw_color = self.get_draw_color()
        draw_color = orig_draw_color[:-2] + "FF"
        orig_sel_color = self.get_sel_color()
        sel_color = orig_sel_color[:-2] + 'FF'

        geo_drawn = []
        geos_selected = []

        for shape in self.storage.get_objects():
            if shape.geo and not shape.geo.is_empty and shape.geo.is_valid:
                if shape in self.get_selected():
                    geos_selected.append(shape.geo)
                else:
                    geo_drawn.append(shape.geo)

        if geo_drawn:
            self.shapes.clear(update=True)

            for geo in geo_drawn:
                self.plot_shape(storage=self.shapes, geometry=geo, color=draw_color, linewidth=1)

            for shape in self.utility:
                self.plot_shape(storage=self.shapes, geometry=shape.geo, linewidth=1)

            self.shapes.redraw()

        if geos_selected:
            self.sel_shapes.clear(update=True)
            for geo in geos_selected:
                self.plot_shape(storage=self.sel_shapes, geometry=geo, color=sel_color, linewidth=3)
            self.sel_shapes.redraw()

    def on_shape_complete(self):
        self.app.log.debug("on_shape_complete()")

        geom_list = []
        try:
            for shape in self.active_tool.geometry:
                geom_list.append(shape)
        except TypeError:
            geom_list = [self.active_tool.geometry]

        if self.app.options['geometry_editor_milling_type'] == 'cl':
            # reverse the geometry coordinates direction to allow creation of Gcode for climb milling
            try:
                for shp in geom_list:
                    p = shp.geo
                    if p is not None:
                        if isinstance(p, Polygon):
                            shp.geo = Polygon(p.exterior.coords[::-1], p.interiors)
                        elif isinstance(p, LinearRing):
                            shp.geo = LinearRing(p.coords[::-1])
                        elif isinstance(p, LineString):
                            shp.geo = LineString(p.coords[::-1])
                        elif isinstance(p, MultiLineString):
                            new_line = []
                            for line in p.geoms:
                                new_line.append(LineString(line.coords[::-1]))
                            shp.geo = MultiLineString(new_line)
                        elif isinstance(p, MultiPolygon):
                            new_poly = []
                            for poly in p.geoms:
                                new_poly.append(Polygon(poly.exterior.coords[::-1], poly.interiors))
                            shp.geo = MultiPolygon(new_poly)
                        else:
                            self.app.log.debug("AppGeoEditor.on_shape_complete() Error --> Unexpected Geometry %s" %
                                               type(p))
            except Exception as e:
                self.app.log.error("AppGeoEditor.on_shape_complete() Error --> %s" % str(e))
                return 'fail'

        # Add shape

        self.add_shape(geom_list)

        # Remove any utility shapes
        self.delete_utility_geometry()
        self.tool_shape.clear(update=True)

        # Re-plot and reset tool.
        self.plot_all()
        # self.active_tool = type(self.active_tool)(self)

    @staticmethod
    def make_storage():

        # Shape storage.
        storage = AppRTreeStorage()
        storage.get_points = DrawToolShape.get_pts

        return storage

    def select_tool(self, pluginName):
        """
        Selects a drawing tool. Impacts the object and appGUI.

        :param pluginName: Name of the tool.
        :return: None
        """
        self.tools[pluginName]["button"].setChecked(True)
        self.on_tool_select(pluginName)

    def set_selected(self, shape):

        # Remove and add to the end.
        if shape in self.selected:
            self.selected.remove(shape)

        self.selected.append(shape)

    def set_unselected(self, shape):
        if shape in self.selected:
            self.selected.remove(shape)

    def snap(self, x, y):
        """
        Adjusts coordinates to snap settings.

        :param x: Input coordinate X
        :param y: Input coordinate Y
        :return: Snapped (x, y)
        """

        snap_x, snap_y = (x, y)
        snap_distance = np.Inf

        # # ## Object (corner?) snap
        # # ## No need for the objects, just the coordinates
        # # ## in the index.
        if self.editor_options["corner_snap"]:
            try:
                nearest_pt, shape = self.storage.nearest((x, y))

                nearest_pt_distance = distance((x, y), nearest_pt)
                if nearest_pt_distance <= float(self.editor_options["global_snap_max"]):
                    snap_distance = nearest_pt_distance
                    snap_x, snap_y = nearest_pt
            except (StopIteration, AssertionError):
                pass

        # # ## Grid snap
        if self.editor_options["grid_snap"]:
            if self.editor_options["global_gridx"] != 0:
                try:
                    snap_x_ = round(
                        x / float(self.editor_options["global_gridx"])) * float(self.editor_options['global_gridx'])
                except TypeError:
                    snap_x_ = x
            else:
                snap_x_ = x

            # If the Grid_gap_linked on Grid Toolbar is checked then the snap distance on GridY entry will be ignored,
            # and it will use the snap distance from GridX entry
            if self.app.ui.grid_gap_link_cb.isChecked():
                if self.editor_options["global_gridx"] != 0:
                    try:
                        snap_y_ = round(
                            y / float(self.editor_options["global_gridx"])) * float(self.editor_options['global_gridx'])
                    except TypeError:
                        snap_y_ = y
                else:
                    snap_y_ = y
            else:
                if self.editor_options["global_gridy"] != 0:
                    try:
                        snap_y_ = round(
                            y / float(self.editor_options["global_gridy"])) * float(self.editor_options['global_gridy'])
                    except TypeError:
                        snap_y_ = y
                else:
                    snap_y_ = y
            nearest_grid_distance = distance((x, y), (snap_x_, snap_y_))
            if nearest_grid_distance < snap_distance:
                snap_x, snap_y = (snap_x_, snap_y_)

        return snap_x, snap_y

    def edit_geometry(self, fcgeometry, multigeo_tool=None):
        """
        Imports the geometry from the given FlatCAM Geometry object
        into the editor.

        :param fcgeometry:      GeometryObject
        :param multigeo_tool:   A tool for the case of the edited geometry being of type 'multigeo'
        :return:                None
        """
        assert isinstance(fcgeometry, Geometry), "Expected a Geometry, got %s" % type(fcgeometry)

        self.deactivate()
        self.activate()

        self.set_editor_ui()

        self.units = self.app.app_units

        # Hide original geometry
        self.fcgeometry = fcgeometry
        fcgeometry.visible = False

        # Set selection tolerance
        DrawToolShape.tolerance = fcgeometry.drawing_tolerance * 10

        self.select_tool("select")

        if self.app.options['tools_mill_spindledir'] == 'CW':
            if self.app.options['geometry_editor_milling_type'] == 'cl':
                milling_type = 1  # CCW motion = climb milling (spindle is rotating CW)
            else:
                milling_type = -1  # CW motion = conventional milling (spindle is rotating CW)
        else:
            if self.app.options['geometry_editor_milling_type'] == 'cl':
                milling_type = -1  # CCW motion = climb milling (spindle is rotating CCW)
            else:
                milling_type = 1  # CW motion = conventional milling (spindle is rotating CCW)

        self.multigeo_tool = multigeo_tool

        def worker_job(editor_obj):
            # Link shapes into editor.
            with editor_obj.app.proc_container.new(_("Working...")):
                editor_obj.app.inform.emit(_("Loading the Geometry into the Editor..."))

                if self.multigeo_tool:
                    editor_obj.multigeo_tool = self.multigeo_tool
                    geo_to_edit = editor_obj.flatten(geometry=fcgeometry.tools[self.multigeo_tool]['solid_geometry'],
                                                     orient_val=milling_type)
                else:
                    geo_to_edit = editor_obj.flatten(geometry=fcgeometry.solid_geometry, orient_val=milling_type)

                # ####################################################################################################
                # remove the invalid geometry and also the Points as those are not relevant for the Editor
                # ####################################################################################################
                geo_to_edit = flatten_shapely_geometry(geo_to_edit)
                cleaned_geo = [g for g in geo_to_edit if g and not g.is_empty and g.is_valid and g.geom_type != 'Point']

                for shape in cleaned_geo:
                    if shape.geom_type == 'Polygon':
                        editor_obj.add_shape(DrawToolShape(shape.exterior), build_ui=False)
                        for inter in shape.interiors:
                            editor_obj.add_shape(DrawToolShape(inter), build_ui=False)
                    else:
                        editor_obj.add_shape(DrawToolShape(shape), build_ui=False)

                editor_obj.plot_all()

                # updated units
                editor_obj.units = self.app.app_units.upper()
                editor_obj.decimals = self.app.decimals

                # start with GRID toolbar activated
                if editor_obj.app.ui.grid_snap_btn.isChecked() is False:
                    editor_obj.app.ui.grid_snap_btn.trigger()

                # trigger a build of the UI
                self.build_ui_sig.emit()

                if multigeo_tool:
                    editor_obj.app.inform.emit(
                        '[WARNING_NOTCL] %s: %s %s: %s' % (
                            _("Editing MultiGeo Geometry, tool"),
                            str(self.multigeo_tool),
                            _("with diameter"),
                            str(fcgeometry.tools[self.multigeo_tool]['tooldia'])
                        )
                    )
                    self.ui.tooldia_entry.set_value(
                        float(fcgeometry.tools[self.multigeo_tool]['data']['tools_mill_tooldia']))
                else:
                    self.ui.tooldia_entry.set_value(float(fcgeometry.obj_options['tools_mill_tooldia']))

        self.app.worker_task.emit({'fcn': worker_job, 'params': [self]})

    def update_editor_geometry(self, fcgeometry):
        """
        Transfers the geometry tool shape buffer to the selected geometry
        object. The geometry already in the object are removed.

        :param fcgeometry:  GeometryObject
        :return:            None
        """

        def worker_job(editor_obj):
            # Link shapes into editor.
            with editor_obj.app.proc_container.new(_("Working...")):
                if editor_obj.multigeo_tool:
                    edited_dia = float(fcgeometry.tools[self.multigeo_tool]['tooldia'])
                    new_dia = self.ui.tooldia_entry.get_value()

                    if new_dia != edited_dia:
                        fcgeometry.tools[self.multigeo_tool]['tooldia'] = new_dia
                        fcgeometry.tools[self.multigeo_tool]['data']['tools_mill_tooldia'] = new_dia

                    tool_geo = []
                    # for shape in self.shape_buffer:
                    for shape in editor_obj.storage.get_objects():
                        new_geo = shape.geo

                        # simplify the MultiLineString
                        if isinstance(new_geo, MultiLineString):
                            new_geo = linemerge(new_geo)

                        tool_geo.append(new_geo)
                    fcgeometry.tools[self.multigeo_tool]['solid_geometry'] = flatten_shapely_geometry(tool_geo)
                    editor_obj.multigeo_tool = None
                else:
                    edited_dia = float(fcgeometry.obj_options['tools_mill_tooldia'])
                    new_dia = self.ui.tooldia_entry.get_value()

                    if new_dia != edited_dia:
                        fcgeometry.obj_options['tools_mill_tooldia'] = new_dia

                new_solid_geometry = []
                # for shape in self.shape_buffer:
                for shape in editor_obj.storage.get_objects():
                    new_geo = shape.geo

                    # simplify the MultiLineString
                    if isinstance(new_geo, MultiLineString):
                        new_geo = linemerge(new_geo)
                    new_solid_geometry.append(new_geo)
                fcgeometry.solid_geometry = flatten_shapely_geometry(new_solid_geometry)

                try:
                    bounds = fcgeometry.bounds()
                    fcgeometry.obj_options['xmin'] = bounds[0]
                    fcgeometry.obj_options['ymin'] = bounds[1]
                    fcgeometry.obj_options['xmax'] = bounds[2]
                    fcgeometry.obj_options['ymax'] = bounds[3]
                except Exception:
                    pass

                self.deactivate()
                editor_obj.app.inform.emit(_("Editor Exit. Geometry object was updated ..."))

        self.app.worker_task.emit({'fcn': worker_job, 'params': [self]})

    def update_options(self, obj):
        if self.paint_tooldia:
            obj.obj_options['tools_mill_tooldia'] = deepcopy(str(self.paint_tooldia))
            self.paint_tooldia = None
            return True
        else:
            return False

    def union(self):
        """
        Makes union of selected polygons. Original polygons
        are deleted.

        :return: None.
        """

        def work_task(editor_self):
            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()

                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                results = unary_union([t.geo for t in selected])
                if results.geom_type == 'MultiLineString':
                    results = linemerge(results)

                # Delete originals.
                for_deletion = [s for s in selected]
                for shape in for_deletion:
                    editor_self.delete_shape(shape)

                # Selected geometry is now gone!
                editor_self.selected = []

                editor_self.add_shape(DrawToolShape(results))
                editor_self.plot_all()
                editor_self.build_ui_sig.emit()
                editor_self.app.inform.emit('[success] %s' % _("Done."))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def intersection_2(self):
        """
        Makes intersection of selected polygons. Original polygons are deleted.

        :return: None
        """

        def work_task(editor_self):
            editor_self.app.log.debug("AppGeoEditor.intersection_2()")

            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()

                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                target = deepcopy(selected[0].geo)
                if target.is_ring:
                    target = Polygon(target)
                tools = selected[1:]
                # toolgeo = unary_union([deepcopy(shp.geo) for shp in tools]).buffer(0.0000001)
                # result = DrawToolShape(target.difference(toolgeo))
                for tool in tools:
                    if tool.geo.is_ring:
                        intersector_geo = Polygon(tool.geo)
                    target = target.difference(intersector_geo)

                if target.geom_type in ['LineString', 'MultiLineString']:
                    target = linemerge(target)

                if target.geom_type == 'Polygon':
                    target = target.exterior

                result = DrawToolShape(target)
                editor_self.add_shape(deepcopy(result))

                # Delete originals.
                for_deletion = [s for s in editor_self.get_selected()]
                for shape_el in for_deletion:
                    editor_self.delete_shape(shape_el)

                # Selected geometry is now gone!
                editor_self.selected = []

                editor_self.plot_all()
                editor_self.build_ui_sig.emit()
                editor_self.app.inform.emit('[success] %s' % _("Done."))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def intersection(self):
        """
        Makes intersection of selected polygons. Original polygons are deleted.

        :return: None
        """

        def work_task(editor_self):
            editor_self.app.log.debug("AppGeoEditor.intersection()")

            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()
                results = []
                intact = []

                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                intersector = selected[0].geo
                if intersector.is_ring:
                    intersector = Polygon(intersector)
                tools = selected[1:]
                for tool in tools:
                    if tool.geo.is_ring:
                        intersected = Polygon(tool.geo)
                    else:
                        intersected = tool.geo
                    if intersector.intersects(intersected):
                        results.append(intersector.intersection(intersected))
                    else:
                        intact.append(tool)

                if results:
                    # Delete originals.
                    for_deletion = [s for s in editor_self.get_selected()]
                    for shape_el in for_deletion:
                        if shape_el not in intact:
                            editor_self.delete_shape(shape_el)

                    for geo in results:
                        if geo.geom_type == 'MultiPolygon':
                            for poly in geo.geoms:
                                p_geo = [poly.exterior] + [ints for ints in poly.interiors]
                                for g in p_geo:
                                    editor_self.add_shape(DrawToolShape(g))
                        elif geo.geom_type == 'Polygon':
                            p_geo = [geo.exterior] + [ints for ints in geo.interiors]
                            for g in p_geo:
                                editor_self.add_shape(DrawToolShape(g))
                        else:
                            editor_self.add_shape(DrawToolShape(geo))

                # Selected geometry is now gone!
                editor_self.selected = []
                editor_self.plot_all()
                editor_self.build_ui_sig.emit()
                editor_self.app.inform.emit('[success] %s' % _("Done."))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def subtract(self):
        def work_task(editor_self):
            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()
                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                try:
                    target = deepcopy(selected[0].geo)
                    tools = selected[1:]
                    # toolgeo = unary_union([deepcopy(shp.geo) for shp in tools]).buffer(0.0000001)
                    # result = DrawToolShape(target.difference(toolgeo))
                    for tool in tools:
                        if tool.geo.is_ring:
                            sub_geo = Polygon(tool.geo)
                        target = target.difference(sub_geo)
                    result = DrawToolShape(target)
                    editor_self.add_shape(deepcopy(result))

                    for_deletion = [s for s in editor_self.get_selected()]
                    for shape in for_deletion:
                        self.delete_shape(shape)

                    editor_self.plot_all()
                    editor_self.build_ui_sig.emit()
                    editor_self.app.inform.emit('[success] %s' % _("Done."))
                except Exception as e:
                    editor_self.app.log.error(str(e))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def subtract_2(self):
        def work_task(editor_self):
            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()
                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                try:
                    target = deepcopy(selected[0].geo)
                    tools = selected[1:]
                    # toolgeo = unary_union([shp.geo for shp in tools]).buffer(0.0000001)
                    for tool in tools:
                        if tool.geo.is_ring:
                            sub_geo = Polygon(tool.geo)
                        target = target.difference(sub_geo)
                    result = DrawToolShape(target)
                    editor_self.add_shape(deepcopy(result))

                    editor_self.delete_shape(selected[0])

                    editor_self.plot_all()
                    editor_self.build_ui_sig.emit()
                    editor_self.app.inform.emit('[success] %s' % _("Done."))
                except Exception as e:
                    editor_self.app.log.error(str(e))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def cutpath(self):
        def work_task(editor_self):
            with editor_self.app.proc_container.new(_("Working...")):
                selected = editor_self.get_selected()
                if len(selected) < 2:
                    editor_self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                _("A selection of minimum two items is required."))
                    editor_self.select_tool('select')
                    return

                tools = selected[1:]
                toolgeo = unary_union([shp.geo for shp in tools])

                target = selected[0]
                if type(target.geo) == Polygon:
                    for ring in poly2rings(target.geo):
                        editor_self.add_shape(DrawToolShape(ring.difference(toolgeo)))
                elif type(target.geo) == LineString or type(target.geo) == LinearRing:
                    editor_self.add_shape(DrawToolShape(target.geo.difference(toolgeo)))
                elif type(target.geo) == MultiLineString:
                    try:
                        for linestring in target.geo:
                            editor_self.add_shape(DrawToolShape(linestring.difference(toolgeo)))
                    except Exception as e:
                        editor_self.app.log.error("Current LinearString does not intersect the target. %s" % str(e))
                else:
                    editor_self.app.log.warning("Not implemented. Object type: %s" % str(type(target.geo)))
                    return

                editor_self.delete_shape(target)
                editor_self.plot_all()
                editor_self.build_ui_sig.emit()
                editor_self.app.inform.emit('[success] %s' % _("Done."))

        self.app.worker_task.emit({'fcn': work_task, 'params': [self]})

    def flatten(self, geometry, orient_val=1, reset=True, pathonly=False):
        """
        Creates a list of non-iterable linear geometry objects.
        Polygons are expanded into its exterior and interiors if specified.

        Results are placed in self.flat_geometry

        :param geometry: Shapely type or a list or a list of lists of such.
        :param orient_val: will orient the exterior coordinates CW if 1 and CCW for else (whatever else means ...)
        https://shapely.readthedocs.io/en/stable/manual.html#polygons
        :param reset: Clears the contents of self.flat_geometry.
        :param pathonly: Expands polygons into linear elements.
        """

        if reset:
            self.flat_geo = []

        # ## If iterable, expand recursively.
        try:
            if isinstance(geometry, (MultiPolygon, MultiLineString)):
                work_geo = geometry.geoms
            else:
                work_geo = geometry

            for geo in work_geo:
                if geo is not None:
                    self.flatten(geometry=geo,
                                 orient_val=orient_val,
                                 reset=False,
                                 pathonly=pathonly)

        # ## Not iterable, do the actual indexing and add.
        except TypeError:
            if type(geometry) == Polygon:
                geometry = orient(geometry, orient_val)

            if pathonly and type(geometry) == Polygon:
                self.flat_geo.append(geometry.exterior)
                self.flatten(geometry=geometry.interiors,
                             reset=False,
                             pathonly=True)
            else:
                self.flat_geo.append(geometry)

        return self.flat_geo


class AppGeoEditorUI:
    def __init__(self, app):
        self.app = app
        self.decimals = self.app.decimals
        self.units = self.app.app_units.upper()

        self.geo_edit_widget = QtWidgets.QWidget()
        # ## Box for custom widgets
        # This gets populated in offspring implementations.
        layout = QtWidgets.QVBoxLayout()
        self.geo_edit_widget.setLayout(layout)

        # add a frame and inside add a vertical box layout. Inside this vbox layout I add all the Drills widgets
        # this way I can hide/show the frame
        self.geo_frame = QtWidgets.QFrame()
        self.geo_frame.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.geo_frame)
        self.tools_box = QtWidgets.QVBoxLayout()
        self.tools_box.setContentsMargins(0, 0, 0, 0)
        self.geo_frame.setLayout(self.tools_box)

        # ## Page Title box (spacing between children)
        self.title_box = QtWidgets.QHBoxLayout()
        self.tools_box.addLayout(self.title_box)

        # ## Page Title icon
        pixmap = QtGui.QPixmap(self.app.resource_location + '/app32.png')
        self.icon = FCLabel()
        self.icon.setPixmap(pixmap)
        self.title_box.addWidget(self.icon, stretch=0)

        # ## Title label
        self.title_label = FCLabel("<font size=5><b>%s</b></font>" % _('Geometry Editor'))
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.title_box.addWidget(self.title_label, stretch=1)

        # App Level label
        self.level = QtWidgets.QToolButton()
        self.level.setToolTip(
            _(
                "Beginner Mode - many parameters are hidden.\n"
                "Advanced Mode - full control.\n"
                "Permanent change is done in 'Preferences' menu."
            )
        )
        # self.level.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.level.setCheckable(True)
        self.title_box.addWidget(self.level)

        dia_grid = GLay(v_spacing=5, h_spacing=3)
        self.tools_box.addLayout(dia_grid)

        # Tool diameter
        tooldia_lbl = FCLabel('%s:' % _("Tool dia"), bold=True)
        tooldia_lbl.setToolTip(
            _("Edited tool diameter.")
        )
        self.tooldia_entry = FCDoubleSpinner()
        self.tooldia_entry.set_precision(self.decimals)
        self.tooldia_entry.setSingleStep(10 ** -self.decimals)
        self.tooldia_entry.set_range(-10000.0000, 10000.0000)

        dia_grid.addWidget(tooldia_lbl, 0, 0)
        dia_grid.addWidget(self.tooldia_entry, 0, 1)

        # #############################################################################################################
        # Tree Widget Frame
        # #############################################################################################################
        # Tree Widget Title
        tw_label = FCLabel('%s' % _("Geometry Table"), bold=True, color='green')
        tw_label.setToolTip(
            _("The list of geometry elements inside the edited object.")
        )
        self.tools_box.addWidget(tw_label)

        tw_frame = FCFrame()
        self.tools_box.addWidget(tw_frame)

        # Grid Layout
        tw_grid = GLay(v_spacing=5, h_spacing=3)
        tw_frame.setLayout(tw_grid)

        # Tree Widget
        self.tw = FCTree(columns=3, header_hidden=False, protected_column=[0, 1], extended_sel=True)
        self.tw.setHeaderLabels(["ID", _("Type"), _("Name")])
        self.tw.setIndentation(0)
        self.tw.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tw.header().setStretchLastSection(True)
        self.tw.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        tw_grid.addWidget(self.tw, 0, 0, 1, 2)

        self.geo_font = QtGui.QFont()
        self.geo_font.setBold(True)
        self.geo_parent = self.tw.invisibleRootItem()

        # #############################################################################################################
        # ############################################ Advanced Editor ################################################
        # #############################################################################################################
        self.adv_frame = QtWidgets.QFrame()
        self.adv_frame.setContentsMargins(0, 0, 0, 0)
        self.tools_box.addWidget(self.adv_frame)

        grid0 = GLay(v_spacing=5, h_spacing=3)
        grid0.setContentsMargins(0, 0, 0, 0)
        self.adv_frame.setLayout(grid0)

        # Zoom Selection
        self.geo_zoom = FCCheckBox(_("Zoom on selection"))
        grid0.addWidget(self.geo_zoom, 0, 0, 1, 2)

        # Parameters Title
        self.param_button = FCButton('%s' % _("Parameters"), checkable=True, color='blue', bold=True,
                                     click_callback=self.on_param_click)
        self.param_button.setToolTip(
            _("Geometry parameters.")
        )
        grid0.addWidget(self.param_button, 2, 0, 1, 2)

        # #############################################################################################################
        # ############################################ Parameter Frame ################################################
        # #############################################################################################################
        self.par_frame = FCFrame()
        grid0.addWidget(self.par_frame, 6, 0, 1, 2)

        par_grid = GLay(v_spacing=5, h_spacing=3)
        self.par_frame.setLayout(par_grid)

        # Is Valid
        is_valid_lbl = FCLabel('%s' % _("Is Valid"), bold=True)
        self.is_valid_entry = FCLabel('None')

        par_grid.addWidget(is_valid_lbl, 0, 0)
        par_grid.addWidget(self.is_valid_entry, 0, 1, 1, 2)

        # Is Empty
        is_empty_lbl = FCLabel('%s' % _("Is Empty"), bold=True)
        self.is_empty_entry = FCLabel('None')

        par_grid.addWidget(is_empty_lbl, 2, 0)
        par_grid.addWidget(self.is_empty_entry, 2, 1, 1, 2)

        # Is Ring
        is_ring_lbl = FCLabel('%s' % _("Is Ring"), bold=True)
        self.is_ring_entry = FCLabel('None')

        par_grid.addWidget(is_ring_lbl, 4, 0)
        par_grid.addWidget(self.is_ring_entry, 4, 1, 1, 2)

        # Is CCW
        is_ccw_lbl = FCLabel('%s' % _("Is CCW"), bold=True)
        self.is_ccw_entry = FCLabel('None')
        self.change_orientation_btn = FCButton(_("Change"))
        self.change_orientation_btn.setIcon(QtGui.QIcon(self.app.resource_location + '/orientation32.png'))
        self.change_orientation_btn.setToolTip(
            _("Change the orientation of the geometric element.\n"
              "Works for LinearRing and Polygons.")
        )
        par_grid.addWidget(is_ccw_lbl, 6, 0)
        par_grid.addWidget(self.is_ccw_entry, 6, 1)
        par_grid.addWidget(self.change_orientation_btn, 6, 2)

        # Is Simple
        is_simple_lbl = FCLabel('%s' % _("Is Simple"), bold=True)
        self.is_simple_entry = FCLabel('None')

        par_grid.addWidget(is_simple_lbl, 8, 0)
        par_grid.addWidget(self.is_simple_entry, 8, 1, 1, 2)

        # Length
        len_lbl = FCLabel('%s' % _("Length"), bold=True)
        len_lbl.setToolTip(
            _("The length of the geometry element.")
        )
        self.geo_len_entry = FCEntry(decimals=self.decimals)
        self.geo_len_entry.setReadOnly(True)

        par_grid.addWidget(len_lbl, 10, 0)
        par_grid.addWidget(self.geo_len_entry, 10, 1, 1, 2)

        # #############################################################################################################
        # Coordinates Frame
        # #############################################################################################################
        # Coordinates
        coords_lbl = FCLabel('%s' % _("Coordinates"), bold=True, color='red')
        coords_lbl.setToolTip(
            _("The coordinates of the selected geometry element.")
        )
        self.tools_box.addWidget(coords_lbl)

        c_frame = FCFrame()
        self.tools_box.addWidget(c_frame)

        # Grid Layout
        coords_grid = GLay(v_spacing=5, h_spacing=3)
        c_frame.setLayout(coords_grid)

        self.geo_coords_entry = FCTextEdit()
        self.geo_coords_entry.setPlaceholderText(
            _("The coordinates of the selected geometry element.")
        )
        coords_grid.addWidget(self.geo_coords_entry, 0, 0, 1, 2)

        # Grid Layout
        v_grid = GLay(v_spacing=5, h_spacing=3)
        self.tools_box.addLayout(v_grid)

        # Vertex Points Number
        vertex_lbl = FCLabel('%s' % _("Last Vertexes"), bold=True)
        vertex_lbl.setToolTip(
            _("The number of vertex points in the last selected geometry element.")
        )
        self.geo_vertex_entry = FCEntry(decimals=self.decimals)
        self.geo_vertex_entry.setReadOnly(True)

        v_grid.addWidget(vertex_lbl, 0, 0)
        v_grid.addWidget(self.geo_vertex_entry, 0, 1)

        # All selected Vertex Points Number
        vertex_all_lbl = FCLabel('%s' % _("Selected Vertexes"), bold=True)
        vertex_all_lbl.setToolTip(
            _("The number of vertex points in all selected geometry elements.")
        )
        self.geo_all_vertex_entry = FCEntry(decimals=self.decimals)
        self.geo_all_vertex_entry.setReadOnly(True)

        v_grid.addWidget(vertex_all_lbl, 2, 0)
        v_grid.addWidget(self.geo_all_vertex_entry, 2, 1)

        GLay.set_common_column_size([grid0, v_grid, tw_grid, coords_grid, dia_grid, par_grid], 0)

        layout.addStretch(1)

        # Editor
        self.exit_editor_button = FCButton(_('Exit Editor'), bold=True)
        self.exit_editor_button.setIcon(QtGui.QIcon(self.app.resource_location + '/power16.png'))
        self.exit_editor_button.setToolTip(
            _("Exit from Editor.")
        )
        layout.addWidget(self.exit_editor_button)

        # Signals
        self.level.toggled.connect(self.on_level_changed)
        self.exit_editor_button.clicked.connect(lambda: self.app.on_editing_finished())

    def on_param_click(self):
        if self.param_button.get_value():
            self.par_frame.show()
        else:
            self.par_frame.hide()

    def change_level(self, level):
        """

        :param level:   application level: either 'b' or 'a'
        :type level:    str
        :return:
        """
        if level == 'a':
            self.level.setChecked(True)
        else:
            self.level.setChecked(False)
        self.on_level_changed(self.level.isChecked())

    def on_level_changed(self, checked):
        if not checked:
            self.level.setText('%s' % _('Beginner'))
            self.level.setStyleSheet("""
                                    QToolButton
                                    {
                                        color: green;
                                    }
                                    """)

            self.adv_frame.hide()

            # Context Menu section
            # self.tw.removeContextMenu()
        else:
            self.level.setText('%s' % _('Advanced'))
            self.level.setStyleSheet("""
                                    QToolButton
                                    {
                                        color: red;
                                    }
                                    """)

            self.adv_frame.show()

            # Context Menu section
            # self.tw.setupContextMenu()


class DrawToolShape(object):
    """
    Encapsulates "shapes" under a common class.
    """

    tolerance = None

    @staticmethod
    def get_pts(o):
        """
        Returns a list of all points in the object, where
        the object can be a Polygon, Not a polygon, or a list
        of such. Search is done recursively.

        :param o:   geometric object
        :return:    List of points
        :rtype:     list
        """
        pts = []

        # Iterable: descend into each item.
        try:
            if isinstance(o, (MultiPolygon, MultiLineString)):
                for subo in o.geoms:
                    pts += DrawToolShape.get_pts(subo)
            else:
                for subo in o:
                    pts += DrawToolShape.get_pts(subo)
        # Non-iterable
        except TypeError:
            if o is None:
                return

            # DrawToolShape: descend into .geo.
            if isinstance(o, DrawToolShape):
                pts += DrawToolShape.get_pts(o.geo)

            # Descend into .exterior and .interiors
            elif isinstance(o, Polygon):
                pts += DrawToolShape.get_pts(o.exterior)
                for i in o.interiors:
                    pts += DrawToolShape.get_pts(i)
            elif isinstance(o, (MultiLineString, MultiPolygon)):
                for geo_pol_line in o.geoms:
                    pts += DrawToolShape.get_pts(geo_pol_line)
            # Has .coords: list them.
            else:
                if DrawToolShape.tolerance is not None:
                    pts += list(o.simplify(DrawToolShape.tolerance).coords)
                else:
                    pts += list(o.coords)
        return pts

    def __init__(self, geo: (BaseGeometry, list)):

        # Shapely type or list of such
        self.geo = geo
        self.utility = False
        self.data = {
            'name': _("Geo Elem"),
            'type': _('Path'),  # 'Path', 'Arc', 'Rectangle', 'Polygon', 'Circle',
            'origin': 'center',  # 'center', 'tl', 'tr', 'bl', 'br'
            'bounds': self.bounds()  # xmin, ymin, xmax, ymax
        }

    def get_all_points(self):
        return DrawToolShape.get_pts(self)

    def bounds(self):
        """
                Returns coordinates of rectangular bounds
                of geometry: (xmin, ymin, xmax, ymax).
                """

        # fixed issue of getting bounds only for one level lists of objects
        # now it can get bounds for nested lists of objects

        if self.geo is None:
            return 0, 0, 0, 0

        def bounds_rec(shape_el):
            if type(shape_el) is list:
                minx = np.Inf
                miny = np.Inf
                maxx = -np.Inf
                maxy = -np.Inf

                for k in shape_el:
                    minx_, miny_, maxx_, maxy_ = bounds_rec(k)
                    minx = min(minx, minx_)
                    miny = min(miny, miny_)
                    maxx = max(maxx, maxx_)
                    maxy = max(maxy, maxy_)
                return minx, miny, maxx, maxy
            else:
                # it's a Shapely object, return its bounds
                return shape_el.bounds

        bounds_coords = bounds_rec(self.geo)
        return bounds_coords

    def mirror(self, axis, point):
        """
        Mirrors the shape around a specified axis passing through
        the given point.

        :param axis:    "X" or "Y" indicates around which axis to mirror.
        :type axis:     str
        :param point:   [x, y] point belonging to the mirror axis.
        :type point:    list
        :return:        None
        """

        px, py = point
        xscale, yscale = {"X": (1.0, -1.0), "Y": (-1.0, 1.0)}[axis]

        def mirror_geom(shape_el):
            if type(shape_el) is list:
                new_obj = []
                for g in shape_el:
                    new_obj.append(mirror_geom(g))
                return new_obj
            else:
                return scale(shape_el, xscale, yscale, origin=(px, py))

        try:
            self.geo = mirror_geom(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.mirror() --> Failed to mirror. No shape selected")

    def rotate(self, angle, point):
        """
        Rotate a shape by an angle (in degrees) around the provided coordinates.


        The angle of rotation are specified in degrees (default). Positive angles are
        counter-clockwise and negative are clockwise rotations.

        The point of origin can be a keyword 'center' for the bounding box
        center (default), 'centroid' for the geometry's centroid, a Point object
        or a coordinate tuple (x0, y0).

        See shapely manual for more information: http://toblerity.org/shapely/manual.html#affine-transformations

        :param angle:   The angle of rotation
        :param point:   The point of origin
        :return:        None
        """

        px, py = point

        def rotate_geom(shape_el):
            if type(shape_el) is list:
                new_obj = []
                for g in shape_el:
                    new_obj.append(rotate_geom(g))
                return new_obj
            else:
                return rotate(shape_el, angle, origin=(px, py))

        try:
            self.geo = rotate_geom(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.rotate() --> Failed to rotate. No shape selected")

    def skew(self, angle_x, angle_y, point):
        """
        Shear/Skew a shape by angles along x and y dimensions.

        angle_x, angle_y : float, float
            The shear angle(s) for the x and y axes respectively. These can be
            specified in either degrees (default) or radians by setting
            use_radians=True.

        See shapely manual for more information: http://toblerity.org/shapely/manual.html#affine-transformations

        :param angle_x:
        :param angle_y:
        :param point:       tuple of coordinates (x,y)
        :return:
        """
        px, py = point

        def skew_geom(shape_el):
            if type(shape_el) is list:
                new_obj = []
                for g in shape_el:
                    new_obj.append(skew_geom(g))
                return new_obj
            else:
                return skew(shape_el, angle_x, angle_y, origin=(px, py))

        try:
            self.geo = skew_geom(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.skew() --> Failed to skew. No shape selected")

    def offset(self, vect):
        """
        Offsets all shapes by a given vector

        :param vect:    (x, y) vector by which to offset the shape geometry
        :type vect:     tuple
        :return:        None
        """

        try:
            dx, dy = vect
        except TypeError:
            log.debug("DrawToolShape.offset() --> An (x,y) pair of values are needed. "
                      "Probable you entered only one value in the Offset field.")
            return

        def translate_recursion(geom):
            if type(geom) == list:
                geoms = []
                for local_geom in geom:
                    geoms.append(translate_recursion(local_geom))
                return geoms
            else:
                return translate(geom, xoff=dx, yoff=dy)

        try:
            self.geo = translate_recursion(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.offset() --> Failed to offset. No shape selected")

    def scale(self, xfactor, yfactor=None, point=None):
        """
        Scales all shape geometry by a given factor.

        :param xfactor:     Factor by which to scale the shape's geometry/
        :type xfactor:      float
        :param yfactor:     Factor by which to scale the shape's geometry/
        :type yfactor:      float
        :param point:       Point of origin; tuple
        :return: None
        """

        try:
            xfactor = float(xfactor)
        except Exception:
            log.debug("DrawToolShape.offset() --> Scale factor has to be a number: integer or float.")
            return

        if yfactor is None:
            yfactor = xfactor
        else:
            try:
                yfactor = float(yfactor)
            except Exception:
                log.debug("DrawToolShape.offset() --> Scale factor has to be a number: integer or float.")
                return

        if point is None:
            px = 0
            py = 0
        else:
            px, py = point

        def scale_recursion(geom):
            if type(geom) == list:
                geoms = []
                for local_geom in geom:
                    geoms.append(scale_recursion(local_geom))
                return geoms
            else:
                return scale(geom, xfactor, yfactor, origin=(px, py))

        try:
            self.geo = scale_recursion(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.scale() --> Failed to scale. No shape selected")

    def buffer(self, value, join=None, factor=None):
        """
        Create a buffered geometry

        :param value:   the distance to which to buffer
        :param join:    the type of connections between nearby buffer lines
        :param factor:  a scaling factor which will do a "sort of" buffer
        :return:        None
        """

        def buffer_recursion(geom):
            if type(geom) == list:
                geoms = []
                for local_geom in geom:
                    geoms.append(buffer_recursion(local_geom))
                return geoms
            else:
                if factor:
                    return scale(geom, xfact=value, yfact=value, origin='center')
                else:
                    return geom.buffer(value, resolution=32, join_style=join)

        try:
            self.geo = buffer_recursion(self.geo)
        except AttributeError:
            log.debug("DrawToolShape.buffer() --> Failed to buffer. No shape selected")


class DrawToolUtilityShape(DrawToolShape):
    """
    Utility shapes are temporary geometry in the editor
    to assist in the creation of shapes. For example, it
    will show the outline of a rectangle from the first
    point to the current mouse pointer before the second
    point is clicked and the final geometry is created.
    """

    def __init__(self, geo: (BaseGeometry, list)):
        super(DrawToolUtilityShape, self).__init__(geo=geo)
        self.utility = True


class DrawTool(object):
    """
    Abstract Class representing a tool in the drawing
    program. Can generate geometry, including temporary
    utility geometry that is updated on user clicks
    and mouse motion.
    """

    def __init__(self, draw_app):
        self.draw_app = draw_app
        self.complete = False
        self.points = []
        self.geometry = None  # DrawToolShape or None

    def click(self, point: Union[list[float, float], tuple[float, float]]):
        """
        :param point: [x, y] Coordinate pair.
        """
        return ""

    def click_release(self, point):
        """
        :param point: [x, y] Coordinate pair.
        """
        return ""

    def on_key(self, key):
        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()
        return

    def utility_geometry(self, data=None):
        return None

    @staticmethod
    def bounds(obj):
        def bounds_rec(o):
            if type(o) is list:
                minx = np.Inf
                miny = np.Inf
                maxx = -np.Inf
                maxy = -np.Inf

                for k in o:
                    try:
                        minx_, miny_, maxx_, maxy_ = bounds_rec(k)
                    except Exception as e:
                        log.error("camlib.Gerber.bounds() --> %s" % str(e))
                        return

                    minx = min(minx, minx_)
                    miny = min(miny, miny_)
                    maxx = max(maxx, maxx_)
                    maxy = max(maxy, maxy_)
                return minx, miny, maxx, maxy
            else:
                # it's a Shapely object, return its bounds
                return o.geo.bounds

        bounds_coords = bounds_rec(obj)
        return bounds_coords


class FCShapeTool(DrawTool):
    """
    Abstract class for tools that create a shape.
    """

    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)

        self.name = None

    def make(self):
        pass


class FCCircle(FCShapeTool):
    """
    Resulting type: Polygon
    """

    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)
        self.name = 'circle'

        self.draw_app = draw_app
        self.app = self.draw_app.app
        self.plugin_name = _("Circle")
        self.storage = self.draw_app.storage
        self.util_geo = None

        self.cursor_data_control = True

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero_circle_geo.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.circle_tool = CircleEditorTool(self.app, self.draw_app, plugin_name=self.plugin_name)
        self.ui = self.circle_tool.ui
        self.circle_tool.run()

        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.draw_app.app.inform.emit(_("Click on Center point ..."))
        self.steps_per_circ = self.draw_app.app.options["geometry_circle_steps"]

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.KeyboardModifier.ShiftModifier:
            # deselect all shapes
            self.draw_app.selected = []
            for ____ in self.storage.get_objects():
                try:
                    __, closest_shape = self.storage.nearest(point)
                    # select closes shape
                    self.draw_app.selected.append(closest_shape)
                except StopIteration:
                    return ""

            if self.draw_app.selected:
                self.draw_app.plot_all()
                self.circle_tool.mode = 'change'
                sel_shape_geo = self.draw_app.selected[-1].geo
                geo_bounds = sel_shape_geo.bounds
                # assuming that the default setting for anchor is center
                origin_x_sel_geo = geo_bounds[0] + ((geo_bounds[2] - geo_bounds[0]) / 2)
                self.circle_tool.ui.x_entry.set_value(origin_x_sel_geo)
                origin_y_sel_geo = geo_bounds[1] + ((geo_bounds[3] - geo_bounds[1]) / 2)
                self.circle_tool.ui.y_entry.set_value(origin_y_sel_geo)
                self.draw_app.app.inform.emit(
                    _("Click on Center point to add a new circle or Apply to change the selection."))
            return

        self.circle_tool.mode = 'add'
        self.points.append(point)
        self.circle_tool.ui.x_entry.set_value(point[0])
        self.circle_tool.ui.y_entry.set_value(point[1])

        if len(self.points) == 1:
            if self.ui.radius_link_btn.isChecked():
                self.draw_app.app.inform.emit(_("Click on Perimeter point to complete ..."))
                return "Click on perimeter to complete ..."
            else:
                self.draw_app.app.inform.emit(_("Click on Perimeter point to set axis major ..."))
                return "Click on perimeter to complete ..."

        if len(self.points) == 2:
            if self.ui.radius_link_btn.isChecked():
                self.make()
                return "Done."
            else:
                self.draw_app.app.inform.emit(_("Click on Perimeter point to set axis minor ..."))
                return "Click on perimeter to complete ..."

        if len(self.points) == 3:
            self.make()
            return "Done."

        return ""

    def utility_geometry(self, data=None):
        if self.ui.radius_link_btn.isChecked():  # circle
            if len(self.points) == 1:
                p1 = self.points[0]
                p2 = data

                radius = np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
                self.ui.radius_x_entry.set_value(radius)
                util_geo = Point(p1).buffer(radius, int(self.steps_per_circ))
                self.util_geo = util_geo
                return DrawToolUtilityShape(util_geo)
        else:  # ellipse
            if len(self.points) == 1:
                p1 = self.points[0]
                p2 = data
                radius = np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
                angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0]) * 180 / math.pi

                axis_min_radius = radius * 0.66
                if axis_min_radius > 3:
                    axis_min_radius = 3
                self.ui.angle_entry.set_value(angle)
                self.ui.radius_x_entry.set_value(radius)
                self.ui.radius_y_entry.set_value(axis_min_radius)
            elif len(self.points) == 2:
                p1 = self.points[0]
                p2 = data

                angle = self.ui.angle_entry.get_value()
                radius = self.ui.radius_x_entry.get_value()
                axis_min_radius = np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
                self.ui.radius_y_entry.set_value(axis_min_radius)
            else:
                return

            circle_geo = Point((p1[0], p1[1])).buffer(1)
            util_geo = scale(circle_geo, radius, axis_min_radius)
            if angle != 0:
                util_geo = rotate(util_geo, angle)

            self.util_geo = util_geo
            return DrawToolUtilityShape(util_geo)

        return None

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:

            if self.draw_app.app.mouse_pos[0] != self.points[-1][0] or (
                    self.draw_app.app.mouse_pos[1] != self.points[-1][1] and
                    self.circle_tool.ui.radius_link_btn.isChecked()):
                try:
                    # VisPy keys
                    if self.circle_tool.radius_x == 0.0:
                        self.circle_tool.radius_x = str(key.name)
                    else:
                        self.circle_tool.radius_x = str(self.circle_tool.radius_x) + str(key.name)
                except AttributeError:
                    # Qt keys
                    if self.circle_tool.radius_x == 0.0:
                        self.circle_tool.radius_x = chr(key)
                    else:
                        self.circle_tool.radius_x = str(self.circle_tool.radius_x) + chr(key)

            if self.draw_app.app.mouse_pos[1] != self.points[-1][1] or (
                    self.draw_app.app.mouse_pos[0] != self.points[-1][0] and
                    self.circle_tool.ui.radius_link_btn.isChecked()):
                try:
                    # VisPy keys
                    if self.circle_tool.radius_y == 0.0:
                        self.circle_tool.radius_y = str(key.name)
                    else:
                        self.circle_tool.radius_y = str(self.circle_tool.radius_y) + str(key.name)
                except AttributeError:
                    # Qt keys
                    if self.circle_tool.radius_y == 0.0:
                        self.circle_tool.radius_y = chr(key)
                    else:
                        self.circle_tool.radius_y = str(self.circle_tool.radius_y) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            new_radius_x, new_radius_y = self.circle_tool.radius_x, self.circle_tool.radius_y

            if self.circle_tool.ui.radius_link_btn.isChecked():
                if self.circle_tool.radius_x == 0:
                    return _("Failed.")
            else:
                if self.circle_tool.radius_x == 0 or self.circle_tool.radius_y == 0:
                    return _("Failed.")

            new_pt = (
                new_radius_x + self.circle_tool.ui.x_entry.get_value(),
                self.circle_tool.ui.y_entry.get_value()
            )
            self.points.append(new_pt)
            self.make()
            self.draw_app.on_shape_complete()
            self.draw_app.select_tool("select")
            return "Done."

        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

    def make(self):
        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        # p1 = self.points[0]
        # p2 = self.points[1]
        # radius = distance(p1, p2)
        # circle_shape = Point(p1).buffer(radius, int(self.steps_per_circ / 4)).exterior

        self.geometry = DrawToolShape(self.util_geo.exterior)
        self.geometry.data['type'] = _('Circle')

        self.complete = True
        self.draw_cursor_data(delete=True)

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass

        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCArc(FCShapeTool):
    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)
        self.name = 'arc'

        self.draw_app = draw_app

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero_arc.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        self.draw_app.app.inform.emit(_("Click on Center point ..."))

        # Direction of rotation between point 1 and 2.
        # 'cw' or 'ccw'. Switch direction by hitting the
        # 'o' key.
        self.direction = "cw"

        # Mode
        # C12 = Center, p1, p2
        # 12C = p1, p2, Center
        # 132 = p1, p3, p2
        self.mode = "c12"  # Center, p1, p2

        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.steps_per_circ = self.draw_app.app.options["geometry_circle_steps"]

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.points.append(point)

        if len(self.points) == 1:
            if self.mode == 'c12':
                self.draw_app.app.inform.emit(_("Click on Start point ..."))
            elif self.mode == '132':
                self.draw_app.app.inform.emit(_("Click on Point3 ..."))
            else:
                self.draw_app.app.inform.emit(_("Click on Stop point ..."))
            return "Click on 1st point ..."

        if len(self.points) == 2:
            if self.mode == 'c12':
                self.draw_app.app.inform.emit(_("Click on Stop point to complete ..."))
            elif self.mode == '132':
                self.draw_app.app.inform.emit(_("Click on Point2 to complete ..."))
            else:
                self.draw_app.app.inform.emit(_("Click on Center point to complete ..."))
            return "Click on 2nd point to complete ..."

        if len(self.points) == 3:
            self.make()
            return "Done."

        return ""

    def on_key(self, key):
        if key == 'D' or key == QtCore.Qt.Key.Key_D:
            self.direction = 'cw' if self.direction == 'ccw' else 'ccw'
            return '%s: %s' % (_('Direction'), self.direction.upper())

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key == 'M' or key == QtCore.Qt.Key.Key_M:
            # delete the possible points made before this action; we want to start anew
            self.points[:] = []
            # and delete the utility geometry made up until this point
            self.draw_app.delete_utility_geometry()

            if self.mode == 'c12':
                self.mode = '12c'
                return _('Mode: Start -> Stop -> Center. Click on Start point ...')
            elif self.mode == '12c':
                self.mode = '132'
                return _('Mode: Point1 -> Point3 -> Point2. Click on Point1 ...')
            else:
                self.mode = 'c12'
                return _('Mode: Center -> Start -> Stop. Click on Center point ...')

    def utility_geometry(self, data=None):
        if len(self.points) == 1:  # Show the radius
            center = self.points[0]
            p1 = data

            return DrawToolUtilityShape(LineString([center, p1]))

        if len(self.points) == 2:  # Show the arc

            if self.mode == 'c12':
                center = self.points[0]
                p1 = self.points[1]
                p2 = data

                radius = np.sqrt((center[0] - p1[0]) ** 2 + (center[1] - p1[1]) ** 2)
                startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
                stopangle = np.arctan2(p2[1] - center[1], p2[0] - center[0])

                return DrawToolUtilityShape([LineString(arc(center, radius, startangle, stopangle,
                                                            self.direction, self.steps_per_circ)),
                                             Point(center)])

            elif self.mode == '132':
                p1 = np.array(self.points[0])
                p3 = np.array(self.points[1])
                p2 = np.array(data)

                try:
                    center, radius, t = three_point_circle(p1, p2, p3)
                except TypeError:
                    return

                direction = 'cw' if np.sign(t) > 0 else 'ccw'

                startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
                stopangle = np.arctan2(p3[1] - center[1], p3[0] - center[0])

                return DrawToolUtilityShape([LineString(arc(center, radius, startangle, stopangle,
                                                            direction, self.steps_per_circ)),
                                             Point(center), Point(p1), Point(p3)])

            else:  # '12c'
                p1 = np.array(self.points[0])
                p2 = np.array(self.points[1])

                # Midpoint
                a = (p1 + p2) / 2.0

                # Parallel vector
                c = p2 - p1

                # Perpendicular vector
                b = np.dot(c, np.array([[0, -1], [1, 0]], dtype=np.float32))
                b /= numpy_norm(b)

                # Distance
                t = distance(data, a)

                # Which side? Cross product with c.
                # cross(M-A, B-A), where line is AB and M is the test point.
                side = (data[0] - p1[0]) * c[1] - (data[1] - p1[1]) * c[0]
                t *= np.sign(side)

                # Center = a + bt
                center = a + b * t

                radius = numpy_norm(center - p1)
                startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
                stopangle = np.arctan2(p2[1] - center[1], p2[0] - center[0])

                return DrawToolUtilityShape([LineString(arc(center, radius, startangle, stopangle,
                                                            self.direction, self.steps_per_circ)),
                                             Point(center)])

        return None

    def make(self):

        if self.mode == 'c12':
            center = self.points[0]
            p1 = self.points[1]
            p2 = self.points[2]

            radius = distance(center, p1)
            startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
            stopangle = np.arctan2(p2[1] - center[1], p2[0] - center[0])
            self.geometry = DrawToolShape(LineString(arc(center, radius, startangle, stopangle,
                                                         self.direction, self.steps_per_circ)))

        elif self.mode == '132':
            p1 = np.array(self.points[0])
            p3 = np.array(self.points[1])
            p2 = np.array(self.points[2])

            center, radius, t = three_point_circle(p1, p2, p3)
            direction = 'cw' if np.sign(t) > 0 else 'ccw'

            startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
            stopangle = np.arctan2(p3[1] - center[1], p3[0] - center[0])

            self.geometry = DrawToolShape(LineString(arc(center, radius, startangle, stopangle,
                                                         direction, self.steps_per_circ)))

        else:  # self.mode == '12c'
            p1 = np.array(self.points[0])
            p2 = np.array(self.points[1])
            pc = np.array(self.points[2])

            # Midpoint
            a = (p1 + p2) / 2.0

            # Parallel vector
            c = p2 - p1

            # Perpendicular vector
            b = np.dot(c, np.array([[0, -1], [1, 0]], dtype=np.float32))
            b /= numpy_norm(b)

            # Distance
            t = distance(pc, a)

            # Which side? Cross product with c.
            # cross(M-A, B-A), where line is AB and M is the test point.
            side = (pc[0] - p1[0]) * c[1] - (pc[1] - p1[1]) * c[0]
            t *= np.sign(side)

            # Center = a + bt
            center = a + b * t

            radius = numpy_norm(center - p1)
            startangle = np.arctan2(p1[1] - center[1], p1[0] - center[0])
            stopangle = np.arctan2(p2[1] - center[1], p2[0] - center[0])

            self.geometry = DrawToolShape(LineString(arc(center, radius, startangle, stopangle,
                                                         self.direction, self.steps_per_circ)))
        self.complete = True

        self.draw_app.app.jump_signal.disconnect()

        self.geometry.data['type'] = _('Arc')
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCRectangle(FCShapeTool):
    """
    Resulting type: Polygon
    """

    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)
        self.name = 'rectangle'
        self.draw_app = draw_app
        self.app = self.draw_app.app
        self.plugin_name = _("Rectangle")
        self.storage = self.draw_app.storage

        self.util_geo = None

        self.cursor_data_control = True

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.rect_tool = RectangleEditorTool(self.app, self.draw_app, plugin_name=self.plugin_name)
        self.rect_tool.run()

        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.draw_app.app.inform.emit(_("Click on 1st corner ..."))

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.KeyboardModifier.ShiftModifier:
            # deselect all shapes
            self.draw_app.selected = []
            for ____ in self.storage.get_objects():
                try:
                    __, closest_shape = self.storage.nearest(point)
                    # select closes shape
                    self.draw_app.selected.append(closest_shape)
                except StopIteration:
                    return ""

            if self.draw_app.selected:
                self.draw_app.plot_all()
                self.rect_tool.mode = 'change'
                sel_shape_geo = self.draw_app.selected[-1].geo
                geo_bounds = sel_shape_geo.bounds
                # assuming that the default setting for anchor is center
                origin_x_sel_geo = geo_bounds[0] + ((geo_bounds[2] - geo_bounds[0]) / 2)
                self.rect_tool.ui.x_entry.set_value(origin_x_sel_geo)
                origin_y_sel_geo = geo_bounds[1] + ((geo_bounds[3] - geo_bounds[1]) / 2)
                self.rect_tool.ui.y_entry.set_value(origin_y_sel_geo)
                self.draw_app.app.inform.emit(
                    _("Click on 1st corner to add a new rectangle or Apply to change the selection."))
            return

        self.rect_tool.mode = 'add'
        self.points.append(point)
        if len(self.points) == 1:
            self.draw_app.app.inform.emit(_("Click on opposite corner to complete ..."))
            return "Click on opposite corner to complete ..."
        if len(self.points) == 2:
            self.make()
            return "Done."

        return ""

    def utility_geometry(self, data=None):
        if len(self.points) == 1:
            p1 = self.points[0]
            p2 = data

            corner_type = self.rect_tool.ui.corner_radio.get_value()
            corner_radius = self.rect_tool.ui.radius_entry.get_value()
            length = abs(p1[0] - p2[0])
            width = abs(p1[1] - p2[1])

            if corner_radius == 0.0:
                corner_type = 's'
            if corner_type in ['r', 'b']:
                length -= 2 * corner_radius
                width -= 2 * corner_radius

            base_util_geo = Polygon([p1, (p2[0], p1[1]), p2, (p1[0], p2[1])])
            center_pt = base_util_geo.centroid
            cx = center_pt.x
            cy = center_pt.y
            minx = cx - (length / 2)
            miny = cy - (width / 2)
            maxx = cx + (length / 2)
            maxy = cy + (width / 2)

            if length < 0 or width < 0:
                corner_type = 's'

            if corner_type == 'r':
                util_geo = box(minx, miny, maxx, maxy).buffer(
                    corner_radius, join_style=base.JOIN_STYLE.round,
                    resolution=self.draw_app.app.options["geometry_circle_steps"]).exterior
            elif corner_type == 'b':
                util_geo = box(minx, miny, maxx, maxy).buffer(
                    corner_radius, join_style=base.JOIN_STYLE.bevel,
                    resolution=self.draw_app.app.options["geometry_circle_steps"]).exterior
            else:  # 's' - square
                util_geo = base_util_geo.exterior

            self.util_geo = util_geo
            return DrawToolUtilityShape(util_geo)

        return None

    def make(self):
        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        # p1 = self.points[0]
        # p2 = self.points[1]
        # # self.geometry = LinearRing([p1, (p2[0], p1[1]), p2, (p1[0], p2[1])])
        # geo = LinearRing([p1, (p2[0], p1[1]), p2, (p1[0], p2[1])])

        self.geometry = DrawToolShape(self.util_geo)
        self.geometry.data['type'] = _('Rectangle')

        self.complete = True
        self.draw_cursor_data(delete=True)

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:

            if self.draw_app.app.mouse_pos[0] != self.points[-1][0]:
                try:
                    # VisPy keys
                    if self.rect_tool.length == 0:
                        self.rect_tool.length = str(key.name)
                    else:
                        self.rect_tool.length = str(self.rect_tool.length) + str(key.name)
                except AttributeError:
                    # Qt keys
                    if self.rect_tool.length == 0:
                        self.rect_tool.length = chr(key)
                    else:
                        self.rect_tool.length = str(self.rect_tool.length) + chr(key)
            if self.draw_app.app.mouse_pos[1] != self.points[-1][1]:
                try:
                    # VisPy keys
                    if self.rect_tool.width == 0:
                        self.rect_tool.width = str(key.name)
                    else:
                        self.rect_tool.width = str(self.rect_tool.width) + str(key.name)
                except AttributeError:
                    # Qt keys
                    if self.rect_tool.width == 0:
                        self.rect_tool.width = chr(key)
                    else:
                        self.rect_tool.width = str(self.rect_tool.width) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            new_x, new_y = self.points[-1][0], self.points[-1][1]

            if self.rect_tool.length != 0:
                target_length = self.rect_tool.length
                if target_length is None:
                    self.rect_tool.length = 0.0
                    return _("Failed.")

                new_x = self.points[-1][0] + target_length

            if self.rect_tool.width != 0:
                target_width = self.rect_tool.width
                if target_width is None:
                    self.rect_tool.width = 0.0
                    return _("Failed.")

                new_y = self.points[-1][1] + target_width

            if self.points[-1] != (new_x, new_y):
                self.draw_app.app.on_jump_to(custom_location=(new_x, new_y), fit_center=False)

            if len(self.points) > 0:
                msg = '%s: (%s, %s). %s' % (
                    _("Projected"), str(self.rect_tool.length), str(self.rect_tool.width),
                    _("Click to complete ..."))
                self.draw_app.app.inform.emit(msg)

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCPolygon(FCShapeTool):
    """
    Resulting type: Polygon
    """

    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)
        self.name = 'polygon'
        self.draw_app = draw_app
        self.app = self.draw_app.app
        self.plugin_name = _("Polygon")

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.polygon_tool = PathEditorTool(self.app, self.draw_app, plugin_name=self.plugin_name)
        self.polygon_tool.run()
        self.new_segment = True

        self.cursor_data_control = True

        self.app.ui.notebook.setTabText(2, self.plugin_name)
        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])

        self.draw_app.app.inform.emit(_("Click on 1st corner ..."))

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.draw_app.in_action = True
        if point != self.points[-1:]:
            self.points.append(point)

        if len(self.points) > 0:
            self.draw_app.app.inform.emit(_("Click on next Point or click right mouse button to complete ..."))
            return "Click on next point or hit ENTER to complete ..."

        return ""

    def make(self):
        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        if self.points[-1] == self.points[-2]:
            self.points.pop(-1)

        # self.geometry = LinearRing(self.points)
        self.geometry = DrawToolShape(LinearRing(self.points))
        self.draw_app.in_action = False
        self.complete = True

        self.draw_app.app.jump_signal.disconnect()
        self.geometry.data['type'] = self.plugin_name
        self.draw_cursor_data(delete=True)
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def utility_geometry(self, data=None):
        if len(self.points) == 1:
            temp_points = [x for x in self.points]
            temp_points.append(data)
            return DrawToolUtilityShape(LineString(temp_points))
        elif len(self.points) > 1:
            temp_points = [x for x in self.points]
            temp_points.append(data)
            return DrawToolUtilityShape(LinearRing(temp_points))
        else:
            return None

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key == 'Backspace' or key == QtCore.Qt.Key.Key_Backspace:
            if len(self.points) > 0:
                self.points = self.points[0:-1]
                # Remove any previous utility shape
                self.draw_app.tool_shape.clear(update=False)
                geo = self.utility_geometry(data=(self.draw_app.snap_x, self.draw_app.snap_y))
                self.draw_app.draw_utility_geometry(geo=geo)
                if geo:
                    return _("Backtracked one point ...")
                else:
                    self.draw_app.app.inform.emit(_("Click on 1st corner ..."))

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:
            try:
                # VisPy keys
                if self.polygon_tool.length == 0 or self.new_segment is True:
                    self.polygon_tool.length = str(key.name)
                    self.new_segment = False
                else:
                    self.polygon_tool.length = str(self.polygon_tool.length) + str(key.name)
            except AttributeError:
                # Qt keys
                if self.polygon_tool.length == 0 or self.new_segment is True:
                    self.polygon_tool.length = chr(key)
                    self.new_segment = False
                else:
                    self.polygon_tool.length = str(self.polygon_tool.length) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            if self.polygon_tool.length != 0:
                target_length = self.polygon_tool.length
                if target_length is None:
                    self.polygon_tool.length = 0.0
                    return _("Failed.")

                first_pt = self.points[-1]
                last_pt = self.draw_app.app.mouse_pos

                seg_length = math.sqrt((last_pt[0] - first_pt[0])**2 + (last_pt[1] - first_pt[1])**2)
                if seg_length == 0.0:
                    return
                try:
                    new_x = first_pt[0] + (last_pt[0] - first_pt[0]) / seg_length * target_length
                    new_y = first_pt[1] + (last_pt[1] - first_pt[1]) / seg_length * target_length
                except ZeroDivisionError as err:
                    self.points = []
                    self.clean_up()
                    return '[ERROR_NOTCL] %s %s' % (_("Failed."), str(err).capitalize())

                if self.points[-1] != (new_x, new_y):
                    self.points.append((new_x, new_y))
                    self.new_segment = True
                    self.draw_app.app.on_jump_to(custom_location=(new_x, new_y), fit_center=False)
                    if len(self.points) > 0:
                        msg = '%s: %s. %s' % (
                            _("Projected"), str(self.polygon_tool.length),
                            _("Click on next Point or click right mouse button to complete ..."))
                        self.draw_app.app.inform.emit(msg)

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.polygon_tool.on_tab_close()


class FCPath(FCShapeTool):
    """
    Resulting type: LineString
    """

    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.draw_app = draw_app
        self.name = 'path'
        self.app = self.draw_app.app

        # show the cursor data
        self.cursor_data_control = True

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero_path5.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.path_tool = PathEditorTool(self.app, self.draw_app, plugin_name=_("Path"))
        self.path_tool.run()

        self.new_segment = True
        self.close_x = 0.0
        self.close_y = 0.0

        self.app.ui.notebook.setTabText(2, _("Path"))
        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])

        self.draw_app.app.inform.emit(_("Click on 1st point ..."))

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.draw_app.in_action = True
        modifier = QtWidgets.QApplication.keyboardModifiers()
        if modifier == Qt.KeyboardModifier.ShiftModifier:
            new_point = self.close_x, self.close_y
            if new_point != self.points[-1:]:
                self.points.append(new_point)
        else:
            if point != self.points[-1:]:
                self.points.append(point)

        if len(self.points) > 0:
            self.draw_app.app.inform.emit(_("Click on next Point or click right mouse button to complete ..."))
            return "Click on next point or hit ENTER to complete ..."

        return ""

    def make(self):
        self.geometry = DrawToolShape(LineString(self.points))
        self.name = 'path'

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        self.draw_app.in_action = False
        self.complete = True

        self.draw_app.app.jump_signal.disconnect()
        self.geometry.data['type'] = _('Path')
        self.draw_cursor_data(delete=True)
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def utility_geometry(self, data=None):
        if len(self.points) > 0:
            modifier = QtWidgets.QApplication.keyboardModifiers()
            if modifier == Qt.KeyboardModifier.ShiftModifier:
                temp_points = [x for x in self.points]
                if not temp_points:
                    return DrawToolUtilityShape(None)

                x_start = temp_points[-1][0]
                y_start = temp_points[-1][1]
                x_end = data[0]
                y_end = data[1]
                dx = x_end - x_start
                dy = y_end - y_start
                det_angle = self.update_angle(dx, dy)

                new_x, new_y = data

                if 0 <= det_angle <= 10:
                    new_x = data[0]
                    new_y = y_start

                if 80 <= det_angle <= 90:
                    new_x = x_start
                    new_y = data[1]

                if 35 <= det_angle <= 55:
                    new_x, new_y = self.closest_point_to_45_degrees(origin=temp_points[-1], current=data)

                self.close_x, self.close_y = new_x, new_y

                temp_points.append([new_x, new_y])
            else:
                temp_points = [x for x in self.points]
                temp_points.append(data)

            return DrawToolUtilityShape(LineString(temp_points))

        return None

    @staticmethod
    def closest_point_to_45_degrees(origin, current):
        # Calculate vector from origin to current point
        vector_x = current[0] - origin[0]
        vector_y = current[1] - origin[1]

        # Calculate the angle between the vector and the x-axis
        angle = math.atan2(vector_y, vector_x)

        # Calculate the angle of the 45-degree line
        angle_45 = math.radians(45)

        # Determine the angle to the closest point on the 45-degree line
        closest_angle = round(angle / angle_45) * angle_45

        # Calculate the coordinates of the closest point
        closest_distance = math.sqrt(vector_x ** 2 + vector_y ** 2)
        closest_point_x = origin[0] + closest_distance * math.cos(closest_angle)
        closest_point_y = origin[1] + closest_distance * math.sin(closest_angle)

        return closest_point_x, closest_point_y

    def update_angle(self, dx, dy):
        try:
            angle = math.degrees(math.atan2(abs(dy), abs(dx)))
            # if angle < 0:
            #     angle += 360
        except Exception as e:
            self.app.log.error("FCPath.update_angle() -> %s" % str(e))
            return None
        return angle

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key == 'Backspace' or key == QtCore.Qt.Key.Key_Backspace:
            if len(self.points) > 0:
                self.points = self.points[0:-1]
                # Remove any previous utility shape
                self.draw_app.tool_shape.clear(update=False)
                geo = self.utility_geometry(data=(self.draw_app.snap_x, self.draw_app.snap_y))
                self.draw_app.draw_utility_geometry(geo=geo)
                if geo:
                    return _("Backtracked one point ...")
                else:
                    return _("Click on 1st point ...")

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:
            try:
                # VisPy keys
                if self.path_tool.length == 0 or self.new_segment is True:
                    self.path_tool.length = str(key.name)
                    self.new_segment = False
                else:
                    self.path_tool.length = str(self.path_tool.length) + str(key.name)
            except AttributeError:
                # Qt keys
                if self.path_tool.length == 0 or self.new_segment is True:
                    self.path_tool.length = chr(key)
                    self.new_segment = False
                else:
                    self.path_tool.length = str(self.path_tool.length) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            if self.path_tool.length != 0:
                # target_length = self.interpolate_length.replace(',', '.')
                # try:
                #     target_length = eval(target_length)
                # except SyntaxError as err:
                #     ret = '%s: %s' % (str(err).capitalize(), self.interpolate_length)
                #     self.interpolate_length = ''
                #     return ret

                target_length = self.path_tool.length
                if target_length is None:
                    self.path_tool.length = 0.0
                    return _("Failed.")

                first_pt = self.points[-1]
                last_pt = self.draw_app.app.mouse_pos

                seg_length = math.sqrt((last_pt[0] - first_pt[0])**2 + (last_pt[1] - first_pt[1])**2)
                if seg_length == 0.0:
                    return
                try:
                    new_x = first_pt[0] + (last_pt[0] - first_pt[0]) / seg_length * target_length
                    new_y = first_pt[1] + (last_pt[1] - first_pt[1]) / seg_length * target_length
                except ZeroDivisionError as err:
                    self.points = []
                    self.clean_up()
                    return '[ERROR_NOTCL] %s %s' % (_("Failed."), str(err).capitalize())

                if self.points[-1] != (new_x, new_y):
                    self.points.append((new_x, new_y))
                    self.new_segment = True
                    self.draw_app.app.on_jump_to(custom_location=(new_x, new_y), fit_center=False)
                    if len(self.points) > 0:
                        msg = '%s: %s. %s' % (
                            _("Projected"), str(self.path_tool.length),
                            _("Click on next Point or click right mouse button to complete ..."))
                        self.draw_app.app.inform.emit(msg)
                        # self.interpolate_length = ''
                        # return "Click on next point or hit ENTER to complete ..."

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.path_tool.on_tab_close()


class FCSelect(DrawTool):
    def __init__(self, draw_app: AppGeoEditor):
        DrawTool.__init__(self, draw_app)
        self.name = 'select'
        self.draw_app: AppGeoEditor = draw_app

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        self.storage = self.draw_app.storage
        # self.shape_buffer = self.draw_app.shape_buffer
        # self.selected = self.draw_app.selected

        # make sure that the cursor text from the FCPath is deleted
        if self.draw_app.app.use_3d_engine and self.draw_app.app.plotcanvas.text_cursor.parent:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        # make sure that the Tools tab is removed
        try:
            self.draw_app.app.ui.notebook.removeTab(2)
        except Exception:
            pass

    def click_release(self, point):
        """

        :param point:   The point for which to find the nearest shape
        :return:
        """

        # list where we store the overlapped shapes under our mouse left click position
        over_shape_list = []

        if self.draw_app.interdict_selection is True:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s' % _("Selection not allowed. Wait ..."))
            return

        # pos[0] and pos[1] are the mouse click coordinates (x, y)
        for ____ in self.storage.get_objects():
            # first method of click selection -> inconvenient
            # minx, miny, maxx, maxy = obj_shape.geo.bounds
            # if (minx <= pos[0] <= maxx) and (miny <= pos[1] <= maxy):
            #     over_shape_list.append(obj_shape)

            # second method of click selection -> slow
            # outside = obj_shape.geo.buffer(0.1)
            # inside = obj_shape.geo.buffer(-0.1)
            # shape_band = outside.difference(inside)
            # if Point(pos).within(shape_band):
            #     over_shape_list.append(obj_shape)

            # 3rd method of click selection -> inconvenient
            try:
                __, closest_shape = self.storage.nearest(point)
            except StopIteration:
                return ""

            over_shape_list.append(closest_shape)

        try:
            # if there is no shape under our click then deselect all shapes
            # it will not work for 3rd method of click selection
            if not over_shape_list:
                self.draw_app.selected = []
                AppGeoEditor.draw_shape_idx = -1
            else:
                # if there are shapes under our click then advance through the list of them, one at the time in a
                # circular way
                AppGeoEditor.draw_shape_idx = (AppGeoEditor.draw_shape_idx + 1) % len(over_shape_list)
                obj_to_add = over_shape_list[int(AppGeoEditor.draw_shape_idx)]

                key_modifier = QtWidgets.QApplication.keyboardModifiers()

                if key_modifier == QtCore.Qt.KeyboardModifier.ShiftModifier:
                    mod_key = 'Shift'
                elif key_modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
                    mod_key = 'Control'
                else:
                    mod_key = None

                if mod_key == self.draw_app.app.options["global_mselect_key"]:
                    # if modifier key is pressed then we add to the selected list the current shape but if it's already
                    # in the selected list, we removed it. Therefore, first click selects, second deselects.
                    if obj_to_add in self.draw_app.selected:
                        self.draw_app.selected.remove(obj_to_add)
                    else:
                        self.draw_app.selected.append(obj_to_add)
                else:
                    self.draw_app.selected = [obj_to_add]
        except Exception as e:
            log.error("[ERROR] AppGeoEditor.FCSelect.click_release() -> Something went bad. %s" % str(e))

        self.draw_app.ui.tw.blockSignals(True)

        self.draw_app.ui.tw.selectionModel().clearSelection()
        for sel_shape in self.draw_app.get_selected():
            iterator = QtWidgets.QTreeWidgetItemIterator(self.draw_app.ui.tw)
            while iterator.value():
                item = iterator.value()
                try:
                    if int(item.text(0)) == id(sel_shape):
                        item.setSelected(True)
                except ValueError:
                    pass
                iterator += 1

        self.draw_app.ui.tw.blockSignals(False)

        # self.draw_app.ui.tw.itemClicked.emit(self.draw_app.ui.tw.currentItem(), 0)
        self.draw_app.update_ui()

        return ""

    def clean_up(self):
        pass


class FCExplode(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'explode'
        self.draw_app = draw_app

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        self.storage = self.draw_app.storage
        self.origin = (0, 0)
        self.destination = None

        self.draw_app.active_tool = self
        if len(self.draw_app.get_selected()) == 0:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s' % _("No shape selected."))
        else:
            self.make()

    def make(self):
        to_be_deleted_list = []
        lines = []

        for shape in self.draw_app.get_selected():
            to_be_deleted_list.append(shape)
            geo = shape.geo

            if geo.geom_type == 'MultiLineString':
                lines = [line for line in geo.geoms]
            elif geo.geom_type == 'MultiPolygon':
                lines = []
                for poly in geo.geoms:
                    lines.append(poly.exterior)
                    lines += list(poly.interiors)
            elif geo.is_ring:
                geo = Polygon(geo)
                ext_coords = list(geo.exterior.coords)

                for c in range(len(ext_coords)):
                    if c < len(ext_coords) - 1:
                        lines.append(LineString([ext_coords[c], ext_coords[c + 1]]))

                for int_geo in geo.interiors:
                    int_coords = list(int_geo.coords)
                    for c in range(len(int_coords)):
                        if c < len(int_coords):
                            lines.append(LineString([int_coords[c], int_coords[c + 1]]))

        for shape in to_be_deleted_list:
            self.draw_app.storage.remove(shape)
            if shape in self.draw_app.selected:
                self.draw_app.selected.remove(shape)

        geo_list = []
        for line in lines:
            line_geo = DrawToolShape(line)
            line_geo.data['type'] = _('Path')
            geo_list.append(line_geo)

        self.geometry = geo_list
        self.draw_app.on_shape_complete()
        self.draw_app.app.inform.emit('[success] %s...' % _("Done."))

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCMove(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'move'
        self.draw_app = draw_app
        self.app = self.draw_app.app
        self.storage = self.draw_app.storage

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        self.origin = None
        self.destination = None
        self.sel_limit = self.draw_app.app.options["geometry_editor_sel_limit"]
        self.selection_shape = self.selection_bbox()

        self.cursor_data_control = True

        if len(self.draw_app.get_selected()) == 0:
            self.has_selection = False
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                          (_("No shape selected."), _("Select some shapes or cancel.")))
        else:
            self.has_selection = True
            self.draw_app.app.inform.emit(_("Click on reference location ..."))

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.move_tool = PathEditorTool(self.app, self.draw_app, plugin_name=_("Move"))
        self.move_tool.run()

        self.app.ui.notebook.setTabText(2, _("Move"))
        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])

        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

    def set_origin(self, origin):
        self.draw_app.app.inform.emit(_("Click on destination point ..."))
        self.origin = origin

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        if self.has_selection is False:
            # self.complete = True
            # self.draw_app.app.inform.emit(_("[WARNING_NOTCL] Move cancelled. No shape selected."))
            # self.select_shapes(point)
            # deselect all shapes
            self.draw_app.selected = []
            for ____ in self.storage.get_objects():
                try:
                    __, closest_shape = self.storage.nearest(point)
                    # select closes shape
                    self.draw_app.selected.append(closest_shape)
                except StopIteration:
                    return ""

            if not self.draw_app.selected:
                self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                              (_("No shape selected."), _("Select some shapes or cancel.")))
                return

            self.has_selection = True
            self.draw_app.plot_all()
            self.selection_shape = self.selection_bbox()
            # self.draw_app.plot_all()
            self.draw_app.app.inform.emit(_("Click on reference location ..."))
            self.set_origin(point)
            return

        if self.origin is None:
            self.points.append(point)
            self.set_origin(point)
            self.selection_shape = self.selection_bbox()
            return "Click on final location."
        else:
            self.destination = point
            self.make()
            # self.draw_app.app.worker_task.emit(({'fcn': self.make,
            #                                      'params': []}))
            return "Done."

    def make(self):
        with self.draw_app.app.proc_container.new('%s...' % _("Moving")):
            # Create new geometry
            dx = self.destination[0] - self.origin[0]
            dy = self.destination[1] - self.origin[1]
            self.geometry = [DrawToolShape(translate(deepcopy(geom.geo), xoff=dx, yoff=dy))
                             for geom in self.draw_app.get_selected()]

            # Delete old
            self.draw_app.delete_selected()
            self.complete = True
            self.origin = None
            self.draw_cursor_data(delete=True)
            self.draw_app.app.inform.emit('[success] %s' % _("Done."))
            try:
                self.draw_app.app.jump_signal.disconnect()
            except TypeError:
                pass

    def selection_bbox(self):
        geo_list = []
        for select_shape in self.draw_app.get_selected():
            if select_shape:
                geometric_data = select_shape.geo
            else:
                continue
            try:
                w_geo = geometric_data.geoms if \
                    isinstance(geometric_data, (MultiPolygon, MultiLineString)) else geometric_data
                geo_list += [g for g in w_geo]
            except TypeError:
                geo_list.append(geometric_data)

        xmin, ymin, xmax, ymax = get_shapely_list_bounds(geo_list)

        pt1 = (xmin, ymin)
        pt2 = (xmax, ymin)
        pt3 = (xmax, ymax)
        pt4 = (xmin, ymax)

        return Polygon([pt1, pt2, pt3, pt4])

    def utility_geometry(self, data=None):
        """
        Temporary geometry on screen while using this tool.

        :param data:
        :return:
        """
        geo_list = []

        if self.origin is None:
            return None

        if len(self.draw_app.get_selected()) == 0:
            return None

        dx = data[0] - self.origin[0]
        dy = data[1] - self.origin[1]

        if len(self.draw_app.get_selected()) <= self.sel_limit:
            try:
                for geom in self.draw_app.get_selected():
                    geo_list.append(translate(geom.geo, xoff=dx, yoff=dy))
            except AttributeError:
                self.draw_app.select_tool('select')
                self.draw_app.selected = []
                return
            return DrawToolUtilityShape(geo_list)
        else:
            try:
                ss_el = translate(self.selection_shape, xoff=dx, yoff=dy)
            except ValueError:
                ss_el = None
            return DrawToolUtilityShape(ss_el)

    def select_shapes(self, pos):
        # list where we store the overlapped shapes under our mouse left click position
        over_shape_list = []

        try:
            _, closest_shape = self.storage.nearest(pos)
        except StopIteration:
            return ""

        over_shape_list.append(closest_shape)

        try:
            # if there is no shape under our click then deselect all shapes
            # it will not work for 3rd method of click selection
            if not over_shape_list:
                self.draw_app.selected = []
                self.draw_app.draw_shape_idx = -1
            else:
                # if there are shapes under our click then advance through the list of them, one at the time in a
                # circular way
                self.draw_app.draw_shape_idx = (AppGeoEditor.draw_shape_idx + 1) % len(over_shape_list)
                try:
                    obj_to_add = over_shape_list[int(AppGeoEditor.draw_shape_idx)]
                except IndexError:
                    return

                key_modifier = QtWidgets.QApplication.keyboardModifiers()
                if self.draw_app.app.options["global_mselect_key"] == 'Control':
                    # if CONTROL key is pressed then we add to the selected list the current shape but if it's
                    # already in the selected list, we removed it. Therefore, first click selects, second deselects.
                    if key_modifier == Qt.KeyboardModifier.ControlModifier:
                        if obj_to_add in self.draw_app.selected:
                            self.draw_app.selected.remove(obj_to_add)
                        else:
                            self.draw_app.selected.append(obj_to_add)
                    else:
                        self.draw_app.selected = []
                        self.draw_app.selected.append(obj_to_add)
                else:
                    if key_modifier == Qt.KeyboardModifier.ShiftModifier:
                        if obj_to_add in self.draw_app.selected:
                            self.draw_app.selected.remove(obj_to_add)
                        else:
                            self.draw_app.selected.append(obj_to_add)
                    else:
                        self.draw_app.selected = []
                        self.draw_app.selected.append(obj_to_add)

        except Exception as e:
            log.error("[ERROR] Something went bad. %s" % str(e))
            raise

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:
            try:
                # VisPy keys
                if self.move_tool.length == 0:
                    self.move_tool.length = str(key.name)
                else:
                    self.move_tool.length = str(self.move_tool.length) + str(key.name)
            except AttributeError:
                # Qt keys
                if self.move_tool.length == 0:
                    self.move_tool.length = chr(key)
                else:
                    self.move_tool.length = str(self.move_tool.length) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            if self.move_tool.length != 0:
                target_length = self.move_tool.length
                if target_length is None:
                    self.move_tool.length = 0.0
                    return _("Failed.")

                first_pt = self.points[-1]
                last_pt = self.draw_app.app.mouse_pos

                seg_length = math.sqrt((last_pt[0] - first_pt[0])**2 + (last_pt[1] - first_pt[1])**2)
                if seg_length == 0.0:
                    return
                try:
                    new_x = first_pt[0] + (last_pt[0] - first_pt[0]) / seg_length * target_length
                    new_y = first_pt[1] + (last_pt[1] - first_pt[1]) / seg_length * target_length
                except ZeroDivisionError as err:
                    self.points = []
                    self.clean_up()
                    return '[ERROR_NOTCL] %s %s' % (_("Failed."), str(err).capitalize())

                if self.points[-1] != (new_x, new_y):
                    self.points.append((new_x, new_y))
                    self.draw_app.app.on_jump_to(custom_location=(new_x, new_y), fit_center=False)
                    self.destination = (new_x, new_y)
                    self.make()
                    self.draw_app.on_shape_complete()
                    self.draw_app.select_tool("select")
                    return "Done."

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.move_tool.on_tab_close()


class FCCopy(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'copy'
        self.draw_app = draw_app
        self.app = self.draw_app.app
        self.storage = self.draw_app.storage

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass

        self.origin = None
        self.destination = None
        self.sel_limit = self.draw_app.app.options["geometry_editor_sel_limit"]
        self.selection_shape = self.selection_bbox()

        # store here the utility geometry, so we can use it on the last step
        self.util_geo = None

        self.clicked_postion = None

        self.cursor_data_control = True

        if len(self.draw_app.get_selected()) == 0:
            self.has_selection = False
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                          (_("No shape selected."), _("Select some shapes or cancel.")))
        else:
            self.has_selection = True
            self.draw_app.app.inform.emit(_("Click on reference location ..."))

        if self.app.use_3d_engine:
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = self.draw_cursor_data
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.copy_tool = CopyEditorTool(self.app, self.draw_app, plugin_name=_("Copy"))
        self.copy_tool.run()

        self.app.ui.notebook.setTabText(2, _("Copy"))
        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])

        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

    def set_origin(self, origin):
        self.draw_app.app.inform.emit(_("Click on destination point ..."))
        self.origin = origin

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        self.clicked_postion = point

        if self.has_selection is False:
            # self.complete = True
            # self.draw_app.app.inform.emit(_("[WARNING_NOTCL] Move cancelled. No shape selected."))
            # self.select_shapes(point)
            # deselect all shapes
            self.draw_app.selected = []
            for ____ in self.storage.get_objects():
                try:
                    __, closest_shape = self.storage.nearest(point)
                    # select closes shape
                    self.draw_app.selected.append(closest_shape)
                except StopIteration:
                    return ""

            if not self.draw_app.selected:
                self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                              (_("No shape selected."), _("Select some shapes or cancel.")))
                return

            self.has_selection = True
            self.draw_app.plot_all()
            self.selection_shape = self.selection_bbox()
            # self.draw_app.plot_all()
            self.draw_app.app.inform.emit(_("Click on reference location ..."))
            return

        if self.origin is None:
            self.points.append(point)
            self.set_origin(point)
            self.selection_shape = self.selection_bbox()
            return "Click on final location."
        else:
            self.destination = point
            self.make()
            # self.draw_app.app.worker_task.emit(({'fcn': self.make,
            #                                      'params': []}))
            return "Done."

    def make(self):
        # Create new geometry
        if len(self.draw_app.get_selected()) > self.sel_limit:
            self.util_geo = self.array_util_geometry((self.clicked_postion[0], self.clicked_postion[1]))

        # when doing circular array we remove the last geometry item in the list because it is the temp_line
        if self.copy_tool.ui.mode_radio.get_value() == 'a' and \
                self.copy_tool.ui.array_type_radio.get_value() == 'circular':
            del self.util_geo.geo[-1]
        self.geometry = [DrawToolShape(deepcopy(shp)) for shp in self.util_geo.geo]

        self.complete = True
        self.origin = None
        self.draw_cursor_data(delete=True)
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass

    def selection_bbox(self):
        geo_list = []
        for select_shape in self.draw_app.get_selected():
            geometric_data = select_shape.geo
            try:
                for g in geometric_data:
                    geo_list.append(g)
            except TypeError:
                geo_list.append(geometric_data)

        xmin, ymin, xmax, ymax = get_shapely_list_bounds(geo_list)

        pt1 = (xmin, ymin)
        pt2 = (xmax, ymin)
        pt3 = (xmax, ymax)
        pt4 = (xmin, ymax)

        return Polygon([pt1, pt2, pt3, pt4])

    def utility_geometry(self, data=None):
        """
        Temporary geometry on screen while using this tool.

        :param data:
        :return:
        """

        if self.origin is None:
            return None

        if len(self.draw_app.get_selected()) == 0:
            return None

        dx = data[0] - self.origin[0]
        dy = data[1] - self.origin[1]

        if len(self.draw_app.get_selected()) <= self.sel_limit:
            copy_mode = self.copy_tool.ui.mode_radio.get_value()
            if copy_mode == 'n':
                try:
                    geo_list = [translate(geom.geo, xoff=dx, yoff=dy) for geom in self.draw_app.get_selected()]
                except AttributeError:
                    self.draw_app.select_tool('select')
                    self.draw_app.selected = []
                    return
                self.util_geo = DrawToolUtilityShape(geo_list)
            else:
                self.util_geo = self.array_util_geometry((dx, dy))
        else:
            try:
                ss_el = translate(self.selection_shape, xoff=dx, yoff=dy)
            except ValueError:
                ss_el = None
            self.util_geo = DrawToolUtilityShape(ss_el)

        return self.util_geo

    def array_util_geometry(self, pos, static=None):
        array_type = self.copy_tool.ui.array_type_radio.get_value()      # 'linear', '2D', 'circular'

        if array_type == 'linear':  # 'Linear'
            return self.linear_geo(pos, static)
        elif array_type == '2D':
            return self.dd_geo(pos)
        elif array_type == 'circular':  # 'Circular'
            return self.circular_geo(pos)

    def linear_geo(self, pos, static):
        axis = self.copy_tool.ui.axis_radio.get_value()  # X, Y or A
        pitch = float(self.copy_tool.ui.pitch_entry.get_value())
        linear_angle = float(self.copy_tool.ui.linear_angle_spinner.get_value())
        array_size = int(self.copy_tool.ui.array_size_entry.get_value())

        if pos[0] is None and pos[1] is None:
            dx = self.draw_app.x
            dy = self.draw_app.y
        else:
            dx = pos[0]
            dy = pos[1]

        geo_list = []
        self.points = [(dx, dy)]

        for item in range(array_size):
            if axis == 'X':
                new_pos = ((dx + (pitch * item)), dy)
            elif axis == 'Y':
                new_pos = (dx, (dy + (pitch * item)))
            else:  # 'A'
                x_adj = pitch * math.cos(math.radians(linear_angle))
                y_adj = pitch * math.sin(math.radians(linear_angle))
                new_pos = ((dx + (x_adj * item)), (dy + (y_adj * item)))

            for g in self.draw_app.get_selected():
                if static is None or static is False:
                    geo_list.append(translate(g.geo, xoff=new_pos[0], yoff=new_pos[1]))
                else:
                    geo_list.append(g.geo)

        return DrawToolUtilityShape(geo_list)

    def dd_geo(self, pos):
        trans_geo = []
        array_2d_type = self.copy_tool.ui.placement_radio.get_value()

        rows = self.copy_tool.ui.rows.get_value()
        columns = self.copy_tool.ui.columns.get_value()

        spacing_rows = self.copy_tool.ui.spacing_rows.get_value()
        spacing_columns = self.copy_tool.ui.spacing_columns.get_value()

        off_x = self.copy_tool.ui.offsetx_entry.get_value()
        off_y = self.copy_tool.ui.offsety_entry.get_value()

        geo_source = [s.geo for s in self.draw_app.get_selected()]

        def geo_bounds(geo: (BaseGeometry, list)):
            minx = np.Inf
            miny = np.Inf
            maxx = -np.Inf
            maxy = -np.Inf

            if type(geo) == list:
                for shp in geo:
                    minx_, miny_, maxx_, maxy_ = geo_bounds(shp)
                    minx = min(minx, minx_)
                    miny = min(miny, miny_)
                    maxx = max(maxx, maxx_)
                    maxy = max(maxy, maxy_)
                return minx, miny, maxx, maxy
            else:
                # it's an object, return its bounds
                return geo.bounds

        xmin, ymin, xmax, ymax = geo_bounds(geo_source)

        currentx = pos[0]
        currenty = pos[1]

        def translate_recursion(geom):
            if type(geom) == list:
                geoms = []
                for local_geom in geom:
                    res_geo = translate_recursion(local_geom)
                    try:
                        geoms += res_geo
                    except TypeError:
                        geoms.append(res_geo)
                return geoms
            else:
                return translate(geom, xoff=currentx, yoff=currenty)

        for row in range(rows):
            currentx = pos[0]

            for col in range(columns):
                trans_geo += translate_recursion(geo_source)
                if array_2d_type == 's':  # 'spacing'
                    currentx += (xmax - xmin + spacing_columns)
                else:   # 'offset'
                    currentx = pos[0] + off_x * (col + 1)    # because 'col' starts from 0 we increment by 1

            if array_2d_type == 's':  # 'spacing'
                currenty += (ymax - ymin + spacing_rows)
            else:   # 'offset;
                currenty = pos[1] + off_y * (row + 1)    # because 'row' starts from 0 we increment by 1

        return DrawToolUtilityShape(trans_geo)

    def circular_geo(self, pos):
        if pos[0] is None and pos[1] is None:
            cdx = self.draw_app.x
            cdy = self.draw_app.y
        else:
            cdx = pos[0] + self.origin[0]
            cdy = pos[1] + self.origin[1]

        utility_list = []

        try:
            radius = distance((cdx, cdy), self.origin)
        except Exception:
            radius = 0

        if radius == 0:
            self.draw_app.delete_utility_geometry()

        if len(self.points) >= 1 and radius > 0:
            try:
                if cdx < self.origin[0]:
                    radius = -radius

                # draw the temp geometry
                initial_angle = math.asin((cdy - self.origin[1]) / radius)
                temp_circular_geo = self.circular_util_shape(radius, initial_angle)

                temp_points = [
                    (self.origin[0], self.origin[1]),
                    (self.origin[0] + pos[0], self.origin[1] + pos[1])
                ]
                temp_line = LineString(temp_points)

                for geo_shape in temp_circular_geo:
                    utility_list.append(geo_shape.geo)
                utility_list.append(temp_line)

                return DrawToolUtilityShape(utility_list)
            except Exception as e:
                log.error("DrillArray.utility_geometry -- circular -> %s" % str(e))

    def circular_util_shape(self, radius, ini_angle):
        direction = self.copy_tool.ui.array_dir_radio.get_value()      # CW or CCW
        angle = self.copy_tool.ui.angle_entry.get_value()
        array_size = int(self.copy_tool.ui.array_size_entry.get_value())

        circular_geo = []
        for i in range(array_size):
            angle_radians = math.radians(angle * i)
            if direction == 'CW':
                x = radius * math.cos(-angle_radians + ini_angle)
                y = radius * math.sin(-angle_radians + ini_angle)
            else:
                x = radius * math.cos(angle_radians + ini_angle)
                y = radius * math.sin(angle_radians + ini_angle)

            for shape in self.draw_app.get_selected():
                geo_sol = translate(shape.geo, x, y)
                # geo_sol = affinity.rotate(geo_sol, angle=(math.pi - angle_radians), use_radians=True)

                circular_geo.append(DrawToolShape(geo_sol))

        return circular_geo

    def select_shapes(self, pos):
        # list where we store the overlapped shapes under our mouse left click position
        over_shape_list = []

        try:
            _, closest_shape = self.storage.nearest(pos)
        except StopIteration:
            return ""

        over_shape_list.append(closest_shape)

        try:
            # if there is no shape under our click then deselect all shapes
            # it will not work for 3rd method of click selection
            if not over_shape_list:
                self.draw_app.selected = []
                self.draw_app.draw_shape_idx = -1
            else:
                # if there are shapes under our click then advance through the list of them, one at the time in a
                # circular way
                self.draw_app.draw_shape_idx = (AppGeoEditor.draw_shape_idx + 1) % len(over_shape_list)
                try:
                    obj_to_add = over_shape_list[int(AppGeoEditor.draw_shape_idx)]
                except IndexError:
                    return

                key_modifier = QtWidgets.QApplication.keyboardModifiers()
                if self.draw_app.app.options["global_mselect_key"] == 'Control':
                    # if CONTROL key is pressed then we add to the selected list the current shape but if it's
                    # already in the selected list, we removed it. Therefore, first click selects, second deselects.
                    if key_modifier == Qt.KeyboardModifier.ControlModifier:
                        if obj_to_add in self.draw_app.selected:
                            self.draw_app.selected.remove(obj_to_add)
                        else:
                            self.draw_app.selected.append(obj_to_add)
                    else:
                        self.draw_app.selected = []
                        self.draw_app.selected.append(obj_to_add)
                else:
                    if key_modifier == Qt.KeyboardModifier.ShiftModifier:
                        if obj_to_add in self.draw_app.selected:
                            self.draw_app.selected.remove(obj_to_add)
                        else:
                            self.draw_app.selected.append(obj_to_add)
                    else:
                        self.draw_app.selected = []
                        self.draw_app.selected.append(obj_to_add)

        except Exception as e:
            log.error("[ERROR] Something went bad. %s" % str(e))
            raise

    def draw_cursor_data(self, pos=None, delete=False):
        if self.cursor_data_control is False:
            self.draw_app.app.plotcanvas.text_cursor.text = ""
            return

        if pos is None:
            pos = self.draw_app.snap_x, self.draw_app.snap_y

        if delete:
            if self.draw_app.app.use_3d_engine:
                self.draw_app.app.plotcanvas.text_cursor.parent = None
                self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None
            return

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        x = pos[0]
        y = pos[1]
        try:
            length = abs(np.sqrt((pos[0] - self.points[-1][0]) ** 2 + (pos[1] - self.points[-1][1]) ** 2))
        except IndexError:
            length = self.draw_app.app.dec_format(0.0, self.draw_app.app.decimals)
        units = self.draw_app.app.app_units.lower()

        x_dec = str(self.draw_app.app.dec_format(x, self.draw_app.app.decimals)) if x else '0.0'
        y_dec = str(self.draw_app.app.dec_format(y, self.draw_app.app.decimals)) if y else '0.0'
        length_dec = str(self.draw_app.app.dec_format(length, self.draw_app.app.decimals)) if length else '0.0'

        l1_txt = 'X:   %s [%s]' % (x_dec, units)
        l2_txt = 'Y:   %s [%s]' % (y_dec, units)
        l3_txt = 'L:   %s [%s]' % (length_dec, units)
        cursor_text = '%s\n%s\n\n%s' % (l1_txt, l2_txt, l3_txt)

        if self.draw_app.app.use_3d_engine:
            new_pos = self.draw_app.app.plotcanvas.translate_coords_2((x, y))
            x, y, __, ___ = self.draw_app.app.plotcanvas.translate_coords((new_pos[0]+30, new_pos[1]))

            # text
            self.draw_app.app.plotcanvas.text_cursor.font_size = fsize
            self.draw_app.app.plotcanvas.text_cursor.text = cursor_text
            self.draw_app.app.plotcanvas.text_cursor.pos = x, y
            self.draw_app.app.plotcanvas.text_cursor.anchors = 'left', 'top'

            if self.draw_app.app.plotcanvas.text_cursor.parent is None:
                self.draw_app.app.plotcanvas.text_cursor.parent = self.draw_app.app.plotcanvas.view.scene

    def on_key(self, key):
        if key == 'C' or key == QtCore.Qt.Key.Key_C:
            self.cursor_data_control = not self.cursor_data_control

        # Jump to coords
        if key == QtCore.Qt.Key.Key_J or key == 'J':
            self.draw_app.app.on_jump_to()

        if key in [str(i) for i in range(10)] + ['.', ',', '+', '-', '/', '*'] or \
                key in [QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_0, QtCore.Qt.Key.Key_1, QtCore.Qt.Key.Key_2,
                        QtCore.Qt.Key.Key_3, QtCore.Qt.Key.Key_4, QtCore.Qt.Key.Key_5, QtCore.Qt.Key.Key_6,
                        QtCore.Qt.Key.Key_7, QtCore.Qt.Key.Key_8, QtCore.Qt.Key.Key_9, QtCore.Qt.Key.Key_Minus,
                        QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Comma, QtCore.Qt.Key.Key_Period,
                        QtCore.Qt.Key.Key_Slash, QtCore.Qt.Key.Key_Asterisk]:
            try:
                # VisPy keys
                if self.copy_tool.length == 0:
                    self.copy_tool.length = str(key.name)
                else:
                    self.copy_tool.length = str(self.copy_tool.length) + str(key.name)
            except AttributeError:
                # Qt keys
                if self.copy_tool.length == 0:
                    self.copy_tool.length = chr(key)
                else:
                    self.copy_tool.length = str(self.copy_tool.length) + chr(key)

        if key == 'Enter' or key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            if self.copy_tool.length != 0:
                target_length = self.copy_tool.length
                if target_length is None:
                    self.copy_tool.length = 0.0
                    return _("Failed.")

                first_pt = self.points[-1]
                last_pt = self.draw_app.app.mouse_pos

                seg_length = math.sqrt((last_pt[0] - first_pt[0])**2 + (last_pt[1] - first_pt[1])**2)
                if seg_length == 0.0:
                    return
                try:
                    new_x = first_pt[0] + (last_pt[0] - first_pt[0]) / seg_length * target_length
                    new_y = first_pt[1] + (last_pt[1] - first_pt[1]) / seg_length * target_length
                except ZeroDivisionError as err:
                    self.points = []
                    self.clean_up()
                    return '[ERROR_NOTCL] %s %s' % (_("Failed."), str(err).capitalize())

                if self.points[-1] != (new_x, new_y):
                    self.points.append((new_x, new_y))
                    self.draw_app.app.on_jump_to(custom_location=(new_x, new_y), fit_center=False)
                    self.destination = (new_x, new_y)
                    self.make()
                    self.draw_app.on_shape_complete()
                    self.draw_app.select_tool("select")
                    return "Done."

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        if self.draw_app.app.use_3d_engine:
            self.draw_app.app.plotcanvas.text_cursor.parent = None
            self.draw_app.app.plotcanvas.view.camera.zoom_callback = lambda *args: None

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.copy_tool.on_tab_close()


class FCText(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'text'
        self.draw_app = draw_app

        try:
            QtGui.QGuiApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.cursor = QtGui.QCursor(QtGui.QPixmap(self.draw_app.app.resource_location + '/aero_text.png'))
        QtGui.QGuiApplication.setOverrideCursor(self.cursor)

        self.app = draw_app.app

        self.draw_app.app.inform.emit(_("Click on 1st point ..."))
        self.origin = (0, 0)

        self.text_gui = TextInputTool(app=self.app, draw_app=self.draw_app)
        self.text_gui.run()
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        # Create new geometry
        dx = point[0]
        dy = point[1]

        if self.text_gui.text_path:
            try:
                self.geometry = DrawToolShape(translate(self.text_gui.text_path, xoff=dx, yoff=dy))
            except Exception as e:
                log.error("Font geometry is empty or incorrect: %s" % str(e))
                self.draw_app.app.inform.emit('[ERROR] %s: %s' %
                                              (_("Font not supported. Only Regular, Bold, Italic and BoldItalic are "
                                                 "supported. Error"), str(e)))
                self.text_gui.text_path = []
                # self.text_gui.hide_tool()
                self.draw_app.select_tool('select')
                self.draw_app.app.jump_signal.disconnect()
                return
        else:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s' % _("No text to add."))
            try:
                self.draw_app.app.jump_signal.disconnect()
            except (TypeError, AttributeError):
                pass
            return

        self.text_gui.text_path = []
        self.text_gui.hide_tool()
        self.complete = True
        self.draw_app.app.inform.emit('[success]%s' % _("Done."))

    def utility_geometry(self, data=None):
        """
        Temporary geometry on screen while using this tool.

        :param data: mouse position coords
        :return:
        """

        dx = data[0] - self.origin[0]
        dy = data[1] - self.origin[1]

        try:
            return DrawToolUtilityShape(translate(self.text_gui.text_path, xoff=dx, yoff=dy))
        except Exception:
            return

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCBuffer(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'buffer'

        # self.shape_buffer = self.draw_app.shape_buffer
        self.draw_app = draw_app
        self.app = draw_app.app

        self.draw_app.app.inform.emit(_("Create buffer geometry ..."))
        self.origin = (0, 0)
        self.buff_tool = BufferSelectionTool(self.app, self.draw_app)
        self.buff_tool.run()
        self.app.ui.notebook.setTabText(2, _("Buffer"))
        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])
        self.activate()

    def on_buffer(self):
        if not self.draw_app.selected:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Cancelled."), _("No shape selected.")))
            return

        try:
            buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value())
        except ValueError:
            # try to convert comma to decimal point. if it's still not working error message and return
            try:
                buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value().replace(',', '.'))
                self.buff_tool.ui.buffer_distance_entry.set_value(buffer_distance)
            except ValueError:
                self.app.inform.emit('[WARNING_NOTCL] %s' %
                                     _("Buffer distance value is missing or wrong format. Add it and retry."))
                return
        # the cb index start from 0 but the join styles for the buffer start from 1 therefore the adjustment
        # I populated the combobox such that the index coincide with the join styles value (whcih is really an INT)
        join_style = self.buff_tool.ui.buffer_corner_cb.currentIndex() + 1
        ret_val = self.buff_tool.buffer(buffer_distance, join_style)

        self.deactivate()
        if ret_val == 'fail':
            return
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def on_buffer_int(self):
        if not self.draw_app.selected:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Cancelled."), _("No shape selected.")))
            return

        try:
            buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value())
        except ValueError:
            # try to convert comma to decimal point. if it's still not working error message and return
            try:
                buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value().replace(',', '.'))
                self.buff_tool.ui.buffer_distance_entry.set_value(buffer_distance)
            except ValueError:
                self.app.inform.emit('[WARNING_NOTCL] %s' %
                                     _("Buffer distance value is missing or wrong format. Add it and retry."))
                return
        # the cb index start from 0 but the join styles for the buffer start from 1 therefore the adjustment
        # I populated the combobox such that the index coincide with the join styles value (whcih is really an INT)
        join_style = self.buff_tool.ui.buffer_corner_cb.currentIndex() + 1
        ret_val = self.buff_tool.buffer_int(buffer_distance, join_style)

        self.deactivate()
        if ret_val == 'fail':
            return
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def on_buffer_ext(self):
        if not self.draw_app.selected:
            self.draw_app.app.inform.emit('[WARNING_NOTCL] %s %s' % (_("Cancelled."), _("No shape selected.")))
            return

        try:
            buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value())
        except ValueError:
            # try to convert comma to decimal point. if it's still not working error message and return
            try:
                buffer_distance = float(self.buff_tool.ui.buffer_distance_entry.get_value().replace(',', '.'))
                self.buff_tool.ui.buffer_distance_entry.set_value(buffer_distance)
            except ValueError:
                self.draw_app.app.inform.emit('[WARNING_NOTCL] %s' %
                                              _("Buffer distance value is missing or wrong format. Add it and retry."))
                return
        # the cb index start from 0 but the join styles for the buffer start from 1 therefore the adjustment
        # I populated the combobox such that the index coincide with the join styles value (whcih is really an INT)
        join_style = self.buff_tool.ui.buffer_corner_cb.currentIndex() + 1
        ret_val = self.buff_tool.buffer_ext(buffer_distance, join_style)
        # self.app.ui.notebook.setTabText(2, _("Tools"))
        # self.draw_app.app.ui.splitter.setSizes([0, 1])

        self.deactivate()
        if ret_val == 'fail':
            return
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))

    def activate(self):
        self.buff_tool.ui.buffer_button.clicked.disconnect()
        self.buff_tool.ui.buffer_int_button.clicked.disconnect()
        self.buff_tool.ui.buffer_ext_button.clicked.disconnect()

        self.buff_tool.ui.buffer_button.clicked.connect(self.on_buffer)
        self.buff_tool.ui.buffer_int_button.clicked.connect(self.on_buffer_int)
        self.buff_tool.ui.buffer_ext_button.clicked.connect(self.on_buffer_ext)

    def deactivate(self):
        self.buff_tool.ui.buffer_button.clicked.disconnect()
        self.buff_tool.ui.buffer_int_button.clicked.disconnect()
        self.buff_tool.ui.buffer_ext_button.clicked.disconnect()

        self.buff_tool.ui.buffer_button.clicked.connect(self.buff_tool.on_buffer)
        self.buff_tool.ui.buffer_int_button.clicked.connect(self.buff_tool.on_buffer_int)
        self.buff_tool.ui.buffer_ext_button.clicked.connect(self.buff_tool.on_buffer_ext)
        self.complete = True
        self.draw_app.select_tool("select")

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()


class FCSimplification(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'simplify'

        self.draw_app = draw_app
        self.app = draw_app.app
        self.storage = self.draw_app.storage

        self.draw_app.app.inform.emit(_("Simplify geometry ..."))
        self.origin = (0, 0)
        self.simp_tool = SimplificationTool(self.app, self.draw_app)
        self.simp_tool.run()

        if self.draw_app.app.ui.splitter.sizes()[0] == 0:
            self.draw_app.app.ui.splitter.setSizes([1, 1])

    def click(self, point):
        for ____ in self.storage.get_objects():
            try:
                __, closest_shape = self.storage.nearest(point)
                self.draw_app.selected.append(closest_shape)
            except StopIteration:
                return ""
        self.draw_app.plot_all()

        last_sel_geo = self.draw_app.selected[-1].geo
        self.simp_tool.calculate_coordinates_vertex(last_sel_geo)

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()


class FCEraser(FCShapeTool):
    def __init__(self, draw_app):
        DrawTool.__init__(self, draw_app)
        self.name = 'eraser'
        self.draw_app = draw_app

        self.origin = None
        self.destination = None

        if len(self.draw_app.get_selected()) == 0:
            if self.draw_app.launched_from_shortcuts is True:
                self.draw_app.launched_from_shortcuts = False
            self.draw_app.app.inform.emit(_("Select a shape to act as deletion area ..."))
        else:
            self.draw_app.app.inform.emit(_("Click to pick-up the erase shape..."))

        self.geometry = []
        self.storage = self.draw_app.storage

        # Switch notebook to Properties page
        self.draw_app.app.ui.notebook.setCurrentWidget(self.draw_app.app.ui.properties_tab)
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

    def set_origin(self, origin):
        self.origin = origin

    def click(self, point):
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass
        self.draw_app.app.jump_signal.connect(lambda x: self.draw_app.update_utility_geometry(data=x))

        if len(self.draw_app.get_selected()) == 0:
            for ____ in self.storage.get_objects():
                try:
                    __, closest_shape = self.storage.nearest(point)
                    self.draw_app.selected.append(closest_shape)
                except StopIteration:
                    if len(self.draw_app.selected) > 0:
                        self.draw_app.app.inform.emit(_("Click to pick-up the erase shape..."))
                    return ""

        if len(self.draw_app.get_selected()) == 0:
            return _("Nothing to erase.")
        else:
            self.draw_app.app.inform.emit(_("Click to pick-up the erase shape..."))

        if self.origin is None:
            self.set_origin(point)
            self.draw_app.app.inform.emit(_("Click to erase ..."))
            return
        else:
            self.destination = point
            self.make()

            # self.draw_app.select_tool("select")
            return

    def make(self):
        eraser_sel_shapes = []

        # create the eraser shape from selection
        for eraser_shape in self.utility_geometry(data=self.destination).geo:
            temp_shape = eraser_shape.buffer(0.0000001)
            temp_shape = Polygon(temp_shape.exterior)
            eraser_sel_shapes.append(temp_shape)
        eraser_sel_shapes = unary_union(eraser_sel_shapes)

        for obj_shape in self.storage.get_objects():
            try:
                geometric_data = obj_shape.geo
                if eraser_sel_shapes.intersects(geometric_data):
                    obj_shape.geo = geometric_data.difference(eraser_sel_shapes)
            except KeyError:
                pass

        self.draw_app.delete_utility_geometry()
        self.draw_app.plot_all()
        self.draw_app.app.inform.emit('[success] %s' % _("Done."))
        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass

    def utility_geometry(self, data=None):
        """
        Temporary geometry on screen while using this tool.

        :param data:
        :return:
        """
        geo_list = []

        if self.origin is None:
            return None

        if len(self.draw_app.get_selected()) == 0:
            return None

        dx = data[0] - self.origin[0]
        dy = data[1] - self.origin[1]

        try:
            for geom in self.draw_app.get_selected():
                geo_list.append(translate(geom.geo, xoff=dx, yoff=dy))
        except AttributeError:
            self.draw_app.select_tool('select')
            self.draw_app.selected = []
            return
        return DrawToolUtilityShape(geo_list)

    def clean_up(self):
        self.draw_app.selected = []
        self.draw_app.plot_all()

        try:
            self.draw_app.app.jump_signal.disconnect()
        except (TypeError, AttributeError):
            pass


class FCPaint(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'paint'
        self.draw_app = draw_app
        self.app = draw_app.app

        self.draw_app.app.inform.emit(_("Create Paint geometry ..."))
        self.origin = (0, 0)
        self.draw_app.paint_tool.run()

    def clean_up(self):
        pass


class FCTransform(FCShapeTool):
    def __init__(self, draw_app):
        FCShapeTool.__init__(self, draw_app)
        self.name = 'transformation'

        self.draw_app = draw_app
        self.app = draw_app.app

        self.draw_app.app.inform.emit(_("Shape transformations ..."))
        self.origin = (0, 0)
        self.draw_app.transform_tool.run()

    def clean_up(self):
        pass


def distance(pt1, pt2):
    return np.sqrt((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2)


def mag(vec):
    return np.sqrt(vec[0] ** 2 + vec[1] ** 2)


def poly2rings(poly):
    return [poly.exterior] + [interior for interior in poly.interiors]


def get_shapely_list_bounds(geometry_list):
    xmin = np.Inf
    ymin = np.Inf
    xmax = -np.Inf
    ymax = -np.Inf

    for gs in geometry_list:
        try:
            gxmin, gymin, gxmax, gymax = gs.bounds
            xmin = min([xmin, gxmin])
            ymin = min([ymin, gymin])
            xmax = max([xmax, gxmax])
            ymax = max([ymax, gymax])
        except Exception as e:
            log.error("Tried to get bounds of empty geometry. --> %s" % str(e))

    return [xmin, ymin, xmax, ymax]
