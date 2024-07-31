
from PyQt6 import QtGui
from PyQt6.QtCore import QSettings

from appGUI.GUIElements import RadioSet, FCCheckBox, FCLabel, GLay, FCFrame
from appGUI.preferences.OptionsGroupUI import OptionsGroupUI

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class CNCJobOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, app, parent=None):
        # OptionsGroupUI.__init__(self, "CNC Job Options Preferences", parent=None)
        super(CNCJobOptPrefGroupUI, self).__init__(self, parent=parent)

        self.setTitle(str(_("Options")))
        self.decimals = app.decimals
        self.options = app.options

        # #############################################################################################################
        # GCode Frame
        # #############################################################################################################
        self.export_gcode_label = FCLabel('%s' % _("Export G-Code"), color='brown', bold=True)
        self.export_gcode_label.setToolTip(
            _("Export and save G-Code to\n"
              "make this object to a file.")
        )
        self.layout.addWidget(self.export_gcode_label)

        qsettings = QSettings("Open Source", "FlatCAM_EVO")
        if qsettings.contains("textbox_font_size"):
            tb_fsize = qsettings.value('textbox_font_size', type=int)
        else:
            tb_fsize = 10
        font = QtGui.QFont()
        font.setPointSize(tb_fsize)

        gcode_frame = FCFrame()
        self.layout.addWidget(gcode_frame)

        gcode_grid = GLay(v_spacing=5, h_spacing=3)
        gcode_frame.setLayout(gcode_grid)

        # Plot Kind
        self.cncplot_method_label = FCLabel('%s:' % _("Plot kind"))
        self.cncplot_method_label.setToolTip(
            _("This selects the kind of geometries on the canvas to plot.\n"
              "Those can be either of type 'Travel' which means the moves\n"
              "above the work piece or it can be of type 'Cut',\n"
              "which means the moves that cut into the material.")
        )

        self.cncplot_method_radio = RadioSet([
            {"label": _("All"), "value": "all"},
            {"label": _("Travel"), "value": "travel"},
            {"label": _("Cut"), "value": "cut"}
        ], orientation='vertical')

        gcode_grid.addWidget(self.cncplot_method_label, 0, 0)
        gcode_grid.addWidget(self.cncplot_method_radio, 0, 1)

        # Display Annotation
        self.annotation_cb = FCCheckBox(_("Display Annotation"))
        self.annotation_cb.setToolTip(
            _("This selects if to display text annotation on the plot.\n"
              "When checked it will display numbers in order for each end\n"
              "of a travel line."
              )
        )

        gcode_grid.addWidget(self.annotation_cb, 2, 0, 1, 2)

        self.layout.addStretch(2)
