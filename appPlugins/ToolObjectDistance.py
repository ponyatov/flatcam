# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 09/29/2019                                         #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCEntry, FCComboBox2

import logging
from copy import deepcopy
import math

from shapely import Point, MultiPolygon
from shapely.ops import nearest_points, unary_union

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ObjectDistance(AppTool):

    def __init__(self, app):
        AppTool.__init__(self, app)

        self.app = app
        self.canvas = self.app.plotcanvas
        self.units = self.app.app_units.lower()
        self.decimals = self.app.decimals

        self.active = False
        self.original_call_source = None

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = ObjectDistanceUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        self.h_point = (0, 0)

    def run(self, toggle=False):
        # if the plugin was already launched do not do it again
        if self.active is True:
            return

        if self.app.plugin_tab_locked is True:
            return

        # if the splitter is hidden, display it
        if self.app.ui.splitter.sizes()[0] == 0:
            self.app.ui.splitter.setSizes([1, 1])

        if toggle:
            pass

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

        # Remove anything else in the appGUI
        self.app.ui.plugin_scroll_area.takeWidget()

        # Put oneself in the appGUI
        self.app.ui.plugin_scroll_area.setWidget(self)

        # Switch notebook to tool page
        self.app.ui.notebook.setCurrentWidget(self.app.ui.plugin_tab)

        self.set_tool_ui()
        self.app.ui.notebook.setTabText(2, _("Object Distance"))

        # activate the plugin
        self.activate_measure_tool()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='Shift+M', **kwargs)

    def connect_signals_at_init(self):
        self.ui.measure_btn.clicked.connect(self.activate_measure_tool)
        self.ui.jump_hp_btn.clicked.connect(self.on_jump_to_half_point)
        self.ui.reset_button.clicked.connect(self.set_tool_ui)
        self.ui.distance_type_combo.currentIndexChanged.connect(self.on_didstance_type_changed)

    def set_tool_ui(self):
        self.units = self.app.app_units.lower()

        # initial view of the layout
        self.init_plugin()

    def init_plugin(self):
        self.ui.start_entry.set_value('(0, 0)')
        self.ui.stop_entry.set_value('(0, 0)')

        self.ui.distance_x_entry.set_value('0.0')
        self.ui.distance_y_entry.set_value('0.0')
        self.ui.angle_entry.set_value('0.0')
        self.ui.total_distance_entry.set_value('0.0')
        self.ui.half_point_entry.set_value('(0, 0)')

        self.ui.jump_hp_btn.setDisabled(True)

        self.active = True

    def on_didstance_type_changed(self):
        self.init_plugin()

    def activate_measure_tool(self):
        # ENABLE the Measuring TOOL
        self.ui.jump_hp_btn.setDisabled(False)

        self.units = self.app.app_units.lower()
        self.original_call_source = deepcopy(self.app.call_source)

        measuring_type = self.ui.distance_type_combo.get_value()

        if measuring_type == 0:      # 0 is "nearest points"
            if self.app.call_source == 'app':
                first_pos, last_pos = self.measure_nearest_in_app()
            elif self.app.call_source == 'geo_editor':
                first_pos, last_pos = self.measure_nearest_in_geo_editor()
            elif self.app.call_source == 'exc_editor':
                first_pos, last_pos = self.measure_nearest_in_exc_editor()
            elif self.app.call_source == 'grb_editor':
                first_pos, last_pos = self.measure_nearest_in_grb_editor()
            else:
                first_pos, last_pos = Point((0, 0)), Point((0, 0))
        else:
            if self.app.call_source == 'app':
                first_pos, last_pos = self.measure_center_in_app()
            elif self.app.call_source == 'geo_editor':
                first_pos, last_pos = self.measure_center_in_geo_editor()
            elif self.app.call_source == 'exc_editor':
                first_pos, last_pos = self.measure_center_in_exc_editor()
            elif self.app.call_source == 'grb_editor':
                first_pos, last_pos = self.measure_center_in_grb_editor()
            else:
                first_pos, last_pos = Point((0, 0)), Point((0, 0))

        if first_pos == "fail":
            return

        # self.ui.start_entry.set_value("(%.*f, %.*f)" % (self.decimals, first_pos.x, self.decimals, first_pos.y))
        # self.ui.stop_entry.set_value("(%.*f, %.*f)" % (self.decimals, last_pos.x, self.decimals, last_pos.y))

        # update start point
        val_start = self.update_start(first_pos)
        self.display_start(val_start)

        # update end point
        val_stop = self.update_end_point(last_pos)
        self.display_end(val_stop)

        # update deltas
        dx, dy = self.update_deltas(first_pt=first_pos, second_pt=last_pos)
        self.display_deltas(dx, dy)

        # update angle
        angle_val = self.update_angle(dx=dx, dy=dy)
        self.display_angle(angle_val)

        # update the total distance
        d = self.update_distance(dx, dy)
        self.display_distance(d)

        self.h_point = self.update_half_distance(first_pos, last_pos, dx, dy)
        if measuring_type == 0:  # 0 is "nearest points"
            if d != 0:
                self.display_half_distance(self.h_point)
            else:
                self.display_half_distance((0.0, 0.0))
                intersect_loc = "(%.*f, %.*f)" % (self.decimals, self.h_point[0], self.decimals, self.h_point[1])
                msg = '[WARNING_NOTCL] %s: %s' % (_("Objects intersects or touch at"), intersect_loc)
                self.app.inform.emit(msg)
        else:
            self.display_half_distance(self.h_point)

        self.active = False

    def measure_nearest_in_app(self):
        selected_objs = self.app.collection.get_selected()
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        geo_first = selected_objs[0].solid_geometry
        geo_second = selected_objs[1].solid_geometry
        if isinstance(selected_objs[0].solid_geometry, list):
            try:
                geo_first = MultiPolygon(geo_first)
            except Exception:
                geo_first = unary_union(geo_first)
        if isinstance(selected_objs[1].solid_geometry, list):
            try:
                geo_second = MultiPolygon(geo_second)
            except Exception:
                geo_second = unary_union(geo_second)

        first_pos, last_pos = nearest_points(geo_first, geo_second)
        return first_pos, last_pos

    def measure_nearest_in_geo_editor(self):
        selected_objs = self.app.geo_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"
        first_pos, last_pos = nearest_points(selected_objs[0].geo, selected_objs[1].geo)
        return first_pos, last_pos

    def measure_nearest_in_grb_editor(self):
        selected_objs = self.app.grb_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        first_pos, last_pos = nearest_points(selected_objs[0].geo['solid'], selected_objs[1].geo['solid'])
        return first_pos, last_pos

    def measure_nearest_in_exc_editor(self):
        selected_objs = self.app.exc_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        # the objects are really MultiLinesStrings made out of 2 lines in cross shape
        xmin, ymin, xmax, ymax = selected_objs[0].geo.bounds
        first_geo_radius = (xmax - xmin) / 2
        first_geo_center = Point(xmin + first_geo_radius, ymin + first_geo_radius)
        first_geo = first_geo_center.buffer(first_geo_radius)

        # the objects are really MultiLinesStrings made out of 2 lines in cross shape
        xmin, ymin, xmax, ymax = selected_objs[1].geo.bounds
        last_geo_radius = (xmax - xmin) / 2
        last_geo_center = Point(xmin + last_geo_radius, ymin + last_geo_radius)
        last_geo = last_geo_center.buffer(last_geo_radius)

        first_pos, last_pos = nearest_points(first_geo, last_geo)
        return first_pos, last_pos

    def measure_center_in_app(self):
        selected_objs = self.app.collection.get_selected()
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        geo_first = selected_objs[0].solid_geometry
        geo_second = selected_objs[1].solid_geometry
        if isinstance(selected_objs[0].solid_geometry, list):
            try:
                geo_first = MultiPolygon(geo_first)
            except Exception:
                geo_first = unary_union(geo_first)
        if isinstance(selected_objs[1].solid_geometry, list):
            try:
                geo_second = MultiPolygon(geo_second)
            except Exception:
                geo_second = unary_union(geo_second)

        first_bounds = geo_first.bounds     # xmin, ymin, xmax, ymax
        first_center_x = first_bounds[0] + (first_bounds[2] - first_bounds[0]) / 2
        first_center_y = first_bounds[1] + (first_bounds[3] - first_bounds[1]) / 2
        second_bounds = geo_second.bounds   # xmin, ymin, xmax, ymax
        second_center_x = second_bounds[0] + (second_bounds[2] - second_bounds[0]) / 2
        second_center_y = second_bounds[1] + (second_bounds[3] - second_bounds[1]) / 2
        return Point((first_center_x, first_center_y)), Point((second_center_x, second_center_y))

    def measure_center_in_geo_editor(self):
        selected_objs = self.app.geo_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"
        geo_first = selected_objs[0].geo
        geo_second = selected_objs[1].geo

        first_bounds = geo_first.bounds  # xmin, ymin, xmax, ymax
        first_center_x = first_bounds[0] + (first_bounds[2] - first_bounds[0]) / 2
        first_center_y = first_bounds[1] + (first_bounds[3] - first_bounds[1]) / 2
        second_bounds = geo_second.bounds  # xmin, ymin, xmax, ymax
        second_center_x = second_bounds[0] + (second_bounds[2] - second_bounds[0]) / 2
        second_center_y = second_bounds[1] + (second_bounds[3] - second_bounds[1]) / 2
        return Point((first_center_x, first_center_y)), Point((second_center_x, second_center_y))

    def measure_center_in_grb_editor(self):
        selected_objs = self.app.grb_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        geo_first = selected_objs[0].geo['solid']
        geo_second = selected_objs[1].geo['solid']

        first_bounds = geo_first.bounds  # xmin, ymin, xmax, ymax
        first_center_x = first_bounds[0] + (first_bounds[2] - first_bounds[0]) / 2
        first_center_y = first_bounds[1] + (first_bounds[3] - first_bounds[1]) / 2
        second_bounds = geo_second.bounds  # xmin, ymin, xmax, ymax
        second_center_x = second_bounds[0] + (second_bounds[2] - second_bounds[0]) / 2
        second_center_y = second_bounds[1] + (second_bounds[3] - second_bounds[1]) / 2
        return Point((first_center_x, first_center_y)), Point((second_center_x, second_center_y))

    def measure_center_in_exc_editor(self):
        selected_objs = self.app.exc_editor.selected
        if len(selected_objs) != 2:
            self.app.inform.emit('[WARNING_NOTCL] %s %s' %
                                 (_("Select two objects and no more. Currently the selection has objects: "),
                                  str(len(selected_objs))))
            return "fail", "fail"

        # the objects are really MultiLinesStrings made out of 2 lines in cross shape
        xmin, ymin, xmax, ymax = selected_objs[0].geo.bounds
        first_geo_radius = (xmax - xmin) / 2
        first_geo_center = Point(xmin + first_geo_radius, ymin + first_geo_radius)
        geo_first = first_geo_center.buffer(first_geo_radius)

        # the objects are really MultiLinesStrings made out of 2 lines in cross shape
        xmin, ymin, xmax, ymax = selected_objs[1].geo.bounds
        last_geo_radius = (xmax - xmin) / 2
        last_geo_center = Point(xmin + last_geo_radius, ymin + last_geo_radius)
        geo_second = last_geo_center.buffer(last_geo_radius)

        first_bounds = geo_first.bounds  # xmin, ymin, xmax, ymax
        first_center_x = first_bounds[0] + (first_bounds[2] - first_bounds[0]) / 2
        first_center_y = first_bounds[1] + (first_bounds[3] - first_bounds[1]) / 2
        second_bounds = geo_second.bounds  # xmin, ymin, xmax, ymax
        second_center_x = second_bounds[0] + (second_bounds[2] - second_bounds[0]) / 2
        second_center_y = second_bounds[1] + (second_bounds[3] - second_bounds[1]) / 2
        return Point((first_center_x, first_center_y)), Point((second_center_x, second_center_y))

    def on_jump_to_half_point(self):
        self.app.on_jump_to(custom_location=self.h_point)
        self.app.inform.emit('[success] %s: %s' %
                             (_("Jumped to the half point between the two selected objects"),
                              "(%.*f, %.*f)" % (self.decimals, self.h_point[0], self.decimals, self.h_point[1])))

    def update_angle(self, dx, dy):
        try:
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360
        except Exception as e:
            self.app.log.error("ObjectDistance.update_angle() -> %s" % str(e))
            return None
        return angle

    def display_angle(self, val):
        if val:
            self.ui.angle_entry.set_value(str(self.app.dec_format(val, self.decimals)))

    def update_start(self, pt):
        return self.app.dec_format(pt.x, self.decimals), self.app.dec_format(pt.y, self.decimals)

    def display_start(self, val):
        if val:
            self.ui.start_entry.set_value(str(val))

    def update_end_point(self, pt):
        # update the end point value
        return self.app.dec_format(pt.x, self.decimals), self.app.dec_format(pt.y, self.decimals)

    def display_end(self, val):
        if val:
            self.ui.stop_entry.set_value(str(val))

    @staticmethod
    def update_deltas(first_pt, second_pt):
        dx = first_pt.x - second_pt.x
        dy = first_pt.y - second_pt.y
        return dx, dy

    def display_deltas(self, dx, dy):
        if dx:
            self.ui.distance_x_entry.set_value(str(self.app.dec_format(abs(dx), self.decimals)))
        if dy:
            self.ui.distance_y_entry.set_value(str(self.app.dec_format(abs(dy), self.decimals)))

    @staticmethod
    def update_distance(dx, dy):
        return math.sqrt(dx ** 2 + dy ** 2)

    def display_distance(self, val):
        if val:
            self.ui.total_distance_entry.set_value('%.*f' % (self.decimals, abs(val)))

    @staticmethod
    def update_half_distance(first_pos, last_pos, dx, dy):
        return min(first_pos.x, last_pos.x) + (abs(dx) / 2), min(first_pos.y, last_pos.y) + (abs(dy) / 2)

    def display_half_distance(self, val):
        if val:
            new_val = (
                self.app.dec_format(val[0], self.decimals),
                self.app.dec_format(val[1], self.decimals)
            )
            self.ui.half_point_entry.set_value(str(new_val))

    def on_plugin_cleanup(self):
        self.active = False
        self.app.call_source = self.original_call_source
        self.app.inform.emit('%s' % _("Done."))


