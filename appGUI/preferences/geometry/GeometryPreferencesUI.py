from PyQt6 import QtWidgets

from appGUI.preferences.geometry.GeometryEditorPrefGroupUI import GeometryEditorPrefGroupUI
from appGUI.preferences.geometry.GeometryAdvOptPrefGroupUI import GeometryAdvOptPrefGroupUI
from appGUI.preferences.geometry.GeometryExpPrefGroupUI import GeometryExpPrefGroupUI
from appGUI.preferences.geometry.GeometryOptPrefGroupUI import GeometryOptPrefGroupUI
from appGUI.preferences.geometry.GeometryGenPrefGroupUI import GeometryGenPrefGroupUI

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class GeometryPreferencesUI(QtWidgets.QWidget):

    def __init__(self, decimals, defaults, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)
        self.decimals = decimals
        self.defaults = defaults

        self.geometry_gen_group = GeometryGenPrefGroupUI(decimals=self.decimals, defaults=self.defaults)
        self.geometry_gen_group.setMinimumWidth(220)
        self.geometry_exp_group = GeometryExpPrefGroupUI(decimals=self.decimals, defaults=self.defaults)
        self.geometry_exp_group.setMinimumWidth(220)
        self.geometry_opt_group = GeometryOptPrefGroupUI(decimals=self.decimals, defaults=self.defaults)
        self.geometry_opt_group.setMinimumWidth(300)
        self.geometry_adv_opt_group = GeometryAdvOptPrefGroupUI(decimals=self.decimals, defaults=self.defaults)
        self.geometry_adv_opt_group.setMinimumWidth(270)
        self.geometry_editor_group = GeometryEditorPrefGroupUI(decimals=self.decimals, defaults=self.defaults)
        self.geometry_editor_group.setMinimumWidth(250)

        self.layout.addWidget(self.geometry_gen_group)

        self.vlay = QtWidgets.QVBoxLayout()
        self.vlay.addWidget(self.geometry_opt_group)
        self.vlay.addWidget(self.geometry_adv_opt_group)
        self.vlay.addWidget(self.geometry_exp_group)

        self.layout.addLayout(self.vlay)

        self.layout.addWidget(self.geometry_editor_group)

        self.layout.addStretch()
