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

from PyQt6 import QtCore

from appEditors.appTextEditor import AppTextEditor
from appObjects.AppObjectTemplate import FlatCAMObj
from appGUI.ObjectUI import ScriptObjectUI

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class ScriptObject(FlatCAMObj):
    """
    Represents a TCL script object.
    """
    optionChanged = QtCore.pyqtSignal(str)
    ui_type = ScriptObjectUI

    def __init__(self, name):
        self.decimals = self.app.decimals

        self.app.log.debug("Creating a ScriptObject object...")
        FlatCAMObj.__init__(self, name)

        self.kind = "script"

        self.obj_options.update({
            "plot": True,
            "type": 'Script',
            "source_file": '',
        })

        self.units = ''

        self.script_editor_tab = None

        self.ser_attrs = ['obj_options', 'kind', 'source_file']
        self.source_file = ''
        self.script_code = ''
        self.script_filename = ''

        self.units_found = self.app.app_units

    def set_ui(self, ui):
        """
        Sets the Object UI in Selected Tab for the FlatCAM Script type of object.
        :param ui:
        :return:
        """
        FlatCAMObj.set_ui(self, ui)
        self.app.log.debug("ScriptObject.set_ui()")

        assert isinstance(self.ui, ScriptObjectUI), \
            "Expected a ScriptObjectUI, got %s" % type(self.ui)

        self.units = self.app.app_units.upper()
        self.units_found = self.app.app_units

        # Fill form fields only on object create
        self.to_form()

        # Show/Hide Advanced Options
        app_mode = self.app.options["global_app_level"]
        self.change_level(app_mode)

        self.script_editor_tab = AppTextEditor(app=self.app, plain_text=True, parent=self.app.ui)

        # tab_here = False
        # # try to not add too many times a tab that it is already installed
        # for idx in range(self.app.ui.plot_tab_area.count()):
        #     if self.app.ui.plot_tab_area.widget(idx).objectName() == self.obj_options['name']:
        #         tab_here = True
        #         break
        #
        # # add the tab if it is not already added
        # if tab_here is False:
        #     self.app.ui.plot_tab_area.addTab(self.script_editor_tab, '%s' % _("Script Editor"))
        #     self.script_editor_tab.setObjectName(self.obj_options['name'])

        # self.app.ui.plot_tab_area.addTab(self.script_editor_tab, '%s' % _("Script Editor"))
        # self.script_editor_tab.setObjectName(self.obj_options['name'])

        # first clear previous text in text editor (if any)
        # self.script_editor_tab.code_editor.clear()
        # self.script_editor_tab.code_editor.setReadOnly(False)

        self.ui.autocomplete_cb.set_value(self.app.options['script_autocompleter'])
        self.on_autocomplete_changed(state=self.app.options['script_autocompleter'])

        self.script_editor_tab.buttonRun.show()

        # Switch plot_area to Script Editor tab
        self.app.ui.plot_tab_area.setCurrentWidget(self.script_editor_tab)

        flt = "FlatCAM Scripts (*.FlatScript);;All Files (*.*)"

        # #############################################################################
        # ############################ SIGNALS ########################################
        # #############################################################################
        self.ui.level.toggled.connect(self.on_level_changed)

        self.script_editor_tab.buttonOpen.clicked.disconnect()
        self.script_editor_tab.buttonOpen.clicked.connect(lambda: self.script_editor_tab.handleOpen(filt=flt))
        self.script_editor_tab.buttonSave.clicked.disconnect()
        self.script_editor_tab.buttonSave.clicked.connect(lambda: self.script_editor_tab.handleSaveGCode(filt=flt))

        self.script_editor_tab.buttonRun.clicked.connect(self.handle_run_code)
        self.script_editor_tab.handleTextChanged()

        self.ui.autocomplete_cb.stateChanged.connect(self.on_autocomplete_changed)

        self.ser_attrs = ['obj_options', 'kind', 'source_file']

        # ---------------------------------------------------- #
        # ----------- LOAD THE TEXT SOURCE FILE -------------- #
        # ---------------------------------------------------- #
        self.app.proc_container.view.set_busy('%s...' % _("Loading"))
        self.script_editor_tab.t_frame.hide()

        try:
            # self.script_editor_tab.code_editor.setPlainText(self.source_file)
            self.script_editor_tab.load_text(self.source_file, move_to_end=True)
        except Exception as e:
            self.app.log.error("ScriptObject.set_ui() --> %s" % str(e))

        self.script_editor_tab.t_frame.show()

        self.app.proc_container.view.set_idle()
        self.build_ui()

    def build_ui(self):
        FlatCAMObj.build_ui(self)

        tab_here = False
        # try to not add too many times a tab that it is already installed
        for idx in range(self.app.ui.plot_tab_area.count()):
            if self.app.ui.plot_tab_area.widget(idx).objectName() == (self.obj_options['name'] + "_editor_tab"):
                tab_here = True
                break

        # add the tab if it is not already added
        if tab_here is False:
            self.app.ui.plot_tab_area.addTab(self.script_editor_tab, '%s' % _("Script Editor"))
            self.script_editor_tab.setObjectName(self.obj_options['name'] + "_editor_tab")
            self.app.ui.plot_tab_area.setCurrentWidget(self.script_editor_tab)

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

        else:
            self.ui.level.setText('%s' % _('Advanced'))
            self.ui.level.setStyleSheet("""
                                                QToolButton
                                                {
                                                    color: red;
                                                }
                                                """)

    def parse_file(self, filename):
        """
        Will set an attribute of the object, self.source_file, with the parsed data.

        :param filename:    Tcl Script file to parse
        :return:            None
        """
        with open(filename, "r") as opened_script:
            script_content = opened_script.readlines()
            script_content = ''.join(script_content)

        self.source_file = script_content
        self.script_filename = filename

    def handle_run_code(self):
        self.script_code = self.script_editor_tab.code_editor.toPlainText()
        self.app.run_script.emit(self.script_code)

    def on_autocomplete_changed(self, state):
        if state:
            self.script_editor_tab.code_editor.completer_enable = True
        else:
            self.script_editor_tab.code_editor.completer_enable = False

    def mirror(self, axis, point):
        pass

    def offset(self, vect):
        pass

    def rotate(self, angle, point):
        pass

    def scale(self, xfactor, yfactor=None, point=None):
        pass

    def skew(self, angle_x, angle_y, point):
        pass

    def buffer(self, distance, join, factor=None):
        pass

    def bounds(self, flatten=False):
        return None, None, None, None

    def to_dict(self):
        """
        Returns a representation of the object as a dictionary.
        Attributes to include are listed in ``self.ser_attrs``.

        :return: A dictionary-encoded copy of the object.
        :rtype: dict
        """
        d = {}
        for attr in self.ser_attrs:
            d[attr] = getattr(self, attr)
        return d

    def from_dict(self, d):
        """
        Sets object's attributes from a dictionary.
        Attributes to include are listed in ``self.ser_attrs``.
        This method will look only for only and all the
        attributes in ``self.ser_attrs``. They must all
        be present. Use only for deserializing saved
        objects.

        :param d: Dictionary of attributes to set in the object.
        :type d: dict
        :return: None
        """
        for attr in self.ser_attrs:
            setattr(self, attr, d[attr])
