# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 2/14/2020                                          #
# MIT Licence                                              #
# ##########################################################

from PyQt6 import QtWidgets, QtCore, QtGui
from appTool import AppTool
from appGUI.GUIElements import VerticalScrollArea, FCLabel, FCButton, FCFrame, GLay, FCComboBox, FCEntry, \
    RadioSet, FCDoubleSpinner, NumericalEvalEntry
from camlib import flatten_shapely_geometry

import logging
from copy import deepcopy
import math

from shapely.ops import unary_union

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class ToolEtchCompensation(AppTool):

    def __init__(self, app):
        self.app = app
        self.decimals = self.app.decimals

        AppTool.__init__(self, app)

        # #############################################################################
        # ######################### Tool GUI ##########################################
        # #############################################################################
        self.ui = EtchUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

    def install(self, icon=None, separator=None, **kwargs):
        AppTool.install(self, icon, separator, shortcut='', **kwargs)

    def run(self, toggle=True):
        self.app.defaults.report_usage("ToolEtchCompensation()")
        self.app.log.debug("ToolEtchCompensation() is running ...")

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

        self.app.ui.notebook.setTabText(2, _("Etch Compensation"))

    def connect_signals_at_init(self):
        self.ui.compensate_btn.clicked.connect(self.on_compensate)
        self.ui.reset_button.clicked.connect(self.set_tool_ui)
        self.ui.ratio_radio.activated_custom.connect(self.on_ratio_change)

        self.ui.oz_entry.textChanged.connect(self.on_oz_conversion)
        self.ui.mils_entry.textChanged.connect(self.on_mils_conversion)

    def set_tool_ui(self):
        self.clear_ui(self.layout)
        self.ui = EtchUI(layout=self.layout, app=self.app)
        self.pluginName = self.ui.pluginName
        self.connect_signals_at_init()

        self.ui.thick_entry.set_value(18.0)
        self.ui.ratio_radio.set_value('factor')

        # SELECT THE CURRENT OBJECT
        obj = self.app.collection.get_active()
        if obj and obj.kind == 'gerber':
            obj_name = obj.obj_options['name']
            self.ui.gerber_combo.set_value(obj_name)

    def on_ratio_change(self, val):
        """
        Called on activated_custom signal of the RadioSet GUI element self.radio_ratio

        :param val:     'c' or 'p': 'c' means custom factor and 'p' means preselected etchants
        :type val:      str
        :return:        None
        :rtype:
        """
        if val == 'factor':
            self.ui.etchants_label.hide()
            self.ui.etchants_combo.hide()
            self.ui.factor_label.show()
            self.ui.factor_entry.show()
            self.ui.offset_label.hide()
            self.ui.offset_entry.hide()
        elif val == 'etch_list':
            self.ui.etchants_label.show()
            self.ui.etchants_combo.show()
            self.ui.factor_label.hide()
            self.ui.factor_entry.hide()
            self.ui.offset_label.hide()
            self.ui.offset_entry.hide()
        else:
            self.ui.etchants_label.hide()
            self.ui.etchants_combo.hide()
            self.ui.factor_label.hide()
            self.ui.factor_entry.hide()
            self.ui.offset_label.show()
            self.ui.offset_entry.show()

    def on_oz_conversion(self, txt):
        try:
            val = eval(txt)
            # oz thickness to mils by multiplying with 1.37
            # mils to microns by multiplying with 25.4
            val *= 34.798
        except Exception:
            self.ui.oz_to_um_entry.set_value('')
            return
        self.ui.oz_to_um_entry.set_value(val, self.decimals)

    def on_mils_conversion(self, txt):
        try:
            val = eval(txt)
            val *= 25.4
        except Exception:
            self.ui.mils_to_um_entry.set_value('')
            return
        self.ui.mils_to_um_entry.set_value(val, self.decimals)

    def on_compensate(self):
        self.app.log.debug("ToolEtchCompensation.on_compensate()")

        ratio_type = self.ui.ratio_radio.get_value()
        thickness = self.ui.thick_entry.get_value() / 1000     # in microns

        grb_circle_steps = int(self.app.options["gerber_circle_steps"])
        obj_name = self.ui.gerber_combo.currentText()

        outname = obj_name + "_comp"

        # Get source object.
        try:
            grb_obj = self.app.collection.get_by_name(obj_name)
        except Exception as e:
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Could not retrieve object"), str(obj_name)))
            return "Could not retrieve object: %s with error: %s" % (obj_name, str(e))

        if grb_obj is None:
            if obj_name == '':
                obj_name = 'None'
            self.app.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Object not found"), str(obj_name)))
            return

        if ratio_type == 'factor':
            factor_value = self.ui.factor_entry.get_value()
            if factor_value is None:
                self.app.inform.emit('[ERROR_NOTCL] %s' % _("Missing parameter value."))
                return
            etch_factor = 1 / factor_value
            offset = thickness / etch_factor
        elif ratio_type == 'etch_list':
            etchant = self.ui.etchants_combo.get_value()
            if etchant == "CuCl2":
                etch_factor = 0.33
            else:
                etch_factor = 0.25
            offset = thickness / etch_factor
        else:
            offset_value = self.ui.offset_entry.get_value()
            if offset_value is None:
                self.app.inform.emit('[ERROR_NOTCL] %s' % _("Missing parameter value."))
                return
            offset = offset_value / 1000   # in microns

        if offset == 0:
            # no need to do anything for zero value, offset, isn't it?
            # compensating with zero is the same as the original
            return

        grb_obj.solid_geometry = flatten_shapely_geometry(grb_obj.solid_geometry)
        new_solid_geometry = []

        for poly in grb_obj.solid_geometry:
            new_solid_geometry.append(poly.buffer(offset, int(grb_circle_steps)))
        new_solid_geometry = unary_union(new_solid_geometry)

        new_options = {}
        for opt in grb_obj.obj_options:
            new_options[opt] = deepcopy(grb_obj.obj_options[opt])

        new_apertures = deepcopy(grb_obj.tools)

        # update the apertures attributes (keys in the apertures dict)
        for ap in new_apertures:
            ap_type = new_apertures[ap]['type']
            for k in new_apertures[ap]:
                if ap_type == 'R' or ap_type == 'O':
                    if k == 'width' or k == 'height':
                        new_apertures[ap][k] += offset
                else:
                    if k == 'size' or k == 'width' or k == 'height':
                        new_apertures[ap][k] += offset

                if k == 'geometry':
                    for geo_el in new_apertures[ap][k]:
                        if 'solid' in geo_el:
                            geo_el['solid'] = geo_el['solid'].buffer(offset, int(grb_circle_steps))

        # in case of 'R' or 'O' aperture type we need to update the aperture 'size' after
        # the 'width' and 'height' keys were updated
        for ap in new_apertures:
            ap_type = new_apertures[ap]['type']
            for k in new_apertures[ap]:
                if ap_type == 'R' or ap_type == 'O':
                    if k == 'size':
                        new_apertures[ap][k] = math.sqrt(
                            new_apertures[ap]['width'] ** 2 + new_apertures[ap]['height'] ** 2)

        def init_func(new_obj, app_obj):
            """
            Init a new object in FlatCAM Object collection

            :param new_obj:     New object
            :type new_obj:      ObjectCollection
            :param app_obj:     App
            :type app_obj:      appMain.App
            :return:            None
            :rtype:
            """
            new_obj.obj_options.update(new_options)
            new_obj.obj_options['name'] = outname
            new_obj.fill_color = deepcopy(grb_obj.fill_color)
            new_obj.outline_color = deepcopy(grb_obj.outline_color)

            new_obj.tools = deepcopy(new_apertures)

            new_obj.solid_geometry = deepcopy(new_solid_geometry)
            new_obj.source_file = app_obj.f_handlers.export_gerber(obj_name=outname, filename=None, local_use=new_obj,
                                                                   use_thread=False)

        self.app.app_obj.new_object('gerber', outname, init_func)

    def reset_fields(self):
        self.ui.gerber_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))

    @staticmethod
    def poly2rings(poly):
        return [poly.exterior] + [interior for interior in poly.interiors]


