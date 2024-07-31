# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# Author: Dennis Hayrullin (c)                             #
# Date: 2016                                               #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtCore, QtGui

import logging
from appGUI.VisPyCanvas import VisPyCanvas, Color
from appGUI.VisPyVisuals import ShapeGroup, ShapeCollection, TextCollection, TextGroup, Cursor
from vispy.scene.visuals import InfiniteLine, Line, Rectangle, Text

import gettext
import appTranslation as fcTranslate
import builtins

import numpy as np
from vispy.geometry import Rect

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class PlotCanvas(QtCore.QObject, VisPyCanvas):
    """
    Class handling the plotting area in the application.
    """

    def __init__(self, fcapp):
        """
        The constructor configures the VisPy figure that
        will contain all plots, creates the base axes and connects
        events to the plotting area.

        :rtype: PlotCanvas
        """

        # super(PlotCanvas, self).__init__()
        # QtCore.QObject.__init__(self)
        # VisPyCanvas.__init__(self)
        super().__init__()

        # VisPyCanvas does not allow new attributes. Override.
        self.unfreeze()

        self.fcapp = fcapp

        settings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if settings.contains("theme"):
            theme = settings.value('theme', type=str)
        else:
            theme = 'default'

        if settings.contains("dark_canvas"):
            dark_canvas = settings.value('dark_canvas', type=bool)
        else:
            dark_canvas = False

        if (theme == 'default' or theme == 'light') and not dark_canvas:
            self.line_color = (0.3, 0.0, 0.0, 1.0)
            # self.rect_hud_color = Color('#0000FF10')
            self.rect_hud_color = Color('#80808040')
            self.text_hud_color = 'black'
        else:
            self.line_color = (0.4, 0.4, 0.4, 1.0)
            self.rect_hud_color = Color('#80808040')
            self.text_hud_color = 'white'

        # workspace lines; I didn't use the rectangle because I didn't want to add another VisPy Node,
        # which might decrease performance
        # self.b_line, self.r_line, self.t_line, self.l_line = None, None, None, None
        self.workspace_line = None

        self.pagesize_dict = {}
        self.pagesize_dict.update(
            {
                'A0': (841, 1189),
                'A1': (594, 841),
                'A2': (420, 594),
                'A3': (297, 420),
                'A4': (210, 297),
                'A5': (148, 210),
                'A6': (105, 148),
                'A7': (74, 105),
                'A8': (52, 74),
                'A9': (37, 52),
                'A10': (26, 37),

                'B0': (1000, 1414),
                'B1': (707, 1000),
                'B2': (500, 707),
                'B3': (353, 500),
                'B4': (250, 353),
                'B5': (176, 250),
                'B6': (125, 176),
                'B7': (88, 125),
                'B8': (62, 88),
                'B9': (44, 62),
                'B10': (31, 44),

                'C0': (917, 1297),
                'C1': (648, 917),
                'C2': (458, 648),
                'C3': (324, 458),
                'C4': (229, 324),
                'C5': (162, 229),
                'C6': (114, 162),
                'C7': (81, 114),
                'C8': (57, 81),
                'C9': (40, 57),
                'C10': (28, 40),

                # American paper sizes
                'LETTER': (8.5*25.4, 11*25.4),
                'LEGAL': (8.5*25.4, 14*25.4),
                'ELEVENSEVENTEEN': (11*25.4, 17*25.4),

                # From https://en.wikipedia.org/wiki/Paper_size
                'JUNIOR_LEGAL': (5*25.4, 8*25.4),
                'HALF_LETTER': (5.5*25.4, 8*25.4),
                'GOV_LETTER': (8*25.4, 10.5*25.4),
                'GOV_LEGAL': (8.5*25.4, 13*25.4),
                'LEDGER': (17*25.4, 11*25.4),
            }
        )

        # <VisPyCanvas>
        self.create_native()
        self.native.setParent(self.fcapp.ui)

        axis_default_color = self.fcapp.options['global_axis_color']
        self.axis_transparency = 0.8

        axis_color = self.color_hex2tuple(axis_default_color)
        axis_color = axis_color[0], axis_color[1], axis_color[2], self.axis_transparency

        # ## AXIS # ##
        # self.v_line = InfiniteLine(pos=0, color=(0.70, 0.3, 0.3, 0.8), vertical=True,
        #                            parent=self.view.scene)

        self.v_line = InfiniteLine(pos=0, color=axis_color, vertical=True, line_width=1.5,
                                   parent=None)
        self.h_line = InfiniteLine(pos=0, color=axis_color, vertical=False, line_width=1.5,
                                   parent=None)

        self.line_parent = None
        if self.fcapp.options["global_cursor_color_enabled"]:
            c_color = Color(self.fcapp.options["global_cursor_color"]).rgba
        else:
            c_color = self.line_color

        self.cursor_v_line = InfiniteLine(pos=None, color=c_color, vertical=True,
                                          parent=self.line_parent)

        self.cursor_h_line = InfiniteLine(pos=None, color=c_color, vertical=False,
                                          parent=self.line_parent)

        # setup HUD

        # TEXT HUD
        self.text_hud = Text('', color=self.text_hud_color, method='gpu', anchor_x='left', parent=None)
        # RECT HUD
        self.rect_hud = Rectangle(width=10, height=10, radius=[5, 5, 5, 5], center=(20, 20),
                                  border_color=self.rect_hud_color, color=self.rect_hud_color, parent=None)
        self.rect_hud.set_gl_state(depth_test=False)

        self.on_update_text_hud()

        # cursor text t obe attached to mouse cursor in Editors
        self.text_cursor = Text('', color=self.text_hud_color, method='gpu', anchor_x='left', parent=None)

        # draw a rectangle made out of 4 lines on the canvas to serve as a hint for the work area
        # all CNC have a limited workspace
        if self.fcapp.options['global_workspace'] is True:
            self.draw_workspace(workspace_size=self.fcapp.options["global_workspaceT"])

        # HUD Display
        self.hud_enabled = False

        # enable the HUD if it is activated in FlatCAM Preferences
        if self.fcapp.options['global_hud'] is True:
            self.on_toggle_hud(state=True, silent=True)

        # Axis Display
        self.axis_enabled = False

        # enable Axis
        if self.fcapp.options['global_axis'] is True:
            self.on_toggle_axis(state=True, silent=True)

        # enable Grid lines
        self.grid_lines_enabled = True

        self.shape_collections = []

        self.shape_collection = self.new_shape_collection()
        self.fcapp.pool_recreated.connect(self.on_pool_recreated)
        self.text_collection = self.new_text_collection()

        self.text_collection.enabled = True

        # Mouse Custom Cursor
        self.c = None
        self.big_cursor = None
        self._cursor_color = Color(self.fcapp.cursor_color_3D).rgba

        # Parent container
        # self.container = container

        # Keep VisPy canvas happy by letting it be "frozen" again.
        self.freeze()

        # fit everything into view
        self.fit_view()

        self.graph_event_connect('mouse_wheel', self.on_mouse_scroll)

        # <QtCore.QObject>
        # self.container.addWidget(self.native)

    @staticmethod
    def color_hex2tuple(hex_color):
        # strip the # from the beginning
        color = hex_color[1:]

        # convert color RGB components from range 0...255 to 0...1
        r_color = int(color[:2], 16) / 255
        g_color = int(color[2:4], 16) / 255
        b_color = int(color[4:6], 16) / 255
        return r_color, g_color, b_color

    def on_toggle_axis(self, signal=None, state=None, silent=None):
        if not state:
            state = not self.axis_enabled

        if state:
            self.axis_enabled = True
            self.fcapp.defaults['global_axis'] = True
            self.v_line.parent = self.view.scene
            self.h_line.parent = self.view.scene
            self.fcapp.ui.axis_status_label.setStyleSheet("""
                                                          QLabel
                                                          {
                                                              color: black;
                                                              background-color: orange;
                                                          }
                                                          """)
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("Axis enabled."), False)
        else:
            self.axis_enabled = False
            self.fcapp.defaults['global_axis'] = False
            self.v_line.parent = None
            self.h_line.parent = None
            self.fcapp.ui.axis_status_label.setStyleSheet("")
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("Axis disabled."), False)

    def apply_axis_color(self):
        self.fcapp.log.debug('PlotCanvas.apply_axis_color() -> axis color applied')

        axis_default_color = self.fcapp.options['global_axis_color']

        axis_color = self.color_hex2tuple(axis_default_color)
        axis_color = axis_color[0], axis_color[1], axis_color[2], self.axis_transparency

        if axis_color is not None:
            axis_color = np.array(axis_color, dtype=np.float32)
            if axis_color.ndim != 1 or axis_color.shape[0] != 4:
                self.fcapp.log.error('axis color must be a 4 element float rgba tuple,'
                                     ' list or array')
            self.v_line._color = axis_color
            self.v_line._changed['color'] = True

            self.h_line._color = axis_color
            self.h_line._changed['color'] = True

    def on_toggle_hud(self, signal=None, state=None, silent=None):
        if state is None:
            state = not self.hud_enabled

        if state:
            self.hud_enabled = True
            self.rect_hud.parent = self.view
            self.text_hud.parent = self.view
            self.fcapp.defaults['global_hud'] = True
            self.fcapp.ui.hud_label.setStyleSheet("""
                                                  QLabel
                                                  {
                                                      color: black;
                                                      background-color: mediumpurple;
                                                  }
                                                  """)
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("HUD enabled."), False)

        else:
            self.hud_enabled = False
            self.rect_hud.parent = None
            self.text_hud.parent = None
            self.fcapp.defaults['global_hud'] = False
            self.fcapp.ui.hud_label.setStyleSheet("")
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("HUD disabled."), False)

    def on_update_text_hud(self, dx=None, dy=None, x=None, y=None):
        """
        Update the text of the location labels from HUD

        :param x:   X location
        :type x:    float
        :param y:   Y location
        :type y:    float
        :param dx:  Delta X location
        :type dx:   float
        :param dy:  Delta Y location
        :type dy:   float
        :return:
        :rtype:     None
        """
        # units
        units = self.fcapp.app_units.lower()

        dx_dec = str(self.fcapp.dec_format(dx, self.fcapp.decimals)) if dx else '0.0'
        dy_dec = str(self.fcapp.dec_format(dy, self.fcapp.decimals)) if dy else '0.0'
        x_dec = str(self.fcapp.dec_format(x, self.fcapp.decimals)) if x else '0.0'
        y_dec = str(self.fcapp.dec_format(y, self.fcapp.decimals)) if y else '0.0'
        l1_hud_text = 'Dx: %s [%s]' % (dx_dec, units)
        l2_hud_text = 'Dy: %s [%s]' % (dy_dec, units)
        l3_hud_text = 'X:   %s [%s]' % (x_dec, units)
        l4_hud_text = 'Y:   %s [%s]' % (y_dec, units)
        hud_text = '%s\n%s\n\n%s\n%s' % (l1_hud_text, l2_hud_text, l3_hud_text, l4_hud_text)

        # font size
        qsettings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("hud_font_size"):
            fsize = qsettings.value('hud_font_size', type=int)
        else:
            fsize = 8

        try:
            c_font = QtGui.QFont("times", fsize)
        except Exception:
            # maybe Unix-like OS's don't have the Times font installed, use whatever is available
            c_font = QtGui.QFont()
            c_font.setPointSize(fsize)

        c_font_metrics = QtGui.QFontMetrics(c_font)

        l1_length = c_font_metrics.horizontalAdvance('Dx:xxx[mm]') + c_font_metrics.horizontalAdvance(str(dx_dec))
        l2_length = c_font_metrics.horizontalAdvance('Dy:xxx[mm]') + c_font_metrics.horizontalAdvance(str(dy_dec))
        l3_length = c_font_metrics.horizontalAdvance('X:xxxxx[mm]') + c_font_metrics.horizontalAdvance(str(x_dec))
        l4_length = c_font_metrics.horizontalAdvance('Y:xxxxx[mm]') + c_font_metrics.horizontalAdvance(str(y_dec))
        # l1_length = c_font_metrics.boundingRect(l1_hud_text).width()
        # l2_length = c_font_metrics.boundingRect(l2_hud_text).width()
        # l3_length = c_font_metrics.boundingRect(l3_hud_text).width()
        # l4_length = c_font_metrics.boundingRect(l4_hud_text).width()

        l1_height = c_font_metrics.boundingRect(l1_hud_text).height()
        # print(self.fcapp.qapp.devicePixelRatio())

        # coordinates and anchors
        height = (5 * l1_height) + c_font_metrics.lineSpacing() * 1.5 + 10
        width = max(l1_length, l2_length, l3_length, l4_length) * 1.3  # don't know where the 1.3 comes
        center_x = (width / 2) + 5
        center_y = (height / 2) + 5

        # text
        self.text_hud.font_size = fsize
        self.text_hud.text = hud_text
        self.text_hud.pos = 10, center_y
        self.text_hud.anchors = 'left', 'center'

        # rectangle
        self.rect_hud.center = center_x, center_y
        self.rect_hud.width = width
        self.rect_hud.height = height
        self.rect_hud.radius = [5, 5, 5, 5]

    def on_toggle_grid_lines(self, signal=None, silent=None):
        state = self.grid_lines_enabled

        settings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        if settings.contains("theme"):
            theme = settings.value('theme', type=str)
        else:
            theme = 'default'

        if settings.contains("dark_canvas"):
            dark_canvas = settings.value('dark_canvas', type=bool)
        else:
            dark_canvas = False

        if (theme == 'default' or theme == 'light') and not dark_canvas:
            color = 'dimgray'
        else:
            color = '#202124ff'

        if state:
            self.fcapp.options['global_grid_lines'] = True
            self.grid_lines_enabled = False
            # self.grid.parent = self.view.scene
            self.grid._grid_color_fn['color'] = Color(color).rgba
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("Grid enabled."), False)
        else:
            self.fcapp.options['global_grid_lines'] = False
            self.grid_lines_enabled = True
            # self.grid.parent = None
            self.grid._grid_color_fn['color'] = Color('#FFFFFFFF').rgba
            if silent is None:
                self.fcapp.inform[str, bool].emit(_("Grid disabled."), False)

        # HACK: enabling/disabling the cursor seams to somehow update the shapes on screen
        # - perhaps is a bug in VisPy implementation
        if self.fcapp.grid_status():
            self.fcapp.app_cursor.enabled = False
            self.fcapp.app_cursor.enabled = True
        else:
            self.fcapp.app_cursor.enabled = True
            self.fcapp.app_cursor.enabled = False

    def draw_workspace(self, workspace_size):
        """
        Draw a rectangular shape on canvas to specify our valid workspace.
        :param workspace_size: the workspace size; tuple
        :return:
        """
        self.delete_workspace()
        try:
            if self.fcapp.app_units.upper() == 'MM':
                dims = self.pagesize_dict[workspace_size]
            else:
                dims = (self.pagesize_dict[workspace_size][0]/25.4, self.pagesize_dict[workspace_size][1]/25.4)
        except Exception as e:
            self.app.log.error("PlotCanvas.draw_workspace() --> %s" % str(e))
            return

        if self.fcapp.options['global_workspace_orientation'] == 'l':
            dims = (dims[1], dims[0])

        a = np.array([(0, 0), (dims[0], 0), (dims[0], dims[1]), (0, dims[1])])

        # if not self.workspace_line:
        #     self.workspace_line = Line(pos=np.array((a[0], a[1], a[2], a[3], a[0])), color=(0.70, 0.3, 0.3, 0.7),
        #                                antialias=True, method='agg', parent=self.view.scene)
        # else:
        #     self.workspace_line.parent = self.view.scene
        self.workspace_line = Line(pos=np.array((a[0], a[1], a[2], a[3], a[0])), color=(0.70, 0.3, 0.3, 0.7),
                                   antialias=True, method='agg', parent=self.view.scene)

        self.fcapp.ui.wplace_label.set_value(workspace_size[:3])
        self.fcapp.ui.wplace_label.setToolTip(workspace_size)
        self.fcapp.ui.wplace_label.setStyleSheet("""
                        QLabel
                        {
                            color: black;
                            background-color: olivedrab;
                        }
                        """)
        self.fcapp.options['global_workspace'] = True

    def delete_workspace(self):
        try:
            self.workspace_line.parent = None
        except Exception:
            pass
        self.fcapp.ui.wplace_label.setStyleSheet("")
        self.fcapp.options['global_workspace'] = False

    # redraw the workspace lines on the plot by re adding them to the parent view.scene
    def restore_workspace(self):
        try:
            self.workspace_line.parent = self.view.scene
        except Exception:
            pass

    def graph_event_connect(self, event_name, callback):
        return getattr(self.events, event_name).connect(callback)

    def graph_event_disconnect(self, event_name, callback=None):
        if callback is None:
            getattr(self.events, event_name).disconnect()
        else:
            getattr(self.events, event_name).disconnect(callback)

    def zoom(self, factor, center=None):
        """
        Zooms the plot by factor around a given
        center point. Takes care of re-drawing.

        :param factor: Number by which to scale the plot.
        :type factor: float
        :param center: Coordinates [x, y] of the point around which to scale the plot.
        :type center: list
        :return: None
        """
        self.view.camera.zoom(factor, center)

    def new_shape_group(self, shape_collection=None):
        if shape_collection:
            return ShapeGroup(shape_collection)
        return ShapeGroup(self.shape_collection)

    def new_shape_collection(self, **kwargs):
        # sc = ShapeCollection(parent=self.view.scene, pool=self.app.pool, **kwargs)
        # self.shape_collections.append(sc)
        # return sc
        return ShapeCollection(parent=self.view.scene, pool=self.fcapp.pool, fcoptions=self.fcapp.options, **kwargs)

    def new_cursor(self, big=None):
        """
        Will create a mouse cursor pointer on canvas

        :param big: if True will create a mouse cursor made out of infinite lines
        :return: the mouse cursor object
        """
        if big is True:
            self.big_cursor = True
            self.c = CursorBig(app=self.fcapp)

            # in case there are multiple new_cursor calls, best to disconnect first the signals
            try:
                self.c.mouse_state_updated.disconnect(self.on_mouse_state)
            except (TypeError, AttributeError):
                pass
            try:
                self.c.mouse_position_updated.disconnect(self.on_mouse_position)
            except (TypeError, AttributeError):
                pass

            self.c.mouse_state_updated.connect(self.on_mouse_state)
            self.c.mouse_position_updated.connect(self.on_mouse_position)
        else:
            self.big_cursor = False
            self.c = Cursor(pos=np.empty((0, 2)), parent=self.view.scene)
            self.c.antialias = 0

        return self.c

    @property
    def cursor_color(self):
        return self._cursor_color

    @cursor_color.setter
    def cursor_color(self, color):
        self._cursor_color = Color(color).rgba
        if self.big_cursor is True:
            self.cursor_h_line.set_data(color=self._cursor_color)
            self.cursor_v_line.set_data(color=self._cursor_color)
        else:
            self.fcapp.cursor_color_3D = self._cursor_color

    def on_mouse_state(self, state):
        if state:
            self.cursor_h_line.parent = self.view.scene
            self.cursor_v_line.parent = self.view.scene
        else:
            self.cursor_h_line.parent = None
            self.cursor_v_line.parent = None

    def on_mouse_position(self, pos):

        if self.fcapp.options['global_cursor_color_enabled']:
            # color = Color(self.fcapp.options['global_cursor_color']).rgba
            color = self.cursor_color
        else:
            color = self.line_color

        self.cursor_h_line.set_data(pos=pos[1], color=color)
        self.cursor_v_line.set_data(pos=pos[0], color=color)
        self.view.scene.update()

    def on_mouse_scroll(self, event):
        # key modifiers
        modifiers = event.modifiers

        pan_delta_x = self.fcapp.options["global_gridx"]
        pan_delta_y = self.fcapp.options["global_gridy"]
        curr_pos = event.pos

        # Controlled pan by mouse wheel
        if 'Shift' in modifiers:
            p1 = np.array(curr_pos)[:2]

            if event.delta[1] > 0:
                curr_pos[0] -= pan_delta_x
            else:
                curr_pos[0] += pan_delta_x
            p2 = np.array(curr_pos)[:2]
            self.view.camera.pan(p2 - p1)
        elif 'Control' in modifiers:
            p1 = np.array(curr_pos)[:2]

            if event.delta[1] > 0:
                curr_pos[1] += pan_delta_y
            else:
                curr_pos[1] -= pan_delta_y
            p2 = np.array(curr_pos)[:2]
            self.view.camera.pan(p2 - p1)

        if self.fcapp.grid_status():
            pos_canvas = self.translate_coords(curr_pos)
            pos = self.fcapp.geo_editor.snap(pos_canvas[0], pos_canvas[1])

            # Update cursor
            self.fcapp.app_cursor.set_data(np.asarray([(pos[0], pos[1])]),
                                           symbol='++', edge_color=self.cursor_color,
                                           edge_width=self.fcapp.options["global_cursor_width"],
                                           size=self.fcapp.options["global_cursor_size"])

    def new_text_group(self, collection=None):
        if collection:
            return TextGroup(collection)
        else:
            return TextGroup(self.text_collection)

    def new_text_collection(self, **kwargs):
        return TextCollection(parent=self.view.scene, **kwargs)

    def fit_view(self, rect=None):

        # Lock updates in other threads
        self.shape_collection.lock_updates()

        if not rect:
            rect = Rect(-1, -1, 20, 20)
            try:
                rect.left, rect.right = self.shape_collection.bounds(axis=0)
                rect.bottom, rect.top = self.shape_collection.bounds(axis=1)
            except TypeError:
                pass

        # adjust the view camera to be slightly bigger than the bounds so the shape collection can be seen clearly
        # otherwise the shape collection boundary will have no border
        dx = rect.right - rect.left
        dy = rect.top - rect.bottom
        x_factor = dx * 0.02
        y_factor = dy * 0.02

        rect.left -= x_factor
        rect.bottom -= y_factor
        rect.right += x_factor
        rect.top += y_factor

        # rect.left *= 0.96
        # rect.bottom *= 0.96
        # rect.right *= 1.04
        # rect.top *= 1.04

        # units = self.fcapp.app_units.upper()
        # if units == 'MM':
        #     compensation = 0.5
        # else:
        #     compensation = 0.5 / 25.4
        # rect.left -= compensation
        # rect.bottom -= compensation
        # rect.right += compensation
        # rect.top += compensation

        self.view.camera.rect = rect

        self.shape_collection.unlock_updates()

    def fit_center(self, loc, rect=None):

        # Lock updates in other threads
        self.shape_collection.lock_updates()

        if not rect:
            try:
                rect = Rect(loc[0]-20, loc[1]-20, 40, 40)
            except TypeError:
                pass

        self.view.camera.rect = rect

        self.shape_collection.unlock_updates()

    def clear(self):
        pass

    def redraw(self):
        self.shape_collection.redraw([])
        self.text_collection.redraw()

    def on_pool_recreated(self, pool):
        self.shape_collection.pool = pool


class CursorBig(QtCore.QObject):
    """
    This is a fake cursor to ensure compatibility with the OpenGL engine (VisPy).
    This way I don't have to chane (disable) things related to the cursor all over when
    using the low performance Matplotlib 2D graphic engine.
    """

    mouse_state_updated = QtCore.pyqtSignal(bool)
    mouse_position_updated = QtCore.pyqtSignal(list)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._enabled = None

    @property
    def enabled(self):
        return True if self._enabled else False

    @enabled.setter
    def enabled(self, value):
        self._enabled = value
        self.mouse_state_updated.emit(value)

    def set_data(self, pos, **kwargs):
        """Internal event handler to draw the cursor when the mouse moves."""
        # if 'edge_color' in kwargs:
        #     color = kwargs['edge_color']
        # else:
        #     if self.app.options['global_theme'] == 'light':
        #         color = '#000000FF'
        #     else:
        #         color = '#FFFFFFFF'

        position = [pos[0][0], pos[0][1]]
        self.mouse_position_updated.emit(position)
