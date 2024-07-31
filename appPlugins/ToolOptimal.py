# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 09/27/2019                                         #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCComboBox, FCCheckBox, \
    FCEntry, FCTextArea, FCSpinner, OptionalHideInputSection
from camlib import grace, flatten_shapely_geometry

import logging
import numpy as np

from shapely import MultiPolygon
from shapely.ops import nearest_points

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolOptimal(AppTool):

    update_text = QtCore.pyqtSignal(list)
    update_sec_distances = QtCore.pyqtSignal(dict)

    def __init__(self, app):
        AppTool.__init__(self, app)

        self.units = self.app.app_units.upper()
        self.decimals = self.app.decimals

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = OptimalUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        # this is the line selected in the textbox with the locations of the minimum
        self.selected_text = ''

        # this is the line selected in the textbox with the locations of the other distances found in the Gerber object
        self.selected_locations_text = ''

        # dict to hold the distances between every two elements in Gerber as keys and the actual locations where that
        # distances happen as values
        self.min_dict = {}

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='Alt+O', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolOptimal()")

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

        self.app.ui.notebook.setTabText(2, _("Find Optimal"))

    def connect_signals_at_init(self):
        self.update_text.connect(self.on_update_text)
        self.update_sec_distances.connect(self.on_update_sec_distances_txt)

        self.ui.calculate_button.clicked.connect(self.find_minimum_distance)
        self.ui.locate_button.clicked.connect(self.on_locate_position)
        self.ui.locations_textb.cursorPositionChanged.connect(self.on_textbox_clicked)

        self.ui.locate_sec_button.clicked.connect(self.on_locate_sec_position)
        self.ui.distances_textb.cursorPositionChanged.connect(self.on_distances_textb_clicked)
        self.ui.locations_sec_textb.cursorPositionChanged.connect(self.on_locations_sec_clicked)

        self.ui.reset_button.clicked.connect(self.set_tool_ui)

    def disconnect_signals(self):
        try:
            self.update_text.disconnect(self.on_update_text)
        except (TypeError, AttributeError):
            pass

        try:
            self.update_sec_distances.disconnect(self.on_update_sec_distances_txt)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.calculate_button.clicked.disconnect(self.find_minimum_distance)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.locate_button.clicked.disconnect(self.on_locate_position)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.locations_textb.cursorPositionChanged.disconnect(self.on_textbox_clicked)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.locate_sec_button.clicked.disconnect(self.on_locate_sec_position)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.distances_textb.cursorPositionChanged.disconnect(self.on_distances_textb_clicked)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.locations_sec_textb.cursorPositionChanged.disconnect(self.on_locations_sec_clicked)
        except (TypeError, AttributeError):
            pass

        try:
            self.ui.reset_button.clicked.disconnect(self.set_tool_ui)
        except (TypeError, AttributeError):
            pass

    def set_tool_ui(self):
        self.clear_ui(self.layout)
        self.ui = OptimalUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.disconnect_signals()
        self.connect_signals_at_init()

        self.ui.result_entry.set_value(0.0)
        self.ui.freq_entry.set_value(0)

        self.ui.precision_spinner.set_value(int(self.app.options["tools_opt_precision"]))
        self.ui.locations_textb.clear()
        # new cursor - select all document
        cursor = self.ui.locations_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)

        # clear previous selection highlight
        tmp = cursor.blockFormat()
        tmp.clearBackground()
        cursor.setBlockFormat(tmp)

        self.ui.locations_textb.setVisible(False)
        self.ui.locate_button.setVisible(False)

        self.ui.result_entry.set_value(0.0)
        self.ui.freq_entry.set_value(0)
        self.reset_fields()

        # SELECT THE CURRENT OBJECT
        obj = self.app.collection.get_active()
        if obj and obj.kind == 'gerber':
            obj_name = obj.obj_options['name']
            self.ui.gerber_object_combo.set_value(obj_name)

    def find_minimum_distance(self):
        self.units = self.app.app_units.upper()
        self.decimals = int(self.ui.precision_spinner.get_value())

        selection_index = self.ui.gerber_object_combo.currentIndex()

        model_index = self.app.collection.index(selection_index, 0, self.ui.gerber_object_combo.rootModelIndex())
        try:
            fcobj = model_index.internalPointer().obj
        except Exception as e:
            self.app.log.error("ToolOptimal.find_minimum_distance() --> %s" % str(e))
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("There is no Gerber object loaded ..."))
            return

        if fcobj.kind != 'gerber':
            self.app.inform.emit('[ERROR_NOTCL] %s' % _("Only Gerber objects can be evaluated."))
            return

        proc = self.app.proc_container.new('%s...' % _("Working"))

        def job_thread(app_obj, plugin_instance):
            app_obj.inform.emit(_("Optimal Tool. Started to search for the minimum distance between copper features."))
            try:
                old_disp_number = 0
                pol_nr = 0
                app_obj.proc_container.update_view_text(' %d%%' % 0)
                total_geo = []

                for ap in list(fcobj.tools.keys()):
                    if 'geometry' in fcobj.tools[ap]:
                        app_obj.inform.emit(
                            '%s: %s' % (_("Optimal Tool. Parsing geometry for aperture"), str(ap)))

                        for geo_el in fcobj.tools[ap]['geometry']:
                            if self.app.abort_flag:
                                # graceful abort requested by the user
                                raise grace

                            if 'solid' in geo_el and geo_el['solid'] is not None and geo_el['solid'].is_valid:
                                total_geo.append(geo_el['solid'])

                app_obj.inform.emit(
                    _("Optimal Tool. Creating a buffer for the object geometry."))
                total_geo = MultiPolygon(total_geo)
                total_geo = total_geo.buffer(0)
                total_geo = flatten_shapely_geometry(total_geo)

                geo_len = len(total_geo)
                if geo_len == 1:
                    app_obj.inform.emit('[ERROR_NOTCL] %s' %
                                        _("The Gerber object has one Polygon as geometry.\n"
                                          "There are no distances between geometry elements to be found."))
                    return 'fail'

                geo_len = (geo_len * (geo_len - 1)) / 2

                app_obj.inform.emit(
                    '%s: %s' % (_("Optimal Tool. Finding the distances between each two elements. Iterations"),
                                str(geo_len)))

                plugin_instance.min_dict = {}
                idx = 1
                for geo in total_geo:
                    for s_geo in total_geo[idx:]:
                        if app_obj.abort_flag:
                            # graceful abort requested by the user
                            raise grace

                        # minimize the number of distances by not taking into considerations those that are too small
                        dist = geo.distance(s_geo)
                        dist = app_obj.dec_format(dist, plugin_instance.decimals)
                        loc_1, loc_2 = nearest_points(geo, s_geo)

                        proc_loc = (
                            (app_obj.dec_format(loc_1.x, self.decimals), app_obj.dec_format(loc_1.y, self.decimals)),
                            (app_obj.dec_format(loc_2.x, self.decimals), app_obj.dec_format(loc_2.y, self.decimals))
                        )

                        if dist in plugin_instance.min_dict:
                            plugin_instance.min_dict[dist].append(proc_loc)
                        else:
                            plugin_instance.min_dict[dist] = [proc_loc]

                        pol_nr += 1
                        disp_number = int(np.interp(pol_nr, [0, geo_len], [0, 100]))

                        if old_disp_number < disp_number <= 100:
                            app_obj.proc_container.update_view_text(' %d%%' % disp_number)
                            old_disp_number = disp_number
                    idx += 1

                app_obj.inform.emit(_("Optimal Tool. Finding the minimum distance."))

                min_list = list(plugin_instance.min_dict.keys())
                min_dist = min(min_list)
                rep_min_dist = min_dist - 10**-self.decimals  # make sure that this will work for isolation case
                min_dist_string = str(app_obj.dec_format(rep_min_dist, self.decimals))
                plugin_instance.ui.result_entry.set_value(min_dist_string)

                freq = len(plugin_instance.min_dict[min_dist])
                freq = '%d' % int(freq)
                plugin_instance.ui.freq_entry.set_value(freq)

                min_locations = plugin_instance.min_dict.pop(min_dist)

                self.update_text.emit(min_locations)
                self.update_sec_distances.emit(plugin_instance.min_dict)

                app_obj.inform.emit('[success] %s' % _("Optimal Tool. Finished successfully."))
            except Exception as ee:
                proc.done()
                app_obj.log.error(str(ee))
                return
            proc.done()

        self.app.worker_task.emit({'fcn': job_thread, 'params': [self.app, self]})

    def on_locate_position(self):
        # cursor = self.locations_textb.textCursor()
        # self.selected_text = cursor.selectedText()

        try:
            if self.selected_text != '':
                loc = eval(self.selected_text)
            else:
                return 'fail'
        except Exception as e:
            self.app.log.error("ToolOptimal.on_locate_position() --> first try %s" % str(e))
            self.app.inform.emit("[ERROR_NOTCL] The selected text is no valid location in the format "
                                 "((x0, y0), (x1, y1)).")
            return

        try:
            loc_1 = loc[0]
            loc_2 = loc[1]
            dx = loc_1[0] - loc_2[0]
            dy = loc_1[1] - loc_2[1]
            loc = (float('%.*f' % (self.decimals, (min(loc_1[0], loc_2[0]) + (abs(dx) / 2)))),
                   float('%.*f' % (self.decimals, (min(loc_1[1], loc_2[1]) + (abs(dy) / 2)))))
            self.app.on_jump_to(custom_location=loc)
        except Exception as e:
            self.app.log.error("ToolOptimal.on_locate_position() --> sec try %s" % str(e))
            return

    def on_update_text(self, data):
        txt = ''
        for loc in data:
            if loc:
                txt += '%s, %s\n' % (str(loc[0]), str(loc[1]))
        self.ui.locations_textb.setPlainText(txt)
        self.ui.locate_button.setDisabled(False)

    def on_textbox_clicked(self):
        # new cursor - select all document
        cursor = self.ui.locations_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)

        # clear previous selection highlight
        tmp = cursor.blockFormat()
        tmp.clearBackground()
        cursor.setBlockFormat(tmp)

        # new cursor - select the current line
        cursor = self.ui.locations_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)

        # highlight the current selected line
        tmp = cursor.blockFormat()
        tmp.setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        cursor.setBlockFormat(tmp)

        self.selected_text = cursor.selectedText()

    def on_update_sec_distances_txt(self, data):
        distance_list = sorted(list(data.keys()))
        txt = ''
        for loc in distance_list:
            txt += '%s\n' % str(loc)
        self.ui.distances_textb.setPlainText(txt)
        self.ui.locate_sec_button.setDisabled(False)

    def on_distances_textb_clicked(self):
        # new cursor - select all document
        cursor = self.ui.distances_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)

        # clear previous selection highlight
        tmp = cursor.blockFormat()
        tmp.clearBackground()
        cursor.setBlockFormat(tmp)

        # new cursor - select the current line
        cursor = self.ui.distances_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)

        # highlight the current selected line
        tmp = cursor.blockFormat()
        tmp.setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        cursor.setBlockFormat(tmp)

        distance_text = cursor.selectedText()
        key_in_min_dict = eval(distance_text)
        self.on_update_locations_text(dist=key_in_min_dict)

    def on_update_locations_text(self, dist):
        distance_list = self.min_dict[dist]
        txt = ''
        for loc in distance_list:
            if loc:
                txt += '%s, %s\n' % (str(loc[0]), str(loc[1]))
        self.ui.locations_sec_textb.setPlainText(txt)

    def on_locations_sec_clicked(self):
        # new cursor - select all document
        cursor = self.ui.locations_sec_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)

        # clear previous selection highlight
        tmp = cursor.blockFormat()
        tmp.clearBackground()
        cursor.setBlockFormat(tmp)

        # new cursor - select the current line
        cursor = self.ui.locations_sec_textb.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)

        # highlight the current selected line
        tmp = cursor.blockFormat()
        tmp.setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        cursor.setBlockFormat(tmp)

        self.selected_locations_text = cursor.selectedText()

    def on_locate_sec_position(self):
        try:
            if self.selected_locations_text != '':
                loc = eval(self.selected_locations_text)
            else:
                return
        except Exception as e:
            self.app.log.error("ToolOptimal.on_locate_sec_position() --> first try %s" % str(e))
            self.app.inform.emit("[ERROR_NOTCL] The selected text is no valid location in the format "
                                 "((x0, y0), (x1, y1)).")
            return

        try:
            loc_1 = loc[0]
            loc_2 = loc[1]
            dx = loc_1[0] - loc_2[0]
            dy = loc_1[1] - loc_2[1]
            loc = (float('%.*f' % (self.decimals, (min(loc_1[0], loc_2[0]) + (abs(dx) / 2)))),
                   float('%.*f' % (self.decimals, (min(loc_1[1], loc_2[1]) + (abs(dy) / 2)))))
            self.app.on_jump_to(custom_location=loc)
        except Exception as e:
            self.app.log.error("ToolOptimal.on_locate_sec_position() --> sec try %s" % str(e))
            return

    def reset_fields(self):
        self.ui.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.ui.gerber_object_combo.setCurrentIndex(0)


