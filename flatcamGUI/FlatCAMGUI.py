# ########################################################## ##
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
# ########################################################## ##

# ########################################################## ##
# File Modified (major mod): Marius Adrian Stanciu         #
# Date: 3/10/2019                                          #
# ########################################################## ##

from PyQt5.QtCore import QSettings
from flatcamGUI.GUIElements import *
import platform
import webbrowser

from flatcamEditors.FlatCAMGeoEditor import FCShapeTool

import gettext
import FlatCAMTranslation as fcTranslate

fcTranslate.apply_language('strings')
import builtins
if '_' not in builtins.__dict__:
    _ = gettext.gettext

class FlatCAMGUI(QtWidgets.QMainWindow):
    # Emitted when persistent window geometry needs to be retained
    geom_update = QtCore.pyqtSignal(int, int, int, int, int, name='geomUpdate')
    final_save = QtCore.pyqtSignal(name='saveBeforeExit')

    def __init__(self, version, beta, app):
        super(FlatCAMGUI, self).__init__()

        self.app = app
        # Divine icon pack by Ipapun @ finicons.com

        # ################################## ##
        # ## BUILDING THE GUI IS DONE HERE # ##
        # ################################## ##

        # ######### ##
        # ## Menu # ##
        # ######### ##
        self.menu = self.menuBar()

        # ## File # ##
        self.menufile = self.menu.addMenu(_('&File'))
        self.menufile.setToolTipsVisible(True)

        # New Project
        self.menufilenewproject = QtWidgets.QAction(QtGui.QIcon('share/file16.png'),
                                                    _('&New Project ...\tCTRL+N'), self)
        self.menufilenewproject.setToolTip(
            _("Will create a new, blank project")
        )
        self.menufile.addAction(self.menufilenewproject)

        # New Category (Excellon, Geometry)
        self.menufilenew = self.menufile.addMenu(QtGui.QIcon('share/file16.png'), _('&New'))
        self.menufilenew.setToolTipsVisible(True)

        self.menufilenewgeo = self.menufilenew.addAction(QtGui.QIcon('share/geometry16.png'), _('Geometry\tN'))
        self.menufilenewgeo.setToolTip(
            _("Will create a new, empty Geometry Object.")
        )
        self.menufilenewgrb = self.menufilenew.addAction(QtGui.QIcon('share/flatcam_icon32.png'), _('Gerber\tB'))
        self.menufilenewgrb.setToolTip(
            _("Will create a new, empty Gerber Object.")
        )
        self.menufilenewexc = self.menufilenew.addAction(QtGui.QIcon('share/drill16.png'), _('Excellon\tL'))
        self.menufilenewexc.setToolTip(
            _("Will create a new, empty Excellon Object.")
        )

        self.menufile_open = self.menufile.addMenu(QtGui.QIcon('share/folder32_bis.png'), _('Open'))
        self.menufile_open.setToolTipsVisible(True)

        # Open gerber ...
        self.menufileopengerber = QtWidgets.QAction(QtGui.QIcon('share/flatcam_icon24.png'),
                                                    _('Open &Gerber ...\tCTRL+G'), self)
        self.menufile_open.addAction(self.menufileopengerber)

        self.menufile_open.addSeparator()

        # Open Excellon ...
        self.menufileopenexcellon = QtWidgets.QAction(QtGui.QIcon('share/open_excellon32.png'),
                                                      _('Open &Excellon ...\tCTRL+E'),
                                                  self)
        self.menufile_open.addAction(self.menufileopenexcellon)

        # Open G-Code ...
        self.menufileopengcode = QtWidgets.QAction(QtGui.QIcon('share/code.png'), _('Open G-&Code ...'), self)
        self.menufile_open.addAction(self.menufileopengcode)

        # Open Project ...
        self.menufileopenproject = QtWidgets.QAction(QtGui.QIcon('share/folder16.png'), _('Open &Project ...'), self)
        self.menufile_open.addAction(self.menufileopenproject)

        self.menufile_open.addSeparator()

        # Open Config File...
        self.menufileopenconfig = QtWidgets.QAction(QtGui.QIcon('share/folder16.png'), _('Open Config ...'), self)
        self.menufile_open.addAction(self.menufileopenconfig)

        # Recent
        self.recent = self.menufile.addMenu(QtGui.QIcon('share/recent_files.png'), _("Recent files"))

        # Separator
        self.menufile.addSeparator()

        # Scripting
        self.menufile_scripting = self.menufile.addMenu(QtGui.QIcon('share/script16.png'), _('Scripting'))
        self.menufile_scripting.setToolTipsVisible(True)

        self.menufilenewscript = QtWidgets.QAction(QtGui.QIcon('share/script_new16.png'), _('New Script ...'),
                                                   self)
        self.menufileopenscript = QtWidgets.QAction(QtGui.QIcon('share/script_open16.png'), _('Open Script ...'),
                                                   self)
        self.menufilerunscript = QtWidgets.QAction(QtGui.QIcon('share/script16.png'), _('Run Script ...\tSHIFT+S'),
                                                   self)
        self.menufilerunscript.setToolTip(
           _( "Will run the opened Tcl Script thus\n"
            "enabling the automation of certain\n"
            "functions of FlatCAM.")
        )
        self.menufile_scripting.addAction(self.menufilenewscript)
        self.menufile_scripting.addAction(self.menufileopenscript)
        self.menufile_scripting.addSeparator()
        self.menufile_scripting.addAction(self.menufilerunscript)

        # Separator
        self.menufile.addSeparator()

        # Import ...
        self.menufileimport = self.menufile.addMenu(QtGui.QIcon('share/import.png'), _('Import'))
        self.menufileimportsvg = QtWidgets.QAction(QtGui.QIcon('share/svg16.png'),
                                                   _('&SVG as Geometry Object ...'), self)
        self.menufileimport.addAction(self.menufileimportsvg)
        self.menufileimportsvg_as_gerber = QtWidgets.QAction(QtGui.QIcon('share/svg16.png'),
                                                             _('&SVG as Gerber Object ...'), self)
        self.menufileimport.addAction(self.menufileimportsvg_as_gerber)
        self.menufileimport.addSeparator()

        self.menufileimportdxf = QtWidgets.QAction(QtGui.QIcon('share/dxf16.png'),
                                                   _('&DXF as Geometry Object ...'), self)
        self.menufileimport.addAction(self.menufileimportdxf)
        self.menufileimportdxf_as_gerber = QtWidgets.QAction(QtGui.QIcon('share/dxf16.png'),
                                                             _('&DXF as Gerber Object ...'), self)
        self.menufileimport.addAction(self.menufileimportdxf_as_gerber)
        self.menufileimport.addSeparator()

        # Export ...
        self.menufileexport = self.menufile.addMenu(QtGui.QIcon('share/export.png'), _('Export'))
        self.menufileexport.setToolTipsVisible(True)

        self.menufileexportsvg = QtWidgets.QAction(QtGui.QIcon('share/export.png'), _('Export &SVG ...'), self)
        self.menufileexport.addAction(self.menufileexportsvg)

        self.menufileexportdxf = QtWidgets.QAction(QtGui.QIcon('share/export.png'), _('Export DXF ...'), self)
        self.menufileexport.addAction(self.menufileexportdxf)

        self.menufileexport.addSeparator()

        self.menufileexportpng = QtWidgets.QAction(QtGui.QIcon('share/export_png32.png'), _('Export &PNG ...'), self)
        self.menufileexportpng.setToolTip(
            _("Will export an image in PNG format,\n"
              "the saved image will contain the visual \n"
              "information currently in FlatCAM Plot Area.")
        )
        self.menufileexport.addAction(self.menufileexportpng)

        self.menufileexport.addSeparator()

        self.menufileexportexcellon = QtWidgets.QAction(QtGui.QIcon('share/drill32.png'), _('Export &Excellon ...'),
                                                        self)
        self.menufileexportexcellon.setToolTip(
           _("Will export an Excellon Object as Excellon file,\n"
             "the coordinates format, the file units and zeros\n"
             "are set in Preferences -> Excellon Export.")
        )
        self.menufileexport.addAction(self.menufileexportexcellon)

        self.menufileexportgerber = QtWidgets.QAction(QtGui.QIcon('share/flatcam_icon32.png'), _('Export &Gerber ...'),
                                                        self)
        self.menufileexportgerber.setToolTip(
            _("Will export an Gerber Object as Gerber file,\n"
              "the coordinates format, the file units and zeros\n"
              "are set in Preferences -> Gerber Export.")
        )
        self.menufileexport.addAction(self.menufileexportgerber)

        # Separator
        self.menufile.addSeparator()

        # Save Defaults
        self.menufilesavedefaults = QtWidgets.QAction(QtGui.QIcon('share/defaults.png'), _('Save &Defaults'), self)
        self.menufile.addAction(self.menufilesavedefaults)

        # Separator
        self.menufile.addSeparator()

        self.menufile_save = self.menufile.addMenu(QtGui.QIcon('share/save_as.png'), _('Save'))

        # Save Project
        self.menufilesaveproject = QtWidgets.QAction(QtGui.QIcon('share/floppy16.png'), _('&Save Project ...'), self)
        self.menufile_save.addAction(self.menufilesaveproject)

        # Save Project As ...
        self.menufilesaveprojectas = QtWidgets.QAction(QtGui.QIcon('share/save_as.png'),
                                                       _('Save Project &As ...\tCTRL+S'), self)
        self.menufile_save.addAction(self.menufilesaveprojectas)

        # Save Project Copy ...
        self.menufilesaveprojectcopy = QtWidgets.QAction(QtGui.QIcon('share/floppy16.png'), _('Save Project C&opy ...'),
                                                     self)
        self.menufile_save.addAction(self.menufilesaveprojectcopy)

        # Separator
        self.menufile.addSeparator()

        # Quit
        self.menufile_exit = QtWidgets.QAction(QtGui.QIcon('share/power16.png'), _('E&xit'), self)
        # exitAction.setShortcut('Ctrl+Q')
        # exitAction.setStatusTip('Exit application')
        self.menufile.addAction(self.menufile_exit)

        # ## Edit # ##
        self.menuedit = self.menu.addMenu(_('&Edit'))
        # Separator
        self.menuedit.addSeparator()
        self.menueditedit = self.menuedit.addAction(QtGui.QIcon('share/edit16.png'), _('Edit Object\tE'))
        self.menueditok = self.menuedit.addAction(QtGui.QIcon('share/edit_ok16.png'), _('Close Editor\tCTRL+S'))

        # adjust the initial state of the menu entries related to the editor
        self.menueditedit.setDisabled(False)
        self.menueditok.setDisabled(True)

        # Separator
        self.menuedit.addSeparator()
        self.menuedit_convert = self.menuedit.addMenu(QtGui.QIcon('share/convert24.png'), _('Conversion'))
        self.menuedit_convertjoin = self.menuedit_convert.addAction(
            QtGui.QIcon('share/join16.png'), _('&Join Geo/Gerber/Exc -> Geo'))
        self.menuedit_convertjoin.setToolTip(
           _("Merge a selection of objects, which can be of type:\n"
             "- Gerber\n"
             "- Excellon\n"
             "- Geometry\n"
             "into a new combo Geometry object.")
        )
        self.menuedit_convertjoinexc = self.menuedit_convert.addAction(
            QtGui.QIcon('share/join16.png'), _('Join Excellon(s) -> Excellon'))
        self.menuedit_convertjoinexc.setToolTip(
           _( "Merge a selection of Excellon objects into a new combo Excellon object.")
        )
        self.menuedit_convertjoingrb = self.menuedit_convert.addAction(
            QtGui.QIcon('share/join16.png'), _('Join Gerber(s) -> Gerber'))
        self.menuedit_convertjoingrb.setToolTip(
            _("Merge a selection of Gerber objects into a new combo Gerber object.")
        )
        # Separator
        self.menuedit_convert.addSeparator()
        self.menuedit_convert_sg2mg = self.menuedit_convert.addAction(
            QtGui.QIcon('share/convert24.png'), _('Convert Single to MultiGeo'))
        self.menuedit_convert_sg2mg.setToolTip(
           _("Will convert a Geometry object from single_geometry type\n"
             "to a multi_geometry type.")
        )
        self.menuedit_convert_mg2sg = self.menuedit_convert.addAction(
            QtGui.QIcon('share/convert24.png'), _('Convert Multi to SingleGeo'))
        self.menuedit_convert_mg2sg.setToolTip(
           _("Will convert a Geometry object from multi_geometry type\n"
             "to a single_geometry type.")
        )
        # Separator
        self.menuedit_convert.addSeparator()
        self.menueditconvert_any2geo = self.menuedit_convert.addAction(QtGui.QIcon('share/copy_geo.png'),
                                                                       _('Convert Any to Geo'))
        self.menueditconvert_any2gerber = self.menuedit_convert.addAction(QtGui.QIcon('share/copy_geo.png'),
                                                                       _('Convert Any to Gerber'))
        self.menuedit_convert.setToolTipsVisible(True)

        # Separator
        self.menuedit.addSeparator()
        self.menueditcopyobject = self.menuedit.addAction(QtGui.QIcon('share/copy.png'), _('&Copy\tCTRL+C'))

        # Separator
        self.menuedit.addSeparator()
        self.menueditdelete = self.menuedit.addAction(QtGui.QIcon('share/trash16.png'), _('&Delete\tDEL'))

        # Separator
        self.menuedit.addSeparator()
        self.menueditorigin = self.menuedit.addAction(QtGui.QIcon('share/origin.png'), _('Se&t Origin\tO'))
        self.menueditjump = self.menuedit.addAction(QtGui.QIcon('share/jump_to16.png'), _('Jump to Location\tJ'))

        # Separator
        self.menuedit.addSeparator()
        self.menuedittoggleunits= self.menuedit.addAction(QtGui.QIcon('share/toggle_units16.png'),
                                                         _('Toggle Units\tQ'))
        self.menueditselectall = self.menuedit.addAction(QtGui.QIcon('share/select_all.png'),
                                                         _('&Select All\tCTRL+A'))

        # Separator
        self.menuedit.addSeparator()
        self.menueditpreferences = self.menuedit.addAction(QtGui.QIcon('share/pref.png'), _('&Preferences\tSHIFT+P'))

        # ## Options # ##
        self.menuoptions = self.menu.addMenu(_('&Options'))
        # self.menuoptions_transfer = self.menuoptions.addMenu(QtGui.QIcon('share/transfer.png'), 'Transfer options')
        # self.menuoptions_transfer_a2p = self.menuoptions_transfer.addAction("Application to Project")
        # self.menuoptions_transfer_p2a = self.menuoptions_transfer.addAction("Project to Application")
        # self.menuoptions_transfer_p2o = self.menuoptions_transfer.addAction("Project to Object")
        # self.menuoptions_transfer_o2p = self.menuoptions_transfer.addAction("Object to Project")
        # self.menuoptions_transfer_a2o = self.menuoptions_transfer.addAction("Application to Object")
        # self.menuoptions_transfer_o2a = self.menuoptions_transfer.addAction("Object to Application")

        # Separator
        # self.menuoptions.addSeparator()

        # self.menuoptions_transform = self.menuoptions.addMenu(QtGui.QIcon('share/transform.png'),
        #                                                       '&Transform Object')
        self.menuoptions_transform_rotate = self.menuoptions.addAction(QtGui.QIcon('share/rotate.png'),
                                                                       _("&Rotate Selection\tSHIFT+(R)"))
        # Separator
        self.menuoptions.addSeparator()

        self.menuoptions_transform_skewx = self.menuoptions.addAction(QtGui.QIcon('share/skewX.png'),
                                                                      _("&Skew on X axis\tSHIFT+X"))
        self.menuoptions_transform_skewy = self.menuoptions.addAction(QtGui.QIcon('share/skewY.png'),
                                                                      _( "S&kew on Y axis\tSHIFT+Y"))

        # Separator
        self.menuoptions.addSeparator()
        self.menuoptions_transform_flipx = self.menuoptions.addAction(QtGui.QIcon('share/flipx.png'),
                                                                      _("Flip on &X axis\tX"))
        self.menuoptions_transform_flipy = self.menuoptions.addAction(QtGui.QIcon('share/flipy.png'),
                                                                      _("Flip on &Y axis\tY"))
        # Separator
        self.menuoptions.addSeparator()

        self.menuoptions_view_source = self.menuoptions.addAction(QtGui.QIcon('share/source32.png'),
                                                                  _("View source\tALT+S"))
        # Separator
        self.menuoptions.addSeparator()

        # ## View # ##
        self.menuview = self.menu.addMenu(_('&View'))
        self.menuviewenable = self.menuview.addAction(QtGui.QIcon('share/replot16.png'), _('Enable all plots\tALT+1'))
        self.menuviewdisableall = self.menuview.addAction(QtGui.QIcon('share/clear_plot16.png'),
                                                          _('Disable all plots\tALT+2'))
        self.menuviewdisableother = self.menuview.addAction(QtGui.QIcon('share/clear_plot16.png'),
                                                            _('Disable non-selected\tALT+3'))
        # Separator
        self.menuview.addSeparator()
        self.menuview_zoom_fit = self.menuview.addAction(QtGui.QIcon('share/zoom_fit32.png'), _("&Zoom Fit\tV"))
        self.menuview_zoom_in = self.menuview.addAction(QtGui.QIcon('share/zoom_in32.png'), _("&Zoom In\t="))
        self.menuview_zoom_out = self.menuview.addAction(QtGui.QIcon('share/zoom_out32.png'), _("&Zoom Out\t-"))
        self.menuview.addSeparator()

        self.menuview_toggle_code_editor = self.menuview.addAction(QtGui.QIcon('share/code_editor32.png'),
                                                                   _('Toggle Code Editor\tCTRL+E'))
        self.menuview.addSeparator()
        self.menuview_toggle_fscreen = self.menuview.addAction(
            QtGui.QIcon('share/fscreen32.png'), _("&Toggle FullScreen\tALT+F10"))
        self.menuview_toggle_parea = self.menuview.addAction(
            QtGui.QIcon('share/plot32.png'), _("&Toggle Plot Area\tCTRL+F10"))
        self.menuview_toggle_notebook = self.menuview.addAction(
            QtGui.QIcon('share/notebook32.png'), _("&Toggle Project/Sel/Tool\t`"))

        self.menuview.addSeparator()
        self.menuview_toggle_grid = self.menuview.addAction(QtGui.QIcon('share/grid32.png'), _("&Toggle Grid Snap\tG")
                                                            )
        self.menuview_toggle_axis = self.menuview.addAction(QtGui.QIcon('share/axis32.png'), _("&Toggle Axis\tSHIFT+G")
                                                            )
        self.menuview_toggle_workspace = self.menuview.addAction(QtGui.QIcon('share/workspace24.png'),
                                                                 _("Toggle Workspace\tSHIFT+W"))

        # ## Tool ###
        self.menutool = QtWidgets.QMenu(_('&Tool'))
        self.menutoolaction = self.menu.addMenu(self.menutool)
        self.menutoolshell = self.menutool.addAction(QtGui.QIcon('share/shell16.png'), _('&Command Line\tS'))

        # ## Help ###
        self.menuhelp = self.menu.addMenu(_('&Help'))
        self.menuhelp_manual = self.menuhelp.addAction(QtGui.QIcon('share/globe16.png'), _('Help\tF1'))
        self.menuhelp_home = self.menuhelp.addAction(QtGui.QIcon('share/home16.png'), _('FlatCAM.org'))
        self.menuhelp.addSeparator()
        self.menuhelp_shortcut_list = self.menuhelp.addAction(QtGui.QIcon('share/shortcuts24.png'),
                                                              _('Shortcuts List\tF3'))
        self.menuhelp_videohelp = self.menuhelp.addAction(QtGui.QIcon('share/youtube32.png'), _('YouTube Channel\tF4')
                                                          )
        self.menuhelp_about = self.menuhelp.addAction(QtGui.QIcon('share/about32.png'), _('About'))

        # ## FlatCAM Editor menu ###
        self.geo_editor_menu = QtWidgets.QMenu(">Geo Editor<")
        self.menu.addMenu(self.geo_editor_menu)

        self.geo_add_circle_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/circle32.png'), _('Add Circle\tO')
        )
        self.geo_add_arc_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/arc16.png'), _('Add Arc\tA'))
        self.geo_editor_menu.addSeparator()
        self.geo_add_rectangle_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/rectangle32.png'), _('Add Rectangle\tR')
        )
        self.geo_add_polygon_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/polygon32.png'), _('Add Polygon\tN')
        )
        self.geo_add_path_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/path32.png'), _('Add Path\tP'))
        self.geo_editor_menu.addSeparator()
        self.geo_add_text_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/text32.png'), _('Add Text\tT'))
        self.geo_editor_menu.addSeparator()
        self.geo_union_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/union16.png'),
                                                                 _('Polygon Union\tU'))
        self.geo_intersection_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/intersection16.png'),
                                                                        _('Polygon Intersection\tE'))
        self.geo_subtract_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/subtract16.png'), _('Polygon Subtraction\tS')
        )
        self.geo_editor_menu.addSeparator()
        self.geo_cutpath_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/cutpath16.png'),
                                                                   _('Cut Path\tX'))
        # self.move_menuitem = self.menu.addAction(QtGui.QIcon('share/move16.png'), "Move Objects 'm'")
        self.geo_copy_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/copy16.png'), _("Copy Geom\tC"))
        self.geo_delete_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/deleteshape16.png'), _("Delete Shape\tDEL")
        )
        self.geo_editor_menu.addSeparator()
        self.geo_move_menuitem = self.geo_editor_menu.addAction(QtGui.QIcon('share/move32.png'), _("Move\tM"))
        self.geo_buffer_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/buffer16.png'),_( "Buffer Tool\tB")
        )
        self.geo_paint_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/paint16.png'), _("Paint Tool\tI")
        )
        self.geo_transform_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/transform.png'),_( "Transform Tool\tALT+R")
        )
        self.geo_editor_menu.addSeparator()
        self.geo_cornersnap_menuitem = self.geo_editor_menu.addAction(
            QtGui.QIcon('share/corner32.png'), _("Toggle Corner Snap\tK")
        )

        self.exc_editor_menu = QtWidgets.QMenu(_(">Excellon Editor<"))
        self.menu.addMenu(self.exc_editor_menu)

        self.exc_add_array_drill_menuitem = self.exc_editor_menu.addAction(
            QtGui.QIcon('share/rectangle32.png'), _('Add Drill Array\tA'))
        self.exc_add_drill_menuitem = self.exc_editor_menu.addAction(QtGui.QIcon('share/plus16.png'),
                                                                     _('Add Drill\tD'))
        self.exc_editor_menu.addSeparator()

        self.exc_resize_drill_menuitem = self.exc_editor_menu.addAction(
            QtGui.QIcon('share/resize16.png'), _('Resize Drill(S)\tR')
        )
        self.exc_copy_drill_menuitem = self.exc_editor_menu.addAction(QtGui.QIcon('share/copy32.png'), _('Copy\tC'))
        self.exc_delete_drill_menuitem = self.exc_editor_menu.addAction(
            QtGui.QIcon('share/deleteshape32.png'), _('Delete\tDEL')
        )
        self.exc_editor_menu.addSeparator()

        self.exc_move_drill_menuitem = self.exc_editor_menu.addAction(
            QtGui.QIcon('share/move32.png'),_( 'Move Drill(s)\tM'))

        # ## APPLICATION GERBER EDITOR MENU ###
        self.grb_editor_menu = QtWidgets.QMenu(_(">Gerber Editor<"))
        self.menu.addMenu(self.grb_editor_menu)

        self.grb_add_pad_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/aperture16.png'), _('Add Pad\tP'))
        self.grb_add_pad_array_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/padarray32.png'), _('Add Pad Array\tA'))
        self.grb_add_track_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/track32.png'), _('Add Track\tT'))
        self.grb_add_region_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/rectangle32.png'),
                                                                      _('Add Region\tN'))
        self.grb_editor_menu.addSeparator()

        self.grb_convert_poly_menuitem  = self.grb_editor_menu.addAction(QtGui.QIcon('share/poligonize32.png'),
                                                                         _("Poligonize\tALT+N"))
        self.grb_add_semidisc_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/semidisc32.png'),
                                                                        _("Add SemiDisc\tE"))
        self.grb_add_disc_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/disc32.png'),
                                                                        _("Add Disc\tD"))
        self.grb_add_buffer_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/buffer16-2.png'),
                                                                      _('Buffer\tB'))
        self.grb_add_scale_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/scale32.png'),
                                                                     _('Scale\tS'))
        self.grb_transform_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/transform.png'),_( "Transform\tALT+R")
        )
        self.grb_editor_menu.addSeparator()

        self.grb_copy_menuitem = self.grb_editor_menu.addAction(QtGui.QIcon('share/copy32.png'), _('Copy\tC'))
        self.grb_delete_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/deleteshape32.png'), _('Delete\tDEL')
        )
        self.grb_editor_menu.addSeparator()

        self.grb_move_menuitem = self.grb_editor_menu.addAction(
            QtGui.QIcon('share/move32.png'),_( 'Move\tM'))

        self.grb_editor_menu.menuAction().setVisible(False)
        self.grb_editor_menu.setDisabled(True)

        self.geo_editor_menu.menuAction().setVisible(False)
        self.geo_editor_menu.setDisabled(True)

        self.exc_editor_menu.menuAction().setVisible(False)
        self.exc_editor_menu.setDisabled(True)

        # ################################
        # ### Project Tab Context menu ###
        # ################################

        self.menuproject = QtWidgets.QMenu()
        self.menuprojectenable = self.menuproject.addAction(QtGui.QIcon('share/replot32.png'), _('Enable Plot'))
        self.menuprojectdisable = self.menuproject.addAction(QtGui.QIcon('share/clear_plot32.png'), _('Disable Plot'))
        self.menuproject.addSeparator()
        self.menuprojectgeneratecnc = self.menuproject.addAction(QtGui.QIcon('share/cnc32.png'), _('Generate CNC'))
        self.menuprojectviewsource = self.menuproject.addAction(QtGui.QIcon('share/source32.png'), _('View Source'))

        self.menuprojectedit = self.menuproject.addAction(QtGui.QIcon('share/edit_ok32.png'), _('Edit'))
        self.menuprojectcopy = self.menuproject.addAction(QtGui.QIcon('share/copy32.png'), _('Copy'))
        self.menuprojectdelete = self.menuproject.addAction(QtGui.QIcon('share/delete32.png'), _('Delete'))
        self.menuprojectsave= self.menuproject.addAction(QtGui.QIcon('share/save_as.png'), _('Save'))
        self.menuproject.addSeparator()

        self.menuprojectproperties = self.menuproject.addAction(QtGui.QIcon('share/properties32.png'), _('Properties'))

        # ################
        # ### Splitter ###
        # ################

        # IMPORTANT #
        # The order: SPITTER -> NOTEBOOK -> SNAP TOOLBAR is important and without it the GUI will not be initialized as
        # desired.
        self.splitter = QtWidgets.QSplitter()
        self.setCentralWidget(self.splitter)

        # self.notebook = QtWidgets.QTabWidget()
        self.notebook = FCDetachableTab(protect=True)
        self.notebook.setTabsClosable(False)
        self.notebook.useOldIndex(True)

        self.splitter.addWidget(self.notebook)

        self.splitter_left = QtWidgets.QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.splitter_left)
        self.splitter_left.addWidget(self.notebook)
        self.splitter_left.setHandleWidth(0)

        # ##############
        # ## Toolbar ###
        # ##############

        # ## TOOLBAR INSTALLATION ###
        self.toolbarfile = QtWidgets.QToolBar(_('File Toolbar'))
        self.toolbarfile.setObjectName('File_TB')
        self.addToolBar(self.toolbarfile)

        self.toolbargeo = QtWidgets.QToolBar(_('Edit Toolbar'))
        self.toolbargeo.setObjectName('Edit_TB')
        self.addToolBar(self.toolbargeo)

        self.toolbarview = QtWidgets.QToolBar(_('View Toolbar'))
        self.toolbarview.setObjectName('View_TB')
        self.addToolBar(self.toolbarview)

        self.toolbarshell = QtWidgets.QToolBar(_('Shell Toolbar'))
        self.toolbarshell.setObjectName('Shell_TB')
        self.addToolBar(self.toolbarshell)

        self.toolbartools = QtWidgets.QToolBar(_('Tools Toolbar'))
        self.toolbartools.setObjectName('Tools_TB')
        self.addToolBar(self.toolbartools)

        self.exc_edit_toolbar = QtWidgets.QToolBar(_('Excellon Editor Toolbar'))
        self.exc_edit_toolbar.setObjectName('ExcEditor_TB')
        self.addToolBar(self.exc_edit_toolbar)

        self.geo_edit_toolbar = QtWidgets.QToolBar(_('Geometry Editor Toolbar'))
        self.geo_edit_toolbar.setObjectName('GeoEditor_TB')
        self.addToolBar(self.geo_edit_toolbar)

        self.grb_edit_toolbar = QtWidgets.QToolBar(_('Gerber Editor Toolbar'))
        self.grb_edit_toolbar.setObjectName('GrbEditor_TB')
        self.addToolBar(self.grb_edit_toolbar)

        self.snap_toolbar = QtWidgets.QToolBar(_('Grid Toolbar'))
        self.snap_toolbar.setObjectName('Snap_TB')
        self.addToolBar(self.snap_toolbar)

        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("layout"):
            layout = settings.value('layout', type=str)
            if layout == 'standard':
                pass
            elif layout == 'compact':
                self.removeToolBar(self.snap_toolbar)
                self.snap_toolbar.setMaximumHeight(30)
                self.splitter_left.addWidget(self.snap_toolbar)

        # ## File Toolbar ###
        self.file_open_gerber_btn = self.toolbarfile.addAction(QtGui.QIcon('share/flatcam_icon32.png'),
                                                               _("Open Gerber"))
        self.file_open_excellon_btn = self.toolbarfile.addAction(QtGui.QIcon('share/drill32.png'), _("Open Excellon"))
        self.toolbarfile.addSeparator()
        self.file_open_btn = self.toolbarfile.addAction(QtGui.QIcon('share/folder32.png'), _("Open project"))
        self.file_save_btn = self.toolbarfile.addAction(QtGui.QIcon('share/floppy32.png'), _("Save project"))

        # ## Edit Toolbar ###
        self.newgeo_btn = self.toolbargeo.addAction(QtGui.QIcon('share/new_geo32_bis.png'), _("New Blank Geometry"))
        self.newgrb_btn = self.toolbargeo.addAction(QtGui.QIcon('share/new_geo32.png'), _("New Blank Gerber"))
        self.newexc_btn = self.toolbargeo.addAction(QtGui.QIcon('share/new_exc32.png'), _("New Blank Excellon"))
        self.toolbargeo.addSeparator()
        self.editgeo_btn = self.toolbargeo.addAction(QtGui.QIcon('share/edit32.png'), _("Editor"))
        self.update_obj_btn = self.toolbargeo.addAction(
            QtGui.QIcon('share/edit_ok32_bis.png'), _("Save Object and close the Editor")
        )

        self.toolbargeo.addSeparator()
        self.delete_btn = self.toolbargeo.addAction(QtGui.QIcon('share/cancel_edit32.png'), _("&Delete"))

        # ## View Toolbar # ##
        self.replot_btn = self.toolbarview.addAction(QtGui.QIcon('share/replot32.png'), _("&Replot"))
        self.clear_plot_btn = self.toolbarview.addAction(QtGui.QIcon('share/clear_plot32.png'), _("&Clear plot"))
        self.zoom_in_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_in32.png'), _("Zoom In"))
        self.zoom_out_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_out32.png'), _("Zoom Out"))
        self.zoom_fit_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_fit32.png'), _("Zoom Fit"))

        # self.toolbarview.setVisible(False)

        # ## Shell Toolbar ##
        self.shell_btn = self.toolbarshell.addAction(QtGui.QIcon('share/shell32.png'), _("&Command Line"))

        # ## Tools Toolbar ##
        self.dblsided_btn = self.toolbartools.addAction(QtGui.QIcon('share/doubleside32.png'), _("2Sided Tool"))
        self.cutout_btn = self.toolbartools.addAction(QtGui.QIcon('share/cut16_bis.png'), _("&Cutout Tool"))
        self.ncc_btn = self.toolbartools.addAction(QtGui.QIcon('share/ncc16.png'), _("NCC Tool"))
        self.paint_btn = self.toolbartools.addAction(QtGui.QIcon('share/paint20_1.png'), _("Paint Tool"))
        self.toolbartools.addSeparator()

        self.panelize_btn = self.toolbartools.addAction(QtGui.QIcon('share/panel16.png'), _("Panel Tool"))
        self.film_btn = self.toolbartools.addAction(QtGui.QIcon('share/film16.png'),_( "Film Tool"))
        self.solder_btn = self.toolbartools.addAction(QtGui.QIcon('share/solderpastebis32.png'), _("SolderPaste Tool"))
        self.sub_btn = self.toolbartools.addAction(QtGui.QIcon('share/sub32.png'), _("Substract Tool"))

        self.toolbartools.addSeparator()

        self.calculators_btn = self.toolbartools.addAction(QtGui.QIcon('share/calculator24.png'), _("Calculators Tool"))
        self.transform_btn = self.toolbartools.addAction(QtGui.QIcon('share/transform.png'), _("Transform Tool"))

        # ## Drill Editor Toolbar ###
        self.select_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select"))
        self.add_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/plus16.png'), _('Add Drill Hole'))
        self.add_drill_array_btn = self.exc_edit_toolbar.addAction(
            QtGui.QIcon('share/addarray16.png'), _('Add Drill Hole Array'))
        self.resize_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/resize16.png'), _('Resize Drill'))
        self.exc_edit_toolbar.addSeparator()

        self.copy_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _('Copy Drill'))
        self.delete_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'), _("Delete Drill"))

        self.exc_edit_toolbar.addSeparator()
        self.move_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move Drill"))

        # ## Geometry Editor Toolbar ###
        self.geo_select_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select"))
        self.geo_add_circle_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/circle32.png'), _('Add Circle'))
        self.geo_add_arc_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/arc32.png'), _('Add Arc'))
        self.geo_add_rectangle_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/rectangle32.png'),
                                                                     _('Add Rectangle'))

        self.geo_edit_toolbar.addSeparator()
        self.geo_add_path_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/path32.png'), _('Add Path'))
        self.geo_add_polygon_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/polygon32.png'), _('Add Polygon'))
        self.geo_edit_toolbar.addSeparator()
        self.geo_add_text_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/text32.png'), _('Add Text'))
        self.geo_add_buffer_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/buffer16-2.png'), _('Add Buffer'))
        self.geo_add_paint_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/paint20_1.png'), _('Paint Shape'))
        self.geo_eraser_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/eraser26.png'), _('Eraser'))

        self.geo_edit_toolbar.addSeparator()
        self.geo_union_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/union32.png'), _('Polygon Union'))
        self.geo_intersection_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/intersection32.png'),
                                                                    _('Polygon Intersection'))
        self.geo_subtract_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/subtract32.png'),
                                                                _('Polygon Subtraction'))

        self.geo_edit_toolbar.addSeparator()
        self.geo_cutpath_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/cutpath32.png'), _('Cut Path'))
        self.geo_copy_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _("Copy Shape(s)"))

        self.geo_delete_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'),
                                                              _("Delete Shape '-'"))
        self.geo_transform_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/transform.png'),
                                                                 _("Transformations"))
        self.geo_edit_toolbar.addSeparator()
        self.geo_move_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move Objects "))

        # ## Gerber Editor Toolbar # ##
        self.grb_select_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select"))
        self.grb_add_pad_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/aperture32.png'), _("Add Pad"))
        self.add_pad_ar_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/padarray32.png'), _('Add Pad Array'))
        self.grb_add_track_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/track32.png'), _("Add Track"))
        self.grb_add_region_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/polygon32.png'), _("Add Region"))
        self.grb_convert_poly_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/poligonize32.png'),
                                                                    _("Poligonize"))

        self.grb_add_semidisc_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/semidisc32.png'), _("SemiDisc"))
        self.grb_add_disc_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/disc32.png'), _("Disc"))
        self.grb_edit_toolbar.addSeparator()

        self.aperture_buffer_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/buffer16-2.png'), _('Buffer'))
        self.aperture_scale_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/scale32.png'), _('Scale'))
        self.aperture_eraser_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/eraser26.png'), _('Eraser'))

        self.grb_edit_toolbar.addSeparator()
        self.aperture_copy_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _("Copy"))
        self.aperture_delete_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'),
                                                                   _("Delete"))
        self.grb_transform_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/transform.png'),
                                                                 _("Transformations"))
        self.grb_edit_toolbar.addSeparator()
        self.aperture_move_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move"))

        # # ## Snap Toolbar # ##
        # Snap GRID toolbar is always active to facilitate usage of measurements done on GRID
        # self.addToolBar(self.snap_toolbar)

        self.grid_snap_btn = self.snap_toolbar.addAction(QtGui.QIcon('share/grid32.png'), _('Snap to grid'))
        self.grid_gap_x_entry = FCEntry2()
        self.grid_gap_x_entry.setMaximumWidth(70)
        self.grid_gap_x_entry.setToolTip(_("Grid X snapping distance"))
        self.snap_toolbar.addWidget(self.grid_gap_x_entry)

        self.grid_gap_y_entry = FCEntry2()
        self.grid_gap_y_entry.setMaximumWidth(70)
        self.grid_gap_y_entry.setToolTip(_("Grid Y snapping distance"))
        self.snap_toolbar.addWidget(self.grid_gap_y_entry)

        self.grid_space_label = QtWidgets.QLabel("  ")
        self.snap_toolbar.addWidget(self.grid_space_label)
        self.grid_gap_link_cb = FCCheckBox()
        self.grid_gap_link_cb.setToolTip(_("When active, value on Grid_X\n"
                                         "is copied to the Grid_Y value."))
        self.snap_toolbar.addWidget(self.grid_gap_link_cb)

        self.ois_grid = OptionalInputSection(self.grid_gap_link_cb, [self.grid_gap_y_entry], logic=False)

        self.corner_snap_btn = self.snap_toolbar.addAction(QtGui.QIcon('share/corner32.png'), _('Snap to corner'))

        self.snap_max_dist_entry = FCEntry()
        self.snap_max_dist_entry.setMaximumWidth(70)
        self.snap_max_dist_entry.setToolTip(_("Max. magnet distance"))
        self.snap_magnet = self.snap_toolbar.addWidget(self.snap_max_dist_entry)


        ############## ##
        # ## Notebook # ##
        ############## ##

        # ## Project # ##
        # self.project_tab = QtWidgets.QWidget()
        # self.project_tab.setObjectName("project_tab")
        # # project_tab.setMinimumWidth(250)  # Hack
        # self.project_tab_layout = QtWidgets.QVBoxLayout(self.project_tab)
        # self.project_tab_layout.setContentsMargins(2, 2, 2, 2)
        # self.notebook.addTab(self.project_tab,_( "Project"))

        self.project_tab = QtWidgets.QWidget()
        self.project_tab.setObjectName("project_tab")

        self.project_frame_lay = QtWidgets.QVBoxLayout(self.project_tab)
        self.project_frame_lay.setContentsMargins(0, 0, 0, 0)

        self.project_frame = QtWidgets.QFrame()
        self.project_frame.setContentsMargins(0, 0, 0, 0)
        self.project_frame_lay.addWidget(self.project_frame)

        self.project_tab_layout = QtWidgets.QVBoxLayout(self.project_frame)
        self.project_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.notebook.addTab(self.project_tab, _("Project"))
        self.project_frame.setDisabled(False)

        # ## Selected # ##
        self.selected_tab = QtWidgets.QWidget()
        self.selected_tab.setObjectName("selected_tab")
        self.selected_tab_layout = QtWidgets.QVBoxLayout(self.selected_tab)
        self.selected_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.selected_scroll_area = VerticalScrollArea()
        self.selected_tab_layout.addWidget(self.selected_scroll_area)
        self.notebook.addTab(self.selected_tab, _("Selected"))

        # ## Tool # ##
        self.tool_tab = QtWidgets.QWidget()
        self.tool_tab.setObjectName("tool_tab")
        self.tool_tab_layout = QtWidgets.QVBoxLayout(self.tool_tab)
        self.tool_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.notebook.addTab(self.tool_tab, _("Tool"))
        self.tool_scroll_area = VerticalScrollArea()
        self.tool_tab_layout.addWidget(self.tool_scroll_area)

        self.right_widget = QtWidgets.QWidget()
        self.right_widget.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.splitter.addWidget(self.right_widget)

        self.right_lay = QtWidgets.QVBoxLayout()
        self.right_lay.setContentsMargins(0, 0, 0, 0)
        self.right_widget.setLayout(self.right_lay)
        # self.plot_tab_area = FCTab()
        self.plot_tab_area = FCDetachableTab(protect=False, protect_by_name=[_('Plot Area')])
        self.plot_tab_area.useOldIndex(True)

        self.right_lay.addWidget(self.plot_tab_area)
        self.plot_tab_area.setTabsClosable(True)

        self.plot_tab = QtWidgets.QWidget()
        self.plot_tab.setObjectName("plotarea")
        self.plot_tab_area.addTab(self.plot_tab, _("Plot Area"))

        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.setContentsMargins(2, 2, 2, 2)
        self.plot_tab.setLayout(self.right_layout)

        # remove the close button from the Plot Area tab (first tab index = 0) as this one will always be ON
        self.plot_tab_area.protectTab(0)

        ###################################### ##
        # ## HERE WE BUILD THE PREF. TAB AREA # ##
        ###################################### ##
        self.preferences_tab = QtWidgets.QWidget()
        self.pref_tab_layout = QtWidgets.QVBoxLayout(self.preferences_tab)
        self.pref_tab_layout.setContentsMargins(2, 2, 2, 2)

        self.pref_tab_area = FCTab()
        self.pref_tab_area.setTabsClosable(False)
        self.pref_tab_area_tabBar = self.pref_tab_area.tabBar()
        self.pref_tab_area_tabBar.setStyleSheet("QTabBar::tab{width:90px;}")
        self.pref_tab_area_tabBar.setExpanding(True)
        self.pref_tab_layout.addWidget(self.pref_tab_area)

        self.general_tab = QtWidgets.QWidget()
        self.pref_tab_area.addTab(self.general_tab, _("General"))
        self.general_tab_lay = QtWidgets.QVBoxLayout()
        self.general_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.general_tab.setLayout(self.general_tab_lay)

        self.hlay1 = QtWidgets.QHBoxLayout()
        self.general_tab_lay.addLayout(self.hlay1)

        self.options_combo = QtWidgets.QComboBox()
        self.options_combo.addItem(_("APP.  DEFAULTS"))
        self.options_combo.addItem(_("PROJ. OPTIONS "))
        self.hlay1.addWidget(self.options_combo)

        # disable this button as it may no longer be useful
        self.options_combo.setVisible(False)
        self.hlay1.addStretch()

        self.general_scroll_area = QtWidgets.QScrollArea()
        self.general_tab_lay.addWidget(self.general_scroll_area)

        self.gerber_tab = QtWidgets.QWidget()
        self.pref_tab_area.addTab(self.gerber_tab, _("GERBER"))
        self.gerber_tab_lay = QtWidgets.QVBoxLayout()
        self.gerber_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.gerber_tab.setLayout(self.gerber_tab_lay)

        self.gerber_scroll_area = QtWidgets.QScrollArea()
        self.gerber_tab_lay.addWidget(self.gerber_scroll_area)

        self.excellon_tab = QtWidgets.QWidget()
        self.pref_tab_area.addTab(self.excellon_tab, _("EXCELLON"))
        self.excellon_tab_lay = QtWidgets.QVBoxLayout()
        self.excellon_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.excellon_tab.setLayout(self.excellon_tab_lay)

        self.excellon_scroll_area = QtWidgets.QScrollArea()
        self.excellon_tab_lay.addWidget(self.excellon_scroll_area)

        self.geometry_tab = QtWidgets.QWidget()
        self.pref_tab_area.addTab(self.geometry_tab, _("GEOMETRY"))
        self.geometry_tab_lay = QtWidgets.QVBoxLayout()
        self.geometry_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.geometry_tab.setLayout(self.geometry_tab_lay)

        self.geometry_scroll_area = QtWidgets.QScrollArea()
        self.geometry_tab_lay.addWidget(self.geometry_scroll_area)

        self.cncjob_tab = QtWidgets.QWidget()
        self.cncjob_tab.setObjectName("cncjob_tab")
        self.pref_tab_area.addTab(self.cncjob_tab, _("CNC-JOB"))
        self.cncjob_tab_lay = QtWidgets.QVBoxLayout()
        self.cncjob_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.cncjob_tab.setLayout(self.cncjob_tab_lay)

        self.cncjob_scroll_area = QtWidgets.QScrollArea()
        self.cncjob_tab_lay.addWidget(self.cncjob_scroll_area)

        self.tools_tab = QtWidgets.QWidget()
        self.pref_tab_area.addTab(self.tools_tab, _("TOOLS"))
        self.tools_tab_lay = QtWidgets.QVBoxLayout()
        self.tools_tab_lay.setContentsMargins(2, 2, 2, 2)
        self.tools_tab.setLayout(self.tools_tab_lay)

        self.tools_scroll_area = QtWidgets.QScrollArea()
        self.tools_tab_lay.addWidget(self.tools_scroll_area)

        self.pref_tab_bottom_layout = QtWidgets.QHBoxLayout()
        self.pref_tab_bottom_layout.setAlignment(QtCore.Qt.AlignVCenter)
        self.pref_tab_layout.addLayout(self.pref_tab_bottom_layout)

        self.pref_tab_bottom_layout_1 = QtWidgets.QHBoxLayout()
        self.pref_tab_bottom_layout_1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.pref_tab_bottom_layout.addLayout(self.pref_tab_bottom_layout_1)

        self.pref_import_button = QtWidgets.QPushButton()
        self.pref_import_button.setText(_("Import Preferences"))
        self.pref_import_button.setMinimumWidth(130)
        self.pref_import_button.setToolTip(
            _("Import a full set of FlatCAM settings from a file\n"
              "previously saved on HDD.\n\n"
              "FlatCAM automatically save a 'factory_defaults' file\n"
              "on the first start. Do not delete that file."))
        self.pref_tab_bottom_layout_1.addWidget(self.pref_import_button)

        self.pref_export_button = QtWidgets.QPushButton()
        self.pref_export_button.setText(_("Export Preferences"))
        self.pref_export_button.setMinimumWidth(130)
        self.pref_export_button.setToolTip(
           _( "Export a full set of FlatCAM settings in a file\n"
              "that is saved on HDD."))
        self.pref_tab_bottom_layout_1.addWidget(self.pref_export_button)

        self.pref_open_button = QtWidgets.QPushButton()
        self.pref_open_button.setText(_("Open Pref Folder"))
        self.pref_open_button.setMinimumWidth(130)
        self.pref_open_button.setToolTip(
            _("Open the folder where FlatCAM save the preferences files."))
        self.pref_tab_bottom_layout_1.addWidget(self.pref_open_button)

        self.pref_tab_bottom_layout_2 = QtWidgets.QHBoxLayout()
        self.pref_tab_bottom_layout_2.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.pref_tab_bottom_layout.addLayout(self.pref_tab_bottom_layout_2)

        self.pref_save_button = QtWidgets.QPushButton()
        self.pref_save_button.setText(_("Save Preferences"))
        self.pref_save_button.setMinimumWidth(130)
        self.pref_save_button.setToolTip(
            _("Save the current settings in the 'current_defaults' file\n"
              "which is the file storing the working default preferences."))
        self.pref_tab_bottom_layout_2.addWidget(self.pref_save_button)

        # #################################################
        # ## HERE WE BUILD THE SHORTCUTS LIST. TAB AREA ###
        # #################################################
        self.shortcuts_tab = QtWidgets.QWidget()
        self.sh_tab_layout = QtWidgets.QVBoxLayout()
        self.sh_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.shortcuts_tab.setLayout(self.sh_tab_layout)

        self.sh_hlay = QtWidgets.QHBoxLayout()
        self.sh_title = QtWidgets.QTextEdit(
            _('<b>Shortcut Key List</b>'))
        self.sh_title.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.sh_title.setFrameStyle(QtWidgets.QFrame.NoFrame)
        self.sh_title.setMaximumHeight(30)
        font = self.sh_title.font()
        font.setPointSize(12)
        self.sh_title.setFont(font)

        self.sh_tab_layout.addWidget(self.sh_title)
        self.sh_tab_layout.addLayout(self.sh_hlay)

        self.app_sh_msg = _(
            '''<b>General Shortcut list</b><br>
            <table border="0" cellpadding="0" cellspacing="0" style="width:283px">
                <tbody>
                    <tr height="20">
                        <td height="20" width="89"><strong>F3</strong></td>
                        <td width="194"><span style="color:#006400"><strong>&nbsp;SHOW SHORTCUT LIST</strong></span></td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>1</strong></td>
                        <td>&nbsp;Switch to Project Tab</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>2</strong></td>
                        <td>&nbsp;Switch to Selected Tab</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>3</strong></td>
                        <td>&nbsp;Switch to Tool Tab</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>B</strong></td>
                        <td>&nbsp;New Gerber</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>E</strong></td>
                        <td>&nbsp;Edit Object (if selected)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>G</strong></td>
                        <td>&nbsp;Grid On/Off</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>J</strong></td>
                        <td>&nbsp;Jump to Coordinates</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>L</strong></td>
                        <td>&nbsp;New Excellon</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>M</strong></td>
                        <td>&nbsp;Move Obj</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>N</strong></td>
                        <td>&nbsp;New Geometry</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>O</strong></td>
                        <td>&nbsp;Set Origin</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Q</strong></td>
                        <td>&nbsp;Change Units</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>P</strong></td>
                        <td>&nbsp;Open Properties Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>R</strong></td>
                        <td>&nbsp;Rotate by 90 degree CW</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>S</strong></td>
                        <td>&nbsp;Shell Toggle</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>T</strong></td>
                        <td>&nbsp;Add a Tool (when in Geometry Selected Tab or in Tools NCC or Tools Paint)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>V</strong></td>
                        <td>&nbsp;Zoom Fit</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>X</strong></td>
                        <td>&nbsp;Flip on X_axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Y</strong></td>
                        <td>&nbsp;Flip on Y_axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>&#39;-&#39;</strong></td>
                        <td>&nbsp;Zoom Out</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>&#39;=&#39;</strong></td>
                        <td>&nbsp;Zoom In</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+A</strong></td>
                        <td>&nbsp;Select All</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+C</strong></td>
                        <td>&nbsp;Copy Obj</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+E</strong></td>
                        <td>&nbsp;Open Excellon File</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+G</strong></td>
                        <td>&nbsp;Open Gerber File</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+N</strong></td>
                        <td>&nbsp;New Project</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+M</strong></td>
                        <td>&nbsp;Measurement Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+O</strong></td>
                        <td>&nbsp;Open Project</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+S</strong></td>
                        <td>&nbsp;Save Project As</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+F10</strong></td>
                        <td>&nbsp;Toggle Plot Area</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+C</strong></td>
                        <td>&nbsp;Copy Obj_Name</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+E</strong></td>
                        <td>&nbsp;Toggle Code Editor</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+G</strong></td>
                        <td>&nbsp;Toggle the axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+P</strong></td>
                        <td>&nbsp;Open Preferences Window</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+R</strong></td>
                        <td>&nbsp;Rotate by 90 degree CCW</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+S</strong></td>
                        <td>&nbsp;Run a Script</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+W</strong></td>
                        <td>&nbsp;Toggle the workspace</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+X</strong></td>
                        <td>&nbsp;Skew on X axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+Y</strong></td>
                        <td>&nbsp;Skew on Y axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+C</strong></td>
                        <td>&nbsp;Calculators Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+D</strong></td>
                        <td>&nbsp;2-Sided PCB Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+K</strong></td>
                        <td>&nbsp;Solder Paste Dispensing Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+L</strong></td>
                        <td>&nbsp;Film PCB Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+N</strong></td>
                        <td>&nbsp;Non-Copper Clearing Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+P</strong></td>
                        <td>&nbsp;Paint Area Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+Q</strong></td>
                        <td>&nbsp;PDF Import Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+R</strong></td>
                        <td>&nbsp;Transformations Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+S</strong></td>
                        <td>&nbsp;View File Source</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+U</strong></td>
                        <td>&nbsp;Cutout PCB Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+1</strong></td>
                        <td>&nbsp;Enable all Plots</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+2</strong></td>
                        <td>&nbsp;Disable all Plots</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+3</strong></td>
                        <td>&nbsp;Disable Non-selected Plots</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+F10</strong></td>
                        <td>&nbsp;Toggle Full Screen</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>F1</strong></td>
                        <td>&nbsp;Open Online Manual</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>F4</strong></td>
                        <td>&nbsp;Open Online Tutorials</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Delete Object</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Alternate: Delete Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>'`'</strong></td>
                        <td>&nbsp;(left to Key_1)Toogle Notebook Area (Left Side)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SPACE</strong></td>
                        <td>&nbsp;En(Dis)able Obj Plot</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Escape</strong></td>
                        <td>&nbsp;Deselects all objects</td>
                    </tr>
                </tbody>
            </table>
    
            '''
        )

        self.sh_app = QtWidgets.QTextEdit()
        self.sh_app.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

        self.sh_app.setText(self.app_sh_msg)
        self.sh_app.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.sh_hlay.addWidget(self.sh_app)

        self.editor_sh_msg = _(
            '''<b>Editor Shortcut list</b><br>
            <br>
            <strong><span style="color:#0000ff">GEOMETRY EDITOR</span></strong><br>
    
            <table border="0" cellpadding="0" cellspacing="0" style="width:283px">
                <tbody>
                    <tr height="20">
                        <td height="20" width="89"><strong>A</strong></td>
                        <td width="194">&nbsp;Draw an Arc</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>B</strong></td>
                        <td>&nbsp;Buffer Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>C</strong></td>
                        <td>&nbsp;Copy Geo Item</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>D</strong></td>
                        <td>&nbsp;Within Add Arc will toogle the ARC direction: CW or CCW</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>E</strong></td>
                        <td>&nbsp;Polygon Intersection Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>I</strong></td>
                        <td>&nbsp;Paint Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>J</strong></td>
                        <td>&nbsp;Jump to Location (x, y)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>K</strong></td>
                        <td>&nbsp;Toggle Corner Snap</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>M</strong></td>
                        <td>&nbsp;Move Geo Item</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>M</strong></td>
                        <td>&nbsp;Within Add Arc will cycle through the ARC modes</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>N</strong></td>
                        <td>&nbsp;Draw a Polygon</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>O</strong></td>
                        <td>&nbsp;Draw a Circle</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>P</strong></td>
                        <td>&nbsp;Draw a Path</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>R</strong></td>
                        <td>&nbsp;Draw Rectangle</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>S</strong></td>
                        <td>&nbsp;Polygon Substraction Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>T</strong></td>
                        <td>&nbsp;Add Text Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>U</strong></td>
                        <td>&nbsp;Polygon Union Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>X</strong></td>
                        <td>&nbsp;Flip shape on X axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Y</strong></td>
                        <td>&nbsp;Flip shape on Y axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+X</strong></td>
                        <td>&nbsp;Skew shape on X axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>SHIFT+Y</strong></td>
                        <td>&nbsp;Skew shape on Y axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+R</strong></td>
                        <td>&nbsp;Editor Transformation Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+X</strong></td>
                        <td>&nbsp;Offset shape on X axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+Y</strong></td>
                        <td>&nbsp;Offset shape on Y axis</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+M</strong></td>
                        <td>&nbsp;Measurement Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+S</strong></td>
                        <td>&nbsp;Save Object and Exit Editor</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+X</strong></td>
                        <td>&nbsp;Polygon Cut Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Space</strong></td>
                        <td>&nbsp;Rotate Geometry</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ENTER</strong></td>
                        <td>&nbsp;Finish drawing for certain tools</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ESC</strong></td>
                        <td>&nbsp;Abort and return to Select</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Delete Shape</td>
                    </tr>
                </tbody>
            </table>
            <br>
            <br>
            <strong><span style="color:#ff0000">EXCELLON EDITOR</span></strong><br>
            <table border="0" cellpadding="0" cellspacing="0" style="width:283px">
                <tbody>
                    <tr height="20">
                        <td height="20" width="89"><strong>A</strong></td>
                        <td width="194">&nbsp;Add Drill Array</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>C</strong></td>
                        <td>&nbsp;Copy Drill(s)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>D</strong></td>
                        <td>&nbsp;Add Drill</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>J</strong></td>
                        <td>&nbsp;Jump to Location (x, y)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>M</strong></td>
                        <td>&nbsp;Move Drill(s)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>R</strong></td>
                        <td>&nbsp;Resize Drill(s)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>T</strong></td>
                        <td>&nbsp;Add a new Tool</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Delete Drill(s)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Alternate: Delete Tool(s)</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ESC</strong></td>
                        <td>&nbsp;Abort and return to Select</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+S</strong></td>
                        <td>&nbsp;Save Object and Exit Editor</td>
                    </tr>
                </tbody>
            </table>
            <br>
            <br>
            <strong><span style="color:#00ff00">GERBER EDITOR</span></strong><br>
            <table border="0" cellpadding="0" cellspacing="0" style="width:283px">
                <tbody>
                    <tr height="20">
                        <td height="20" width="89"><strong>A</strong></td>
                        <td width="194">&nbsp;Add Pad Array</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>B</strong></td>
                        <td>&nbsp;Buffer</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>C</strong></td>
                        <td>&nbsp;Copy</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>D</strong></td>
                        <td>&nbsp;Add Disc</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>E</strong></td>
                        <td>&nbsp;Add SemiDisc</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>J</strong></td>
                        <td>&nbsp;Jump to Location (x, y)</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>M</strong></td>
                        <td>&nbsp;Move</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>N</strong></td>
                        <td>&nbsp;Add Region</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>P</strong></td>
                        <td>&nbsp;Add Pad</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>R</strong></td>
                        <td>&nbsp;Within Track & Region Tools will cycle in REVERSE the bend modes</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>S</strong></td>
                        <td>&nbsp;Scale</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>T</strong></td>
                        <td>&nbsp;Add Track</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>T</strong></td>
                        <td>&nbsp;Within Track & Region Tools will cycle FORWARD the bend modes</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Delete</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>Del</strong></td>
                        <td>&nbsp;Alternate: Delete Apertures</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ESC</strong></td>
                        <td>&nbsp;Abort and return to Select</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>CTRL+S</strong></td>
                        <td>&nbsp;Save Object and Exit Editor</td>
                    </tr>
                    <tr height="20">
                        <td height="20">&nbsp;</td>
                        <td>&nbsp;</td>
                    </tr>
                    <tr height="20">
                        <td height="20"><strong>ALT+R</strong></td>
                        <td>&nbsp;Transformation Tool</td>
                    </tr>
                </tbody>
            </table>
                    '''
        )
        self.sh_editor = QtWidgets.QTextEdit()
        self.sh_editor.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.sh_editor.setText(self.editor_sh_msg)
        self.sh_editor.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.sh_hlay.addWidget(self.sh_editor)


        # ########################################################### ##
        # # ## HERE WE BUILD THE CONTEXT MENU FOR RMB CLICK ON CANVAS # ##
        # ########################################################### ##
        self.popMenu = FCMenu()

        self.popmenu_disable = self.popMenu.addAction(QtGui.QIcon('share/disable32.png'), _("Disable Plot"))
        self.popmenu_panel_toggle = self.popMenu.addAction(QtGui.QIcon('share/notebook16.png'), _("Toggle Panel"))

        self.popMenu.addSeparator()
        self.cmenu_newmenu = self.popMenu.addMenu(QtGui.QIcon('share/file32.png'), _("New"))
        self.popmenu_new_geo = self.cmenu_newmenu.addAction(QtGui.QIcon('share/new_geo32_bis.png'), _("Geometry"))
        self.popmenu_new_grb = self.cmenu_newmenu.addAction(QtGui.QIcon('share/flatcam_icon32.png'), "Gerber")
        self.popmenu_new_exc = self.cmenu_newmenu.addAction(QtGui.QIcon('share/new_exc32.png'), _("Excellon"))
        self.cmenu_newmenu.addSeparator()
        self.popmenu_new_prj = self.cmenu_newmenu.addAction(QtGui.QIcon('share/file16.png'), _("Project"))
        self.popMenu.addSeparator()

        self.cmenu_gridmenu = self.popMenu.addMenu(QtGui.QIcon('share/grid32_menu.png'), _("Grids"))

        self.cmenu_viewmenu = self.popMenu.addMenu(QtGui.QIcon('share/view64.png'), _("View"))
        self.zoomfit = self.cmenu_viewmenu.addAction(QtGui.QIcon('share/zoom_fit32.png'), _("Zoom Fit"))
        self.clearplot = self.cmenu_viewmenu.addAction(QtGui.QIcon('share/clear_plot32.png'), _("Clear Plot"))
        self.replot = self.cmenu_viewmenu.addAction(QtGui.QIcon('share/replot32.png'), _("Replot"))
        self.popMenu.addSeparator()

        self.g_editor_cmenu = self.popMenu.addMenu(QtGui.QIcon('share/draw32.png'), _("Geo Editor"))
        self.draw_line = self.g_editor_cmenu.addAction(QtGui.QIcon('share/path32.png'), _("Line"))
        self.draw_rect = self.g_editor_cmenu.addAction(QtGui.QIcon('share/rectangle32.png'), _("Rectangle"))
        self.draw_cut = self.g_editor_cmenu.addAction(QtGui.QIcon('share/cutpath32.png'), _("Cut"))
        self.g_editor_cmenu.addSeparator()
        self.draw_move = self.g_editor_cmenu.addAction(QtGui.QIcon('share/move32.png'), _("Move"))

        self.grb_editor_cmenu = self.popMenu.addMenu(QtGui.QIcon('share/draw32.png'), _("Gerber Editor"))
        self.grb_draw_pad = self.grb_editor_cmenu.addAction(QtGui.QIcon('share/aperture32.png'), _("Pad"))
        self.grb_draw_pad_array = self.grb_editor_cmenu.addAction(QtGui.QIcon('share/padarray32.png'), _("Pad Array"))
        self.grb_draw_track = self.grb_editor_cmenu.addAction(QtGui.QIcon('share/track32.png'), _("Track"))
        self.grb_draw_region = self.grb_editor_cmenu.addAction(QtGui.QIcon('share/polygon32.png'), _("Region"))

        self.e_editor_cmenu = self.popMenu.addMenu(QtGui.QIcon('share/drill32.png'), _("Exc Editor"))
        self.drill = self.e_editor_cmenu.addAction(QtGui.QIcon('share/drill32.png'), _("Add Drill"))
        self.drill_array = self.e_editor_cmenu.addAction(QtGui.QIcon('share/addarray32.png'), _("Add Drill Array"))

        self.popMenu.addSeparator()
        self.popmenu_copy = self.popMenu.addAction(QtGui.QIcon('share/copy32.png'), _("Copy"))
        self.popmenu_delete = self.popMenu.addAction(QtGui.QIcon('share/delete32.png'), _("Delete"))
        self.popmenu_edit = self.popMenu.addAction(QtGui.QIcon('share/edit32.png'), _("Edit"))
        self.popmenu_save = self.popMenu.addAction(QtGui.QIcon('share/floppy32.png'), _("Close Editor"))
        self.popmenu_save.setVisible(False)
        self.popMenu.addSeparator()

        self.popmenu_move = self.popMenu.addAction(QtGui.QIcon('share/move32.png'), _("Move"))
        self.popmenu_properties = self.popMenu.addAction(QtGui.QIcon('share/properties32.png'), _("Properties"))


        ################################## ##
        # ## Here we build the CNCJob Tab # ##
        ################################## ##
        self.cncjob_tab = QtWidgets.QWidget()
        self.cncjob_tab_layout = QtWidgets.QGridLayout(self.cncjob_tab)
        self.cncjob_tab_layout.setContentsMargins(2, 2, 2, 2)
        self.cncjob_tab.setLayout(self.cncjob_tab_layout)

        self.code_editor = FCTextAreaExtended()
        stylesheet = """
                        QTextEdit { selection-background-color:yellow;
                                    selection-color:black;
                        }
                     """

        self.code_editor.setStyleSheet(stylesheet)

        self.buttonPreview = QtWidgets.QPushButton(_('Print Preview'))
        self.buttonPrint = QtWidgets.QPushButton(_('Print Code'))
        self.buttonFind = QtWidgets.QPushButton(_('Find in Code'))
        self.buttonFind.setFixedWidth(100)
        self.buttonPreview.setFixedWidth(100)
        self.entryFind = FCEntry()
        self.entryFind.setMaximumWidth(200)
        self.buttonReplace = QtWidgets.QPushButton(_('Replace With'))
        self.buttonReplace.setFixedWidth(100)
        self.entryReplace = FCEntry()
        self.entryReplace.setMaximumWidth(200)
        self.sel_all_cb = QtWidgets.QCheckBox(_('All'))
        self.sel_all_cb.setToolTip(
            _("When checked it will replace all instances in the 'Find' box\n"
              "with the text in the 'Replace' box..")
        )
        self.buttonOpen = QtWidgets.QPushButton(_('Open Code'))
        self.buttonSave = QtWidgets.QPushButton(_('Save Code'))

        self.cncjob_tab_layout.addWidget(self.code_editor, 0, 0, 1, 5)

        cnc_tab_lay_1 = QtWidgets.QHBoxLayout()
        cnc_tab_lay_1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        cnc_tab_lay_1.addWidget(self.buttonFind)
        cnc_tab_lay_1.addWidget(self.entryFind)
        cnc_tab_lay_1.addWidget(self.buttonReplace)
        cnc_tab_lay_1.addWidget(self.entryReplace)
        cnc_tab_lay_1.addWidget(self.sel_all_cb)
        self.cncjob_tab_layout.addLayout(cnc_tab_lay_1, 1, 0, 1, 1, QtCore.Qt.AlignLeft)

        cnc_tab_lay_3 = QtWidgets.QHBoxLayout()
        cnc_tab_lay_3.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        cnc_tab_lay_3.addWidget(self.buttonPreview)
        cnc_tab_lay_3.addWidget(self.buttonPrint)
        self.cncjob_tab_layout.addLayout(cnc_tab_lay_3, 2, 0, 1, 1, QtCore.Qt.AlignLeft)

        cnc_tab_lay_4 = QtWidgets.QHBoxLayout()
        cnc_tab_lay_4.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        cnc_tab_lay_4.addWidget(self.buttonOpen)
        cnc_tab_lay_4.addWidget(self.buttonSave)
        self.cncjob_tab_layout.addLayout(cnc_tab_lay_4, 2, 4, 1, 1)

        ################################ ##
        # ## Build InfoBar is done here # ##
        ################################ ##
        self.infobar = self.statusBar()
        self.fcinfo = FlatCAMInfoBar()
        self.infobar.addWidget(self.fcinfo, stretch=1)

        self.rel_position_label = QtWidgets.QLabel(
            "<b>Dx</b>: 0.0000&nbsp;&nbsp;   <b>Dy</b>: 0.0000&nbsp;&nbsp;&nbsp;&nbsp;")
        self.rel_position_label.setMinimumWidth(110)
        self.rel_position_label.setToolTip(_("Relative neasurement.\nReference is last click position"))
        self.infobar.addWidget(self.rel_position_label)

        self.position_label = QtWidgets.QLabel(
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>X</b>: 0.0000&nbsp;&nbsp;   <b>Y</b>: 0.0000")
        self.position_label.setMinimumWidth(110)
        self.position_label.setToolTip(_("Absolute neasurement.\nReference is (X=0, Y= 0) position"))
        self.infobar.addWidget(self.position_label)

        self.units_label = QtWidgets.QLabel("[in]")
        self.units_label.setMargin(2)
        self.infobar.addWidget(self.units_label)

        # disabled
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        # infobar.addWidget(self.progress_bar)

        self.activity_view = FlatCAMActivityView()
        self.infobar.addWidget(self.activity_view)

        self.app_icon = QtGui.QIcon()
        self.app_icon.addFile('share/flatcam_icon16.png', QtCore.QSize(16, 16))
        self.app_icon.addFile('share/flatcam_icon24.png', QtCore.QSize(24, 24))
        self.app_icon.addFile('share/flatcam_icon32.png', QtCore.QSize(32, 32))
        self.app_icon.addFile('share/flatcam_icon48.png', QtCore.QSize(48, 48))
        self.app_icon.addFile('share/flatcam_icon128.png', QtCore.QSize(128, 128))
        self.app_icon.addFile('share/flatcam_icon256.png', QtCore.QSize(256, 256))
        self.setWindowIcon(self.app_icon)

        self.setGeometry(100, 100, 1024, 650)
        self.setWindowTitle('FlatCAM %s %s - %s' % (version, ('BETA' if beta else ''), platform.architecture()[0]))
        self.show()

        self.filename = ""
        self.units = ""
        self.setAcceptDrops(True)

        # # restore the Toolbar State from file
        # try:
        #     with open(self.app.data_path + '\gui_state.config', 'rb') as stream:
        #         self.restoreState(QtCore.QByteArray(stream.read()))
        #     log.debug("FlatCAMGUI.__init__() --> UI state restored.")
        # except IOError:
        #     log.debug("FlatCAMGUI.__init__() --> UI state not restored. IOError")
        #     pass

        # ################### ##
        # ## INITIALIZE GUI # ##
        # ################### ##

        self.grid_snap_btn.setCheckable(True)
        self.corner_snap_btn.setCheckable(True)
        self.update_obj_btn.setEnabled(False)
        # start with GRID activated
        self.grid_snap_btn.trigger()

        self.g_editor_cmenu.menuAction().setVisible(False)
        self.grb_editor_cmenu.menuAction().setVisible(False)
        self.e_editor_cmenu.menuAction().setVisible(False)

        self.general_defaults_form = GeneralPreferencesUI()
        self.gerber_defaults_form = GerberPreferencesUI()
        self.excellon_defaults_form = ExcellonPreferencesUI()
        self.geometry_defaults_form = GeometryPreferencesUI()
        self.cncjob_defaults_form = CNCJobPreferencesUI()
        self.tools_defaults_form = ToolsPreferencesUI()

        self.general_options_form = GeneralPreferencesUI()
        self.gerber_options_form = GerberPreferencesUI()
        self.excellon_options_form = ExcellonPreferencesUI()
        self.geometry_options_form = GeometryPreferencesUI()
        self.cncjob_options_form = CNCJobPreferencesUI()
        self.tools_options_form = ToolsPreferencesUI()

        QtWidgets.qApp.installEventFilter(self)

        # restore the Toolbar State from file
        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("saved_gui_state"):
            saved_gui_state = settings.value('saved_gui_state')
            self.restoreState(saved_gui_state)
            log.debug("FlatCAMGUI.__init__() --> UI state restored.")

        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("layout"):
            layout = settings.value('layout', type=str)
            if layout == 'standard':
                self.exc_edit_toolbar.setVisible(False)
                self.exc_edit_toolbar.setDisabled(True)
                self.geo_edit_toolbar.setVisible(False)
                self.geo_edit_toolbar.setDisabled(True)
                self.grb_edit_toolbar.setVisible(False)
                self.grb_edit_toolbar.setDisabled(True)

                self.corner_snap_btn.setVisible(False)
                self.snap_magnet.setVisible(False)
            elif layout == 'compact':
                self.exc_edit_toolbar.setDisabled(True)
                self.geo_edit_toolbar.setDisabled(True)
                self.grb_edit_toolbar.setDisabled(True)

                self.snap_magnet.setVisible(True)
                self.corner_snap_btn.setVisible(True)
                self.snap_magnet.setDisabled(True)
                self.corner_snap_btn.setDisabled(True)
            log.debug("FlatCAMGUI.__init__() --> UI layout restored from QSettings.")
        else:
            self.exc_edit_toolbar.setVisible(False)
            self.exc_edit_toolbar.setDisabled(True)
            self.geo_edit_toolbar.setVisible(False)
            self.geo_edit_toolbar.setDisabled(True)
            self.grb_edit_toolbar.setVisible(False)
            self.grb_edit_toolbar.setDisabled(True)

            self.corner_snap_btn.setVisible(False)
            self.snap_magnet.setVisible(False)
            settings.setValue('layout', "standard")

            # This will write the setting to the platform specific storage.
            del settings
            log.debug("FlatCAMGUI.__init__() --> UI layout restored from defaults. QSettings set to 'standard'")

    def eventFilter(self, obj, event):
        if self.general_defaults_form.general_app_group.toggle_tooltips_cb.get_value() is False:
            if event.type() == QtCore.QEvent.ToolTip:
                return True
            else:
                return False

        return False

    def populate_toolbars(self):

        # ## File Toolbar # ##
        self.file_open_gerber_btn = self.toolbarfile.addAction(QtGui.QIcon('share/flatcam_icon32.png'),
                                                               _("Open Gerber"))
        self.file_open_excellon_btn = self.toolbarfile.addAction(QtGui.QIcon('share/drill32.png'), _("Open Excellon"))
        self.toolbarfile.addSeparator()
        self.file_open_btn = self.toolbarfile.addAction(QtGui.QIcon('share/folder32.png'), _("Open project"))
        self.file_save_btn = self.toolbarfile.addAction(QtGui.QIcon('share/floppy32.png'), _("Save project"))

        # ## Edit Toolbar # ##
        self.newgeo_btn = self.toolbargeo.addAction(QtGui.QIcon('share/new_geo32_bis.png'), _("New Blank Geometry"))
        self.newexc_btn = self.toolbargeo.addAction(QtGui.QIcon('share/new_exc32.png'), _("New Blank Excellon"))
        self.toolbargeo.addSeparator()
        self.editgeo_btn = self.toolbargeo.addAction(QtGui.QIcon('share/edit32.png'), _("Editor"))
        self.update_obj_btn = self.toolbargeo.addAction(
            QtGui.QIcon('share/edit_ok32_bis.png'), _("Save Object and close the Editor")
        )

        self.toolbargeo.addSeparator()
        self.delete_btn = self.toolbargeo.addAction(QtGui.QIcon('share/cancel_edit32.png'), _("&Delete"))

        # ## View Toolbar # ##
        self.replot_btn = self.toolbarview.addAction(QtGui.QIcon('share/replot32.png'), _("&Replot"))
        self.clear_plot_btn = self.toolbarview.addAction(QtGui.QIcon('share/clear_plot32.png'), _("&Clear plot"))
        self.zoom_in_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_in32.png'), _("Zoom In"))
        self.zoom_out_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_out32.png'), _("Zoom Out"))
        self.zoom_fit_btn = self.toolbarview.addAction(QtGui.QIcon('share/zoom_fit32.png'), _("Zoom Fit"))

        # self.toolbarview.setVisible(False)

        # ## Shell Toolbar # ##
        self.shell_btn = self.toolbarshell.addAction(QtGui.QIcon('share/shell32.png'), _("&Command Line"))

        # ## Tools Toolbar # ##
        self.dblsided_btn = self.toolbartools.addAction(QtGui.QIcon('share/doubleside32.png'), _("2Sided Tool"))
        self.cutout_btn = self.toolbartools.addAction(QtGui.QIcon('share/cut16_bis.png'), _("&Cutout Tool"))
        self.ncc_btn = self.toolbartools.addAction(QtGui.QIcon('share/ncc16.png'), _("NCC Tool"))
        self.paint_btn = self.toolbartools.addAction(QtGui.QIcon('share/paint20_1.png'), _("Paint Tool"))
        self.toolbartools.addSeparator()

        self.panelize_btn = self.toolbartools.addAction(QtGui.QIcon('share/panel16.png'), _("Panel Tool"))
        self.film_btn = self.toolbartools.addAction(QtGui.QIcon('share/film16.png'), _("Film Tool"))
        self.solder_btn = self.toolbartools.addAction(QtGui.QIcon('share/solderpastebis32.png'),
                                                      _("SolderPaste Tool"))
        self.sub_btn = self.toolbartools.addAction(QtGui.QIcon('share/sub32.png'), _("Substract Tool"))

        self.toolbartools.addSeparator()

        self.calculators_btn = self.toolbartools.addAction(QtGui.QIcon('share/calculator24.png'),
                                                           _("Calculators Tool"))
        self.transform_btn = self.toolbartools.addAction(QtGui.QIcon('share/transform.png'), _("Transform Tool"))

        # ## Excellon Editor Toolbar # ##
        self.select_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select"))
        self.add_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/plus16.png'), _('Add Drill Hole'))
        self.add_drill_array_btn = self.exc_edit_toolbar.addAction(
            QtGui.QIcon('share/addarray16.png'), _('Add Drill Hole Array'))
        self.resize_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/resize16.png'), _('Resize Drill'))
        self.exc_edit_toolbar.addSeparator()

        self.copy_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _('Copy Drill'))
        self.delete_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'),
                                                                _("Delete Drill"))

        self.exc_edit_toolbar.addSeparator()
        self.move_drill_btn = self.exc_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move Drill"))

        # ## Geometry Editor Toolbar # ##
        self.geo_select_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select 'Esc'"))
        self.geo_add_circle_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/circle32.png'), _('Add Circle'))
        self.geo_add_arc_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/arc32.png'), _('Add Arc'))
        self.geo_add_rectangle_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/rectangle32.png'),
                                                                     _('Add Rectangle'))

        self.geo_edit_toolbar.addSeparator()
        self.geo_add_path_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/path32.png'), _('Add Path'))
        self.geo_add_polygon_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/polygon32.png'),
                                                                   _('Add Polygon'))
        self.geo_edit_toolbar.addSeparator()
        self.geo_add_text_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/text32.png'), _('Add Text'))
        self.geo_add_buffer_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/buffer16-2.png'),
                                                                  _('Add Buffer'))
        self.geo_add_paint_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/paint20_1.png'), _('Paint Shape'))
        self.geo_eraser_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/eraser26.png'), _('Eraser'))


        self.geo_edit_toolbar.addSeparator()
        self.geo_union_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/union32.png'), _('Polygon Union'))
        self.geo_intersection_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/intersection32.png'),
                                                               _('Polygon Intersection'))
        self.geo_subtract_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/subtract32.png'),
                                                                _('Polygon Subtraction'))

        self.geo_edit_toolbar.addSeparator()
        self.geo_cutpath_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/cutpath32.png'), _('Cut Path'))
        self.geo_copy_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _("Copy Objects"))
        self.geo_delete_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'),
                                                              _("Delete Shape"))
        self.geo_transform_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/transform.png'),
                                                                 _("Transformations"))

        self.geo_edit_toolbar.addSeparator()
        self.geo_move_btn = self.geo_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move Objects"))

        # ## Gerber Editor Toolbar # ##
        self.grb_select_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/pointer32.png'), _("Select"))
        self.grb_add_pad_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/aperture32.png'), _("Add Pad"))
        self.add_pad_ar_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/padarray32.png'), _('Add Pad Array'))
        self.grb_add_track_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/track32.png'), _("Add Track"))
        self.grb_add_region_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/polygon32.png'), _("Add Region"))
        self.grb_convert_poly_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/poligonize32.png'),
                                                                    _("Poligonize"))

        self.grb_add_semidisc_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/semidisc32.png'), _("SemiDisc"))
        self.grb_add_disc_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/disc32.png'), _("Disc"))
        self.grb_edit_toolbar.addSeparator()

        self.aperture_buffer_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/buffer16-2.png'), _('Buffer'))
        self.aperture_scale_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/scale32.png'), _('Scale'))
        self.aperture_eraser_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/eraser26.png'), _('Eraser'))

        self.grb_edit_toolbar.addSeparator()
        self.aperture_copy_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/copy32.png'), _("Copy"))
        self.aperture_delete_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/trash32.png'),
                                                                   _("Delete"))
        self.grb_transform_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/transform.png'),
                                                                 _("Transformations"))
        self.grb_edit_toolbar.addSeparator()
        self.aperture_move_btn = self.grb_edit_toolbar.addAction(QtGui.QIcon('share/move32.png'), _("Move"))

        # ## Snap Toolbar # ##
        # Snap GRID toolbar is always active to facilitate usage of measurements done on GRID
        # self.addToolBar(self.snap_toolbar)

        self.grid_snap_btn = self.snap_toolbar.addAction(QtGui.QIcon('share/grid32.png'), _('Snap to grid'))
        self.grid_gap_x_entry = FCEntry2()
        self.grid_gap_x_entry.setMaximumWidth(70)
        self.grid_gap_x_entry.setToolTip(_("Grid X snapping distance"))
        self.snap_toolbar.addWidget(self.grid_gap_x_entry)

        self.grid_gap_y_entry = FCEntry2()
        self.grid_gap_y_entry.setMaximumWidth(70)
        self.grid_gap_y_entry.setToolTip(_("Grid Y snapping distance"))
        self.snap_toolbar.addWidget(self.grid_gap_y_entry)

        self.grid_space_label = QtWidgets.QLabel("  ")
        self.snap_toolbar.addWidget(self.grid_space_label)
        self.grid_gap_link_cb = FCCheckBox()
        self.grid_gap_link_cb.setToolTip(_("When active, value on Grid_X\n"
                                         "is copied to the Grid_Y value."))
        self.snap_toolbar.addWidget(self.grid_gap_link_cb)

        self.ois_grid = OptionalInputSection(self.grid_gap_link_cb, [self.grid_gap_y_entry], logic=False)

        self.corner_snap_btn = self.snap_toolbar.addAction(QtGui.QIcon('share/corner32.png'), _('Snap to corner'))

        self.snap_max_dist_entry = FCEntry()
        self.snap_max_dist_entry.setMaximumWidth(70)
        self.snap_max_dist_entry.setToolTip(_("Max. magnet distance"))
        self.snap_magnet = self.snap_toolbar.addWidget(self.snap_max_dist_entry)

        self.grid_snap_btn.setCheckable(True)
        self.corner_snap_btn.setCheckable(True)
        self.update_obj_btn.setEnabled(False)
        # start with GRID activated
        self.grid_snap_btn.trigger()

        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("layout"):
            layout = settings.value('layout', type=str)
            if layout == 'standard':
                self.exc_edit_toolbar.setVisible(False)
                self.exc_edit_toolbar.setDisabled(True)
                self.geo_edit_toolbar.setVisible(False)
                self.geo_edit_toolbar.setDisabled(True)
                self.grb_edit_toolbar.setVisible(False)
                self.grb_edit_toolbar.setDisabled(True)

                self.corner_snap_btn.setVisible(False)
                self.snap_magnet.setVisible(False)
            elif layout == 'compact':
                self.exc_edit_toolbar.setVisible(True)
                self.exc_edit_toolbar.setDisabled(True)
                self.geo_edit_toolbar.setVisible(True)
                self.geo_edit_toolbar.setDisabled(True)
                self.grb_edit_toolbar.setVisible(True)
                self.grb_edit_toolbar.setDisabled(True)

                self.corner_snap_btn.setVisible(True)
                self.snap_magnet.setVisible(True)
                self.corner_snap_btn.setDisabled(True)
                self.snap_magnet.setDisabled(True)

    def keyPressEvent(self, event):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        active = self.app.collection.get_active()
        selected = self.app.collection.get_selected()

        # events out of the self.app.collection view (it's about Project Tab) are of type int
        if type(event) is int:
            key = event
        # events from the GUI are of type QKeyEvent
        elif type(event) == QtGui.QKeyEvent:
            key = event.key()
        # events from Vispy are of type KeyEvent
        else:
            key = event.key

        if self.app.call_source == 'app':
            if modifiers == QtCore.Qt.ControlModifier:
                if key == QtCore.Qt.Key_A:
                    self.app.on_selectall()

                if key == QtCore.Qt.Key_C:
                    self.app.on_copy_object()

                if key == QtCore.Qt.Key_E:
                    self.app.on_fileopenexcellon()

                if key == QtCore.Qt.Key_G:
                    self.app.on_fileopengerber()

                if key == QtCore.Qt.Key_N:
                    self.app.on_file_new_click()

                if key == QtCore.Qt.Key_M:
                    self.app.measurement_tool.run()

                if key == QtCore.Qt.Key_O:
                    self.app.on_file_openproject()

                if key == QtCore.Qt.Key_S:
                    self.app.on_file_saveproject()

                # Toggle Plot Area
                if key == QtCore.Qt.Key_F10 or key == 'F10':
                    self.app.on_toggle_plotarea()

                return
            elif modifiers == QtCore.Qt.ShiftModifier:

                # Copy Object Name
                if key == QtCore.Qt.Key_C:
                    self.app.on_copy_name()

                # Toggle Code Editor
                if key == QtCore.Qt.Key_E:
                    self.app.on_toggle_code_editor()

                # Toggle axis
                if key == QtCore.Qt.Key_G:
                    if self.app.toggle_axis is False:
                        self.app.plotcanvas.v_line.set_data(color=(0.70, 0.3, 0.3, 1.0))
                        self.app.plotcanvas.h_line.set_data(color=(0.70, 0.3, 0.3, 1.0))
                        self.app.plotcanvas.redraw()
                        self.app.toggle_axis = True
                    else:
                        self.app.plotcanvas.v_line.set_data(color=(0.0, 0.0, 0.0, 0.0))

                        self.app.plotcanvas.h_line.set_data(color=(0.0, 0.0, 0.0, 0.0))
                        self.app.plotcanvas.redraw()
                        self.app.toggle_axis = False

                # Open Preferences Window
                if key == QtCore.Qt.Key_P:
                    self.app.on_preferences()
                    return

                # Rotate Object by 90 degree CCW
                if key == QtCore.Qt.Key_R:
                    self.app.on_rotate(silent=True, preset=-float(self.app.defaults['tools_transform_rotate']))
                    return

                # Run a Script
                if key == QtCore.Qt.Key_S:
                    self.app.on_filerunscript()
                    return

                # Toggle Workspace
                if key == QtCore.Qt.Key_W:
                    self.app.on_workspace_menu()
                    return

                # Skew on X axis
                if key == QtCore.Qt.Key_X:
                    self.app.on_skewx()
                    return

                # Skew on Y axis
                if key == QtCore.Qt.Key_Y:
                    self.app.on_skewy()
                    return
            elif modifiers == QtCore.Qt.AltModifier:
                # Eanble all plots
                if key == Qt.Key_1:
                    self.app.enable_all_plots()

                # Disable all plots
                if key == Qt.Key_2:
                    self.app.disable_all_plots()

                # Disable all other plots
                if key == Qt.Key_3:
                    self.app.disable_other_plots()

                # Calculator Tool
                if key == QtCore.Qt.Key_C:
                    self.app.calculator_tool.run(toggle=True)

                # 2-Sided PCB Tool
                if key == QtCore.Qt.Key_D:
                    self.app.dblsidedtool.run(toggle=True)
                    return

                # Solder Paste Dispensing Tool
                if key == QtCore.Qt.Key_K:
                    self.app.paste_tool.run(toggle=True)
                    return

                # Film Tool
                if key == QtCore.Qt.Key_L:
                    self.app.film_tool.run(toggle=True)
                    return

                # Non-Copper Clear Tool
                if key == QtCore.Qt.Key_N:
                    self.app.ncclear_tool.run(toggle=True)
                    return

                # Paint Tool
                if key == QtCore.Qt.Key_P:
                    self.app.paint_tool.run(toggle=True)
                    return

                # Paint Tool
                if key == QtCore.Qt.Key_Q:
                    self.app.pdf_tool.run()
                    return

                # Transformation Tool
                if key == QtCore.Qt.Key_R:
                    self.app.transform_tool.run(toggle=True)
                    return

                # View Source Object Content
                if key == QtCore.Qt.Key_S:
                    self.app.on_view_source()
                    return

                # Cutout Tool
                if key == QtCore.Qt.Key_U:
                    self.app.cutout_tool.run(toggle=True)
                    return

                # Substract Tool
                if key == QtCore.Qt.Key_W:
                    self.app.sub_tool.run(toggle=True)
                    return

                # Panelize Tool
                if key == QtCore.Qt.Key_Z:
                    self.app.panelize_tool.run(toggle=True)
                    return

                # Toggle Fullscreen
                if key == QtCore.Qt.Key_F10 or key == 'F10':
                    self.app.on_fullscreen()
                    return
            elif modifiers == QtCore.Qt.NoModifier:
                # Open Manual
                if key == QtCore.Qt.Key_F1 or key == 'F1':
                    webbrowser.open(self.app.manual_url)

                # Show shortcut list
                if key == QtCore.Qt.Key_F3 or key == 'F3':
                    self.app.on_shortcut_list()

                # Open Video Help
                if key == QtCore.Qt.Key_F4 or key == 'F4':
                    webbrowser.open(self.app.video_url)

                # Switch to Project Tab
                if key == QtCore.Qt.Key_1:
                    self.app.on_select_tab('project')

                # Switch to Selected Tab
                if key == QtCore.Qt.Key_2:
                    self.app.on_select_tab('selected')

                # Switch to Tool Tab
                if key == QtCore.Qt.Key_3:
                    self.app.on_select_tab('tool')

                # Delete from PyQt
                # It's meant to make a difference between delete objects and delete tools in
                # Geometry Selected tool table
                if key == QtCore.Qt.Key_Delete:
                    self.app.on_delete_keypress()

                # Delete from canvas
                if key == 'Delete':
                    # Delete via the application to
                    # ensure cleanup of the GUI
                    if active:
                        active.app.on_delete()

                # Escape = Deselect All
                if key == QtCore.Qt.Key_Escape or key == 'Escape':
                    self.app.on_deselect_all()

                    # if in full screen, exit to normal view
                    self.showNormal()
                    self.app.restore_toolbar_view()
                    self.splitter_left.setVisible(True)
                    self.app.toggle_fscreen = False

                    # try to disconnect the slot from Set Origin
                    try:
                        self.app.plotcanvas.vis_disconnect('mouse_press', self.app.on_set_zero_click)
                    except:
                        pass
                    self.app.inform.emit("")

                # Space = Toggle Active/Inactive
                if key == QtCore.Qt.Key_Space:
                    for select in selected:
                        select.ui.plot_cb.toggle()
                    self.app.collection.update_view()
                    self.app.delete_selection_shape()

                # New Geometry
                if key == QtCore.Qt.Key_B:
                    self.app.new_gerber_object()

                # Copy Object Name
                if key == QtCore.Qt.Key_E:
                    self.app.object2editor()

                # Grid toggle
                if key == QtCore.Qt.Key_G:
                    self.app.ui.grid_snap_btn.trigger()

                # Jump to coords
                if key == QtCore.Qt.Key_J:
                    self.app.on_jump_to()

                # New Excellon
                if key == QtCore.Qt.Key_L:
                    self.app.new_excellon_object()

                # Move tool toggle
                if key == QtCore.Qt.Key_M:
                    self.app.move_tool.toggle()

                # New Geometry
                if key == QtCore.Qt.Key_N:
                    self.app.new_geometry_object()

                # Set Origin
                if key == QtCore.Qt.Key_O:
                    self.app.on_set_origin()
                    return

                # Properties Tool
                if key == QtCore.Qt.Key_P:
                    self.app.properties_tool.run()
                    return

                # Change Units
                if key == QtCore.Qt.Key_Q:
                    # if self.app.defaults["units"] == 'MM':
                    #     self.app.ui.general_defaults_form.general_app_group.units_radio.set_value("IN")
                    # else:
                    #     self.app.ui.general_defaults_form.general_app_group.units_radio.set_value("MM")
                    # self.app.on_toggle_units(no_pref=True)
                    self.app.on_toggle_units_click()

                # Rotate Object by 90 degree CW
                if key == QtCore.Qt.Key_R:
                    self.app.on_rotate(silent=True, preset=self.app.defaults['tools_transform_rotate'])

                # Shell toggle
                if key == QtCore.Qt.Key_S:
                    self.app.on_toggle_shell()

                # Add a Tool from shortcut
                if key == QtCore.Qt.Key_T:
                    self.app.on_tool_add_keypress()

                # Zoom Fit
                if key == QtCore.Qt.Key_V:
                    self.app.on_zoom_fit(None)

                # Mirror on X the selected object(s)
                if key == QtCore.Qt.Key_X:
                    self.app.on_flipx()

                # Mirror on Y the selected object(s)
                if key == QtCore.Qt.Key_Y:
                    self.app.on_flipy()

                # Zoom In
                if key == QtCore.Qt.Key_Equal:
                    self.app.plotcanvas.zoom(1 / self.app.defaults['global_zoom_ratio'], self.app.mouse)

                # Zoom Out
                if key == QtCore.Qt.Key_Minus:
                    self.app.plotcanvas.zoom(self.app.defaults['global_zoom_ratio'], self.app.mouse)

                # toggle display of Notebook area
                if key == QtCore.Qt.Key_QuoteLeft:
                    self.app.on_toggle_notebook()

                return
        elif self.app.call_source == 'geo_editor':
            if modifiers == QtCore.Qt.ControlModifier:
                # save (update) the current geometry and return to the App
                if key == QtCore.Qt.Key_S or key == 'S':
                    self.app.editor2object()
                    return

                # toggle the measurement tool
                if key == QtCore.Qt.Key_M or key == 'M':
                    self.app.measurement_tool.run()
                    return

                # Cut Action Tool
                if key == QtCore.Qt.Key_X or key == 'X':
                    if self.app.geo_editor.get_selected() is not None:
                        self.app.geo_editor.cutpath()
                    else:
                        msg = _('Please first select a geometry item to be cutted\n' \
                              'then select the geometry item that will be cutted\n' \
                              'out of the first item. In the end press ~X~ key or\n' \
                              'the toolbar button.')

                        messagebox = QtWidgets.QMessageBox()
                        messagebox.setText(msg)
                        messagebox.setWindowTitle(_("Warning"))
                        messagebox.setWindowIcon(QtGui.QIcon('share/warning.png'))
                        messagebox.setStandardButtons(QtWidgets.QMessageBox.Ok)
                        messagebox.setDefaultButton(QtWidgets.QMessageBox.Ok)
                        messagebox.exec_()
                    return

            elif modifiers == QtCore.Qt.ShiftModifier:
                # Skew on X axis
                if key == QtCore.Qt.Key_X or key == 'X':
                    self.app.geo_editor.transform_tool.on_skewx_key()
                    return

                # Skew on Y axis
                if key == QtCore.Qt.Key_Y or key == 'Y':
                    self.app.geo_editor.transform_tool.on_skewy_key()
                    return
            elif modifiers == QtCore.Qt.AltModifier:

                # Transformation Tool
                if key == QtCore.Qt.Key_R or key == 'R':
                    self.app.geo_editor.select_tool('transform')
                    return

                # Offset on X axis
                if key == QtCore.Qt.Key_X or key == 'X':
                    self.app.geo_editor.transform_tool.on_offx_key()
                    return

                # Offset on Y axis
                if key == QtCore.Qt.Key_Y or key == 'Y':
                    self.app.geo_editor.transform_tool.on_offy_key()
                    return
            elif modifiers == QtCore.Qt.NoModifier:
                # toggle display of Notebook area
                if key == QtCore.Qt.Key_QuoteLeft or key == '`':
                    self.app.on_toggle_notebook()

                # Finish the current action. Use with tools that do not
                # complete automatically, like a polygon or path.
                if key == QtCore.Qt.Key_Enter or key == 'Enter':
                    if isinstance(self.app.geo_editor.active_tool, FCShapeTool):
                        if self.app.geo_editor.active_tool.name == 'rotate':
                            self.app.geo_editor.active_tool.make()

                            if self.app.geo_editor.active_tool.complete:
                                self.app.geo_editor.on_shape_complete()
                                self.app.inform.emit(_("[success] Done."))
                            # automatically make the selection tool active after completing current action
                            self.app.geo_editor.select_tool('select')
                            return
                        else:
                            self.app.geo_editor.active_tool.click(
                                self.app.geo_editor.snap(self.app.geo_editor.x, self.app.geo_editor.y))

                            self.app.geo_editor.active_tool.make()

                            if self.app.geo_editor.active_tool.complete:
                                self.app.geo_editor.on_shape_complete()
                                self.app.inform.emit(_("[success] Done."))
                            # automatically make the selection tool active after completing current action
                            self.app.geo_editor.select_tool('select')

                # Abort the current action
                if key == QtCore.Qt.Key_Escape or key == 'Escape':
                    # TODO: ...?
                    # self.on_tool_select("select")
                    self.app.inform.emit(_("[WARNING_NOTCL] Cancelled."))

                    self.app.geo_editor.delete_utility_geometry()

                    # deselect any shape that might be selected
                    self.app.geo_editor.selected = []

                    self.app.geo_editor.replot()
                    self.app.geo_editor.select_tool('select')

                    # hide the notebook
                    self.app.ui.splitter.setSizes([0, 1])
                    return

                # Delete selected object
                if key == QtCore.Qt.Key_Delete or key == 'Delete':
                    self.app.geo_editor.delete_selected()
                    self.app.geo_editor.replot()

                # Rotate
                if key == QtCore.Qt.Key_Space or key == 'Space':
                    self.app.geo_editor.transform_tool.on_rotate_key()

                if key == QtCore.Qt.Key_Minus or key == '-':
                    self.app.plotcanvas.zoom(1 / self.app.defaults['global_zoom_ratio'],
                                             [self.app.geo_editor.snap_x, self.app.geo_editor.snap_y])

                if key == QtCore.Qt.Key_Equal or key == '=':
                    self.app.plotcanvas.zoom(self.app.defaults['global_zoom_ratio'],
                                             [self.app.geo_editor.snap_x, self.app.geo_editor.snap_y])

                # Switch to Project Tab
                if key == QtCore.Qt.Key_1 or key == '1':
                    self.app.on_select_tab('project')

                # Switch to Selected Tab
                if key == QtCore.Qt.Key_2 or key == '2':
                    self.app.on_select_tab('selected')

                # Switch to Tool Tab
                if key == QtCore.Qt.Key_3 or key == '3':
                    self.app.on_select_tab('tool')

                if self.app.geo_editor.active_tool is not None and self.geo_select_btn.isChecked() == False:
                    response = self.app.geo_editor.active_tool.on_key(key=key)
                    if response is not None:
                        self.app.inform.emit(response)
                else:
                    # Arc Tool
                    if key == QtCore.Qt.Key_A or key == 'A':
                        self.app.geo_editor.select_tool('arc')

                    # Buffer
                    if key == QtCore.Qt.Key_B or key == 'B':
                        self.app.geo_editor.select_tool('buffer')

                    # Copy
                    if key == QtCore.Qt.Key_C or key == 'C':
                        self.app.geo_editor.on_copy_click()

                    # Substract Tool
                    if key == QtCore.Qt.Key_E or key == 'E':
                        if self.app.geo_editor.get_selected() is not None:
                            self.app.geo_editor.intersection()
                        else:
                            msg = _("Please select geometry items \n" \
                                  "on which to perform Intersection Tool.")

                            messagebox = QtWidgets.QMessageBox()
                            messagebox.setText(msg)
                            messagebox.setWindowTitle(_("Warning"))
                            messagebox.setWindowIcon(QtGui.QIcon('share/warning.png'))
                            messagebox.setStandardButtons(QtWidgets.QMessageBox.Ok)
                            messagebox.setDefaultButton(QtWidgets.QMessageBox.Ok)
                            messagebox.exec_()

                    # Grid Snap
                    if key == QtCore.Qt.Key_G or key == 'G':
                        self.app.ui.grid_snap_btn.trigger()

                        # make sure that the cursor shape is enabled/disabled, too
                        if self.app.geo_editor.options['grid_snap'] is True:
                            self.app.app_cursor.enabled = True
                        else:
                            self.app.app_cursor.enabled = False

                    # Paint
                    if key == QtCore.Qt.Key_I or key == 'I':
                        self.app.geo_editor.select_tool('paint')

                    # Jump to coords
                    if key == QtCore.Qt.Key_J or key == 'J':
                        self.app.on_jump_to()

                    # Corner Snap
                    if key == QtCore.Qt.Key_K or key == 'K':
                        self.app.geo_editor.on_corner_snap()

                    # Move
                    if key == QtCore.Qt.Key_M or key == 'M':
                        self.app.geo_editor.on_move_click()

                    # Polygon Tool
                    if key == QtCore.Qt.Key_N or key == 'N':
                        self.app.geo_editor.select_tool('polygon')

                    # Circle Tool
                    if key == QtCore.Qt.Key_O or key == 'O':
                        self.app.geo_editor.select_tool('circle')

                    # Path Tool
                    if key == QtCore.Qt.Key_P or key == 'P':
                        self.app.geo_editor.select_tool('path')

                    # Rectangle Tool
                    if key == QtCore.Qt.Key_R or key == 'R':
                        self.app.geo_editor.select_tool('rectangle')

                    # Substract Tool
                    if key == QtCore.Qt.Key_S or key == 'S':
                        if self.app.geo_editor.get_selected() is not None:
                            self.app.geo_editor.subtract()
                        else:
                            msg = _(
                                "Please select geometry items \n"
                                "on which to perform Substraction Tool.")

                            messagebox = QtWidgets.QMessageBox()
                            messagebox.setText(msg)
                            messagebox.setWindowTitle(_("Warning"))
                            messagebox.setWindowIcon(QtGui.QIcon('share/warning.png'))
                            messagebox.setStandardButtons(QtWidgets.QMessageBox.Ok)
                            messagebox.setDefaultButton(QtWidgets.QMessageBox.Ok)
                            messagebox.exec_()

                    # Add Text Tool
                    if key == QtCore.Qt.Key_T or key == 'T':
                        self.app.geo_editor.select_tool('text')

                    # Substract Tool
                    if key == QtCore.Qt.Key_U or key == 'U':
                        if self.app.geo_editor.get_selected() is not None:
                            self.app.geo_editor.union()
                        else:
                            msg = _("Please select geometry items \n"
                                  "on which to perform union.")

                            messagebox = QtWidgets.QMessageBox()
                            messagebox.setText(msg)
                            messagebox.setWindowTitle(_("Warning"))
                            messagebox.setWindowIcon(QtGui.QIcon('share/warning.png'))
                            messagebox.setStandardButtons(QtWidgets.QMessageBox.Ok)
                            messagebox.setDefaultButton(QtWidgets.QMessageBox.Ok)
                            messagebox.exec_()

                    if key == QtCore.Qt.Key_V or key == 'V':
                        self.app.on_zoom_fit(None)

                    # Flip on X axis
                    if key == QtCore.Qt.Key_X or key == 'X':
                        self.app.geo_editor.transform_tool.on_flipx()
                        return

                    # Flip on Y axis
                    if key == QtCore.Qt.Key_Y or key == 'Y':
                        self.app.geo_editor.transform_tool.on_flipy()
                        return

                # Show Shortcut list
                if key == 'F3':
                    self.app.on_shortcut_list()
        elif self.app.call_source == 'grb_editor':
            if modifiers == QtCore.Qt.ControlModifier:
                # save (update) the current geometry and return to the App
                if key == QtCore.Qt.Key_S or key == 'S':
                    self.app.editor2object()
                    return

                # toggle the measurement tool
                if key == QtCore.Qt.Key_M or key == 'M':
                    self.app.measurement_tool.run()
                    return

            elif modifiers == QtCore.Qt.ShiftModifier:
                pass
            elif modifiers == QtCore.Qt.AltModifier:
                # Poligonize Tool
                if key == QtCore.Qt.Key_N or key == 'N':
                    self.app.grb_editor.on_poligonize()
                    return

                # Transformation Tool
                if key == QtCore.Qt.Key_R or key == 'R':
                    self.app.grb_editor.on_transform()
                    return
            elif modifiers == QtCore.Qt.NoModifier:
                # Abort the current action
                if key == QtCore.Qt.Key_Escape or key == 'Escape':
                    # self.on_tool_select("select")
                    self.app.inform.emit(_("[WARNING_NOTCL] Cancelled."))

                    self.app.grb_editor.delete_utility_geometry()

                    # self.app.grb_editor.plot_all()
                    self.app.grb_editor.active_tool.clean_up()
                    self.app.grb_editor.select_tool('select')
                    return

                # Delete selected object if delete key event comes out of canvas
                if key == 'Delete':
                    self.app.grb_editor.launched_from_shortcuts = True
                    if self.app.grb_editor.selected:
                        self.app.grb_editor.delete_selected()
                        self.app.grb_editor.plot_all()
                    else:
                        self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to delete."))
                    return

                # Delete aperture in apertures table if delete key event comes from the Selected Tab
                if key == QtCore.Qt.Key_Delete:
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.grb_editor.on_aperture_delete()
                    return

                if key == QtCore.Qt.Key_Minus or key == '-':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.plotcanvas.zoom(1 / self.app.defaults['global_zoom_ratio'],
                                             [self.app.grb_editor.snap_x, self.app.grb_editor.snap_y])
                    return

                if key == QtCore.Qt.Key_Equal or key == '=':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.plotcanvas.zoom(self.app.defaults['global_zoom_ratio'],
                                             [self.app.grb_editor.snap_x, self.app.grb_editor.snap_y])
                    return

                # toggle display of Notebook area
                if key == QtCore.Qt.Key_QuoteLeft or key == '`':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.on_toggle_notebook()
                    return

                # Rotate
                if key == QtCore.Qt.Key_Space or key == 'Space':
                    self.app.grb_editor.transform_tool.on_rotate_key()

                # Switch to Project Tab
                if key == QtCore.Qt.Key_1 or key == '1':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('project')
                    return

                # Switch to Selected Tab
                if key == QtCore.Qt.Key_2 or key == '2':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('selected')
                    return

                # Switch to Tool Tab
                if key == QtCore.Qt.Key_3 or key == '3':
                    self.app.grb_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('tool')
                    return

                # we do this so we can reuse the following keys while inside a Tool
                # the above keys are general enough so were left outside
                if self.app.grb_editor.active_tool is not None and self.grb_select_btn.isChecked() is False:
                    response = self.app.grb_editor.active_tool.on_key(key=key)
                    if response is not None:
                        self.app.inform.emit(response)
                else:
                    # Add Array of pads
                    if key == QtCore.Qt.Key_A or key == 'A':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.inform.emit("Click on target point.")
                        self.app.ui.add_pad_ar_btn.setChecked(True)

                        self.app.grb_editor.x = self.app.mouse[0]
                        self.app.grb_editor.y = self.app.mouse[1]

                        self.app.grb_editor.select_tool('array')
                        return

                    # Scale Tool
                    if key == QtCore.Qt.Key_B or key == 'B':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.grb_editor.select_tool('buffer')
                        return

                    # Copy
                    if key == QtCore.Qt.Key_C or key == 'C':
                        self.app.grb_editor.launched_from_shortcuts = True
                        if self.app.grb_editor.selected:
                            self.app.inform.emit(_("Click on target point."))
                            self.app.ui.aperture_copy_btn.setChecked(True)
                            self.app.grb_editor.on_tool_select('copy')
                            self.app.grb_editor.active_tool.set_origin(
                                (self.app.grb_editor.snap_x, self.app.grb_editor.snap_y))
                        else:
                            self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to copy."))
                        return

                    # Add Disc Tool
                    if key == QtCore.Qt.Key_D or key == 'D':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.grb_editor.select_tool('disc')
                        return

                    # Add SemiDisc Tool
                    if key == QtCore.Qt.Key_E or key == 'E':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.grb_editor.select_tool('semidisc')
                        return

                    # Grid Snap
                    if key == QtCore.Qt.Key_G or key == 'G':
                        self.app.grb_editor.launched_from_shortcuts = True
                        # make sure that the cursor shape is enabled/disabled, too
                        if self.app.grb_editor.options['grid_snap'] is True:
                            self.app.app_cursor.enabled = False
                        else:
                            self.app.app_cursor.enabled = True
                        self.app.ui.grid_snap_btn.trigger()
                        return

                    # Jump to coords
                    if key == QtCore.Qt.Key_J or key == 'J':
                        self.app.on_jump_to()

                    # Corner Snap
                    if key == QtCore.Qt.Key_K or key == 'K':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.ui.corner_snap_btn.trigger()
                        return

                    # Move
                    if key == QtCore.Qt.Key_M or key == 'M':
                        self.app.grb_editor.launched_from_shortcuts = True
                        if self.app.grb_editor.selected:
                            self.app.inform.emit(_("Click on target point."))
                            self.app.ui.aperture_move_btn.setChecked(True)
                            self.app.grb_editor.on_tool_select('move')
                            self.app.grb_editor.active_tool.set_origin(
                                (self.app.grb_editor.snap_x, self.app.grb_editor.snap_y))
                        else:
                            self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to move."))
                        return

                    # Add Region Tool
                    if key == QtCore.Qt.Key_N or key == 'N':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.grb_editor.select_tool('region')
                        return

                    # Add Pad Tool
                    if key == QtCore.Qt.Key_P or key == 'P':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.inform.emit(_("Click on target point."))
                        self.app.ui.add_pad_ar_btn.setChecked(True)

                        self.app.grb_editor.x = self.app.mouse[0]
                        self.app.grb_editor.y = self.app.mouse[1]

                        self.app.grb_editor.select_tool('pad')
                        return

                    # Scale Tool
                    if key == QtCore.Qt.Key_S or key == 'S':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.grb_editor.select_tool('scale')
                        return

                    # Add Track
                    if key == QtCore.Qt.Key_T or key == 'T':
                        self.app.grb_editor.launched_from_shortcuts = True
                        # ## Current application units in Upper Case
                        self.app.grb_editor.select_tool('track')
                        return

                    # Zoom Fit
                    if key == QtCore.Qt.Key_V or key == 'V':
                        self.app.grb_editor.launched_from_shortcuts = True
                        self.app.on_zoom_fit(None)
                        return

                # Show Shortcut list
                if key == QtCore.Qt.Key_F3 or key == 'F3':
                    self.app.on_shortcut_list()
                    return
        elif self.app.call_source == 'exc_editor':
            if modifiers == QtCore.Qt.ControlModifier:
                # save (update) the current geometry and return to the App
                if key == QtCore.Qt.Key_S or key == 'S':
                    self.app.editor2object()
                    return

                # toggle the measurement tool
                if key == QtCore.Qt.Key_M or key == 'M':
                    self.app.measurement_tool.run()
                    return

            elif modifiers == QtCore.Qt.ShiftModifier:
                pass
            elif modifiers == QtCore.Qt.AltModifier:
                pass
            elif modifiers == QtCore.Qt.NoModifier:
                # Abort the current action
                if key == QtCore.Qt.Key_Escape or key == 'Escape':
                    # TODO: ...?
                    # self.on_tool_select("select")
                    self.app.inform.emit(_("[WARNING_NOTCL] Cancelled."))

                    self.app.exc_editor.delete_utility_geometry()

                    self.app.exc_editor.replot()
                    # self.select_btn.setChecked(True)
                    # self.on_tool_select('select')
                    self.app.exc_editor.select_tool('drill_select')
                    return

                # Delete selected object if delete key event comes out of canvas
                if key == 'Delete':
                    self.app.exc_editor.launched_from_shortcuts = True
                    if self.app.exc_editor.selected:
                        self.app.exc_editor.delete_selected()
                        self.app.exc_editor.replot()
                    else:
                        self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to delete."))
                    return

                # Delete tools in tools table if delete key event comes from the Selected Tab
                if key == QtCore.Qt.Key_Delete:
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.exc_editor.on_tool_delete()
                    return

                if key == QtCore.Qt.Key_Minus or key == '-':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.plotcanvas.zoom(1 / self.app.defaults['global_zoom_ratio'],
                                             [self.app.exc_editor.snap_x, self.app.exc_editor.snap_y])
                    return

                if key == QtCore.Qt.Key_Equal or key == '=':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.plotcanvas.zoom(self.app.defaults['global_zoom_ratio'],
                                             [self.app.exc_editor.snap_x, self.app.exc_editor.snap_y])
                    return

                # toggle display of Notebook area
                if key == QtCore.Qt.Key_QuoteLeft or key == '`':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.on_toggle_notebook()
                    return

                # Switch to Project Tab
                if key == QtCore.Qt.Key_1 or key == '1':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('project')
                    return

                # Switch to Selected Tab
                if key == QtCore.Qt.Key_2 or key == '2':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('selected')
                    return

                # Switch to Tool Tab
                if key == QtCore.Qt.Key_3 or key == '3':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.on_select_tab('tool')
                    return

                # Add Array of Drill Hole Tool
                if key == QtCore.Qt.Key_A or key == 'A':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.inform.emit("Click on target point.")
                    self.app.ui.add_drill_array_btn.setChecked(True)

                    self.app.exc_editor.x = self.app.mouse[0]
                    self.app.exc_editor.y = self.app.mouse[1]

                    self.app.exc_editor.select_tool('drill_array')
                    return

                # Copy
                if key == QtCore.Qt.Key_C or key == 'C':
                    self.app.exc_editor.launched_from_shortcuts = True
                    if self.app.exc_editor.selected:
                        self.app.inform.emit(_("Click on target point."))
                        self.app.ui.copy_drill_btn.setChecked(True)
                        self.app.exc_editor.on_tool_select('drill_copy')
                        self.app.exc_editor.active_tool.set_origin(
                            (self.app.exc_editor.snap_x, self.app.exc_editor.snap_y))
                    else:
                        self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to copy."))
                    return

                # Add Drill Hole Tool
                if key == QtCore.Qt.Key_D or key == 'D':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.inform.emit(_("Click on target point."))
                    self.app.ui.add_drill_btn.setChecked(True)

                    self.app.exc_editor.x = self.app.mouse[0]
                    self.app.exc_editor.y = self.app.mouse[1]

                    self.app.exc_editor.select_tool('drill_add')
                    return

                # Grid Snap
                if key == QtCore.Qt.Key_G or key == 'G':
                    self.app.exc_editor.launched_from_shortcuts = True
                    # make sure that the cursor shape is enabled/disabled, too
                    if self.app.exc_editor.options['grid_snap'] is True:
                        self.app.app_cursor.enabled = False
                    else:
                        self.app.app_cursor.enabled = True
                    self.app.ui.grid_snap_btn.trigger()
                    return

                # Jump to coords
                if key == QtCore.Qt.Key_J or key == 'J':
                    self.app.on_jump_to()

                # Corner Snap
                if key == QtCore.Qt.Key_K or key == 'K':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.ui.corner_snap_btn.trigger()
                    return

                # Move
                if key == QtCore.Qt.Key_M or key == 'M':
                    self.app.exc_editor.launched_from_shortcuts = True
                    if self.app.exc_editor.selected:
                        self.app.inform.emit(_("Click on target point."))
                        self.app.ui.move_drill_btn.setChecked(True)
                        self.app.exc_editor.on_tool_select('drill_move')
                        self.app.exc_editor.active_tool.set_origin(
                            (self.app.exc_editor.snap_x, self.app.exc_editor.snap_y))
                    else:
                        self.app.inform.emit(_("[WARNING_NOTCL] Cancelled. Nothing selected to move."))
                    return

                # Resize Tool
                if key == QtCore.Qt.Key_R or key == 'R':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.exc_editor.select_tool('drill_resize')
                    return

                # Add Tool
                if key == QtCore.Qt.Key_T or key == 'T':
                    self.app.exc_editor.launched_from_shortcuts = True
                    # ## Current application units in Upper Case
                    self.units = self.general_defaults_form.general_app_group.units_radio.get_value().upper()
                    tool_add_popup = FCInputDialog(title=_("New Tool ..."),
                                                   text=_('Enter a Tool Diameter:'),
                                                   min=0.0000, max=99.9999, decimals=4)
                    tool_add_popup.setWindowIcon(QtGui.QIcon('share/letter_t_32.png'))

                    val, ok = tool_add_popup.get_value()
                    if ok:
                        self.app.exc_editor.on_tool_add(tooldia=val)
                        self.app.inform.emit(
                            _("[success] Added new tool with dia: {dia} {units}").format(dia='%.4f' % float(val),
                                                                                         units=str(self.units)))
                    else:
                        self.app.inform.emit(
                            _("[WARNING_NOTCL] Adding Tool cancelled ..."))
                    return

                # Zoom Fit
                if key == QtCore.Qt.Key_V or key == 'V':
                    self.app.exc_editor.launched_from_shortcuts = True
                    self.app.on_zoom_fit(None)
                    return

                # Propagate to tool
                response = None
                if self.app.exc_editor.active_tool is not None:
                    response = self.app.exc_editor.active_tool.on_key(key=key)
                if response is not None:
                    self.app.inform.emit(response)

                # Show Shortcut list
                if key == QtCore.Qt.Key_F3 or key == 'F3':
                    self.app.on_shortcut_list()
                    return
        elif self.app.call_source == 'measurement':
            if modifiers == QtCore.Qt.ControlModifier:
                pass
            elif modifiers == QtCore.Qt.AltModifier:
                pass
            elif modifiers == QtCore.Qt.ShiftModifier:
                pass
            elif modifiers == QtCore.Qt.NoModifier:
                if key == QtCore.Qt.Key_Escape or key == 'Escape':
                    # abort the measurement action
                    self.app.measurement_tool.deactivate_measure_tool()
                    self.app.inform.emit(_("Measurement Tool exit..."))
                    return

                if key == QtCore.Qt.Key_G or key == 'G':
                    self.app.ui.grid_snap_btn.trigger()
                    return

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                self.filename = str(url.toLocalFile())

                if self.filename == "":
                    self.app.inform.emit("Open cancelled.")
                else:
                    extension = self.filename.lower().rpartition('.')[-1]

                    if extension in self.app.grb_list:
                        self.app.worker_task.emit({'fcn': self.app.open_gerber,
                                                   'params': [self.filename]})
                    else:
                        event.ignore()

                    if extension in self.app.exc_list:
                        self.app.worker_task.emit({'fcn': self.app.open_excellon,
                                                   'params': [self.filename]})
                    else:
                        event.ignore()

                    if extension in self.app.gcode_list:
                        self.app.worker_task.emit({'fcn': self.app.open_gcode,
                                                   'params': [self.filename]})
                    else:
                        event.ignore()

                    if extension in self.app.svg_list:
                        object_type = 'geometry'
                        self.app.worker_task.emit({'fcn': self.app.import_svg,
                                                   'params': [self.filename, object_type, None]})

                    if extension in self.app.dxf_list:
                        object_type = 'geometry'
                        self.app.worker_task.emit({'fcn': self.app.import_dxf,
                                                   'params': [self.filename, object_type, None]})

                    if extension in self.app.pdf_list:
                        self.app.pdf_tool.periodic_check(1000)
                        self.app.worker_task.emit({'fcn': self.app.pdf_tool.open_pdf,
                                                   'params': [self.filename]})

                    if extension in self.app.prj_list:
                        # self.app.open_project() is not Thread Safe
                        self.app.open_project(self.filename)
                    else:
                        event.ignore()
        else:
            event.ignore()

    def closeEvent(self, event):
        if self.app.save_in_progress:
            self.app.inform.emit(_("[WARNING_NOTCL] Application is saving the project. Please wait ..."))
        else:
            grect = self.geometry()

            # self.splitter.sizes()[0] is actually the size of the "notebook"
            if not self.isMaximized():
                self.geom_update.emit(grect.x(), grect.y(), grect.width(), grect.height(), self.splitter.sizes()[0])

            self.final_save.emit()
        event.ignore()


class GeneralPreferencesUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.general_app_group = GeneralAppPrefGroupUI()
        self.general_app_group.setFixedWidth(280)

        self.general_gui_group = GeneralGUIPrefGroupUI()
        self.general_gui_group.setFixedWidth(250)

        self.general_gui_set_group = GeneralGUISetGroupUI()
        self.general_gui_set_group.setFixedWidth(250)

        self.layout.addWidget(self.general_app_group)
        self.layout.addWidget(self.general_gui_group)
        self.layout.addWidget(self.general_gui_set_group)

        self.layout.addStretch()


class GerberPreferencesUI(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.gerber_gen_group = GerberGenPrefGroupUI()
        self.gerber_gen_group.setFixedWidth(250)
        self.gerber_opt_group = GerberOptPrefGroupUI()
        self.gerber_opt_group.setFixedWidth(230)
        self.gerber_exp_group = GerberExpPrefGroupUI()
        self.gerber_exp_group.setFixedWidth(230)
        self.gerber_adv_opt_group = GerberAdvOptPrefGroupUI()
        self.gerber_adv_opt_group.setFixedWidth(200)
        self.gerber_editor_group = GerberEditorPrefGroupUI()
        self.gerber_editor_group.setFixedWidth(200)

        self.vlay = QtWidgets.QVBoxLayout()
        self.vlay.addWidget(self.gerber_opt_group)
        self.vlay.addWidget(self.gerber_exp_group)

        self.layout.addWidget(self.gerber_gen_group)
        self.layout.addLayout(self.vlay)
        self.layout.addWidget(self.gerber_adv_opt_group)
        self.layout.addWidget(self.gerber_editor_group)

        self.layout.addStretch()


class ExcellonPreferencesUI(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.excellon_gen_group = ExcellonGenPrefGroupUI()
        self.excellon_gen_group.setFixedWidth(220)
        self.excellon_opt_group = ExcellonOptPrefGroupUI()
        self.excellon_opt_group.setFixedWidth(290)
        self.excellon_exp_group = ExcellonExpPrefGroupUI()
        self.excellon_exp_group.setFixedWidth(250)
        self.excellon_adv_opt_group = ExcellonAdvOptPrefGroupUI()
        self.excellon_adv_opt_group.setFixedWidth(250)
        self.excellon_editor_group = ExcellonEditorPrefGroupUI()
        self.excellon_editor_group.setFixedWidth(260)

        self.vlay = QtWidgets.QVBoxLayout()
        self.vlay.addWidget(self.excellon_opt_group)
        self.vlay.addWidget(self.excellon_exp_group)

        self.layout.addWidget(self.excellon_gen_group)
        self.layout.addLayout(self.vlay)
        self.layout.addWidget(self.excellon_adv_opt_group)
        self.layout.addWidget(self.excellon_editor_group)

        self.layout.addStretch()


class GeometryPreferencesUI(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.geometry_gen_group = GeometryGenPrefGroupUI()
        self.geometry_gen_group.setFixedWidth(220)
        self.geometry_opt_group = GeometryOptPrefGroupUI()
        self.geometry_opt_group.setFixedWidth(300)
        self.geometry_adv_opt_group = GeometryAdvOptPrefGroupUI()
        self.geometry_adv_opt_group.setFixedWidth(270)
        self.geometry_editor_group = GeometryEditorPrefGroupUI()
        self.geometry_editor_group.setFixedWidth(250)

        self.layout.addWidget(self.geometry_gen_group)
        self.layout.addWidget(self.geometry_opt_group)
        self.layout.addWidget(self.geometry_adv_opt_group)
        self.layout.addWidget(self.geometry_editor_group)

        self.layout.addStretch()


class ToolsPreferencesUI(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.tools_ncc_group = ToolsNCCPrefGroupUI()
        self.tools_ncc_group.setMinimumWidth(200)
        self.tools_paint_group = ToolsPaintPrefGroupUI()
        self.tools_paint_group.setMinimumWidth(200)

        self.tools_cutout_group = ToolsCutoutPrefGroupUI()
        self.tools_cutout_group.setMinimumWidth(220)

        self.tools_2sided_group = Tools2sidedPrefGroupUI()
        self.tools_2sided_group.setMinimumWidth(220)

        self.tools_film_group = ToolsFilmPrefGroupUI()
        self.tools_film_group.setMinimumWidth(220)

        self.tools_panelize_group = ToolsPanelizePrefGroupUI()
        self.tools_panelize_group.setMinimumWidth(220)

        self.tools_calculators_group = ToolsCalculatorsPrefGroupUI()
        self.tools_calculators_group.setMinimumWidth(220)

        self.tools_transform_group = ToolsTransformPrefGroupUI()
        self.tools_transform_group.setMinimumWidth(200)

        self.tools_solderpaste_group = ToolsSolderpastePrefGroupUI()
        self.tools_solderpaste_group.setMinimumWidth(200)

        self.vlay = QtWidgets.QVBoxLayout()
        self.vlay.addWidget(self.tools_ncc_group)
        self.vlay.addWidget(self.tools_paint_group)
        self.vlay.addWidget(self.tools_film_group)

        self.vlay1 = QtWidgets.QVBoxLayout()
        self.vlay1.addWidget(self.tools_cutout_group)
        self.vlay1.addWidget(self.tools_transform_group)
        self.vlay1.addWidget(self.tools_2sided_group)

        self.vlay2 = QtWidgets.QVBoxLayout()
        self.vlay2.addWidget(self.tools_panelize_group)
        self.vlay2.addWidget(self.tools_calculators_group)

        self.vlay3 = QtWidgets.QVBoxLayout()
        self.vlay3.addWidget(self.tools_solderpaste_group)

        self.layout.addLayout(self.vlay)
        self.layout.addLayout(self.vlay1)
        self.layout.addLayout(self.vlay2)
        self.layout.addLayout(self.vlay3)

        self.layout.addStretch()


class CNCJobPreferencesUI(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)

        self.cncjob_gen_group = CNCJobGenPrefGroupUI()
        self.cncjob_gen_group.setFixedWidth(320)
        self.cncjob_opt_group = CNCJobOptPrefGroupUI()
        self.cncjob_opt_group.setFixedWidth(260)
        self.cncjob_adv_opt_group = CNCJobAdvOptPrefGroupUI()
        self.cncjob_adv_opt_group.setFixedWidth(260)

        self.layout.addWidget(self.cncjob_gen_group)
        self.layout.addWidget(self.cncjob_opt_group)
        self.layout.addWidget(self.cncjob_adv_opt_group)

        self.layout.addStretch()


class OptionsGroupUI(QtWidgets.QGroupBox):
    def __init__(self, title, parent=None):
        # QtGui.QGroupBox.__init__(self, title, parent=parent)
        super(OptionsGroupUI, self).__init__()
        self.setStyleSheet("""
        QGroupBox
        {
            font-size: 16px;
            font-weight: bold;
        }
        """)

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)


class GeneralGUIPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        super(GeneralGUIPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("GUI Preferences")))

        # Create a form layout for the Application general settings
        self.form_box = QtWidgets.QFormLayout()

        # Grid X Entry
        self.gridx_label = QtWidgets.QLabel(_('Grid X value:'))
        self.gridx_label.setToolTip(
           _("This is the Grid snap value on X axis.")
        )
        self.gridx_entry = LengthEntry()

        # Grid Y Entry
        self.gridy_label = QtWidgets.QLabel(_('Grid Y value:'))
        self.gridy_label.setToolTip(
            _("This is the Grid snap value on Y axis.")
        )
        self.gridy_entry = LengthEntry()

        # Snap Max Entry
        self.snap_max_label = QtWidgets.QLabel(_('Snap Max:'))
        self.snap_max_label.setToolTip(_("Max. magnet distance"))
        self.snap_max_dist_entry = FCEntry()

        # Workspace
        self.workspace_lbl = QtWidgets.QLabel(_('Workspace:'))
        self.workspace_lbl.setToolTip(
           _("Draw a delimiting rectangle on canvas.\n"
             "The purpose is to illustrate the limits for our work.")
        )
        self.workspace_type_lbl = QtWidgets.QLabel(_('Wk. format:'))
        self.workspace_type_lbl.setToolTip(
           _("Select the type of rectangle to be used on canvas,\n"
             "as valid workspace.")
        )
        self.workspace_cb = FCCheckBox()
        self.wk_cb = FCComboBox()
        self.wk_cb.addItem('A4P')
        self.wk_cb.addItem('A4L')
        self.wk_cb.addItem('A3P')
        self.wk_cb.addItem('A3L')

        self.wks = OptionalInputSection(self.workspace_cb, [self.workspace_type_lbl, self.wk_cb])

        # Plot Fill Color
        self.pf_color_label = QtWidgets.QLabel(_('Plot Fill:'))
        self.pf_color_label.setToolTip(
           _("Set the fill color for plotted objects.\n"
             "First 6 digits are the color and the last 2\n"
             "digits are for alpha (transparency) level.")
        )
        self.pf_color_entry = FCEntry()
        self.pf_color_button = QtWidgets.QPushButton()
        self.pf_color_button.setFixedSize(15, 15)

        self.form_box_child_1 = QtWidgets.QHBoxLayout()
        self.form_box_child_1.addWidget(self.pf_color_entry)
        self.form_box_child_1.addWidget(self.pf_color_button)
        self.form_box_child_1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Plot Fill Transparency Level
        self.pf_alpha_label = QtWidgets.QLabel(_('Alpha Level:'))
        self.pf_alpha_label.setToolTip(
           _("Set the fill transparency for plotted objects.")
        )
        self.pf_color_alpha_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pf_color_alpha_slider.setMinimum(0)
        self.pf_color_alpha_slider.setMaximum(255)
        self.pf_color_alpha_slider.setSingleStep(1)

        self.pf_color_alpha_spinner = FCSpinner()
        self.pf_color_alpha_spinner.setFixedWidth(70)
        self.pf_color_alpha_spinner.setMinimum(0)
        self.pf_color_alpha_spinner.setMaximum(255)

        self.form_box_child_2 = QtWidgets.QHBoxLayout()
        self.form_box_child_2.addWidget(self.pf_color_alpha_slider)
        self.form_box_child_2.addWidget(self.pf_color_alpha_spinner)

        # Plot Line Color
        self.pl_color_label = QtWidgets.QLabel(_('Plot Line:'))
        self.pl_color_label.setToolTip(
           _("Set the line color for plotted objects.")
        )
        self.pl_color_entry = FCEntry()
        self.pl_color_button = QtWidgets.QPushButton()
        self.pl_color_button.setFixedSize(15, 15)

        self.form_box_child_3 = QtWidgets.QHBoxLayout()
        self.form_box_child_3.addWidget(self.pl_color_entry)
        self.form_box_child_3.addWidget(self.pl_color_button)
        self.form_box_child_3.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Plot Selection (left - right) Fill Color
        self.sf_color_label = QtWidgets.QLabel(_('Sel. Fill:'))
        self.sf_color_label.setToolTip(
            _("Set the fill color for the selection box\n"
              "in case that the selection is done from left to right.\n"
              "First 6 digits are the color and the last 2\n"
              "digits are for alpha (transparency) level.")
        )
        self.sf_color_entry = FCEntry()
        self.sf_color_button = QtWidgets.QPushButton()
        self.sf_color_button.setFixedSize(15, 15)

        self.form_box_child_4 = QtWidgets.QHBoxLayout()
        self.form_box_child_4.addWidget(self.sf_color_entry)
        self.form_box_child_4.addWidget(self.sf_color_button)
        self.form_box_child_4.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Plot Selection (left - right) Fill Transparency Level
        self.sf_alpha_label = QtWidgets.QLabel(_('Alpha Level:'))
        self.sf_alpha_label.setToolTip(
            _("Set the fill transparency for the 'left to right' selection box.")
        )
        self.sf_color_alpha_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sf_color_alpha_slider.setMinimum(0)
        self.sf_color_alpha_slider.setMaximum(255)
        self.sf_color_alpha_slider.setSingleStep(1)

        self.sf_color_alpha_spinner = FCSpinner()
        self.sf_color_alpha_spinner.setFixedWidth(70)
        self.sf_color_alpha_spinner.setMinimum(0)
        self.sf_color_alpha_spinner.setMaximum(255)

        self.form_box_child_5 = QtWidgets.QHBoxLayout()
        self.form_box_child_5.addWidget(self.sf_color_alpha_slider)
        self.form_box_child_5.addWidget(self.sf_color_alpha_spinner)

        # Plot Selection (left - right) Line Color
        self.sl_color_label = QtWidgets.QLabel(_('Sel. Line:'))
        self.sl_color_label.setToolTip(
            _("Set the line color for the 'left to right' selection box.")
        )
        self.sl_color_entry = FCEntry()
        self.sl_color_button = QtWidgets.QPushButton()
        self.sl_color_button.setFixedSize(15, 15)

        self.form_box_child_6 = QtWidgets.QHBoxLayout()
        self.form_box_child_6.addWidget(self.sl_color_entry)
        self.form_box_child_6.addWidget(self.sl_color_button)
        self.form_box_child_6.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Plot Selection (right - left) Fill Color
        self.alt_sf_color_label = QtWidgets.QLabel(_('Sel2. Fill:'))
        self.alt_sf_color_label.setToolTip(
            _("Set the fill color for the selection box\n"
              "in case that the selection is done from right to left.\n"
              "First 6 digits are the color and the last 2\n"
              "digits are for alpha (transparency) level.")
        )
        self.alt_sf_color_entry = FCEntry()
        self.alt_sf_color_button = QtWidgets.QPushButton()
        self.alt_sf_color_button.setFixedSize(15, 15)

        self.form_box_child_7 = QtWidgets.QHBoxLayout()
        self.form_box_child_7.addWidget(self.alt_sf_color_entry)
        self.form_box_child_7.addWidget(self.alt_sf_color_button)
        self.form_box_child_7.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Plot Selection (right - left) Fill Transparency Level
        self.alt_sf_alpha_label = QtWidgets.QLabel(_('Alpha Level:'))
        self.alt_sf_alpha_label.setToolTip(
            _("Set the fill transparency for selection 'right to left' box.")
        )
        self.alt_sf_color_alpha_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.alt_sf_color_alpha_slider.setMinimum(0)
        self.alt_sf_color_alpha_slider.setMaximum(255)
        self.alt_sf_color_alpha_slider.setSingleStep(1)

        self.alt_sf_color_alpha_spinner = FCSpinner()
        self.alt_sf_color_alpha_spinner.setFixedWidth(70)
        self.alt_sf_color_alpha_spinner.setMinimum(0)
        self.alt_sf_color_alpha_spinner.setMaximum(255)

        self.form_box_child_8 = QtWidgets.QHBoxLayout()
        self.form_box_child_8.addWidget(self.alt_sf_color_alpha_slider)
        self.form_box_child_8.addWidget(self.alt_sf_color_alpha_spinner)

        # Plot Selection (right - left) Line Color
        self.alt_sl_color_label = QtWidgets.QLabel(_('Sel2. Line:'))
        self.alt_sl_color_label.setToolTip(
            _("Set the line color for the 'right to left' selection box.")
        )
        self.alt_sl_color_entry = FCEntry()
        self.alt_sl_color_button = QtWidgets.QPushButton()
        self.alt_sl_color_button.setFixedSize(15, 15)

        self.form_box_child_9 = QtWidgets.QHBoxLayout()
        self.form_box_child_9.addWidget(self.alt_sl_color_entry)
        self.form_box_child_9.addWidget(self.alt_sl_color_button)
        self.form_box_child_9.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Editor Draw Color
        self.draw_color_label = QtWidgets.QLabel(_('Editor Draw:'))
        self.alt_sf_color_label.setToolTip(
            _("Set the color for the shape.")
        )
        self.draw_color_entry = FCEntry()
        self.draw_color_button = QtWidgets.QPushButton()
        self.draw_color_button.setFixedSize(15, 15)

        self.form_box_child_10 = QtWidgets.QHBoxLayout()
        self.form_box_child_10.addWidget(self.draw_color_entry)
        self.form_box_child_10.addWidget(self.draw_color_button)
        self.form_box_child_10.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Editor Draw Selection Color
        self.sel_draw_color_label = QtWidgets.QLabel(_('Editor Draw Sel.:'))
        self.sel_draw_color_label.setToolTip(
            _("Set the color of the shape when selected.")
        )
        self.sel_draw_color_entry = FCEntry()
        self.sel_draw_color_button = QtWidgets.QPushButton()
        self.sel_draw_color_button.setFixedSize(15, 15)

        self.form_box_child_11 = QtWidgets.QHBoxLayout()
        self.form_box_child_11.addWidget(self.sel_draw_color_entry)
        self.form_box_child_11.addWidget(self.sel_draw_color_button)
        self.form_box_child_11.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Project Tab items color
        self.proj_color_label = QtWidgets.QLabel(_('Project Items:'))
        self.proj_color_label.setToolTip(
            _("Set the color of the items in Project Tab Tree.")
        )
        self.proj_color_entry = FCEntry()
        self.proj_color_button = QtWidgets.QPushButton()
        self.proj_color_button.setFixedSize(15, 15)

        self.form_box_child_12 = QtWidgets.QHBoxLayout()
        self.form_box_child_12.addWidget(self.proj_color_entry)
        self.form_box_child_12.addWidget(self.proj_color_button)
        self.form_box_child_12.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.proj_color_dis_label = QtWidgets.QLabel(_('Proj. Dis. Items:'))
        self.proj_color_dis_label.setToolTip(
            _("Set the color of the items in Project Tab Tree,\n"
              "for the case when the items are disabled.")
        )
        self.proj_color_dis_entry = FCEntry()
        self.proj_color_dis_button = QtWidgets.QPushButton()
        self.proj_color_dis_button.setFixedSize(15, 15)

        self.form_box_child_13 = QtWidgets.QHBoxLayout()
        self.form_box_child_13.addWidget(self.proj_color_dis_entry)
        self.form_box_child_13.addWidget(self.proj_color_dis_button)
        self.form_box_child_13.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Just to add empty rows
        self.spacelabel = QtWidgets.QLabel('')

        # Add (label - input field) pair to the QFormLayout
        self.form_box.addRow(self.spacelabel, self.spacelabel)

        self.form_box.addRow(self.gridx_label, self.gridx_entry)
        self.form_box.addRow(self.gridy_label, self.gridy_entry)
        self.form_box.addRow(self.snap_max_label, self.snap_max_dist_entry)

        self.form_box.addRow(self.workspace_lbl, self.workspace_cb)
        self.form_box.addRow(self.workspace_type_lbl, self.wk_cb)
        self.form_box.addRow(self.spacelabel, self.spacelabel)
        self.form_box.addRow(self.pf_color_label, self.form_box_child_1)
        self.form_box.addRow(self.pf_alpha_label, self.form_box_child_2)
        self.form_box.addRow(self.pl_color_label, self.form_box_child_3)
        self.form_box.addRow(self.sf_color_label, self.form_box_child_4)
        self.form_box.addRow(self.sf_alpha_label, self.form_box_child_5)
        self.form_box.addRow(self.sl_color_label, self.form_box_child_6)
        self.form_box.addRow(self.alt_sf_color_label, self.form_box_child_7)
        self.form_box.addRow(self.alt_sf_alpha_label, self.form_box_child_8)
        self.form_box.addRow(self.alt_sl_color_label, self.form_box_child_9)
        self.form_box.addRow(self.draw_color_label, self.form_box_child_10)
        self.form_box.addRow(self.sel_draw_color_label, self.form_box_child_11)
        self.form_box.addRow(QtWidgets.QLabel(""))
        self.form_box.addRow(self.proj_color_label, self.form_box_child_12)
        self.form_box.addRow(self.proj_color_dis_label, self.form_box_child_13)

        self.form_box.addRow(self.spacelabel, self.spacelabel)

        # Add the QFormLayout that holds the Application general defaults
        # to the main layout of this TAB
        self.layout.addLayout(self.form_box)


class GeneralGUISetGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        super(GeneralGUISetGroupUI, self).__init__(self)

        self.setTitle(str(_("GUI Settings")))

        # Create a form layout for the Application general settings
        self.form_box = QtWidgets.QFormLayout()

        # Layout selection
        self.layout_label = QtWidgets.QLabel(_('Layout:'))
        self.layout_label.setToolTip(
            _("Select an layout for FlatCAM.\n"
              "It is applied immediately.")
        )
        self.layout_combo = FCComboBox()
        # don't translate the QCombo items as they are used in QSettings and identified by name
        self.layout_combo.addItem("standard")
        self.layout_combo.addItem("compact")

        # Set the current index for layout_combo
        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("layout"):
            layout = settings.value('layout', type=str)
            idx = self.layout_combo.findText(layout.capitalize())
            self.layout_combo.setCurrentIndex(idx)

        # Style selection
        self.style_label = QtWidgets.QLabel(_('Style:'))
        self.style_label.setToolTip(
            _("Select an style for FlatCAM.\n"
              "It will be applied at the next app start.")
        )
        self.style_combo = FCComboBox()
        self.style_combo.addItems(QtWidgets.QStyleFactory.keys())
        # find current style
        index = self.style_combo.findText(QtWidgets.qApp.style().objectName(), QtCore.Qt.MatchFixedString)
        self.style_combo.setCurrentIndex(index)
        self.style_combo.activated[str].connect(self.handle_style)

        # Enable High DPI Support
        self.hdpi_label = QtWidgets.QLabel(_('HDPI Support:'))
        self.hdpi_label.setToolTip(
            _("Enable High DPI support for FlatCAM.\n"
              "It will be applied at the next app start.")
        )
        self.hdpi_cb = FCCheckBox()

        settings = QSettings("Open Source", "FlatCAM")
        if settings.contains("hdpi"):
            self.hdpi_cb.set_value(settings.value('hdpi', type=int))
        else:
            self.hdpi_cb.set_value(False)
        self.hdpi_cb.stateChanged.connect(self.handle_hdpi)

        # Clear Settings
        self.clear_label = QtWidgets.QLabel(_('Clear GUI Settings:'))
        self.clear_label.setToolTip(
            _("Clear the GUI settings for FlatCAM,\n"
              "such as: layout, gui state, style, hdpi support etc.")
        )
        self.clear_btn = FCButton(_("Clear"))
        self.clear_btn.clicked.connect(self.handle_clear)

        # Enable Hover box
        self.hover_label = QtWidgets.QLabel(_('Hover Shape:'))
        self.hover_label.setToolTip(
            _("Enable display of a hover shape for FlatCAM objects.\n"
              "It is displayed whenever the mouse cursor is hovering\n"
              "over any kind of not-selected object.")
        )
        self.hover_cb = FCCheckBox()

        # Enable Selection box
        self.selection_label = QtWidgets.QLabel(_('Sel. Shape:'))
        self.selection_label.setToolTip(
            _("Enable the display of a selection shape for FlatCAM objects.\n"
              "It is displayed whenever the mouse selects an object\n"
              "either by clicking or dragging mouse from left to right or\n"
              "right to left.")
        )
        self.selection_cb = FCCheckBox()

        # Just to add empty rows
        self.spacelabel = QtWidgets.QLabel('')

        # Add (label - input field) pair to the QFormLayout
        self.form_box.addRow(self.spacelabel, self.spacelabel)

        self.form_box.addRow(self.layout_label, self.layout_combo)
        self.form_box.addRow(self.style_label, self.style_combo)
        self.form_box.addRow(self.hdpi_label, self.hdpi_cb)
        self.form_box.addRow(self.clear_label, self.clear_btn)
        self.form_box.addRow(self.hover_label, self.hover_cb)
        self.form_box.addRow(self.selection_label, self.selection_cb)

        # Add the QFormLayout that holds the Application general defaults
        # to the main layout of this TAB
        self.layout.addLayout(self.form_box)

    def handle_style(self, style):
        # set current style
        settings = QSettings("Open Source", "FlatCAM")
        settings.setValue('style', style)

        # This will write the setting to the platform specific storage.
        del settings

    def handle_hdpi(self, state):
        # set current HDPI
        settings = QSettings("Open Source", "FlatCAM")
        settings.setValue('hdpi', state)

        # This will write the setting to the platform specific storage.
        del settings

    def handle_clear(self):
        msgbox = QtWidgets.QMessageBox()
        msgbox.setText(_("Are you sure you want to delete the GUI Settings? "
                         "\n")
                       )
        msgbox.setWindowTitle(_("Clear GUI Settings"))
        msgbox.setWindowIcon(QtGui.QIcon('share/trash32.png'))
        bt_yes = msgbox.addButton(_('Yes'), QtWidgets.QMessageBox.YesRole)
        bt_no = msgbox.addButton(_('No'), QtWidgets.QMessageBox.NoRole)

        msgbox.setDefaultButton(bt_no)
        msgbox.exec_()
        response = msgbox.clickedButton()

        if response == bt_yes:
            settings = QSettings("Open Source", "FlatCAM")
            for key in settings.allKeys():
                settings.remove(key)
            # This will write the setting to the platform specific storage.
            del settings


class GeneralAppPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        super(GeneralAppPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("App Preferences")))

        # Create a form layout for the Application general settings
        self.form_box = QtWidgets.QFormLayout()

        # Units for FlatCAM
        self.unitslabel = QtWidgets.QLabel(_('<b>Units:</b>'))
        self.unitslabel.setToolTip(_("The default value for FlatCAM units.\n"
                                     "Whatever is selected here is set every time\n"
                                     "FLatCAM is started."))
        self.units_radio = RadioSet([{'label': 'IN', 'value': 'IN'},
                                     {'label': 'MM', 'value': 'MM'}])

        # Application Level for FlatCAM
        self.app_level_label = QtWidgets.QLabel(_('<b>APP. LEVEL:</b>'))
        self.app_level_label.setToolTip(_("Choose the default level of usage for FlatCAM.\n"
                                          "BASIC level -> reduced functionality, best for beginner's.\n"
                                          "ADVANCED level -> full functionality.\n\n"
                                          "The choice here will influence the parameters in\n"
                                          "the Selected Tab for all kinds of FlatCAM objects."))
        self.app_level_radio = RadioSet([{'label': _('Basic'), 'value': 'b'},
                                         {'label': _('Advanced'), 'value': 'a'}])

        # Languages for FlatCAM
        self.languagelabel = QtWidgets.QLabel(_('<b>Languages:</b>'))
        self.languagelabel.setToolTip(_("Set the language used throughout FlatCAM."))
        self.language_cb = FCComboBox()
        self.languagespace = QtWidgets.QLabel('')
        self.language_apply_btn = FCButton(_("Apply Language"))
        self.language_apply_btn.setToolTip(_("Set the language used throughout FlatCAM.\n"
                                             "The app will restart after click."
                                             "Windows: When FlatCAM is installed in Program Files\n"
                                             "directory, it is possible that the app will not\n"
                                             "restart after the button is clicked due of Windows\n"
                                             "security features. In this case the language will be\n"
                                             "applied at the next app start."))

        # Shell StartUp CB
        self.shell_startup_label = QtWidgets.QLabel(_('Shell at StartUp:'))
        self.shell_startup_label.setToolTip(
            _("Check this box if you want the shell to\n"
              "start automatically at startup.")
        )
        self.shell_startup_cb = FCCheckBox(label='')
        self.shell_startup_cb.setToolTip(
            _("Check this box if you want the shell to\n"
              "start automatically at startup.")
        )

        # Version Check CB
        self.version_check_label = QtWidgets.QLabel(_('Version Check:'))
        self.version_check_label.setToolTip(
            _("Check this box if you want to check\n"
              "for a new version automatically at startup.")
        )
        self.version_check_cb = FCCheckBox(label='')
        self.version_check_cb.setToolTip(
            _("Check this box if you want to check\n"
              "for a new version automatically at startup.")
        )

        # Send Stats CB
        self.send_stats_label = QtWidgets.QLabel(_('Send Stats:'))
        self.send_stats_label.setToolTip(
            _("Check this box if you agree to send anonymous\n"
              "stats automatically at startup, to help improve FlatCAM.")
        )
        self.send_stats_cb = FCCheckBox(label='')
        self.send_stats_cb.setToolTip(
            _("Check this box if you agree to send anonymous\n"
              "stats automatically at startup, to help improve FlatCAM.")
        )

        self.ois_version_check = OptionalInputSection(self.version_check_cb, [self.send_stats_cb])

        # Select mouse pan button
        self.panbuttonlabel = QtWidgets.QLabel(_('<b>Pan Button:</b>'))
        self.panbuttonlabel.setToolTip(_("Select the mouse button to use for panning:\n"
                                         "- MMB --> Middle Mouse Button\n"
                                         "- RMB --> Right Mouse Button"))
        self.pan_button_radio = RadioSet([{'label': 'MMB', 'value': '3'},
                                          {'label': 'RMB', 'value': '2'}])

        # Multiple Selection Modifier Key
        self.mselectlabel = QtWidgets.QLabel(_('<b>Multiple Sel:</b>'))
        self.mselectlabel.setToolTip(_("Select the key used for multiple selection."))
        self.mselect_radio = RadioSet([{'label': 'CTRL', 'value': 'Control'},
                                       {'label': 'SHIFT', 'value': 'Shift'}])

        # Project at StartUp CB
        self.project_startup_label = QtWidgets.QLabel(_('Project at StartUp:'))
        self.project_startup_label.setToolTip(
            _("Check this box if you want the project/selected/tool tab area to\n"
              "to be shown automatically at startup.")
        )
        self.project_startup_cb = FCCheckBox(label='')
        self.project_startup_cb.setToolTip(
            _("Check this box if you want the project/selected/tool tab area to\n"
              "to be shown automatically at startup.")
        )

        # Project autohide CB
        self.project_autohide_label = QtWidgets.QLabel(_('Project AutoHide:'))
        self.project_autohide_label.setToolTip(
           _("Check this box if you want the project/selected/tool tab area to\n"
             "hide automatically when there are no objects loaded and\n"
             "to show whenever a new object is created.")
        )
        self.project_autohide_cb = FCCheckBox(label='')
        self.project_autohide_cb.setToolTip(
            _("Check this box if you want the project/selected/tool tab area to\n"
              "hide automatically when there are no objects loaded and\n"
              "to show whenever a new object is created.")
        )

        # Enable/Disable ToolTips globally
        self.toggle_tooltips_label = QtWidgets.QLabel(_('<b>Enable ToolTips:</b>'))
        self.toggle_tooltips_label.setToolTip(
           _("Check this box if you want to have toolTips displayed\n"
             "when hovering with mouse over items throughout the App.")
        )
        self.toggle_tooltips_cb = FCCheckBox(label='')
        self.toggle_tooltips_cb.setToolTip(
           _("Check this box if you want to have toolTips displayed\n"
             "when hovering with mouse over items throughout the App.")
        )
        self.worker_number_label = QtWidgets.QLabel(_('Workers number:'))
        self.worker_number_label.setToolTip(
            _("The number of Qthreads made available to the App.\n"
              "A bigger number may finish the jobs more quickly but\n"
              "depending on your computer speed, may make the App\n"
              "unresponsive. Can have a value between 2 and 16.\n"
              "Default value is 2.\n"
              "After change, it will be applied at next App start.")
        )
        self.worker_number_sb = FCSpinner()
        self.worker_number_sb.setToolTip(
            _("The number of Qthreads made available to the App.\n"
              "A bigger number may finish the jobs more quickly but\n"
              "depending on your computer speed, may make the App\n"
              "unresponsive. Can have a value between 2 and 16.\n"
              "Default value is 2.\n"
              "After change, it will be applied at next App start.")
        )
        self.worker_number_sb.set_range(2, 16)

        # Geometric tolerance
        tol_label = QtWidgets.QLabel("Geo Tolerance:")
        tol_label.setToolTip(_(
            "This value can counter the effect of the Circle Steps\n"
            "parameter. Default value is 0.01.\n"
            "A lower value will increase the detail both in image\n"
            "and in Gcode for the circles, with a higher cost in\n"
            "performance. Higher value will provide more\n"
            "performance at the expense of level of detail."
        ))
        self.tol_entry = FCEntry()
        self.tol_entry.setToolTip(_(
            "This value can counter the effect of the Circle Steps\n"
            "parameter. Default value is 0.01.\n"
            "A lower value will increase the detail both in image\n"
            "and in Gcode for the circles, with a higher cost in\n"
            "performance. Higher value will provide more\n"
            "performance at the expense of level of detail."
        ))
        # Just to add empty rows
        self.spacelabel = QtWidgets.QLabel('')

        # Add (label - input field) pair to the QFormLayout
        self.form_box.addRow(self.unitslabel, self.units_radio)
        self.form_box.addRow(self.app_level_label, self.app_level_radio)
        self.form_box.addRow(self.languagelabel, self.language_cb)
        self.form_box.addRow(self.languagespace, self.language_apply_btn)

        self.form_box.addRow(self.spacelabel, self.spacelabel)
        self.form_box.addRow(self.shell_startup_label, self.shell_startup_cb)
        self.form_box.addRow(self.version_check_label, self.version_check_cb)
        self.form_box.addRow(self.send_stats_label, self.send_stats_cb)

        self.form_box.addRow(self.panbuttonlabel, self.pan_button_radio)
        self.form_box.addRow(self.mselectlabel, self.mselect_radio)
        self.form_box.addRow(self.project_startup_label, self.project_startup_cb)
        self.form_box.addRow(self.project_autohide_label, self.project_autohide_cb)
        self.form_box.addRow(self.toggle_tooltips_label, self.toggle_tooltips_cb)
        self.form_box.addRow(self.worker_number_label, self.worker_number_sb)
        self.form_box.addRow(tol_label, self.tol_entry)

        self.form_box.addRow(self.spacelabel, self.spacelabel)

        # Add the QFormLayout that holds the Application general defaults
        # to the main layout of this TAB
        self.layout.addLayout(self.form_box)

        # Save compressed project CB
        self.open_style_cb = FCCheckBox(_('"Open" behavior'))
        self.open_style_cb.setToolTip(
            _("When checked the path for the last saved file is used when saving files,\n"
              "and the path for the last opened file is used when opening files.\n\n"
              "When unchecked the path for opening files is the one used last: either the\n"
              "path for saving files or the path for opening files.")
        )
        # self.advanced_cb.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.layout.addWidget(self.open_style_cb)

        # Save compressed project CB
        self.save_type_cb = FCCheckBox(_('Save Compressed Project'))
        self.save_type_cb.setToolTip(
            _("Whether to save a compressed or uncompressed project.\n"
              "When checked it will save a compressed FlatCAM project.")
        )
        # self.advanced_cb.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.layout.addWidget(self.save_type_cb)

        hlay1 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay1)

        # Project LZMA Comppression Level
        self.compress_combo = FCComboBox()
        self.compress_label = QtWidgets.QLabel(_('Compression Level:'))
        self.compress_label.setToolTip(
            _("The level of compression used when saving\n"
              "a FlatCAM project. Higher value means better compression\n"
              "but require more RAM usage and more processing time.")
        )
        # self.advanced_cb.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.compress_combo.addItems([str(i) for i in range(10)])

        hlay1.addWidget(self.compress_label)
        hlay1.addWidget(self.compress_combo)

        self.proj_ois = OptionalInputSection(self.save_type_cb, [self.compress_label, self.compress_combo], True)

        self.form_box_2 = QtWidgets.QFormLayout()
        self.layout.addLayout(self.form_box_2)

        self.layout.addStretch()


class GerberGenPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Gerber General Preferences", parent=parent)
        super(GerberGenPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Gerber General")))

        # ## Plot options
        self.plot_options_label = QtWidgets.QLabel(_("<b>Plot Options:</b>"))
        self.layout.addWidget(self.plot_options_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Solid CB
        self.solid_cb = FCCheckBox(label=_('Solid'))
        self.solid_cb.setToolTip(
            _("Solid color polygons.")
        )
        grid0.addWidget(self.solid_cb, 0, 0)

        # Multicolored CB
        self.multicolored_cb = FCCheckBox(label=_('M-Color'))
        self.multicolored_cb.setToolTip(
            _("Draw polygons in different colors.")
        )
        grid0.addWidget(self.multicolored_cb, 0, 1)

        # Plot CB
        self.plot_cb = FCCheckBox(label=_('Plot'))
        self.plot_options_label.setToolTip(
            _("Plot (show) this object.")
        )
        grid0.addWidget(self.plot_cb, 0, 2)

        # Number of circle steps for circular aperture linear approximation
        self.circle_steps_label = QtWidgets.QLabel(_("Circle Steps:"))
        self.circle_steps_label.setToolTip(
            _("The number of circle steps for Gerber \n"
            "circular aperture linear approximation.")
        )
        grid0.addWidget(self.circle_steps_label, 1, 0)
        self.circle_steps_entry = IntEntry()
        grid0.addWidget(self.circle_steps_entry, 1, 1)

        self.layout.addStretch()


class GerberOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Gerber Options Preferences", parent=parent)
        super(GerberOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Gerber Options")))

        # ## Isolation Routing
        self.isolation_routing_label = QtWidgets.QLabel(_("<b>Isolation Routing:</b>"))
        self.isolation_routing_label.setToolTip(
            _("Create a Geometry object with\n"
              "toolpaths to cut outside polygons.")
        )
        self.layout.addWidget(self.isolation_routing_label)

        # Cutting Tool Diameter
        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        tdlabel = QtWidgets.QLabel(_('Tool dia:'))
        tdlabel.setToolTip(
            _("Diameter of the cutting tool.")
        )
        grid0.addWidget(tdlabel, 0, 0)
        self.iso_tool_dia_entry = LengthEntry()
        grid0.addWidget(self.iso_tool_dia_entry, 0, 1)

        # Nr of passes
        passlabel = QtWidgets.QLabel(_('Width (# passes):'))
        passlabel.setToolTip(
            _("Width of the isolation gap in\n"
              "number (integer) of tool widths.")
        )
        grid0.addWidget(passlabel, 1, 0)
        self.iso_width_entry = IntEntry()
        grid0.addWidget(self.iso_width_entry, 1, 1)

        # Pass overlap
        overlabel = QtWidgets.QLabel(_('Pass overlap:'))
        overlabel.setToolTip(
            _("How much (fraction) of the tool width to overlap each tool pass.\n"
              "Example:\n"
              "A value here of 0.25 means an overlap of 25% from the tool diameter found above.")
        )
        grid0.addWidget(overlabel, 2, 0)
        self.iso_overlap_entry = FloatEntry()
        grid0.addWidget(self.iso_overlap_entry, 2, 1)

        milling_type_label = QtWidgets.QLabel(_('Milling Type:'))
        milling_type_label.setToolTip(
            _("Milling type:\n"
              "- climb / best for precision milling and to reduce tool usage\n"
              "- conventional / useful when there is no backlash compensation")
        )
        grid0.addWidget(milling_type_label, 3, 0)
        self.milling_type_radio = RadioSet([{'label': 'Climb', 'value': 'cl'},
                                            {'label': 'Conv.', 'value': 'cv'}])
        grid0.addWidget(self.milling_type_radio, 3, 1)

        # Combine passes
        self.combine_passes_cb = FCCheckBox(label=_('Combine Passes'))
        self.combine_passes_cb.setToolTip(
            _("Combine all passes into one object")
        )
        grid0.addWidget(self.combine_passes_cb, 4, 0, 1, 2)

        # ## Clear non-copper regions
        self.clearcopper_label = QtWidgets.QLabel(_("<b>Clear non-copper:</b>"))
        self.clearcopper_label.setToolTip(
            _("Create a Geometry object with\n"
              "toolpaths to cut all non-copper regions.")
        )
        self.layout.addWidget(self.clearcopper_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        # Margin
        bmlabel = QtWidgets.QLabel(_('Boundary Margin:'))
        bmlabel.setToolTip(
            _("Specify the edge of the PCB\n"
              "by drawing a box around all\n"
              "objects with this minimum\n"
              "distance.")
        )
        grid1.addWidget(bmlabel, 0, 0)
        self.noncopper_margin_entry = LengthEntry()
        grid1.addWidget(self.noncopper_margin_entry, 0, 1)

        # Rounded corners
        self.noncopper_rounded_cb = FCCheckBox(label=_("Rounded corners"))
        self.noncopper_rounded_cb.setToolTip(
            _("Creates a Geometry objects with polygons\n"
              "covering the copper-free areas of the PCB.")
        )
        grid1.addWidget(self.noncopper_rounded_cb, 1, 0, 1, 2)

        # ## Bounding box
        self.boundingbox_label = QtWidgets.QLabel(_('<b>Bounding Box:</b>'))
        self.layout.addWidget(self.boundingbox_label)

        grid2 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid2)

        bbmargin = QtWidgets.QLabel(_('Boundary Margin:'))
        bbmargin.setToolTip(
            _("Distance of the edges of the box\n"
              "to the nearest polygon.")
        )
        grid2.addWidget(bbmargin, 0, 0)
        self.bbmargin_entry = LengthEntry()
        grid2.addWidget(self.bbmargin_entry, 0, 1)

        self.bbrounded_cb = FCCheckBox(label=_("Rounded corners"))
        self.bbrounded_cb.setToolTip(
            _("If the bounding box is \n"
              "to have rounded corners\n"
              "their radius is equal to\n"
              "the margin.")
        )
        grid2.addWidget(self.bbrounded_cb, 1, 0, 1, 2)
        self.layout.addStretch()


class GerberAdvOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Gerber Adv. Options Preferences", parent=parent)
        super(GerberAdvOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Gerber Adv. Options")))

        # ## Advanced Gerber Parameters
        self.adv_param_label = QtWidgets.QLabel(_("<b>Advanced Param.:</b>"))
        self.adv_param_label.setToolTip(
            _("A list of Gerber advanced parameters.\n"
              "Those parameters are available only for\n"
              "Advanced App. Level.")
        )
        self.layout.addWidget(self.adv_param_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Follow Attribute
        self.follow_cb = FCCheckBox(label=_('"Follow"'))
        self.follow_cb.setToolTip(
            _("Generate a 'Follow' geometry.\n"
              "This means that it will cut through\n"
              "the middle of the trace.")
        )
        grid0.addWidget(self.follow_cb, 0, 0)

        # Aperture Table Visibility CB
        self.aperture_table_visibility_cb = FCCheckBox(label=_('Table Show/Hide'))
        self.aperture_table_visibility_cb.setToolTip(
            _("Toggle the display of the Gerber Apertures Table.\n"
              "Also, on hide, it will delete all mark shapes\n"
              "that are drawn on canvas.")

        )
        grid0.addWidget(self.aperture_table_visibility_cb, 1, 0)

        # Scale Aperture Factor
        # self.scale_aperture_label = QtWidgets.QLabel(_('Ap. Scale Factor:'))
        # self.scale_aperture_label.setToolTip(
        #     _("Change the size of the selected apertures.\n"
        #     "Factor by which to multiply\n"
        #     "geometric features of this object.")
        # )
        # grid0.addWidget(self.scale_aperture_label, 2, 0)
        #
        # self.scale_aperture_entry = FloatEntry2()
        # grid0.addWidget(self.scale_aperture_entry, 2, 1)

        # Buffer Aperture Factor
        # self.buffer_aperture_label = QtWidgets.QLabel(_('Ap. Buffer Factor:'))
        # self.buffer_aperture_label.setToolTip(
        #     _("Change the size of the selected apertures.\n"
        #     "Factor by which to expand/shrink\n"
        #     "geometric features of this object.")
        # )
        # grid0.addWidget(self.buffer_aperture_label, 3, 0)
        #
        # self.buffer_aperture_entry = FloatEntry2()
        # grid0.addWidget(self.buffer_aperture_entry, 3, 1)

        self.layout.addStretch()


class GerberExpPrefGroupUI(OptionsGroupUI):

    def __init__(self, parent=None):
        super(GerberExpPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Gerber Export")))

        # Plot options
        self.export_options_label = QtWidgets.QLabel(_("<b>Export Options:</b>"))
        self.export_options_label.setToolTip(
            _("The parameters set here are used in the file exported\n"
              "when using the File -> Export -> Export Gerber menu entry.")
        )
        self.layout.addWidget(self.export_options_label)

        form = QtWidgets.QFormLayout()
        self.layout.addLayout(form)

        # Gerber Units
        self.gerber_units_label = QtWidgets.QLabel(_('<b>Units</b>:'))
        self.gerber_units_label.setToolTip(
            _("The units used in the Gerber file.")
        )

        self.gerber_units_radio = RadioSet([{'label': 'INCH', 'value': 'IN'},
                                            {'label': 'MM', 'value': 'MM'}])
        self.gerber_units_radio.setToolTip(
            _("The units used in the Gerber file.")
        )

        form.addRow(self.gerber_units_label, self.gerber_units_radio)

        # Gerber format
        self.digits_label = QtWidgets.QLabel(_("<b>Int/Decimals:</b>"))
        self.digits_label.setToolTip(
            _("The number of digits in the whole part of the number\n"
              "and in the fractional part of the number.")
        )

        hlay1 = QtWidgets.QHBoxLayout()

        self.format_whole_entry = IntEntry()
        self.format_whole_entry.setMaxLength(1)
        self.format_whole_entry.setAlignment(QtCore.Qt.AlignRight)
        self.format_whole_entry.setFixedWidth(30)
        self.format_whole_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the whole part of Gerber coordinates.")
        )
        hlay1.addWidget(self.format_whole_entry, QtCore.Qt.AlignLeft)

        gerber_separator_label= QtWidgets.QLabel(':')
        gerber_separator_label.setFixedWidth(5)
        hlay1.addWidget(gerber_separator_label, QtCore.Qt.AlignLeft)

        self.format_dec_entry = IntEntry()
        self.format_dec_entry.setMaxLength(1)
        self.format_dec_entry.setAlignment(QtCore.Qt.AlignRight)
        self.format_dec_entry.setFixedWidth(30)
        self.format_dec_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the decimal part of Gerber coordinates.")
        )
        hlay1.addWidget(self.format_dec_entry, QtCore.Qt.AlignLeft)
        hlay1.addStretch()

        form.addRow(self.digits_label, hlay1)

        # Gerber Zeros
        self.zeros_label = QtWidgets.QLabel(_('<b>Zeros</b>:'))
        self.zeros_label.setAlignment(QtCore.Qt.AlignLeft)
        self.zeros_label.setToolTip(
            _("This sets the type of Gerber zeros.\n"
              "If LZ then Leading Zeros are removed and\n"
              "Trailing Zeros are kept.\n"
              "If TZ is checked then Trailing Zeros are removed\n"
              "and Leading Zeros are kept.")
        )

        self.zeros_radio = RadioSet([{'label': 'LZ', 'value': 'L'},
                                     {'label': 'TZ', 'value': 'T'}])
        self.zeros_radio.setToolTip(
            _("This sets the type of Gerber zeros.\n"
              "If LZ then Leading Zeros are removed and\n"
              "Trailing Zeros are kept.\n"
              "If TZ is checked then Trailing Zeros are removed\n"
              "and Leading Zeros are kept.")
        )

        form.addRow(self.zeros_label, self.zeros_radio)

        self.layout.addStretch()


class GerberEditorPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Gerber Adv. Options Preferences", parent=parent)
        super(GerberEditorPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Gerber Editor")))

        # Advanced Gerber Parameters
        self.param_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.param_label.setToolTip(
            _("A list of Gerber Editor parameters.")
        )
        self.layout.addWidget(self.param_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Selection Limit
        self.sel_limit_label = QtWidgets.QLabel(_("Selection limit:"))
        self.sel_limit_label.setToolTip(
            _("Set the number of selected Gerber geometry\n"
              "items above which the utility geometry\n"
              "becomes just a selection rectangle.\n"
              "Increases the performance when moving a\n"
              "large number of geometric elements.")
        )
        self.sel_limit_entry = IntEntry()

        grid0.addWidget(self.sel_limit_label, 0, 0)
        grid0.addWidget(self.sel_limit_entry, 0, 1)

        self.layout.addStretch()


class ExcellonGenPrefGroupUI(OptionsGroupUI):

    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Excellon Options", parent=parent)
        super(ExcellonGenPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Excellon General")))

        # Plot options
        self.plot_options_label = QtWidgets.QLabel(_("<b>Plot Options:</b>"))
        self.layout.addWidget(self.plot_options_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        self.plot_cb = FCCheckBox(label=_('Plot'))
        self.plot_cb.setToolTip(
            "Plot (show) this object."
        )
        grid1.addWidget(self.plot_cb, 0, 0)

        self.solid_cb = FCCheckBox(label=_('Solid'))
        self.solid_cb.setToolTip(
            "Plot as solid circles."
        )
        grid1.addWidget(self.solid_cb, 0, 1)

        # Excellon format
        self.excellon_format_label = QtWidgets.QLabel(_("<b>Excellon Format:</b>"))
        self.excellon_format_label.setToolTip(
            _("The NC drill files, usually named Excellon files\n"
              "are files that can be found in different formats.\n"
              "Here we set the format used when the provided\n"
              "coordinates are not using period.\n"
              "\n"
              "Possible presets:\n"
              "\n"
              "PROTEUS 3:3 MM LZ\n"
              "DipTrace 5:2 MM TZ\n"
              "DipTrace 4:3 MM LZ\n"
              "\n"
              "EAGLE 3:3 MM TZ\n"
              "EAGLE 4:3 MM TZ\n"
              "EAGLE 2:5 INCH TZ\n"
              "EAGLE 3:5 INCH TZ\n"
              "\n"
              "ALTIUM 2:4 INCH LZ\n"
              "Sprint Layout 2:4 INCH LZ"
              "\n"
              "KiCAD 3:5 INCH TZ")
        )
        self.layout.addWidget(self.excellon_format_label)

        hlay1 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay1)
        self.excellon_format_in_label = QtWidgets.QLabel(_("INCH:"))
        self.excellon_format_in_label.setAlignment(QtCore.Qt.AlignLeft)
        self.excellon_format_in_label.setToolTip(
            _("Default values for INCH are 2:4"))
        hlay1.addWidget(self.excellon_format_in_label, QtCore.Qt.AlignLeft)

        self.excellon_format_upper_in_entry = IntEntry()
        self.excellon_format_upper_in_entry.setMaxLength(1)
        self.excellon_format_upper_in_entry.setAlignment(QtCore.Qt.AlignRight)
        self.excellon_format_upper_in_entry.setFixedWidth(30)
        self.excellon_format_upper_in_entry.setToolTip(
           _("This numbers signify the number of digits in\n"
             "the whole part of Excellon coordinates.")
        )
        hlay1.addWidget(self.excellon_format_upper_in_entry, QtCore.Qt.AlignLeft)

        excellon_separator_in_label= QtWidgets.QLabel(':')
        excellon_separator_in_label.setFixedWidth(5)
        hlay1.addWidget(excellon_separator_in_label, QtCore.Qt.AlignLeft)

        self.excellon_format_lower_in_entry = IntEntry()
        self.excellon_format_lower_in_entry.setMaxLength(1)
        self.excellon_format_lower_in_entry.setAlignment(QtCore.Qt.AlignRight)
        self.excellon_format_lower_in_entry.setFixedWidth(30)
        self.excellon_format_lower_in_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the decimal part of Excellon coordinates.")
        )
        hlay1.addWidget(self.excellon_format_lower_in_entry, QtCore.Qt.AlignLeft)
        hlay1.addStretch()

        hlay2 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay2)
        self.excellon_format_mm_label = QtWidgets.QLabel(_("METRIC:"))
        self.excellon_format_mm_label.setAlignment(QtCore.Qt.AlignLeft)
        self.excellon_format_mm_label.setToolTip(
            _("Default values for METRIC are 3:3"))
        hlay2.addWidget(self.excellon_format_mm_label, QtCore.Qt.AlignLeft)

        self.excellon_format_upper_mm_entry = IntEntry()
        self.excellon_format_upper_mm_entry.setMaxLength(1)
        self.excellon_format_upper_mm_entry.setAlignment(QtCore.Qt.AlignRight)
        self.excellon_format_upper_mm_entry.setFixedWidth(30)
        self.excellon_format_upper_mm_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the whole part of Excellon coordinates.")
        )
        hlay2.addWidget(self.excellon_format_upper_mm_entry, QtCore.Qt.AlignLeft)

        excellon_separator_mm_label = QtWidgets.QLabel(':')
        excellon_separator_mm_label.setFixedWidth(5)
        hlay2.addWidget(excellon_separator_mm_label, QtCore.Qt.AlignLeft)

        self.excellon_format_lower_mm_entry = IntEntry()
        self.excellon_format_lower_mm_entry.setMaxLength(1)
        self.excellon_format_lower_mm_entry.setAlignment(QtCore.Qt.AlignRight)
        self.excellon_format_lower_mm_entry.setFixedWidth(30)
        self.excellon_format_lower_mm_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the decimal part of Excellon coordinates.")
        )
        hlay2.addWidget(self.excellon_format_lower_mm_entry, QtCore.Qt.AlignLeft)
        hlay2.addStretch()

        grid2 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid2)

        self.excellon_zeros_label = QtWidgets.QLabel(_('Default <b>Zeros</b>:'))
        self.excellon_zeros_label.setAlignment(QtCore.Qt.AlignLeft)
        self.excellon_zeros_label.setToolTip(
            _("This sets the type of Excellon zeros.\n"
              "If LZ then Leading Zeros are kept and\n"
              "Trailing Zeros are removed.\n"
              "If TZ is checked then Trailing Zeros are kept\n"
              "and Leading Zeros are removed.")
        )
        grid2.addWidget(self.excellon_zeros_label, 0, 0)

        self.excellon_zeros_radio = RadioSet([{'label': 'LZ', 'value': 'L'},
                                              {'label': 'TZ', 'value': 'T'}])
        self.excellon_zeros_radio.setToolTip(
            _("This sets the default type of Excellon zeros.\n"
              "If it is not detected in the parsed file the value here\n"
              "will be used."
              "If LZ then Leading Zeros are kept and\n"
              "Trailing Zeros are removed.\n"
              "If TZ is checked then Trailing Zeros are kept\n"
              "and Leading Zeros are removed.")
        )
        grid2.addWidget(self.excellon_zeros_radio, 0, 1)

        self.excellon_units_label = QtWidgets.QLabel(_('Default <b>Units</b>:'))
        self.excellon_units_label.setAlignment(QtCore.Qt.AlignLeft)
        self.excellon_units_label.setToolTip(
            _("This sets the default units of Excellon files.\n"
              "If it is not detected in the parsed file the value here\n"
              "will be used."
              "Some Excellon files don't have an header\n"
              "therefore this parameter will be used.")
        )
        grid2.addWidget(self.excellon_units_label, 1, 0)

        self.excellon_units_radio = RadioSet([{'label': 'INCH', 'value': 'INCH'},
                                              {'label': 'MM', 'value': 'METRIC'}])
        self.excellon_units_radio.setToolTip(
            _("This sets the units of Excellon files.\n"
              "Some Excellon files don't have an header\n"
              "therefore this parameter will be used.")
        )
        grid2.addWidget(self.excellon_units_radio, 1, 1)

        grid2.addWidget(QtWidgets.QLabel(""), 2, 0)

        self.excellon_general_label = QtWidgets.QLabel(_("<b>Excellon Optimization:</b>"))
        grid2.addWidget(self.excellon_general_label, 3, 0, 1, 2)

        self.excellon_optimization_label = QtWidgets.QLabel(_('Algorithm:   '))
        self.excellon_optimization_label.setToolTip(
            _("This sets the optimization type for the Excellon drill path.\n"
              "If MH is checked then Google OR-Tools algorithm with MetaHeuristic\n"
              "Guided Local Path is used. Default search time is 3sec.\n"
              "Use set_sys excellon_search_time value Tcl Command to set other values.\n"
              "If Basic is checked then Google OR-Tools Basic algorithm is used.\n"
              "\n"
              "If DISABLED, then FlatCAM works in 32bit mode and it uses \n"
              "Travelling Salesman algorithm for path optimization.")
        )
        grid2.addWidget(self.excellon_optimization_label, 4, 0)

        self.excellon_optimization_radio = RadioSet([{'label': 'MH', 'value': 'M'},
                                     {'label': 'Basic', 'value': 'B'}])
        self.excellon_optimization_radio.setToolTip(
            _("This sets the optimization type for the Excellon drill path.\n"
              "If MH is checked then Google OR-Tools algorithm with MetaHeuristic\n"
              "Guided Local Path is used. Default search time is 3sec.\n"
              "Use set_sys excellon_search_time value Tcl Command to set other values.\n"
              "If Basic is checked then Google OR-Tools Basic algorithm is used.\n"
              "\n"
              "If DISABLED, then FlatCAM works in 32bit mode and it uses \n"
              "Travelling Salesman algorithm for path optimization.")
        )
        grid2.addWidget(self.excellon_optimization_radio, 4, 1)

        self.optimization_time_label = QtWidgets.QLabel(_('Optimization Time:   '))
        self.optimization_time_label.setAlignment(QtCore.Qt.AlignLeft)
        self.optimization_time_label.setToolTip(
            _("When OR-Tools Metaheuristic (MH) is enabled there is a\n"
              "maximum threshold for how much time is spent doing the\n"
              "path optimization. This max duration is set here.\n"
              "In seconds.")

        )
        grid2.addWidget(self.optimization_time_label, 5, 0)

        self.optimization_time_entry = IntEntry()
        self.optimization_time_entry.setValidator(QtGui.QIntValidator(0, 999))
        grid2.addWidget(self.optimization_time_entry, 5, 1)

        current_platform = platform.architecture()[0]
        if current_platform == '64bit':
            self.excellon_optimization_label.setDisabled(False)
            self.excellon_optimization_radio.setDisabled(False)
            self.optimization_time_label.setDisabled(False)
            self.optimization_time_entry.setDisabled(False)
            self.excellon_optimization_radio.activated_custom.connect(self.optimization_selection)

        else:
            self.excellon_optimization_label.setDisabled(True)
            self.excellon_optimization_radio.setDisabled(True)
            self.optimization_time_label.setDisabled(True)
            self.optimization_time_entry.setDisabled(True)

        self.layout.addStretch()

    def optimization_selection(self):
        if self.excellon_optimization_radio.get_value() == 'M':
            self.optimization_time_label.setDisabled(False)
            self.optimization_time_entry.setDisabled(False)
        else:
            self.optimization_time_label.setDisabled(True)
            self.optimization_time_entry.setDisabled(True)


class ExcellonOptPrefGroupUI(OptionsGroupUI):

    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Excellon Options", parent=parent)
        super(ExcellonOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Excellon Options")))

        # ## Create CNC Job
        self.cncjob_label = QtWidgets.QLabel(_('<b>Create CNC Job</b>'))
        self.cncjob_label.setToolTip(
            _("Parameters used to create a CNC Job object\n"
              "for this drill object.")
        )
        self.layout.addWidget(self.cncjob_label)

        grid2 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid2)

        cutzlabel = QtWidgets.QLabel(_('Cut Z:'))
        cutzlabel.setToolTip(
            _("Drill depth (negative)\n"
              "below the copper surface.")
        )
        grid2.addWidget(cutzlabel, 0, 0)
        self.cutz_entry = LengthEntry()
        grid2.addWidget(self.cutz_entry, 0, 1)

        travelzlabel = QtWidgets.QLabel(_('Travel Z:'))
        travelzlabel.setToolTip(
            _("Tool height when travelling\n"
              "across the XY plane.")
        )
        grid2.addWidget(travelzlabel, 1, 0)
        self.travelz_entry = LengthEntry()
        grid2.addWidget(self.travelz_entry, 1, 1)

        # Tool change:
        toolchlabel = QtWidgets.QLabel(_("Tool change:"))
        toolchlabel.setToolTip(
            _("Include tool-change sequence\n"
              "in G-Code (Pause for tool change).")
        )
        self.toolchange_cb = FCCheckBox()
        grid2.addWidget(toolchlabel, 2, 0)
        grid2.addWidget(self.toolchange_cb, 2, 1)

        toolchangezlabel = QtWidgets.QLabel(_('Toolchange Z:'))
        toolchangezlabel.setToolTip(
            _("Toolchange Z position.")
        )
        grid2.addWidget(toolchangezlabel, 3, 0)
        self.toolchangez_entry = LengthEntry()
        grid2.addWidget(self.toolchangez_entry, 3, 1)

        frlabel = QtWidgets.QLabel(_('Feedrate:'))
        frlabel.setToolTip(
            _("Tool speed while drilling\n"
              "(in units per minute).")
        )
        grid2.addWidget(frlabel, 4, 0)
        self.feedrate_entry = LengthEntry()
        grid2.addWidget(self.feedrate_entry, 4, 1)

        # Spindle speed
        spdlabel = QtWidgets.QLabel(_('Spindle Speed:'))
        spdlabel.setToolTip(
            _("Speed of the spindle\n"
              "in RPM (optional)")
        )
        grid2.addWidget(spdlabel, 5, 0)
        self.spindlespeed_entry = IntEntry(allow_empty=True)
        grid2.addWidget(self.spindlespeed_entry, 5, 1)

        # Spindle direction
        spindle_dir_label = QtWidgets.QLabel(_('Spindle dir.:'))
        spindle_dir_label.setToolTip(
            _("This sets the direction that the spindle is rotating.\n"
              "It can be either:\n"
              "- CW = clockwise or\n"
              "- CCW = counter clockwise")
        )

        self.spindledir_radio = RadioSet([{'label': 'CW', 'value': 'CW'},
                                          {'label': 'CCW', 'value': 'CCW'}])
        grid2.addWidget(spindle_dir_label, 6, 0)
        grid2.addWidget(self.spindledir_radio, 6, 1)

        # Dwell
        dwelllabel = QtWidgets.QLabel(_('Dwell:'))
        dwelllabel.setToolTip(
            _("Pause to allow the spindle to reach its\n"
              "speed before cutting.")
        )
        dwelltime = QtWidgets.QLabel(_('Duration:'))
        dwelltime.setToolTip(
            _("Number of milliseconds for spindle to dwell.")
        )
        self.dwell_cb = FCCheckBox()
        self.dwelltime_entry = FCEntry()
        grid2.addWidget(dwelllabel, 7, 0)
        grid2.addWidget(self.dwell_cb, 7, 1)
        grid2.addWidget(dwelltime, 8, 0)
        grid2.addWidget(self.dwelltime_entry, 8, 1)

        self.ois_dwell_exc = OptionalInputSection(self.dwell_cb, [self.dwelltime_entry])

        # postprocessor selection
        pp_excellon_label = QtWidgets.QLabel(_("Postprocessor:"))
        pp_excellon_label.setToolTip(
            _("The postprocessor file that dictates\n"
              "gcode output.")
        )
        grid2.addWidget(pp_excellon_label, 9, 0)
        self.pp_excellon_name_cb = FCComboBox()
        self.pp_excellon_name_cb.setFocusPolicy(Qt.StrongFocus)
        grid2.addWidget(self.pp_excellon_name_cb, 9, 1)

        # ### Choose what to use for Gcode creation: Drills, Slots or Both
        excellon_gcode_type_label = QtWidgets.QLabel(_('<b>Gcode:    </b>'))
        excellon_gcode_type_label.setToolTip(
            _("Choose what to use for GCode generation:\n"
              "'Drills', 'Slots' or 'Both'.\n"
              "When choosing 'Slots' or 'Both', slots will be\n"
              "converted to drills.")
        )
        self.excellon_gcode_type_radio = RadioSet([{'label': 'Drills', 'value': 'drills'},
                                                   {'label': 'Slots', 'value': 'slots'},
                                                   {'label': 'Both', 'value': 'both'}])
        grid2.addWidget(excellon_gcode_type_label, 10, 0)
        grid2.addWidget(self.excellon_gcode_type_radio, 10, 1)

        # until I decide to implement this feature those remain disabled
        excellon_gcode_type_label.hide()
        self.excellon_gcode_type_radio.setVisible(False)

        # ### Milling Holes ## ##
        self.mill_hole_label = QtWidgets.QLabel(_('<b>Mill Holes</b>'))
        self.mill_hole_label.setToolTip(
            _("Create Geometry for milling holes.")
        )
        grid2.addWidget(excellon_gcode_type_label, 11, 0, 1, 2)

        tdlabel = QtWidgets.QLabel(_('Drill Tool dia:'))
        tdlabel.setToolTip(
            _("Diameter of the cutting tool.")
        )
        grid2.addWidget(tdlabel, 12, 0)
        self.tooldia_entry = LengthEntry()
        grid2.addWidget(self.tooldia_entry, 12, 1)
        stdlabel = QtWidgets.QLabel(_('Slot Tool dia:'))
        stdlabel.setToolTip(
            _("Diameter of the cutting tool\n"
              "when milling slots.")
        )
        grid2.addWidget(stdlabel, 13, 0)
        self.slot_tooldia_entry = LengthEntry()
        grid2.addWidget(self.slot_tooldia_entry, 13, 1)

        grid4 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid4)

        # Adding the Excellon Format Defaults Button
        self.excellon_defaults_button = QtWidgets.QPushButton()
        self.excellon_defaults_button.setText(str(_("Defaults")))
        self.excellon_defaults_button.setFixedWidth(80)
        grid4.addWidget(self.excellon_defaults_button, 0, 0, QtCore.Qt.AlignRight)

        self.layout.addStretch()


class ExcellonAdvOptPrefGroupUI(OptionsGroupUI):

    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Excellon Advanced Options", parent=parent)
        super(ExcellonAdvOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Excellon Adv. Options")))

        # #######################
        # ## ADVANCED OPTIONS ###
        # #######################

        self.cncjob_label = QtWidgets.QLabel(_('<b>Advanced Options:</b>'))
        self.cncjob_label.setToolTip(
            _("Parameters used to create a CNC Job object\n"
              "for this drill object that are shown when App Level is Advanced.")
        )
        self.layout.addWidget(self.cncjob_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        offsetlabel = QtWidgets.QLabel(_('Offset Z:'))
        offsetlabel.setToolTip(
            _("Some drill bits (the larger ones) need to drill deeper\n"
              "to create the desired exit hole diameter due of the tip shape.\n"
              "The value here can compensate the Cut Z parameter."))
        grid1.addWidget(offsetlabel, 0, 0)
        self.offset_entry = LengthEntry()
        grid1.addWidget(self.offset_entry, 0, 1)

        toolchange_xy_label = QtWidgets.QLabel(_('Toolchange X,Y:'))
        toolchange_xy_label.setToolTip(
            _("Toolchange X,Y position.")
        )
        grid1.addWidget(toolchange_xy_label, 1, 0)
        self.toolchangexy_entry = FCEntry()
        grid1.addWidget(self.toolchangexy_entry, 1, 1)

        startzlabel = QtWidgets.QLabel(_('Start move Z:'))
        startzlabel.setToolTip(
            _("Height of the tool just after start.\n"
              "Delete the value if you don't need this feature.")
        )
        grid1.addWidget(startzlabel, 2, 0)
        self.estartz_entry = FloatEntry()
        grid1.addWidget(self.estartz_entry, 2, 1)

        endzlabel = QtWidgets.QLabel(_('End move Z:'))
        endzlabel.setToolTip(
            _("Height of the tool after\n"
              "the last move at the end of the job.")
        )
        grid1.addWidget(endzlabel, 3, 0)
        self.eendz_entry = LengthEntry()
        grid1.addWidget(self.eendz_entry, 3, 1)

        fr_rapid_label = QtWidgets.QLabel(_('Feedrate Rapids:'))
        fr_rapid_label.setToolTip(
            _("Tool speed while drilling\n"
              "(in units per minute).\n"
              "This is for the rapid move G00.\n"
              "It is useful only for Marlin,\n"
              "ignore for any other cases.")
        )
        grid1.addWidget(fr_rapid_label, 4, 0)
        self.feedrate_rapid_entry = LengthEntry()
        grid1.addWidget(self.feedrate_rapid_entry, 4, 1)

        # Probe depth
        self.pdepth_label = QtWidgets.QLabel(_("Probe Z depth:"))
        self.pdepth_label.setToolTip(
            _("The maximum depth that the probe is allowed\n"
              "to probe. Negative value, in current units.")
        )
        grid1.addWidget(self.pdepth_label, 5, 0)
        self.pdepth_entry = FCEntry()
        grid1.addWidget(self.pdepth_entry, 5, 1)

        # Probe feedrate
        self.feedrate_probe_label = QtWidgets.QLabel(_("Feedrate Probe:"))
        self.feedrate_probe_label.setToolTip(
           _( "The feedrate used while the probe is probing.")
        )
        grid1.addWidget(self.feedrate_probe_label, 6, 0)
        self.feedrate_probe_entry = FCEntry()
        grid1.addWidget(self.feedrate_probe_entry, 6, 1)

        fplungelabel = QtWidgets.QLabel(_('Fast Plunge:'))
        fplungelabel.setToolTip(
            _("By checking this, the vertical move from\n"
              "Z_Toolchange to Z_move is done with G0,\n"
              "meaning the fastest speed available.\n"
              "WARNING: the move is done at Toolchange X,Y coords.")
        )
        self.fplunge_cb = FCCheckBox()
        grid1.addWidget(fplungelabel, 7, 0)
        grid1.addWidget(self.fplunge_cb, 7, 1)

        fretractlabel = QtWidgets.QLabel(_('Fast Retract:'))
        fretractlabel.setToolTip(
            _("Exit hole strategy.\n"
              " - When uncheked, while exiting the drilled hole the drill bit\n"
              "will travel slow, with set feedrate (G1), up to zero depth and then\n"
              "travel as fast as possible (G0) to the Z Move (travel height).\n"
              " - When checked the travel from Z cut (cut depth) to Z_move\n"
              "(travel height) is done as fast as possible (G0) in one move.")
        )
        self.fretract_cb = FCCheckBox()
        grid1.addWidget(fretractlabel, 8, 0)
        grid1.addWidget(self.fretract_cb, 8, 1)

        self.layout.addStretch()


class ExcellonExpPrefGroupUI(OptionsGroupUI):

    def __init__(self, parent=None):
        super(ExcellonExpPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Excellon Export")))

        # Plot options
        self.export_options_label = QtWidgets.QLabel(_("<b>Export Options:</b>"))
        self.export_options_label.setToolTip(
            _("The parameters set here are used in the file exported\n"
              "when using the File -> Export -> Export Excellon menu entry.")
        )
        self.layout.addWidget(self.export_options_label)

        form = QtWidgets.QFormLayout()
        self.layout.addLayout(form)

        # Excellon Units
        self.excellon_units_label = QtWidgets.QLabel(_('<b>Units</b>:'))
        self.excellon_units_label.setToolTip(
            _("The units used in the Excellon file.")
        )

        self.excellon_units_radio = RadioSet([{'label': 'INCH', 'value': 'INCH'},
                                              {'label': 'MM', 'value': 'METRIC'}])
        self.excellon_units_radio.setToolTip(
            _("The units used in the Excellon file.")
        )

        form.addRow(self.excellon_units_label, self.excellon_units_radio)

        # Excellon non-decimal format
        self.digits_label = QtWidgets.QLabel(_("<b>Int/Decimals:</b>"))
        self.digits_label.setToolTip(
            _("The NC drill files, usually named Excellon files\n"
              "are files that can be found in different formats.\n"
              "Here we set the format used when the provided\n"
              "coordinates are not using period.")
        )

        hlay1 = QtWidgets.QHBoxLayout()

        self.format_whole_entry = IntEntry()
        self.format_whole_entry.setMaxLength(1)
        self.format_whole_entry.setAlignment(QtCore.Qt.AlignRight)
        self.format_whole_entry.setFixedWidth(30)
        self.format_whole_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the whole part of Excellon coordinates.")
        )
        hlay1.addWidget(self.format_whole_entry, QtCore.Qt.AlignLeft)

        excellon_separator_label= QtWidgets.QLabel(':')
        excellon_separator_label.setFixedWidth(5)
        hlay1.addWidget(excellon_separator_label, QtCore.Qt.AlignLeft)

        self.format_dec_entry = IntEntry()
        self.format_dec_entry.setMaxLength(1)
        self.format_dec_entry.setAlignment(QtCore.Qt.AlignRight)
        self.format_dec_entry.setFixedWidth(30)
        self.format_dec_entry.setToolTip(
            _("This numbers signify the number of digits in\n"
              "the decimal part of Excellon coordinates.")
        )
        hlay1.addWidget(self.format_dec_entry, QtCore.Qt.AlignLeft)
        hlay1.addStretch()

        form.addRow(self.digits_label, hlay1)

        # Select the Excellon Format
        self.format_label = QtWidgets.QLabel(_("<b>Format:</b>"))
        self.format_label.setToolTip(
            _("Select the kind of coordinates format used.\n"
              "Coordinates can be saved with decimal point or without.\n"
              "When there is no decimal point, it is required to specify\n"
              "the number of digits for integer part and the number of decimals.\n"
              "Also it will have to be specified if LZ = leading zeros are kept\n"
              "or TZ = trailing zeros are kept.")
        )
        self.format_radio = RadioSet([{'label': 'Decimal', 'value': 'dec'},
                                      {'label': 'No-Decimal', 'value': 'ndec'}])
        self.format_radio.setToolTip(
            _("Select the kind of coordinates format used.\n"
              "Coordinates can be saved with decimal point or without.\n"
              "When there is no decimal point, it is required to specify\n"
              "the number of digits for integer part and the number of decimals.\n"
              "Also it will have to be specified if LZ = leading zeros are kept\n"
              "or TZ = trailing zeros are kept.")
        )

        form.addRow(self.format_label, self.format_radio)

        # Excellon Zeros
        self.zeros_label = QtWidgets.QLabel(_('<b>Zeros</b>:'))
        self.zeros_label.setAlignment(QtCore.Qt.AlignLeft)
        self.zeros_label.setToolTip(
            _("This sets the type of Excellon zeros.\n"
              "If LZ then Leading Zeros are kept and\n"
              "Trailing Zeros are removed.\n"
              "If TZ is checked then Trailing Zeros are kept\n"
              "and Leading Zeros are removed.")
        )

        self.zeros_radio = RadioSet([{'label': 'LZ', 'value': 'LZ'},
                                     {'label': 'TZ', 'value': 'TZ'}])
        self.zeros_radio.setToolTip(
            _("This sets the default type of Excellon zeros.\n"
              "If LZ then Leading Zeros are kept and\n"
              "Trailing Zeros are removed.\n"
              "If TZ is checked then Trailing Zeros are kept\n"
              "and Leading Zeros are removed.")
        )

        form.addRow(self.zeros_label, self.zeros_radio)

        self.layout.addStretch()
        self.format_radio.activated_custom.connect(self.optimization_selection)

    def optimization_selection(self):
        if self.format_radio.get_value() == 'dec':
            self.zeros_label.setDisabled(True)
            self.zeros_radio.setDisabled(True)
        else:
            self.zeros_label.setDisabled(False)
            self.zeros_radio.setDisabled(False)


class ExcellonEditorPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        super(ExcellonEditorPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Excellon Editor")))

        # Excellon Editor Parameters
        self.param_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.param_label.setToolTip(
            _("A list of Excellon Editor parameters.")
        )
        self.layout.addWidget(self.param_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Selection Limit
        self.sel_limit_label = QtWidgets.QLabel(_("Selection limit:"))
        self.sel_limit_label.setToolTip(
            _("Set the number of selected Excellon geometry\n"
              "items above which the utility geometry\n"
              "becomes just a selection rectangle.\n"
              "Increases the performance when moving a\n"
              "large number of geometric elements.")
        )
        self.sel_limit_entry = IntEntry()

        grid0.addWidget(self.sel_limit_label, 0, 0)
        grid0.addWidget(self.sel_limit_entry, 0, 1)

        # New tool diameter
        self.addtool_entry_lbl = QtWidgets.QLabel(_('New Tool Dia:'))
        self.addtool_entry_lbl.setToolTip(
            _("Diameter for the new tool")
        )

        self.addtool_entry = FCEntry()
        self.addtool_entry.setValidator(QtGui.QDoubleValidator(0.0001, 99.9999, 4))

        grid0.addWidget(self.addtool_entry_lbl, 1, 0)
        grid0.addWidget(self.addtool_entry, 1, 1)

        # Number of drill holes in a drill array
        self.drill_array_size_label = QtWidgets.QLabel(_('Nr of drills:'))
        self.drill_array_size_label.setToolTip(
            _("Specify how many drills to be in the array.")
        )
        # self.drill_array_size_label.setFixedWidth(100)

        self.drill_array_size_entry = LengthEntry()

        grid0.addWidget(self.drill_array_size_label, 2, 0)
        grid0.addWidget(self.drill_array_size_entry, 2, 1)

        self.drill_array_linear_label = QtWidgets.QLabel(_('<b>Linear Drill Array:</b>'))
        grid0.addWidget(self.drill_array_linear_label, 3, 0, 1, 2)

        # Linear Drill Array direction
        self.drill_axis_label = QtWidgets.QLabel(_('Linear Dir.:'))
        self.drill_axis_label.setToolTip(
            _("Direction on which the linear array is oriented:\n"
              "- 'X' - horizontal axis \n"
              "- 'Y' - vertical axis or \n"
              "- 'Angle' - a custom angle for the array inclination")
        )
        # self.drill_axis_label.setFixedWidth(100)
        self.drill_axis_radio = RadioSet([{'label': 'X', 'value': 'X'},
                                          {'label': 'Y', 'value': 'Y'},
                                          {'label': 'Angle', 'value': 'A'}])

        grid0.addWidget(self.drill_axis_label, 4, 0)
        grid0.addWidget(self.drill_axis_radio, 4, 1)

        # Linear Drill Array pitch distance
        self.drill_pitch_label = QtWidgets.QLabel(_('Pitch:'))
        self.drill_pitch_label.setToolTip(
            _("Pitch = Distance between elements of the array.")
        )
        # self.drill_pitch_label.setFixedWidth(100)
        self.drill_pitch_entry = LengthEntry()

        grid0.addWidget(self.drill_pitch_label, 5, 0)
        grid0.addWidget(self.drill_pitch_entry, 5, 1)

        # Linear Drill Array custom angle
        self.drill_angle_label = QtWidgets.QLabel(_('Angle:'))
        self.drill_angle_label.setToolTip(
            _("Angle at which each element in circular array is placed.")
        )
        self.drill_angle_entry = LengthEntry()

        grid0.addWidget(self.drill_angle_label, 6, 0)
        grid0.addWidget(self.drill_angle_entry, 6, 1)

        self.drill_array_circ_label = QtWidgets.QLabel(_('<b>Circular Drill Array:</b>'))
        grid0.addWidget(self.drill_array_circ_label, 7, 0, 1, 2)

        # Circular Drill Array direction
        self.drill_circular_direction_label = QtWidgets.QLabel(_('Circular Dir.:'))
        self.drill_circular_direction_label.setToolTip(
            _("Direction for circular array.\n"
              "Can be CW = clockwise or CCW = counter clockwise.")
        )

        self.drill_circular_dir_radio = RadioSet([{'label': 'CW', 'value': 'CW'},
                                                  {'label': 'CCW.', 'value': 'CCW'}])

        grid0.addWidget(self.drill_circular_direction_label, 8, 0)
        grid0.addWidget(self.drill_circular_dir_radio, 8, 1)

        # Circular Drill Array Angle
        self.drill_circular_angle_label = QtWidgets.QLabel(_('Circ. Angle:'))
        self.drill_circular_angle_label.setToolTip(
            _("Angle at which each element in circular array is placed.")
        )
        self.drill_circular_angle_entry = LengthEntry()

        grid0.addWidget(self.drill_circular_angle_label, 9, 0)
        grid0.addWidget(self.drill_circular_angle_entry, 9, 1)

        self.layout.addStretch()


class GeometryGenPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Geometry General Preferences", parent=parent)
        super(GeometryGenPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Geometry General")))

        # ## Plot options
        self.plot_options_label = QtWidgets.QLabel(_("<b>Plot Options:</b>"))
        self.layout.addWidget(self.plot_options_label)

        # Plot CB
        self.plot_cb = FCCheckBox(label=_('Plot'))
        self.plot_cb.setToolTip(
            _("Plot (show) this object.")
        )
        self.layout.addWidget(self.plot_cb)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Number of circle steps for circular aperture linear approximation
        self.circle_steps_label = QtWidgets.QLabel(_("Circle Steps:"))
        self.circle_steps_label.setToolTip(
            _("The number of circle steps for <b>Geometry</b> \n"
              "circle and arc shapes linear approximation.")
        )
        grid0.addWidget(self.circle_steps_label, 1, 0)
        self.circle_steps_entry = IntEntry()
        grid0.addWidget(self.circle_steps_entry, 1, 1)

        # Tools
        self.tools_label = QtWidgets.QLabel(_("<b>Tools:</b>"))
        grid0.addWidget(self.tools_label, 2, 0, 1, 2)

        # Tooldia
        tdlabel = QtWidgets.QLabel(_('Tool dia:'))
        tdlabel.setToolTip(
            _("Diameters of the cutting tools, separated by ','")
        )
        grid0.addWidget(tdlabel, 3, 0)
        self.cnctooldia_entry = FCEntry()
        grid0.addWidget(self.cnctooldia_entry, 3, 1)

        self.layout.addStretch()


class GeometryOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Geometry Options Preferences", parent=parent)
        super(GeometryOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Geometry Options")))

        # ------------------------------
        # ## Create CNC Job
        # ------------------------------
        self.cncjob_label = QtWidgets.QLabel(_('<b>Create CNC Job:</b>'))
        self.cncjob_label.setToolTip(
            _("Create a CNC Job object\n"
              "tracing the contours of this\n"
              "Geometry object.")
        )
        self.layout.addWidget(self.cncjob_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        # Cut Z
        cutzlabel = QtWidgets.QLabel(_('Cut Z:'))
        cutzlabel.setToolTip(
            _("Cutting depth (negative)\n"
              "below the copper surface.")
        )
        grid1.addWidget(cutzlabel, 0, 0)
        self.cutz_entry = LengthEntry()
        grid1.addWidget(self.cutz_entry, 0, 1)

        # Multidepth CheckBox
        self.multidepth_cb = FCCheckBox(label=_('Multidepth'))
        self.multidepth_cb.setToolTip(
            _("Multidepth usage: True or False.")
        )
        grid1.addWidget(self.multidepth_cb, 1, 0)

        # Depth/pass
        dplabel = QtWidgets.QLabel(_('Depth/Pass:'))
        dplabel.setToolTip(
            _("The depth to cut on each pass,\n"
              "when multidepth is enabled.\n"
              "It has positive value although\n"
              "it is a fraction from the depth\n"
              "which has negative value.")
        )

        grid1.addWidget(dplabel, 2, 0)
        self.depthperpass_entry = LengthEntry()
        grid1.addWidget(self.depthperpass_entry, 2, 1)

        self.ois_multidepth = OptionalInputSection(self.multidepth_cb, [self.depthperpass_entry])

        # Travel Z
        travelzlabel = QtWidgets.QLabel(_('Travel Z:'))
        travelzlabel.setToolTip(
            _("Height of the tool when\n"
              "moving without cutting.")
        )
        grid1.addWidget(travelzlabel, 3, 0)
        self.travelz_entry = LengthEntry()
        grid1.addWidget(self.travelz_entry, 3, 1)

        # Tool change:
        toolchlabel = QtWidgets.QLabel(_("Tool change:"))
        toolchlabel.setToolTip(
            _("Include tool-change sequence\n"
              "in G-Code (Pause for tool change).")
        )
        self.toolchange_cb = FCCheckBox()
        grid1.addWidget(toolchlabel, 4, 0)
        grid1.addWidget(self.toolchange_cb, 4, 1)

        # Toolchange Z
        toolchangezlabel = QtWidgets.QLabel(_('Toolchange Z:'))
        toolchangezlabel.setToolTip(
            _("Toolchange Z position.")
        )
        grid1.addWidget(toolchangezlabel, 5, 0)
        self.toolchangez_entry = LengthEntry()
        grid1.addWidget(self.toolchangez_entry, 5, 1)

        # Feedrate X-Y
        frlabel = QtWidgets.QLabel(_('Feed Rate X-Y:'))
        frlabel.setToolTip(
            _("Cutting speed in the XY\n"
              "plane in units per minute")
        )
        grid1.addWidget(frlabel, 6, 0)
        self.cncfeedrate_entry = LengthEntry()
        grid1.addWidget(self.cncfeedrate_entry, 6, 1)

        # Feedrate Z (Plunge)
        frz_label = QtWidgets.QLabel(_('Feed Rate Z:'))
        frz_label.setToolTip(
            _("Cutting speed in the XY\n"
              "plane in units per minute.\n"
              "It is called also Plunge.")
        )
        grid1.addWidget(frz_label, 7, 0)
        self.cncplunge_entry = LengthEntry()
        grid1.addWidget(self.cncplunge_entry, 7, 1)

        # Spindle Speed
        spdlabel = QtWidgets.QLabel(_('Spindle speed:'))
        spdlabel.setToolTip(
            _("Speed of the spindle\n"
              "in RPM (optional)")
        )
        grid1.addWidget(spdlabel, 8, 0)
        self.cncspindlespeed_entry = IntEntry(allow_empty=True)
        grid1.addWidget(self.cncspindlespeed_entry, 8, 1)

        # Spindle direction
        spindle_dir_label = QtWidgets.QLabel(_('Spindle dir.:'))
        spindle_dir_label.setToolTip(
            _("This sets the direction that the spindle is rotating.\n"
              "It can be either:\n"
              "- CW = clockwise or\n"
              "- CCW = counter clockwise")
        )

        self.spindledir_radio = RadioSet([{'label': 'CW', 'value': 'CW'},
                                          {'label': 'CCW', 'value': 'CCW'}])
        grid1.addWidget(spindle_dir_label, 9, 0)
        grid1.addWidget(self.spindledir_radio, 9, 1)

        # Dwell
        self.dwell_cb = FCCheckBox(label=_('Dwell:'))
        self.dwell_cb.setToolTip(
            _("Pause to allow the spindle to reach its\n"
              "speed before cutting.")
        )
        dwelltime = QtWidgets.QLabel(_('Duration:'))
        dwelltime.setToolTip(
            _("Number of milliseconds for spindle to dwell.")
        )
        self.dwelltime_entry = FCEntry()
        grid1.addWidget(self.dwell_cb, 10, 0)
        grid1.addWidget(dwelltime, 11, 0)
        grid1.addWidget(self.dwelltime_entry, 11, 1)

        self.ois_dwell = OptionalInputSection(self.dwell_cb, [self.dwelltime_entry])

        # postprocessor selection
        pp_label = QtWidgets.QLabel(_("Postprocessor:"))
        pp_label.setToolTip(
            _("The postprocessor file that dictates\n"
              "Machine Code output.")
        )
        grid1.addWidget(pp_label, 12, 0)
        self.pp_geometry_name_cb = FCComboBox()
        self.pp_geometry_name_cb.setFocusPolicy(Qt.StrongFocus)
        grid1.addWidget(self.pp_geometry_name_cb, 12, 1)

        self.layout.addStretch()


class GeometryAdvOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Geometry Advanced Options Preferences", parent=parent)
        super(GeometryAdvOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Geometry Adv. Options")))

        # ------------------------------
        # ## Advanced Options
        # ------------------------------
        self.cncjob_label = QtWidgets.QLabel(_('<b>Advanced Options:</b>'))
        self.cncjob_label.setToolTip(
            _("Parameters to create a CNC Job object\n"
              "tracing the contours of a Geometry object.")
        )
        self.layout.addWidget(self.cncjob_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        # Toolchange X,Y
        toolchange_xy_label = QtWidgets.QLabel(_('Toolchange X,Y:'))
        toolchange_xy_label.setToolTip(
            _("Toolchange X,Y position.")
        )
        grid1.addWidget(toolchange_xy_label, 1, 0)
        self.toolchangexy_entry = FCEntry()
        grid1.addWidget(self.toolchangexy_entry, 1, 1)

        # Start move Z
        startzlabel = QtWidgets.QLabel(_('Start move Z:'))
        startzlabel.setToolTip(
            _("Height of the tool just after starting the work.\n"
              "Delete the value if you don't need this feature.")
        )
        grid1.addWidget(startzlabel, 2, 0)
        self.gstartz_entry = FloatEntry()
        grid1.addWidget(self.gstartz_entry, 2, 1)

        # End move Z
        endzlabel = QtWidgets.QLabel(_('End move Z:'))
        endzlabel.setToolTip(
            _("Height of the tool after\n"
              "the last move at the end of the job.")
        )
        grid1.addWidget(endzlabel, 3, 0)
        self.gendz_entry = LengthEntry()
        grid1.addWidget(self.gendz_entry, 3, 1)

        # Feedrate rapids
        fr_rapid_label = QtWidgets.QLabel(_('Feedrate Rapids:'))
        fr_rapid_label.setToolTip(
            _("Cutting speed in the XY plane\n"
              "(in units per minute).\n"
              "This is for the rapid move G00.\n"
              "It is useful only for Marlin,\n"
              "ignore for any other cases."
            )
        )
        grid1.addWidget(fr_rapid_label, 4, 0)
        self.cncfeedrate_rapid_entry = LengthEntry()
        grid1.addWidget(self.cncfeedrate_rapid_entry, 4, 1)

        # End move extra cut
        self.extracut_cb = FCCheckBox(label=_('Re-cut 1st pt.'))
        self.extracut_cb.setToolTip(
            _("In order to remove possible\n"
              "copper leftovers where first cut\n"
              "meet with last cut, we generate an\n"
              "extended cut over the first cut section.")
        )
        grid1.addWidget(self.extracut_cb, 5, 0)

        # Probe depth
        self.pdepth_label = QtWidgets.QLabel(_("Probe Z depth:"))
        self.pdepth_label.setToolTip(
            _("The maximum depth that the probe is allowed\n"
              "to probe. Negative value, in current units.")
        )
        grid1.addWidget(self.pdepth_label, 6, 0)
        self.pdepth_entry = FCEntry()
        grid1.addWidget(self.pdepth_entry, 6, 1)

        # Probe feedrate
        self.feedrate_probe_label = QtWidgets.QLabel(_("Feedrate Probe:"))
        self.feedrate_probe_label.setToolTip(
            _("The feedrate used while the probe is probing.")
        )
        grid1.addWidget(self.feedrate_probe_label, 7, 0)
        self.feedrate_probe_entry = FCEntry()
        grid1.addWidget(self.feedrate_probe_entry, 7, 1)

        # Fast Move from Z Toolchange
        fplungelabel = QtWidgets.QLabel(_('Fast Plunge:'))
        fplungelabel.setToolTip(
            _("By checking this, the vertical move from\n"
              "Z_Toolchange to Z_move is done with G0,\n"
              "meaning the fastest speed available.\n"
              "WARNING: the move is done at Toolchange X,Y coords.")
        )
        self.fplunge_cb = FCCheckBox()
        grid1.addWidget(fplungelabel, 8, 0)
        grid1.addWidget(self.fplunge_cb, 8, 1)

        # Size of trace segment on X axis
        segx_label = QtWidgets.QLabel(_("Seg. X size:"))
        segx_label.setToolTip(
            _("The size of the trace segment on the X axis.\n"
              "Useful for auto-leveling.\n"
              "A value of 0 means no segmentation on the X axis.")
        )
        grid1.addWidget(segx_label, 9, 0)
        self.segx_entry = FCEntry()
        grid1.addWidget(self.segx_entry, 9, 1)

        # Size of trace segment on Y axis
        segy_label = QtWidgets.QLabel(_("Seg. Y size:"))
        segy_label.setToolTip(
            _("The size of the trace segment on the Y axis.\n"
              "Useful for auto-leveling.\n"
              "A value of 0 means no segmentation on the Y axis.")
        )
        grid1.addWidget(segy_label, 10, 0)
        self.segy_entry = FCEntry()
        grid1.addWidget(self.segy_entry, 10, 1)

        self.layout.addStretch()


class GeometryEditorPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Gerber Adv. Options Preferences", parent=parent)
        super(GeometryEditorPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Geometry Editor")))

        # Advanced Geometry Parameters
        self.param_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.param_label.setToolTip(
            _("A list of Geometry Editor parameters.")
        )
        self.layout.addWidget(self.param_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Selection Limit
        self.sel_limit_label = QtWidgets.QLabel(_("Selection limit:"))
        self.sel_limit_label.setToolTip(
            _("Set the number of selected geometry\n"
              "items above which the utility geometry\n"
              "becomes just a selection rectangle.\n"
              "Increases the performance when moving a\n"
              "large number of geometric elements.")
        )
        self.sel_limit_entry = IntEntry()

        grid0.addWidget(self.sel_limit_label, 0, 0)
        grid0.addWidget(self.sel_limit_entry, 0, 1)

        self.layout.addStretch()


class CNCJobGenPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "CNC Job General Preferences", parent=None)
        super(CNCJobGenPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("CNC Job General")))

        # ## Plot options
        self.plot_options_label = QtWidgets.QLabel(_("<b>Plot Options:</b>"))
        self.layout.addWidget(self.plot_options_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)
        grid0.setColumnStretch(1, 1)
        grid0.setColumnStretch(2, 1)

        # Plot CB
        # self.plot_cb = QtWidgets.QCheckBox('Plot')
        self.plot_cb = FCCheckBox(_('Plot Object'))
        self.plot_cb.setToolTip(
            "Plot (show) this object."
        )
        grid0.addWidget(self.plot_cb, 0, 0)

        # Plot Kind
        self.cncplot_method_label = QtWidgets.QLabel(_("Plot kind:"))
        self.cncplot_method_label.setToolTip(
            _("This selects the kind of geometries on the canvas to plot.\n"
              "Those can be either of type 'Travel' which means the moves\n"
              "above the work piece or it can be of type 'Cut',\n"
              "which means the moves that cut into the material.")
        )

        self.cncplot_method_radio = RadioSet([
            {"label": "All", "value": "all"},
            {"label": "Travel", "value": "travel"},
            {"label": "Cut", "value": "cut"}
        ], stretch=False)

        grid0.addWidget(self.cncplot_method_label, 1, 0)
        grid0.addWidget(self.cncplot_method_radio, 1, 1)
        grid0.addWidget(QtWidgets.QLabel(''), 1, 2)

        # Display Annotation
        self.annotation_label = QtWidgets.QLabel(_("Display Annotation:"))
        self.annotation_label.setToolTip(
            _("This selects if to display text annotation on the plot.\n"
              "When checked it will display numbers in order for each end\n"
              "of a travel line."
            )
        )
        self.annotation_cb = FCCheckBox()

        grid0.addWidget(self.annotation_label, 2, 0)
        grid0.addWidget(self.annotation_cb, 2, 1)
        grid0.addWidget(QtWidgets.QLabel(''), 2, 2)

        # Annotation Font Size
        self.annotation_fontsize_label = QtWidgets.QLabel(_("Annotation Size:"))
        self.annotation_fontsize_label.setToolTip(
            _("The font size of the annotation text. In pixels.")
        )
        grid0.addWidget(self.annotation_fontsize_label, 3, 0)
        self.annotation_fontsize_sp = FCSpinner()
        grid0.addWidget(self.annotation_fontsize_sp, 3, 1)
        grid0.addWidget(QtWidgets.QLabel(''), 3, 2)

        # Annotation Font Color
        self.annotation_color_label = QtWidgets.QLabel(_('Annotation Color:'))
        self.annotation_color_label.setToolTip(
            _("Set the font color for the annotation texts.")
        )
        self.annotation_fontcolor_entry = FCEntry()
        self.annotation_fontcolor_button = QtWidgets.QPushButton()
        self.annotation_fontcolor_button.setFixedSize(15, 15)

        self.form_box_child = QtWidgets.QHBoxLayout()
        self.form_box_child.setContentsMargins(0, 0, 0, 0)
        self.form_box_child.addWidget(self.annotation_fontcolor_entry)
        self.form_box_child.addWidget(self.annotation_fontcolor_button, alignment=Qt.AlignRight)
        self.form_box_child.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        color_widget = QtWidgets.QWidget()
        color_widget.setLayout(self.form_box_child)
        grid0.addWidget(self.annotation_color_label, 4, 0)
        grid0.addWidget(color_widget, 4, 1)
        grid0.addWidget(QtWidgets.QLabel(''), 4, 2)

        # ###################################################################
        # Number of circle steps for circular aperture linear approximation #
        # ###################################################################
        self.steps_per_circle_label = QtWidgets.QLabel(_("Circle Steps:"))
        self.steps_per_circle_label.setToolTip(
            _("The number of circle steps for <b>GCode</b> \n"
              "circle and arc shapes linear approximation.")
        )
        grid0.addWidget(self.steps_per_circle_label, 5, 0)
        self.steps_per_circle_entry = IntEntry()
        grid0.addWidget(self.steps_per_circle_entry, 5, 1)

        # Tool dia for plot
        tdlabel = QtWidgets.QLabel(_('Tool dia:'))
        tdlabel.setToolTip(
            _("Diameter of the tool to be\n"
              "rendered in the plot.")
        )
        grid0.addWidget(tdlabel, 6, 0)
        self.tooldia_entry = LengthEntry()
        grid0.addWidget(self.tooldia_entry,6, 1)

        # Number of decimals to use in GCODE coordinates
        cdeclabel = QtWidgets.QLabel(_('Coords dec.:'))
        cdeclabel.setToolTip(
            _("The number of decimals to be used for \n"
              "the X, Y, Z coordinates in CNC code (GCODE, etc.)")
        )
        grid0.addWidget(cdeclabel, 7, 0)
        self.coords_dec_entry = IntEntry()
        grid0.addWidget(self.coords_dec_entry, 7, 1)

        # Number of decimals to use in GCODE feedrate
        frdeclabel = QtWidgets.QLabel(_('Feedrate dec.:'))
        frdeclabel.setToolTip(
            _("The number of decimals to be used for \n"
              "the Feedrate parameter in CNC code (GCODE, etc.)")
        )
        grid0.addWidget(frdeclabel, 8, 0)
        self.fr_dec_entry = IntEntry()
        grid0.addWidget(self.fr_dec_entry, 8, 1)

        self.layout.addStretch()


class CNCJobOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "CNC Job Options Preferences", parent=None)
        super(CNCJobOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("CNC Job Options")))

        # ## Export G-Code
        self.export_gcode_label = QtWidgets.QLabel(_("<b>Export G-Code:</b>"))
        self.export_gcode_label.setToolTip(
            _("Export and save G-Code to\n"
              "make this object to a file.")
        )
        self.layout.addWidget(self.export_gcode_label)

        # Prepend to G-Code
        prependlabel = QtWidgets.QLabel(_('Prepend to G-Code:'))
        prependlabel.setToolTip(
            _("Type here any G-Code commands you would\n"
              "like to add at the beginning of the G-Code file.")
        )
        self.layout.addWidget(prependlabel)

        self.prepend_text = FCTextArea()
        self.layout.addWidget(self.prepend_text)

        # Append text to G-Code
        appendlabel = QtWidgets.QLabel(_('Append to G-Code:'))
        appendlabel.setToolTip(
            _("Type here any G-Code commands you would\n"
              "like to append to the generated file.\n"
              "I.e.: M2 (End of program)")
        )
        self.layout.addWidget(appendlabel)

        self.append_text = FCTextArea()
        self.layout.addWidget(self.append_text)

        self.layout.addStretch()


class CNCJobAdvOptPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "CNC Job Advanced Options Preferences", parent=None)
        super(CNCJobAdvOptPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("CNC Job Adv. Options")))

        # ## Export G-Code
        self.export_gcode_label = QtWidgets.QLabel(_("<b>Export G-Code:</b>"))
        self.export_gcode_label.setToolTip(
            _("Export and save G-Code to\n"
              "make this object to a file.")
        )
        self.layout.addWidget(self.export_gcode_label)

        # Prepend to G-Code
        toolchangelabel = QtWidgets.QLabel(_('Toolchange G-Code:'))
        toolchangelabel.setToolTip(
            _("Type here any G-Code commands you would\n"
              "like to be executed when Toolchange event is encountered.\n"
              "This will constitute a Custom Toolchange GCode,\n"
              "or a Toolchange Macro.")
        )
        self.layout.addWidget(toolchangelabel)

        self.toolchange_text = FCTextArea()
        self.layout.addWidget(self.toolchange_text)

        hlay = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay)

        # Toolchange Replacement GCode
        self.toolchange_cb = FCCheckBox(label=_('Use Toolchange Macro'))
        self.toolchange_cb.setToolTip(
            _("Check this box if you want to use\n"
              "a Custom Toolchange GCode (macro).")
        )
        hlay.addWidget(self.toolchange_cb)
        hlay.addStretch()

        hlay1 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(hlay1)

        # Variable list
        self.tc_variable_combo = FCComboBox()
        self.tc_variable_combo.setToolTip(
            _("A list of the FlatCAM variables that can be used\n"
              "in the Toolchange event.\n"
              "They have to be surrounded by the '%' symbol")
        )
        hlay1.addWidget(self.tc_variable_combo)

        # Populate the Combo Box
        variables = [_('Parameters'), 'tool', 'tooldia', 't_drills', 'x_toolchange', 'y_toolchange', 'z_toolchange',
                     'z_cut', 'z_move', 'z_depthpercut', 'spindlespeed', 'dwelltime']
        self.tc_variable_combo.addItems(variables)
        self.tc_variable_combo.setItemData(0, _("FlatCAM CNC parameters"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(1, _("tool = tool number"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(2, _("tooldia = tool diameter"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(3, _("t_drills = for Excellon, total number of drills"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(4, _("x_toolchange = X coord for Toolchange"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(5, _("y_toolchange = Y coord for Toolchange"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(6, _("z_toolchange = Z coord for Toolchange"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(7, _("z_cut = Z depth for the cut"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(8, _("z_move = Z height for travel"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(9, _("z_depthpercut = the step value for multidepth cut"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(10, _("spindlesspeed = the value for the spindle speed"), Qt.ToolTipRole)
        self.tc_variable_combo.setItemData(11,
                                           _("dwelltime = time to dwell to allow the spindle to reach it's set RPM"),
                                           Qt.ToolTipRole)

        hlay1.addStretch()

        # Insert Variable into the Toolchange G-Code Text Box
        # self.tc_insert_buton = FCButton("Insert")
        # self.tc_insert_buton.setToolTip(
        #     "Insert the variable in the GCode Box\n"
        #     "surrounded by the '%' symbol."
        # )
        # hlay1.addWidget(self.tc_insert_buton)

        self.layout.addStretch()


class ToolsNCCPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "NCC Tool Options", parent=parent)
        super(ToolsNCCPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("NCC Tool Options")))

        # ## Clear non-copper regions
        self.clearcopper_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.clearcopper_label.setToolTip(
            _("Create a Geometry object with\n"
              "toolpaths to cut all non-copper regions.")
        )
        self.layout.addWidget(self.clearcopper_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        ncctdlabel = QtWidgets.QLabel(_('Tools dia:'))
        ncctdlabel.setToolTip(
            _("Diameters of the cutting tools, separated by ','")
        )
        grid0.addWidget(ncctdlabel, 0, 0)
        self.ncc_tool_dia_entry = FCEntry()
        grid0.addWidget(self.ncc_tool_dia_entry, 0, 1)

        nccoverlabel = QtWidgets.QLabel(_('Overlap Rate:'))
        nccoverlabel.setToolTip(
           _( "How much (fraction) of the tool width to overlap each tool pass.\n"
              "Example:\n"
              "A value here of 0.25 means 25% from the tool diameter found above.\n\n"
              "Adjust the value starting with lower values\n"
              "and increasing it if areas that should be cleared are still \n"
              "not cleared.\n"
              "Lower values = faster processing, faster execution on PCB.\n"
              "Higher values = slow processing and slow execution on CNC\n"
              "due of too many paths.")
        )
        grid0.addWidget(nccoverlabel, 1, 0)
        self.ncc_overlap_entry = FloatEntry()
        grid0.addWidget(self.ncc_overlap_entry, 1, 1)

        nccmarginlabel = QtWidgets.QLabel(_('Margin:'))
        nccmarginlabel.setToolTip(
            _("Bounding box margin.")
        )
        grid0.addWidget(nccmarginlabel, 2, 0)
        self.ncc_margin_entry = FloatEntry()
        grid0.addWidget(self.ncc_margin_entry, 2, 1)

        # Method
        methodlabel = QtWidgets.QLabel(_('Method:'))
        methodlabel.setToolTip(
            _("Algorithm for non-copper clearing:<BR>"
              "<B>Standard</B>: Fixed step inwards.<BR>"
              "<B>Seed-based</B>: Outwards from seed.<BR>"
              "<B>Line-based</B>: Parallel lines.")
        )
        grid0.addWidget(methodlabel, 3, 0)
        self.ncc_method_radio = RadioSet([
            {"label": "Standard", "value": "standard"},
            {"label": "Seed-based", "value": "seed"},
            {"label": "Straight lines", "value": "lines"}
        ], orientation='vertical', stretch=False)
        grid0.addWidget(self.ncc_method_radio, 3, 1)

        # Connect lines
        pathconnectlabel = QtWidgets.QLabel(_("Connect:"))
        pathconnectlabel.setToolTip(
            _("Draw lines between resulting\n"
              "segments to minimize tool lifts.")
        )
        grid0.addWidget(pathconnectlabel, 4, 0)
        self.ncc_connect_cb = FCCheckBox()
        grid0.addWidget(self.ncc_connect_cb, 4, 1)

        contourlabel = QtWidgets.QLabel(_("Contour:"))
        contourlabel.setToolTip(
           _("Cut around the perimeter of the polygon\n"
             "to trim rough edges.")
        )
        grid0.addWidget(contourlabel, 5, 0)
        self.ncc_contour_cb = FCCheckBox()
        grid0.addWidget(self.ncc_contour_cb, 5, 1)

        restlabel = QtWidgets.QLabel(_("Rest M.:"))
        restlabel.setToolTip(
            _("If checked, use 'rest machining'.\n"
              "Basically it will clear copper outside PCB features,\n"
              "using the biggest tool and continue with the next tools,\n"
              "from bigger to smaller, to clear areas of copper that\n"
              "could not be cleared by previous tool.\n"
              "If not checked, use the standard algorithm.")
        )
        grid0.addWidget(restlabel, 6, 0)
        self.ncc_rest_cb = FCCheckBox()
        grid0.addWidget(self.ncc_rest_cb, 6, 1)

        self.layout.addStretch()


class ToolsCutoutPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Cutout Tool Options", parent=parent)
        super(ToolsCutoutPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Cutout Tool Options")))

        # ## Board cuttout
        self.board_cutout_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.board_cutout_label.setToolTip(
            _("Create toolpaths to cut around\n"
              "the PCB and separate it from\n"
              "the original board.")
        )
        self.layout.addWidget(self.board_cutout_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        tdclabel = QtWidgets.QLabel(_('Tool dia:'))
        tdclabel.setToolTip(
           _("Diameter of the cutting tool.")
        )
        grid0.addWidget(tdclabel, 0, 0)
        self.cutout_tooldia_entry = LengthEntry()
        grid0.addWidget(self.cutout_tooldia_entry, 0, 1)

        marginlabel = QtWidgets.QLabel(_('Margin:'))
        marginlabel.setToolTip(
            _("Distance from objects at which\n"
              "to draw the cutout.")
        )
        grid0.addWidget(marginlabel, 1, 0)
        self.cutout_margin_entry = LengthEntry()
        grid0.addWidget(self.cutout_margin_entry, 1, 1)

        gaplabel = QtWidgets.QLabel(_('Gap size:'))
        gaplabel.setToolTip(
            _("Size of the gaps in the toolpath\n"
              "that will remain to hold the\n"
              "board in place.")
        )
        grid0.addWidget(gaplabel, 2, 0)
        self.cutout_gap_entry = LengthEntry()
        grid0.addWidget(self.cutout_gap_entry, 2, 1)

        gaps_label = QtWidgets.QLabel(_('Gaps:'))
        gaps_label.setToolTip(
            _("Number of bridge gaps used for the cutout.\n"
              "There can be maximum 8 bridges/gaps.\n"
              "The choices are:\n"
              "- lr    - left + right\n"
              "- tb    - top + bottom\n"
              "- 4     - left + right +top + bottom\n"
              "- 2lr   - 2*left + 2*right\n"
              "- 2tb  - 2*top + 2*bottom\n"
              "- 8     - 2*left + 2*right +2*top + 2*bottom")
        )
        grid0.addWidget(gaps_label, 3, 0)
        self.gaps_combo = FCComboBox()
        grid0.addWidget(self.gaps_combo, 3, 1)

        gaps_items = ['LR', 'TB', '4', '2LR', '2TB', '8']
        for it in gaps_items:
            self.gaps_combo.addItem(it)
            self.gaps_combo.setStyleSheet('background-color: rgb(255,255,255)')

        # Surrounding convex box shape
        self.convex_box = FCCheckBox()
        self.convex_box_label = QtWidgets.QLabel(_("Convex Sh.:"))
        self.convex_box_label.setToolTip(
            _("Create a convex shape surrounding the entire PCB.")
        )
        grid0.addWidget(self.convex_box_label, 4, 0)
        grid0.addWidget(self.convex_box, 4, 1)

        self.layout.addStretch()


class Tools2sidedPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "2sided Tool Options", parent=parent)
        super(Tools2sidedPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("2Sided Tool Options")))

        # ## Board cuttout
        self.dblsided_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.dblsided_label.setToolTip(
            _("A tool to help in creating a double sided\n"
              "PCB using alignment holes.")
        )
        self.layout.addWidget(self.dblsided_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # ## Drill diameter for alignment holes
        self.drill_dia_entry = LengthEntry()
        self.dd_label = QtWidgets.QLabel(_("Drill diam.:"))
        self.dd_label.setToolTip(
            _("Diameter of the drill for the "
              "alignment holes.")
        )
        grid0.addWidget(self.dd_label, 0, 0)
        grid0.addWidget(self.drill_dia_entry, 0, 1)

        # ## Axis
        self.mirror_axis_radio = RadioSet([{'label': 'X', 'value': 'X'},
                                           {'label': 'Y', 'value': 'Y'}])
        self.mirax_label = QtWidgets.QLabel(_("Mirror Axis:"))
        self.mirax_label.setToolTip(
            _("Mirror vertically (X) or horizontally (Y).")
        )
        # grid_lay.addRow("Mirror Axis:", self.mirror_axis)
        self.empty_lb1 = QtWidgets.QLabel("")
        grid0.addWidget(self.empty_lb1, 1, 0)
        grid0.addWidget(self.mirax_label, 2, 0)
        grid0.addWidget(self.mirror_axis_radio, 2, 1)

        # ## Axis Location
        self.axis_location_radio = RadioSet([{'label': 'Point', 'value': 'point'},
                                             {'label': 'Box', 'value': 'box'}])
        self.axloc_label = QtWidgets.QLabel(_("Axis Ref:"))
        self.axloc_label.setToolTip(
            _("The axis should pass through a <b>point</b> or cut\n "
              "a specified <b>box</b> (in a Geometry object) in \n"
              "the middle.")
        )
        # grid_lay.addRow("Axis Location:", self.axis_location)
        grid0.addWidget(self.axloc_label, 3, 0)
        grid0.addWidget(self.axis_location_radio, 3, 1)

        self.layout.addStretch()


class ToolsPaintPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Paint Area Tool Options", parent=parent)
        super(ToolsPaintPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Paint Tool Options")))

        # ------------------------------
        # ## Paint area
        # ------------------------------
        self.paint_label = QtWidgets.QLabel(_('<b>Parameters:</b>'))
        self.paint_label.setToolTip(
            _("Creates tool paths to cover the\n"
              "whole area of a polygon (remove\n"
              "all copper). You will be asked\n"
              "to click on the desired polygon.")
        )
        self.layout.addWidget(self.paint_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Tool dia
        ptdlabel = QtWidgets.QLabel(_('Tool dia:'))
        ptdlabel.setToolTip(
            _("Diameter of the tool to\n"
              "be used in the operation.")
        )
        grid0.addWidget(ptdlabel, 0, 0)

        self.painttooldia_entry = LengthEntry()
        grid0.addWidget(self.painttooldia_entry, 0, 1)

        # Overlap
        ovlabel = QtWidgets.QLabel(_('Overlap Rate:'))
        ovlabel.setToolTip(
            _("How much (fraction) of the tool\n"
              "width to overlap each tool pass.")
        )
        grid0.addWidget(ovlabel, 1, 0)
        self.paintoverlap_entry = LengthEntry()
        grid0.addWidget(self.paintoverlap_entry, 1, 1)

        # Margin
        marginlabel = QtWidgets.QLabel(_('Margin:'))
        marginlabel.setToolTip(
            _("Distance by which to avoid\n"
              "the edges of the polygon to\n"
              "be painted.")
        )
        grid0.addWidget(marginlabel, 2, 0)
        self.paintmargin_entry = LengthEntry()
        grid0.addWidget(self.paintmargin_entry, 2, 1)

        # Method
        methodlabel = QtWidgets.QLabel(_('Method:'))
        methodlabel.setToolTip(
            _("Algorithm to paint the polygon:<BR>"
              "<B>Standard</B>: Fixed step inwards.<BR>"
              "<B>Seed-based</B>: Outwards from seed.")
        )
        grid0.addWidget(methodlabel, 3, 0)
        self.paintmethod_combo = RadioSet([
            {"label": "Standard", "value": "standard"},
            {"label": "Seed-based", "value": "seed"},
            {"label": "Straight lines", "value": "lines"}
        ], orientation='vertical', stretch=False)
        grid0.addWidget(self.paintmethod_combo, 3, 1)

        # Connect lines
        pathconnectlabel = QtWidgets.QLabel(_("Connect:"))
        pathconnectlabel.setToolTip(
            _("Draw lines between resulting\n"
              "segments to minimize tool lifts.")
        )
        grid0.addWidget(pathconnectlabel, 4, 0)
        self.pathconnect_cb = FCCheckBox()
        grid0.addWidget(self.pathconnect_cb, 4, 1)

        # Paint contour
        contourlabel = QtWidgets.QLabel(_("Contour:"))
        contourlabel.setToolTip(
            _("Cut around the perimeter of the polygon\n"
              "to trim rough edges.")
        )
        grid0.addWidget(contourlabel, 5, 0)
        self.contour_cb = FCCheckBox()
        grid0.addWidget(self.contour_cb, 5, 1)

        # Polygon selection
        selectlabel = QtWidgets.QLabel(_('Selection:'))
        selectlabel.setToolTip(
            _("How to select the polygons to paint.")
        )
        grid0.addWidget(selectlabel, 6, 0)
        self.selectmethod_combo = RadioSet([
            {"label": "Single", "value": "single"},
            {"label": "All", "value": "all"},
            # {"label": "Rectangle", "value": "rectangle"}
        ])
        grid0.addWidget(self.selectmethod_combo, 6, 1)

        self.layout.addStretch()


class ToolsFilmPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Cutout Tool Options", parent=parent)
        super(ToolsFilmPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Film Tool Options")))

        # ## Board cuttout
        self.film_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.film_label.setToolTip(
            _("Create a PCB film from a Gerber or Geometry\n"
              "FlatCAM object.\n"
              "The file is saved in SVG format.")
        )
        self.layout.addWidget(self.film_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        self.film_type_radio = RadioSet([{'label': 'Pos', 'value': 'pos'},
                                         {'label': 'Neg', 'value': 'neg'}])
        ftypelbl = QtWidgets.QLabel(_('Film Type:'))
        ftypelbl.setToolTip(
            _("Generate a Positive black film or a Negative film.\n"
              "Positive means that it will print the features\n"
              "with black on a white canvas.\n"
              "Negative means that it will print the features\n"
              "with white on a black canvas.\n"
              "The Film format is SVG.")
        )
        grid0.addWidget(ftypelbl, 0, 0)
        grid0.addWidget(self.film_type_radio, 0, 1)

        self.film_boundary_entry = FCEntry()
        self.film_boundary_label = QtWidgets.QLabel(_("Border:"))
        self.film_boundary_label.setToolTip(
            _("Specify a border around the object.\n"
              "Only for negative film.\n"
              "It helps if we use as a Box Object the same \n"
              "object as in Film Object. It will create a thick\n"
              "black bar around the actual print allowing for a\n"
              "better delimitation of the outline features which are of\n"
              "white color like the rest and which may confound with the\n"
              "surroundings if not for this border.")
        )
        grid0.addWidget(self.film_boundary_label, 1, 0)
        grid0.addWidget(self.film_boundary_entry, 1, 1)

        self.film_scale_entry = FCEntry()
        self.film_scale_label = QtWidgets.QLabel(_("Scale Stroke:"))
        self.film_scale_label.setToolTip(
            _("Scale the line stroke thickness of each feature in the SVG file.\n"
              "It means that the line that envelope each SVG feature will be thicker or thinner,\n"
              "therefore the fine features may be more affected by this parameter.")
        )
        grid0.addWidget(self.film_scale_label, 2, 0)
        grid0.addWidget(self.film_scale_entry, 2, 1)

        self.layout.addStretch()


class ToolsPanelizePrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Cutout Tool Options", parent=parent)
        super(ToolsPanelizePrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Panelize Tool Options")))

        # ## Board cuttout
        self.panelize_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.panelize_label.setToolTip(
            _("Create an object that contains an array of (x, y) elements,\n"
              "each element is a copy of the source object spaced\n"
              "at a X distance, Y distance of each other.")
        )
        self.layout.addWidget(self.panelize_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # ## Spacing Columns
        self.pspacing_columns = FCEntry()
        self.spacing_columns_label = QtWidgets.QLabel(_("Spacing cols:"))
        self.spacing_columns_label.setToolTip(
            _("Spacing between columns of the desired panel.\n"
              "In current units.")
        )
        grid0.addWidget(self.spacing_columns_label, 0, 0)
        grid0.addWidget(self.pspacing_columns, 0, 1)

        # ## Spacing Rows
        self.pspacing_rows = FCEntry()
        self.spacing_rows_label = QtWidgets.QLabel(_("Spacing rows:"))
        self.spacing_rows_label.setToolTip(
            _("Spacing between rows of the desired panel.\n"
              "In current units.")
        )
        grid0.addWidget(self.spacing_rows_label, 1, 0)
        grid0.addWidget(self.pspacing_rows, 1, 1)

        # ## Columns
        self.pcolumns = FCEntry()
        self.columns_label = QtWidgets.QLabel(_("Columns:"))
        self.columns_label.setToolTip(
            _("Number of columns of the desired panel")
        )
        grid0.addWidget(self.columns_label, 2, 0)
        grid0.addWidget(self.pcolumns, 2, 1)

        # ## Rows
        self.prows = FCEntry()
        self.rows_label = QtWidgets.QLabel(_("Rows:"))
        self.rows_label.setToolTip(
            _("Number of rows of the desired panel")
        )
        grid0.addWidget(self.rows_label, 3, 0)
        grid0.addWidget(self.prows, 3, 1)

        # ## Type of resulting Panel object
        self.panel_type_radio = RadioSet([{'label': 'Gerber', 'value': 'gerber'},
                                          {'label': 'Geo', 'value': 'geometry'}])
        self.panel_type_label = QtWidgets.QLabel(_("Panel Type:"))
        self.panel_type_label.setToolTip(
           _( "Choose the type of object for the panel object:\n"
              "- Gerber\n"
              "- Geometry")
        )

        grid0.addWidget(self.panel_type_label, 4, 0)
        grid0.addWidget(self.panel_type_radio, 4, 1)

        # ## Constrains
        self.pconstrain_cb = FCCheckBox(_("Constrain within:"))
        self.pconstrain_cb.setToolTip(
            _("Area define by DX and DY within to constrain the panel.\n"
              "DX and DY values are in current units.\n"
              "Regardless of how many columns and rows are desired,\n"
              "the final panel will have as many columns and rows as\n"
              "they fit completely within selected area.")
        )
        grid0.addWidget(self.pconstrain_cb, 5, 0)

        self.px_width_entry = FCEntry()
        self.x_width_lbl = QtWidgets.QLabel(_("Width (DX):"))
        self.x_width_lbl.setToolTip(
            _("The width (DX) within which the panel must fit.\n"
              "In current units.")
        )
        grid0.addWidget(self.x_width_lbl, 6, 0)
        grid0.addWidget(self.px_width_entry, 6, 1)

        self.py_height_entry = FCEntry()
        self.y_height_lbl = QtWidgets.QLabel(_("Height (DY):"))
        self.y_height_lbl.setToolTip(
            _("The height (DY)within which the panel must fit.\n"
              "In current units.")
        )
        grid0.addWidget(self.y_height_lbl, 7, 0)
        grid0.addWidget(self.py_height_entry, 7, 1)

        self.layout.addStretch()


class ToolsCalculatorsPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):
        # OptionsGroupUI.__init__(self, "Calculators Tool Options", parent=parent)
        super(ToolsCalculatorsPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Calculators Tool Options")))

        # ## V-shape Calculator Tool
        self.vshape_tool_label = QtWidgets.QLabel(_("<b>V-Shape Tool Calculator:</b>"))
        self.vshape_tool_label.setToolTip(
            _("Calculate the tool diameter for a given V-shape tool,\n"
              "having the tip diameter, tip angle and\n"
              "depth-of-cut as parameters.")
        )
        self.layout.addWidget(self.vshape_tool_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # ## Tip Diameter
        self.tip_dia_entry = FCEntry()
        self.tip_dia_label = QtWidgets.QLabel(_("Tip Diameter:"))
        self.tip_dia_label.setToolTip(
            _("This is the tool tip diameter.\n"
              "It is specified by manufacturer.")
        )
        grid0.addWidget(self.tip_dia_label, 0, 0)
        grid0.addWidget(self.tip_dia_entry, 0, 1)

        # ## Tip angle
        self.tip_angle_entry = FCEntry()
        self.tip_angle_label = QtWidgets.QLabel(_("Tip angle:"))
        self.tip_angle_label.setToolTip(
            _("This is the angle on the tip of the tool.\n"
              "It is specified by manufacturer.")
        )
        grid0.addWidget(self.tip_angle_label, 1, 0)
        grid0.addWidget(self.tip_angle_entry, 1, 1)

        # ## Depth-of-cut Cut Z
        self.cut_z_entry = FCEntry()
        self.cut_z_label = QtWidgets.QLabel(_("Cut Z:"))
        self.cut_z_label.setToolTip(
            _("This is depth to cut into material.\n"
              "In the CNCJob object it is the CutZ parameter.")
        )
        grid0.addWidget(self.cut_z_label, 2, 0)
        grid0.addWidget(self.cut_z_entry, 2, 1)

        # ## Electroplating Calculator Tool
        self.plate_title_label = QtWidgets.QLabel(_("<b>ElectroPlating Calculator:</b>"))
        self.plate_title_label.setToolTip(
            _("This calculator is useful for those who plate the via/pad/drill holes,\n"
              "using a method like grahite ink or calcium hypophosphite ink or palladium chloride.")
        )
        self.layout.addWidget(self.plate_title_label)

        grid1 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid1)

        # ## PCB Length
        self.pcblength_entry = FCEntry()
        self.pcblengthlabel = QtWidgets.QLabel(_("Board Length:"))

        self.pcblengthlabel.setToolTip(_('This is the board length. In centimeters.'))
        grid1.addWidget(self.pcblengthlabel, 0, 0)
        grid1.addWidget(self.pcblength_entry, 0, 1)

        # ## PCB Width
        self.pcbwidth_entry = FCEntry()
        self.pcbwidthlabel = QtWidgets.QLabel(_("Board Width:"))

        self.pcbwidthlabel.setToolTip(_('This is the board width.In centimeters.'))
        grid1.addWidget(self.pcbwidthlabel, 1, 0)
        grid1.addWidget(self.pcbwidth_entry, 1, 1)

        # ## Current Density
        self.cdensity_label = QtWidgets.QLabel(_("Current Density:"))
        self.cdensity_entry = FCEntry()

        self.cdensity_label.setToolTip(_("Current density to pass through the board. \n"
                                         "In Amps per Square Feet ASF."))
        grid1.addWidget(self.cdensity_label, 2, 0)
        grid1.addWidget(self.cdensity_entry, 2, 1)

        # ## PCB Copper Growth
        self.growth_label = QtWidgets.QLabel(_("Copper Growth:"))
        self.growth_entry = FCEntry()

        self.growth_label.setToolTip(_("How thick the copper growth is intended to be.\n"
                                       "In microns."))
        grid1.addWidget(self.growth_label, 3, 0)
        grid1.addWidget(self.growth_entry, 3, 1)

        self.layout.addStretch()


class ToolsTransformPrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):

        super(ToolsTransformPrefGroupUI, self).__init__(self)

        self.setTitle(str(_("Transform Tool Options")))

        # ## Transformations
        self.transform_label = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.transform_label.setToolTip(
            _("Various transformations that can be applied\n"
              "on a FlatCAM object.")
        )
        self.layout.addWidget(self.transform_label)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # ## Rotate Angle
        self.rotate_entry = FCEntry()
        self.rotate_label = QtWidgets.QLabel(_("Rotate Angle:"))
        self.rotate_label.setToolTip(
            _("Angle for rotation. In degrees.")
        )
        grid0.addWidget(self.rotate_label, 0, 0)
        grid0.addWidget(self.rotate_entry, 0, 1)

        # ## Skew/Shear Angle on X axis
        self.skewx_entry = FCEntry()
        self.skewx_label = QtWidgets.QLabel(_("Skew_X angle:"))
        self.skewx_label.setToolTip(
             _("Angle for Skew/Shear on X axis. In degrees.")
        )
        grid0.addWidget(self.skewx_label, 1, 0)
        grid0.addWidget(self.skewx_entry, 1, 1)

        # ## Skew/Shear Angle on Y axis
        self.skewy_entry = FCEntry()
        self.skewy_label = QtWidgets.QLabel(_("Skew_Y angle:"))
        self.skewy_label.setToolTip(
             _("Angle for Skew/Shear on Y axis. In degrees.")
        )
        grid0.addWidget(self.skewy_label, 2, 0)
        grid0.addWidget(self.skewy_entry, 2, 1)

        # ## Scale factor on X axis
        self.scalex_entry = FCEntry()
        self.scalex_label = QtWidgets.QLabel(_("Scale_X factor:"))
        self.scalex_label.setToolTip(
            _("Factor for scaling on X axis.")
        )
        grid0.addWidget(self.scalex_label, 3, 0)
        grid0.addWidget(self.scalex_entry, 3, 1)

        # ## Scale factor on X axis
        self.scaley_entry = FCEntry()
        self.scaley_label = QtWidgets.QLabel(_("Scale_Y factor:"))
        self.scaley_label.setToolTip(
            _("Factor for scaling on Y axis.")
        )
        grid0.addWidget(self.scaley_label, 4, 0)
        grid0.addWidget(self.scaley_entry, 4, 1)

        # ## Link Scale factors
        self.link_cb = FCCheckBox(_("Link"))
        self.link_cb.setToolTip(
            _("Scale the selected object(s)\n"
              "using the Scale_X factor for both axis.")
        )
        grid0.addWidget(self.link_cb, 5, 0)

        # ## Scale Reference
        self.reference_cb = FCCheckBox(_("Scale Reference"))
        self.reference_cb.setToolTip(
            _("Scale the selected object(s)\n"
              "using the origin reference when checked,\n"
              "and the center of the biggest bounding box\n"
              "of the selected objects when unchecked.")
        )
        grid0.addWidget(self.reference_cb, 5, 1)

        # ## Offset distance on X axis
        self.offx_entry = FCEntry()
        self.offx_label = QtWidgets.QLabel(_("Offset_X val:"))
        self.offx_label.setToolTip(
           _("Distance to offset on X axis. In current units.")
        )
        grid0.addWidget(self.offx_label, 6, 0)
        grid0.addWidget(self.offx_entry, 6, 1)

        # ## Offset distance on Y axis
        self.offy_entry = FCEntry()
        self.offy_label = QtWidgets.QLabel(_("Offset_Y val:"))
        self.offy_label.setToolTip(
            _("Distance to offset on Y axis. In current units.")
        )
        grid0.addWidget(self.offy_label, 7, 0)
        grid0.addWidget(self.offy_entry, 7, 1)

        # ## Mirror (Flip) Reference Point
        self.mirror_reference_cb = FCCheckBox(_("Mirror Reference"))
        self.mirror_reference_cb.setToolTip(
            _("Flip the selected object(s)\n"
              "around the point in Point Entry Field.\n"
              "\n"
              "The point coordinates can be captured by\n"
              "left click on canvas together with pressing\n"
              "SHIFT key. \n"
              "Then click Add button to insert coordinates.\n"
              "Or enter the coords in format (x, y) in the\n"
              "Point Entry field and click Flip on X(Y)"))
        grid0.addWidget(self.mirror_reference_cb, 8, 1)

        self.flip_ref_label = QtWidgets.QLabel(_(" Mirror Ref. Point:"))
        self.flip_ref_label.setToolTip(
            _("Coordinates in format (x, y) used as reference for mirroring.\n"
              "The 'x' in (x, y) will be used when using Flip on X and\n"
              "the 'y' in (x, y) will be used when using Flip on Y and")
        )
        self.flip_ref_entry = EvalEntry2("(0, 0)")

        grid0.addWidget(self.flip_ref_label, 9, 0)
        grid0.addWidget(self.flip_ref_entry, 9, 1)

        self.layout.addStretch()


class ToolsSolderpastePrefGroupUI(OptionsGroupUI):
    def __init__(self, parent=None):

        super(ToolsSolderpastePrefGroupUI, self).__init__(self)

        self.setTitle(str(_("SolderPaste Tool Options")))

        # ## Solder Paste Dispensing
        self.solderpastelabel = QtWidgets.QLabel(_("<b>Parameters:</b>"))
        self.solderpastelabel.setToolTip(
            _("A tool to create GCode for dispensing\n"
              "solder paste onto a PCB.")
        )
        self.layout.addWidget(self.solderpastelabel)

        grid0 = QtWidgets.QGridLayout()
        self.layout.addLayout(grid0)

        # Nozzle Tool Diameters
        nozzletdlabel = QtWidgets.QLabel(_('Tools dia:'))
        nozzletdlabel.setToolTip(
            _("Diameters of nozzle tools, separated by ','")
        )
        self.nozzle_tool_dia_entry = FCEntry()
        grid0.addWidget(nozzletdlabel, 0, 0)
        grid0.addWidget(self.nozzle_tool_dia_entry, 0, 1)

        # New Nozzle Tool Dia
        self.addtool_entry_lbl = QtWidgets.QLabel(_('<b>New Nozzle Dia:</b>'))
        self.addtool_entry_lbl.setToolTip(
            _("Diameter for the new Nozzle tool to add in the Tool Table")
        )
        self.addtool_entry = FCEntry()
        grid0.addWidget(self.addtool_entry_lbl, 1, 0)
        grid0.addWidget(self.addtool_entry, 1, 1)

        # Z dispense start
        self.z_start_entry = FCEntry()
        self.z_start_label = QtWidgets.QLabel(_("Z Dispense Start:"))
        self.z_start_label.setToolTip(
            _("The height (Z) when solder paste dispensing starts.")
        )
        grid0.addWidget(self.z_start_label, 2, 0)
        grid0.addWidget(self.z_start_entry, 2, 1)

        # Z dispense
        self.z_dispense_entry = FCEntry()
        self.z_dispense_label = QtWidgets.QLabel(_("Z Dispense:"))
        self.z_dispense_label.setToolTip(
            _("The height (Z) when doing solder paste dispensing.")
        )
        grid0.addWidget(self.z_dispense_label, 3, 0)
        grid0.addWidget(self.z_dispense_entry, 3, 1)

        # Z dispense stop
        self.z_stop_entry = FCEntry()
        self.z_stop_label = QtWidgets.QLabel(_("Z Dispense Stop:"))
        self.z_stop_label.setToolTip(
            _("The height (Z) when solder paste dispensing stops.")
        )
        grid0.addWidget(self.z_stop_label, 4, 0)
        grid0.addWidget(self.z_stop_entry, 4, 1)

        # Z travel
        self.z_travel_entry = FCEntry()
        self.z_travel_label = QtWidgets.QLabel(_("Z Travel:"))
        self.z_travel_label.setToolTip(
            _("The height (Z) for travel between pads\n"
              "(without dispensing solder paste).")
        )
        grid0.addWidget(self.z_travel_label, 5, 0)
        grid0.addWidget(self.z_travel_entry, 5, 1)

        # Z toolchange location
        self.z_toolchange_entry = FCEntry()
        self.z_toolchange_label = QtWidgets.QLabel(_("Z Toolchange:"))
        self.z_toolchange_label.setToolTip(
            _("The height (Z) for tool (nozzle) change.")
        )
        grid0.addWidget(self.z_toolchange_label, 6, 0)
        grid0.addWidget(self.z_toolchange_entry, 6, 1)

        # X,Y Toolchange location
        self.xy_toolchange_entry = FCEntry()
        self.xy_toolchange_label = QtWidgets.QLabel(_("XY Toolchange:"))
        self.xy_toolchange_label.setToolTip(
            _("The X,Y location for tool (nozzle) change.\n"
              "The format is (x, y) where x and y are real numbers.")
        )
        grid0.addWidget(self.xy_toolchange_label, 7, 0)
        grid0.addWidget(self.xy_toolchange_entry, 7, 1)

        # Feedrate X-Y
        self.frxy_entry = FCEntry()
        self.frxy_label = QtWidgets.QLabel(_("Feedrate X-Y:"))
        self.frxy_label.setToolTip(
            _("Feedrate (speed) while moving on the X-Y plane.")
        )
        grid0.addWidget(self.frxy_label, 8, 0)
        grid0.addWidget(self.frxy_entry, 8, 1)

        # Feedrate Z
        self.frz_entry = FCEntry()
        self.frz_label = QtWidgets.QLabel(_("Feedrate Z:"))
        self.frz_label.setToolTip(
            _("Feedrate (speed) while moving vertically\n"
              "(on Z plane).")
        )
        grid0.addWidget(self.frz_label, 9, 0)
        grid0.addWidget(self.frz_entry, 9, 1)

        # Feedrate Z Dispense
        self.frz_dispense_entry = FCEntry()
        self.frz_dispense_label = QtWidgets.QLabel(_("Feedrate Z Dispense:"))
        self.frz_dispense_label.setToolTip(
            _("Feedrate (speed) while moving up vertically\n"
              "to Dispense position (on Z plane).")
        )
        grid0.addWidget(self.frz_dispense_label, 10, 0)
        grid0.addWidget(self.frz_dispense_entry, 10, 1)

        # Spindle Speed Forward
        self.speedfwd_entry = FCEntry()
        self.speedfwd_label = QtWidgets.QLabel(_("Spindle Speed FWD:"))
        self.speedfwd_label.setToolTip(
            _("The dispenser speed while pushing solder paste\n"
              "through the dispenser nozzle.")
        )
        grid0.addWidget(self.speedfwd_label, 11, 0)
        grid0.addWidget(self.speedfwd_entry, 11, 1)

        # Dwell Forward
        self.dwellfwd_entry = FCEntry()
        self.dwellfwd_label = QtWidgets.QLabel(_("Dwell FWD:"))
        self.dwellfwd_label.setToolTip(
            _("Pause after solder dispensing.")
        )
        grid0.addWidget(self.dwellfwd_label, 12, 0)
        grid0.addWidget(self.dwellfwd_entry, 12, 1)

        # Spindle Speed Reverse
        self.speedrev_entry = FCEntry()
        self.speedrev_label = QtWidgets.QLabel(_("Spindle Speed REV:"))
        self.speedrev_label.setToolTip(
            _("The dispenser speed while retracting solder paste\n"
              "through the dispenser nozzle.")
        )
        grid0.addWidget(self.speedrev_label, 13, 0)
        grid0.addWidget(self.speedrev_entry, 13, 1)

        # Dwell Reverse
        self.dwellrev_entry = FCEntry()
        self.dwellrev_label = QtWidgets.QLabel(_("Dwell REV:"))
        self.dwellrev_label.setToolTip(
            _("Pause after solder paste dispenser retracted,\n"
              "to allow pressure equilibrium.")
        )
        grid0.addWidget(self.dwellrev_label, 14, 0)
        grid0.addWidget(self.dwellrev_entry, 14, 1)

        # Postprocessors
        pp_label = QtWidgets.QLabel(_('PostProcessors:'))
        pp_label.setToolTip(
            _("Files that control the GCode generation.")
        )

        self.pp_combo = FCComboBox()
        grid0.addWidget(pp_label, 15, 0)
        grid0.addWidget(self.pp_combo, 15, 1)

        self.layout.addStretch()


class FlatCAMActivityView(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setMinimumWidth(200)

        self.icon = QtWidgets.QLabel(self)
        self.icon.setGeometry(0, 0, 16, 12)
        self.movie = QtGui.QMovie("share/active.gif")
        self.icon.setMovie(self.movie)
        # self.movie.start()

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setAlignment(QtCore.Qt.AlignLeft)
        self.setLayout(layout)

        layout.addWidget(self.icon)
        self.text = QtWidgets.QLabel(self)
        self.text.setText(_("Idle."))

        layout.addWidget(self.text)

    def set_idle(self):
        self.movie.stop()
        self.text.setText(_("Idle."))

    def set_busy(self, msg):
        self.movie.start()
        self.text.setText(msg)


class FlatCAMInfoBar(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(FlatCAMInfoBar, self).__init__(parent=parent)

        self.icon = QtWidgets.QLabel(self)
        self.icon.setGeometry(0, 0, 12, 12)
        self.pmap = QtGui.QPixmap('share/graylight12.png')
        self.icon.setPixmap(self.pmap)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        self.setLayout(layout)

        layout.addWidget(self.icon)

        self.text = QtWidgets.QLabel(self)
        self.text.setText(_("Application started ..."))
        self.text.setToolTip(_("Hello!"))

        layout.addWidget(self.text)

        layout.addStretch()

    def set_text_(self, text, color=None):
        self.text.setText(text)
        self.text.setToolTip(text)
        if color:
            self.text.setStyleSheet('color: %s' % str(color))

    def set_status(self, text, level="info"):
        level = str(level)
        self.pmap.fill()
        if level == "ERROR" or level == "ERROR_NOTCL":
            self.pmap = QtGui.QPixmap('share/redlight12.png')
        elif level == "success" or level == "SUCCESS":
            self.pmap = QtGui.QPixmap('share/greenlight12.png')
        elif level == "WARNING" or level == "WARNING_NOTCL":
            self.pmap = QtGui.QPixmap('share/yellowlight12.png')
        elif level == "selected" or level == "SELECTED":
            self.pmap = QtGui.QPixmap('share/bluelight12.png')
        else:
            self.pmap = QtGui.QPixmap('share/graylight12.png')

        self.set_text_(text)
        self.icon.setPixmap(self.pmap)
# end of file