class EtchUI:

    pluginName = _("Etch Compensation")

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

        # Title
        title_label = FCLabel("%s" % self.pluginName, size=16, bold=True)
        self.tools_box.addWidget(title_label)

        # #############################################################################################################
        # Source Object Frame
        # #############################################################################################################
        self.gerber_label = FCLabel('%s' % _("Source Object"), color='darkorange', bold=True)
        self.gerber_label.setToolTip(
            _("Gerber object that will be compensated.")
        )
        self.tools_box.addWidget(self.gerber_label)

        # Target Gerber Object
        self.gerber_combo = FCComboBox()
        self.gerber_combo.setModel(self.app.collection)
        self.gerber_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.gerber_combo.is_last = True
        self.gerber_combo.obj_type = "Gerber"

        self.tools_box.addWidget(self.gerber_combo)

        # #############################################################################################################
        # Utilities
        # #############################################################################################################
        self.util_label = FCLabel('%s' % _("Utilities"), color='red', bold=True)
        self.util_label.setToolTip('%s.' % _("Conversion utilities"))
        self.tools_box.addWidget(self.util_label)

        util_frame = FCFrame()
        self.tools_box.addWidget(util_frame)

        # Grid Layout
        grid0 = GLay(v_spacing=5, h_spacing=3)
        util_frame.setLayout(grid0)

        # Oz to um conversion
        self.oz_um_label = FCLabel('%s:' % _('Oz to Microns'))
        self.oz_um_label.setToolTip(
            _("Will convert from oz thickness to microns [um].\n"
              "Can use formulas with operators: /, *, +, -, %, .\n"
              "The real numbers use the dot decimals separator.")
        )
        grid0.addWidget(self.oz_um_label, 0, 0, 1, 2)

        hlay_1 = QtWidgets.QHBoxLayout()

        self.oz_entry = NumericalEvalEntry(border_color='#0069A9')
        self.oz_entry.setPlaceholderText(_("Oz value"))
        self.oz_to_um_entry = FCEntry()
        self.oz_to_um_entry.setPlaceholderText(_("Microns value"))
        self.oz_to_um_entry.setReadOnly(True)

        hlay_1.addWidget(self.oz_entry)
        hlay_1.addWidget(FCLabel(" "))
        hlay_1.addWidget(self.oz_to_um_entry)
        grid0.addLayout(hlay_1, 2, 0, 1, 2)

        # Mils to um conversion
        self.mils_um_label = FCLabel('%s:' % _('Mils to Microns'))
        self.mils_um_label.setToolTip(
            _("Will convert from mils to microns [um].\n"
              "Can use formulas with operators: /, *, +, -, %, .\n"
              "The real numbers use the dot decimals separator.")
        )
        grid0.addWidget(self.mils_um_label, 4, 0, 1, 2)

        hlay_2 = QtWidgets.QHBoxLayout()

        self.mils_entry = NumericalEvalEntry(border_color='#0069A9')
        self.mils_entry.setPlaceholderText(_("Mils value"))
        self.mils_to_um_entry = FCEntry()
        self.mils_to_um_entry.setPlaceholderText(_("Microns value"))
        self.mils_to_um_entry.setReadOnly(True)

        hlay_2.addWidget(self.mils_entry)
        hlay_2.addWidget(FCLabel(" "))
        hlay_2.addWidget(self.mils_to_um_entry)
        grid0.addLayout(hlay_2, 6, 0, 1, 2)

        # #############################################################################################################
        # COMMON PARAMETERS Frame
        # #############################################################################################################
        self.param_label = FCLabel('%s' % _("Parameters"), color='blue', bold=True)
        self.param_label.setToolTip(_("Parameters used for this tool."))
        self.tools_box.addWidget(self.param_label)

        self.gp_frame = FCFrame()
        self.tools_box.addWidget(self.gp_frame)

        grid1 = GLay(v_spacing=5, h_spacing=3)
        self.gp_frame.setLayout(grid1)

        # Thickness
        self.thick_label = FCLabel('%s:' % _('Copper Thickness'))
        self.thick_label.setToolTip(
            _("The thickness of the copper foil.\n"
              "In microns [um].")
        )
        self.thick_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.thick_entry.set_precision(self.decimals)
        self.thick_entry.set_range(0.0000, 10000.0000)

        grid1.addWidget(self.thick_label, 0, 0)
        grid1.addWidget(self.thick_entry, 0, 1)

        self.ratio_label = FCLabel('%s:' % _("Ratio"))
        self.ratio_label.setToolTip(
            _("The ratio of lateral etch versus depth etch.\n"
              "Can be:\n"
              "- custom -> the user will enter a custom value\n"
              "- preselection -> value which depends on a selection of etchants")
        )
        self.ratio_radio = RadioSet([
            {'label': _('Etch Factor'), 'value': 'factor'},
            {'label': _('Etchants list'), 'value': 'etch_list'},
            {'label': _('Manual offset'), 'value': 'manual'}
        ], orientation='vertical', compact=True)

        grid1.addWidget(self.ratio_label, 2, 0, 1, 2)
        grid1.addWidget(self.ratio_radio, 4, 0, 1, 2)

        separator_line = QtWidgets.QFrame()
        separator_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        grid1.addWidget(separator_line, 6, 0, 1, 2)

        # Etchants
        self.etchants_label = FCLabel('%s:' % _('Etchants'))
        self.etchants_label.setToolTip(
            _("A list of etchants.")
        )
        self.etchants_combo = FCComboBox(callback=self.confirmation_message)
        self.etchants_combo.addItems(["CuCl2", "Fe3Cl", _("Alkaline baths")])

        grid1.addWidget(self.etchants_label, 8, 0)
        grid1.addWidget(self.etchants_combo, 8, 1)

        # Etch Factor
        self.factor_label = FCLabel('%s:' % _('Etch Factor'))
        self.factor_label.setToolTip(
            _("The ratio between depth etch and lateral etch .\n"
              "Accepts real numbers and formulas using the operators: /,*,+,-,%")
        )
        self.factor_entry = NumericalEvalEntry(border_color='#0069A9')
        self.factor_entry.setPlaceholderText(_("Real number or formula"))

        grid1.addWidget(self.factor_label, 10, 0)
        grid1.addWidget(self.factor_entry, 10, 1)

        # Manual Offset
        self.offset_label = FCLabel('%s:' % _('Offset'))
        self.offset_label.setToolTip(
            _("Value with which to increase or decrease (buffer)\n"
              "the copper features. In microns [um].")
        )
        self.offset_entry = FCDoubleSpinner(callback=self.confirmation_message)
        self.offset_entry.set_precision(self.decimals)
        self.offset_entry.set_range(-10000.0000, 10000.0000)

        grid1.addWidget(self.offset_label, 12, 0)
        grid1.addWidget(self.offset_entry, 12, 1)

        # Hide the Etchants and Etch factor
        self.etchants_label.hide()
        self.etchants_combo.hide()
        self.factor_label.hide()
        self.factor_entry.hide()
        self.offset_label.hide()
        self.offset_entry.hide()

        # #############################################################################################################
        # Generate Etch Compensation Button
        # #############################################################################################################
        self.compensate_btn = FCButton(_('Compensate'), bold=True)
        self.compensate_btn.setIcon(QtGui.QIcon(self.app.resource_location + '/etch_32.png'))
        self.compensate_btn.setToolTip(
            _("Will increase the copper features thickness to compensate the lateral etch.")
        )
        self.tools_box.addWidget(self.compensate_btn)

        self.tools_box.addStretch(1)

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

# end of file