class ObjectDistanceUI:

    pluginName = _("Object Distance")

    def __init__(self, layout, app):
        self.app = app
        self.decimals = self.app.decimals
        self.layout = layout
        self.units = self.app.app_units.lower()

        # ## Title
        title_label = FCLabel("<font size=4><b>%s</b></font><br>" % self.pluginName)
        self.layout.addWidget(title_label)

        # #############################################################################################################
        # Parameters Frame
        # #############################################################################################################
        self.param_label = FCLabel('%s' % _("Parameters"), color='blue', bold=True)
        self.param_label.setToolTip(
            _("Parameters used for this tool.")
        )
        self.layout.addWidget(self.param_label)

        par_frame = FCFrame()
        self.layout.addWidget(par_frame)

        param_grid = GLay(v_spacing=5, h_spacing=3)
        par_frame.setLayout(param_grid)

        # Distance Type

        self.distance_type_label = FCLabel("%s:" % _("Type"))
        self.distance_type_label.setToolTip(
            _("The type of distance to be calculated.\n"
              "- Nearest points - minimal distance between objects\n"
              "- Center points - distance between the center of the bounding boxes")
        )

        self.distance_type_combo = FCComboBox2()
        self.distance_type_combo.addItems([_("Nearest points"), _("Center points")])
        param_grid.addWidget(self.distance_type_label, 0, 0)
        param_grid.addWidget(self.distance_type_combo, 0, 1)

        # #############################################################################################################
        # Coordinates Frame
        # #############################################################################################################
        self.coords_label = FCLabel('%s' % _("Coordinates"), color='green', bold=True)
        self.layout.addWidget(self.coords_label)

        coords_frame = FCFrame()
        self.layout.addWidget(coords_frame)

        coords_grid = GLay(v_spacing=5, h_spacing=3)
        coords_frame.setLayout(coords_grid)

        # separator_line = QtWidgets.QFrame()
        # separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        # separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        # grid0.addWidget(separator_line, 6, 0, 1, 2)

        # Start Point
        self.start_label = FCLabel("%s:" % _('Start point'))
        self.start_label.setToolTip(_("This is measuring Start point coordinates."))

        self.start_entry = FCEntry()
        self.start_entry.setReadOnly(True)
        self.start_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.start_entry.setToolTip(_("This is measuring Start point coordinates."))

        coords_grid.addWidget(self.start_label, 0, 0)
        coords_grid.addWidget(self.start_entry, 0, 1)
        coords_grid.addWidget(FCLabel("%s" % self.units), 0, 2)

        # End Point
        self.stop_label = FCLabel("%s:" % _('End point'))
        self.stop_label.setToolTip(_("This is the measuring Stop point coordinates."))

        self.stop_entry = FCEntry()
        self.stop_entry.setReadOnly(True)
        self.stop_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.stop_entry.setToolTip(_("This is the measuring Stop point coordinates."))

        coords_grid.addWidget(self.stop_label, 2, 0)
        coords_grid.addWidget(self.stop_entry, 2, 1)
        coords_grid.addWidget(FCLabel("%s" % self.units), 2, 2)

        # #############################################################################################################
        # Coordinates Frame
        # #############################################################################################################
        self.res_label = FCLabel('%s' % _("Results"), color='red', bold=True)
        self.layout.addWidget(self.res_label)

        res_frame = FCFrame()
        self.layout.addWidget(res_frame)

        res_grid = GLay(v_spacing=5, h_spacing=3)
        res_frame.setLayout(res_grid)

        # DX distance
        self.distance_x_label = FCLabel('%s:' % _("Dx"))
        self.distance_x_label.setToolTip(_("This is the distance measured over the X axis."))

        self.distance_x_entry = FCEntry()
        self.distance_x_entry.setReadOnly(True)
        self.distance_x_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.distance_x_entry.setToolTip(_("This is the distance measured over the X axis."))

        res_grid.addWidget(self.distance_x_label, 0, 0)
        res_grid.addWidget(self.distance_x_entry, 0, 1)
        res_grid.addWidget(FCLabel("%s" % self.units), 0, 2)

        # DY distance
        self.distance_y_label = FCLabel('%s:' % _("Dy"))
        self.distance_y_label.setToolTip(_("This is the distance measured over the Y axis."))

        self.distance_y_entry = FCEntry()
        self.distance_y_entry.setReadOnly(True)
        self.distance_y_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.distance_y_entry.setToolTip(_("This is the distance measured over the Y axis."))

        res_grid.addWidget(self.distance_y_label, 2, 0)
        res_grid.addWidget(self.distance_y_entry, 2, 1)
        res_grid.addWidget(FCLabel("%s" % self.units), 2, 2)

        # Angle
        self.angle_label = FCLabel('%s:' % _("Angle"))
        self.angle_label.setToolTip(_("This is orientation angle of the measuring line."))

        self.angle_entry = FCEntry()
        self.angle_entry.setReadOnly(True)
        self.angle_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.angle_entry.setToolTip(_("This is orientation angle of the measuring line."))

        res_grid.addWidget(self.angle_label, 4, 0)
        res_grid.addWidget(self.angle_entry, 4, 1)
        res_grid.addWidget(FCLabel("%s" % "°"), 4, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        res_grid.addWidget(separator_line, 6, 0, 1, 3)

        # Total Distance
        self.total_distance_label = FCLabel('%s:' % _('DISTANCE'), bold=True)
        self.total_distance_label.setToolTip(_("This is the point to point Euclidian distance."))

        self.total_distance_entry = FCEntry()
        self.total_distance_entry.setReadOnly(True)
        self.total_distance_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                                               QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.total_distance_entry.setToolTip(_("This is the point to point Euclidian distance."))

        res_grid.addWidget(self.total_distance_label, 8, 0)
        res_grid.addWidget(self.total_distance_entry, 8, 1)
        res_grid.addWidget(FCLabel("%s" % self.units), 8, 2)
        
        # Half Point
        self.half_point_label = FCLabel('%s:' % _('Half Point'), bold=True)
        self.half_point_label.setToolTip(_("This is the middle point of the point to point Euclidean distance."))

        self.half_point_entry = FCEntry()
        self.half_point_entry.setReadOnly(True)
        self.half_point_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.half_point_entry.setToolTip(_("This is the middle point of the point to point Euclidean distance."))

        res_grid.addWidget(self.half_point_label, 10, 0)
        res_grid.addWidget(self.half_point_entry, 10, 1)
        res_grid.addWidget(FCLabel("%s" % self.units), 10, 2)

        # Buttons
        self.measure_btn = FCButton(_("Measure"))
        self.layout.addWidget(self.measure_btn)

        self.jump_hp_btn = FCButton(_("Jump to Half Point"))
        self.jump_hp_btn.setDisabled(True)
        self.layout.addWidget(self.jump_hp_btn)

        GLay.set_common_column_size([param_grid, coords_grid, res_grid], 0)

        self.layout.addStretch(1)

        # ## Reset Tool
        self.reset_button = FCButton(_("Reset Tool"), bold=True)
        self.reset_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reset32.png'))
        self.reset_button.setToolTip(
            _("Will reset the tool parameters.")
        )
        self.layout.addWidget(self.reset_button)
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
