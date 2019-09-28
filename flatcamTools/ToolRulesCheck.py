# ########################################################## ##
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 09/27/2019                                          #
# MIT Licence                                              #
# ########################################################## ##

from FlatCAMTool import FlatCAMTool
from copy import copy, deepcopy
from ObjectCollection import *
import time
from FlatCAMPool import *
from os import getpid
import copyreg, types, sys

import gettext
import FlatCAMTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


def _pickle_method(m):
    class_self = m.im_class if m.im_self is None else m.im_self
    print(getattr, (class_self, m.im_func.func_name))
    return getattr, (class_self, m.im_func.func_name)


copyreg.pickle(types.MethodType, _pickle_method)


class RulesCheck(FlatCAMTool):

    toolName = _("Check Rules")

    def __init__(self, app):
        super(RulesCheck, self).__init__(self)
        self.app = app

        # ## Title
        title_label = QtWidgets.QLabel("%s" % self.toolName)
        title_label.setStyleSheet("""
                        QLabel
                        {
                            font-size: 16px;
                            font-weight: bold;
                        }
                        """)
        self.layout.addWidget(title_label)

        # Form Layout
        form_layout = QtWidgets.QFormLayout()
        self.layout.addLayout(form_layout)

        self.gerber_title_lbl = QtWidgets.QLabel('<b>%s</b>:' % _("Gerber Files"))
        self.gerber_title_lbl.setToolTip(
            _("Gerber files for which to check rules.")
        )

        # Copper object
        self.copper_object = QtWidgets.QComboBox()
        self.copper_object.setModel(self.app.collection)
        self.copper_object.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.copper_object.setCurrentIndex(1)

        self.copper_object_lbl = QtWidgets.QLabel('%s:' % _("Copper"))
        self.copper_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )

        # SolderMask object
        self.sm_object = QtWidgets.QComboBox()
        self.sm_object.setModel(self.app.collection)
        self.sm_object.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.sm_object.setCurrentIndex(1)

        self.sm_object_lbl = QtWidgets.QLabel('%s:' % _("SolderMask"))
        self.sm_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )

        # SilkScreen object
        self.ss_object = QtWidgets.QComboBox()
        self.ss_object.setModel(self.app.collection)
        self.ss_object.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.ss_object.setCurrentIndex(1)

        self.ss_object_lbl = QtWidgets.QLabel('%s:' % _("Silkscreen"))
        self.ss_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )

        # Outline object
        self.outline_object = QtWidgets.QComboBox()
        self.outline_object.setModel(self.app.collection)
        self.outline_object.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        self.outline_object.setCurrentIndex(1)

        self.outline_object_lbl = QtWidgets.QLabel('%s:' % _("Outline"))
        self.outline_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )
        form_layout.addRow(self.gerber_title_lbl)
        form_layout.addRow(self.copper_object_lbl, self.copper_object)
        form_layout.addRow(self.sm_object_lbl, self.sm_object)
        form_layout.addRow(self.ss_object_lbl, self.ss_object)
        form_layout.addRow(self.outline_object_lbl, self.outline_object)
        form_layout.addRow(QtWidgets.QLabel(""))

        self.excellon_title_lbl = QtWidgets.QLabel('<b>%s</b>:' % _("Excellon Files"))
        self.excellon_title_lbl.setToolTip(
            _("Excellon files for which to check rules.")
        )

        # Excellon 1 object
        self.e1_object = QtWidgets.QComboBox()
        self.e1_object.setModel(self.app.collection)
        self.e1_object.setRootModelIndex(self.app.collection.index(1, 0, QtCore.QModelIndex()))
        self.e1_object.setCurrentIndex(1)

        self.e1_object_lbl = QtWidgets.QLabel('%s:' % _("Excellon 1"))
        self.e1_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )

        # Excellon 2 object
        self.e2_object = QtWidgets.QComboBox()
        self.e2_object.setModel(self.app.collection)
        self.e2_object.setRootModelIndex(self.app.collection.index(1, 0, QtCore.QModelIndex()))
        self.e2_object.setCurrentIndex(1)

        self.e2_object_lbl = QtWidgets.QLabel('%s:' % _("Excellon 2"))
        self.e2_object_lbl.setToolTip(
            _("Object to be panelized. This means that it will\n"
              "be duplicated in an array of rows and columns.")
        )

        form_layout.addRow(self.excellon_title_lbl)
        form_layout.addRow(self.e1_object_lbl, self.e1_object)
        form_layout.addRow(self.e2_object_lbl, self.e2_object)
        form_layout.addRow(QtWidgets.QLabel(""))

        # Form Layout
        form_layout_1 = QtWidgets.QFormLayout()
        self.layout.addLayout(form_layout_1)

        # Copper2copper clearance
        self.clearance_copper2copper_cb = FCCheckBox('%s:' % _("Copper to copper clearance"))
        self.clearance_copper2copper_cb.setToolTip(
            _("This checks if the minimum clearance between copper\n"
              "features is met.")
        )
        form_layout_1.addRow(self.clearance_copper2copper_cb)

        # Copper2copper clearance value
        self.clearance_copper2copper_entry = FCEntry()
        self.clearance_copper2copper_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_copper2copper_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_copper2copper_lbl, self.clearance_copper2copper_entry)

        self.c2c = OptionalInputSection(
            self.clearance_copper2copper_cb, [self.clearance_copper2copper_lbl, self.clearance_copper2copper_entry])

        # Copper2soldermask clearance
        self.clearance_copper2sm_cb = FCCheckBox('%s:' % _("Copper to soldermask clearance"))
        self.clearance_copper2sm_cb.setToolTip(
            _("This checks if the minimum clearance between copper\n"
              "features and soldermask features is met.")
        )
        form_layout_1.addRow(self.clearance_copper2sm_cb)

        # Copper2soldermask clearance value
        self.clearance_copper2sm_entry = FCEntry()
        self.clearance_copper2sm_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_copper2sm_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_copper2sm_lbl, self.clearance_copper2sm_entry)

        self.c2sm = OptionalInputSection(
            self.clearance_copper2sm_cb, [self.clearance_copper2sm_lbl, self.clearance_copper2sm_entry])

        # Copper2silkscreen clearance
        self.clearance_copper2sk_cb = FCCheckBox('%s:' % _("Copper to silkscreen clearance"))
        self.clearance_copper2sk_cb.setToolTip(
            _("This checks if the minimum clearance between copper\n"
              "features and silkscreen features is met.")
        )
        form_layout_1.addRow(self.clearance_copper2sk_cb)

        # Copper2silkscreen clearance value
        self.clearance_copper2sk_entry = FCEntry()
        self.clearance_copper2sk_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_copper2sk_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_copper2sk_lbl, self.clearance_copper2sk_entry)

        self.c2sk = OptionalInputSection(
            self.clearance_copper2sk_cb, [self.clearance_copper2sk_lbl, self.clearance_copper2sk_entry])

        # Copper2outline clearance
        self.clearance_copper2ol_cb = FCCheckBox('%s:' % _("Copper to outline clearance"))
        self.clearance_copper2ol_cb.setToolTip(
            _("This checks if the minimum clearance between copper\n"
              "features and the outline is met.")
        )
        form_layout_1.addRow(self.clearance_copper2ol_cb)

        # Copper2outline clearance value
        self.clearance_copper2ol_entry = FCEntry()
        self.clearance_copper2ol_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_copper2ol_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_copper2ol_lbl, self.clearance_copper2ol_entry)

        self.c2ol = OptionalInputSection(
            self.clearance_copper2ol_cb, [self.clearance_copper2ol_lbl, self.clearance_copper2ol_entry])

        # Silkscreen2silkscreen clearance
        self.clearance_silk2silk_cb = FCCheckBox('%s:' % _("Silkscreen to silkscreen clearance"))
        self.clearance_silk2silk_cb.setToolTip(
            _("This checks if the minimum clearance between silkscreen\n"
              "features and silkscreen features is met.")
        )
        form_layout_1.addRow(self.clearance_silk2silk_cb)

        # Copper2silkscreen clearance value
        self.clearance_silk2silk_entry = FCEntry()
        self.clearance_silk2silk_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_silk2silk_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_silk2silk_lbl, self.clearance_silk2silk_entry)

        self.s2s = OptionalInputSection(
            self.clearance_silk2silk_cb, [self.clearance_silk2silk_lbl, self.clearance_silk2silk_entry])

        # Silkscreen2soldermask clearance
        self.clearance_silk2sm_cb = FCCheckBox('%s:' % _("Silkscreen to soldermask clearance"))
        self.clearance_silk2sm_cb.setToolTip(
            _("This checks if the minimum clearance between silkscreen\n"
              "features and soldermask features is met.")
        )
        form_layout_1.addRow(self.clearance_silk2sm_cb)

        # Silkscreen2soldermask clearance value
        self.clearance_silk2sm_entry = FCEntry()
        self.clearance_silk2sm_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_silk2sm_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_silk2sm_lbl, self.clearance_silk2sm_entry)

        self.s2sm = OptionalInputSection(
            self.clearance_silk2sm_cb, [self.clearance_silk2sm_lbl, self.clearance_silk2sm_entry])

        # Soldermask2soldermask clearance
        self.clearance_sm2sm_cb = FCCheckBox('%s:' % _("Soldermask to soldermask clearance"))
        self.clearance_sm2sm_cb.setToolTip(
            _("This checks if the minimum clearance between soldermask\n"
              "features and soldermask features is met.")
        )
        form_layout_1.addRow(self.clearance_sm2sm_cb)

        # Soldermask2soldermask clearance value
        self.clearance_sm2sm_entry = FCEntry()
        self.clearance_sm2sm_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_sm2sm_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_sm2sm_lbl, self.clearance_sm2sm_entry)

        self.sm2sm = OptionalInputSection(
            self.clearance_sm2sm_cb, [self.clearance_sm2sm_lbl, self.clearance_sm2sm_entry])

        form_layout_1.addRow(QtWidgets.QLabel(""))

        # Drill2Drill clearance
        self.clearance_d2d_cb = FCCheckBox('%s:' % _("Drill hole to drill hole clearance"))
        self.clearance_d2d_cb.setToolTip(
            _("This checks if the minimum clearance between a drill hole\n"
              "and another drill hole is met.")
        )
        form_layout_1.addRow(self.clearance_d2d_cb)

        # Drill2Drill clearance value
        self.clearance_d2d_entry = FCEntry()
        self.clearance_d2d_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.clearance_d2d_lbl.setToolTip(
            _("Minimum acceptable clearance value.")
        )
        form_layout_1.addRow(self.clearance_d2d_lbl, self.clearance_d2d_entry)

        self.d2d = OptionalInputSection(
            self.clearance_d2d_cb, [self.clearance_d2d_lbl, self.clearance_d2d_entry])

        # Ring integrity check
        self.ring_integrity_cb = FCCheckBox('%s:' % _("Ring integrity check"))
        self.ring_integrity_cb.setToolTip(
            _("This checks if the minimum copper ring left by drilling\n"
              "a hole into a pad is met.")
        )
        form_layout_1.addRow(self.ring_integrity_cb)

        # Ring integrity value
        self.ring_integrity_entry = FCEntry()
        self.ring_integrity_lbl = QtWidgets.QLabel('%s:' % _("Min value"))
        self.ring_integrity_lbl.setToolTip(
            _("Minimum acceptable ring value.")
        )
        form_layout_1.addRow(self.ring_integrity_lbl, self.ring_integrity_entry)

        self.d2d = OptionalInputSection(
            self.ring_integrity_cb, [self.ring_integrity_lbl, self.ring_integrity_entry])

        # Drill holes overlap check
        self.drill_overlap_cb = FCCheckBox('%s:' % _("Drill hole overlap check"))
        self.drill_overlap_cb.setToolTip(
            _("This checks if drill holes are overlapping\n"
              "one over another.")
        )
        form_layout_1.addRow(self.drill_overlap_cb)

        # Buttons
        hlay_2 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay_2)

        # hlay_2.addStretch()
        self.run_button = QtWidgets.QPushButton(_("Run Rules Check"))
        self.run_button.setToolTip(
            _("Panelize the specified object around the specified box.\n"
              "In other words it creates multiple copies of the source object,\n"
              "arranged in a 2D array of rows and columns.")
        )
        hlay_2.addWidget(self.run_button)

        self.layout.addStretch()

        # #######################################################
        # ################ SIGNALS ##############################
        # #######################################################
        self.run_button.clicked.connect(self.execute)
        # self.app.collection.rowsInserted.connect(self.on_object_loaded)

        # list to hold the temporary objects
        self.objs = []

        # final name for the panel object
        self.outname = ""

        # flag to signal the constrain was activated
        self.constrain_flag = False

    # def on_object_loaded(self, index, row):
    #     print(index.internalPointer().child_items[row].obj.options['name'], index.data())

    def run(self, toggle=True):
        self.app.report_usage("ToolRulesCheck()")

        if toggle:
            # if the splitter is hidden, display it, else hide it but only if the current widget is the same
            if self.app.ui.splitter.sizes()[0] == 0:
                self.app.ui.splitter.setSizes([1, 1])
            else:
                try:
                    if self.app.ui.tool_scroll_area.widget().objectName() == self.toolName:
                        # if tab is populated with the tool but it does not have the focus, focus on it
                        if not self.app.ui.notebook.currentWidget() is self.app.ui.tool_tab:
                            # focus on Tool Tab
                            self.app.ui.notebook.setCurrentWidget(self.app.ui.tool_tab)
                        else:
                            self.app.ui.splitter.setSizes([0, 1])
                except AttributeError:
                    pass
        else:
            if self.app.ui.splitter.sizes()[0] == 0:
                self.app.ui.splitter.setSizes([1, 1])

        FlatCAMTool.run(self)
        self.set_tool_ui()

        self.app.ui.notebook.setTabText(2, _("Rules Tool"))

    def install(self, icon=None, separator=None, **kwargs):
        FlatCAMTool.install(self, icon, separator, shortcut='ALT+R', **kwargs)

    def set_tool_ui(self):
        self.reset_fields()

    def foo(self, bar, baz):
        print("start", getpid())
        bar = bar ** 2
        print(bar, getpid())
        print("end", getpid())
        return bar, baz

    def execute(self):
        log.debug("started")
        self.pool = Pool()
        log.debug("executing")
        self.results = list()
        i = 50
        while i < 100:
            j = i + 1
            while j < 150:
                self.results.append(self.pool.apply_async(self.foo, args=(i, j)))
                j = j + 1
            i = i + 1

        output = [p.get() for p in self.results]
        print(output)
        log.debug("finished")

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict

    def reset_fields(self):
        # self.object_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        # self.box_combo.setRootModelIndex(self.app.collection.index(0, 0, QtCore.QModelIndex()))
        pass