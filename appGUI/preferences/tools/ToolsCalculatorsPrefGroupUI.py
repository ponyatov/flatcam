from PyQt6 import QtWidgets

from appGUI.GUIElements import FCDoubleSpinner, FCLabel, GLay, FCFrame
from appGUI.preferences.OptionsGroupUI import OptionsGroupUI

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class ToolsCalculatorsPrefGroupUI(OptionsGroupUI):
    def __init__(self, app, parent=None):
        # OptionsGroupUI.__init__(self, "Calculators Plugin", parent=parent)
        super(ToolsCalculatorsPrefGroupUI, self).__init__(self, parent=parent)

        self.setTitle(str(_("Calculators Plugin")))
        self.decimals = app.decimals
        self.options = app.options

        # #############################################################################################################
        # V-Shape Tool Frame
        # #############################################################################################################
        self.vshape_tool_label = FCLabel('<span style="color:%s;"><b>%s</b></span>' % (self.app.theme_safe_color('green'), _("V-Shape Tool Calculator")))
        self.vshape_tool_label.setToolTip(
            _("Calculate the tool diameter for a given V-shape tool,\n"
              "having the tip diameter, tip angle and\n"
              "depth-of-cut as parameters.")
        )
        self.layout.addWidget(self.vshape_tool_label)

        v_frame = FCFrame()
        self.layout.addWidget(v_frame)

        v_grid = GLay(v_spacing=5, h_spacing=3)
        v_frame.setLayout(v_grid)

        # ## Tip Diameter
        self.tip_dia_entry = FCDoubleSpinner()
        self.tip_dia_entry.set_range(0.000001, 10000.0000)
        self.tip_dia_entry.set_precision(self.decimals)
        self.tip_dia_entry.setSingleStep(0.1)

        self.tip_dia_label = FCLabel('%s:' % _("Tip Diameter"))
        self.tip_dia_label.setToolTip(
            _("This is the tool tip diameter.\n"
              "It is specified by manufacturer.")
        )
        v_grid.addWidget(self.tip_dia_label, 0, 0)
        v_grid.addWidget(self.tip_dia_entry, 0, 1)

        # ## Tip angle
        self.tip_angle_entry = FCDoubleSpinner()
        self.tip_angle_entry.set_range(0.0, 180.0)
        self.tip_angle_entry.set_precision(self.decimals)
        self.tip_angle_entry.setSingleStep(5)

        self.tip_angle_label = FCLabel('%s:' % _("Tip Angle"))
        self.tip_angle_label.setToolTip(
            _("This is the angle on the tip of the tool.\n"
              "It is specified by manufacturer.")
        )
        v_grid.addWidget(self.tip_angle_label, 2, 0)
        v_grid.addWidget(self.tip_angle_entry, 2, 1)

        # ## Depth-of-cut Cut Z
        self.cut_z_entry = FCDoubleSpinner()
        self.cut_z_entry.set_range(-10000.0000, 0.0000)
        self.cut_z_entry.set_precision(self.decimals)
        self.cut_z_entry.setSingleStep(0.01)

        self.cut_z_label = FCLabel('%s:' % _("Cut Z"))
        self.cut_z_label.setToolTip(
            _("This is depth to cut into material.\n"
              "In the CNCJob object it is the CutZ parameter.")
        )
        v_grid.addWidget(self.cut_z_label, 4, 0)
        v_grid.addWidget(self.cut_z_entry, 4, 1)

        # #############################################################################################################
        # Electroplating Frame
        # #############################################################################################################
        self.plate_title_label = FCLabel('<span style="color:%s;"><b>%s</b></span>' % (self.app.theme_safe_color('brown'), _("ElectroPlating Calculator")))
        self.plate_title_label.setToolTip(
            _("This calculator is useful for those who plate the via/pad/drill holes,\n"
              "using a method like graphite ink or calcium hypophosphite ink or palladium chloride.")
        )
        self.layout.addWidget(self.plate_title_label)

        el_frame = FCFrame()
        self.layout.addWidget(el_frame)

        el_grid = GLay(v_spacing=5, h_spacing=3)
        el_frame.setLayout(el_grid)

        # ## PCB Length
        self.pcblength_entry = FCDoubleSpinner()
        self.pcblength_entry.set_range(0.000001, 10000.0000)
        self.pcblength_entry.set_precision(self.decimals)
        self.pcblength_entry.setSingleStep(0.1)

        self.pcblengthlabel = FCLabel('%s:' % _("Board Length"))

        self.pcblengthlabel.setToolTip(_('This is the board length. In centimeters.'))
        el_grid.addWidget(self.pcblengthlabel, 0, 0)
        el_grid.addWidget(self.pcblength_entry, 0, 1)

        # ## PCB Width
        self.pcbwidth_entry = FCDoubleSpinner()
        self.pcbwidth_entry.set_range(0.000001, 10000.0000)
        self.pcbwidth_entry.set_precision(self.decimals)
        self.pcbwidth_entry.setSingleStep(0.1)

        self.pcbwidthlabel = FCLabel('%s:' % _("Board Width"))

        self.pcbwidthlabel.setToolTip(_('This is the board width.In centimeters.'))
        el_grid.addWidget(self.pcbwidthlabel, 2, 0)
        el_grid.addWidget(self.pcbwidth_entry, 2, 1)
        
        # AREA
        self.area_label = FCLabel('%s:' % _("Area"))
        self.area_label.setToolTip(_('This is the board area.'))
        self.area_entry = FCDoubleSpinner()
        self.area_entry.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.area_entry.set_precision(self.decimals)
        self.area_entry.set_range(0.0, 10000.0000)
        
        el_grid.addWidget(self.area_label, 4, 0)
        el_grid.addWidget(self.area_entry, 4, 1)
        
        # ## Current Density
        self.cdensity_label = FCLabel('%s:' % _("Current Density"))
        self.cdensity_entry = FCDoubleSpinner()
        self.cdensity_entry.set_range(0.000001, 10000.0000)
        self.cdensity_entry.set_precision(self.decimals)
        self.cdensity_entry.setSingleStep(0.1)

        self.cdensity_label.setToolTip(_("Current density to pass through the board. \n"
                                         "In Amps per Square Feet ASF."))
        el_grid.addWidget(self.cdensity_label, 6, 0)
        el_grid.addWidget(self.cdensity_entry, 6, 1)

        # ## PCB Copper Growth
        self.growth_label = FCLabel('%s:' % _("Copper Growth"))
        self.growth_entry = FCDoubleSpinner()
        self.growth_entry.set_range(0.000001, 10000.0000)
        self.growth_entry.set_precision(self.decimals)
        self.growth_entry.setSingleStep(0.01)

        self.growth_label.setToolTip(_("How thick the copper growth is intended to be.\n"
                                       "In microns."))
        el_grid.addWidget(self.growth_label, 8, 0)
        el_grid.addWidget(self.growth_entry, 8, 1)

        GLay.set_common_column_size([v_grid, el_grid], 0)

        self.layout.addStretch()
