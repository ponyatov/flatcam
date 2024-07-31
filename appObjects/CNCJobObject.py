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

from PyQt6 import QtCore, QtWidgets

from appEditors.appTextEditor import AppTextEditor
from appObjects.AppObjectTemplate import FlatCAMObj, ObjectDeleted
from appGUI.GUIElements import FCFileSaveDialog, FCCheckBox
from appGUI.ObjectUI import CNCObjectUI
from camlib import CNCjob

import os
import sys
import math
import re

from io import StringIO
from datetime import datetime as dt
from copy import deepcopy

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class CNCJobObject(FlatCAMObj, CNCjob):
    """
    Represents G-Code.
    """
    optionChanged = QtCore.pyqtSignal(str)
    build_al_table_sig = QtCore.pyqtSignal()

    ui_type = CNCObjectUI

    def __init__(self, name, units="in", kind="generic", z_move=0.1,
                 feedrate=3.0, feedrate_rapid=3.0, z_cut=-0.002, tooldia=0.0,
                 spindlespeed=None):

        self.app.log.debug("Creating CNCJob object...")

        self.decimals = self.app.decimals

        CNCjob.__init__(self, units=units, kind=kind, z_move=z_move,
                        feedrate=feedrate, feedrate_rapid=feedrate_rapid, z_cut=z_cut, tooldia=tooldia,
                        spindlespeed=spindlespeed, steps_per_circle=int(self.app.options["cncjob_steps_per_circle"]))

        FlatCAMObj.__init__(self, name)

        self.kind = "cncjob"

        self.obj_options.update({
            "plot": True,
            "tooldia": 0.03937,  # 0.4mm in inches
            "append": "",
            "prepend": "",
            "dwell": False,
            "dwelltime": 1,
            "type": 'Geometry',

            "cncjob_tooldia": self.app.options["cncjob_tooldia"],
            "cncjob_coords_type": self.app.options["cncjob_coords_type"],
            "cncjob_coords_decimals": self.app.options["cncjob_coords_decimals"],
            "cncjob_fr_decimals": self.app.options["cncjob_fr_decimals"],

            # bed square compensation
            "cncjob_bed_max_x": self.app.options["cncjob_bed_max_x"],
            "cncjob_bed_max_y": self.app.options["cncjob_bed_max_y"],
            "cncjob_bed_offset_x": self.app.options["cncjob_bed_offset_x"],
            "cncjob_bed_offset_y": self.app.options["cncjob_bed_offset_y"],
            "cncjob_bed_skew_x": self.app.options["cncjob_bed_skew_x"],
            "cncjob_bed_skew_y": self.app.options["cncjob_bed_skew_y"],

            "cncjob_steps_per_circle": 16,

            # "toolchange_macro": '',
            # "toolchange_macro_enable": False
            "tools_al_travel_z": self.app.options["tools_al_travel_z"],
            "tools_al_probe_depth": self.app.options["tools_al_probe_depth"],
            "tools_al_probe_fr": self.app.options["tools_al_probe_fr"],
            "tools_al_controller": self.app.options["tools_al_controller"],
            "tools_al_method": self.app.options["tools_al_method"],
            "tools_al_mode": self.app.options["tools_al_mode"],
            "tools_al_rows": self.app.options["tools_al_rows"],
            "tools_al_columns": self.app.options["tools_al_columns"],
            "tools_al_grbl_jog_step": self.app.options["tools_al_grbl_jog_step"],
            "tools_al_grbl_jog_fr": self.app.options["tools_al_grbl_jog_fr"],
        })

        '''
            When self.tools is an attribute of a CNCJob object created from a Geometry object.
            This is a dict of dictionaries. Each dict is associated with a tool present in the file. The key is the 
            diameter of the tools and the value is another dict that will hold the data under the following form:
               {tooldia:   {
                           'tooluid': 1,
                           'offset': 'Path',
                           'type_item': 'Rough',
                           'tool_type': 'C1',
                           'data': {} # a dict to hold the parameters
                           'gcode': "" # a string with the actual GCODE
                           'gcode_parsed': {} # dictionary holding the CNCJob geometry and type of geometry 
                           (cut or move)
                           'solid_geometry': []
                           },
                           ...
               }
            It is populated in the GeometryObject.mtool_gen_cncjob()
            BEWARE: I rely on the ordered nature of the Python 3.7 dictionary. Things might change ...
        '''

        '''
            When self.tools is an attribute of a CNCJob object created from a Geometry object.
            This is a dict of dictionaries. Each dict is associated with a tool present in the file. The key is the 
            diameter of the tools and the value is another dict that will hold the data under the following form:
              {tooldia:   {
                          'tool': int,
                          'nr_drills': int,
                          'nr_slots': int,
                          'offset': float,
                          'data': {},           a dict to hold the parameters
                          'gcode': "",          a string with the actual GCODE
                          'gcode_parsed': [],   list of dicts holding the CNCJob geometry and 
                                                type of geometry (cut or move)
                          'solid_geometry': [],
                          },
                          ...
              }
           It is populated in the ExcellonObject.on_create_cncjob_click() but actually 
           it's done in camlib.CNCJob.tcl_gcode_from_excellon_by_tool()
           BEWARE: I rely on the ordered nature of the Python 3.7 dictionary. Things might change ...
       '''
        self.tools = {}

        # the current tool that is used to generate GCode
        self.tool = None

        # flag to store if the CNCJob is part of a special group of CNCJob objects that can't be processed by the
        # default engine of FlatCAM. They generated by some of tools and are special cases of CNCJob objects.
        self.special_group = None

        # for now it show if the plot will be done for multi-tool CNCJob (True) or for single tool
        # (like the one in the TCL Command), False
        self.multitool = False

        self.multigeo = False

        self.coords_decimals = 4
        self.fr_decimals = 2

        self.annotations_dict = {}

        # used for parsing the GCode lines to adjust the GCode when the GCode is offseted or scaled
        gcodex_re_string = r'(?=.*(X[-\+]?\d*\.\d*))'
        self.g_x_re = re.compile(gcodex_re_string)
        gcodey_re_string = r'(?=.*(Y[-\+]?\d*\.\d*))'
        self.g_y_re = re.compile(gcodey_re_string)
        gcodez_re_string = r'(?=.*(Z[-\+]?\d*\.\d*))'
        self.g_z_re = re.compile(gcodez_re_string)

        gcodef_re_string = r'(?=.*(F[-\+]?\d*\.\d*))'
        self.g_f_re = re.compile(gcodef_re_string)
        gcodet_re_string = r'(?=.*(\=\s*[-\+]?\d*\.\d*))'
        self.g_t_re = re.compile(gcodet_re_string)

        gcodenr_re_string = r'([+-]?\d*\.\d+)'
        self.g_nr_re = re.compile(gcodenr_re_string)

        if self.app.use_3d_engine:
            self.text_col = self.app.plotcanvas.new_text_collection()
            self.text_col.enabled = True
            self.annotation = self.app.plotcanvas.new_text_group(collection=self.text_col)

        self.gcode_editor_tab = None
        self.gcode_viewer_tab = None

        self.source_file = ''
        self.units_found = self.app.app_units

        self.prepend_snippet = ''
        self.append_snippet = ''
        self.gc_header = ''
        self.gc_start = ''
        self.gc_end = ''

        # it is possible that the user will process only a few tools not all in the parent object
        # here we store the used tools so the UI will build only those that were generated
        self.used_tools = []

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from predecessors.
        self.ser_attrs += [
            'obj_options', 'kind', 'tools', 'multitool', 'append_snippet', 'prepend_snippet', 'gc_header', 'gc_start',
            'multigeo', 'used_tools'
        ]

        # this is used, so we don't recreate the GCode for loaded objects in set_ui(), it is already there
        self.is_loaded_from_project = False

    def build_ui(self):
        self.ui_disconnect()

        FlatCAMObj.build_ui(self)
        self.app.log.debug("CNCJobObject.build_ui()")

        self.units = self.app.app_units.upper()

        # if the FlatCAM object is Excellon don't build the CNC Tools Table but hide it
        self.ui.cnc_tools_table.hide()
        self.ui.exc_cnc_tools_table.hide()

        if self.obj_options['type'].lower() == 'geometry':
            self.build_cnc_tools_table()
            self.ui.cnc_tools_table.show()

        if self.obj_options['type'].lower() == 'excellon':
            try:
                self.build_excellon_cnc_tools()
            except Exception as err:
                self.app.log.error("appObjects.CNCJobObject.build_ui -> %s" % str(err))
            self.ui.exc_cnc_tools_table.show()

        self.ui_connect()

    def build_cnc_tools_table(self):
        tool_idx = 0

        # reset the Tools Table
        self.ui.cnc_tools_table.setRowCount(0)

        # for the case when self.tools is empty: it can happen for old projects who stored the data elsewhere
        if not self.tools:
            self.ui.cnc_tools_table.setRowCount(1)
        else:
            n = len(self.used_tools)
            self.ui.cnc_tools_table.setRowCount(n)

        for dia_key, dia_value in self.tools.items():
            if dia_key in self.used_tools:
                tool_idx += 1
                row_no = tool_idx - 1

                t_id = QtWidgets.QTableWidgetItem('%d' % int(tool_idx))
                # id.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.ui.cnc_tools_table.setItem(row_no, 0, t_id)  # Tool name/id

                # Make sure that the tool diameter when in MM is with no more than 2 decimals.
                # There are no tool bits in MM with more than 2 decimals diameter.
                # For INCH the decimals should be no more than 4. There are no tools under 10mils.

                dia_item = QtWidgets.QTableWidgetItem('%.*f' % (self.decimals, float(dia_value['tooldia'])))

                offset_txt = list(str(dia_value['data']['tools_mill_offset_value']))
                offset_txt[0] = offset_txt[0].upper()
                offset_item = QtWidgets.QTableWidgetItem(''.join(offset_txt))

                job_item_options = [_('Roughing'), _('Finishing'), _('Isolation'), _('Polishing')]
                tool_shape_options = ["C1", "C2", "C3", "C4", "B", "V", "L"]

                try:
                    job_item_txt = job_item_options[dia_value['data']['tools_mill_job_type']]
                except TypeError:
                    job_item_txt = dia_value['data']['tools_mill_job_type']
                job_item = QtWidgets.QTableWidgetItem(job_item_txt)

                try:
                    tool_shape_item_txt = tool_shape_options[dia_value['data']['tools_mill_tool_shape']]
                except TypeError:
                    tool_shape_item_txt = dia_value['data']['tools_mill_tool_shape']
                tool_shape_item = QtWidgets.QTableWidgetItem(tool_shape_item_txt)

                t_id.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                dia_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                offset_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                job_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                tool_shape_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)

                # hack so the checkbox stay centered in the table cell
                # used this:
                # https://stackoverflow.com/questions/32458111/pyqt-allign-checkbox-and-put-it-in-every-row
                # plot_item = QtWidgets.QWidget()
                # checkbox = FCCheckBox()
                # checkbox.setCheckState(QtCore.Qt.Checked)
                # qhboxlayout = QtWidgets.QHBoxLayout(plot_item)
                # qhboxlayout.addWidget(checkbox)
                # qhboxlayout.setAlignment(QtCore.Qt.AlignCenter)
                # qhboxlayout.setContentsMargins(0, 0, 0, 0)
                plot_item = FCCheckBox()
                plot_item.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
                tool_uid_item = QtWidgets.QTableWidgetItem(str(dia_key))
                if self.ui.plot_cb.isChecked():
                    plot_item.setChecked(True)

                self.ui.cnc_tools_table.setItem(row_no, 1, dia_item)  # Diameter
                self.ui.cnc_tools_table.setItem(row_no, 2, offset_item)  # Offset
                self.ui.cnc_tools_table.setItem(row_no, 3, job_item)  # Job Type
                self.ui.cnc_tools_table.setItem(row_no, 4, tool_shape_item)  # Tool Shape

                # ## REMEMBER: THIS COLUMN IS HIDDEN IN OBJECTUI.PY # ##
                self.ui.cnc_tools_table.setItem(row_no, 5, tool_uid_item)  # Tool unique ID)
                self.ui.cnc_tools_table.setCellWidget(row_no, 6, plot_item)

        # make the diameter column editable
        # for row in range(tool_idx):
        #     self.ui.cnc_tools_table.item(row, 1).setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
        #                                                   QtCore.Qt.ItemFlag.ItemIsEnabled)

        for row in range(tool_idx):
            self.ui.cnc_tools_table.item(row, 0).setFlags(
                self.ui.cnc_tools_table.item(row, 0).flags() ^ QtCore.Qt.ItemFlag.ItemIsSelectable)

        self.ui.cnc_tools_table.resizeColumnsToContents()
        self.ui.cnc_tools_table.resizeRowsToContents()

        vertical_header = self.ui.cnc_tools_table.verticalHeader()
        # vertical_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        vertical_header.hide()
        self.ui.cnc_tools_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        horizontal_header = self.ui.cnc_tools_table.horizontalHeader()
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
        horizontal_header.resizeSection(4, 17)
        # horizontal_header.setStretchLastSection(True)
        self.ui.cnc_tools_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.ui.cnc_tools_table.setColumnWidth(0, 20)
        self.ui.cnc_tools_table.setColumnWidth(4, 40)
        self.ui.cnc_tools_table.setColumnWidth(6, 17)

        # self.ui.geo_tools_table.setSortingEnabled(True)

        self.ui.cnc_tools_table.setMinimumHeight(self.ui.cnc_tools_table.getHeight())
        self.ui.cnc_tools_table.setMaximumHeight(self.ui.cnc_tools_table.getHeight())

    def build_excellon_cnc_tools(self):
        # for the case that self.tools is empty: old projects
        if not self.tools:
            return

        # reset the Tools Table
        self.ui.exc_cnc_tools_table.setRowCount(0)

        n = len(self.used_tools)
        self.ui.exc_cnc_tools_table.setRowCount(n)

        row_no = 0
        for t_id, dia_value in self.tools.items():
            if t_id in self.used_tools:
                tooldia = self.tools[t_id]['tooldia']

                try:
                    offset_val = self.app.dec_format(float(dia_value['offset']), self.decimals) + \
                                 float(dia_value['data']['tools_drill_cutz'])
                except KeyError:
                    offset_val = self.app.dec_format(float(dia_value['offset_z']), self.decimals) + \
                                 float(dia_value['data']['tools_drill_cutz'])
                except ValueError:
                    # for older loaded projects
                    offset_val = self.z_cut

                try:
                    nr_drills = int(dia_value['nr_drills'])
                except (KeyError, ValueError):
                    # for older loaded projects
                    nr_drills = 0

                try:
                    nr_slots = int(dia_value['nr_slots'])
                except (KeyError, ValueError):
                    # for older loaded projects
                    nr_slots = 0

                t_id_item = QtWidgets.QTableWidgetItem('%d' % int(t_id))
                dia_item = QtWidgets.QTableWidgetItem('%.*f' % (self.decimals, float(tooldia)))
                nr_drills_item = QtWidgets.QTableWidgetItem('%d' % nr_drills)
                nr_slots_item = QtWidgets.QTableWidgetItem('%d' % nr_slots)
                cutz_item = QtWidgets.QTableWidgetItem('%f' % offset_val)
                t_id_item_2 = QtWidgets.QTableWidgetItem('%d' % int(t_id))

                t_id_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                dia_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                nr_drills_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                nr_slots_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                t_id_item_2.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                cutz_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)

                plot_cnc_exc_item = FCCheckBox()
                plot_cnc_exc_item.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)

                if self.ui.plot_cb.isChecked():
                    plot_cnc_exc_item.setChecked(True)

                self.ui.exc_cnc_tools_table.setItem(row_no, 0, t_id_item)  # Tool name/id
                self.ui.exc_cnc_tools_table.setItem(row_no, 1, dia_item)  # Diameter
                self.ui.exc_cnc_tools_table.setItem(row_no, 2, nr_drills_item)  # Nr of drills
                self.ui.exc_cnc_tools_table.setItem(row_no, 3, nr_slots_item)  # Nr of slots

                # ## REMEMBER: THIS COLUMN IS HIDDEN IN OBJECTUI.PY # ##
                self.ui.exc_cnc_tools_table.setItem(row_no, 4, t_id_item_2)  # Tool unique ID)
                self.ui.exc_cnc_tools_table.setItem(row_no, 5, cutz_item)
                # add it only if there is any gcode in the tool storage
                if dia_value['gcode_parsed']:
                    self.ui.exc_cnc_tools_table.setCellWidget(row_no, 6, plot_cnc_exc_item)

                row_no += 1

        for row in range(row_no):
            self.ui.exc_cnc_tools_table.item(row, 0).setFlags(
                self.ui.exc_cnc_tools_table.item(row, 0).flags() ^ QtCore.Qt.ItemFlag.ItemIsSelectable)

        self.ui.exc_cnc_tools_table.resizeColumnsToContents()
        self.ui.exc_cnc_tools_table.resizeRowsToContents()

        vertical_header = self.ui.exc_cnc_tools_table.verticalHeader()
        vertical_header.hide()
        self.ui.exc_cnc_tools_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        horizontal_header = self.ui.exc_cnc_tools_table.horizontalHeader()
        horizontal_header.setMinimumSectionSize(10)
        horizontal_header.setDefaultSectionSize(70)
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        horizontal_header.resizeSection(0, 20)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        horizontal_header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Fixed)

        # horizontal_header.setStretchLastSection(True)
        self.ui.exc_cnc_tools_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.ui.exc_cnc_tools_table.setColumnWidth(0, 20)
        self.ui.exc_cnc_tools_table.setColumnWidth(6, 17)

        self.ui.exc_cnc_tools_table.setMinimumHeight(self.ui.exc_cnc_tools_table.getHeight())
        self.ui.exc_cnc_tools_table.setMaximumHeight(self.ui.exc_cnc_tools_table.getHeight())

    def set_ui(self, ui):
        FlatCAMObj.set_ui(self, ui)

        self.app.log.debug("FlatCAMCNCJob.set_ui()")

        assert isinstance(self.ui, CNCObjectUI), \
            "Expected a CNCObjectUI, got %s" % type(self.ui)

        self.units = self.app.app_units.upper()
        self.units_found = self.app.app_units

        # this signal has to be connected to it's slot before the defaults are populated
        # the decision done in the slot has to override the default value set below
        # self.ui.toolchange_cb.toggled.connect(self.on_toolchange_custom_clicked)

        self.form_fields.update({
            "plot":             self.ui.plot_cb,
            "tooldia":          self.ui.tooldia_entry,
            # "append":         self.ui.append_text,
            # "prepend":        self.ui.prepend_text,
            # "toolchange_macro": self.ui.toolchange_text,
            # "toolchange_macro_enable": self.ui.toolchange_cb,
        })

        # Fill form fields only on object create
        self.to_form()

        # this means that the object that created this CNCJob was an Excellon or Geometry
        try:
            if self.travel_distance:
                self.ui.estimated_frame.show()
                self.ui.t_distance_entry.set_value(self.app.dec_format(self.travel_distance, self.decimals))
                self.ui.units_label.setText(str(self.units).lower())
                self.ui.units_label.setDisabled(True)

                self.ui.t_time_label.show()
                self.ui.t_time_entry.setVisible(True)
                self.ui.t_time_entry.setDisabled(True)
                # if time is more than 1 then we have minutes, else we have seconds
                if self.routing_time > 1:
                    time_r = self.app.dec_format(math.ceil(float(self.routing_time)), self.decimals)
                    self.ui.t_time_entry.set_value(time_r)
                    self.ui.units_time_label.setText('min')
                else:
                    time_r = self.routing_time * 60
                    time_r = self.app.dec_format(math.ceil(float(time_r)), self.decimals)
                    self.ui.t_time_entry.set_value(time_r)
                    self.ui.units_time_label.setText('sec')
                self.ui.units_time_label.setDisabled(True)
        except AttributeError:
            pass

        if self.multitool is False:
            self.ui.tooldia_entry.show()
            self.ui.updateplot_button.show()
        else:
            self.ui.tooldia_entry.hide()
            self.ui.updateplot_button.hide()

        # set the kind of geometries are plotted by default with plot2() from camlib.CNCJob
        self.ui.cncplot_method_combo.set_value(self.app.options["cncjob_plot_kind"])

        # #############################################################################################################
        # ##################################### SIGNALS CONNECTIONS ###################################################
        # #############################################################################################################
        self.ui.level.toggled.connect(self.on_level_changed)

        # annotation signal
        try:
            self.ui.annotation_cb.stateChanged.disconnect(self.on_annotation_change)
        except (TypeError, AttributeError):
            pass
        self.ui.annotation_cb.stateChanged.connect(self.on_annotation_change)

        # set if to display text annotations
        self.ui.annotation_cb.set_value(self.app.options["cncjob_annotation"])

        # update plot button - active only for SingleGeo type objects
        self.ui.updateplot_button.clicked.connect(self.on_updateplot_button_click)

        # Plot Kind
        self.ui.cncplot_method_combo.activated_custom.connect(self.on_plot_kind_change)

        # Export/REview GCode buttons signals
        self.ui.export_gcode_button.clicked.connect(self.on_exportgcode_button_click)
        self.ui.review_gcode_button.clicked.connect(self.on_review_code_click)

        # Editor Signal
        self.ui.editor_button.clicked.connect(lambda: self.app.on_editing_start())

        # Properties
        self.ui.info_button.toggled.connect(self.on_properties)
        self.calculations_finished.connect(self.update_area_chull)
        self.ui.treeWidget.itemExpanded.connect(self.on_properties_expanded)
        self.ui.treeWidget.itemCollapsed.connect(self.on_properties_expanded)

        # Include CNC Job Snippets changed
        self.ui.snippets_cb.toggled.connect(self.on_update_source_file)

        self.ui.autolevel_button.clicked.connect(lambda: self.app.levelling_tool.run(toggle=True))

        # ###################################### END Signal connections ###############################################
        # #############################################################################################################

        # On CNCJob object creation, generate the GCode
        if self.is_loaded_from_project is False:
            self.prepend_snippet = self.app.options['cncjob_prepend']
            self.append_snippet = self.app.options['cncjob_append']
            self.gc_header = self.gcode_header()
        else:
            # this is dealt when loading the project, the header, prepend and append are already loaded
            # by being 'serr_attrs' attributes
            pass

        gc = self.export_gcode(preamble=self.prepend_snippet, postamble=self.append_snippet, to_file=True,
                               s_code=self.gc_start)

        # set the Source File attribute with the calculated GCode
        try:
            # gc is StringIO
            self.source_file = gc.getvalue()
        except AttributeError:
            # gc is text
            self.source_file = gc

        if self.append_snippet != '' or self.prepend_snippet != '':
            self.ui.snippets_cb.set_value(True)

        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.change_level(app_mode)

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

            self.ui.annotation_cb.hide()
        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                                QToolButton
                                                {
                                                    color: red;
                                                }
                                                """)

            self.ui.annotation_cb.show()

    def ui_connect(self):
        for row in range(self.ui.cnc_tools_table.rowCount()):
            try:
                self.ui.cnc_tools_table.cellWidget(row, 6).clicked.connect(self.on_plot_cb_click_table)
            except AttributeError:
                pass
        for row in range(self.ui.exc_cnc_tools_table.rowCount()):
            try:
                self.ui.exc_cnc_tools_table.cellWidget(row, 6).clicked.connect(self.on_plot_cb_click_table)
            except AttributeError:
                pass
        self.ui.plot_cb.stateChanged.connect(self.on_plot_cb_click)

    def ui_disconnect(self):
        for row in range(self.ui.cnc_tools_table.rowCount()):
            try:
                self.ui.cnc_tools_table.cellWidget(row, 6).clicked.disconnect(self.on_plot_cb_click_table)
            except (TypeError, AttributeError):
                pass

        for row in range(self.ui.exc_cnc_tools_table.rowCount()):
            try:
                self.ui.exc_cnc_tools_table.cellWidget(row, 6).clicked.disconnect(self.on_plot_cb_click_table)
            except (TypeError, AttributeError):
                pass

        try:
            self.ui.plot_cb.stateChanged.disconnect(self.on_plot_cb_click)
        except (TypeError, AttributeError):
            pass

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

    def on_updateplot_button_click(self, *args):
        """
        Callback for the "Updata Plot" button. Reads the form for updates
        and plots the object.
        """
        self.read_form()
        self.on_plot_kind_change(dia=self.ui.tooldia_entry.get_value())

    def on_plot_kind_change(self, dia=None):
        kind = self.ui.cncplot_method_combo.get_value()

        def worker_task():
            with self.app.proc_container.new('%s ...' % _("Plotting")):
                self.plot(kind=kind, dia=dia)

        self.app.worker_task.emit({'fcn': worker_task, 'params': []})

    def on_exportgcode_button_click(self):
        """
        Handler activated by a button clicked when exporting GCode.

        :return:
        """
        self.app.defaults.report_usage("cncjob_on_exportgcode_button")

        self.read_form()
        name = self.app.collection.get_active().obj_options['name']
        save_gcode = False

        if 'Roland' in self.pp_excellon_name or 'Roland' in self.pp_geometry_name:
            _filter_ = "RML1 Files .rol (*.rol);;All Files (*.*)"
        elif 'nccad' in self.pp_excellon_name.lower() or 'nccad' in self.pp_geometry_name.lower():
            _filter_ = "KOSY Files .knc (*.knc);;All Files (*.*)"
        elif 'hpgl' in self.pp_geometry_name:
            _filter_ = "HPGL Files .plt (*.plt);;All Files (*.*)"
        else:
            save_gcode = True
            _filter_ = self.app.options['cncjob_save_filters']

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

        self.export_gcode_handler(filename, is_gcode=save_gcode)

    def export_gcode_handler(self, filename, is_gcode=True, rename_object=True):
        # preamble = ''
        # postamble = ''
        filename = str(filename)

        if filename == '':
            self.app.inform.emit('[WARNING_NOTCL] %s' % _("Export cancelled ..."))
            return
        else:
            if is_gcode is True:
                used_extension = filename.rpartition('.')[2]
                self.update_filters(last_ext=used_extension, filter_string='cncjob_save_filters')

        if rename_object:
            new_name = os.path.split(str(filename))[1].rpartition('.')[0]
            self.ui.name_entry.set_value(new_name)
            self.on_name_activate(silent=True)

        if self.source_file == '':
            return 'fail'

        try:
            force_windows_line_endings = self.app.options['cncjob_line_ending']
            if force_windows_line_endings and sys.platform != 'win32':
                with open(filename, 'w', newline='\r\n') as f:
                    for line in self.source_file:
                        f.write(line)
            else:
                with open(filename, 'w') as f:
                    for line in self.source_file:
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

        if self.app.options["global_open_style"] is False:
            self.app.file_opened.emit("gcode", filename)
        self.app.file_saved.emit("gcode", filename)
        self.app.inform.emit('[success] %s: %s' % (_("File saved to"), filename))

    def on_review_code_click(self):
        """
        Handler activated by a button clicked when reviewing GCode.

        :return:
        """

        self.app.proc_container.view.set_busy('%s...' % _("Loading"))

        # preamble = self.prepend_snippet
        # postamble = self.append_snippet
        #
        # gco = self.export_gcode(preamble=preamble, postamble=postamble, to_file=True)
        # if gco == 'fail':
        #     return
        # else:
        #     self.app.gcode_edited = gco
        self.app.gcode_edited = self.source_file

        self.gcode_editor_tab = AppTextEditor(app=self.app, plain_text=True)

        # add the tab if it was closed
        self.app.ui.plot_tab_area.addTab(self.gcode_editor_tab, '%s' % _("Code Review"))
        self.gcode_editor_tab.setObjectName('code_editor_tab')

        # delete the absolute and relative position and messages in the infobar
        self.app.ui.position_label.setText("")
        self.app.ui.rel_position_label.setText("")

        self.gcode_editor_tab.code_editor.completer_enable = False
        self.gcode_editor_tab.buttonRun.hide()

        # Switch plot_area to CNCJob tab
        self.app.ui.plot_tab_area.setCurrentWidget(self.gcode_editor_tab)

        self.gcode_editor_tab.t_frame.hide()
        # then append the text from GCode to the text editor
        try:
            # self.gcode_editor_tab.load_text(self.app.gcode_edited.getvalue(), move_to_start=True, clear_text=True)
            self.gcode_editor_tab.load_text(self.app.gcode_edited, move_to_start=True, clear_text=True)
        except Exception as e:
            self.app.log.error('FlatCAMCNCJob.on_review_code_click() -->%s' % str(e))
            return

        self.gcode_editor_tab.t_frame.show()
        self.app.proc_container.view.set_idle()

        self.gcode_editor_tab.buttonSave.hide()
        self.gcode_editor_tab.buttonOpen.hide()
        # self.gcode_editor_tab.buttonPrint.hide()
        # self.gcode_editor_tab.buttonPreview.hide()
        self.gcode_editor_tab.buttonReplace.hide()
        self.gcode_editor_tab.sel_all_cb.hide()
        self.gcode_editor_tab.entryReplace.hide()
        self.gcode_editor_tab.code_editor.setReadOnly(True)

        # make sure that the Find entry keeps the focus on the line
        self.gcode_editor_tab.entryFind.keep_focus = False

        self.app.inform.emit('[success] %s...' % _('Loaded Machine Code into Code Editor'))

    def on_update_source_file(self):
        preamble = ''
        postamble = ''
        if self.ui.snippets_cb.get_value():
            preamble = self.prepend_snippet
            postamble = self.append_snippet

        gco = self.export_gcode(preamble=preamble, postamble=postamble, to_file=True)
        if gco == 'fail':
            self.app.inform.emit('[ERROR_NOTCL] %s %s...' % (_('Failed.'), _('CNC Machine Code could not be updated')))
            return
        else:
            self.source_file = gco.getvalue()
            self.app.inform.emit('[success] %s...' % _('CNC Machine Code was updated'))

    def gcode_header(self, comment_start_symbol=None, comment_stop_symbol=None):
        """
        Will create a header to be added to all GCode files generated by FlatCAM

        :param comment_start_symbol:    A symbol to be used as the first symbol in a comment
        :param comment_stop_symbol:     A symbol to be used as the last symbol in a comment
        :return:                        A string with a GCode header
        """

        self.app.log.debug("FlatCAMCNCJob.gcode_header()")
        time_str = "{:%A, %d %B %Y at %H:%M}".format(dt.now())
        marlin = False
        hpgl = False
        probe_pp = False
        nccad_pp = False

        gcode = ''

        start_comment = comment_start_symbol if comment_start_symbol is not None else '('
        stop_comment = comment_stop_symbol if comment_stop_symbol is not None else ')'

        if self.obj_options['type'].lower() == 'geometry':
            try:
                for key in self.tools:
                    try:
                        ppg = self.tools[key]['data']['tools_mill_ppname_g']
                    except KeyError:
                        # for older loaded projects
                        ppg = self.app.options['tools_mill_ppname_g']

                    if 'marlin' in ppg.lower() or 'repetier' in ppg.lower():
                        marlin = True
                        break
                    if ppg == 'hpgl':
                        hpgl = True
                        break
                    if "toolchange_probe" in ppg.lower():
                        probe_pp = True
                        break
                    if "nccad" in ppg.lower():
                        nccad_pp = True
            except Exception as e:
                self.app.log.debug("FlatCAMCNCJob.gcode_header() error: --> %s" % str(e))
                pass

        try:
            if 'marlin' in self.obj_options['tools_drill_ppname_e'].lower() or \
                    'repetier' in self.obj_options['tools_drill_ppname_e'].lower():
                marlin = True
        except KeyError:
            # self.app.log.debug("FlatCAMCNCJob.gcode_header(): --> There is no such self.option: %s" % str(e))
            pass

        try:
            if "toolchange_probe" in self.obj_options['tools_drill_ppname_e'].lower():
                probe_pp = True
        except KeyError:
            # self.app.log.debug("FlatCAMCNCJob.gcode_header(): --> There is no such self.option: %s" % str(e))
            pass

        try:
            if 'nccad' in self.obj_options['tools_drill_ppname_e'].lower():
                nccad_pp = True
        except KeyError:
            pass

        if marlin is True:
            gcode += ';Marlin(Repetier) G-code generated by FlatCAM Evo v%s - Version Date:    %s\n' % \
                     (str(self.app.version), str(self.app.version_date)) + '\n'

            gcode += ';Name: ' + str(self.obj_options['name']) + '\n'
            gcode += ';Type: ' + "G-code from " + str(self.obj_options['type']) + '\n'

            gcode += ';Units: ' + self.units.upper() + '\n' + "\n"
            gcode += ';Created on ' + time_str + '\n' + '\n'
        elif hpgl is True:
            gcode += 'CO "HPGL code generated by FlatCAM Evo v%s - Version Date:    %s' % \
                     (str(self.app.version), str(self.app.version_date)) + '";\n'

            gcode += 'CO "Name: ' + str(self.obj_options['name']) + '";\n'
            gcode += 'CO "Type: ' + "HPGL code from " + str(self.obj_options['type']) + '";\n'

            gcode += 'CO "Units: ' + self.units.upper() + '";\n'
            gcode += 'CO "Created on ' + time_str + '";\n'
        elif probe_pp is True:
            gcode += '(G-code generated by FlatCAM Evo v%s - Version Date: %s)\n' % \
                     (str(self.app.version), str(self.app.version_date)) + '\n'

            gcode += '(This GCode tool change is done by using a Probe.)\n' \
                     '(Make sure that before you start the job you first do a rough zero for Z axis.)\n' \
                     '(This means that you need to zero the CNC axis and then jog to the toolchange X, Y location,)\n' \
                     '(mount the probe and adjust the Z so more or less the probe tip touch the plate. ' \
                     'Then zero the Z axis.)\n' + '\n'

            gcode += '(Name: ' + str(self.obj_options['name']) + ')\n'
            gcode += '(Type: ' + "G-code from " + str(self.obj_options['type']) + ')\n'

            gcode += '(Units: ' + self.units.upper() + ')\n' + "\n"
            gcode += '(Created on ' + time_str + ')\n' + '\n'
        elif nccad_pp is True:
            gcode += ';NCCAD9 G-code generated by FlatCAM Evo v%s - Version Date:    %s\n' % \
                     (str(self.app.version), str(self.app.version_date)) + '\n'

            gcode += ';Name: ' + str(self.obj_options['name']) + '\n'
            gcode += ';Type: ' + "G-code from " + str(self.obj_options['type']) + '\n'

            gcode += ';Units: ' + self.units.upper() + '\n' + "\n"
            gcode += ';Created on ' + time_str + '\n' + '\n'
        else:
            gcode += '%sG-code generated by FlatCAM Evo v%s - Version Date: %s%s\n' % \
                     (start_comment, str(self.app.version), str(self.app.version_date), stop_comment) + '\n'

            gcode += '%sName: ' % start_comment + str(self.obj_options['name']) + '%s\n' % stop_comment
            gcode += '%sType: ' % start_comment + "G-code from " + str(self.obj_options['type']) + '%s\n' % stop_comment

            gcode += '%sUnits: ' % start_comment + self.units.upper() + '%s\n' % stop_comment + "\n"
            gcode += '%sCreated on ' % start_comment + time_str + '%s\n' % stop_comment + '\n'

        return gcode

    @staticmethod
    def gcode_footer(end_command=None):
        """
        Will add the M02 to the end of GCode, if requested.

        :param end_command: 'M02' or 'M30' - String
        :return:
        """
        if end_command:
            return end_command
        else:
            return 'M02'

    def export_gcode(self, filename=None, preamble='', postamble='', to_file=False, from_tcl=False, glob_gcode='',
                     s_code=''):
        """
        This will save the GCode from the Gcode object to a file on the OS filesystem

        :param filename:    filename for the GCode file
        :param preamble:    a custom Gcode block to be added at the beginning of the Gcode file
        :param postamble:   a custom Gcode block to be added at the end of the Gcode file
        :param to_file:     if False then no actual file is saved but the app will know that a file was created
        :param from_tcl:    True if run from Tcl Shell
        :param glob_gcode:  Passing an object attribute that is used to hold GCode; string
        :return:            None
        """

        global_gcode = self.gcode if glob_gcode == '' else glob_gcode
        start_code = self.gc_start if s_code == '' else s_code
        include_header = True

        if preamble == '':
            preamble = self.app.options["cncjob_prepend"]
        if postamble == '':
            postamble = self.app.options["cncjob_append"]

        # try:
        #     if self.special_group:
        #         self.app.inform.emit('[WARNING_NOTCL] %s %s %s.' %
        #                              (_("This CNCJob object can't be processed because it is a"),
        #                               str(self.special_group),
        #                               _("CNCJob object")))
        #         return 'fail'
        # except AttributeError:
        #     pass

        # if this dict is not empty then the object is a Geometry object
        if self.obj_options['type'].lower() == 'geometry':
            # for the case that self.tools is empty: old projects
            try:
                first_key = list(self.tools.keys())[0]
                try:
                    include_header = self.app.preprocessors[self.tools[first_key]['data']['tools_mill_ppname_g']]
                except KeyError:
                    try:
                        # for older loaded projects
                        self.app.log.debug(
                            "CNCJobObject.export_gcode() --> old project detected. Results are unreliable.")
                        include_header = self.app.preprocessors[self.app.options['ppname_g']]
                    except KeyError:
                        # for older loaded projects
                        self.app.log.debug(
                            "CNCJobObject.export_gcode() --> old project detected. Results are unreliable.")
                        include_header = self.app.preprocessors[self.app.options['tools_mill_ppname_g']]

                include_header = include_header.include_header
            except (TypeError, IndexError):
                include_header = self.app.preprocessors['default'].include_header

        # if this dict is not empty then the object is an Excellon object
        if self.obj_options['type'].lower() == 'excellon':
            # for the case that self.tools is empty: old projects
            try:
                first_key = list(self.tools.keys())[0]
                try:
                    include_header = self.app.preprocessors[
                        self.tools[first_key]['data']['tools_drill_ppname_e']
                    ].include_header
                except KeyError:
                    # for older loaded projects
                    try:
                        include_header = self.app.preprocessors[
                            self.tools[first_key]['data']['ppname_e']
                        ].include_header
                    except KeyError:
                        self.app.log.debug(
                            "CNCJobObject.export_gcode() --> old project detected. Results are unreliable.")
                        # for older loaded projects
                        include_header = self.app.preprocessors[
                            self.app.options['tools_drill_ppname_e']
                        ].include_header
            except TypeError:
                # when self.tools is empty - old projects
                include_header = self.app.preprocessors['default'].include_header

        gcode = ''

        if include_header is False:
            # detect if using multi-tool and make the Gcode summation correctly for each case
            if self.multitool is True:
                try:
                    if self.obj_options['type'].lower() == 'geometry':
                        for tooluid_key in self.tools:
                            for key, value in self.tools[tooluid_key].items():
                                if key == 'gcode':
                                    gcode += value
                                    break
                except TypeError:
                    pass
            else:
                gcode += global_gcode

            # g = sstart_code + '\n' + preamble + '\n' + gcode + '\n' + postamble
            g = ''
            end_gcode = self.gcode_footer() if self.app.options['cncjob_footer'] is True else ''
            if preamble != '' and postamble != '':
                g = start_code + '\n' + preamble + '\n' + gcode + '\n' + postamble + '\n' + end_gcode
            if preamble == '':
                g = start_code + '\n' + gcode + '\n' + postamble + '\n' + end_gcode
            if postamble == '':
                g = start_code + '\n' + preamble + '\n' + gcode + '\n' + end_gcode
            if preamble == '' and postamble == '':
                g = start_code + '\n' + gcode + '\n' + end_gcode
        else:
            # detect if using multi-tool and make the Gcode summation correctly for each case
            if self.multitool is True:
                # for the case that self.tools is empty: old projects
                try:
                    if self.obj_options['type'].lower() == 'excellon':
                        for tooluid_key in self.tools:
                            for key, value in self.tools[tooluid_key].items():
                                if key == 'gcode' and value:
                                    gcode += value
                                    break
                    else:
                        # it's made from a Geometry object
                        for tooluid_key in self.tools:
                            for key, value in self.tools[tooluid_key].items():
                                if key == 'gcode' and value:
                                    gcode += value
                                    break
                except TypeError:
                    pass
            else:
                gcode += global_gcode

            end_gcode = self.gcode_footer() if self.app.options['cncjob_footer'] is True else ''

            # detect if using a HPGL preprocessor
            hpgl = False
            # for the case that self.tools is empty: old projects
            try:
                if self.obj_options['type'].lower() == 'geometry':
                    for key in self.tools:
                        if 'tools_mill_ppname_g' in self.tools[key]['data']:
                            if 'hpgl' in self.tools[key]['data']['tools_mill_ppname_g']:
                                hpgl = True
                                break
                elif self.obj_options['type'].lower() == 'excellon':
                    for key in self.tools:
                        if 'ppname_e' in self.tools[key]['data']:
                            if 'hpgl' in self.tools[key]['data']['ppname_e']:
                                hpgl = True
                                break
            except TypeError:
                hpgl = False

            if hpgl:
                processed_body_gcode = ''
                pa_re = re.compile(r"^PA\s*(-?\d+\.\d*),?\s*(-?\d+\.\d*)*;?$")

                # process body gcode
                for gline in gcode.splitlines():
                    match = pa_re.search(gline)
                    if match:
                        x_int = int(float(match.group(1)))
                        y_int = int(float(match.group(2)))
                        new_line = 'PA%d,%d;\n' % (x_int, y_int)
                        processed_body_gcode += new_line
                    else:
                        processed_body_gcode += gline + '\n'

                gcode = processed_body_gcode
                g = self.gc_header + '\n' + start_code + '\n' + preamble + '\n' + \
                    gcode + '\n' + postamble + end_gcode
            else:
                g = ''
                if preamble != '' and postamble != '':
                    g = self.gc_header + start_code + '\n' + preamble + '\n' + gcode + '\n' + \
                        postamble + '\n' + end_gcode
                if preamble == '':
                    g = self.gc_header + start_code + '\n' + gcode + '\n' + postamble + '\n' + end_gcode
                if postamble == '':
                    g = self.gc_header + start_code + '\n' + preamble + '\n' + gcode + '\n' + end_gcode
                if preamble == '' and postamble == '':
                    g = self.gc_header + start_code + '\n' + gcode + '\n' + end_gcode

        lines = StringIO(g)

        # Write
        if filename is not None:
            try:
                force_windows_line_endings = self.app.options['cncjob_line_ending']
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
        elif to_file is False:
            # Just for adding it to the recent files list.
            if self.app.options["global_open_style"] is False:
                self.app.file_opened.emit("cncjob", filename)
            self.app.file_saved.emit("cncjob", filename)

            self.app.inform.emit('[success] %s: %s' % (_("Saved to"), filename))
        else:
            return lines

    def get_gcode(self, preamble='', postamble=''):
        """
        We need this to be able to get_gcode separately for shell command export_gcode

        :param preamble:    Extra GCode added to the beginning of the GCode
        :param postamble:   Extra GCode added at the end of the GCode
        :return:            The modified GCode
        """
        return preamble + '\n' + self.gcode + "\n" + postamble

    def get_svg(self):
        # we need this to be able get_svg separately for shell command export_svg
        pass

    def on_plot_cb_click(self, *args):
        """
        Handler for clicking on the Plot checkbox.

        :param args:
        :return:
        """
        if self.muted_ui:
            return

        kind = self.ui.cncplot_method_combo.get_value()
        self.read_form_item('plot')

        self.ui_disconnect()
        # cb_flag = self.ui.plot_cb.isChecked()
        cb_flag = self.obj_options['plot']

        try:
            for row in range(self.ui.cnc_tools_table.rowCount()):
                table_cb = self.ui.cnc_tools_table.cellWidget(row, 6)
                if cb_flag:
                    table_cb.setChecked(True)
                else:
                    table_cb.setChecked(False)
        except AttributeError:
            # TODO from Tcl commands - should fix it sometime
            pass
        self.ui_connect()

        self.plot(kind=kind)

    def on_plot_cb_click_table(self):
        """
        Handler for clicking the plot checkboxes added into a Table on each row. Purpose: toggle visibility for the
        tool/aperture found on that row.
        :return:
        """

        # self.ui.cnc_tools_table.cellWidget(row, 2).widget().setCheckState(QtCore.Qt.Unchecked)
        self.ui_disconnect()
        # cw = self.sender()
        # cw_index = self.ui.cnc_tools_table.indexAt(cw.pos())
        # cw_row = cw_index.row()

        kind = self.ui.cncplot_method_combo.get_value()

        self.shapes.clear(update=True)
        if self.obj_options['type'].lower() == "excellon":
            for r in range(self.ui.exc_cnc_tools_table.rowCount()):
                row_dia = float('%.*f' % (self.decimals, float(self.ui.exc_cnc_tools_table.item(r, 1).text())))
                for tooluid_key in self.tools:
                    tooldia = float('%.*f' % (self.decimals, float(self.tools[tooluid_key]['tooldia'])))
                    if row_dia == tooldia:
                        gcode_parsed = self.tools[tooluid_key]['gcode_parsed']
                        if self.ui.exc_cnc_tools_table.cellWidget(r, 6).isChecked():
                            self.plot2(tooldia=tooldia, obj=self, visible=True, gcode_parsed=gcode_parsed, kind=kind)
        else:
            for tooluid_key in self.tools:
                tooldia = float('%.*f' % (self.decimals, float(self.tools[tooluid_key]['tooldia'])))
                gcode_parsed = self.tools[tooluid_key]['gcode_parsed']
                # tool_uid = int(self.ui.cnc_tools_table.item(cw_row, 3).text())

                for r in range(self.ui.cnc_tools_table.rowCount()):
                    if int(self.ui.cnc_tools_table.item(r, 5).text()) == int(tooluid_key):
                        if self.ui.cnc_tools_table.cellWidget(r, 6).isChecked():
                            self.plot2(tooldia=tooldia, obj=self, visible=True, gcode_parsed=gcode_parsed, kind=kind)

        self.shapes.redraw()

        # make sure that the general plot is disabled if one of the row plot's are disabled and
        # if all the row plot's are enabled also enable the general plot checkbox
        cb_cnt = 0
        total_row = self.ui.cnc_tools_table.rowCount()
        for row in range(total_row):
            if self.ui.cnc_tools_table.cellWidget(row, 6).isChecked():
                cb_cnt += 1
            else:
                cb_cnt -= 1
        if cb_cnt < total_row:
            self.ui.plot_cb.setChecked(False)
        else:
            self.ui.plot_cb.setChecked(True)
        self.ui_connect()

    def plot(self, visible=None, kind='all', dia=None):
        """
        # Does all the required setup and returns False
        # if the 'ptint' option is set to False.

        :param visible: Boolean to decide if the object will be plotted as visible or disabled on canvas
        :param kind:    String. Can be "all" or "travel" or "cut". For CNCJob plotting
        :param dia:     The diameter used to render the tool paths
        :return:        None
        """
        if not FlatCAMObj.plot(self):
            return

        visible = visible if visible else self.obj_options['plot']

        # Geometry shapes plotting
        try:
            if self.multitool is False:  # single tool usage
                dia_plot = dia
                if dia_plot is None:
                    if self.obj_options['type'].lower() == "excellon":
                        try:
                            dia_plot = float(self.obj_options["tooldia"])
                        except ValueError:
                            # we may have a tuple with only one element and a comma
                            dia_plot = [float(el) for el in self.obj_options["tooldia"].split(',') if el != ''][0]
                    else:
                        # try:
                        #     dia_plot = float(self.obj_options["tools_mill_tooldia"])
                        # except ValueError:
                        #     # we may have a tuple with only one element and a comma
                        #     dia_plot = [
                        #         float(el) for el in self.obj_options["tools_mill_tooldia"].split(',') if el != ''
                        #     ][0]
                        dia_plot = float(self.obj_options["cncjob_tooldia"])

                self.plot2(tooldia=dia_plot, obj=self, visible=visible, kind=kind)
            else:
                # I do this so the travel lines thickness will reflect the tool diameter
                # may work only for objects created within the app and not Gcode imported from elsewhere for which we
                # don't know the origin
                if self.obj_options['type'].lower() == "excellon":
                    if self.tools:
                        for toolid_key in self.used_tools:
                            dia_plot = self.app.dec_format(float(self.tools[toolid_key]['tooldia']), self.decimals)
                            gcode_parsed = self.tools[toolid_key]['gcode_parsed']
                            if not gcode_parsed:
                                self.app.log.debug("Tool %s has no 'gcode_parsed'." % str(toolid_key))
                                continue
                            # gcode_parsed = self.gcode_parsed
                            self.plot2(tooldia=dia_plot, obj=self, visible=visible, gcode_parsed=gcode_parsed,
                                       kind=kind)
                else:
                    # multiple tools usage
                    if self.tools:
                        for tooluid_key in self.used_tools:
                            dia_plot = self.app.dec_format(
                                float(self.tools[tooluid_key]['tooldia']),
                                self.decimals
                            )
                            gcode_parsed = self.tools[tooluid_key]['gcode_parsed']
                            self.plot2(tooldia=dia_plot, obj=self, visible=visible, gcode_parsed=gcode_parsed,
                                       kind=kind)
            self.shapes.redraw()
        except (ObjectDeleted, AttributeError) as err:
            self.app.log.debug("CNCJobObject.plot() --> %s" % str(err))
            self.shapes.clear(update=True)
            if self.app.use_3d_engine:
                self.annotation.clear(update=True)

        # Annotations shapes plotting
        try:
            if self.app.use_3d_engine:
                if self.ui.annotation_cb.get_value() and visible:
                    self.plot_annotations(obj=self, visible=True)
                else:
                    self.plot_annotations(obj=self, visible=False)

        except (ObjectDeleted, AttributeError):
            if self.app.use_3d_engine:
                self.annotation.clear(update=True)

    def on_annotation_change(self, val):
        """
        Handler for toggling the annotation display by clicking a checkbox.
        :return:
        """

        if self.app.use_3d_engine:
            # Annotations shapes plotting
            try:
                if self.app.use_3d_engine:
                    if val and self.ui.plot_cb.get_value():
                        self.plot_annotations(obj=self, visible=True)
                    else:
                        self.plot_annotations(obj=self, visible=False)

            except (ObjectDeleted, AttributeError):
                if self.app.use_3d_engine:
                    self.annotation.clear(update=True)

            # self.annotation.redraw()
        else:
            kind = self.ui.cncplot_method_combo.get_value()
            self.plot(kind=kind)

    def convert_units(self, units):
        """
        Units conversion used by the CNCJob objects.

        :param units:   Can be "MM" or "IN"
        :return:
        """

        self.app.log.debug("FlatCAMObj.FlatCAMECNCjob.convert_units()")

        factor = CNCjob.convert_units(self, units)
        self.obj_options["tooldia"] = float(self.obj_options["tooldia"]) * factor

        param_list = ['cutz', 'depthperpass', 'travelz', 'feedrate', 'feedrate_z', 'feedrate_rapid',
                      'endz', 'toolchangez']

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

                if dia_key == 'type':
                    tool_dia_copy[dia_key] = dia_value
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

                if dia_key == 'gcode':
                    tool_dia_copy[dia_key] = dia_value
                if dia_key == 'gcode_parsed':
                    tool_dia_copy[dia_key] = dia_value
                if dia_key == 'solid_geometry':
                    tool_dia_copy[dia_key] = dia_value

                # if dia_key == 'solid_geometry':
                #     tool_dia_copy[dia_key] = affinity.scale(dia_value, xfact=factor, origin=(0, 0))
                # if dia_key == 'gcode_parsed':
                #     for g in dia_value:
                #         g['geom'] = affinity.scale(g['geom'], factor, factor, origin=(0, 0))
                #
                #     tool_dia_copy['gcode_parsed'] = deepcopy(dia_value)
                #     tool_dia_copy['solid_geometry'] = unary_union([geo['geom'] for geo in dia_value])

            temp_tools_dict.update({
                tooluid_key: deepcopy(tool_dia_copy)
            })
            tool_dia_copy.clear()

        self.tools.clear()
        self.tools = deepcopy(temp_tools_dict)