class OptimalUI:

    pluginName = _("Find Optimal")

    def __init__(self, layout, app):
        self.app = app
        self.decimals = self.app.decimals
        self.layout = layout
        self.units = self.app.app_units.upper()

        # ## Title
        title_label = FCLabel("%s" % self.pluginName, size=16, bold=True)
        self.layout.addWidget(title_label)
        # self.layout.addWidget(FCLabel(""))

        # #############################################################################################################
        # Gerber Source Object
        # #############################################################################################################
        self.obj_combo_label = FCLabel('%s' % _("Source Object"), color='darkorange', bold=True)
        self.obj_combo_label.setToolTip(
            "Gerber object for which to find the minimum distance between copper features."
        )
        self.layout.addWidget(self.obj_combo_label)

        # ## Gerber Object to mirror
        self.gerber_object_combo = FCComboBox()
        self.gerber_object_combo.setModel(self.app.collection)
        self.gerber_object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.gerber_object_combo.is_last = True
        self.gerber_object_combo.obj_type = "Gerber"

        self.gerber_object_label = FCLabel('%s:' % _("GERBER"), bold=True)
        self.gerber_object_label.setToolTip(
            "Gerber object for which to find the minimum distance between copper features."
        )
        self.layout.addWidget(self.gerber_object_combo)

        # separator_line = QtWidgets.QFrame()
        # separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        # separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        # grid0.addWidget(separator_line, 4, 0, 1, 2)

        # #############################################################################################################
        # Parameters Frame
        # #############################################################################################################
        self.param_label = FCLabel('%s' % _("Parameters"), color='blue', bold=True)
        self.param_label.setToolTip(_("Parameters used for this tool."))
        self.layout.addWidget(self.param_label)

        par_frame = FCFrame()
        self.layout.addWidget(par_frame)

        param_grid = GLay(v_spacing=5, h_spacing=3)
        par_frame.setLayout(param_grid)

        # Precision = nr of decimals
        self.precision_label = FCLabel('%s:' % _("Precision"))
        self.precision_label.setToolTip(_("Number of decimals kept for found distances."))

        self.precision_spinner = FCSpinner(callback=self.confirmation_message_int)
        self.precision_spinner.set_range(2, 10)
        self.precision_spinner.setWrapping(True)
        param_grid.addWidget(self.precision_label, 0, 0)
        param_grid.addWidget(self.precision_spinner, 0, 1)

        # #############################################################################################################
        # Results Frame
        # #############################################################################################################
        res_label = FCLabel('%s' % _("Minimum distance"), color='green', bold=True)
        res_label.setToolTip(_("Display minimum distance between copper features."))
        self.layout.addWidget(res_label)

        res_frame = FCFrame()
        self.layout.addWidget(res_frame)

        res_grid = GLay(v_spacing=5, h_spacing=3, c_stretch=[0, 1, 0])
        res_frame.setLayout(res_grid)

        # Result value
        self.result_label = FCLabel('%s:' % _("Determined"))
        self.result_entry = FCEntry()
        self.result_entry.setReadOnly(True)

        self.units_lbl = FCLabel(self.units.lower())
        self.units_lbl.setDisabled(True)

        res_grid.addWidget(self.result_label, 0, 0)
        res_grid.addWidget(self.result_entry, 0, 1)
        res_grid.addWidget(self.units_lbl, 0, 2)

        # Frequency of minimum encounter
        self.freq_label = FCLabel('%s:' % _("Occurring"))
        self.freq_label.setToolTip(_("How many times this minimum is found."))
        self.freq_entry = FCEntry()
        self.freq_entry.setReadOnly(True)

        res_grid.addWidget(self.freq_label, 2, 0)
        res_grid.addWidget(self.freq_entry, 2, 1, 1, 2)

        # Control if to display the locations of where the minimum was found
        self.locations_cb = FCCheckBox(_("Minimum points coordinates"))
        self.locations_cb.setToolTip(_("Coordinates for points where minimum distance was found."))
        res_grid.addWidget(self.locations_cb, 4, 0, 1, 3)

        # Locations where minimum was found
        self.locations_textb = FCTextArea()
        self.locations_textb.setPlaceholderText(
            _("Coordinates for points where minimum distance was found.")
        )
        self.locations_textb.setReadOnly(True)
        stylesheet = """
                                QTextEdit { selection-background-color:blue;
                                            selection-color:white;
                                }
                             """

        self.locations_textb.setStyleSheet(stylesheet)
        res_grid.addWidget(self.locations_textb, 6, 0, 1, 3)

        # "Jump" button
        self.locate_button = FCButton(_("Jump to selected position"))
        self.locate_button.setToolTip(
            _("Select a position in the Locations text box and then\n"
              "click this button.")
        )
        self.locate_button.setMinimumWidth(60)
        self.locate_button.setDisabled(True)
        res_grid.addWidget(self.locate_button, 8, 0, 1, 3)

        # #############################################################################################################
        # Other Distances
        # #############################################################################################################
        self.title_second_res_label = FCLabel('%s' % _("Other distances"), color='magenta', bold=True)
        self.title_second_res_label.setToolTip(_("Will display other distances in the Gerber file ordered from\n"
                                                 "the minimum to the maximum, not including the absolute minimum."))
        self.layout.addWidget(self.title_second_res_label)

        other_frame = FCFrame()
        self.layout.addWidget(other_frame)

        other_grid = GLay(v_spacing=5, h_spacing=3)
        other_frame.setLayout(other_grid)

        # Control if to display the locations of where the minimum was found
        self.sec_locations_cb = FCCheckBox(_("Other distances points coordinates"))
        self.sec_locations_cb.setToolTip(_("Other distances and the coordinates for points\n"
                                           "where the distance was found."))
        other_grid.addWidget(self.sec_locations_cb, 0, 0, 1, 2)

        # this way I can hide/show the frame
        self.sec_locations_frame = QtWidgets.QFrame()
        self.sec_locations_frame.setContentsMargins(0, 0, 0, 0)
        other_grid.addWidget(self.sec_locations_frame, 2, 0, 1, 2)

        self.distances_box = QtWidgets.QVBoxLayout()
        self.distances_box.setContentsMargins(0, 0, 0, 0)
        self.sec_locations_frame.setLayout(self.distances_box)

        # Other Distances label
        self.distances_label = FCLabel('%s' % _("Gerber distances"))
        self.distances_label.setToolTip(_("Other distances and the coordinates for points\n"
                                          "where the distance was found."))
        self.distances_box.addWidget(self.distances_label)

        # Other distances
        self.distances_textb = FCTextArea()
        self.distances_textb.setPlaceholderText(
            _("Other distances and the coordinates for points\n"
              "where the distance was found.")
        )
        self.distances_textb.setReadOnly(True)
        stylesheet = """
                                QTextEdit { selection-background-color:blue;
                                            selection-color:white;
                                }
                             """

        self.distances_textb.setStyleSheet(stylesheet)
        self.distances_box.addWidget(self.distances_textb)

        self.distances_box.addWidget(FCLabel(''))

        # Other Locations label
        self.locations_label = FCLabel('%s' % _("Points coordinates"))
        self.locations_label.setToolTip(_("Other distances and the coordinates for points\n"
                                          "where the distance was found."))
        self.distances_box.addWidget(self.locations_label)

        # Locations where minimum was found
        self.locations_sec_textb = FCTextArea()
        self.locations_sec_textb.setPlaceholderText(
            _("Other distances and the coordinates for points\n"
              "where the distance was found.")
        )
        self.locations_sec_textb.setReadOnly(True)
        stylesheet = """
                                QTextEdit { selection-background-color:blue;
                                            selection-color:white;
                                }
                             """

        self.locations_sec_textb.setStyleSheet(stylesheet)
        self.distances_box.addWidget(self.locations_sec_textb)

        # "Jump" button
        self.locate_sec_button = FCButton(_("Jump to selected position"))
        self.locate_sec_button.setToolTip(
            _("Select a position in the Locations text box and then\n"
              "click this button.")
        )
        self.locate_sec_button.setMinimumWidth(60)
        self.locate_sec_button.setDisabled(True)
        self.distances_box.addWidget(self.locate_sec_button)

        # GO button
        self.calculate_button = FCButton(_("Find Minimum"), bold=True)
        self.calculate_button.setIcon(QtGui.QIcon(self.app.resource_location + '/open_excellon32.png'))
        self.calculate_button.setToolTip(
            _("Calculate the minimum distance between copper features,\n"
              "this will allow the determination of the right tool to\n"
              "use for isolation or copper clearing.")
        )
        self.calculate_button.setMinimumWidth(60)
        self.layout.addWidget(self.calculate_button)

        GLay.set_common_column_size([param_grid, res_grid], 0)

        self.layout.addStretch(1)

        # ## Reset Tool
        self.reset_button = FCButton(_("Reset Tool"), bold=True)
        self.reset_button.setIcon(QtGui.QIcon(self.app.resource_location + '/reset32.png'))
        self.reset_button.setToolTip(
            _("Will reset the tool parameters.")
        )
        self.layout.addWidget(self.reset_button)

        self.loc_ois = OptionalHideInputSection(self.locations_cb, [self.locations_textb, self.locate_button])
        self.sec_loc_ois = OptionalHideInputSection(self.sec_locations_cb, [self.sec_locations_frame])

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
