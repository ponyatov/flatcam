# ##########################################################
# FlatCAM Evo: 2D Post-processing for Manufacturing        #
# File by:  Marius Adrian Stanciu (c)                      #
# Date:     11/12/2020                                     #
# License:  MIT Licence                                    #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import (VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCComboBox, RadioSet,
                                FCDoubleSpinner, FCCheckBox, OptionalInputSection)

import logging
from copy import deepcopy
import numpy as np

from shapely import Polygon, line_merge, MultiLineString, Point, simplify
from shapely.ops import unary_union

import gettext
import appTranslation as fcTranslate
import builtins

from appParsers.ParseGerber import Gerber
from matplotlib.backend_bases import KeyEvent as mpl_key_event
from camlib import flatten_shapely_geometry

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolFollow(AppTool, Gerber):

    optimal_found_sig = QtCore.pyqtSignal(float)

    def __init__(self, app):
        self.app = app
        self.decimals = self.app.decimals

        AppTool.__init__(self, app)
        Gerber.__init__(self, steps_per_circle=self.app.options["gerber_circle_steps"])

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = FollowUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        # disconnect flags
        self.area_sel_disconnect_flag = False

        self.first_click = False
        self.cursor_pos = None
        self.mouse_is_dragging = False

        self.mm = None
        self.mp = None
        self.mr = None
        self.kp = None

        self.sel_rect = []

        # store here the points for the "Polygon" area selection shape
        self.points = []
        # set this as True when in middle of drawing a "Polygon" area selection shape
        # it is made False by first click to signify that the shape is complete
        self.poly_drawn = False

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolFollow()")

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

        self.app.ui.notebook.setTabText(2, _("Follow"))

    def connect_signals_at_init(self):
        self.ui.level.toggled.connect(self.on_level_changed)
        self.ui.select_method_radio.activated_custom.connect(self.ui.on_selection)
        self.ui.generate_geometry_button.clicked.connect(self.on_generate_geometry_click)

    def set_tool_ui(self):
        self.units = self.app.app_units.upper()

        self.clear_ui(self.layout)
        self.ui = FollowUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        self.ui.select_method_radio.set_value('all')     # _("All")
        self.ui.area_shape_radio.set_value('square')

        self.sel_rect[:] = []
        self.points = []
        self.poly_drawn = False
        self.area_sel_disconnect_flag = False

        # SELECT THE CURRENT OBJECT
        obj = self.app.collection.get_active()
        if obj and obj.kind == 'gerber':
            obj_name = obj.obj_options['name']
            self.ui.object_combo.set_value(obj_name)

        # Set UI
        self.ui.simplify_cb.set_value(self.app.options["tools_follow_simplification"])
        self.ui.tol_entry.set_value(self.app.options["tools_follow_tolerance"])
        self.ui.union_cb.set_value(self.app.options["tools_follow_union"])

        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.change_level(app_mode)

        # SIGNALS
        self.ui.simplify_cb.stateChanged.connect(self.on_simplify_changed)
        self.ui.tol_entry.valueChanged.connect(self.on_tolerance_changed)
        self.ui.union_cb.stateChanged.connect(self.on_union_changed)

    def on_simplify_changed(self, checked):
        self.app.options["tools_follow_simplification"] = checked

    def on_tolerance_changed(self, value):
        self.app.options["tools_follow_tolerance"] = value

    def on_union_changed(self, checked):
        self.app.options["tools_follow_union"] = checked

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

            # Parameters section
            self.ui.gp_frame.hide()
            self.ui.param_label.hide()
        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                        QToolButton
                                        {
                                            color: red;
                                        }
                                        """)

            # Parameters section
            self.ui.gp_frame.show()
            self.ui.param_label.show()

    def on_generate_geometry_click(self):
        obj_name = self.ui.object_combo.currentText()

        # Get source object.
        try:
            obj = self.app.collection.get_by_name(obj_name)
        except Exception as e:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Could not retrieve object"), str(obj_name)))
            return "Could not retrieve object: %s with error: %s" % (obj_name, str(e))

        if obj is None:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Object not found"), str(obj_name)))
            return

        formatted_name = obj_name.rpartition('.')[0]
        if formatted_name == '':
            formatted_name = obj_name
        outname = '%s_follow' % formatted_name

        select_method = self.ui.select_method_radio.get_value()
        if select_method == 'all':  # _("All")
            self.follow_all(obj, outname)
        else:
            # disable the "notebook UI" until finished
            self.app.ui.notebook.setDisabled(True)

            self.app.inform.emit('[WARNING_NOTCL] %s' % _("Click the start point of the area."))

            if self.app.use_3d_engine:
                self.app.plotcanvas.graph_event_disconnect('mouse_press', self.app.on_mouse_click_over_plot)
                self.app.plotcanvas.graph_event_disconnect('mouse_move', self.app.on_mouse_move_over_plot)
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.app.on_mouse_click_release_over_plot)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.app.mp)
                self.app.plotcanvas.graph_event_disconnect(self.app.mm)
                self.app.plotcanvas.graph_event_disconnect(self.app.mr)

            self.mr = self.app.plotcanvas.graph_event_connect('mouse_release', self.on_mouse_release)
            self.mm = self.app.plotcanvas.graph_event_connect('mouse_move', self.on_mouse_move)
            self.kp = self.app.plotcanvas.graph_event_connect('key_press', self.on_key_press)

            # disconnect flags
            self.area_sel_disconnect_flag = True

    def follow_all(self, obj, outname):
        def job_thread(tool_obj):
            tool_obj.follow_geo(obj, outname)

        self.app.worker_task.emit({'fcn': job_thread, 'params': [self]})

    def follow_area(self):
        obj_name = self.ui.object_combo.currentText()

        # Get source object.
        try:
            obj = self.app.collection.get_by_name(obj_name)
        except Exception as e:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Could not retrieve object"), str(obj_name)))
            return "Could not retrieve object: %s with error: %s" % (obj_name, str(e))

        if obj is None:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Object not found"), str(obj_name)))
            return

        formatted_name = obj_name.rpartition('.')[0]
        if formatted_name == '':
            formatted_name = obj_name
        outname = '%s_follow' % formatted_name

        def job_thread(tool_obj):
            tool_obj.follow_geo_area(obj, outname)

        self.app.worker_task.emit({'fcn': job_thread, 'params': [self]})

    def follow_geo(self, followed_obj, outname):
        """
        Creates a geometry object "following" the gerber paths.

        :param followed_obj:    Gerber object for which to generate the follow geometry
        :type followed_obj:     AppObjects.FlatCAMGerber.GerberObject
        :param outname:         Nme of the resulting Geometry object
        :type outname:          str
        :return: None
        """

        should_union = self.ui.union_cb.get_value()
        should_simplify = self.ui.simplify_cb.get_value()
        simplify_tol = self.ui.tol_entry.get_value()

        def follow_init(new_obj, app_obj):
            if type(app_obj.defaults["tools_mill_tooldia"]) == float:
                tools_list = [app_obj.defaults["tools_mill_tooldia"]]
            else:
                try:
                    temp_tools = app_obj.defaults["tools_mill_tooldia"].split(",")
                    tools_list = [
                        float(eval(dia)) for dia in temp_tools if dia != ''
                    ]
                except Exception as e:
                    self.app.log.error("ToolFollow.follow_geo -> At least one tool diameter needed. -> %s" % str(e))
                    return 'fail'

            # store here the default data for Geometry Data
            new_data = {}

            for opt_key in app_obj.options:
                if opt_key.find('geometry' + "_") == 0:
                    oname = opt_key[len('geometry') + 1:]
                    new_data[oname] = app_obj.options[opt_key]
                if opt_key.find('tools_') == 0:
                    new_data[opt_key] = app_obj.options[opt_key]

            flattened_follow_geometry = flatten_shapely_geometry(followed_obj.follow_geometry)
            cleaned_flat_follow_geometry = [
                f for f in flattened_follow_geometry if not isinstance(f, Point) and not f.is_empty
            ]

            merged_geo = line_merge(MultiLineString(cleaned_flat_follow_geometry))
            if merged_geo and not merged_geo.is_empty:
                flattened_follow_geometry = flatten_shapely_geometry(merged_geo)

            followed_obj.follow_geometry = flattened_follow_geometry

            # Filter out empty geometries
            follow_geo = [
                g for g in followed_obj.follow_geometry
                if g and not g.is_empty and g.is_valid and g.geom_type != 'Point'
            ]

            if should_simplify and simplify_tol > 0.0:
                follow_geo = [simplify(f, tolerance=simplify_tol) for f in follow_geo]
            if should_union:
                follow_geo = unary_union(follow_geo)

            if not follow_geo:
                self.app.log.warning("ToolFollow.follow_geo() -> Empty Follow Geometry")
                return 'fail'

            new_obj.multigeo = True

            # Propagate options
            new_obj.obj_options["tools_mill_tooldia"] = app_obj.defaults["tools_mill_tooldia"]
            new_obj.solid_geometry = follow_geo
            new_obj.tools = {
                1: {
                    'tooldia': app_obj.dec_format(float(tools_list[0]), self.decimals),
                    'data': deepcopy(new_data),
                    'solid_geometry': new_obj.solid_geometry
                }
            }

        ret = self.app.app_obj.new_object("geometry", outname, follow_init)
        if ret == 'fail':
            self.app.inform.emit("[ERROR_NOTCL] %s" % _("Failed to create Follow Geometry."))
        else:
            self.app.inform.emit("[success] %s" % _("Done."))

    def follow_geo_area(self, followed_obj, outname):
        """
        Creates a geometry object "following" the gerber paths.

        :param followed_obj:    Gerber object for which to generate the follow geometry
        :type followed_obj:     AppObjects.FlatCAMGerber.GerberObject
        :param outname:         Nme of the resulting Geometry object
        :type outname:          str
        :return: None
        """
        should_union = self.ui.union_cb.get_value()
        should_simplify = self.ui.simplify_cb.get_value()
        simplify_tol = self.ui.tol_entry.get_value()

        def follow_init(new_obj, app_obj):
            new_obj.multigeo = True

            if type(app_obj.defaults["tools_mill_tooldia"]) == float:
                tools_list = [app_obj.defaults["tools_mill_tooldia"]]
            else:
                try:
                    temp_tools = app_obj.defaults["tools_mill_tooldia"].split(",")
                    tools_list = [
                        float(eval(dia)) for dia in temp_tools if dia != ''
                    ]
                except Exception as e:
                    app_obj.log.error("ToolFollow.follow_geo -> At least one tool diameter needed. -> %s" % str(e))
                    return 'fail'

            # store here the default data for Geometry Data
            new_data = {}

            for opt_key, opt_val in app_obj.options.items():
                if opt_key.find('geometry' + "_") == 0:
                    oname = opt_key[len('geometry') + 1:]
                    new_data[oname] = app_obj.options[opt_key]
                if opt_key.find('tools_') == 0:
                    new_data[opt_key] = app_obj.options[opt_key]

            # Propagate options
            new_obj.obj_options["tools_mill_tooldia"] = app_obj.defaults["tools_mill_tooldia"]
            new_data["tools_mill_tooldia"] = app_obj.defaults["tools_mill_tooldia"]

            target_geo = unary_union(followed_obj.follow_geometry)
            area_follow = target_geo.intersection(deepcopy(unary_union(self.sel_rect)))
            self.sel_rect[:] = []
            self.points = []

            area_follow = flatten_shapely_geometry(area_follow)
            cleaned_flat_follow_area = [
                f for f in area_follow if not isinstance(f, Point) and not f.is_empty
            ]

            merged_geo = line_merge(MultiLineString(cleaned_flat_follow_area))
            if merged_geo and not merged_geo.is_empty:
                area_follow = flatten_shapely_geometry(merged_geo)

            cleaned_area_follow = [g for g in area_follow if not g.is_empty and g.is_valid and g.geom_type != 'Point']

            if should_simplify and simplify_tol > 0.0:
                cleaned_area_follow = [simplify(f, tolerance=simplify_tol) for f in cleaned_area_follow]
            if should_union:
                cleaned_area_follow = unary_union(cleaned_area_follow)

            new_obj.multigeo = True
            new_obj.solid_geometry = deepcopy(cleaned_area_follow)
            new_obj.tools = {
                1: {
                    'tooldia': app_obj.dec_format(float(tools_list[0]), self.decimals),
                    'offset': 'Path',
                    'offset_value': 0.0,
                    'type': 'Rough',
                    'tool_type': 'C1',
                    'data': deepcopy(new_data),
                    'solid_geometry': new_obj.solid_geometry
                }
            }

        ret = self.app.app_obj.new_object("geometry", outname, follow_init)
        if ret == 'fail':
            self.app.inform.emit("[ERROR_NOTCL] %s" % _("Failed to create Follow Geometry."))
        else:
            self.app.inform.emit("[success] %s" % _("Done."))

    # To be called after clicking on the plot.
    def on_mouse_release(self, event):
        if self.app.use_3d_engine:
            event_pos = event.pos
            right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            right_button = 3

        try:
            x = float(event_pos[0])
            y = float(event_pos[1])
        except TypeError:
            return

        event_pos = (x, y)

        shape_type = self.ui.area_shape_radio.get_value()

        curr_pos = self.app.plotcanvas.translate_coords(event_pos)
        if self.app.grid_status():
            curr_pos = self.app.geo_editor.snap(curr_pos[0], curr_pos[1])

        x1, y1 = curr_pos[0], curr_pos[1]

        # do paint single only for left mouse clicks
        if event.button == 1:
            if shape_type == "square":
                if not self.first_click:
                    self.first_click = True
                    self.app.inform.emit('[WARNING_NOTCL] %s' % _("Click the end point of the area."))

                    self.cursor_pos = self.app.plotcanvas.translate_coords(event_pos)
                    if self.app.grid_status():
                        self.cursor_pos = self.app.geo_editor.snap(self.cursor_pos[0], self.cursor_pos[1])
                else:
                    self.app.inform.emit(_("Zone added. Click to start adding next zone or right click to finish."))
                    self.app.delete_selection_shape()

                    x0, y0 = self.cursor_pos[0], self.cursor_pos[1]
                    pt1 = (x0, y0)
                    pt2 = (x1, y0)
                    pt3 = (x1, y1)
                    pt4 = (x0, y1)

                    new_rectangle = Polygon([pt1, pt2, pt3, pt4])
                    self.sel_rect.append(new_rectangle)

                    # add a temporary shape on canvas
                    self.draw_tool_selection_shape(old_coords=(x0, y0), coords=(x1, y1))

                    self.first_click = False
                    return
            else:
                self.points.append((x1, y1))

                if len(self.points) > 1:
                    self.poly_drawn = True
                    self.app.inform.emit(_("Click on next Point or click right mouse button to complete ..."))

                return ""
        elif event.button == right_button and self.mouse_is_dragging is False:

            shape_type = self.ui.area_shape_radio.get_value()

            if shape_type == "square":
                self.first_click = False
            else:
                # if we finish to add a polygon
                if self.poly_drawn is True:
                    try:
                        # try to add the point where we last clicked if it is not already in the self.points
                        last_pt = (x1, y1)
                        if last_pt != self.points[-1]:
                            self.points.append(last_pt)
                    except IndexError:
                        pass

                    # we need to add a Polygon and a Polygon can be made only from at least 3 points
                    if len(self.points) > 2:
                        self.delete_moving_selection_shape()
                        pol = Polygon(self.points)
                        # do not add invalid polygons even if they are drawn by utility geometry
                        if pol.is_valid:
                            self.sel_rect.append(pol)
                            self.draw_selection_shape_polygon(points=self.points)
                            self.app.inform.emit(
                                _("Zone added. Click to start adding next zone or right click to finish."))

                    self.points = []
                    self.poly_drawn = False
                    return

            self.delete_tool_selection_shape()

            if self.app.use_3d_engine:
                self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_mouse_release)
                self.app.plotcanvas.graph_event_disconnect('mouse_move', self.on_mouse_move)
                self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
            else:
                self.app.plotcanvas.graph_event_disconnect(self.mr)
                self.app.plotcanvas.graph_event_disconnect(self.mm)
                self.app.plotcanvas.graph_event_disconnect(self.kp)

            self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press',
                                                                  self.app.on_mouse_click_over_plot)
            self.app.mm = self.app.plotcanvas.graph_event_connect('mouse_move',
                                                                  self.app.on_mouse_move_over_plot)
            self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                  self.app.on_mouse_click_release_over_plot)

            # disconnect flags
            self.area_sel_disconnect_flag = False
            # disable the "notebook UI" until finished
            self.app.ui.notebook.setDisabled(False)

            if len(self.sel_rect) == 0:
                return

            self.follow_area()

    # called on mouse move
    def on_mouse_move(self, event):
        shape_type = self.ui.area_shape_radio.get_value()

        if self.app.use_3d_engine:
            event_pos = event.pos
            event_is_dragging = event.is_dragging
            # right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            event_is_dragging = self.app.plotcanvas.is_dragging
            # right_button = 3

        try:
            x = float(event_pos[0])
            y = float(event_pos[1])
        except TypeError:
            return

        curr_pos = self.app.plotcanvas.translate_coords((x, y))

        # detect mouse dragging motion
        if event_is_dragging == 1:
            self.mouse_is_dragging = True
        else:
            self.mouse_is_dragging = False

        # update the cursor position
        if self.app.grid_status():
            # Update cursor
            curr_pos = self.app.geo_editor.snap(curr_pos[0], curr_pos[1])

            self.app.app_cursor.set_data(np.asarray([(curr_pos[0], curr_pos[1])]),
                                         symbol='++', edge_color=self.app.plotcanvas.cursor_color,
                                         edge_width=self.app.options["global_cursor_width"],
                                         size=self.app.options["global_cursor_size"])

        if self.cursor_pos is None:
            self.cursor_pos = (0, 0)

        self.app.dx = curr_pos[0] - float(self.cursor_pos[0])
        self.app.dy = curr_pos[1] - float(self.cursor_pos[1])

        # # update the positions on status bar
        # self.app.ui.position_label.setText("&nbsp;<b>X</b>: %.4f&nbsp;&nbsp;   "
        #                                    "<b>Y</b>: %.4f&nbsp;" % (curr_pos[0], curr_pos[1]))
        # self.app.ui.rel_position_label.setText("<b>Dx</b>: %.4f&nbsp;&nbsp;  <b>Dy</b>: "
        #                                        "%.4f&nbsp;&nbsp;&nbsp;&nbsp;" % (self.app.dx, self.app.dy))
        self.app.ui.update_location_labels(self.app.dx, self.app.dy, curr_pos[0], curr_pos[1])

        # units = self.app.app_units.lower()
        # self.app.plotcanvas.text_hud.text = \
        #     'Dx:\t{:<.4f} [{:s}]\nDy:\t{:<.4f} [{:s}]\n\nX:  \t{:<.4f} [{:s}]\nY:  \t{:<.4f} [{:s}]'.format(
        #         self.app.dx, units, self.app.dy, units, curr_pos[0], units, curr_pos[1], units)
        self.app.plotcanvas.on_update_text_hud(self.app.dx, self.app.dy, curr_pos[0], curr_pos[1])

        # draw the utility geometry
        if shape_type == "square":
            if self.first_click:
                self.app.delete_selection_shape()
                self.app.draw_moving_selection_shape(old_coords=(self.cursor_pos[0], self.cursor_pos[1]),
                                                     coords=(curr_pos[0], curr_pos[1]))
        else:
            self.delete_moving_selection_shape()
            self.draw_moving_selection_shape_poly(points=self.points, data=(curr_pos[0], curr_pos[1]))

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
            if self.area_sel_disconnect_flag is True:
                try:
                    if self.app.use_3d_engine:
                        self.app.plotcanvas.graph_event_disconnect('mouse_release', self.on_mouse_release)
                        self.app.plotcanvas.graph_event_disconnect('mouse_move', self.on_mouse_move)
                        self.app.plotcanvas.graph_event_disconnect('key_press', self.on_key_press)
                    else:
                        self.app.plotcanvas.graph_event_disconnect(self.mr)
                        self.app.plotcanvas.graph_event_disconnect(self.mm)
                        self.app.plotcanvas.graph_event_disconnect(self.kp)
                except Exception as e:
                    self.app.log.error("ToolFollow.on_key_press() _1 --> %s" % str(e))

                self.app.mp = self.app.plotcanvas.graph_event_connect('mouse_press',
                                                                      self.app.on_mouse_click_over_plot)
                self.app.mm = self.app.plotcanvas.graph_event_connect('mouse_move',
                                                                      self.app.on_mouse_move_over_plot)
                self.app.mr = self.app.plotcanvas.graph_event_connect('mouse_release',
                                                                      self.app.on_mouse_click_release_over_plot)
            self.points = []
            self.poly_drawn = False
            self.sel_rect[:] = []

            self.delete_moving_selection_shape()
            self.delete_tool_selection_shape()

            # disable the "notebook UI" until finished
            self.app.ui.notebook.setDisabled(False)


class FollowUI:

    pluginName = _("Follow")

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
        title_label = FCLabel("%s" % self.pluginName, size=16, bold=True)
        title_label.setToolTip(
            _("Create a Geometry object with\n"
              "toolpaths to cut through the middle of polygons.")
        )

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
        # ################################ The object to be followed ##################################################
        # #############################################################################################################
        self.obj_combo_label = FCLabel('%s' % _("Source Object"), color='darkorange', bold=True)
        self.obj_combo_label.setToolTip(
            _("A Gerber object to be followed.\n"
              "Create a Geometry object with a path\n"
              "following the Gerber traces.")
        )
        self.tools_box.addWidget(self.obj_combo_label)

        self.object_combo = FCComboBox()
        self.object_combo.setModel(self.app.collection)
        self.object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.object_combo.is_last = True

        self.tools_box.addWidget(self.object_combo)

        # #############################################################################################################
        # COMMON PARAMETERS Frame
        # #############################################################################################################
        self.param_label = FCLabel('%s' % _("Parameters"), color='blue', bold=True)
        self.param_label.setToolTip(_("Parameters that are common for all tools."))
        self.tools_box.addWidget(self.param_label)

        self.gp_frame = FCFrame()
        self.tools_box.addWidget(self.gp_frame)

        grid0 = GLay(v_spacing=5, h_spacing=3)
        self.gp_frame.setLayout(grid0)

        # Simplification
        self.simplify_cb = FCCheckBox(_("Simplify"))
        self.simplify_cb.setToolTip(
            _("If checked, the toolpaths will be simplified with the given tolerance.")
        )
        self.tol_label = FCLabel('%s:' % _('Tolerance'))
        self.tol_label.setToolTip(
            _("The tolerance of the simplification.")
        )
        self.tol_entry = FCDoubleSpinner()
        self.tol_entry.set_range(0.0, 10000.0)
        self.tol_entry.set_precision(self.decimals)
        self.tol_entry.setSingleStep(0.01)

        self.simp_optional = OptionalInputSection(self.simplify_cb, [self.tol_label, self.tol_entry])

        grid0.addWidget(self.simplify_cb, 0, 0, 1, 2)
        grid0.addWidget(self.tol_label, 2, 0)
        grid0.addWidget(self.tol_entry, 2, 1)

        # UNION
        self.union_cb = FCCheckBox(_("Union"))
        self.union_cb.setToolTip(
            _("If checked, the toolpaths will be joined into a Union.")
        )

        grid0.addWidget(self.union_cb, 4, 0, 1, 2)

        # Polygon selection
        self.select_label = FCLabel('%s:' % _('Selection'))
        self.select_label.setToolTip(
            _("Selection of area to be processed.\n"
              "- 'All Polygons' - the process will start after click.\n"
              "- 'Area Selection' - left mouse click to start selection of the area to be processed.")
        )

        self.select_method_radio = RadioSet([{'label': _("All"), 'value': 'all'},
                                             {'label': _("Area Selection"), 'value': 'area'}])

        grid0.addWidget(self.select_label, 6, 0)
        grid0.addWidget(self.select_method_radio, 6, 1)

        # Area Selection shape
        self.area_shape_label = FCLabel('%s:' % _("Shape"))
        self.area_shape_label.setToolTip(
            _("The kind of selection shape used for area selection.")
        )

        self.area_shape_radio = RadioSet([{'label': _("Square"), 'value': 'square'},
                                          {'label': _("Polygon"), 'value': 'polygon'}])

        grid0.addWidget(self.area_shape_label, 8, 0)
        grid0.addWidget(self.area_shape_radio, 8, 1)

        self.area_shape_label.hide()
        self.area_shape_radio.hide()

        self.generate_geometry_button = FCButton("%s" % _("Generate Geometry"), bold=True)
        self.generate_geometry_button.setIcon(QtGui.QIcon(self.app.resource_location + '/geometry32.png'))
        self.generate_geometry_button.setToolTip(_("Generate a 'Follow' geometry.\n"
                                                   "This means that it will cut through\n"
                                                   "the middle of the trace."))
        self.tools_box.addWidget(self.generate_geometry_button)

        self.tools_box.addStretch(1)

        # ## Reset Tool
        self.reset_button = FCButton(_("Reset Tool"), bold=True)
        self.reset_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reset32.png'))
        self.reset_button.setToolTip(
            _("Will reset the tool parameters.")
        )
        self.tools_box.addWidget(self.reset_button)
        # ############################ FINISHED GUI ###################################
        # #############################################################################

    def on_selection(self, val):
        if val == 'area':  # _("Area Selection")
            self.area_shape_label.show()
            self.area_shape_radio.show()
        else:   # All
            self.area_shape_label.hide()
            self.area_shape_radio.hide()

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
