
from PyQt6 import QtWidgets

from appGUI.preferences.tools.Tools2InvertPrefGroupUI import Tools2InvertPrefGroupUI
from appGUI.preferences.tools.Tools2PunchGerberPrefGroupUI import Tools2PunchGerberPrefGroupUI
from appGUI.preferences.tools.Tools2ExtractPrefGroupUI import Tools2EDrillsPrefGroupUI
from appGUI.preferences.tools.Tools2FiducialsPrefGroupUI import Tools2FiducialsPrefGroupUI
from appGUI.preferences.tools.Tools2CThievingPrefGroupUI import Tools2CThievingPrefGroupUI
from appGUI.preferences.tools.Tools2QRCodePrefGroupUI import Tools2QRCodePrefGroupUI
from appGUI.preferences.tools.Tools2OptimalPrefGroupUI import Tools2OptimalPrefGroupUI
from appGUI.preferences.tools.Tools2RulesCheckPrefGroupUI import Tools2RulesCheckPrefGroupUI

from appGUI.ColumnarFlowLayout import ColumnarFlowLayout

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class Plugins2PreferencesUI(QtWidgets.QWidget):

    def __init__(self, app, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        if app.defaults['global_gui_layout'] == 0:
            self.layout = QtWidgets.QHBoxLayout()
        else:
            self.layout = ColumnarFlowLayout()
        self.setLayout(self.layout)

        self.tools2_checkrules_group = Tools2RulesCheckPrefGroupUI(app=app)
        self.tools2_checkrules_group.setMinimumWidth(250)

        self.tools2_optimal_group = Tools2OptimalPrefGroupUI(app=app)
        self.tools2_optimal_group.setMinimumWidth(250)

        self.tools2_qrcode_group = Tools2QRCodePrefGroupUI(app=app)
        self.tools2_qrcode_group.setMinimumWidth(280)

        self.tools2_cfill_group = Tools2CThievingPrefGroupUI(app=app)
        self.tools2_cfill_group.setMinimumWidth(250)

        self.tools2_fiducials_group = Tools2FiducialsPrefGroupUI(app=app)
        self.tools2_fiducials_group.setMinimumWidth(250)

        self.tools2_edrills_group = Tools2EDrillsPrefGroupUI(app=app)
        self.tools2_edrills_group.setMinimumWidth(250)

        self.tools2_punch_group = Tools2PunchGerberPrefGroupUI(app=app)
        self.tools2_punch_group.setMinimumWidth(250)

        self.tools2_invert_group = Tools2InvertPrefGroupUI(app=app)
        self.tools2_invert_group.setMinimumWidth(250)

        self.vlay = QtWidgets.QVBoxLayout()
        self.vlay.addWidget(self.tools2_checkrules_group)
        self.vlay.addWidget(self.tools2_optimal_group)

        self.vlay1 = QtWidgets.QVBoxLayout()
        self.vlay1.addWidget(self.tools2_qrcode_group)
        self.vlay1.addWidget(self.tools2_fiducials_group)

        self.vlay2 = QtWidgets.QVBoxLayout()
        self.vlay2.addWidget(self.tools2_cfill_group)

        self.vlay3 = QtWidgets.QVBoxLayout()
        self.vlay3.addWidget(self.tools2_edrills_group)

        self.vlay4 = QtWidgets.QVBoxLayout()
        self.vlay4.addWidget(self.tools2_punch_group)
        self.vlay4.addWidget(self.tools2_invert_group)

        self.layout.addLayout(self.vlay)
        self.layout.addLayout(self.vlay1)
        self.layout.addLayout(self.vlay2)
        self.layout.addLayout(self.vlay3)
        self.layout.addLayout(self.vlay4)

        self.layout.addStretch()
