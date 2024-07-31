# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 3/10/2019                                          #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCTree
import logging
from copy import deepcopy
import math

from shapely import MultiPolygon, Polygon, MultiLineString
from shapely.ops import unary_union

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ObjectReport(AppTool):
    pluginName = _("Object Report")

    calculations_finished = QtCore.pyqtSignal(float, float, float, float, float, object)

    def __init__(self, app):
        AppTool.__init__(self, app)

        # self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)

        self.decimals = self.app.decimals
        self.layout.setContentsMargins(0, 0, 0, 0)

        # this way I can hide/show the frame
        self.info_frame = QtWidgets.QFrame()
        self.info_frame.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.info_frame)
        self.info_box = QtWidgets.QVBoxLayout()
        self.info_box.setContentsMargins(0, 0, 0, 0)
        self.info_frame.setLayout(self.info_box)

        # ## Title
        # title_label = FCLabel("%s" % self.pluginName, size=16, bold=True)
        # title_label.setStyleSheet("""
        #                 QLabel
        #                 {
        #                     font-size: 16px;
        #                     font-weight: bold;
        #                 }
        #                 """)
        # self.info_box.addWidget(title_label)

        self.treeWidget = FCTree(columns=2)
        self.treeWidget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.treeWidget.setStyleSheet("QTreeWidget {border: 0px;}")

        self.info_box.addWidget(self.treeWidget)
        # self.info_box.setStretch(0, 0)

        self.calculations_finished.connect(self.show_area_chull)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolReport()")

        if self.app.plugin_tab_locked is True:
            return

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

        self.properties()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='P', **kwargs)

    def set_tool_ui(self):
        # this reset the TreeWidget
        self.treeWidget.clear()
        self.info_frame.show()

    def properties(self):
        obj_list = self.app.collection.get_selected()
        if not obj_list:
            self.app.inform.emit('[ERROR_NOTCL] %s' % _("No object is selected."))
            # self.app.ui.notebook.setTabText(2, _("Plugins"))
            # self.info_frame.hide()
            self.app.ui.notebook.removeTab(2)
            self.app.ui.notebook.setCurrentWidget(self.app.ui.project_tab)
            return

        # delete the selection shape, if any
        try:
            self.app.delete_selection_shape()
        except Exception as e:
            self.app.log.error("ToolReport.Properties.properties() --> %s" % str(e))

        # populate the properties items
        for obj in obj_list:
            self.addItems(obj)
            self.app.inform.emit('[success] %s' % _("Object Properties are displayed."))

        # make sure that the FCTree widget columns are resized to content
        self.treeWidget.resize_sig.emit()

        self.app.ui.notebook.setTabText(2, _("Object Report"))

    def addItems(self, obj):
        parent = self.treeWidget.invisibleRootItem()
        apertures = ''
        tools = ''
        drills = ''
        slots = ''
        others = ''

        font = QtGui.QFont()
        font.setBold(True)

        p_color = QtGui.QColor("#000000") if self.app.options['global_theme'] in ['default', 'light'] \
            else QtGui.QColor("#FFFFFF")

        # main Items categories
        obj_type = self.treeWidget.addParent(parent, _('TYPE'), expanded=True, color=p_color, font=font)
        obj_name = self.treeWidget.addParent(parent, _('NAME'), expanded=True, color=p_color, font=font)
        dims = self.treeWidget.addParent(
            parent, _('Dimensions'), expanded=True, color=p_color, font=font)
        units = self.treeWidget.addParent(parent, _('Units'), expanded=True, color=p_color, font=font)
        options = self.treeWidget.addParent(parent, _('Options'), color=p_color, font=font)

        if obj.kind.lower() == 'gerber':
            apertures = self.treeWidget.addParent(
                parent, _('Apertures'), expanded=True, color=p_color, font=font)
        else:
            tools = self.treeWidget.addParent(
                parent, _('Tools'), expanded=True, color=p_color, font=font)

        if obj.kind.lower() == 'excellon':
            drills = self.treeWidget.addParent(
                parent, _('Drills'), expanded=True, color=p_color, font=font)
            slots = self.treeWidget.addParent(
                parent, _('Slots'), expanded=True, color=p_color, font=font)

        if obj.kind.lower() == 'cncjob':
            others = self.treeWidget.addParent(
                parent, _('Others'), expanded=True, color=p_color, font=font)

        separator = self.treeWidget.addParent(parent, '')

        self.treeWidget.addChild(
            obj_type, ['%s:' % _('Object Type'), ('%s' % (obj.kind.upper()))], True, font=font, font_items=1)
        try:
            self.treeWidget.addChild(obj_type,
                                     [
                                         '%s:' % _('Geo Type'),
                                         ('%s' % (
                                             {
                                                 False: _("Single-Geo"),
                                                 True: _("Multi-Geo")
                                             }[obj.multigeo])
                                          )
                                     ],
                                     True)
        except Exception as e:
            self.app.log.error("Properties.addItems() --> %s" % str(e))

        self.treeWidget.addChild(obj_name, [obj.obj_options['name']])

        def job_thread(obj_prop):
            self.app.proc_container.new('%s...' % _("Working"))

            length = 0.0
            width = 0.0
            area = 0.0
            copper_area = 0.0

            geo = obj_prop.solid_geometry
            if geo:
                # calculate physical dimensions
                try:
                    xmin, ymin, xmax, ymax = obj_prop.bounds()

                    length = abs(xmax - xmin)
                    width = abs(ymax - ymin)
                except Exception as ee:
                    self.app.log.error("PropertiesTool.addItems() -> calculate dimensions --> %s" % str(ee))

                # calculate box area
                if self.app.app_units.lower() == 'mm':
                    area = (length * width) / 100
                else:
                    area = length * width

                if obj_prop.kind.lower() == 'gerber':
                    # calculate copper area
                    try:
                        for geo_el in geo:
                            copper_area += geo_el.area
                    except TypeError:
                        copper_area += geo.area
                    copper_area /= 100
            else:
                xmin = []
                ymin = []
                xmax = []
                ymax = []

                if obj_prop.kind.lower() == 'cncjob':
                    try:
                        # for CNCJob objects created from Excellon
                        for tool_k in obj_prop.tools:
                            x0, y0, x1, y1 = unary_union(obj_prop.tools[tool_k]['solid_geometry']).bounds
                            xmin.append(x0)
                            ymin.append(y0)
                            xmax.append(x1)
                            ymax.append(y1)
                    except Exception as ee:
                        self.app.log.error("PropertiesTool.addItems() --> %s" % str(ee))

                    try:
                        for tool_k in obj_prop.tools:
                            x0, y0, x1, y1 = unary_union(obj_prop.tools[tool_k]['solid_geometry']).bounds
                            xmin.append(x0)
                            ymin.append(y0)
                            xmax.append(x1)
                            ymax.append(y1)
                    except Exception as ee:
                        self.app.log.error("PropertiesTool.addItems() --> %s" % str(ee))
                else:
                    try:
                        for tool_k in obj_prop.tools:
                            x0, y0, x1, y1 = unary_union(obj_prop.tools[tool_k]['solid_geometry']).bounds
                            xmin.append(x0)
                            ymin.append(y0)
                            xmax.append(x1)
                            ymax.append(y1)
                    except Exception as ee:
                        self.app.log.error("PropertiesTool.addItems() --> %s" % str(ee))

                try:
                    xmin = min(xmin)
                    ymin = min(ymin)
                    xmax = max(xmax)
                    ymax = max(ymax)

                    length = abs(xmax - xmin)
                    width = abs(ymax - ymin)

                    # calculate box area
                    if self.app.app_units.lower() == 'mm':
                        area = (length * width) / 100
                    else:
                        area = length * width

                    if obj_prop.kind.lower() == 'gerber':
                        # calculate copper area

                        # create a complete solid_geometry from the tools
                        geo_tools = []
                        for tool_k in obj_prop.tools:
                            if 'solid_geometry' in obj_prop.tools[tool_k]:
                                for geo_el in obj_prop.tools[tool_k]['solid_geometry']:
                                    geo_tools.append(geo_el)

                        geo_tools_mp = MultiPolygon(geo_tools)
                        try:
                            for geo_el in geo_tools_mp.geoms:
                                copper_area += geo_el.area
                        except TypeError:
                            copper_area += geo_tools_mp.area
                        copper_area /= 100
                except Exception as err:
                    self.app.log.error("Properties.addItems() --> %s" % str(err))

            area_chull = 0.0
            if obj_prop.kind.lower() != 'cncjob':
                # calculate and add convex hull area
                if geo:
                    if isinstance(geo, list) and geo[0] is not None:
                        if isinstance(geo, MultiPolygon):
                            env_obj = geo.convex_hull
                        elif (isinstance(geo, MultiPolygon) and len(geo.geoms) == 1) or \
                                (isinstance(geo, list) and len(geo) == 1) and isinstance(geo[0], Polygon):
                            env_obj = unary_union(geo)
                            env_obj = env_obj.convex_hull
                        else:
                            env_obj = unary_union(geo)
                            env_obj = env_obj.convex_hull

                        area_chull = env_obj.area
                    else:
                        area_chull = 0
                else:
                    try:
                        area_chull = []
                        for tool_k in obj_prop.tools:
                            area_el = unary_union(obj_prop.tools[tool_k]['solid_geometry']).convex_hull
                            area_chull.append(area_el.area)
                        area_chull = max(area_chull)
                    except Exception as er:
                        area_chull = None
                        self.app.log.error("Properties.addItems() --> %s" % str(er))

            if self.app.app_units.lower() == 'mm' and area_chull:
                area_chull = area_chull / 100

            if area_chull is None:
                area_chull = 0

            self.calculations_finished.emit(area, length, width, area_chull, copper_area, dims)

        self.app.worker_task.emit({'fcn': job_thread, 'params': [obj]})

        # Units items
        f_unit = {'in': _('Inch'), 'mm': _('Metric')}[str(self.app.app_units.lower())]
        self.treeWidget.addChild(units, ['FlatCAM units:', f_unit], True)

        o_unit = {
            'in': _('Inch'),
            'mm': _('Metric'),
            'inch': _('Inch'),
            'metric': _('Metric')
        }[str(obj.units_found.lower())]
        self.treeWidget.addChild(units, ['Object units:', o_unit], True)

        # Options items
        for option in obj.obj_options:
            if option == 'name':
                continue
            self.treeWidget.addChild(options, [str(option), str(obj.obj_options[option])], True)

        # Items that depend on the object type
        if obj.kind.lower() == 'gerber':
            temp_ap = {}
            for ap in obj.tools:
                temp_ap.clear()
                temp_ap = deepcopy(obj.tools[ap])
                temp_ap.pop('geometry', None)

                solid_nr = 0
                follow_nr = 0
                clear_nr = 0

                if 'geometry' in obj.tools[ap]:
                    if obj.tools[ap]['geometry']:
                        font.setBold(True)
                        for el in obj.tools[ap]['geometry']:
                            if 'solid' in el:
                                solid_nr += 1
                            if 'follow' in el:
                                follow_nr += 1
                            if 'clear' in el:
                                clear_nr += 1
                else:
                    font.setBold(False)
                temp_ap['Solid_Geo'] = '%s Polygons' % str(solid_nr)
                temp_ap['Follow_Geo'] = '%s LineStrings' % str(follow_nr)
                temp_ap['Clear_Geo'] = '%s Polygons' % str(clear_nr)

                apid = self.treeWidget.addParent(
                    apertures, str(ap), expanded=False, color=p_color, font=font)
                for key in temp_ap:
                    self.treeWidget.addChild(apid, [str(key), str(temp_ap[key])], True)
        elif obj.kind.lower() == 'excellon':
            tot_drill_cnt = 0
            tot_slot_cnt = 0

            for tool, value in obj.tools.items():
                toolid = self.treeWidget.addParent(
                    tools, str(tool), expanded=False, color=p_color, font=font)

                drill_cnt = 0  # variable to store the nr of drills per tool
                slot_cnt = 0  # variable to store the nr of slots per tool

                # Find no of drills for the current tool
                if 'drills' in value and value['drills']:
                    drill_cnt = len(value['drills'])

                tot_drill_cnt += drill_cnt

                # Find no of slots for the current tool
                if 'slots' in value and value['slots']:
                    slot_cnt = len(value['slots'])

                tot_slot_cnt += slot_cnt

                self.treeWidget.addChild(
                    toolid,
                    [
                        _('Diameter'),
                        '%.*f %s' % (self.decimals, value['tooldia'], self.app.app_units.lower())
                    ],
                    True
                )
                self.treeWidget.addChild(toolid, [_('Drills number'), str(drill_cnt)], True)
                self.treeWidget.addChild(toolid, [_('Slots number'), str(slot_cnt)], True)

            self.treeWidget.addChild(drills, [_('Drills total number:'), str(tot_drill_cnt)], True)
            self.treeWidget.addChild(slots, [_('Slots total number:'), str(tot_slot_cnt)], True)
        elif obj.kind.lower() == 'geometry':
            for tool, value in obj.tools.items():
                geo_tool = self.treeWidget.addParent(
                    tools, str(tool), expanded=True, color=p_color, font=font)
                for k, v in value.items():
                    if k == 'solid_geometry':
                        # printed_value = _('Present') if v else _('None')
                        try:
                            if isinstance(k, (MultiPolygon, MultiLineString)):
                                printed_value = str(len(v.geoms))
                            else:
                                printed_value = str(len(v))
                        except (TypeError, AttributeError):
                            printed_value = '1'
                        self.treeWidget.addChild(geo_tool, [str(k), printed_value], True)
                    elif k == 'data':
                        tool_data = self.treeWidget.addParent(
                            geo_tool, str(k).capitalize(), color=p_color, font=font)
                        for data_k, data_v in v.items():
                            self.treeWidget.addChild(tool_data, [str(data_k), str(data_v)], True)
                    else:
                        self.treeWidget.addChild(geo_tool, [str(k), str(v)], True)
        elif obj.kind.lower() == 'cncjob':
            # for CNCJob objects made from Gerber or Geometry objects
            if obj.obj_options['type'].lower() == 'geometry':
                for tool, value in obj.tools.items():
                    geo_tool = self.treeWidget.addParent(
                        tools, str(tool), expanded=True, color=p_color, font=font)
                    for k, v in value.items():
                        if k == 'solid_geometry':
                            printed_value = _('Present') if v else _('None')
                            self.treeWidget.addChild(geo_tool, [_("Solid Geometry"), printed_value], True)
                        elif k == 'gcode':
                            printed_value = _('Present') if v != '' else _('None')
                            self.treeWidget.addChild(geo_tool, [_("GCode Text"), printed_value], True)
                        elif k == 'gcode_parsed':
                            printed_value = _('Present') if v else _('None')
                            self.treeWidget.addChild(geo_tool, [_("GCode Geometry"), printed_value], True)
                        elif k == 'data':
                            pass
                        else:
                            self.treeWidget.addChild(geo_tool, [str(k), str(v)], True)

                    v = value['data']
                    tool_data = self.treeWidget.addParent(
                        geo_tool, _("Tool Data"), color=p_color, font=font)
                    for data_k, data_v in v.items():
                        self.treeWidget.addChild(tool_data, [str(data_k).capitalize(), str(data_v)], True)

            # for CNCJob objects made from Excellon objects
            if obj.obj_options['type'].lower() == 'excellon':
                for tool_id, value in obj.tools.items():
                    tool_dia = obj.tools[tool_id]['tooldia']
                    exc_tool = self.treeWidget.addParent(
                        tools, str(tool_id), expanded=False, color=p_color, font=font
                    )
                    self.treeWidget.addChild(
                        exc_tool,
                        [
                            _('Diameter'),
                            '%.*f %s' % (self.decimals, tool_dia, self.app.app_units.lower())
                        ],
                        True
                    )
                    for k, v in value.items():
                        if k == 'solid_geometry':
                            printed_value = _('Present') if v else _('None')
                            self.treeWidget.addChild(exc_tool, [_("Solid Geometry"), printed_value], True)
                        elif k == 'nr_drills':
                            self.treeWidget.addChild(exc_tool, [_("Drills number"), str(v)], True)
                        elif k == 'nr_slots':
                            self.treeWidget.addChild(exc_tool, [_("Slots number"), str(v)], True)
                        elif k == 'gcode':
                            printed_value = _('Present') if v != '' else _('None')
                            self.treeWidget.addChild(exc_tool, [_("GCode Text"), printed_value], True)
                        elif k == 'gcode_parsed':
                            printed_value = _('Present') if v else _('None')
                            self.treeWidget.addChild(exc_tool, [_("GCode Geometry"), printed_value], True)
                        else:
                            pass

                    self.treeWidget.addChild(
                        exc_tool,
                        [
                            _("Depth of Cut"),
                            '%.*f %s' % (
                                self.decimals,
                                (obj.z_cut - abs(value['data']['tools_drill_offset'])),
                                self.app.app_units.lower()
                            )
                        ],
                        True
                    )
                    self.treeWidget.addChild(
                        exc_tool,
                        [
                            _("Clearance Height"),
                            '%.*f %s' % (
                                self.decimals,
                                obj.z_move,
                                self.app.app_units.lower()
                            )
                        ],
                        True
                    )
                    self.treeWidget.addChild(
                        exc_tool,
                        [
                            _("Feedrate"),
                            '%.*f %s/min' % (
                                self.decimals,
                                obj.feedrate,
                                self.app.app_units.lower()
                            )
                        ],
                        True
                    )

                    v = value['data']
                    tool_data = self.treeWidget.addParent(
                        exc_tool, _("Tool Data"), color=p_color, font=font)
                    for data_k, data_v in v.items():
                        self.treeWidget.addChild(tool_data, [str(data_k).capitalize(), str(data_v)], True)

            r_time = obj.routing_time
            if r_time > 1:
                units_lbl = 'min'
            else:
                r_time *= 60
                units_lbl = 'sec'
            r_time = math.ceil(float(r_time))
            self.treeWidget.addChild(
                others,
                [
                    '%s:' % _('Routing time'),
                    '%.*f %s' % (self.decimals, r_time, units_lbl)],
                True
            )
            self.treeWidget.addChild(
                others,
                [
                    '%s:' % _('Travelled distance'),
                    '%.*f %s' % (self.decimals, obj.travel_distance, self.app.app_units.lower())
                ],
                True
            )

        self.treeWidget.addChild(separator, [''])

    def show_area_chull(self, area, length, width, chull_area, copper_area, location):

        # add dimensions
        self.treeWidget.addChild(
            location,
            ['%s:' % _('Length'), '%.*f %s' % (self.decimals, length, self.app.app_units.lower())],
            True
        )
        self.treeWidget.addChild(
            location,
            ['%s:' % _('Width'), '%.*f %s' % (self.decimals, width, self.app.app_units.lower())],
            True
        )

        # add box area
        if self.app.app_units.lower() == 'mm':
            self.treeWidget.addChild(location, ['%s:' % _('Box Area'), '%.*f %s' % (self.decimals, area, 'cm2')], True)
            self.treeWidget.addChild(
                location,
                ['%s:' % _('Convex_Hull Area'), '%.*f %s' % (self.decimals, chull_area, 'cm2')],
                True
            )

        else:
            self.treeWidget.addChild(location, ['%s:' % _('Box Area'), '%.*f %s' % (self.decimals, area, 'in2')], True)
            self.treeWidget.addChild(
                location,
                ['%s:' % _('Convex_Hull Area'), '%.*f %s' % (self.decimals, chull_area, 'in2')],
                True
            )

        # add copper area
        if self.app.app_units.lower() == 'mm':
            self.treeWidget.addChild(
                location, ['%s:' % _('Copper Area'), '%.*f %s' % (self.decimals, copper_area, 'cm2')], True)
        else:
            self.treeWidget.addChild(
                location, ['%s:' % _('Copper Area'), '%.*f %s' % (self.decimals, copper_area, 'in2')], True)

# end of file
