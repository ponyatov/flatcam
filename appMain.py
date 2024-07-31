# ###########################################################
# FlatCAM: 2D Post-processing for Manufacturing             #
# http://flatcam.org                                        #
# Author: Juan Pablo Caram (c)                              #
# Date: 2/5/2014                                            #
# MIT Licence                                               #
# Modified by Marius Stanciu (2019)                         #
# ###########################################################

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import QSettings, pyqtSlot
from PyQt6.QtCore import Qt, pyqtSignal, QMetaObject
from PyQt6.QtGui import QAction, QTextCursor

import os.path
import sys

import urllib.request
import urllib.parse
import urllib.error

from datetime import datetime as dt
from copy import deepcopy, copy
import numpy as np

import getopt
import random
import simplejson as json
import shutil
import traceback
import logging
import time
import webbrowser
import platform
import re
import subprocess

from shapely import Point, MultiPolygon, MultiLineString, Polygon
from shapely.ops import unary_union
from io import StringIO

import gc

from multiprocessing.connection import Listener, Client
from multiprocessing import Pool
import socket

import tkinter as tk

import libs.qdarktheme
import libs.qdarktheme.themes.dark.stylesheet as qdarksheet
import libs.qdarktheme.themes.light.stylesheet as qlightsheet

from typing import Union

# ####################################################################################################################
# ###################################      Imports part of FlatCAM       #############################################
# ####################################################################################################################

# App appGUI
from appGUI.PlotCanvas import PlotCanvas
from appGUI.PlotCanvasLegacy import PlotCanvasLegacy
from appGUI.PlotCanvas3d import PlotCanvas3d
from appGUI.MainGUI import MainGUI
from appGUI.VisPyVisuals import ShapeCollection
from appGUI.GUIElements import FCMessageBox, FCInputSpinner, FCButton, DialogBoxRadio, Dialog_box, FCTree, \
    FCInputDoubleSpinner, FCFileSaveDialog, message_dialog, AppSystemTray, FCInputDialogSlider, \
    GLay, FCLabel, DialogBoxChoice, VerticalScrollArea
from appGUI.themes import dark_style_sheet, light_style_sheet

# Various
from appCommon.Common import color_variant
from appCommon.Common import ExclusionAreas
from appCommon.Common import AppLogging
from appCommon.RegisterFileKeywords import RegisterFK, Extensions, KeyWords

from appHandlers.appIO import appIO
from appHandlers.appEdit import appEditor

from Bookmark import BookmarkManager
from appDatabase import ToolsDB2

# App defaults (preferences)
from defaults import AppDefaults
from defaults import AppOptions

# App Objects
from appGUI.preferences.OptionsGroupUI import OptionsGroupUI
from appGUI.preferences.PreferencesUIManager import PreferencesUIManager
from appObjects.ObjectCollection import ObjectCollection, GerberObject, ExcellonObject, GeometryObject, \
    CNCJobObject, ScriptObject, DocumentObject
from appObjects.AppObjectTemplate import FlatCAMObj
from appObjects.AppObject import AppObject

# App Parsing files
from appParsers.ParseExcellon import Excellon
from appParsers.ParseGerber import Gerber
from camlib import to_dict, Geometry, CNCjob

# App Pre-processors
from appPreProcessor import load_preprocessors

# App appEditors
from appEditors.appGeoEditor import AppGeoEditor
from appEditors.appExcEditor import AppExcEditor
from appEditors.appGerberEditor import AppGerberEditor
from appEditors.appTextEditor import AppTextEditor
from appEditors.appGCodeEditor import AppGCodeEditor

# App Workers
from appProcess import *
from appWorkerStack import WorkerStack

# App Plugins
from appPlugins import *

from numpy import Inf

# App Translation
import gettext
import appTranslation as fcTranslate
import builtins

import darkdetect

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class App(QtCore.QObject):
    """
    The main application class. The constructor starts the GUI and all other classes used by the program.
    """

    # ###############################################################################################################
    # ########################################## App ################################################################
    # ###############################################################################################################

    # ###############################################################################################################
    # #################################### Get Cmd Line Options #####################################################
    # ###############################################################################################################
    cmd_line_shellfile = ''
    cmd_line_shellvar = ''
    cmd_line_headless = None

    cmd_line_help = "FlatCam.py --shellfile=<cmd_line_shellfile>\n" \
                    "FlatCam.py --shellvar=<1,'C:\\path',23>\n" \
                    "FlatCam.py --headless=1"
    try:
        # Multiprocessing pool will spawn additional processes with 'multiprocessing-fork' flag
        cmd_line_options, args = getopt.getopt(sys.argv[1:], "h:", ["shellfile=",
                                                                    "shellvar=",
                                                                    "headless=",
                                                                    "multiprocessing-fork="])
    except getopt.GetoptError:
        print(cmd_line_help)
        sys.exit(2)

    for opt, arg in cmd_line_options:
        if opt == '-h':
            print(cmd_line_help)
            sys.exit()
        elif opt == '--shellfile':
            cmd_line_shellfile = arg
        elif opt == '--shellvar':
            cmd_line_shellvar = arg
        elif opt == '--headless':
            try:
                cmd_line_headless = eval(arg)
            except NameError:
                pass

    # ###############################################################################################################
    # ################################### Version and VERSION DATE ##################################################
    # ###############################################################################################################
    version = "Unstable"
    # version = 1.0
    version_date = "2023/6/31"
    beta = True
    engine = '3D'

    # current date now
    date = str(dt.today()).rpartition('.')[0]
    date = ''.join(c for c in date if c not in ':-')
    date = date.replace(' ', '_')

    # ###############################################################################################################
    # ############################################ URLS's ###########################################################
    # ###############################################################################################################
    # URL for update checks and statistics
    version_url = "http://flatcam.org/version"

    # App URL
    app_url = "http://flatcam.org"

    # Manual URL
    manual_url = "http://flatcam.org/manual/index.html"
    video_url = "https://www.youtube.com/playlist?list=PLVvP2SYRpx-AQgNlfoxw93tXUXon7G94_"
    gerber_spec_url = "https://www.ucamco.com/files/downloads/file/81/The_Gerber_File_Format_specification." \
                      "pdf?7ac957791daba2cdf4c2c913f67a43da"
    excellon_spec_url = "https://www.ucamco.com/files/downloads/file/305/the_xnc_file_format_specification.pdf"
    bug_report_url = "https://bitbucket.org/jpcgt/flatcam/issues?status=new&status=open"
    donate_url = "https://www.paypal.com/cgi-bin/webscr?cmd=_" \
                 "donations&business=WLTJJ3Q77D98L&currency_code=USD&source=url"
    # this variable will hold the project status
    # if True it will mean that the project was modified and not saved
    should_we_save = False

    # flag is True if saving action has been triggered
    save_in_progress = False

    # ###############################################################################################################
    # #######################################    APP Signals   ######################################################
    # ###############################################################################################################

    # Inform the user
    # Handled by: App.info() --> Print on the status bar
    inform = QtCore.pyqtSignal([str], [str, bool])
    # Handled by: App.info_shell() --> Print on the shell
    inform_shell = QtCore.pyqtSignal([str], [str, bool])
    inform_no_echo = QtCore.pyqtSignal(str)

    app_quit = QtCore.pyqtSignal()

    # General purpose background task
    worker_task = QtCore.pyqtSignal(dict)

    # File opened
    # Handled by:
    #  * register_folder()
    #  * register_recent()
    # Note: Setting the parameters to unicode does not seem
    #       to have an effect. Then are received as Qstring
    #       anyway.

    # File type and filename
    file_opened = QtCore.pyqtSignal(str, str)
    # File type and filename
    file_saved = QtCore.pyqtSignal(str, str)
    # close app signal
    close_app_signal = pyqtSignal()
    # will perform the cleanup operation after a Graceful Exit
    # usefull for the NCC Tool and Paint Tool where some progressive plotting might leave
    # graphic residues behind
    cleanup = pyqtSignal()
    # emitted when the new_project is created in a threaded way
    new_project_signal = pyqtSignal()
    # Percentage of progress
    progress = QtCore.pyqtSignal(int)
    # Emitted when a new object has been added or deleted from/to the collection
    object_status_changed = QtCore.pyqtSignal(object, str, str)

    message = QtCore.pyqtSignal(str, str, str)

    # Emitted when a shell command is finished(one command only)
    shell_command_finished = QtCore.pyqtSignal(object)
    # Emitted when multiprocess pool has been recreated
    pool_recreated = QtCore.pyqtSignal(object)
    # Emitted when an unhandled exception happens
    # in the worker task.
    thread_exception = QtCore.pyqtSignal(object)
    # used to signal that there are arguments for the app
    args_at_startup = QtCore.pyqtSignal(list)
    # a reusable signal to replot a list of objects
    # should be disconnected after use, so it can be reused
    replot_signal = pyqtSignal(list)
    # signal emitted when jumping
    jump_signal = pyqtSignal(tuple)
    # signal emitted when jumping
    locate_signal = pyqtSignal(tuple, str)

    proj_selection_changed = pyqtSignal(object, object)
    # used by the AppScript object to process a script
    run_script = pyqtSignal(str)
    # used when loading a project and parsing the project file
    restore_project = pyqtSignal(object, str, bool, bool, bool, bool)
    # used when loading a project and restoring objects
    restore_project_objects_sig = pyqtSignal(object, str, bool, bool)
    # post-Edit actions
    post_edit_sig = pyqtSignal()

    # noinspection PyUnresolvedReferences
    def __init__(self, qapp, user_defaults=True):
        """
        Starts the application.

        :return:    the application
        :rtype:     QtCore.QObject
        """

        super().__init__()

        # #############################################################################################################
        # ######################################### LOGGING ###########################################################
        # #############################################################################################################
        self.log = logging.getLogger('base')
        self.log.setLevel(logging.DEBUG)
        # log.setLevel(logging.WARNING)
        formatter = logging.Formatter('[%(levelname)s][%(threadName)s] %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

        self.log.info("Starting the application...")

        self.qapp = qapp

        # App Editors will be instantiated further below
        self.exc_editor = None
        self.grb_editor = None
        self.geo_editor = None

        # when True, the app has to return from any thread
        self.abort_flag = False

        # ###########################################################################################################
        # ############################################ Data #########################################################
        # ###########################################################################################################

        self.recent = []
        self.recent_projects = []

        self.clipboard = QtWidgets.QApplication.clipboard()

        self.project_filename = None
        self.toggle_units_ignore = False

        self.main_thread = QtWidgets.QApplication.instance().thread()

        # ###########################################################################################################
        # ###########################################################################################################
        # ######################################## Variables for global usage #######################################
        # ###########################################################################################################
        # ###########################################################################################################

        # hold the App units
        self.units = 'MM'

        # coordinates for relative position display
        self.rel_point1 = (0, 0)
        self.rel_point2 = (0, 0)

        # variable to store coordinates
        self.pos_jump = (0, 0)

        # variable to store mouse coordinates
        self._mouse_click_pos = [0, 0]
        self._mouse_pos = [0, 0]

        # variable to store the delta positions on canvas
        self.dx = 0
        self.dy = 0

        # decide if we have a double click or single click
        self.doubleclick = False

        # store here the is_dragging value
        self.event_is_dragging = False

        # variable to store if a command is active (then the var is not None) and which one it is
        self.command_active = None
        # variable to store the status of moving selection action
        # None value means that it's not a selection action
        # True value = a selection from left to right
        # False value = a selection from right to left
        self.selection_type = None

        # List to store the objects that are currently loaded in FlatCAM
        # This list is updated on each object creation or object delete
        self.all_objects_list = []

        self.objects_under_the_click_list = []

        # List to store the objects that are selected
        self.sel_objects_list = []

        # holds the key modifier if pressed (CTRL, SHIFT or ALT)
        self.key_modifiers = None

        # Variable to store the status of the code editor
        self.toggle_codeeditor = False

        # Variable to be used for situations when we don't want the LMB click on canvas to auto open the Project Tab
        self.click_noproject = False

        # store here the mouse cursor
        self.cursor = None

        # while True no canvas context menu will be shown
        self.inhibit_context_menu = False

        # Variable to store the GCODE that was edited
        self.gcode_edited = ""

        # Variable to store old state of the Tools Toolbar; used in the Editor2Object and in Object2Editor methods
        self.old_state_of_tools_toolbar = False

        self.text_editor_tab = None

        # here store the color of a Tab text before it is changed, so it can be restored in the future
        self.old_tab_text_color = None

        # reference for the self.ui.code_editor
        self.reference_code_editor = None
        self.script_code = ''

        # if Tools DB are changed/edited in the Edit -> Tools Database tab the value will be set to True
        self.tools_db_changed_flag = False

        # last used filters
        self.last_op_gerber_filter = None
        self.last_op_excellon_filter = None
        self.last_op_gcode_filter = None

        # global variable used by NCC Tool to signal that some polygons could not be cleared, if True
        # flag for polygons not cleared
        self.poly_not_cleared = False

        # VisPy visuals
        self.isHovering = False
        self.notHovering = True

        # Window geometry
        self.x_pos = None
        self.y_pos = None
        self.width = None
        self.height = None

        # this holds a widget that is installed in the Plot Area when View Source option is used
        self.source_editor_tab = None

        self.pagesize = {}

        # used in the delayed shutdown self.start_delayed_quit() method
        self.save_timer = None

        # to use for tools like Distance tool who depends on the event sources who are changed inside the appEditors
        # depending on from where those tools are called different actions can be done
        self.call_source = 'app'

        # this is a flag to signal to other tools that the ui tooltab is locked and not accessible
        self.plugin_tab_locked = False

        # ############################################################################################################
        # ################# Setup the listening thread for another instance launching with args ######################
        # ############################################################################################################
        if sys.platform == 'win32':
            # make sure the thread is stored by using a self. otherwise it's garbage collected
            self.listen_th = QtCore.QThread()
            self.listen_th.start(priority=QtCore.QThread.Priority.LowestPriority)

            self.new_launch = ArgsThread()
            self.new_launch.open_signal[list].connect(self.on_startup_args)
            self.new_launch.moveToThread(self.listen_th)
            self.new_launch.start.emit()    # noqa

        # ############################################################################################################
        # ########################################## OS-specific #####################################################
        # ############################################################################################################
        portable = False

        # Folder for user settings.
        if sys.platform == 'win32':
            # if platform.architecture()[0] == '32bit':
            #     self.log.debug("Win32!")
            # else:
            #     self.log.debug("Win64!")

            # #######################################################################################################
            # ####### CONFIG FILE WITH PARAMETERS REGARDING PORTABILITY #############################################
            # #######################################################################################################
            config_file = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '\\config\\configuration.txt'
            try:
                with open(config_file, 'r'):
                    pass
            except FileNotFoundError:
                config_file = os.path.dirname(os.path.realpath(__file__)) + '\\config\\configuration.txt'

            try:
                with open(config_file, 'r') as f:
                    try:
                        for line in f:
                            param = str(line).replace('\n', '').rpartition('=')

                            if param[0] == 'portable':
                                try:
                                    portable = eval(param[2])
                                except NameError:
                                    portable = False
                            if param[0] == 'headless':
                                if param[2].lower() == 'true':
                                    self.cmd_line_headless = 1
                    except Exception as e:
                        self.log.error('App.__init__() -->%s' % str(e))
                        return
            except FileNotFoundError as e:
                self.log.error(str(e))
                pass

            if portable is False:
                # self.data_path = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, None, 0) + '\\FlatCAM'
                self.data_path = os.path.join(os.getenv('appdata'), 'FlatCAM')
            else:
                self.data_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '\\config'

            self.os = 'windows'
        else:  # Linux/Unix/MacOS
            self.data_path = os.path.expanduser('~') + '/.FlatCAM'
            self.os = 'unix'

        # ############################################################################################################
        # ################################# Setup folders and files ##################################################
        # ############################################################################################################

        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)
            self.log.debug('Created data folder: ' + self.data_path)

        self.preprocessorpaths = self.preprocessors_path()
        if not os.path.exists(self.preprocessorpaths):
            os.makedirs(self.preprocessorpaths)
            self.log.debug('Created preprocessors folder: ' + self.preprocessorpaths)

        # create tools_db.FlatDB file if there is none
        db_path = self.tools_database_path()

        try:
            f = open(db_path)
            f.close()
        except IOError:
            self.log.debug('Creating empty tools_db.FlatDB')
            f = open(db_path, 'w')
            json.dump({}, f)
            f.close()

        # create current_defaults.FlatConfig file if there is none
        def_path = self.defaults_path()
        try:
            f = open(def_path)
            f.close()
        except IOError:
            self.log.debug('Creating empty current_defaults.FlatConfig')
            f = open(def_path, 'w')
            json.dump({}, f)
            f.close()

        # the factory defaults are written only once at the first launch of the application after installation
        AppDefaults.save_factory_defaults(self.factory_defaults_path(), self.version)

        # create a recent files json file if there is none
        rec_f_path = self.recent_files_path()
        try:
            f = open(rec_f_path)
            f.close()
        except IOError:
            self.log.debug('Creating empty recent.json')
            f = open(rec_f_path, 'w')
            json.dump([], f)
            f.close()

        # create a recent projects json file if there is none
        rec_proj_path = self.recent_projects_path()
        try:
            fp = open(rec_proj_path)
            fp.close()
        except IOError:
            self.log.debug('Creating empty recent_projects.json')
            fp = open(rec_proj_path, 'w')
            json.dump([], fp)
            fp.close()

        # Application directory. CHDIR to it. Otherwise, trying to load GUI icons will fail as their path is relative.
        # This will fail under cx_freeze ...
        self.app_home = os.path.dirname(os.path.realpath(__file__))

        # self.log.debug("Application path is " + self.app_home)
        # self.log.debug("Started in " + os.getcwd())

        # cx_freeze workaround
        if os.path.isfile(self.app_home):
            self.app_home = os.path.dirname(self.app_home)

        os.chdir(self.app_home)

        # ############################################################################################################
        # ################################# DEFAULTS - PREFERENCES STORAGE ###########################################
        # ############################################################################################################
        self.defaults = AppDefaults(beta=self.beta, version=self.version)

        # current_defaults_path = os.path.join(self.data_path, "current_defaults.FlatConfig")
        current_defaults_path = self.defaults_path()
        if user_defaults:
            self.defaults.load(filename=current_defaults_path, inform=self.inform)

        # ###########################################################################################################
        # ######################################## UPDATE THE OPTIONS ###############################################
        # ###########################################################################################################
        self.options = AppOptions(version=self.version)
        # -----------------------------------------------------------------------------------------------------------
        #   Update the self.options from the self.defaults
        #   The self.options holds the application defaults while the self.options holds the object defaults
        # -----------------------------------------------------------------------------------------------------------
        # Copy app defaults to project options
        for def_key, def_val in self.defaults.items():
            self.options[def_key] = deepcopy(def_val)

        # self.preferencesUiManager.show_preferences_gui()

        # Set global_theme based on appearance
        if self.options["global_appearance"] == 'auto':
            if darkdetect.isDark():
                theme = 'dark'
            else:
                theme = 'light'
        else:
            if self.options["global_appearance"] == 'default':
                theme = 'default'
            elif self.options["global_appearance"] == 'dark':
                theme = 'dark'
            else:
                theme = 'light'

        self.options["global_theme"] = theme

        self.app_units = self.options["units"]
        self.default_units = self.defaults["units"]
        self.decimals = int(self.options['units_precision'])

        if self.options["global_theme"] == 'default':
            self.resource_location = 'assets/resources'
        elif self.options["global_theme"] == 'light':
            self.resource_location = 'assets/resources'
            qlightsheet.STYLE_SHEET = light_style_sheet.L_STYLE_SHEET
            self.qapp.setStyleSheet(libs.qdarktheme.load_stylesheet('light'))
        else:
            self.resource_location = 'assets/resources/dark_resources'
            qdarksheet.STYLE_SHEET = dark_style_sheet.D_STYLE_SHEET
            self.qapp.setStyleSheet(libs.qdarktheme.load_stylesheet())

        # ############################################################################################################
        # ################################### Set LOG verbosity ######################################################
        # ############################################################################################################

        if self.options["global_log_verbose"] == 2:
            self.log.handlers.pop()
            self.log = AppLogging(app=self, log_level=2)
        if self.options["global_log_verbose"] == 0:
            self.log.handlers.pop()
            self.log = AppLogging(app=self, log_level=0)

        # ###########################################################################################################
        # #################################### SETUP OBJECT CLASSES #################################################
        # ###########################################################################################################
        self.setup_obj_classes()

        # ###########################################################################################################
        # ###################################### CREATE MULTIPROCESSING POOL #######################################
        # ###########################################################################################################
        self.pool = Pool(processes=self.options["global_process_number"])

        # ###########################################################################################################
        # ###################################### Clear GUI Settings - once at first start ###########################
        # ###########################################################################################################
        if self.options["first_run"] is True:
            # on first run clear the previous QSettings, therefore clearing the GUI settings
            qsettings = QSettings("Open Source", "FlatCAM_EVO")
            for key in qsettings.allKeys():
                qsettings.remove(key)
            # This will write the setting to the platform specific storage.
            del qsettings

        # ###########################################################################################################
        # ###################################### Setting the Splash Screen ##########################################
        # ###########################################################################################################
        splash_settings = QSettings("Open Source", "FlatCAM_EVO")
        if splash_settings.contains("splash_screen"):
            show_splash = splash_settings.value("splash_screen")
        else:
            splash_settings.setValue('splash_screen', 1)

            # This will write the setting to the platform specific storage.
            del splash_settings
            show_splash = 1

        if show_splash and self.cmd_line_headless != 1:
            splash_pix = QtGui.QPixmap(self.resource_location + '/splash.png')
            # self.splash = QtWidgets.QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
            self.splash = QtWidgets.QSplashScreen(splash_pix)
            # self.splash.setMask(splash_pix.mask())

            # move splashscreen to the current monitor
            # desktop = QtWidgets.QApplication.desktop()
            # screen = desktop.screenNumber(QtGui.QCursor.pos())
            # screen = QtWidgets.QWidget.screen(self.splash)
            screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
            if screen:
                current_screen_center = screen.availableGeometry().center()
                self.splash.move(current_screen_center - self.splash.rect().center())

            self.splash.show()
            self.splash.showMessage(_("The application is initializing ..."),
                                    alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                                    color=QtGui.QColor("lightgray"))
        else:
            self.splash = None
            show_splash = 0

        # ###########################################################################################################
        # ########################################## LOAD LANGUAGES  ################################################
        # ###########################################################################################################

        self.languages = fcTranslate.load_languages()
        aval_languages = []
        for name in sorted(self.languages.values()):
            aval_languages.append(name)
        self.options["global_languages"] = aval_languages

        # ###########################################################################################################
        # ####################################### APPLY APP LANGUAGE ################################################
        # ###########################################################################################################

        ret_val = fcTranslate.apply_language('strings')

        if ret_val == "no language":
            self.inform.emit('[ERROR] %s' % _("Could not find the Language files. The App strings are missing."))
            self.log.debug("Could not find the Language files. The App strings are missing.")
        else:
            # make the current language the current selection on the language combobox
            self.options["global_language_current"] = ret_val
            self.log.debug("App.__init__() --> Applied %s language." % str(ret_val).capitalize())

        # ###########################################################################################################
        # #################################### LOAD PREPROCESSORS ###################################################
        # ###########################################################################################################

        # ----------------------------------------- WARNING --------------------------------------------------------
        # Preprocessors need to be loaded before the Preferences Manager builds the Preferences
        # That's because the number of preprocessors can vary and here the combobox is populated
        # -----------------------------------------------------------------------------------------------------------

        # a dictionary that have as keys the name of the preprocessor files and the value is the class from
        # the preprocessor file
        self.preprocessors = load_preprocessors(self)

        # make sure that always the 'default' preprocessor is the first item in the dictionary
        if 'default' in self.preprocessors.keys():
            # add the 'default' name first in the dict after removing from the preprocessor's dictionary
            default_pp = self.preprocessors.pop('default')
            new_ppp_dict = {
                'default': default_pp
            }

            # then add the rest of the keys
            for name, val_class in self.preprocessors.items():
                new_ppp_dict[name] = val_class

            # and now put back the ordered dict with 'default' key first
            self.preprocessors = deepcopy(new_ppp_dict)

        # populate the Plugins Preprocessors
        self.options["tools_drill_preprocessor_list"] = []
        self.options["tools_mill_preprocessor_list"] = []
        self.options["tools_solderpaste_preprocessor_list"] = []
        for name in list(self.preprocessors.keys()):
            lowered_name = name.lower()

            # 'Paste' preprocessors are to be used only in the Solder Paste Dispensing Plugin
            if 'paste' in lowered_name:
                self.options["tools_solderpaste_preprocessor_list"].append(name)
                continue

            self.options["tools_mill_preprocessor_list"].append(name)

            # HPGL preprocessor is only for Geometry objects therefore it should not be in the Excellon Preferences
            if 'hpgl' not in lowered_name:
                self.options["tools_drill_preprocessor_list"].append(name)

        # ###########################################################################################################
        # ######################################### Initialize GUI ##################################################
        # ###########################################################################################################

        # FlatCAM colors used in plotting
        self.FC_light_green = '#BBF268BF'
        self.FC_dark_green = '#006E20BF'
        self.FC_light_blue = '#a5a5ffbf'
        self.FC_dark_blue = '#0000ffbf'

        theme_settings = QtCore.QSettings("Open Source", "FlatCAM_EVO")
        theme_settings.setValue("appearance", self.options["global_appearance"])
        theme_settings.setValue("theme", self.options["global_theme"])
        theme_settings.setValue("dark_canvas", self.options["global_dark_canvas"])

        if self.options["global_cursor_color_enabled"]:
            self.cursor_color_3D = self.options["global_cursor_color"]
        else:
            if (theme == 'light' or theme == 'default') and not self.options["global_dark_canvas"]:
                self.cursor_color_3D = 'black'
            else:
                self.cursor_color_3D = 'gray'

        # update the 'options' dict with the setting in QSetting
        self.options['global_theme'] = theme

        # ########################
        self.ui = MainGUI(self)
        # ########################

        # decide if to show or hide the Notebook side of the screen at startup
        if self.options["global_project_at_startup"] is True:
            self.ui.splitter.setSizes([1, 1])
        else:
            self.ui.splitter.setSizes([0, 1])

        # ###########################################################################################################
        # ########################################### Initialize Tcl Shell ##########################################
        # ###########################    always initialize it after the UI is initialized   #########################
        # ###########################################################################################################
        self.shell = FCShell(app=self, version=self.version)
        self.log.debug("Stardate: %s" % self.date)
        self.log.debug("TCL Shell has been initialized.")

        # ###########################################################################################################
        # ####################################### Auto-complete KEYWORDS ############################################
        # ######################## Setup after the Defaults class was instantiated ##################################
        # ###########################################################################################################
        self.regFK = RegisterFK(
            ui=self.ui,
            inform_sig=self.inform,
            options_dict=self.options,
            shell=self.shell,
            log=self.log,
            keywords=KeyWords(),
            extensions=Extensions()
        )

        # ###########################################################################################################
        # ########################################### AUTOSAVE SETUP ################################################
        # ###########################################################################################################

        self.block_autosave = False
        self.autosave_timer = QtCore.QTimer(self)
        self.save_project_auto_update()
        self.autosave_timer.timeout.connect(self.save_project_auto)

        # ###########################################################################################################
        # ##################################### UPDATE PREFERENCES GUI FORMS ########################################
        # ###########################################################################################################
        self.preferencesUiManager = PreferencesUIManager(
            data_path=self.data_path,
            ui=self.ui,
            inform=self.inform,
            options=self.options,
            defaults=self.defaults
        )

        self.preferencesUiManager.defaults_write_form()

        # When the self.options dictionary changes will update the Preferences GUI forms
        self.options.set_change_callback(self.on_defaults_dict_change)

        # set the value used in the Windows Title
        self.engine = self.options["global_graphic_engine"]

        # ###########################################################################################################
        # ###################################### CREATE UNIQUE SERIAL NUMBER ########################################
        # ###########################################################################################################
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
        if self.options['global_serial'] == 0 or len(str(self.options['global_serial'])) < 10:
            self.options['global_serial'] = ''.join([random.choice(chars) for __ in range(20)])
            self.preferencesUiManager.save_defaults(silent=True, first_time=True)

        self.defaults.propagate_defaults()

        # ###########################################################################################################
        # #################################### SETUP OBJECT COLLECTION ##############################################
        # ###########################################################################################################

        self.collection = ObjectCollection(app=self)
        self.ui.project_tab_layout.addWidget(self.collection.view)

        self.app_obj = AppObject(app=self)

        # ### Adjust tabs width ## ##
        # self.collection.view.setMinimumWidth(self.ui.options_scroll_area.widget().sizeHint().width() +
        #     self.ui.options_scroll_area.verticalScrollBar().sizeHint().width())
        self.collection.view.setMinimumWidth(290)
        self.log.debug("Finished creating Object Collection.")

        # ###########################################################################################################
        # ######################################## SETUP 3D Area ####################################################
        # ###########################################################################################################
        self.area_3d_tab = QtWidgets.QWidget()

        # ###########################################################################################################
        # ######################################## SETUP Plot Area ##################################################
        # ###########################################################################################################

        self.use_3d_engine = True
        # determine if the Legacy Graphic Engine is to be used or the OpenGL one
        if self.options["global_graphic_engine"] == '2D':
            self.use_3d_engine = False

        # PlotCanvas Event signals disconnect id holders
        self.mp = None
        self.mm = None
        self.mr = None
        self.mdc = None
        self.mp_zc = None
        self.kp = None

        # Matplotlib axis
        self.axes = None

        self.app_cursor = None
        self.hover_shapes = None

        if show_splash:
            self.splash.showMessage(_("The application is initializing ...\n"
                                      "Canvas initialization started."),
                                    alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                                    color=QtGui.QColor("lightgray"))
        start_plot_time = time.time()  # debug

        # set up the PlotCanvas
        self.plotcanvas = self.on_plotcanvas_setup()
        if self.plotcanvas == 'fail':
            self.splash.finish(self.ui)
            self.log.debug("Failed to start the Canvas.")

            self.clear_pool()
            self.log.error("Failed to start the Canvas")
            raise SystemError("Failed to start the Canvas")

        # add he PlotCanvas setup to the UI
        self.on_plotcanvas_add(self.plotcanvas, self.ui.right_layout)

        # #############################################################################################################
        # ################   SHAPES STORAGE   #########################################################################
        # #############################################################################################################

        # Storage for shapes, storage that can be used by FlatCAm tools for utility geometry
        if self.use_3d_engine:
            # VisPy visuals
            try:
                self.tool_shapes = ShapeCollection(parent=self.plotcanvas.view.scene, layers=1, pool=self.pool)
            except AttributeError:
                self.tool_shapes = None

            # Storage for Hover Shapes
            self.hover_shapes = ShapeCollection(parent=self.plotcanvas.view.scene, layers=1, pool=self.pool)

            # Storage for Selection shapes
            self.sel_shapes = ShapeCollection(parent=self.plotcanvas.view.scene, layers=1, pool=self.pool)
        else:
            from appGUI.PlotCanvasLegacy import ShapeCollectionLegacy
            self.tool_shapes = ShapeCollectionLegacy(obj=self, app=self, name="tool")

            # Storage for Hover Shapes will use the default Matplotlib axes
            self.hover_shapes = ShapeCollectionLegacy(obj=self, app=self, name='hover')

            # Storage for Selection shapes
            self.sel_shapes = ShapeCollectionLegacy(obj=self, app=self, name="selection")
        # #############################################################################################################

        end_plot_time = time.time()
        self.used_time = end_plot_time - start_plot_time
        self.log.debug("Finished Canvas initialization in %s seconds." % str(self.used_time))

        if show_splash:
            self.splash.showMessage('%s: %ssec' % (_("The application is initializing ...\n"
                                                     "Canvas initialization started.\n"
                                                     "Canvas initialization finished in"), '%.2f' % self.used_time),
                                    alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                                    color=QtGui.QColor("lightgray"))
        self.ui.splitter.setStretchFactor(1, 2)

        # ###########################################################################################################
        # ############################################### Worker SETUP ##############################################
        # ###########################################################################################################
        w_number = int(self.options["global_worker_number"]) if self.options["global_worker_number"] else 2
        self.workers = WorkerStack(workers_number=w_number)

        self.worker_task.connect(self.workers.add_task)
        self.log.debug("Finished creating Workers crew.")

        # ###########################################################################################################
        # ############################################# Activity Monitor ############################################
        # ###########################################################################################################
        self.proc_container = FCVisibleProcessContainer(self.ui.activity_view)

        # ###########################################################################################################
        # ########################################## Other setups ###################################################
        # ###########################################################################################################

        # Sets up FlatCAMObj, FCProcess and FCProcessContainer.
        self.setup_default_properties_tab()

        # ###########################################################################################################
        # ########################################## Tools and Plugins ##############################################
        # ###########################################################################################################

        self.dblsidedtool = None
        self.distance_tool = None
        self.distance_min_tool = None
        self.panelize_tool = None
        self.film_tool = None
        self.paste_tool = None
        self.calculator_tool = None
        self.rules_tool = None
        self.sub_tool = None
        self.move_tool = None

        self.cutout_tool = None
        self.ncclear_tool = None
        self.paint_tool = None
        self.isolation_tool = None
        self.follow_tool = None
        self.drilling_tool = None
        self.milling_tool = None
        self.levelling_tool = None

        self.optimal_tool = None
        self.transform_tool = None
        self.report_tool = None
        self.pdf_tool = None
        self.image_tool = None
        self.pcb_wizard_tool = None
        self.qrcode_tool = None
        self.copper_thieving_tool = None
        self.fiducial_tool = None
        self.extract_tool = None
        self.align_objects_tool = None
        self.punch_tool = None
        self.invert_tool = None
        self.markers_tool = None
        self.etch_tool = None

        # when this list will get populated will contain a list of references to all the Plugins in this APp
        self.app_plugins = []

        # always install tools only after the shell is initialized because the self.inform.emit() depends on shell
        try:
            self.install_tools()
        except AttributeError as e:
            self.log.debug("App.__init__() install_tools() --> %s" % str(e))

        # ###########################################################################################################
        # ######################################### BookMarks Manager ###############################################
        # ###########################################################################################################

        # install Bookmark Manager and populate bookmarks in the Help -> Bookmarks
        self.install_bookmarks()
        self.book_dialog_tab = BookmarkManager(app=self, storage=self.options["global_bookmarks"])

        # ###########################################################################################################
        # ########################################### Tools Database ################################################
        # ###########################################################################################################

        self.tools_db_tab = None

        # ### System Font Parsing ###
        # self.f_parse = ParseFont(self)
        # self.parse_system_fonts()

        # ###########################################################################################################
        # ############################################## Shell SETUP ################################################
        # ###########################################################################################################
        # show TCL shell at start-up based on the Menu -? Edit -> Preferences setting.
        if self.options["global_shell_at_startup"]:
            self.ui.shell_dock.show()
        else:
            self.ui.shell_dock.hide()

        # ###########################################################################################################
        # ######################################### Check for updates ###############################################
        # ###########################################################################################################

        # Separate thread (Not worker)
        # Check for updates on startup but only if the user consent and the app is not in Beta version
        if (self.beta is False or self.beta is None) and self.options["global_version_check"] is True:
            self.log.info("Checking for updates in background (this is version %s)." % str(self.version))

            # self.thr2 = QtCore.QThread()
            self.worker_task.emit({'fcn': self.version_check, 'params': []})
            # self.thr2.start(QtCore.QThread.Priority.LowPriority)

        # ###########################################################################################################
        # ################################## ADDING FlatCAM EDITORS section #########################################
        # ###########################################################################################################

        # watch out for the position of the editor instantiation ... if it is done before a save of the default values
        # at the first launch of the App , the editors will not be functional.
        try:
            self.geo_editor = AppGeoEditor(self)
        except Exception as es:
            self.log.error("appMain.__init__() --> Geo Editor Error: %s" % str(es))

        try:
            self.exc_editor = AppExcEditor(self)
        except Exception as es:
            self.log.error("appMain.__init__() --> Excellon Editor Error: %s" % str(es))

        try:
            self.grb_editor = AppGerberEditor(self)
        except Exception as es:
            self.log.error("appMain.__init__() --> Gerber Editor Error: %s" % str(es))

        try:
            self.gcode_editor = AppGCodeEditor(self)
        except Exception as es:
            self.log.error("appMain.__init__() --> GCode Editor Error: %s" % str(es))

        self.log.debug("Finished adding FlatCAM Editor's.")

        self.ui.set_ui_title(name=_("New Project - Not saved"))

        # ###########################################################################################################
        # ########################################### EXCLUSION AREAS ###############################################
        # ###########################################################################################################
        self.exc_areas = ExclusionAreas(app=self)

        # ###########################################################################################################
        # ###########################################################################################################
        # ###################################### INSTANTIATE CLASSES THAT HOLD THE MENU HANDLERS ####################
        # ###########################################################################################################
        # ###########################################################################################################
        self.f_handlers = appIO(app=self)
        self.edit_class = appEditor(app=self)

        # this is calculated in the class above (somehow?)
        self.options["root_folder_path"] = self.app_home

        # ###########################################################################################################
        # ##################################### FIRST RUN SECTION ###################################################
        # ################################ It's done only once after install   #####################################
        # ###########################################################################################################
        if self.options["first_run"] is True:
            # ONLY AT FIRST STARTUP INIT THE GUI LAYOUT TO 'minimal'
            self.log.debug("-> First Run: Setting up the first Layout")
            initial_lay = 'minimal'
            self.on_layout(lay=initial_lay, connect_signals=False)

            # Set the combobox in Preferences to the current layout
            idx = self.ui.general_pref_form.general_gui_group.layout_combo.findText(initial_lay)
            self.ui.general_pref_form.general_gui_group.layout_combo.setCurrentIndex(idx)

            # after the first run, this object should be False
            self.options["first_run"] = False
            self.log.debug("-> First Run: Updating the Defaults file with Factory Defaults")
            self.preferencesUiManager.save_defaults(silent=True)

        # ###########################################################################################################
        # ############################################### SYS TRAY ##################################################
        # ###########################################################################################################
        self.parent_w = QtWidgets.QWidget()
        if self.cmd_line_headless == 1:
            # if running headless always have the systray to be able to quit the app correctly
            self.trayIcon = AppSystemTray(app=self,
                                          icon=QtGui.QIcon(self.resource_location +
                                                           '/app32.png'),
                                          headless=True,
                                          parent=self.parent_w)
        else:
            if self.options["global_systray_icon"]:
                self.trayIcon = AppSystemTray(app=self,
                                              icon=QtGui.QIcon(self.resource_location + '/app32.png'),
                                              parent=self.parent_w)

        # ###########################################################################################################
        # ############################################ SETUP RECENT ITEMS ###########################################
        # ###########################################################################################################
        self.setup_recent_items()

        # ###########################################################################################################
        # ###########################################################################################################
        # ############################################# Signal handling #############################################
        # ###########################################################################################################
        # ###########################################################################################################

        # ########################################## Custom signals  ################################################
        # signal for displaying messages in status bar
        self.inform[str].connect(self.info)
        self.inform[str, bool].connect(self.info)
        self.inform_no_echo[str].connect(lambda txt: self.info(msg=txt, shell_echo=False))  # noqa

        # signals for displaying messages in the Tcl Shell are now connected in the ToolShell class

        # loading a project
        self.restore_project.connect(self.f_handlers.restore_project_handler)   # noqa
        self.restore_project_objects_sig.connect(self.f_handlers.restore_project_objects)   # noqa
        # signal to be called when the app is quiting
        self.app_quit.connect(self.quit_application, type=Qt.ConnectionType.QueuedConnection)
        self.message.connect(
            lambda title, msg, kind: message_dialog(title=title, message=msg, kind=kind, parent=self.ui))
        # self.progress.connect(self.set_progress_bar)

        # signals emitted when file state change
        self.file_opened.connect(self.register_recent)
        self.file_opened.connect(lambda kind, filename: self.register_folder(filename))
        self.file_saved.connect(lambda kind, filename: self.register_save_folder(filename))

        # when the options dictionary values change
        self.options.set_change_callback(callback=self.on_options_value_changed)

        # post_edit signal
        self.post_edit_sig.connect(self.on_editing_final_action, type=Qt.ConnectionType.QueuedConnection)

        # ###########################################################################################################
        # ########################################## Standard signals ###############################################
        # ###########################################################################################################
        # File Signals
        self.connect_filemenu_signals()

        # Edit Signals
        self.connect_editmenu_signals()

        # Options Signals
        self.connect_optionsmenu_signals()

        # View Signals
        self.connect_menuview_signals()

        # Tool Signals
        self.ui.menu_plugins_shell.triggered.connect(self.ui.toggle_shell_ui)
        # the rest are auto-inserted

        # Help Signals
        self.connect_menuhelp_signals()

        # Project Context Menu Signals
        self.connect_project_context_signals()

        # ToolBar signals
        self.connect_toolbar_signals()

        # Canvas Context Menu
        self.connect_canvas_context_signals()

        # Notebook tab clicking
        # self.ui.notebook.tabBarClicked.connect(self.on_properties_tab_click)
        self.ui.notebook.currentChanged.connect(self.on_notebook_tab_changed)

        # self.ui.notebook.callback_on_close = self.on_close_notebook_tab

        # Plot Area double clicking
        self.ui.plot_tab_area.tabBarDoubleClicked.connect(self.on_plot_area_tab_double_clicked)

        # ###########################################################################################################
        # #################################### GUI PREFERENCES SIGNALS ##############################################
        # ###########################################################################################################

        # ##################################### Workspace Setting Signals ###########################################
        self.ui.general_pref_form.general_app_set_group.wk_cb.currentIndexChanged.connect(
            self.on_workspace_modified)
        self.ui.general_pref_form.general_app_set_group.wk_orientation_radio.activated_custom.connect(
            self.on_workspace_modified
        )

        self.ui.general_pref_form.general_app_set_group.workspace_cb.stateChanged.connect(self.on_workspace)

        # ###########################################################################################################
        # ######################################## GUI SETTINGS SIGNALS #############################################
        # ###########################################################################################################
        self.ui.general_pref_form.general_app_set_group.cursor_radio.activated_custom.connect(self.on_cursor_type)

        # ######################################## Tools related signals ############################################

        # portability changed signal
        self.ui.general_pref_form.general_app_group.portability_cb.stateChanged.connect(self.on_portable_checked)

        # Object list
        self.object_status_changed.connect(self.collection.on_collection_updated)

        # when there are arguments at application startup this get launched
        self.args_at_startup[list].connect(self.on_startup_args)

        # ###########################################################################################################
        # ########################################### GUI SIGNALS ###################################################
        # ###########################################################################################################
        self.ui.hud_label.clicked.connect(self.plotcanvas.on_toggle_hud)
        self.ui.axis_status_label.clicked.connect(self.plotcanvas.on_toggle_axis)
        self.ui.pref_status_label.clicked.connect(self.on_toggle_preferences)

        # ###########################################################################################################
        # ####################################### VARIOUS SIGNALS ###################################################
        # ###########################################################################################################
        # connect the abort_all_tasks related slots to the related signals
        self.proc_container.idle_flag.connect(self.app_is_idle)

        # signal emitted when a tab is closed in the Plot Area
        self.ui.plot_tab_area.tab_closed_signal.connect(self.on_plot_area_tab_closed)

        # signal emitted when a tab is closed in the Plot Area
        self.ui.notebook.tab_closed_signal.connect(self.on_notebook_closed)

        # signal to close the application
        self.close_app_signal.connect(self.kill_app)    # noqa

        # signal to process the body of a script
        self.run_script.connect(self.script_processing)     # noqa
        # ################################# FINISHED CONNECTING SIGNALS #############################################
        # ###########################################################################################################
        # ###########################################################################################################
        # ###########################################################################################################

        self.log.debug("Finished connecting Signals.")

        # ###########################################################################################################
        # ##################################### Finished the CONSTRUCTOR ############################################
        # ###########################################################################################################
        self.log.debug("END of constructor. Releasing control.")
        self.log.debug("... Resistance is futile. You will be assimilated ...")
        self.log.debug("... I disagree. While we live and breath, we can be free!\n")

        # ###########################################################################################################
        # ########################################## SHOW GUI #######################################################
        # ###########################################################################################################

        # if the app is not started as headless, show it
        if self.cmd_line_headless != 1:
            if show_splash:
                # finish the splash
                self.splash.finish(self.ui)

            mgui_settings = QSettings("Open Source", "FlatCAM_EVO")
            if mgui_settings.contains("maximized_gui"):
                maximized_ui = mgui_settings.value('maximized_gui', type=bool)
                if maximized_ui is True:
                    self.ui.showMaximized()
                else:
                    self.ui.show()
            else:
                self.ui.show()

            if self.options["global_systray_icon"]:
                self.trayIcon.show()
        else:
            try:
                self.trayIcon.show()
            except Exception as t_err:
                self.log.error("App.__init__() Running headless and trying to show the systray got: %s" % str(t_err))
            self.log.warning("*******************  RUNNING HEADLESS  *******************")

        # ###########################################################################################################
        # ######################################## START-UP ARGUMENTS ###############################################
        # ###########################################################################################################

        # test if the program was started with a script as parameter
        if self.cmd_line_shellvar:
            try:
                cnt = 0
                command_tcl = 0
                for i in self.cmd_line_shellvar.split(','):
                    if i is not None:
                        # noinspection PyBroadException
                        try:
                            command_tcl = eval(i)
                        except Exception:
                            command_tcl = i

                    command_tcl_formatted = 'set shellvar_{nr} "{cmd}"'.format(cmd=str(command_tcl), nr=str(cnt))

                    cnt += 1

                    # if there are Windows paths then replace the path separator with a Unix like one
                    if sys.platform == 'win32':
                        command_tcl_formatted = command_tcl_formatted.replace('\\', '/')
                    self.shell.exec_command(command_tcl_formatted, no_echo=True)
            except Exception as ext:
                print("ERROR: ", ext)
                sys.exit(2)

        if self.cmd_line_shellfile:
            if self.cmd_line_headless != 1:
                if self.ui.shell_dock.isHidden():
                    self.ui.shell_dock.show()
            try:
                with open(self.cmd_line_shellfile, "r") as myfile:
                    # if show_splash:
                    #     self.splash.showMessage('%s: %ssec\n%s' % (
                    #         _("Canvas initialization started.\n"
                    #           "Canvas initialization finished in"), '%.2f' % self.used_time,
                    #         _("Executing Tcl Script ...")),
                    #                             alignment=Qt.AlignBottom | Qt.AlignLeft,
                    #                             color=QtGui.QColor("lightgray"))
                    cmd_line_shellfile_text = myfile.read()
                    if self.cmd_line_headless != 1:
                        self.shell.exec_command(cmd_line_shellfile_text)
                    else:
                        self.shell.exec_command(cmd_line_shellfile_text, no_echo=True)

            except Exception as ext:
                print("ERROR: ", ext)
                sys.exit(2)

        # accept some type file as command line parameter: FlatCAM project, FlatCAM preferences or scripts
        # the path/file_name must be enclosed in quotes, if it contains spaces
        if App.args:
            self.args_at_startup.emit(App.args)

        if self.defaults.old_defaults_found is True:
            self.inform.emit('[WARNING_NOTCL] %s' % _("Found old default preferences files. "
                                                      "Please reboot the application to update."))
            self.defaults.old_defaults_found = False

    # ######################################### INIT FINISHED  #######################################################
    # #################################################################################################################
    # #################################################################################################################
    # #################################################################################################################
    # #################################################################################################################
    # #################################################################################################################

    @staticmethod
    def copy_and_overwrite(from_path, to_path):
        """
        From here:
        https://stackoverflow.com/questions/12683834/how-to-copy-directory-recursively-in-python-and-overwrite-all

        :param from_path: source path
        :param to_path: destination path
        :return: None
        """
        if os.path.exists(to_path):
            shutil.rmtree(to_path)
        try:
            shutil.copytree(from_path, to_path)
        except FileNotFoundError:
            from_new_path = os.path.dirname(os.path.realpath(__file__)) + '\\appGUI\\VisPyData\\data'
            shutil.copytree(from_new_path, to_path)

    def on_startup_args(self, args, silent=False):
        """
        This will process any arguments provided to the application at startup. Like trying to launch a file or project.

        :param silent: when True it will not print messages on Tcl Shell and/or status bar
        :param args: a list containing the application args at startup
        :return: None
        """

        if args is not None:
            args_to_process = args
        else:
            args_to_process = App.args

        self.log.debug("Application was started with arguments: %s. Processing ..." % str(args_to_process))
        for argument in args_to_process:
            if '.FlatPrj'.lower() in argument.lower():
                try:
                    project_name = str(argument)

                    if project_name == "":
                        if silent is False:
                            self.inform.emit(_("Cancelled."))
                    else:
                        # self.open_project(project_name)
                        run_from_arg = True
                        # self.worker_task.emit({'fcn': self.open_project,
                        #                        'params': [project_name, run_from_arg]})
                        self.f_handlers.open_project(filename=project_name, run_from_arg=run_from_arg)
                except Exception as e:
                    self.log.error("Could not open FlatCAM project file as App parameter due: %s" % str(e))

            elif '.FlatConfig'.lower() in argument.lower():
                try:
                    file_name = str(argument)

                    if file_name == "":
                        if silent is False:
                            self.inform.emit(_("Open Config file failed."))
                    else:
                        run_from_arg = True
                        # self.worker_task.emit({'fcn': self.open_config_file,
                        #                        'params': [file_name, run_from_arg]})
                        self.f_handlers.open_config_file(file_name, run_from_arg=run_from_arg)
                except Exception as e:
                    self.log.error("Could not open FlatCAM Config file as App parameter due: %s" % str(e))

            elif '.FlatScript'.lower() in argument.lower() or '.TCL'.lower() in argument.lower():
                try:
                    file_name = str(argument)

                    if file_name == "":
                        if silent is False:
                            self.inform.emit(_("Open Script file failed."))
                    else:
                        if silent is False:
                            self.f_handlers.on_file_open_script(name=file_name)
                            self.ui.plot_tab_area.setCurrentWidget(self.ui.plot_tab)
                        self.f_handlers.on_file_run_cript(name=file_name)
                except Exception as e:
                    self.log.error("Could not open FlatCAM Script file as App parameter due: %s" % str(e))

            elif 'quit'.lower() in argument.lower() or 'exit'.lower() in argument.lower():
                self.log.debug("App.on_startup_args() --> Quit event.")
                sys.exit()

            elif 'save'.lower() in argument.lower():
                self.log.debug("App.on_startup_args() --> Save event. App Defaults saved.")
                self.defaults.update(self.options)
                self.preferencesUiManager.save_defaults()
            else:
                exc_list = self.ui.util_pref_form.fa_excellon_group.exc_list_text.get_value().split(',')
                proc_arg = argument.lower()
                for ext in exc_list:
                    proc_ext = ext.replace(' ', '')
                    proc_ext = '.%s' % proc_ext
                    if proc_ext.lower() in proc_arg and proc_ext != '.':
                        file_name = str(argument)
                        if file_name == "":
                            if silent is False:
                                self.inform.emit(_("Open Excellon file failed."))
                        else:
                            self.f_handlers.on_file_open_excellon(name=file_name)
                            return

                gco_list = self.ui.util_pref_form.fa_gcode_group.gco_list_text.get_value().split(',')
                for ext in gco_list:
                    proc_ext = ext.replace(' ', '')
                    proc_ext = '.%s' % proc_ext
                    if proc_ext.lower() in proc_arg and proc_ext != '.':
                        file_name = str(argument)
                        if file_name == "":
                            if silent is False:
                                self.inform.emit(_("Open GCode file failed."))
                        else:
                            self.f_handlers.on_file_open_gcode(name=file_name)
                            return

                grb_list = self.ui.util_pref_form.fa_gerber_group.grb_list_text.get_value().split(',')
                for ext in grb_list:
                    proc_ext = ext.replace(' ', '')
                    proc_ext = '.%s' % proc_ext
                    if proc_ext.lower() in proc_arg and proc_ext != '.':
                        file_name = str(argument)
                        if file_name == "":
                            if silent is False:
                                self.inform.emit(_("Open Gerber file failed."))
                        else:
                            self.f_handlers.on_file_open_gerber(name=file_name)
                            return

        # if it reached here without already returning then the app was registered with a file that it does not
        # recognize therefore we must quit but take into consideration the app reboot from within, in that case
        # the args_to_process will contain the path to the FlatCAM.exe (cx_freezed executable)

        # for arg in args_to_process:
        #     if 'FlatCAM.exe' in arg:
        #         continue
        #     else:
        #         sys.exit(2)

    def tools_database_path(self):
        return os.path.join(self.data_path, 'tools_db_%s.FlatDB' % str(self.version))

    def defaults_path(self):
        return os.path.join(self.data_path, 'current_defaults_%s.FlatConfig' % str(self.version))

    def factory_defaults_path(self):
        return os.path.join(self.data_path, 'factory_defaults_%s.FlatConfig' % str(self.version))

    def recent_files_path(self):
        return os.path.join(self.data_path, 'recent.json')

    def recent_projects_path(self):
        return os.path.join(self.data_path, 'recent_projects.json')

    def preprocessors_path(self):
        return os.path.join(self.data_path, 'preprocessors')

    def log_path(self):
        return os.path.join(self.data_path, 'log.txt')

    def on_options_value_changed(self, key_changed):
        # when changing those properties the associated keys change, so we get an updated Properties default Tab
        if key_changed in [
            "global_grid_lines", "global_grid_snap", "global_axis", "global_workspace", "global_workspaceT",
            "global_workspace_orientation", "global_hud"
        ]:
            self.on_properties_tab_click()

        # TODO handle changing the units in the Preferences
        # if key_changed == "units":
        #     self.on_toggle_units(no_pref=False)

    def on_app_restart(self):

        # make sure that the Sys Tray icon is hidden before restart otherwise it will
        # be left in the SySTray
        try:
            self.trayIcon.hide()
        except Exception:
            pass

        fcTranslate.restart_program(app=self)

    def clear_pool(self):
        """
        Clear the multiprocessing pool and calls garbage collector.

        :return: None
        """
        self.pool.close()

        self.pool = Pool(processes=self.options["global_process_number"])
        self.pool_recreated.emit(self.pool)

        gc.collect()

    def install_tools(self, init_tcl=False):
        """
        This installs the FlatCAM tools (plugin-like) which reside in their own classes.
        Instantiation of the Tools classes.
        The order that the tools are installed is important as they can depend on each other installing position.

        :return: None
        """

        if init_tcl:
            # Tcl "Shell" tool has to be initialized always first because other tools print messages in the Shell Dock
            self.shell = FCShell(app=self, version=self.version)
            self.log.debug("TCL was re-instantiated. TCL variables are reset.")

        self.distance_tool = Distance(self)
        self.distance_tool.install(icon=QtGui.QIcon(self.resource_location + '/distance16.png'), pos=self.ui.menuedit,
                                   before=self.ui.menuedit_numeric_move,
                                   separator=False)

        self.distance_min_tool = ObjectDistance(self)
        self.distance_min_tool.install(icon=QtGui.QIcon(self.resource_location + '/distance_min16.png'),
                                       pos=self.ui.menuedit,
                                       before=self.ui.menuedit_numeric_move,
                                       separator=True)

        self.dblsidedtool = DblSidedTool(self)
        self.dblsidedtool.install(icon=QtGui.QIcon(self.resource_location + '/doubleside16.png'), separator=False)

        self.align_objects_tool = AlignObjects(self)
        self.align_objects_tool.install(icon=QtGui.QIcon(self.resource_location + '/align16.png'), separator=False)

        self.extract_tool = ToolExtract(self)
        self.extract_tool.install(icon=QtGui.QIcon(self.resource_location + '/extract32.png'), separator=True)

        self.panelize_tool = Panelize(self)
        self.panelize_tool.install(icon=QtGui.QIcon(self.resource_location + '/panelize16.png'))

        self.film_tool = Film(self)
        self.film_tool.install(icon=QtGui.QIcon(self.resource_location + '/film32.png'))

        self.paste_tool = SolderPaste(self)
        self.paste_tool.install(icon=QtGui.QIcon(self.resource_location + '/solderpastebis32.png'))

        self.calculator_tool = ToolCalculator(self)
        self.calculator_tool.install(icon=QtGui.QIcon(self.resource_location + '/calculator32.png'), separator=True)

        self.sub_tool = ToolSub(self)
        self.sub_tool.install(icon=QtGui.QIcon(self.resource_location + '/sub32.png'),
                              pos=self.ui.menu_plugins, separator=True)

        self.rules_tool = RulesCheck(self)
        self.rules_tool.install(icon=QtGui.QIcon(self.resource_location + '/rules32.png'),
                                pos=self.ui.menu_plugins, separator=False)

        self.optimal_tool = ToolOptimal(self)
        self.optimal_tool.install(icon=QtGui.QIcon(self.resource_location + '/open_excellon32.png'),
                                  pos=self.ui.menu_plugins, separator=True)

        self.move_tool = ToolMove(self)
        self.move_tool.install(icon=QtGui.QIcon(self.resource_location + '/move16.png'), pos=self.ui.menuedit,
                               before=self.ui.menuedit_numeric_move, separator=True)

        self.cutout_tool = CutOut(self)
        self.cutout_tool.install(icon=QtGui.QIcon(self.resource_location + '/cut32.png'), pos=self.ui.menu_plugins,
                                 before=self.sub_tool.menuAction)

        self.ncclear_tool = NonCopperClear(self)
        self.ncclear_tool.install(icon=QtGui.QIcon(self.resource_location + '/ncc32.png'), pos=self.ui.menu_plugins,
                                  before=self.sub_tool.menuAction, separator=True)

        self.paint_tool = ToolPaint(self)
        self.paint_tool.install(icon=QtGui.QIcon(self.resource_location + '/paint32.png'), pos=self.ui.menu_plugins,
                                before=self.sub_tool.menuAction, separator=True)

        self.isolation_tool = ToolIsolation(self)
        self.isolation_tool.install(icon=QtGui.QIcon(self.resource_location + '/iso_16.png'), pos=self.ui.menu_plugins,
                                    before=self.sub_tool.menuAction, separator=True)

        self.follow_tool = ToolFollow(self)
        self.follow_tool.install(icon=QtGui.QIcon(self.resource_location + '/follow32.png'), pos=self.ui.menu_plugins,
                                 before=self.sub_tool.menuAction, separator=True)

        self.drilling_tool = ToolDrilling(self)
        self.drilling_tool.install(icon=QtGui.QIcon(self.resource_location + '/extract_drill32.png'),
                                   pos=self.ui.menu_plugins, before=self.sub_tool.menuAction, separator=True)
        self.milling_tool = ToolMilling(self)
        self.milling_tool.install(icon=QtGui.QIcon(self.resource_location + '/milling_tool32.png'),
                                  pos=self.ui.menu_plugins, before=self.sub_tool.menuAction, separator=True)

        self.levelling_tool = ToolLevelling(self)
        self.levelling_tool.install(icon=QtGui.QIcon(self.resource_location + '/level32.png'),
                                    pos=self.ui.menuoptions_experimental, separator=True)

        self.copper_thieving_tool = ToolCopperThieving(self)
        self.copper_thieving_tool.install(icon=QtGui.QIcon(self.resource_location + '/copperfill32.png'),
                                          pos=self.ui.menu_plugins)

        self.fiducial_tool = ToolFiducials(self)
        self.fiducial_tool.install(icon=QtGui.QIcon(self.resource_location + '/fiducials_32.png'),
                                   pos=self.ui.menu_plugins)

        self.qrcode_tool = QRCode(self)
        self.qrcode_tool.install(icon=QtGui.QIcon(self.resource_location + '/qrcode32.png'),
                                 pos=self.ui.menu_plugins)

        self.punch_tool = ToolPunchGerber(self)
        self.punch_tool.install(icon=QtGui.QIcon(self.resource_location + '/punch32.png'), pos=self.ui.menu_plugins)

        self.invert_tool = ToolInvertGerber(self)
        self.invert_tool.install(icon=QtGui.QIcon(self.resource_location + '/invert32.png'), pos=self.ui.menu_plugins)

        self.markers_tool = ToolMarkers(self)
        self.markers_tool.install(icon=QtGui.QIcon(self.resource_location + '/corners_32.png'),
                                  pos=self.ui.menu_plugins)

        self.etch_tool = ToolEtchCompensation(self)
        self.etch_tool.install(icon=QtGui.QIcon(self.resource_location + '/etch_32.png'), pos=self.ui.menu_plugins)

        self.transform_tool = ToolTransform(self)
        self.transform_tool.install(icon=QtGui.QIcon(self.resource_location + '/transform.png'),
                                    pos=self.ui.menuoptions, separator=True)

        self.report_tool = ObjectReport(self)
        self.report_tool.install(icon=QtGui.QIcon(self.resource_location + '/properties32.png'),
                                 pos=self.ui.menuoptions)

        self.pdf_tool = ToolPDF(self)
        self.pdf_tool.install(icon=QtGui.QIcon(self.resource_location + '/pdf32.png'),
                              pos=self.ui.menufileimport,
                              separator=True)

        try:
            self.image_tool = ToolImage(self)
            self.image_tool.install(icon=QtGui.QIcon(self.resource_location + '/image32.png'),
                                    pos=self.ui.menufileimport,
                                    separator=True)
        except Exception as im_err:
            self.log.error("Image Import plugin could not be started due of: %s" % str(im_err))
            self.image_tool = lambda x: None

        self.pcb_wizard_tool = PcbWizard(self)
        self.pcb_wizard_tool.install(icon=QtGui.QIcon(self.resource_location + '/drill32.png'),
                                     pos=self.ui.menufileimport)

        # create a list of plugins references
        self.app_plugins = [
            self.dblsidedtool,
            self.distance_tool,
            self.distance_min_tool,
            self.panelize_tool,
            self.film_tool,
            self.paste_tool,
            self.calculator_tool,
            self.rules_tool,
            self.sub_tool,
            self.move_tool,

            self.cutout_tool,
            self.ncclear_tool,
            self.paint_tool,
            self.isolation_tool,
            self.follow_tool,
            self.drilling_tool,
            self.milling_tool,
            self.levelling_tool,

            self.optimal_tool,
            self.transform_tool,
            self.report_tool,
            self.pdf_tool,
            self.image_tool,
            self.pcb_wizard_tool,
            self.qrcode_tool,
            self.copper_thieving_tool,
            self.fiducial_tool,
            self.extract_tool,
            self.align_objects_tool,
            self.punch_tool,
            self.invert_tool,
            self.markers_tool,
            self.etch_tool
        ]

        self.log.debug("Tools are installed.")

    def remove_tools(self):
        """
        Will remove all the actions in the Tool menu.
        :return: None
        """
        for act in self.ui.menu_plugins.actions():
            self.ui.menu_plugins.removeAction(act)

    def init_tools(self, init_tcl=True):
        """
        Initialize the Tool tab in the notebook side of the central widget.
        Remove the actions in the Tools menu.
        Instantiate again the FlatCAM tools (plugins).
        All this is required when changing the layout: standard, compact etc.

        :param init_tcl:    Bool. If True will init the Tcl Shell
        :return:            None
        """

        self.log.debug("init_tools()")

        # delete the data currently in the Tools Tab and the Tab itself
        found_idx = None
        for tab_idx in range(self.ui.notebook.count()):
            if self.ui.notebook.widget(tab_idx).objectName() == "plugin_tab":
                found_idx = tab_idx
                print(found_idx)
                break
        remove_idx = found_idx if found_idx else 2
        widget = QtWidgets.QTabWidget.widget(self.ui.notebook, remove_idx)
        if widget is not None:
            widget.deleteLater()
        self.ui.notebook.removeTab(remove_idx)

        # rebuild the Tools Tab
        # self.ui.plugin_tab = QtWidgets.QWidget()
        # self.ui.plugin_tab_layout = QtWidgets.QVBoxLayout(self.ui.plugin_tab)
        # self.ui.plugin_tab_layout.setContentsMargins(2, 2, 2, 2)
        # self.ui.notebook.addTab(self.ui.plugin_tab, _("Tool"))
        # self.ui.plugin_scroll_area = VerticalScrollArea()
        # self.ui.plugin_tab_layout.addWidget(self.ui.plugin_scroll_area)

        # reinstall all the Tools as some may have been removed when the data was removed from the Tools Tab
        # first remove all of them
        self.remove_tools()

        # re-add the TCL "Shell" action to the Tools menu and reconnect it to ist slot function
        self.ui.menu_plugins_shell = self.ui.menu_plugins.addAction(
            QtGui.QIcon(self.resource_location + '/shell16.png'), '&Command Line\tS')
        self.ui.menu_plugins_shell.triggered.connect(self.ui.toggle_shell_ui)

        # third install all of them
        t0 = time.time()
        try:
            self.install_tools(init_tcl=init_tcl)
        except AttributeError:
            pass

        self.log.debug("%s: %s" % ("Tools are initialized in", str(time.time() - t0)))

    # def parse_system_fonts(self):
    #     self.worker_task.emit({'fcn': self.f_parse.get_fonts_by_types,
    #                            'params': []})

    def connect_filemenu_signals(self):
        # ### Menu
        self.ui.menufilenewproject.triggered.connect(self.f_handlers.on_file_new_click)
        self.ui.menufilenewgeo.triggered.connect(lambda: self.app_obj.new_geometry_object())
        self.ui.menufilenewgrb.triggered.connect(lambda: self.app_obj.new_gerber_object())
        self.ui.menufilenewexc.triggered.connect(lambda: self.app_obj.new_excellon_object())
        self.ui.menufilenewdoc.triggered.connect(lambda: self.app_obj.new_document_object())

        self.ui.menufileopengerber.triggered.connect(lambda: self.f_handlers.on_file_open_gerber())
        self.ui.menufileopenexcellon.triggered.connect(lambda: self.f_handlers.on_file_open_excellon())
        self.ui.menufileopengcode.triggered.connect(lambda: self.f_handlers.on_file_open_gcode())
        self.ui.menufileopenproject.triggered.connect(lambda: self.f_handlers.on_file_open_project())
        self.ui.menufileopenconfig.triggered.connect(lambda: self.f_handlers.on_file_open_config())

        self.ui.menufilenewscript.triggered.connect(self.f_handlers.on_file_new_script)
        self.ui.menufileopenscript.triggered.connect(self.f_handlers.on_file_open_script)
        self.ui.menufileopenscriptexample.triggered.connect(self.f_handlers.on_file_open_script_example)

        self.ui.menufilerunscript.triggered.connect(self.f_handlers.on_file_run_cript)

        self.ui.menufileimportsvg.triggered.connect(lambda: self.f_handlers.on_file_import_svg("geometry"))
        self.ui.menufileimportsvg_as_gerber.triggered.connect(lambda: self.f_handlers.on_file_import_svg("gerber"))

        self.ui.menufileimportdxf.triggered.connect(lambda: self.f_handlers.on_file_import_dxf("geometry"))
        self.ui.menufileimportdxf_as_gerber.triggered.connect(lambda: self.f_handlers.on_file_import_dxf("gerber"))
        self.ui.menufileimport_hpgl2_as_geo.triggered.connect(lambda: self.f_handlers.on_file_open_hpgl2())
        self.ui.menufileexportsvg.triggered.connect(self.f_handlers.on_file_export_svg)
        self.ui.menufileexportpng.triggered.connect(self.f_handlers.on_file_export_png)
        self.ui.menufileexportexcellon.triggered.connect(self.f_handlers.on_file_export_excellon)
        self.ui.menufileexportgerber.triggered.connect(self.f_handlers.on_file_export_gerber)

        self.ui.menufileexportdxf.triggered.connect(self.f_handlers.on_file_export_dxf)

        self.ui.menufile_print.triggered.connect(lambda: self.f_handlers.on_file_save_objects_pdf(use_thread=True))

        self.ui.menufilesaveproject.triggered.connect(self.f_handlers.on_file_save_project)
        self.ui.menufilesaveprojectas.triggered.connect(self.f_handlers.on_file_save_project_as)
        # self.ui.menufilesaveprojectcopy.triggered.connect(lambda: self.on_file_save_project_as(make_copy=True))
        self.ui.menufilesavedefaults.triggered.connect(self.f_handlers.on_file_save_defaults)

        self.ui.menufileexportpref.triggered.connect(self.f_handlers.on_export_preferences)
        self.ui.menufileimportpref.triggered.connect(self.f_handlers.on_import_preferences)

    def connect_editmenu_signals(self):
        self.ui.menufile_exit.triggered.connect(self.final_save)

        self.ui.menueditedit.triggered.connect(lambda: self.on_editing_start())
        self.ui.menueditok.triggered.connect(lambda: self.on_editing_finished())

        self.ui.menuedit_join2geo.triggered.connect(self.edit_class.on_edit_join)
        self.ui.menuedit_join_exc2exc.triggered.connect(self.edit_class.on_edit_join_exc)
        self.ui.menuedit_join_grb2grb.triggered.connect(self.edit_class.on_edit_join_grb)

        self.ui.menuedit_convert_sg2mg.triggered.connect(self.edit_class.on_convert_singlegeo_to_multigeo)
        self.ui.menuedit_convert_mg2sg.triggered.connect(self.edit_class.on_convert_multigeo_to_singlegeo)

        self.ui.menueditdelete.triggered.connect(self.on_delete)

        self.ui.menueditcopyobject.triggered.connect(self.on_copy_command)
        self.ui.menueditconvert_any2geo.triggered.connect(lambda: self.edit_class.convert_any2geo())
        self.ui.menueditconvert_any2gerber.triggered.connect(lambda: self.edit_class.convert_any2gerber())
        self.ui.menueditconvert_any2excellon.triggered.connect(lambda: self.edit_class.convert_any2excellon())

        self.ui.menuedit_numeric_move.triggered.connect(lambda: self.on_numeric_move())

        self.ui.menueditorigin.triggered.connect(self.on_set_origin)
        self.ui.menuedit_move2origin.triggered.connect(self.on_move2origin)
        self.ui.menuedit_center_in_origin.triggered.connect(self.edit_class.on_custom_origin)

        self.ui.menueditjump.triggered.connect(self.on_jump_to)
        self.ui.menueditlocate.triggered.connect(lambda: self.on_locate(obj=self.collection.get_active()))

        self.ui.menueditselectall.triggered.connect(self.on_selectall)
        self.ui.menueditpreferences.triggered.connect(self.on_preferences)

    def connect_optionsmenu_signals(self):
        # self.ui.menuoptions_transfer_a2o.triggered.connect(self.on_options_app2object)
        # self.ui.menuoptions_transfer_a2p.triggered.connect(self.on_defaults2options)
        # self.ui.menuoptions_transfer_o2a.triggered.connect(self.on_options_object2app)
        # self.ui.menuoptions_transfer_p2a.triggered.connect(self.on_options_project2app)
        # self.ui.menuoptions_transfer_o2p.triggered.connect(self.on_options_object2project)
        # self.ui.menuoptions_transfer_p2o.triggered.connect(self.on_options_project2object)

        self.ui.menuoptions_transform_rotate.triggered.connect(self.on_rotate)

        self.ui.menuoptions_transform_skewx.triggered.connect(self.on_skewx)
        self.ui.menuoptions_transform_skewy.triggered.connect(self.on_skewy)

        self.ui.menuoptions_transform_flipx.triggered.connect(self.on_flipx)
        self.ui.menuoptions_transform_flipy.triggered.connect(self.on_flipy)
        self.ui.menuoptions_view_source.triggered.connect(self.on_view_source)
        self.ui.menuoptions_tools_db.triggered.connect(lambda: self.on_tools_database(source='app'))
        self.ui.menuoptions_experimental_3D_area.triggered.connect(self.on_3d_area)

    def connect_menuview_signals(self):
        self.ui.menuviewenable.triggered.connect(self.enable_all_plots)
        self.ui.menuviewdisableall.triggered.connect(self.disable_all_plots)
        self.ui.menuviewenableother.triggered.connect(self.enable_other_plots)
        self.ui.menuviewdisableother.triggered.connect(self.disable_other_plots)

        self.ui.menuview_zoom_fit.triggered.connect(self.on_zoom_fit)
        self.ui.menuview_zoom_in.triggered.connect(self.on_zoom_in)
        self.ui.menuview_zoom_out.triggered.connect(self.on_zoom_out)
        self.ui.menuview_replot.triggered.connect(self.plot_all)

        self.ui.menuview_toggle_code_editor.triggered.connect(self.on_toggle_code_editor)
        self.ui.menuview_toggle_fscreen.triggered.connect(self.ui.on_full_screen_toggled)
        self.ui.menuview_toggle_parea.triggered.connect(self.ui.on_toggle_plotarea)
        self.ui.menuview_toggle_notebook.triggered.connect(self.ui.on_toggle_notebook)
        self.ui.menu_toggle_nb.triggered.connect(self.ui.on_toggle_notebook)
        self.ui.menuview_toggle_grid.triggered.connect(self.ui.on_toggle_grid)
        self.ui.menuview_toggle_workspace.triggered.connect(self.on_workspace_toggle)

        self.ui.menuview_toggle_grid_lines.triggered.connect(self.plotcanvas.on_toggle_grid_lines)
        self.ui.menuview_toggle_axis.triggered.connect(self.plotcanvas.on_toggle_axis)
        self.ui.menuview_toggle_hud.triggered.connect(self.plotcanvas.on_toggle_hud)
        self.ui.menuview_show_log.triggered.connect(self.on_show_log)

    def connect_menuhelp_signals(self):
        self.ui.menuhelp_about.triggered.connect(self.on_about)
        self.ui.menuhelp_readme.triggered.connect(self.on_howto)
        self.ui.menuhelp_donate.triggered.connect(lambda: webbrowser.open(self.donate_url))
        self.ui.menuhelp_manual.triggered.connect(lambda: webbrowser.open(self.manual_url))
        self.ui.menuhelp_report_bug.triggered.connect(lambda: webbrowser.open(self.bug_report_url))
        self.ui.menuhelp_exc_spec.triggered.connect(lambda: webbrowser.open(self.excellon_spec_url))
        self.ui.menuhelp_gerber_spec.triggered.connect(lambda: webbrowser.open(self.gerber_spec_url))
        self.ui.menuhelp_videohelp.triggered.connect(lambda: webbrowser.open(self.video_url))
        self.ui.menuhelp_shortcut_list.triggered.connect(self.ui.on_shortcut_list)

    def connect_project_context_signals(self):
        self.ui.menuprojectenable.triggered.connect(lambda: self.on_enable_sel_plots())
        self.ui.menuprojectdisable.triggered.connect(self.on_disable_sel_plots)
        self.ui.menuprojectviewsource.triggered.connect(self.on_view_source)

        self.ui.menuprojectcopy.triggered.connect(self.on_copy_command)
        self.ui.menuprojectedit.triggered.connect(self.on_editing_start)

        self.ui.menuprojectdelete.triggered.connect(self.on_delete)
        self.ui.menuprojectsave.triggered.connect(self.on_project_context_save)
        self.ui.menuprojectproperties.triggered.connect(self.obj_properties)

        # Project Context Menu -> Color Setting
        for act in self.ui.menuprojectcolor.actions():
            act.triggered.connect(self.on_set_color_action_triggered)

    def connect_canvas_context_signals(self):
        self.ui.popmenu_disable.triggered.connect(lambda: self.toggle_plots(self.collection.get_selected()))
        self.ui.popmenu_panel_toggle.triggered.connect(self.ui.on_toggle_notebook)

        # New
        self.ui.popmenu_new_geo.triggered.connect(lambda: self.app_obj.new_geometry_object())
        self.ui.popmenu_new_grb.triggered.connect(lambda: self.app_obj.new_gerber_object())
        self.ui.popmenu_new_exc.triggered.connect(lambda: self.app_obj.new_excellon_object())
        self.ui.popmenu_new_prj.triggered.connect(lambda: self.f_handlers.on_file_new_project())

        # View
        self.ui.zoomfit.triggered.connect(self.on_zoom_fit)
        self.ui.clearplot.triggered.connect(self.clear_plots)
        self.ui.replot.triggered.connect(self.plot_all)

        # Colors
        for act in self.ui.pop_menucolor.actions():
            act.triggered.connect(self.on_set_color_action_triggered)

        self.ui.popmenu_copy.triggered.connect(self.on_copy_command)
        self.ui.popmenu_delete.triggered.connect(self.on_delete)
        self.ui.popmenu_edit.triggered.connect(self.on_editing_start)
        self.ui.popmenu_save.triggered.connect(lambda: self.on_editing_finished())
        self.ui.popmenu_numeric_move.triggered.connect(lambda: self.on_numeric_move())
        self.ui.popmenu_move.triggered.connect(self.obj_move)
        self.ui.popmenu_move2origin.triggered.connect(self.on_move2origin)

        self.ui.popmenu_properties.triggered.connect(self.obj_properties)

    def connect_tools_signals_to_toolbar(self):
        self.log.debug(" -> Connecting Plugin Toolbar Signals")

        self.ui.drill_btn.triggered.connect(lambda: self.drilling_tool.run(toggle=True))
        self.ui.mill_btn.triggered.connect(lambda: self.milling_tool.run(toggle=True))
        self.ui.level_btn.triggered.connect(lambda: self.levelling_tool.run(toggle=True))

        self.ui.isolation_btn.triggered.connect(lambda: self.isolation_tool.run(toggle=True))
        self.ui.follow_btn.triggered.connect(lambda: self.follow_tool.run(toggle=True))
        self.ui.ncc_btn.triggered.connect(lambda: self.ncclear_tool.run(toggle=True))
        self.ui.paint_btn.triggered.connect(lambda: self.paint_tool.run(toggle=True))

        self.ui.cutout_btn.triggered.connect(lambda: self.cutout_tool.run(toggle=True))
        self.ui.panelize_btn.triggered.connect(lambda: self.panelize_tool.run(toggle=True))
        self.ui.film_btn.triggered.connect(lambda: self.film_tool.run(toggle=True))
        self.ui.dblsided_btn.triggered.connect(lambda: self.dblsidedtool.run(toggle=True))

        self.ui.align_btn.triggered.connect(lambda: self.align_objects_tool.run(toggle=True))
        # self.ui.sub_btn.triggered.connect(lambda: self.sub_tool.run(toggle=True))

        # self.ui.extract_btn.triggered.connect(lambda: self.extract_tool.run(toggle=True))
        self.ui.copperfill_btn.triggered.connect(lambda: self.copper_thieving_tool.run(toggle=True))
        self.ui.markers_tool_btn.triggered.connect(lambda: self.markers_tool.run(toggle=True))
        self.ui.punch_btn.triggered.connect(lambda: self.punch_tool.run(toggle=True))
        self.ui.calculators_btn.triggered.connect(lambda: self.calculator_tool.run(toggle=True))

        #
        # self.ui.solder_btn.triggered.connect(lambda: self.paste_tool.run(toggle=True))
        # self.ui.rules_btn.triggered.connect(lambda: self.rules_tool.run(toggle=True))
        # self.ui.optimal_btn.triggered.connect(lambda: self.optimal_tool.run(toggle=True))
        #
        # self.ui.transform_btn.triggered.connect(lambda: self.transform_tool.run(toggle=True))
        # self.ui.qrcode_btn.triggered.connect(lambda: self.qrcode_tool.run(toggle=True))
        # self.ui.fiducials_btn.triggered.connect(lambda: self.fiducial_tool.run(toggle=True))
        # self.ui.invert_btn.triggered.connect(lambda: self.invert_tool.run(toggle=True))
        # self.ui.etch_btn.triggered.connect(lambda: self.etch_tool.run(toggle=True))

    def connect_editors_toolbar_signals(self):
        self.log.debug(" -> Connecting Editors Toolbar Signals")

        # Geometry Editor Toolbar Signals
        self.geo_editor.connect_geo_toolbar_signals()

        # Gerber Editor Toolbar Signals
        self.grb_editor.connect_grb_toolbar_signals()

        # Excellon Editor Toolbar Signals
        self.exc_editor.connect_exc_toolbar_signals()

    def connect_toolbar_signals(self):
        """
        Reconnect the signals to the actions in the toolbar.
        This has to be done each time after the FlatCAM tools are removed/installed.

        :return: None
        """
        self.log.debug(" -> Connecting Toolbar Signals")
        # Toolbar

        # File Toolbar Signals
        # ui.file_new_btn.triggered.connect(self.on_file_new_project)
        self.ui.file_open_btn.triggered.connect(lambda: self.f_handlers.on_file_open_project())
        self.ui.file_save_btn.triggered.connect(lambda: self.f_handlers.on_file_save_project())
        self.ui.file_open_gerber_btn.triggered.connect(lambda: self.f_handlers.on_file_open_gerber())
        self.ui.file_open_excellon_btn.triggered.connect(lambda: self.f_handlers.on_file_open_excellon())

        # View Toolbar Signals
        self.ui.clear_plot_btn.triggered.connect(self.clear_plots)
        self.ui.replot_btn.triggered.connect(self.plot_all)
        self.ui.zoom_fit_btn.triggered.connect(self.on_zoom_fit)
        self.ui.zoom_in_btn.triggered.connect(lambda: self.plotcanvas.zoom(1 / 1.5))
        self.ui.zoom_out_btn.triggered.connect(lambda: self.plotcanvas.zoom(1.5))

        # Edit Toolbar Signals
        self.ui.editor_start_btn.triggered.connect(self.on_editing_start)
        self.ui.editor_exit_btn.clicked.connect(lambda: self.on_editing_finished(force_cancel=True))
        self.ui.copy_btn.triggered.connect(self.on_copy_command)
        self.ui.delete_btn.triggered.connect(self.on_delete)

        self.ui.distance_btn.triggered.connect(lambda: self.distance_tool.run(toggle=True))
        # self.ui.distance_min_btn.triggered.connect(lambda: self.distance_min_tool.run(toggle=True))
        self.ui.origin_btn.triggered.connect(self.on_set_origin)
        # self.ui.move2origin_btn.triggered.connect(self.on_move2origin)
        # self.ui.center_in_origin_btn.triggered.connect(self.on_custom_origin)

        self.ui.jmp_btn.triggered.connect(self.on_jump_to)
        self.ui.locate_btn.triggered.connect(lambda: self.on_locate(obj=self.collection.get_active()))

        # Scripting Toolbar Signals
        self.ui.shell_btn.triggered.connect(self.ui.toggle_shell_ui)
        self.ui.new_script_btn.triggered.connect(self.f_handlers.on_file_new_script)
        self.ui.open_script_btn.triggered.connect(self.f_handlers.on_file_open_script)
        self.ui.run_script_btn.triggered.connect(self.f_handlers.on_file_run_cript)

        # Tools Toolbar Signals
        try:
            self.connect_tools_signals_to_toolbar()
        except Exception as c_err:
            self.log.error("App.connect_toolbar_signals() tools signals -> %s" % str(c_err))

    def on_layout(self, lay=None, connect_signals=True):
        """
        Set the toolbars layout (location).

        :param connect_signals: Useful when used in the App.__init__(); bool
        :param lay:             Type of layout to be set on the toolbard
        :return:                None
        """

        self.defaults.report_usage("on_layout()")
        self.log.debug(" ---> New Layout")

        if lay:
            current_layout = lay
        else:
            current_layout = self.ui.general_pref_form.general_gui_group.layout_combo.get_value()

        lay_settings = QSettings("Open Source", "FlatCAM_EVO")
        lay_settings.setValue('layout', current_layout)

        # This will write the setting to the platform specific storage.
        del lay_settings

        # first remove the toolbars:
        self.log.debug(" -> Remove Toolbars")
        try:
            self.ui.removeToolBar(self.ui.toolbarfile)
            self.ui.removeToolBar(self.ui.toolbaredit)
            self.ui.removeToolBar(self.ui.toolbarview)
            self.ui.removeToolBar(self.ui.toolbarshell)
            self.ui.removeToolBar(self.ui.toolbarplugins)
            self.ui.removeToolBar(self.ui.exc_edit_toolbar)
            self.ui.removeToolBar(self.ui.geo_edit_toolbar)
            self.ui.removeToolBar(self.ui.grb_edit_toolbar)
            self.ui.removeToolBar(self.ui.toolbarshell)
        except Exception:
            pass

        self.log.debug(" -> Add New Toolbars")
        if current_layout == 'compact':
            # ## TOOLBAR INSTALLATION # ##
            self.ui.toolbarfile = QtWidgets.QToolBar('File Toolbar')
            self.ui.toolbarfile.setObjectName('File_TB')
            self.ui.toolbarfile.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.ui.toolbarfile)

            self.ui.toolbaredit = QtWidgets.QToolBar('Edit Toolbar')
            self.ui.toolbaredit.setObjectName('Edit_TB')
            self.ui.toolbaredit.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.ui.toolbaredit)

            self.ui.toolbarshell = QtWidgets.QToolBar('Shell Toolbar')
            self.ui.toolbarshell.setObjectName('Shell_TB')
            self.ui.toolbarshell.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.ui.toolbarshell)

            self.ui.toolbarplugins = QtWidgets.QToolBar('Plugin Toolbar')
            self.ui.toolbarplugins.setObjectName('Plugins_TB')
            self.ui.toolbarplugins.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.ui.toolbarplugins)

            self.ui.geo_edit_toolbar = QtWidgets.QToolBar('Geometry Editor Toolbar')
            self.ui.geo_edit_toolbar.setObjectName('GeoEditor_TB')
            self.ui.geo_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.ui.geo_edit_toolbar)

            self.ui.toolbarview = QtWidgets.QToolBar('View Toolbar')
            self.ui.toolbarview.setObjectName('View_TB')
            self.ui.toolbarview.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.ui.toolbarview)

            self.ui.addToolBarBreak(area=Qt.ToolBarArea.RightToolBarArea)

            self.ui.grb_edit_toolbar = QtWidgets.QToolBar('Gerber Editor Toolbar')
            self.ui.grb_edit_toolbar.setObjectName('GrbEditor_TB')
            self.ui.grb_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.ui.grb_edit_toolbar)

            self.ui.exc_edit_toolbar = QtWidgets.QToolBar('Excellon Editor Toolbar')
            self.ui.exc_edit_toolbar.setObjectName('ExcEditor_TB')
            self.ui.exc_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.ui.exc_edit_toolbar)
        else:
            # ## TOOLBAR INSTALLATION # ##
            self.ui.toolbarfile = QtWidgets.QToolBar('File Toolbar')
            self.ui.toolbarfile.setObjectName('File_TB')
            self.ui.toolbarfile.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.toolbarfile)

            self.ui.toolbaredit = QtWidgets.QToolBar('Edit Toolbar')
            self.ui.toolbaredit.setObjectName('Edit_TB')
            self.ui.toolbaredit.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.toolbaredit)

            self.ui.toolbarview = QtWidgets.QToolBar('View Toolbar')
            self.ui.toolbarview.setObjectName('View_TB')
            self.ui.toolbarview.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.toolbarview)

            self.ui.toolbarshell = QtWidgets.QToolBar('Shell Toolbar')
            self.ui.toolbarshell.setObjectName('Shell_TB')
            self.ui.toolbarshell.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.toolbarshell)

            self.ui.toolbarplugins = QtWidgets.QToolBar('Plugin Toolbar')
            self.ui.toolbarplugins.setObjectName('Plugins_TB')
            self.ui.toolbarplugins.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.toolbarplugins)

            self.ui.exc_edit_toolbar = QtWidgets.QToolBar('Excellon Editor Toolbar')
            # self.ui.exc_edit_toolbar.setVisible(False)
            self.ui.exc_edit_toolbar.setObjectName('ExcEditor_TB')
            self.ui.exc_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.exc_edit_toolbar)

            self.ui.addToolBarBreak()

            self.ui.geo_edit_toolbar = QtWidgets.QToolBar('Geometry Editor Toolbar')
            # self.ui.geo_edit_toolbar.setVisible(False)
            self.ui.geo_edit_toolbar.setObjectName('GeoEditor_TB')
            self.ui.geo_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.geo_edit_toolbar)

            self.ui.grb_edit_toolbar = QtWidgets.QToolBar('Gerber Editor Toolbar')
            # self.ui.grb_edit_toolbar.setVisible(False)
            self.ui.grb_edit_toolbar.setObjectName('GrbEditor_TB')
            self.ui.grb_edit_toolbar.setStyleSheet("QToolBar{spacing:0px;}")
            self.ui.addToolBar(self.ui.grb_edit_toolbar)

        if current_layout == 'minimal':
            self.ui.toolbarview.setVisible(False)
            self.ui.toolbarshell.setVisible(False)
            self.ui.geo_edit_toolbar.setVisible(False)
            self.ui.grb_edit_toolbar.setVisible(False)
            self.ui.exc_edit_toolbar.setVisible(False)
            self.ui.lock_toolbar(lock=True)

        # add all the actions to the toolbars
        self.ui.populate_toolbars()

        try:
            # reconnect all the signals to the toolbar actions
            if connect_signals is True:
                self.connect_toolbar_signals()
        except Exception as e:
            self.log.error(
                "App.on_layout() - connect toolbar signals -> %s" % str(e))

        # Editor Toolbars Signals
        try:
            self.connect_editors_toolbar_signals()
        except Exception as m_err:
            self.log.error("App.on_layout() - connect editor signals -> %s" % str(m_err))

        self.ui.grid_snap_btn.setChecked(True)

        self.ui.corner_snap_btn.setVisible(False)
        self.ui.snap_magnet.setVisible(False)

        self.ui.grid_gap_x_entry.setText(str(self.options["global_gridx"]))
        self.ui.grid_gap_y_entry.setText(str(self.options["global_gridy"]))
        self.ui.snap_max_dist_entry.setText(str(self.options["global_snap_max"]))
        self.ui.grid_gap_link_cb.setChecked(True)

    def on_editing_start(self):
        """
        Send the current Geometry, Gerber, "Excellon" object or CNCJob (if any) its editor.

        :return: None
        """
        self.defaults.report_usage("on_editing_start()")

        edited_object = self.collection.get_active()
        if edited_object is None:
            self.inform.emit('[ERROR_NOTCL] %s %s' % (_("The Editor could not start."), _("No object is selected.")))
            return

        if edited_object and edited_object.kind in ['cncjob', 'excellon', 'geometry', 'gerber']:
            if edited_object.kind != 'geometry':
                edited_object.build_ui()
        else:
            self.inform.emit('[WARNING_NOTCL] %s' % _("Select a Geometry, Gerber, Excellon or CNCJob Object to edit."))
            self.ui.menuobjects.setDisabled(False)
            return

        self.ui.notebook.setCurrentWidget(self.ui.properties_tab)

        if edited_object.kind == 'geometry':
            if self.geo_editor is None:
                self.ui.menuobjects.setDisabled(False)
                self.inform.emit('[ERROR_NOTCL] %s' % _("The Editor could not start."))
                return

            # store the Geometry Editor Toolbar visibility before entering the Editor
            self.geo_editor.toolbar_old_state = True if self.ui.geo_edit_toolbar.isVisible() else False

            # we set the notebook to hidden
            # self.ui.splitter.setSizes([0, 1])
            if edited_object.multigeo is True:
                sel_rows = set()
                for item in edited_object.ui.geo_tools_table.selectedItems():
                    sel_rows.add(item.row())
                sel_rows = list(sel_rows)

                if len(sel_rows) > 1:
                    self.inform.emit('[WARNING_NOTCL] %s' %
                                     _("Simultaneous editing of tools geometry in a MultiGeo Geometry "
                                       "is not possible.\n"
                                       "Edit only one geometry at a time."))
                    self.ui.menuobjects.setDisabled(False)
                    return

                if not sel_rows:
                    self.inform.emit('[WARNING_NOTCL] %s.' % _("No Tool Selected"))
                    self.ui.menuobjects.setDisabled(False)
                    return

                # determine the tool dia of the selected tool
                # selected_tooldia = float(edited_object.ui.geo_tools_table.item(sel_rows[0], 1).text())
                sel_id = int(edited_object.ui.geo_tools_table.item(sel_rows[0], 5).text())

                multi_tool = sel_id
                self.log.debug("Editing MultiGeo Geometry with tool diameter: %s" % str(multi_tool))
                self.geo_editor.edit_geometry(edited_object, multigeo_tool=multi_tool)
            else:
                self.log.debug("Editing SingleGeo Geometry with tool diameter.")
                self.geo_editor.edit_geometry(edited_object)

            # set call source to the Editor we go into
            self.call_source = 'geo_editor'
        elif edited_object.kind == 'excellon':
            if self.exc_editor is None:
                self.ui.menuobjects.setDisabled(False)
                self.inform.emit('[ERROR_NOTCL] %s' % _("The Editor could not start."))
                return

            # store the Excellon Editor Toolbar visibility before entering the Editor
            self.exc_editor.toolbar_old_state = True if self.ui.exc_edit_toolbar.isVisible() else False

            if self.ui.splitter.sizes()[0] == 0:
                self.ui.splitter.setSizes([1, 1])

            self.exc_editor.edit_fcexcellon(edited_object)

            # set call source to the Editor we go into
            self.call_source = 'exc_editor'
        elif edited_object.kind == 'gerber':
            if self.grb_editor is None:
                self.ui.menuobjects.setDisabled(False)
                self.inform.emit('[ERROR_NOTCL] %s' % _("The Editor could not start."))
                return

            # store the Gerber Editor Toolbar visibility before entering the Editor
            self.grb_editor.toolbar_old_state = True if self.ui.grb_edit_toolbar.isVisible() else False

            if self.ui.splitter.sizes()[0] == 0:
                self.ui.splitter.setSizes([1, 1])

            self.grb_editor.edit_fcgerber(edited_object)

            # set call source to the Editor we go into
            self.call_source = 'grb_editor'

            # reset the following variables so the UI is built again after edit
            edited_object.ui_build = False
        elif edited_object.kind == 'cncjob':
            if self.gcode_editor is None:
                self.ui.menuobjects.setDisabled(False)
                self.inform.emit('[ERROR_NOTCL] %s' % _("The Editor could not start."))
                return

            if self.ui.splitter.sizes()[0] == 0:
                self.ui.splitter.setSizes([1, 1])

            # set call source to the Editor we go into
            self.call_source = 'gcode_editor'

            self.gcode_editor.edit_fcgcode(edited_object)

        for idx in range(self.ui.notebook.count()):
            # store the Properties Tab text color here and change the color and text
            if self.ui.notebook.tabText(idx) == _("Properties"):
                self.old_tab_text_color = self.ui.notebook.tabBar.tabTextColor(idx)
                self.ui.notebook.tabBar.setTabTextColor(idx, QtGui.QColor('red'))
                self.ui.notebook.tabBar.setTabText(idx, _("Editor"))

            # disable the Project Tab
            if self.ui.notebook.tabText(idx) == _("Project"):
                self.ui.notebook.tabBar.setTabEnabled(idx, False)

        # delete any selection shape that might be active as they are not relevant in Editor
        self.delete_selection_shape()

        # hide the Tools Toolbar
        plugins_tb = self.ui.toolbarplugins
        if plugins_tb.isVisible():
            self.old_state_of_tools_toolbar = True
            plugins_tb.hide()
        else:
            self.old_state_of_tools_toolbar = False

        # make sure that we can't select another object while in Editor Mode:
        self.ui.project_frame.setDisabled(True)
        # disable the objects menu as it may interfere with the appEditors
        self.ui.menuobjects.setDisabled(True)
        # disable the tools menu as it makes sense not to be available when in the Editor
        self.ui.menu_plugins.setDisabled(True)

        self.ui.plot_tab_area.setTabText(0, _("EDITOR Area"))
        self.ui.plot_tab_area.protectTab(0)
        self.log.debug("######################### Starting the EDITOR ################################")
        self.inform.emit('[WARNING_NOTCL] %s' % _("Editor is activated ..."))

        self.should_we_save = True

    def on_editing_finished(self, cleanup=None, force_cancel=None):
        """
        Transfers the Geometry or an "Excellon", from its editor to the current object.

        :param cleanup:         if True then we closed the app when the editor was open, so we close first the editor
        :param force_cancel:    if True always add Cancel button
        :return:                None
        """
        self.defaults.report_usage("on_editing_finished()")

        # do not update a Geometry/"Excellon"/Gerber/GCode object unless it comes out of an editor
        if self.call_source == 'app':
            return

        # make sure that when we exit an Editor with a tool active then we make some clean-up
        try:
            if self.use_3d_engine:
                self.plotcanvas.text_cursor.parent = None
                self.plotcanvas.view.camera.zoom_callback = lambda *args: None
        except Exception:
            pass

        # This is the object that exit from the Editor. It may be the edited object, but it can be a new object
        # created by the Editor
        edited_obj = self.collection.get_active()

        if cleanup is None:
            msgbox = FCMessageBox(parent=self.ui)
            title = _("Exit Editor")
            txt = _("Do you want to save the changes?")
            msgbox.setWindowTitle(title)  # taskbar still shows it
            msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
            msgbox.setText('<b>%s</b>' % title)
            msgbox.setInformativeText(txt)
            msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/save_as.png'))

            bt_yes = msgbox.addButton(_('Yes'), QtWidgets.QMessageBox.ButtonRole.YesRole)
            bt_no = msgbox.addButton(_('No'), QtWidgets.QMessageBox.ButtonRole.NoRole)
            if edited_obj.kind in ["geometry", "gerber", "excellon"] or force_cancel is not None:
                bt_cancel = msgbox.addButton(_('Cancel'), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            else:
                bt_cancel = None

            msgbox.setDefaultButton(bt_yes)
            msgbox.exec()
            response = msgbox.clickedButton()

            if response == bt_yes:
                # show the Tools Toolbar
                plugins_tb = self.ui.toolbarplugins
                if self.old_state_of_tools_toolbar is True:
                    plugins_tb.show()

                # clean the Tools Tab
                found_idx = None
                for idx in range(self.ui.notebook.count()):
                    if self.ui.notebook.widget(idx).objectName() == "plugin_tab":
                        found_idx = idx
                        break
                if found_idx:
                    self.ui.notebook.setCurrentWidget(self.ui.properties_tab)
                    self.ui.notebook.removeTab(found_idx)

                if edited_obj.kind == 'geometry':
                    obj_type = "Geometry"
                    self.geo_editor.update_editor_geometry(edited_obj)
                    # self.geo_editor.update_options(edited_obj)

                    # restore GUI to the Selected TAB
                    # Remove anything else in the appGUI
                    self.ui.plugin_scroll_area.takeWidget()

                    # update the geo object options, so it is including the bounding box values
                    try:
                        xmin, ymin, xmax, ymax = edited_obj.bounds(flatten=True)
                        edited_obj.obj_options['xmin'] = xmin
                        edited_obj.obj_options['ymin'] = ymin
                        edited_obj.obj_options['xmax'] = xmax
                        edited_obj.obj_options['ymax'] = ymax
                    except (AttributeError, ValueError) as e:
                        self.inform.emit('[WARNING] %s' % _("Object empty after edit."))
                        self.log.debug("App.on_editing_finished() --> Geometry --> %s" % str(e))

                    edited_obj.build_ui()
                    edited_obj.plot()
                    self.inform.emit('[success] %s' % _("Editor exited. Editor content saved."))

                elif edited_obj.kind == 'gerber':
                    obj_type = "Gerber"
                    self.grb_editor.update_fcgerber()
                    # self.grb_editor.update_options(edited_obj)

                    # delete the old object (the source object) if it was an empty one
                    try:
                        if len(edited_obj.solid_geometry) == 0:
                            old_name = edited_obj.obj_options['name']
                            self.collection.delete_by_name(old_name)
                    except TypeError:
                        # if the solid_geometry is a single Polygon the len() will not work
                        # in any case, falling here means that we have something in the solid_geometry, even if only
                        # a single Polygon, therefore we pass this
                        pass

                    self.inform.emit('[success] %s' % _("Editor exited. Editor content saved."))

                    # restore GUI to the Selected TAB
                    # Remove anything else in the GUI
                    self.ui.properties_scroll_area.takeWidget()

                elif edited_obj.kind == 'excellon':
                    obj_type = "Excellon"
                    self.exc_editor.update_fcexcellon(edited_obj)
                    # self.exc_editor.update_options(edited_obj)

                    # restore GUI to the Selected TAB
                    # Remove anything else in the GUI
                    self.ui.plugin_scroll_area.takeWidget()

                    # delete the old object (the source object) if it was an empty one
                    # find if we have drills:
                    has_drills = None
                    for tt in edited_obj.tools:
                        if 'drills' in edited_obj.tools[tt] and edited_obj.tools[tt]['drills']:
                            has_drills = True
                            break
                    # find if we have slots:
                    has_slots = None
                    for tt in edited_obj.tools:
                        if 'slots' in edited_obj.tools[tt] and edited_obj.tools[tt]['slots']:
                            has_slots = True
                            break
                    if has_drills is None and has_slots is None:
                        old_name = edited_obj.obj_options['name']
                        self.collection.delete_by_name(name=old_name)
                    self.inform.emit('[success] %s' % _("Editor exited. Editor content saved."))

                elif edited_obj.kind == 'cncjob':
                    obj_type = "CNCJob"
                    self.gcode_editor.update_fcgcode(edited_obj)
                    # self.exc_editor.update_options(edited_obj)

                    # restore GUI to the Selected TAB
                    # Remove anything else in the GUI
                    self.ui.plugin_scroll_area.takeWidget()
                    edited_obj.build_ui()

                    # close the open tab
                    for idx in range(self.ui.plot_tab_area.count()):
                        if self.ui.plot_tab_area.widget(idx).objectName() == 'gcode_editor_tab':
                            self.ui.plot_tab_area.closeTab(idx)
                    self.inform.emit('[success] %s' % _("Editor exited. Editor content saved."))

                else:
                    self.inform.emit('[WARNING_NOTCL] %s' %
                                     _("Select a Gerber, Geometry, Excellon or CNCJob Object to update."))
                    return

                # make sure to update the Offset field in Properties Tab
                try:
                    edited_obj.set_offset_values()
                except AttributeError:
                    # not all objects have this attribute
                    pass

                self.inform.emit('[selected] %s %s' % (obj_type, _("is updated, returning to App...")))
            elif response == bt_no:
                # show the Tools Toolbar
                plugins_tb = self.ui.toolbarplugins
                if self.old_state_of_tools_toolbar is True:
                    plugins_tb.show()

                # clean the Tools Tab
                found_idx = None
                for idx in range(self.ui.notebook.count()):
                    if self.ui.notebook.widget(idx).objectName() == "plugin_tab":
                        found_idx = idx
                        break
                if found_idx:
                    self.ui.notebook.setCurrentWidget(self.ui.properties_tab)
                    self.ui.notebook.removeTab(2)

                self.inform.emit('[WARNING_NOTCL] %s' % _("Editor exited. Editor content was not saved."))

                if edited_obj.kind == 'geometry':
                    self.geo_editor.deactivate()
                    edited_obj.build_ui()
                    edited_obj.plot()
                elif edited_obj.kind == 'gerber':
                    self.grb_editor.deactivate_grb_editor()
                    edited_obj.build_ui()
                elif edited_obj.kind == 'excellon':
                    self.exc_editor.deactivate()
                    edited_obj.build_ui()
                elif edited_obj.kind == 'cncjob':
                    self.gcode_editor.deactivate()
                    edited_obj.build_ui()

                    # close the open tab
                    for idx in range(self.ui.plot_tab_area.count()):
                        try:
                            if self.ui.plot_tab_area.widget(idx).objectName() == 'gcode_editor_tab':
                                self.ui.plot_tab_area.closeTab(idx)
                        except AttributeError:
                            continue
                else:
                    self.inform.emit('[WARNING_NOTCL] %s' %
                                     _("Select a Gerber, Geometry, Excellon or CNCJob Object to update."))
                    return
            elif response == bt_cancel:
                return

            # edited_obj.set_ui(edited_obj.ui_type(decimals=self.decimals))
            # edited_obj.build_ui()
            # Switch notebook to Properties page
            # self.ui.notebook.setCurrentWidget(self.ui.properties_tab)
        else:
            # show the Tools Toolbar
            plugins_tb = self.ui.toolbarplugins
            if self.old_state_of_tools_toolbar is True:
                plugins_tb.show()

            if edited_obj.kind == 'geometry':
                self.geo_editor.deactivate()
            elif edited_obj.kind == 'gerber':
                self.grb_editor.deactivate_grb_editor()
            elif edited_obj.kind == 'excellon':
                self.exc_editor.deactivate()
            elif edited_obj.kind == 'cncjob':
                self.gcode_editor.deactivate()
            else:
                self.inform.emit('[WARNING_NOTCL] %s' %
                                 _("Select a Gerber, Geometry, Excellon or CNCJob object to update."))
                return

        self.post_edit_sig.emit()

    def on_editing_final_action(self):
        self.log.debug("######################### Closing the EDITOR ################################")
        self.call_source = 'app'

        # if notebook is hidden we show it
        if self.ui.splitter.sizes()[0] == 0:
            self.ui.splitter.setSizes([1, 1])

        # change back the tab name
        for idx in range(self.ui.notebook.count()):
            # restore the Properties Tab text and color
            if self.ui.notebook.tabText(idx) == _("Editor"):
                self.ui.notebook.tabBar.setTabTextColor(idx, self.old_tab_text_color)
                self.ui.notebook.tabBar.setTabText(idx, _("Properties"))

            # enable the Project Tab
            if self.ui.notebook.tabText(idx) == _("Project"):
                self.ui.notebook.tabBar.setTabEnabled(idx, True)

        self.ui.plot_tab_area.setTabText(0, _("Plot Area"))
        self.ui.plot_tab_area.protectTab(0)

        # make sure that we re-enable the selection on Project Tab after returning from Editor Mode:
        self.ui.project_frame.setDisabled(False)

        QMetaObject.invokeMethod(self, "modify_menu_items", Qt.ConnectionType.QueuedConnection)

    @QtCore.pyqtSlot()
    def modify_menu_items(self):
        # re-enable the objects menu that was disabled on entry in Editor mode
        self.ui.menuobjects.setDisabled(False)
        # re-enable the tool menu that was disabled on entry in Editor mode
        self.ui.menu_plugins.setDisabled(False)

    def get_last_folder(self):
        """
        Get the folder path from where the last file was opened.
        :return: String, last opened folder path
        """
        return self.options["global_last_folder"]

    def get_last_save_folder(self):
        """
        Get the folder path from where the last file was saved.
        :return: String, last saved folder path
        """
        loc = self.options["global_last_save_folder"]
        if loc is None:
            loc = self.options["global_last_folder"]
        if loc is None:
            loc = os.path.dirname(__file__)
        return loc

    @QtCore.pyqtSlot(str)
    @QtCore.pyqtSlot(str, bool)
    def info(self, msg, shell_echo=True):
        """
        Informs the user. Normally on the status bar, optionally also on the shell.

        :param msg:         Text to write. Composed of a first part between brackets which is the level and the rest
                            which is the message. The level part will control the text color and the used icon
        :type msg:          str
        :param shell_echo:  Control if to display the message msg in the Shell
        :type shell_echo:   bool
        :return: None
        """

        # Type of message in brackets at the beginning of the message.
        match = re.search(r"^\[(.*?)](.*)", msg)
        if match:
            level = match.group(1)
            msg_ = match.group(2)
            self.ui.fcinfo.set_status(str(msg_), level=level)

            if shell_echo is True:
                if level.lower() == "error":
                    self.shell_message(msg, error=True, show=True)
                elif level.lower() == "warning":
                    self.shell_message(msg, warning=True, show=True)

                elif level.lower() == "error_notcl":
                    self.shell_message(msg, error=True, show=False)

                elif level.lower() == "warning_notcl":
                    self.shell_message(msg, warning=True, show=False)

                elif level.lower() == "success":
                    self.shell_message(msg, success=True, show=False)

                elif level.lower() == "selected":
                    self.shell_message(msg, selected=True, show=False)

                else:
                    self.shell_message(msg, show=False)

        else:
            self.ui.fcinfo.set_status(str(msg), level="info")

            # make sure that if the message is to clear the infobar with a space
            # is not printed over and over on the shell
            if msg != '' and shell_echo is True:
                self.shell_message(msg)
        QtWidgets.QApplication.processEvents()

    def info_shell(self, msg, new_line=True):
        """
        A handler for a signal that call for printing directly on the Tcl Shell without printing in status bar.

        :param msg:         The message to be printed
        :type msg:          str
        :param new_line:    if True then after printing the message add a new line char
        :type new_line:     bool
        :return:
        :rtype:
        """
        self.shell_message(msg=msg, new_line=new_line)

    def save_to_file(self, content_to_save, txt_content):
        """
        Save something to a file.

        :param content_to_save: text when is in HTML
        :type content_to_save:  str
        :param txt_content:     text that is not HTML
        :type txt_content:      str
        :return:
        :rtype:
        """
        self.defaults.report_usage("save_to_file")
        self.log.debug("save_to_file()")

        date = str(dt.today()).rpartition('.')[0]
        date = ''.join(c for c in date if c not in ':-')
        date = date.replace(' ', '_')

        filter__ = "HTML File .html (*.html);;TXT File .txt (*.txt);;All Files (*.*)"
        path_to_save = self.options["global_last_save_folder"] if \
            self.options["global_last_save_folder"] is not None else self.data_path
        final_path = os.path.join(path_to_save, 'file_%s' % str(date))

        try:
            filename, _f = FCFileSaveDialog.get_saved_filename(
                caption=_("Save to file"),
                directory=final_path,
                ext_filter=filter__
            )
        except TypeError:
            filename, _f = FCFileSaveDialog.get_saved_filename(
                caption=_("Save to file"),
                ext_filter=filter__)

        filename = str(filename)

        if filename == "":
            self.inform.emit('[WARNING_NOTCL] %s' % _("Cancelled."))
            return
        else:
            try:
                with open(filename, 'w') as f:
                    ___ = f.read()
            except PermissionError:
                self.inform.emit('[WARNING] %s' %
                                 _("Permission denied, saving not possible.\n"
                                   "Most likely another app is holding the file open and not accessible."))
                return
            except IOError:
                self.log.debug('Creating a new file ...')
                f = open(filename, 'w')
                f.close()
            except Exception:
                e = sys.exc_info()[0]
                self.log.error("Could not load the file.")
                self.log.error(str(e))
                self.inform.emit('[ERROR_NOTCL] %s' % _("Could not load the file."))
                return

            # Save content
            if filename.rpartition('.')[2].lower() == 'html':
                file_content = content_to_save
            else:
                file_content = txt_content

            try:
                with open(filename, "w") as f:
                    f.write(file_content)
            except Exception:
                self.inform.emit('[ERROR_NOTCL] %s %s' % (_("Failed to write defaults to file."), str(filename)))
                return

        self.inform.emit('[success] %s: %s' % (_("Exported file to"), filename))

    def register_recent(self, kind, filename):
        """
        Will register the files opened into record dictionaries. The FlatCAM projects has its own
        dictionary.

        :param kind:        type of file that was opened
        :param filename:    the path and file name for the file that was opened
        :return:
        """
        self.log.debug("register_recent()")
        self.log.debug("   %s" % kind)
        self.log.debug("   %s" % filename)

        record = {'kind': str(kind), 'filename': str(filename)}
        if record in self.recent:
            return
        if record in self.recent_projects:
            return

        if record['kind'] == 'project':
            self.recent_projects.insert(0, record)
        else:
            self.recent.insert(0, record)

        if len(self.recent) > self.options['global_recent_limit']:  # Limit reached
            self.recent.pop()

        if len(self.recent_projects) > self.options['global_recent_limit']:  # Limit reached
            self.recent_projects.pop()

        try:
            f = open(os.path.join(self.data_path, 'recent.json'), 'w')
        except IOError:
            self.log.error("Failed to open recent items file for writing.")
            self.inform.emit('[ERROR_NOTCL] %s' %
                             _('Failed to open recent files file for writing.'))
            return

        json.dump(self.recent, f, default=to_dict, indent=2, sort_keys=True)
        f.close()

        try:
            fp = open(os.path.join(self.data_path, 'recent_projects.json'), 'w')
        except IOError:
            self.log.error("Failed to open recent items file for writing.")
            self.inform.emit('[ERROR_NOTCL] %s' %
                             _('Failed to open recent projects file for writing.'))
            return

        json.dump(self.recent_projects, fp, default=to_dict, indent=2, sort_keys=True)
        fp.close()

        # Re-build the recent items menu
        self.setup_recent_items()

    def on_about(self):
        """
        Displays the "about" dialog found in the Menu --> Help.

        :return: None
        """
        self.defaults.report_usage("on_about")

        version = self.version
        version_date = self.version_date
        beta = self.beta

        class AboutDialog(QtWidgets.QDialog):
            # noinspection PyUnresolvedReferences
            def __init__(self, app, parent):
                QtWidgets.QDialog.__init__(self, parent=parent)

                self.app = app
                self.app_icon = self.app.ui.app_icon

                # Icon and title
                self.setWindowIcon(self.app_icon)
                self.setWindowTitle(_("About"))
                self.resize(600, 200)
                # self.setStyleSheet("background-image: url(share/flatcam_icon256.png); background-attachment: fixed")
                # self.setStyleSheet(
                #     "border-image: url(share/flatcam_icon256.png) 0 0 0 0 compact compact; "
                #     "background-attachment: fixed"
                # )

                # bgimage = QtGui.QImage(self.resource_location + '/flatcam_icon256.png')
                # s_bgimage = bgimage.scaled(QtCore.QSize(self.frameGeometry().width(), self.frameGeometry().height()))
                # palette = QtGui.QPalette()
                # palette.setBrush(10, QtGui.QBrush(bgimage))  # 10 = Windowrole
                # self.setPalette(palette)

                logo = FCLabel()
                logo.setPixmap(QtGui.QPixmap(self.app.resource_location + '/app256.png'))

                title = FCLabel(
                    "<font size=8><B>FlatCAM Evo</B></font><BR>"
                    "{title}<BR>"
                    "<BR>"
                    "<BR>"
                    "<a href = \"https://bitbucket.org/jpcgt/flatcam/src/Beta/\"><B>{devel}</B></a><BR>"
                    "<a href = \"https://bitbucket.org/jpcgt/flatcam/downloads/\"><b>{down}</B></a><BR>"
                    "<a href = \"https://bitbucket.org/jpcgt/flatcam/issues?status=new&status=open/\">"
                    "<B>{issue}</B></a><BR>".format(
                        title=_("PCB Manufacturing files Viewer/Editor with Plugins"),
                        devel=_("Development"),
                        down=_("DOWNLOAD"),
                        issue=_("Issue tracker"))
                )
                title.setOpenExternalLinks(True)

                closebtn = FCButton(_("Close"))

                tab_widget = QtWidgets.QTabWidget()
                description_label = FCLabel(
                    "FlatCAM Evo {version} {beta} ({date}) - {arch}<br>"
                    "<a href = \"http://flatcam.org/\">http://flatcam.org</a><br>".format(
                        version=version,
                        beta=('BETA' if beta else ''),
                        date=version_date,
                        arch=platform.architecture()[0])
                )
                description_label.setOpenExternalLinks(True)

                lic_lbl_header = FCLabel(
                    '%s:<br>%s<br>' % (
                        _('Licensed under the MIT license'),
                        "<a href = \"http://www.opensource.org/licenses/mit-license.php\">"
                        "http://www.opensource.org/licenses/mit-license.php</a>"
                    )
                )
                lic_lbl_header.setOpenExternalLinks(True)

                lic_lbl_body = FCLabel(
                    _(
                        'Permission is hereby granted, free of charge, to any person obtaining a copy\n'
                        'of this software and associated documentation files (the "Software"), to deal\n'
                        'in the Software without restriction, including without limitation the rights\n'
                        'to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n'
                        'copies of the Software, and to permit persons to whom the Software is\n'
                        'furnished to do so, subject to the following conditions:\n\n'

                        'The above copyright notice and this permission notice shall be included in\n'
                        'all copies or substantial portions of the Software.\n\n'

                        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
                        'IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n'
                        'FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n'
                        'AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n'
                        'LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n'
                        'OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n'
                        'THE SOFTWARE.'
                    )
                )

                attributions_label = FCLabel(
                    _(
                        'Some of the icons used are from the following sources:<br>'
                        '<div>Icons by <a href="https://www.flaticon.com/authors/freepik" '
                        'title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/"             '
                        'title="Flaticon">www.flaticon.com</a></div>'
                        '<div>Icons by <a target="_blank" href="https://icons8.com">Icons8</a></div>'
                        'Icons by <a href="http://www.onlinewebfonts.com">oNline Web Fonts</a>'
                        '<div>Icons by <a href="https://www.flaticon.com/authors/pixel-perfect" '
                        'title="Pixel perfect">Pixel perfect</a> from <a href="https://www.flaticon.com/" '
                        'title="Flaticon">www.flaticon.com</a></div>'
                        '<div>Icons by <a href="https://www.flaticon.com/authors/anggara" '
                        'title="Anggara"> Anggara </a> from <a href="https://www.flaticon.com/" '
                        'title="Flaticon">www.flaticon.com</a></div>'
                        '<div>Icons by <a href="https://www.flaticon.com/authors/kharisma" '
                        'title="Kharisma"> Kharisma </a> from <a href="https://www.flaticon.com/" '
                        'title="Flaticon">www.flaticon.com</a></div>'
                    )
                )
                attributions_label.setOpenExternalLinks(True)

                # layouts
                layout1 = QtWidgets.QVBoxLayout()
                layout1_1 = QtWidgets.QHBoxLayout()
                layout1_2 = QtWidgets.QHBoxLayout()

                layout2 = QtWidgets.QHBoxLayout()
                layout3 = QtWidgets.QHBoxLayout()

                self.setLayout(layout1)
                layout1.addLayout(layout1_1)
                layout1.addLayout(layout1_2)

                layout1.addLayout(layout2)
                layout1.addLayout(layout3)

                layout1_1.addStretch()
                layout1_1.addWidget(description_label)
                layout1_2.addWidget(tab_widget)

                self.splash_tab = QtWidgets.QWidget()
                self.splash_tab.setObjectName("splash_about")
                self.splash_tab_layout = QtWidgets.QHBoxLayout(self.splash_tab)
                self.splash_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.splash_tab, _("Splash"))

                self.programmmers_tab = QtWidgets.QWidget()
                self.programmmers_tab.setObjectName("programmers_about")
                self.programmmers_tab_layout = QtWidgets.QVBoxLayout(self.programmmers_tab)
                self.programmmers_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.programmmers_tab, _("Programmers"))

                self.translators_tab = QtWidgets.QWidget()
                self.translators_tab.setObjectName("translators_about")
                self.translators_tab_layout = QtWidgets.QVBoxLayout(self.translators_tab)
                self.translators_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.translators_tab, _("Translators"))

                self.license_tab = QtWidgets.QWidget()
                self.license_tab.setObjectName("license_about")
                self.license_tab_layout = QtWidgets.QVBoxLayout(self.license_tab)
                self.license_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.license_tab, _("License"))

                self.attributions_tab = QtWidgets.QWidget()
                self.attributions_tab.setObjectName("attributions_about")
                self.attributions_tab_layout = QtWidgets.QVBoxLayout(self.attributions_tab)
                self.attributions_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.attributions_tab, _("Attributions"))

                self.splash_tab_layout.addWidget(logo, stretch=0)
                self.splash_tab_layout.addWidget(title, stretch=1)

                pal = QtGui.QPalette()
                pal.setColor(QtGui.QPalette.ColorRole.Window, Qt.GlobalColor.white)

                programmers = [
                    {
                        'name': "Denis Hayrullin",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Kamil Sopko",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "David Robertson",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Matthieu Berthomé",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Mike Evans",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Victor Benso",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Jørn Sandvik Nilsson",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Lei Zheng",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Leandro Heck",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Marco A Quezada",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Cedric Dussud",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Chris Hemingway",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "David Kahler",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Damian Wrobel",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Daniel Sallin",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Bruno Vunderl",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Gonzalo Lopez",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Jakob Staudt",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Mike Smith",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Barnaby Walters",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Steve Martina",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Thomas Duffin",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Andrey Kultyapov",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Alex Lazar",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Chris Breneman",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Eric Varsanyi",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Lubos Medovarsky",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "@Idechix",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "@SM",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "@grbf",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "@Symonty",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "@mgix",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Emily Ellis",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Maksym Stetsyuk",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Peter Nitschneider",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Bogusz Jagoda",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Andre Spahlinger",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Hans Boot",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Dmitriy Klabukov",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Robert Niemöller",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Adam Coddington",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Ali Khalil",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Maftei Albert-Alexandru",
                        'description': '',
                        'email': ''
                    },
                    {
                        'name': "Emily Ellis",
                        'description': '',
                        'email': ''
                    },
                ]

                self.prog_grid_lay = GLay(v_spacing=5, h_spacing=3, c_stretch=[0, 0, 1])
                self.prog_grid_lay.setHorizontalSpacing(20)

                prog_widget = QtWidgets.QWidget()
                prog_widget.setLayout(self.prog_grid_lay)
                prog_scroll = QtWidgets.QScrollArea()
                prog_scroll.setWidget(prog_widget)
                prog_scroll.setWidgetResizable(True)
                prog_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                prog_scroll.setPalette(pal)

                self.programmmers_tab_layout.addWidget(prog_scroll)

                # Headers
                self.prog_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("Programmer")), 0, 0)
                self.prog_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("Status")), 0, 1)
                self.prog_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("E-mail")), 0, 2)

                # FlatCAM Author
                self.prog_grid_lay.addWidget(FCLabel('%s' % "Juan Pablo Caram"), 1, 0)
                self.prog_grid_lay.addWidget(FCLabel('%s' % _("FlatCAM Author")), 1, 1)

                # FlatCAM EVO Author
                self.prog_grid_lay.addWidget(FCLabel('%s' % "Marius Stanciu"), 2, 0)
                self.prog_grid_lay.addWidget(FCLabel('%s' % _("FlatCAM Evo Author/Maintainer")), 2, 1)
                self.prog_grid_lay.addWidget(FCLabel('%s' % "<marius_adrian@yahoo.com>"), 2, 2)
                self.prog_grid_lay.addWidget(FCLabel(''), 3, 0)

                # randomize the order of the programmers at each launch
                random.shuffle(programmers)
                line = 4
                for prog in programmers:
                    self.prog_grid_lay.addWidget(FCLabel('%s' % prog['name']), line, 0)
                    self.prog_grid_lay.addWidget(FCLabel('%s' % prog['description']), line, 1)
                    self.prog_grid_lay.addWidget(FCLabel('%s' % prog['email']), line, 2)

                    line += 1
                    if (line % 4) == 0:
                        self.prog_grid_lay.addWidget(FCLabel(''), line, 0)
                        line += 1

                self.translator_grid_lay = GLay(v_spacing=5, h_spacing=3, c_stretch=[0, 0, 1, 0])

                # trans_widget = QtWidgets.QWidget()
                # trans_widget.setLayout(self.translator_grid_lay)
                # self.translators_tab_layout.addWidget(trans_widget)
                # self.translators_tab_layout.addStretch()

                translators = [
                    {
                        'language': 'BR - Portuguese',
                        'authors': [("Carlos Stein", '<carlos.stein@gmail.com>')],
                    },
                    {
                        'language': 'Chinese Simplified',
                        'authors': [("余俊霄 (Yu Junxiao)", '')]
                    },
                    {
                        'language': 'French',
                        'authors': [("Michel Maciejewski", '<micmac589@gmail.com>'), ('Olivier Cornet', '')]
                    },
                    {
                        'language': 'Italian',
                        'authors': [("Massimiliano Golfetto", '<golfetto.pcb@gmail.com>')]
                    },
                    {
                        'language': 'German',
                        'authors': [("Marius Stanciu (Google-Tr)", ''), ('Jens Karstedt', ''), ('Detlef Eckardt', '')],
                    },
                    {
                        'language': 'Romanian',
                        'authors': [("Marius Stanciu", '<marius_adrian@yahoo.com>')]
                    },
                    {
                        'language': 'Russian',
                        'authors': [("Andrey Kultyapov", '<camellan@yandex.ru>')]
                    },
                    {
                        'language': 'Spanish',
                        'authors': [("Marius Stanciu (Google-Tr)", '')]
                    },
                    {
                        'language': 'Turkish',
                        'authors': [("Mehmet Kaya", '<malatyakaya480@gmail.com>')]
                    },
                ]

                trans_widget = QtWidgets.QWidget()
                trans_widget.setLayout(self.translator_grid_lay)
                trans_scroll = QtWidgets.QScrollArea()
                trans_scroll.setWidget(trans_widget)
                trans_scroll.setWidgetResizable(True)
                trans_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                trans_scroll.setPalette(pal)
                self.translators_tab_layout.addWidget(trans_scroll)

                self.translator_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("Language")), 0, 0)
                self.translator_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("Translator")), 0, 1)
                self.translator_grid_lay.addWidget(FCLabel('<b>%s</b>' % _("E-mail")), 0, 2)

                line = 1
                for i in translators:
                    self.translator_grid_lay.addWidget(FCLabel('%s' % i['language'], color='blue', bold=False), line, 0)
                    for author in range(len(i['authors'])):
                        auth_widget = FCLabel('%s' % i['authors'][author][0])
                        email_widget = FCLabel('%s' % i['authors'][author][1])
                        self.translator_grid_lay.addWidget(auth_widget, line, 1)
                        self.translator_grid_lay.addWidget(email_widget, line, 2)
                        line += 1

                    line += 1

                self.translator_grid_lay.setColumnStretch(1, 1)
                self.translators_tab_layout.addStretch()

                self.license_tab_layout.addWidget(lic_lbl_header)
                self.license_tab_layout.addWidget(lic_lbl_body)

                self.license_tab_layout.addStretch()

                self.attributions_tab_layout.addWidget(attributions_label)
                self.attributions_tab_layout.addStretch()

                layout3.addStretch()
                layout3.addWidget(closebtn)

                closebtn.clicked.connect(self.accept)

        AboutDialog(app=self, parent=self.ui).exec()

    def on_howto(self):
        """
        Displays the "about" dialog found in the Menu --> Help.

        :return: None
        """

        class HowtoDialog(QtWidgets.QDialog):
            def __init__(self, app, parent):
                QtWidgets.QDialog.__init__(self, parent=parent)

                self.app = app
                self.app_icon = self.app.ui.app_icon

                open_source_link = "<a href = 'https://opensource.org/'<b>Open Source</b></a>"
                new_features_link = "<a href = 'https://bitbucket.org/jpcgt/flatcam/pull-requests/'" \
                                    "<b>click</b></a>"

                bugs_link = "<a href = 'https://bitbucket.org/jpcgt/flatcam/issues/new'<b>click</b></a>"
                donation_link = "<a href = 'https://www.paypal.com/cgi-bin/webscr?cmd=_" \
                                "donations&business=WLTJJ3Q77D98L&currency_code=USD&source=url'<b>click</b></a>"

                # Icon and title
                self.setWindowIcon(self.app_icon)
                self.setWindowTitle('%s ...' % _("How To"))
                self.resize(750, 375)

                logo = FCLabel()
                logo.setPixmap(QtGui.QPixmap(self.app.resource_location + '/contribute256.png'))

                # content = FCLabel(
                #     "%s<br>"
                #     "%s<br><br>"
                #     "%s,<br>"
                #     "%s<br>"
                #     "<ul>"
                #     "<li> &nbsp;%s %s</li>"
                #     "<li> &nbsp;%s %s</li>"
                #     "</ul>"
                #     "%s %s.<br>"
                #     "%s"
                #     "<ul>"
                #     "<li> &nbsp;%s &#128077;</li>"
                #     "<li> &nbsp;%s &#128513;</li>"
                #     "</ul>" %
                #     (
                #         _("This program is %s and free in a very wide meaning of the word.") % open_source_link,
                #         _("Yet it cannot evolve without <b>contributions</b>."),
                #         _("If you want to see this application grow and become better and better"),
                #         _("you can <b>contribute</b> to the development yourself by:"),
                #         _("Pull Requests on the Bitbucket repository, if you are a developer"),
                #         new_features_link,
                #         _("Bug Reports by providing the steps required to reproduce the bug"),
                #         bugs_link,
                #         _("If you like or use this program you can make a donation"),
                #         donation_link,
                #         _("You don't have to make a donation %s, and it is totally optional but:") % donation_link,
                #         _("it will be welcomed with joy"),
                #         _("it will give me a reason to continue")
                #     )
                # )

                # font-weight: bold;
                content = FCLabel(
                    "%s<br>"
                    "%s<br><br>"
                    "%s,<br>"
                    "%s<br>"
                    "<ul>"
                    "<li> &nbsp;%s %s</li>"
                    "<li> &nbsp;%s %s</li>"
                    "</ul>"
                    "<br><br>"
                    "%s <br>"
                    "<span style='color: blue;'>%s</span> %s %s<br>" %
                    (
                        _("This program is %s and free in a very wide meaning of the word.") % open_source_link,
                        _("Yet it cannot evolve without <b>contributions</b>."),
                        _("If you want to see this application grow and become better and better"),
                        _("you can <b>contribute</b> to the development yourself by:"),
                        _("Pull Requests on the Bitbucket repository, if you are a developer"),
                        new_features_link,
                        _("Bug Reports by providing the steps required to reproduce the bug"),
                        bugs_link,
                        _("If you like what you have seen so far ..."),
                        _("Donations are NOT required."), _("But they are welcomed"),
                        donation_link
                    )
                )
                content.setOpenExternalLinks(True)

                # palette
                pal = QtGui.QPalette()
                pal.setColor(QtGui.QPalette.ColorRole.Base, Qt.GlobalColor.white)

                # layouts
                main_layout = QtWidgets.QVBoxLayout()
                self.setLayout(main_layout)

                tab_layout = QtWidgets.QHBoxLayout()
                buttons_hlay = QtWidgets.QHBoxLayout()

                main_layout.addLayout(tab_layout)
                main_layout.addLayout(buttons_hlay)

                tab_widget = QtWidgets.QTabWidget()
                tab_layout.addWidget(tab_widget)

                closebtn = FCButton(_("Close"))
                buttons_hlay.addStretch()
                buttons_hlay.addWidget(closebtn)

                # CONTRIBUTE section
                self.intro_tab = QtWidgets.QWidget()
                self.intro_tab_layout = QtWidgets.QHBoxLayout(self.intro_tab)
                self.intro_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.intro_tab, _("Contribute"))

                self.grid_lay = GLay(v_spacing=5, h_spacing=20)
                # self.grid_lay.setHorizontalSpacing(20)

                intro_wdg = QtWidgets.QWidget()
                intro_wdg.setLayout(self.grid_lay)
                intro_scroll_area = QtWidgets.QScrollArea()
                intro_scroll_area.setWidget(intro_wdg)
                intro_scroll_area.setWidgetResizable(True)
                intro_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                intro_scroll_area.setPalette(pal)

                self.grid_lay.addWidget(logo, 0, 0)
                self.grid_lay.addWidget(content, 0, 1)
                self.intro_tab_layout.addWidget(intro_scroll_area)

                # LINKS EXCHANGE section
                self.links_tab = QtWidgets.QWidget()
                self.links_tab_layout = QtWidgets.QVBoxLayout(self.links_tab)
                self.links_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.links_tab, _("Links Exchange"))

                self.links_lay = QtWidgets.QHBoxLayout()

                links_wdg = QtWidgets.QWidget()
                links_wdg.setLayout(self.links_lay)
                links_scroll_area = QtWidgets.QScrollArea()
                links_scroll_area.setWidget(links_wdg)
                links_scroll_area.setWidgetResizable(True)
                links_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                links_scroll_area.setPalette(pal)

                self.links_lay.addWidget(
                    FCLabel('%s' % _("Soon ...")), alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
                self.links_tab_layout.addWidget(links_scroll_area)

                # HOW TO section
                self.howto_tab = QtWidgets.QWidget()
                self.howto_tab_layout = QtWidgets.QVBoxLayout(self.howto_tab)
                self.howto_tab_layout.setContentsMargins(2, 2, 2, 2)
                tab_widget.addTab(self.howto_tab, _("How To's"))

                self.howto_lay = QtWidgets.QHBoxLayout()

                howto_wdg = QtWidgets.QWidget()
                howto_wdg.setLayout(self.howto_lay)
                howto_scroll_area = QtWidgets.QScrollArea()
                howto_scroll_area.setWidget(howto_wdg)
                howto_scroll_area.setWidgetResizable(True)
                howto_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                howto_scroll_area.setPalette(pal)

                self.howto_lay.addWidget(
                    FCLabel('%s' % _("Soon ...")), alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
                self.howto_tab_layout.addWidget(howto_scroll_area)

                # BUTTONS section
                closebtn.clicked.connect(self.accept)

        HowtoDialog(app=self, parent=self.ui).exec()

    def install_bookmarks(self, book_dict=None):
        """
        Install the bookmarks actions in the Help menu -> Bookmarks

        :param book_dict:   a dict having the actions text as keys and the weblinks as the values
        :return:            None
        """

        if book_dict is None:
            self.options["global_bookmarks"].update(
                {
                    '1': ['FlatCAM', "http://flatcam.org"],
                    '2': [_('Backup Site'), ""]
                }
            )
        else:
            self.options["global_bookmarks"].clear()
            self.options["global_bookmarks"].update(book_dict)

        # first try to disconnect if somehow they get connected from elsewhere
        for act in self.ui.menuhelp_bookmarks.actions():
            try:
                act.triggered.disconnect()
            except TypeError:
                pass

            # clear all actions except the last one who is the Bookmark manager
            if act is self.ui.menuhelp_bookmarks.actions()[-1]:
                pass
            else:
                self.ui.menuhelp_bookmarks.removeAction(act)

        bm_limit = int(self.options["global_bookmarks_limit"])
        if self.options["global_bookmarks"]:

            # order the self.options["global_bookmarks"] dict keys by the value as integer
            # the whole convoluted things is because when serializing the self.options (on app close or save)
            # the JSON is first making the keys as strings (therefore I have to use strings too
            # or do the conversion :(
            # )
            # and it is ordering them (actually I want that to make the options easy to search within) but making
            # the '10' entry just after '1' therefore ordering as strings

            sorted_bookmarks = sorted(list(self.options["global_bookmarks"].items())[:bm_limit],
                                      key=lambda x: int(x[0]))
            for entry, bookmark in sorted_bookmarks:
                title = bookmark[0]
                weblink = bookmark[1]

                act = QtGui.QAction(parent=self.ui.menuhelp_bookmarks)
                act.setText(title)

                act.setIcon(QtGui.QIcon(self.resource_location + '/link16.png'))
                # from here: https://stackoverflow.com/questions/20390323/pyqt-dynamic-generate-qmenu-action-and-connect
                if title == _('Backup Site') and weblink == "":
                    act.triggered.connect(self.on_backup_site)
                else:
                    act.triggered.connect(lambda sig, link=weblink: webbrowser.open(link))
                self.ui.menuhelp_bookmarks.insertAction(self.ui.menuhelp_bookmarks_manager, act)

        self.ui.menuhelp_bookmarks_manager.triggered.connect(self.on_bookmarks_manager)

    def on_bookmarks_manager(self):
        """
        Adds the bookmark manager in a Tab in Plot Area.

        :return:
        """
        for idx in range(self.ui.plot_tab_area.count()):
            if self.ui.plot_tab_area.tabText(idx) == _("Bookmarks Manager"):
                # there can be only one instance of Bookmark Manager at one time
                return

        # BookDialog(app=self, storage=self.options["global_bookmarks"], parent=self.ui).exec()
        self.book_dialog_tab = BookmarkManager(app=self, storage=self.options["global_bookmarks"], parent=self.ui)
        self.book_dialog_tab.setObjectName("bookmarks_tab")

        # add the tab if it was closed
        self.ui.plot_tab_area.addTab(self.book_dialog_tab, _("Bookmarks Manager"))

        # delete the absolute and relative position and messages in the infobar
        # self.ui.position_label.setText("")
        # self.ui.rel_position_label.setText("")

        # hide coordinates toolbars in the infobar while in DB
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        # Switch plot_area to preferences page
        self.ui.plot_tab_area.setCurrentWidget(self.book_dialog_tab)

    def on_backup_site(self):
        """
        Called when the user click on the menu entry Help -> Bookmarks -> Backup Site

        :return:
        :rtype:
        """
        msgbox = FCMessageBox(parent=self.ui)
        title = _("Alternative website")
        txt = _("This entry will resolve to another website if:\n\n"
                "1. FlatCAM.org website is down\n"
                "2. Someone forked FlatCAM project and wants to point\n"
                "to his own website\n\n"
                "If you can't get any informations about the application\n"
                "use the YouTube channel link from the Help menu.")
        msgbox.setWindowTitle(title)  # taskbar still shows it
        msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
        msgbox.setText('<b>%s</b>\n\n' % title)
        msgbox.setInformativeText(txt)

        msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/globe16.png'))

        bt_yes = msgbox.addButton(_('Close'), QtWidgets.QMessageBox.ButtonRole.YesRole)

        msgbox.setDefaultButton(bt_yes)
        msgbox.exec()
        # response = msgbox.clickedButton()

    def final_save(self):
        """
        Callback for doing a preferences save to file whenever the application is about to quit.
        If the project has changes, it will ask the user to save the project.

        :return: None
        """

        if self.save_in_progress:
            self.inform.emit('[WARNING_NOTCL] %s' % _("Application is saving the project. Please wait ..."))
            return

        if self.should_we_save and self.collection.get_list():
            msgbox = FCMessageBox(parent=self.ui)
            title = _("Save changes")
            txt = _("There are files/objects modified.\n"
                    "Do you want to Save the project?")
            msgbox.setWindowTitle(title)  # taskbar still shows it
            msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
            msgbox.setText('<b>%s</b>' % title)
            msgbox.setInformativeText(txt)
            msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/save_as.png'))

            bt_yes = msgbox.addButton(_('Yes'), QtWidgets.QMessageBox.ButtonRole.YesRole)
            bt_no = msgbox.addButton(_('No'), QtWidgets.QMessageBox.ButtonRole.NoRole)
            bt_cancel = msgbox.addButton(_('Cancel'), QtWidgets.QMessageBox.ButtonRole.RejectRole)

            msgbox.setDefaultButton(bt_yes)
            msgbox.exec()
            response = msgbox.clickedButton()

            if response == bt_yes:
                try:
                    self.trayIcon.hide()
                except Exception:
                    pass
                self.f_handlers.on_file_save_project_as(use_thread=True, quit_action=True)
            elif response == bt_no:
                try:
                    self.trayIcon.hide()
                except Exception:
                    pass
                self.quit_application()
            elif response == bt_cancel:
                return
        else:
            try:
                self.trayIcon.hide()
            except Exception:
                pass
            self.quit_application()

    def quit_application(self, silent=False):
        """
        Called (as a pyslot or not) when the application is quit.

        :return: None
        """

        # make sure that any change we made while working in the app is saved to the defaults
        # WARNING !!! Do not hide UI before saving the state of the UI in the defaults file !!!
        # TODO in the future we need to make a difference between settings that need to be persistent all the time
        self.defaults.update(self.options)
        self.preferencesUiManager.save_defaults(silent=True)

        if silent is False:
            self.log.debug("App.quit_application() --> App Defaults saved.")

        # hide the UI so the user experiments a faster shutdown
        self.ui.hide()

        if sys.platform == 'win32':
            self.new_launch.stop.emit()     # noqa
            # https://forum.qt.io/topic/108777/stop-a-loop-in-object-that-has-been-moved-to-a-qthread/7
            if self.listen_th.isRunning():
                self.listen_th.requestInterruption()
                self.log.debug("ArgThread QThread requested an interruption.")

        # close editors before quiting the app, if they are open
        if self.call_source == 'geo_editor':
            self.geo_editor.deactivate()
            try:
                self.geo_editor.disconnect()
            except TypeError:
                pass
            if silent is False:
                self.log.debug("App.quit_application() --> Geo Editor deactivated.")

        if self.call_source == 'exc_editor':
            self.exc_editor.deactivate()
            try:
                self.exc_editor.disconnect()
            except TypeError:
                pass
            if silent is False:
                self.log.debug("App.quit_application() --> Excellon Editor deactivated.")

        if self.call_source == 'grb_editor':
            self.grb_editor.deactivate_grb_editor()
            try:
                self.grb_editor.disconnect()
            except TypeError:
                pass
            if silent is False:
                self.log.debug("App.quit_application() --> Gerber Editor deactivated.")

        # disconnect the mouse events
        if self.use_3d_engine:
            self.mm = self.plotcanvas.graph_event_disconnect('mouse_move', self.on_mouse_move_over_plot)
            self.mp = self.plotcanvas.graph_event_disconnect('mouse_press', self.on_mouse_click_over_plot)
            self.mr = self.plotcanvas.graph_event_disconnect('mouse_release', self.on_mouse_click_release_over_plot)
            self.mdc = self.plotcanvas.graph_event_disconnect('mouse_double_click',
                                                              self.on_mouse_double_click_over_plot)
            self.kp = self.plotcanvas.graph_event_disconnect('key_press', self.ui.keyPressEvent)
        else:
            self.plotcanvas.graph_event_disconnect(self.mm)
            self.plotcanvas.graph_event_disconnect(self.mp)
            self.plotcanvas.graph_event_disconnect(self.mr)
            self.plotcanvas.graph_event_disconnect(self.mdc)
            self.plotcanvas.graph_event_disconnect(self.kp)

        if self.cmd_line_headless != 1:
            # save app state to file
            stgs = QSettings("Open Source", "FlatCAM_EVO")
            stgs.setValue('saved_gui_state', self.ui.saveState())
            stgs.setValue('maximized_gui', self.ui.isMaximized())
            stgs.setValue(
                'language',
                self.ui.general_pref_form.general_app_group.language_combo.get_value()
            )
            stgs.setValue(
                'notebook_font_size',
                self.ui.general_pref_form.general_app_set_group.notebook_font_size_spinner.get_value()
            )
            stgs.setValue(
                'axis_font_size',
                self.ui.general_pref_form.general_app_set_group.axis_font_size_spinner.get_value()
            )
            stgs.setValue(
                'textbox_font_size',
                self.ui.general_pref_form.general_app_set_group.textbox_font_size_spinner.get_value()
            )
            stgs.setValue(
                'hud_font_size',
                self.ui.general_pref_form.general_app_set_group.hud_font_size_spinner.get_value()
            )
            # This will write the setting to the platform specific storage.
            del stgs

        if silent is False:
            self.log.debug("App.quit_application() --> App UI state saved.")

        # try to quit the QThread that run ArgsThread class
        try:
            # del self.new_launch
            if sys.platform == 'win32':
                self.listen_th.quit()
                self.listen_th.wait(1000)
        except Exception as e:
            if silent is False:
                self.log.error("App.quit_application() --> %s" % str(e))

        # terminate workers
        # self.workers.__del__()
        self.clear_pool()

        self.workers.quit()

        # quit app by signalling for self.kill_app() method
        # self.close_app_signal.emit()
        # sys.exit(0)
        QtWidgets.QApplication.quit()
        if sys.platform == 'win32':
            try:
                self.new_launch.close_command()
            except Exception:
                pass

    @staticmethod
    def kill_app():
        QtCore.QCoreApplication.instance().quit()
        # When the main event loop is not started yet in which case the qApp.quit() will do nothing
        # we use the following command
        sys.exit(0)
        # raise SystemExit

    def on_portable_checked(self, state):
        """
        Callback called when the checkbox in Preferences GUI is checked.
        It will set the application as portable by creating the preferences and recent files in the
        'config' folder found in the FlatCAM installation folder.

        :param state: boolean, the state of the checkbox when clicked/checked
        :return:
        """

        line_no = 0
        data = None

        if sys.platform != 'win32':
            # this won't work in Linux or macOS
            return

        # test if the app was frozen and choose the path for the configuration file
        if getattr(sys, "frozen", False) is True:
            current_data_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '\\config'
        else:
            current_data_path = os.path.dirname(os.path.realpath(__file__)) + '\\config'

        config_file = current_data_path + '\\configuration.txt'
        try:
            with open(config_file, 'r') as f:
                try:
                    data = f.readlines()
                except Exception as e:
                    self.log.error('App.__init__() -->%s' % str(e))
                    return
        except FileNotFoundError:
            pass

        for line in data:
            line = line.strip('\n')
            param = str(line).rpartition('=')
            if param[0] == 'portable':
                break
            line_no += 1

        if state == QtCore.Qt.CheckState.Checked:
            data[line_no] = 'portable=True\n'
            # create the new defauults files
            # create current_defaults.FlatConfig file if there is none
            try:
                f = open(current_data_path + '/current_defaults.FlatConfig')
                f.close()
            except IOError:
                self.log.debug('Creating empty current_defaults.FlatConfig')
                f = open(current_data_path + '/current_defaults.FlatConfig', 'w')
                json.dump({}, f)
                f.close()

            # create factory_defaults.FlatConfig file if there is none
            try:
                f = open(current_data_path + '/factory_defaults.FlatConfig')
                f.close()
            except IOError:
                self.log.debug('Creating empty factory_defaults.FlatConfig')
                f = open(current_data_path + '/factory_defaults.FlatConfig', 'w')
                json.dump({}, f)
                f.close()

            try:
                f = open(current_data_path + '/recent.json')
                f.close()
            except IOError:
                self.log.debug('Creating empty recent.json')
                f = open(current_data_path + '/recent.json', 'w')
                json.dump([], f)
                f.close()

            try:
                fp = open(current_data_path + '/recent_projects.json')
                fp.close()
            except IOError:
                self.log.debug('Creating empty recent_projects.json')
                fp = open(current_data_path + '/recent_projects.json', 'w')
                json.dump([], fp)
                fp.close()

            # save the current defaults to the new defaults file
            self.preferencesUiManager.save_defaults(silent=True, data_path=current_data_path)

        else:
            data[line_no] = 'portable=False\n'

        with open(config_file, 'w') as f:
            f.writelines(data)

    def on_defaults_dict_change(self, field):
        """
        Called whenever a key changed in the "self.options" dictionary. It will set the required GUI element in the
        Edit -> Preferences tab window.

        :param field:   the key of the "self.options" dictionary that was changed.
        :return:        None
        """
        self.preferencesUiManager.defaults_write_form_field(field=field)

    def on_deselect_all(self):
        self.collection.set_all_inactive()
        self.delete_selection_shape()

    def on_workspace_modified(self):
        # self.save_defaults(silent=True)

        self.plotcanvas.delete_workspace()
        self.preferencesUiManager.defaults_read_form()
        self.plotcanvas.draw_workspace(workspace_size=self.options['global_workspaceT'])

    def on_workspace(self):
        if self.ui.general_pref_form.general_app_set_group.workspace_cb.get_value():
            self.plotcanvas.draw_workspace(workspace_size=self.options['global_workspaceT'])
            self.inform[str, bool].emit(_("Workspace enabled."), False)
        else:
            self.plotcanvas.delete_workspace()
            self.inform[str, bool].emit(_("Workspace disabled."), False)
        self.preferencesUiManager.defaults_read_form()
        # self.save_defaults(silent=True)

    def on_workspace_toggle(self):
        state = False if self.ui.general_pref_form.general_app_set_group.workspace_cb.get_value() else True
        try:
            self.ui.general_pref_form.general_app_set_group.workspace_cb.stateChanged.disconnect(self.on_workspace)
        except TypeError:
            pass

        self.ui.general_pref_form.general_app_set_group.workspace_cb.set_value(state)
        self.ui.general_pref_form.general_app_set_group.workspace_cb.stateChanged.connect(self.on_workspace)
        self.on_workspace()

    def on_show_log(self):
        if sys.platform == 'win32':
            subprocess.Popen('explorer %s' % self.log_path())
        elif sys.platform == 'darwin':
            os.system('open "%s"' % self.log_path())
        else:
            subprocess.Popen(['xdg-open', self.log_path()])
        self.inform.emit('[success] %s' % _("FlatCAM log opened."))

    def on_cursor_type(self, val, control_cursor=True):
        """

        :param val:                 type of mouse cursor, set in Preferences ('small' or 'big')
        :param control_cursor:      if True, it is enabled only if the grid snap is active
        :return: None
        """
        self.app_cursor.enabled = False

        if val == 'small':
            self.ui.general_pref_form.general_app_set_group.cursor_size_entry.setDisabled(False)
            self.ui.general_pref_form.general_app_set_group.cursor_size_lbl.setDisabled(False)
            self.app_cursor = self.plotcanvas.new_cursor()
        else:
            self.ui.general_pref_form.general_app_set_group.cursor_size_entry.setDisabled(True)
            self.ui.general_pref_form.general_app_set_group.cursor_size_lbl.setDisabled(True)
            self.app_cursor = self.plotcanvas.new_cursor(big=True)

        if control_cursor is True:
            if self.ui.grid_snap_btn.isChecked():
                self.app_cursor.enabled = True
            else:
                self.app_cursor.enabled = False
        else:
            self.app_cursor.enabled = True

    def on_tool_add_keypress(self):
        # ## Current application units in Upper Case
        self.units = self.app_units.upper()

        notebook_widget_name = self.ui.notebook.currentWidget().objectName()

        # work only if the notebook tab on focus is the properties_tab and only if the object is Geometry
        if notebook_widget_name == 'properties_tab':
            if self.collection.get_active().kind == 'geometry':
                # Tool add works for Geometry only if Advanced is True in Preferences
                if self.options["global_app_level"] == 'a':
                    tool_add_popup = FCInputSpinner(title='%s...' % _("New Tool"),
                                                    text='%s:' % _('Enter a Tool Diameter'),
                                                    min=0.0000, max=100.0000, decimals=self.decimals, step=0.1)
                    tool_add_popup.setWindowIcon(QtGui.QIcon(self.resource_location + '/letter_t_32.png'))
                    tool_add_popup.wdg.selectAll()

                    val, ok = tool_add_popup.get_value()
                    if ok:
                        if float(val) == 0:
                            self.inform.emit('[WARNING_NOTCL] %s' %
                                             _("Please enter a tool diameter with non-zero value, in Float format."))
                            return
                        try:
                            self.collection.get_active().on_tool_add(dia=float(val))
                        except Exception as tadd_err:
                            self.log.debug("App.on_tool_add_keypress() --> %s" % str(tadd_err))
                    else:
                        self.inform.emit('[WARNING_NOTCL] %s...' % _("Adding Tool cancelled"))
                else:
                    msgbox = FCMessageBox(parent=self.ui)
                    title = _("Tool adding ...")
                    txt = _("Adding Tool works only when Advanced is checked.\n"
                            "Go to Preferences -> General - Show Advanced Options.")
                    msgbox.setWindowTitle(title)  # taskbar still shows it
                    msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
                    msgbox.setText('<b>%s</b>' % title)
                    msgbox.setInformativeText(txt)
                    msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/warning.png'))

                    bt_ok = msgbox.addButton(_('Ok'), QtWidgets.QMessageBox.ButtonRole.AcceptRole)

                    msgbox.setDefaultButton(bt_ok)
                    msgbox.exec()

        # work only if the notebook tab on focus is the Tools_Tab
        if notebook_widget_name == 'plugin_tab':
            try:
                tool_widget = self.ui.plugin_scroll_area.widget().objectName()
            except AttributeError:
                return

            # and only if the tool is NCC Tool
            if tool_widget == self.ncclear_tool.pluginName:
                self.ncclear_tool.on_add_tool_by_key()

            # and only if the tool is Paint Area Tool
            elif tool_widget == self.paint_tool.pluginName:
                self.paint_tool.on_add_tool_by_key()

            # and only if the tool is Solder Paste Dispensing Tool
            elif tool_widget == self.paste_tool.pluginName:
                self.paste_tool.on_add_tool_by_key()

            # and only if the tool is Isolation Tool
            elif tool_widget == self.isolation_tool.pluginName:
                self.isolation_tool.on_add_tool_by_key()

    # It's meant to delete tools in tool tables via a 'Delete' shortcut key but only if certain conditions are met
    # See description below.
    def on_delete_keypress(self):
        notebook_widget_name = self.ui.notebook.currentWidget().objectName()

        # work only if the notebook tab on focus is the properties_tab and only if the object is Geometry
        if notebook_widget_name == 'properties_tab':
            if self.collection.get_active().kind == 'geometry':
                self.collection.get_active().on_tool_delete()

        # work only if the notebook tab on focus is the Tools_Tab
        elif notebook_widget_name == 'plugin_tab':
            tool_widget = self.ui.plugin_scroll_area.widget().objectName()

            # and only if the tool is NCC Plugin
            if tool_widget == self.ncclear_tool.pluginName:
                self.ncclear_tool.on_tool_delete()

            # and only if the tool is Paint Plugin
            elif tool_widget == self.paint_tool.pluginName:
                self.paint_tool.on_tool_delete()

            # and only if the tool is Solder Paste Dispensing Plugin
            elif tool_widget == self.paste_tool.pluginName:
                self.paste_tool.on_tool_delete()

            # and only if the tool is Isolation Plugin
            elif tool_widget == self.isolation_tool.pluginName:
                self.isolation_tool.on_tool_delete()
        else:
            self.on_delete()

    # It's meant to delete selected objects. It may work also activated by a shortcut key 'Delete' same as above so in
    # some screens you have to be careful where you hover with your mouse.
    # Hovering over Selected tab, if the selected tab is a Geometry it will delete tools in tool table. But even if
    # there is a Selected tab in focus with a Geometry inside, if you hover over canvas it will delete an object.
    # Complicated, I know :)
    def on_delete(self, force_deletion=False):
        """
        Delete the currently selected FlatCAMObjs.

        :param force_deletion:  used by Tcl command
        :return: None
        """
        self.defaults.report_usage("on_delete()")

        response = None
        bt_ok = None

        # Make sure that the deletion will happen only after the Editor is no longer active otherwise we might delete
        # a geometry object before we update it.
        if self.call_source == 'app':
            if self.options["global_delete_confirmation"] is True and force_deletion is False:
                msgbox = FCMessageBox(parent=self.ui)
                title = _("Delete objects")
                txt = _("Are you sure you want to permanently delete\n"
                        "the selected objects?")
                msgbox.setWindowTitle(title)  # taskbar still shows it
                msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
                msgbox.setText('<b>%s</b>' % title)
                msgbox.setInformativeText(txt)
                msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/deleteshape32.png'))

                bt_ok = msgbox.addButton(_('Ok'), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
                msgbox.addButton(_('Cancel'), QtWidgets.QMessageBox.ButtonRole.RejectRole)

                msgbox.setDefaultButton(bt_ok)
                msgbox.exec()
                response = msgbox.clickedButton()

            if self.options["global_delete_confirmation"] is False or force_deletion is True:
                response = bt_ok

            if response == bt_ok:
                if self.collection.get_active():
                    self.log.debug("App.on_delete()")

                    for obj_active in self.collection.get_selected():
                        # if the deleted object is GerberObject then make sure to delete the possible mark shapes
                        if obj_active.kind == 'gerber':
                            obj_active.mark_shapes_storage.clear()
                            obj_active.mark_shapes.clear(update=True)
                            obj_active.mark_shapes.enabled = False
                            self.tool_shapes.clear(update=True)

                        elif obj_active.kind == 'cncjob':
                            try:
                                obj_active.text_col.enabled = False
                                del obj_active.text_col
                                obj_active.annotation.clear(update=True)
                                del obj_active.annotation
                                obj_active.probing_shapes.clear(update=True)
                            except AttributeError as e:
                                self.log.debug(
                                    "App.on_delete() --> CNCJob object: %s. %s" % (str(obj_active.obj_options['name']),
                                                                                   str(e))
                                )

                    for ob in self.collection.get_selected():
                        self.delete_first_selected(ob)

                    # make sure that the selection shape is deleted, too
                    self.delete_selection_shape()

                    # if there are no longer objects delete also the exclusion areas shapes
                    if not self.collection.get_list():
                        self.exc_areas.clear_shapes()
                else:
                    self.inform.emit('[ERROR_NOTCL] %s %s' % (_("Failed."), _("No object is selected.")))
        else:
            self.inform.emit(_("Save the work in Editor and try again ..."))

    def delete_first_selected(self, del_obj=None):

        # Keep this for later
        try:
            if del_obj is not None:
                sel_obj = del_obj
            else:
                sel_obj = self.collection.get_active()

            name = sel_obj.obj_options["name"]
            isPlotted = sel_obj.obj_options["plot"]
        except AttributeError:
            self.log.debug("Nothing selected for deletion")
            return

        if self.use_3d_engine is False:
            # Remove plot only if the object was plotted otherwise delaxes will fail
            if isPlotted:
                try:
                    self.plotcanvas.figure.delaxes(self.collection.get_active().shapes.axes)
                except Exception as e:
                    self.log.error("App.delete_first_selected() --> %s" % str(e))

            self.plotcanvas.auto_adjust_axes()

        # Remove from dictionary
        self.collection.delete_active()

        # Clear form
        self.setup_default_properties_tab()

        self.inform.emit('%s: %s' % (_("Object deleted"), name))

    def on_set_origin(self):
        """
        Set the origin to the left mouse click position

        :return: None
        """

        # display the message for the user
        # and ask him to click on the desired position
        self.defaults.report_usage("on_set_origin()")

        self.inform.emit(_('Click to set the origin ...'))
        self.inhibit_context_menu = True

        def origin_replot():
            def worker_task():
                with self.proc_container.new('%s...' % _("Plotting")):
                    for obj in self.collection.get_list():
                        obj.plot()
                    self.plotcanvas.fit_view()
                if self.use_3d_engine:
                    self.plotcanvas.graph_event_disconnect('mouse_release', self.on_set_zero_click)
                else:
                    self.plotcanvas.graph_event_disconnect(self.mp_zc)
                self.inhibit_context_menu = False

            self.worker_task.emit({'fcn': worker_task, 'params': []})

        self.mp_zc = self.plotcanvas.graph_event_connect('mouse_release', self.on_set_zero_click)

        # first disconnect it as it may have been used by something else
        try:
            self.replot_signal.disconnect()  # noqa
        except TypeError:
            pass
        self.replot_signal[list].connect(origin_replot)

    def on_set_zero_click(self, event, location=None, noplot=False, use_thread=True):
        """

        :param event:
        :param location:
        :param noplot:
        :param use_thread:
        :return:
        """
        noplot_sig = noplot
        right_button = 2 if self.use_3d_engine else 3

        def worker_task(app_obj):
            with app_obj.proc_container.new(_("Setting Origin...")):
                obj_list = app_obj.collection.get_list()

                for obj in obj_list:
                    obj.offset((x, y))
                    app_obj.app_obj.object_changed.emit(obj)

                    # Update the object bounding box options
                    a, b, c, d = obj.bounds()
                    obj.obj_options['xmin'] = a
                    obj.obj_options['ymin'] = b
                    obj.obj_options['xmax'] = c
                    obj.obj_options['ymax'] = d

                    # make sure to update the Offset field in Properties Tab
                    try:
                        obj.set_offset_values()
                    except AttributeError:
                        # not all objects have this attribute
                        pass

                app_obj.inform.emit('[success] %s...' % _('Origin set'))

                # update the source_file container with the new offseted code
                for obj in obj_list:
                    out_name = obj.obj_options["name"]

                    if obj.kind == 'gerber':
                        obj.source_file = app_obj.f_handlers.export_gerber(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'excellon':
                        obj.source_file = app_obj.f_handlers.export_excellon(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'geometry':
                        obj.source_file = app_obj.f_handlers.export_dxf(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                if noplot_sig is False:
                    app_obj.replot_signal.emit([])

        if location is not None:
            if len(location) != 2:
                self.inform.emit('[ERROR_NOTCL] %s...' % _("Origin coordinates specified but incomplete."))
                return 'fail'

            x, y = location

            if use_thread is True:
                self.worker_task.emit({'fcn': worker_task, 'params': [self]})
            else:
                worker_task(self)
            self.should_we_save = True
            return

        if event is not None and event.button == 1:
            event_pos = event.pos if self.use_3d_engine else (event.xdata, event.ydata)
            pos_canvas = self.plotcanvas.translate_coords(event_pos)

            if self.grid_status():
                pos = self.geo_editor.snap(pos_canvas[0], pos_canvas[1])
            else:
                pos = pos_canvas

            x = 0 - pos[0]
            y = 0 - pos[1]

            if use_thread is True:
                self.worker_task.emit({'fcn': worker_task, 'params': [self]})
            else:
                worker_task(self)
            self.should_we_save = True
        elif event is not None and event.button == right_button:
            if self.ui.popMenu.mouse_is_panning is False:
                if self.use_3d_engine:
                    self.plotcanvas.graph_event_disconnect('mouse_release', self.on_set_zero_click)
                    self.inhibit_context_menu = False
                else:
                    self.plotcanvas.graph_event_disconnect(self.mp_zc)

                self.inform.emit('[WARNING_NOTCL] %s' % _("Cancelled."))

    def on_move2origin(self, use_thread=True):
        """
        Move selected objects to origin.
        :param use_thread: Control if to use threaded operation. Boolean.
        :return:
        """

        def worker_task():
            with self.proc_container.new(_("Moving to Origin...")):
                obj_list = self.collection.get_selected()

                if not obj_list:
                    self.inform.emit('[ERROR_NOTCL] %s' % _("Failed. No object(s) selected..."))
                    return

                xminlist = []
                yminlist = []

                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)

                # get the minimum x,y for all objects selected
                x = min(xminlist)
                y = min(yminlist)

                for obj in obj_list:
                    obj.offset((-x, -y))
                    self.app_obj.object_changed.emit(obj)

                    # Update the object bounding box options
                    a, b, c, d = obj.bounds()
                    obj.obj_options['xmin'] = a
                    obj.obj_options['ymin'] = b
                    obj.obj_options['xmax'] = c
                    obj.obj_options['ymax'] = d

                    # make sure to update the Offset field in Properties Tab
                    try:
                        obj.set_offset_values()
                    except AttributeError:
                        # not all objects have this attribute
                        pass

                for obj in obj_list:
                    obj.plot()
                self.plotcanvas.fit_view()

                for obj in obj_list:
                    out_name = obj.obj_options["name"]

                    if obj.kind == 'gerber':
                        obj.source_file = self.f_handlers.export_gerber(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'excellon':
                        obj.source_file = self.f_handlers.export_excellon(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                    elif obj.kind == 'geometry':
                        obj.source_file = self.f_handlers.export_dxf(
                            obj_name=out_name, filename=None, local_use=obj, use_thread=False)
                self.inform.emit('[success] %s...' % _('Origin set'))

        if use_thread is True:
            self.worker_task.emit({'fcn': worker_task, 'params': []})
        else:
            worker_task()
        self.should_we_save = True

    def on_jump_to(self, custom_location=None, fit_center=True):
        """
        Jump to a location by setting the mouse cursor location.

        :param custom_location:     Jump to a specified point. (x, y) tuple.
        :param fit_center:          If to fit view. Boolean.
        :return:

        """
        self.defaults.report_usage("on_jump_to()")

        if not custom_location:
            dia_box_location = None

            try:
                dia_box_location = eval(self.clipboard.text())
            except Exception:
                pass

            if isinstance(dia_box_location, tuple):
                dia_box_location = str(dia_box_location)
            else:
                dia_box_location = None

            # dia_box = Dialog_box(title=_("Jump to ..."),
            #                      label=_("Enter the coordinates in format X,Y:"),
            #                      icon=QtGui.QIcon(self.resource_location + '/jump_to32.png'),
            #                      initial_text=dia_box_location)

            dia_box = DialogBoxRadio(title=_("Jump to ..."),
                                     label=_("Enter the coordinates in format X,Y:"),
                                     icon=QtGui.QIcon(self.resource_location + '/jump_to32.png'),
                                     initial_text=dia_box_location,
                                     reference=self.options['global_jump_ref'],
                                     parent=self.ui)

            if dia_box.ok is True:
                try:
                    location = eval(dia_box.location)

                    if not isinstance(location, tuple):
                        self.inform.emit(_("Wrong coordinates. Enter coordinates in format: X,Y"))
                        return

                    if dia_box.reference == 'rel':
                        rel_x = self.mouse_pos[0] + location[0]
                        rel_y = self.mouse_pos[1] + location[1]
                        location = (rel_x, rel_y)
                    self.options['global_jump_ref'] = dia_box.reference
                except Exception:
                    return
            else:
                return
        else:
            location = custom_location

        self.jump_signal.emit(location)     # noqa

        if fit_center:
            self.plotcanvas.fit_center(loc=location)

        cursor = QtGui.QCursor()

        if self.use_3d_engine:
            # I don't know where those differences come from, but they are constant for the current
            # execution of the application, and they are multiples of a value around 0.0263mm.
            # In a random way sometimes they are more sometimes they are less
            # if units == 'MM':
            #     cal_factor = 0.0263
            # else:
            #     cal_factor = 0.0263 / 25.4

            cal_location = (location[0], location[1])

            canvas_origin = self.plotcanvas.native.mapToGlobal(QtCore.QPoint(0, 0))
            jump_loc = self.plotcanvas.translate_coords_2((cal_location[0], cal_location[1]))

            j_pos = (
                int(canvas_origin.x() + round(jump_loc[0])),
                int(canvas_origin.y() + round(jump_loc[1]))
            )
            cursor.setPos(j_pos[0], j_pos[1])
        else:
            # find the canvas origin which is in the top left corner
            canvas_origin = self.plotcanvas.native.mapToGlobal(QtCore.QPoint(0, 0))
            # determine the coordinates for the lowest left point of the canvas
            x0, y0 = canvas_origin.x(), canvas_origin.y() + self.ui.right_layout.geometry().height()

            # transform the given location from data coordinates to display coordinates. THe display coordinates are
            # in pixels where the origin 0,0 is in the lowest left point of the display window (in our case is the
            # canvas) and the point (width, height) is in the top-right location
            loc = self.plotcanvas.axes.transData.transform_point(location)
            j_pos = (
                int(x0 + loc[0]),
                int(y0 - loc[1])
            )
            cursor.setPos(j_pos[0], j_pos[1])
            self.plotcanvas.mouse = [location[0], location[1]]
            if self.options["global_cursor_color_enabled"] is True:
                self.plotcanvas.draw_cursor(x_pos=location[0], y_pos=location[1], color=self.cursor_color_3D)
            else:
                self.plotcanvas.draw_cursor(x_pos=location[0], y_pos=location[1])

        if self.grid_status():
            # Update cursor
            self.app_cursor.set_data(np.asarray([(location[0], location[1])]),
                                     symbol='++', edge_color=self.plotcanvas.cursor_color,
                                     edge_width=self.options["global_cursor_width"],
                                     size=self.options["global_cursor_size"])

        # Set the relative position label
        dx = location[0] - float(self.rel_point1[0])
        dy = location[1] - float(self.rel_point1[1])

        self.ui.update_location_labels(dx, dy, location[0], location[1])
        self.plotcanvas.on_update_text_hud(dx, dy, location[0], location[1])

        self.inform.emit('[success] %s' % _("Done."))
        return location

    def on_locate(self, obj, fit_center=True):
        """
        Jump to one of the corners (or center) of an object by setting the mouse cursor location

        :param obj:         The object on which to locate certain points
        :param fit_center:  If to fit view. Boolean.
        :return:            A point location. (x, y) tuple.

        """
        self.defaults.report_usage("on_locate()")

        if obj is None:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return 'fail'

        choices = [
            {"label": _("T Left"), "value": "tl"},
            {"label": _("T Right"), "value": "tr"},
            {"label": _("B Left"), "value": "bl"},
            {"label": _("B Right"), "value": "br"},
            {"label": _("Center"), "value": "c"}
        ]
        dia_box = DialogBoxChoice(title=_("Locate ..."),
                                  icon=QtGui.QIcon(self.resource_location + '/locate16.png'),
                                  choices=choices,
                                  default_choice=self.options['global_locate_pt'],
                                  parent=self.ui)

        if dia_box.ok is True:
            try:
                location_point = dia_box.location_point
                self.options['global_locate_pt'] = dia_box.location_point
            except Exception:
                return
        else:
            return

        loc_b = obj.bounds()
        if location_point == 'bl':
            location = (loc_b[0], loc_b[1])
        elif location_point == 'tl':
            location = (loc_b[0], loc_b[3])
        elif location_point == 'br':
            location = (loc_b[2], loc_b[1])
        elif location_point == 'tr':
            location = (loc_b[2], loc_b[3])
        else:
            # center
            cx = loc_b[0] + abs((loc_b[2] - loc_b[0]) / 2)
            cy = loc_b[1] + abs((loc_b[3] - loc_b[1]) / 2)
            location = (cx, cy)

        self.locate_signal.emit(location, location_point)   # noqa

        if fit_center:
            self.plotcanvas.fit_center(loc=location)

        cursor = QtGui.QCursor()

        if self.use_3d_engine:
            # I don't know where those differences come from, but they are constant for the current
            # execution of the application, and they are multiples of a value around 0.0263mm.
            # In a random way sometimes they are more sometimes they are less
            # if units == 'MM':
            #     cal_factor = 0.0263
            # else:
            #     cal_factor = 0.0263 / 25.4

            cal_location = (location[0], location[1])

            canvas_origin = self.plotcanvas.native.mapToGlobal(QtCore.QPoint(0, 0))
            jump_loc = self.plotcanvas.translate_coords_2((cal_location[0], cal_location[1]))

            j_pos = (
                int(canvas_origin.x() + round(jump_loc[0])),
                int(canvas_origin.y() + round(jump_loc[1]))
            )
            cursor.setPos(j_pos[0], j_pos[1])
        else:
            # find the canvas origin which is in the top left corner
            canvas_origin = self.plotcanvas.native.mapToGlobal(QtCore.QPoint(0, 0))
            # determine the coordinates for the lowest left point of the canvas
            x0, y0 = canvas_origin.x(), canvas_origin.y() + self.ui.right_layout.geometry().height()

            # transform the given location from data coordinates to display coordinates. THe display coordinates are
            # in pixels where the origin 0,0 is in the lowest left point of the display window (in our case is the
            # canvas) and the point (width, height) is in the top-right location
            loc = self.plotcanvas.axes.transData.transform_point(location)
            j_pos = (
                int(x0 + loc[0]),
                int(y0 - loc[1])
            )
            cursor.setPos(j_pos[0], j_pos[1])
            self.plotcanvas.mouse = [location[0], location[1]]
            if self.options["global_cursor_color_enabled"] is True:
                self.plotcanvas.draw_cursor(x_pos=location[0], y_pos=location[1], color=self.cursor_color_3D)
            else:
                self.plotcanvas.draw_cursor(x_pos=location[0], y_pos=location[1])

        if self.grid_status():
            # Update cursor
            self.app_cursor.set_data(np.asarray([(location[0], location[1])]),
                                     symbol='++', edge_color=self.plotcanvas.cursor_color,
                                     edge_width=self.options["global_cursor_width"],
                                     size=self.options["global_cursor_size"])

        # Set the relative position label
        self.dx = location[0] - float(self.rel_point1[0])
        self.dy = location[1] - float(self.rel_point1[1])
        # Set the position label
        # self.ui.position_label.setText("&nbsp;<b>X</b>: %.4f&nbsp;&nbsp;   "
        #                                "<b>Y</b>: %.4f&nbsp;" % (location[0], location[1]))
        # self.ui.rel_position_label.setText("<b>Dx</b>: %.4f&nbsp;&nbsp;  <b>Dy</b>: "
        #                                    "%.4f&nbsp;&nbsp;&nbsp;&nbsp;" % (self.dx, self.dy))
        self.ui.update_location_labels(self.dx, self.dy, location[0], location[1])

        # units = self.app_units.lower()
        # self.plotcanvas.text_hud.text = \
        #     'Dx:\t{:<.4f} [{:s}]\nDy:\t{:<.4f} [{:s}]\n\nX:  \t{:<.4f} [{:s}]\nY:  \t{:<.4f} [{:s}]'.format(
        #         self.dx, units, self.dy, units, location[0], units, location[1], units)
        self.plotcanvas.on_update_text_hud(self.dx, self.dy, location[0], location[1])

        self.inform.emit('[success] %s' % _("Done."))
        return location

    def on_numeric_move(self, val=None):
        """
        Move to a specific location (absolute or relative against current position)

        :param val: custom offset value, (x, y)
        :type val:  tuple
        :return:    None
        :rtype:     None
        """

        # move only the objects selected and plotted and visible
        obj_list = [
            obj for obj in self.collection.get_selected() if obj.obj_options['plot'] and obj.visible is True
        ]

        if not obj_list:
            self.inform.emit('[ERROR_NOTCL] %s %s' % (_("Failed."), _("Nothing selected.")))
            return

        def bounds_rec(obj):
            try:
                minx = Inf
                miny = Inf
                maxx = -Inf
                maxy = -Inf

                work_geo = obj.geoms if isinstance(obj, (MultiPolygon, MultiLineString)) else obj
                for k in work_geo:
                    minx_, miny_, maxx_, maxy_ = bounds_rec(k)
                    minx = min(minx, minx_)
                    miny = min(miny, miny_)
                    maxx = max(maxx, maxx_)
                    maxy = max(maxy, maxy_)
                return minx, miny, maxx, maxy
            except TypeError:
                # it's an App object, return its bounds
                if obj:
                    return obj.bounds()

        bounds = bounds_rec(obj_list)   # noqa

        if not val:
            dia_box_location = (0.0, 0.0)

            dia_box = DialogBoxRadio(title=_("Move to ..."),
                                     label=_("Enter the coordinates in format X,Y:"),
                                     icon=QtGui.QIcon(self.resource_location + '/move32_bis.png'),
                                     initial_text=dia_box_location,
                                     reference=self.options['global_move_ref'],
                                     parent=self.ui)

            if dia_box.ok is True:
                try:
                    location = [float(x) if x != '' else 0.0 for x in dia_box.location.split(',')]
                    if not isinstance(location, (tuple, list)):
                        self.inform.emit(_("Wrong coordinates. Enter coordinates in format: X,Y"))
                        return

                    if dia_box.reference == 'abs':
                        abs_x = location[0] - bounds[0]
                        abs_y = location[1] - bounds[1]
                        location = (abs_x, abs_y)
                    self.options['global_jump_ref'] = dia_box.reference
                except Exception:
                    return
            else:
                return
        else:
            location = val

        self.move_tool.move_handler(offset=location, objects=obj_list)

    def on_copy_command(self):
        """
        Will copy a selection of objects, creating new objects.
        :return:
        """
        self.defaults.report_usage("on_copy_command()")

        def initialize(obj_init, app_obj):
            """

            :param obj_init:    the new object
            :type obj_init:     class
            :param app_obj:     An instance of the App class
            :type app_obj:      App
            :return:            None
            :rtype:
            """

            obj_init.solid_geometry = deepcopy(obj.solid_geometry)
            try:
                obj_init.follow_geometry = deepcopy(obj.follow_geometry)
            except AttributeError:
                pass

            try:
                obj_init.tools = deepcopy(obj.tools)
            except AttributeError:
                pass

            try:
                if obj.tools:
                    obj_init.tools = deepcopy(obj.tools)
            except Exception as cerr:
                app_obj.log.error("App.on_copy_command() --> %s" % str(cerr))
                return "fail"

            try:
                obj_init.source_file = deepcopy(obj.source_file)
            except (AttributeError, TypeError):
                pass

        def initialize_excellon(obj_init, app_obj):
            obj_init.source_file = deepcopy(obj.source_file)

            obj_init.tools = deepcopy(obj.tools)

            obj_init.create_geometry()

            if not obj_init.tools:
                app_obj.debug("on_copy_command() --> no excellon tools")
                return 'fail'

        def initialize_script(new_obj, app_obj):
            app_obj.log.debug("Script copied.")
            new_obj.source_file = deepcopy(obj.source_file)

        def initialize_document(new_obj, app_obj):
            app_obj.log.debug("Document copied.")
            new_obj.source_file = deepcopy(obj.source_file)

        for obj in self.collection.get_selected():
            obj_name = obj.obj_options["name"]

            try:
                if obj.kind == 'excellon':
                    self.app_obj.new_object("excellon", str(obj_name) + "_copy", initialize_excellon)
                elif obj.kind == 'gerber':
                    self.app_obj.new_object("gerber", str(obj_name) + "_copy", initialize)
                elif obj.kind == 'geometry':
                    self.app_obj.new_object("geometry", str(obj_name) + "_copy", initialize)
                elif obj.kind == 'script':
                    self.app_obj.new_object("script", str(obj_name) + "_copy", initialize_script)
                elif obj.kind == 'document':
                    self.app_obj.new_object("document", str(obj_name) + "_copy", initialize_document)
            except Exception as e:
                self.log.error("Copy operation failed: %s for object: %s" % (str(e), str(obj_name)))

    def on_copy_object2(self, custom_name):

        def initialize_geometry(obj_init, app_obj):
            obj_init.solid_geometry = deepcopy(obj.solid_geometry)
            try:
                obj_init.follow_geometry = deepcopy(obj.follow_geometry)
            except AttributeError:
                pass

            try:
                obj_init.tools = deepcopy(obj.tools)
            except AttributeError:
                pass

            try:
                if obj.tools:
                    obj_init.tools = deepcopy(obj.tools)
            except Exception as ee:
                app_obj.error("on_copy_object2() --> %s" % str(ee))

        def initialize_gerber(obj_init, app_obj):
            obj_init.solid_geometry = deepcopy(obj.solid_geometry)
            obj_init.tools = deepcopy(obj.tools)
            obj_init.aperture_macros = deepcopy(obj.aperture_macros)
            if not obj_init.tools:
                app_obj.debug("on_copy_object2() --> no gerber apertures")
                return 'fail'

        def initialize_excellon(new_obj, app_obj):
            new_obj.tools = deepcopy(obj.tools)
            new_obj.create_geometry()
            if not new_obj.tools:
                app_obj.debug("on_copy_object2() --> no excellon tools")
                return 'fail'
            new_obj.source_file = app_obj.f_handlers.export_excellon(obj_name=outname, local_use=new_obj,
                                                                     filename=None, use_thread=False)

        for obj in self.collection.get_selected():
            obj_name = obj.obj_options["name"]
            outname = str(obj_name) + custom_name

            try:
                if isinstance(obj, ExcellonObject):
                    self.app_obj.new_object("excellon", outname, initialize_excellon)
                elif isinstance(obj, GerberObject):
                    self.app_obj.new_object("gerber", outname, initialize_gerber)
                elif isinstance(obj, GeometryObject):
                    self.app_obj.new_object("geometry", outname, initialize_geometry)
            except Exception as er:
                return "Operation failed: %s" % str(er)

    def on_rename_object(self, text):
        """
        Will rename an object.

        :param text:    New name for the object.
        :return:
        """
        self.defaults.report_usage("on_rename_object()")

        named_obj = self.collection.get_active()
        for obj in named_obj:
            if obj is list:
                self.on_rename_object(text)
            else:
                try:
                    obj.obj_options['name'] = text
                except Exception as e:
                    self.log.error(
                        "App.on_rename_object() --> Could not rename the object in the list. --> %s" % str(e))

    def abort_all_tasks(self):
        """
        Executed when a certain key combo is pressed (Ctrl+Alt+X). Will abort current task
        on the first possible occasion.

        :return:
        """
        if self.abort_flag is False:
            msg = "%s %s" % (_("Aborting."), _("The current task will be gracefully closed as soon as possible..."))
            self.inform.emit(msg)
            self.abort_flag = True
            self.cleanup.emit()     # noqa

    def app_is_idle(self):
        if self.abort_flag:
            self.inform.emit('[WARNING_NOTCL] %s' % _("The current task was gracefully closed on user request..."))
            self.abort_flag = False

    def on_selectall(self):
        """
        Will draw a selection box shape around the selected objects.

        :return:
        """

        # delete the possible selection box around a possible selected object
        self.delete_selection_shape()
        for name in self.collection.get_names():
            self.collection.set_active(name)
            curr_sel_obj = self.collection.get_by_name(name)
            # create the selection box around the selected object
            if self.options['global_selection_shape'] is True:
                try:
                    self.draw_selection_shape(curr_sel_obj)
                except Exception as gerr:
                    self.log.error(
                        "App.on_select_all(). Object %s can't be selected on canvas. Error: %s" % (name, str(gerr)))

    def on_toggle_preferences(self):
        pref_open = False
        for idx in range(self.ui.plot_tab_area.count()):
            if self.ui.plot_tab_area.tabText(idx) == _("Preferences"):
                pref_open = True

        if pref_open:
            for idx in range(self.ui.plot_tab_area.count()):
                if self.ui.plot_tab_area.tabText(idx) == _("Preferences"):
                    self.ui.plot_tab_area.removeTab(idx)
                    break

            self.log.debug("Preferences GUI was closed.")
            self.preferencesUiManager.clear_preferences_gui()
            self.ui.pref_status_label.setStyleSheet("")
        else:
            self.on_preferences()

    def on_preferences(self):
        """
        Adds the Preferences in a Tab in Plot Area

        :return:
        """

        self.preferencesUiManager.show_preferences_gui()

        # add the tab if it was closed
        self.ui.plot_tab_area.addTab(self.ui.preferences_tab, _("Preferences"))

        # delete the absolute and relative position and messages in the infobar
        # self.ui.position_label.setText("")
        # self.ui.rel_position_label.setText("")
        # hide coordinates toolbars in the infobar while in DB
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        # Switch plot_area to preferences page
        self.ui.plot_tab_area.setCurrentWidget(self.ui.preferences_tab)
        # self.ui.show()

        self.ui.pref_status_label.setStyleSheet("""
                                                QLabel
                                                {
                                                    color: black;
                                                    background-color: lightseagreen;
                                                }
                                                """
                                                )

        # detect changes in the preferences
        for idx in range(self.ui.pref_tab_area.count()):
            for tb in self.ui.pref_tab_area.widget(idx).findChildren(QtWidgets.QWidget):
                try:
                    try:
                        tb.textEdited.disconnect(self.preferencesUiManager.on_preferences_edited)
                    except (TypeError, AttributeError):
                        pass
                    tb.textEdited.connect(self.preferencesUiManager.on_preferences_edited)
                except AttributeError:
                    pass

                try:
                    try:
                        tb.modificationChanged.disconnect(self.preferencesUiManager.on_preferences_edited)
                    except (TypeError, AttributeError):
                        pass
                    tb.modificationChanged.connect(self.preferencesUiManager.on_preferences_edited)
                except AttributeError:
                    pass

                try:
                    try:
                        tb.toggled.disconnect(self.preferencesUiManager.on_preferences_edited)
                    except (TypeError, AttributeError):
                        pass
                    tb.toggled.connect(self.preferencesUiManager.on_preferences_edited)
                except AttributeError:
                    pass

                try:
                    try:
                        tb.valueChanged.disconnect(self.preferencesUiManager.on_preferences_edited)
                    except (TypeError, AttributeError):
                        pass
                    tb.valueChanged.connect(self.preferencesUiManager.on_preferences_edited)
                except AttributeError:
                    pass

                try:
                    try:
                        tb.currentIndexChanged.disconnect(self.preferencesUiManager.on_preferences_edited)
                    except (TypeError, AttributeError):
                        pass
                    tb.currentIndexChanged.connect(self.preferencesUiManager.on_preferences_edited)
                except AttributeError:
                    pass

    def on_tools_database(self, source='app'):
        """
        Adds the Tools Database in a Tab in Plot Area.

        :return:
        """
        filename = self.tools_database_path()

        # load the database tools from the file
        try:
            with open(filename) as f:
                __ = f.read()
        except Exception as eros:
            self.log.error("The tools DB file is not loaded: %s" % str(eros))
            self.log.error("Could not access tools DB file. The file may be locked,\n"
                           "not existing or doesn't have the read permissions.\n"
                           "Check to see if exists, it should be here: %s\n"
                           "It may help to reboot the app, it will try to recreate it if it's missing." %
                           self.data_path)
            self.inform.emit('[ERROR] %s' % _("Could not load the file."))
            return 'fail'

        for idx in range(self.ui.plot_tab_area.count()):
            if self.ui.plot_tab_area.tabText(idx) == _("Tools Database"):
                # there can be only one instance of Tools Database at one time
                return

        if source == 'app':
            self.tools_db_tab = ToolsDB2(
                app=self,
                parent=self.ui,
                callback_on_tool_request=self.on_geometry_tool_add_from_db_executed
            )
        elif source == 'ncc':
            self.tools_db_tab = ToolsDB2(
                app=self,
                parent=self.ui,
                callback_on_tool_request=self.ncclear_tool.on_ncc_tool_add_from_db_executed
            )
        elif source == 'paint':
            self.tools_db_tab = ToolsDB2(
                app=self,
                parent=self.ui,
                callback_on_tool_request=self.paint_tool.on_paint_tool_add_from_db_executed
            )
        elif source == 'iso':
            self.tools_db_tab = ToolsDB2(
                app=self,
                parent=self.ui,
                callback_on_tool_request=self.isolation_tool.on_iso_tool_add_from_db_executed
            )
        elif source == 'cutout':
            self.tools_db_tab = ToolsDB2(
                app=self,
                parent=self.ui,
                callback_on_tool_request=self.cutout_tool.on_cutout_tool_add_from_db_executed
            )

        # add the tab if it was closed
        try:
            self.ui.plot_tab_area.addTab(self.tools_db_tab, _("Tools Database"))
            self.tools_db_tab.setObjectName("database_tab")
        except Exception as e:
            self.log.error("App.on_tools_database() --> %s" % str(e))
            return

        # delete the absolute and relative position and messages in the infobar
        # self.ui.position_label.setText("")
        # self.ui.rel_position_label.setText("")

        # hide coordinates toolbars in the infobar while in DB
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        # Switch plot_area to preferences page
        self.ui.plot_tab_area.setCurrentWidget(self.tools_db_tab)

        # detect changes in the Tools in Tools DB, connect signals from table widget in tab
        self.tools_db_tab.ui_connect()

    def on_3d_area(self):
        if self.use_3d_engine is False:
            msg = '[ERROR_NOTCL] %s' % _("Not available for Legacy 2D graphic mode.")
            self.inform.emit(msg)
            return

        # add the tab if it was closed
        try:
            self.ui.plot_tab_area.addTab(self.area_3d_tab, _("3D Area"))
            self.area_3d_tab.setObjectName("3D_area_tab")
        except Exception as e:
            self.log.error("App.on_3d_area() --> %s" % str(e))
            return

        plot_container_3d = QtWidgets.QVBoxLayout()
        self.area_3d_tab.setLayout(plot_container_3d)

        try:
            plotcanvas3d = PlotCanvas3d(plot_container_3d, self)
        except Exception as er:
            msg_txt = traceback.format_exc()
            self.log.error("App.on_3d_area() failed -> %s" % str(er))
            self.log.error("OpenGL canvas initialization failed with the following error.\n" + msg_txt)
            msg = '[ERROR_NOTCL] %s' % _("An internal error has occurred. See shell.\n")
            msg += msg_txt
            self.inform.emit(msg)
            return 'fail'

        # So it can receive key presses
        plotcanvas3d.native.setFocus()

        pan_button = 2 if self.options["global_pan_button"] == '2' else 3
        # Set the mouse button for panning
        plotcanvas3d.view.camera.pan_button_setting = pan_button

        # self.mm = plotcanvas3D.graph_event_connect('mouse_move', self.on_mouse_move_over_plot)
        # self.mp = plotcanvas3D.graph_event_connect('mouse_press', self.on_mouse_click_over_plot)
        # self.mr = plotcanvas3D.graph_event_connect('mouse_release', self.on_mouse_click_release_over_plot)
        # self.mdc = plotcanvas3D.graph_event_connect('mouse_double_click', self.on_mouse_double_click_over_plot)

        # Keys over plot enabled
        # self.kp = plotcanvas3D.graph_event_connect('key_press', self.ui.keyPressEvent)

        # hide coordinates toolbars in the infobar
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        # Switch plot_area to Area 3D page
        self.ui.plot_tab_area.setCurrentWidget(self.area_3d_tab)

    def on_geometry_tool_add_from_db_executed(self, tool):
        """
        Here add the tool from DB  in the selected geometry object.

        :return:
        """
        tool_from_db = deepcopy(tool)
        obj = self.collection.get_active()

        if obj is None:
            self.inform.emit('[ERROR_NOTCL] %s' % _("No object is selected."))
            return

        if obj.kind == 'geometry':
            if tool['data']['tool_target'] not in [0, 1]:  # General, Milling Type
                # close the tab and delete it
                for idx in range(self.ui.plot_tab_area.count()):
                    if self.ui.plot_tab_area.tabText(idx) == _("Tools Database"):
                        wdg = self.ui.plot_tab_area.widget(idx)
                        wdg.deleteLater()
                        self.ui.plot_tab_area.removeTab(idx)
                self.inform.emit('[ERROR_NOTCL] %s' % _("Selected tool can't be used here. Pick another."))
                return

            # obj.on_tool_from_db_inserted(tool=tool_from_db)
            self.milling_tool.on_tool_from_db_inserted(tool=tool_from_db)

            # close the tab and delete it
            for idx in range(self.ui.plot_tab_area.count()):
                if self.ui.plot_tab_area.tabText(idx) == _("Tools Database"):
                    wdg = self.ui.plot_tab_area.widget(idx)
                    wdg.deleteLater()
                    self.ui.plot_tab_area.removeTab(idx)
            self.inform.emit('[success] %s' % _("Tool from DB added in Tool Table."))
        elif obj.kind == 'gerber':
            if tool['data']['tool_target'] not in [0, 3]:  # General, Isolation Type
                # close the tab and delete it
                for idx in range(self.ui.plot_tab_area.count()):
                    if self.ui.plot_tab_area.tabText(idx) == _("Tools Database"):
                        wdg = self.ui.plot_tab_area.widget(idx)
                        wdg.deleteLater()
                        self.ui.plot_tab_area.removeTab(idx)
                self.inform.emit('[ERROR_NOTCL] %s' % _("Selected tool can't be used here. Pick another."))
                return
            self.isolation_tool.on_tool_from_db_inserted(tool=tool_from_db)

            # close the tab and delete it
            for idx in range(self.ui.plot_tab_area.count()):
                if self.ui.plot_tab_area.tabText(idx) == _("Tools Database"):
                    wdg = self.ui.plot_tab_area.widget(idx)
                    wdg.deleteLater()
                    self.ui.plot_tab_area.removeTab(idx)
            self.inform.emit('[success] %s' % _("Tool from DB added in Tool Table."))
        else:
            self.inform.emit('[ERROR_NOTCL] %s' % _("Adding tool from DB is not allowed for this object."))

    def on_plot_area_tab_closed(self, tab_obj_name):
        """
        Executed whenever a QTab is closed in the Plot Area.

        :param tab_obj_name: The objectName of the Tab that was closed. This objectName is assigned on Tab creation
        :return:
        """

        if tab_obj_name == "preferences_tab":
            self.preferencesUiManager.on_close_preferences_tab(parent=self.ui)
        elif tab_obj_name == "database_tab":
            # disconnect the signals from the table widget in tab
            self.tools_db_tab.ui_disconnect()

            if self.tools_db_changed_flag is True:
                msgbox = FCMessageBox(parent=self.ui)
                title = _("Save Tools Database")
                txt = _("One or more Tools are edited.\n"
                        "Do you want to save?")
                msgbox.setWindowTitle(title)  # taskbar still shows it
                msgbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/app128.png'))
                msgbox.setText('<b>%s</b>' % title)
                msgbox.setInformativeText(txt)
                msgbox.setIconPixmap(QtGui.QPixmap(self.resource_location + '/save_as.png'))

                bt_yes = msgbox.addButton(_('Yes'), QtWidgets.QMessageBox.ButtonRole.YesRole)
                msgbox.addButton(_('No'), QtWidgets.QMessageBox.ButtonRole.NoRole)

                msgbox.setDefaultButton(bt_yes)
                msgbox.exec()
                response = msgbox.clickedButton()

                if response == bt_yes:
                    self.tools_db_tab.on_save_tools_db()
                    self.inform.emit('[success] %s' % "Tools DB saved to file.")
                else:
                    self.tools_db_changed_flag = False
                    self.inform.emit('')
                    return
            self.tools_db_tab.deleteLater()
        elif tab_obj_name == "text_editor_tab":
            self.toggle_codeeditor = False
        elif tab_obj_name == "bookmarks_tab":
            self.book_dialog_tab.rebuild_actions()
            self.book_dialog_tab.deleteLater()
        elif tab_obj_name == "3D_area_tab":
            self.area_3d_tab.deleteLater()
            self.area_3d_tab = QtWidgets.QWidget()
        elif tab_obj_name == "gcode_editor_tab":
            self.on_editing_finished()
        else:
            pass

        # restore the coords toolbars
        self.ui.toggle_coords(checked=self.options["global_coords_bar_show"])
        self.ui.toggle_delta_coords(checked=self.options["global_delta_coords_bar_show"])

    def on_plot_area_tab_double_clicked(self):
        # tab_obj_name = self.ui.plot_tab_area.widget(index).objectName()
        # print(tab_obj_name)
        self.ui.on_toggle_notebook()

    def on_notebook_closed(self):

        # closed_plugin_name = self.ui.plugin_scroll_area.widget().objectName()
        # # print(closed_plugin_name)
        # if closed_plugin_name == _("Levelling"):
        #     # clear the possible drawn probing shapes
        #     self.levelling_tool.probing_shapes.clear(update=True)
        # elif closed_plugin_name in [_("Isolation"), _("NCC"), _("Paint"), _("Punch Gerber")]:
        #     self.tool_shapes.clear(update=True)

        # disconnected_tool = self.ui.plugin_scroll_area.widget()

        # try:
        #     # if the closed plugin name is Milling
        #     disconnected_tool.disconnect_signals()
        #     disconnected_tool.ui_disconnect()
        #     disconnected_tool.clear_ui(disconnected_tool.layout)
        #
        # except Exception as err:
        #     print(str(err))

        try:
            # this signal is used by the Plugins to change the selection on App objects combo boxes when the
            # selection happen in Project Tab (collection view)
            # when the plugin is closed then it's not needed
            self.proj_selection_changed.disconnect()    # noqa
        except (TypeError, AttributeError):
            pass

        try:
            # clear the possible drawn probing shapes for Levelling Tool
            self.levelling_tool.probing_shapes.clear(update=True)
        except AttributeError:
            pass

        try:
            # clean possible tool shapes for Isolation, NCC, Paint, Punch Gerber Plugins
            self.tool_shapes.clear(update=True)
        except AttributeError:
            pass

        # clean the Tools Tab
        found_idx = None
        for idx in range(self.ui.notebook.count()):
            if self.ui.notebook.widget(idx).objectName() == "plugin_tab":
                found_idx = idx
                break
        if found_idx:
            # #########################################################################################################
            # first do the Plugin cleanup
            # #########################################################################################################
            for plugin in self.app_plugins:
                try:
                    # execute this only for the current active plugin
                    if self.ui.notebook.tabText(found_idx) != plugin.pluginName:
                        continue
                    plugin.on_plugin_cleanup()
                except AttributeError:
                    # not all plugins have this implemented
                    # print("This does not have it", self.ui.notebook.tabText(tab_idx))
                    pass
            self.ui.notebook.setCurrentWidget(self.ui.properties_tab)
            self.ui.notebook.removeTab(found_idx)

        # HACK: the content was removed but let's create it again
        self.ui.plugin_tab = QtWidgets.QWidget()
        self.ui.plugin_tab.setObjectName("plugin_tab")
        self.ui.plugin_tab_layout = QtWidgets.QVBoxLayout(self.ui.plugin_tab)
        self.ui.plugin_tab_layout.setContentsMargins(2, 2, 2, 2)
        # self.notebook.addTab(self.plugin_tab, _("Tool"))

        self.ui.plugin_scroll_area = VerticalScrollArea()
        # self.plugin_scroll_area.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.ui.plugin_tab_layout.addWidget(self.ui.plugin_scroll_area)

    # def on_close_notebook_tab(self):
    # self.tool_shapes.clear(update=True)

    def on_gui_coords_clicked(self):
        self.distance_tool.run(toggle=True)

    def on_flipy(self):
        """
        Executed when the menu entry in Options -> Flip on Y axis is clicked.

        :return:
        """
        self.defaults.report_usage("on_flipy()")

        obj_list = self.collection.get_selected()
        xminlist = []
        yminlist = []
        xmaxlist = []
        ymaxlist = []

        if not obj_list:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
        else:
            try:
                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)
                    xmaxlist.append(xmax)
                    ymaxlist.append(ymax)

                # get the minimum x,y and maximum x,y for all objects selected
                xminimal = min(xminlist)
                yminimal = min(yminlist)
                xmaximal = max(xmaxlist)
                ymaximal = max(ymaxlist)

                px = 0.5 * (xminimal + xmaximal)
                py = 0.5 * (yminimal + ymaximal)

                # execute mirroring
                for obj in obj_list:
                    obj.mirror('X', [px, py])
                    obj.plot()
                    self.app_obj.object_changed.emit(obj)
                self.inform.emit('[success] %s.' % _("Flip on Y axis done"))
            except Exception as e:
                self.inform.emit('[ERROR_NOTCL] %s: %s.' % (_("Action was not executed"), str(e)))
                return

    def on_flipx(self):
        """
        Executed when the menu entry in Options -> Flip on X axis is clicked.

        :return:
        """

        self.defaults.report_usage("on_flipx()")

        obj_list = self.collection.get_selected()
        xminlist = []
        yminlist = []
        xmaxlist = []
        ymaxlist = []

        if not obj_list:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
        else:
            try:
                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)
                    xmaxlist.append(xmax)
                    ymaxlist.append(ymax)

                # get the minimum x,y and maximum x,y for all objects selected
                xminimal = min(xminlist)
                yminimal = min(yminlist)
                xmaximal = max(xmaxlist)
                ymaximal = max(ymaxlist)

                px = 0.5 * (xminimal + xmaximal)
                py = 0.5 * (yminimal + ymaximal)

                # execute mirroring
                for obj in obj_list:
                    obj.mirror('Y', [px, py])
                    obj.plot()
                    self.app_obj.object_changed.emit(obj)
                self.inform.emit('[success] %s.' % _("Flip on X axis done"))
            except Exception as e:
                self.inform.emit('[ERROR_NOTCL] %s: %s.' % (_("Action was not executed"), str(e)))
                return

    def on_rotate(self, silent=False, preset=None):
        """
        Executed when Options -> Rotate Selection menu entry is clicked.

        :param silent:  If silent is True then use the preset value for the angle of the rotation.
        :param preset:  A value to be used as predefined angle for rotation.
        :return:
        """
        self.defaults.report_usage("on_rotate()")

        obj_list = self.collection.get_selected()
        xminlist = []
        yminlist = []
        xmaxlist = []
        ymaxlist = []

        if not obj_list:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
        else:
            if silent is False:
                rotatebox = FCInputDoubleSpinner(title=_("Transform"), text=_("Enter the Angle value:"),
                                                 min=-360, max=360, decimals=4,
                                                 init_val=float(self.options['tools_transform_rotate']),
                                                 parent=self.ui)
                rotatebox.setWindowIcon(QtGui.QIcon(self.resource_location + '/rotate.png'))

                num, ok = rotatebox.get_value()
            else:
                num = preset
                ok = True

            if ok:
                try:
                    # first get a bounding box to fit all
                    for obj in obj_list:
                        xmin, ymin, xmax, ymax = obj.bounds()
                        xminlist.append(xmin)
                        yminlist.append(ymin)
                        xmaxlist.append(xmax)
                        ymaxlist.append(ymax)

                    # get the minimum x,y and maximum x,y for all objects selected
                    xminimal = min(xminlist)
                    yminimal = min(yminlist)
                    xmaximal = max(xmaxlist)
                    ymaximal = max(ymaxlist)
                    px = 0.5 * (xminimal + xmaximal)
                    py = 0.5 * (yminimal + ymaximal)

                    for sel_obj in obj_list:
                        sel_obj.rotate(-float(num), point=(px, py))
                        sel_obj.plot()
                        self.app_obj.object_changed.emit(sel_obj)
                    self.inform.emit('[success] %s' % _("Rotation done."))
                except Exception as e:
                    self.inform.emit('[ERROR_NOTCL] %s: %s' % (_("Rotation movement was not executed."), str(e)))
                    return

    def on_skewx(self):
        """
        Executed when the menu entry in Options -> Skew on X axis is clicked.

        :return:
        """

        self.defaults.report_usage("on_skewx()")

        obj_list = self.collection.get_selected()
        xminlist = []
        yminlist = []

        if not obj_list:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
        else:
            skewxbox = FCInputDoubleSpinner(title=_("Transform"), text=_("Enter the Angle value:"),
                                            min=-360, max=360, decimals=4,
                                            init_val=float(self.options['tools_transform_skew_x']),
                                            parent=self.ui)
            skewxbox.setWindowIcon(QtGui.QIcon(self.resource_location + '/skewX.png'))

            num, ok = skewxbox.get_value()
            if ok:
                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)

                # get the minimum x,y and maximum x,y for all objects selected
                xminimal = min(xminlist)
                yminimal = min(yminlist)

                for obj in obj_list:
                    obj.skew(num, 0, point=(xminimal, yminimal))

                    # make sure to update the Offset field in Properties Tab
                    try:
                        obj.set_offset_values()
                    except AttributeError:
                        # not all objects have this attribute
                        pass

                    obj.plot()
                    self.app_obj.object_changed.emit(obj)
                self.inform.emit('[success] %s' % _("Skew on X axis done."))

    def on_skewy(self):
        """
        Executed when the menu entry in Options -> Skew on Y axis is clicked.

        :return:
        """

        self.defaults.report_usage("on_skewy()")

        obj_list = self.collection.get_selected()
        xminlist = []
        yminlist = []

        if not obj_list:
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
        else:
            skewybox = FCInputDoubleSpinner(title=_("Transform"), text=_("Enter the Angle value:"),
                                            min=-360, max=360, decimals=4,
                                            init_val=float(self.options['tools_transform_skew_y']),
                                            parent=self.ui)
            skewybox.setWindowIcon(QtGui.QIcon(self.resource_location + '/skewY.png'))

            num, ok = skewybox.get_value()
            if ok:
                # first get a bounding box to fit all
                for obj in obj_list:
                    xmin, ymin, xmax, ymax = obj.bounds()
                    xminlist.append(xmin)
                    yminlist.append(ymin)

                # get the minimum x,y and maximum x,y for all objects selected
                xminimal = min(xminlist)
                yminimal = min(yminlist)

                for obj in obj_list:
                    obj.skew(0, num, point=(xminimal, yminimal))

                    # make sure to update the Offset field in Properties Tab
                    try:
                        obj.set_offset_values()
                    except AttributeError:
                        # not all objects have this attribute
                        pass

                    obj.plot()
                    self.app_obj.object_changed.emit(obj)
                self.inform.emit('[success] %s' % _("Skew on Y axis done."))

    def on_plots_updated(self):
        """
        Callback used to report when the plots have changed.
        Adjust axes and zooms to fit.

        :return: None
        """
        self.plotcanvas.update() if self.use_3d_engine else self.plotcanvas.auto_adjust_axes()
        self.on_zoom_fit()
        self.collection.update_view()

    def on_toolbar_replot(self):
        """
        Callback for toolbar button. Re-plots all objects.

        :return: None
        """

        try:
            obj = self.collection.get_active()
            obj.read_form() if obj else self.on_zoom_fit()
        except Exception as e:
            self.log.debug("on_toolbar_replot() -> %s" % str(e))

        self.plot_all()

    def grid_status(self):
        return True if self.ui.grid_snap_btn.isChecked() else False

    def populate_cmenu_grids(self):
        units = self.app_units.lower()

        # for act in self.ui.cmenu_gridmenu.actions():
        #     act.triggered.disconnect()
        self.ui.cmenu_gridmenu.clear()

        sorted_list = sorted(self.options["global_grid_context_menu"][str(units)])

        grid_toggle = self.ui.cmenu_gridmenu.addAction(QtGui.QIcon(self.resource_location + '/grid32_menu.png'),
                                                       _("Grid On/Off"))
        grid_toggle.setCheckable(True)
        grid_toggle.setChecked(True) if self.grid_status() else grid_toggle.setChecked(False)

        self.ui.cmenu_gridmenu.addSeparator()
        for grid in sorted_list:
            action = self.ui.cmenu_gridmenu.addAction(QtGui.QIcon(self.resource_location + '/grid32_menu.png'),
                                                      "%s" % str(grid))
            action.triggered.connect(self.set_grid)

        self.ui.cmenu_gridmenu.addSeparator()
        grid_add = self.ui.cmenu_gridmenu.addAction(QtGui.QIcon(self.resource_location + '/plus32.png'),
                                                    _("Add"))
        grid_delete = self.ui.cmenu_gridmenu.addAction(QtGui.QIcon(self.resource_location + '/delete32.png'),
                                                       _("Delete"))
        grid_add.triggered.connect(self.on_grid_add)
        grid_delete.triggered.connect(self.on_grid_delete)
        grid_toggle.triggered.connect(lambda: self.ui.grid_snap_btn.trigger())

    def set_grid(self):
        menu_action = self.sender()
        assert isinstance(menu_action, QtGui.QAction), "Expected QAction got %s" % type(menu_action)

        self.ui.grid_gap_x_entry.setText(menu_action.text())
        self.ui.grid_gap_y_entry.setText(menu_action.text())

    def on_grid_add(self):
        # ## Current application units in lower Case
        units = self.app_units.lower()

        grid_add_popup = FCInputDoubleSpinner(title=_("New Grid ..."),
                                              text=_('Enter a Grid Value:'),
                                              min=0.0000, max=99.9999, decimals=self.decimals,
                                              parent=self.ui)
        grid_add_popup.setWindowIcon(QtGui.QIcon(self.resource_location + '/plus32.png'))

        val, ok = grid_add_popup.get_value()
        if ok:
            if float(val) == 0:
                self.inform.emit('[WARNING_NOTCL] %s' %
                                 _("Please enter a grid value with non-zero value, in Float format."))
                return
            else:
                if val not in self.options["global_grid_context_menu"][str(units)]:
                    self.options["global_grid_context_menu"][str(units)].append(val)
                    self.inform.emit('[success] %s...' % _("New Grid added"))
                else:
                    self.inform.emit('[WARNING_NOTCL] %s...' % _("Grid already exists"))
        else:
            self.inform.emit('[WARNING_NOTCL] %s...' % _("Adding New Grid cancelled"))

    def on_grid_delete(self):
        # ## Current application units in lower Case
        units = self.app_units.lower()

        grid_del_popup = FCInputDoubleSpinner(title="Delete Grid ...",
                                              text='Enter a Grid Value:',
                                              min=0.0000, max=99.9999, decimals=self.decimals,
                                              parent=self.ui)
        grid_del_popup.setWindowIcon(QtGui.QIcon(self.resource_location + '/delete32.png'))

        val, ok = grid_del_popup.get_value()
        if ok:
            if float(val) == 0:
                self.inform.emit('[WARNING_NOTCL] %s' %
                                 _("Please enter a grid value with non-zero value, in Float format."))
                return
            else:
                try:
                    self.options["global_grid_context_menu"][str(units)].remove(val)
                except ValueError:
                    self.inform.emit('[ERROR_NOTCL]%s...' % _("Grid Value does not exist"))
                    return
                self.inform.emit('[success] %s...' % _("Grid Value deleted"))
        else:
            self.inform.emit('[WARNING_NOTCL] %s...' % _("Delete Grid value cancelled"))

    def on_copy_name(self):
        self.defaults.report_usage("on_copy_name()")

        obj = self.collection.get_active()
        try:
            name = obj.obj_options["name"]
        except AttributeError:
            self.log.debug("on_copy_name() --> No object selected to copy it's name")
            self.inform.emit('[WARNING_NOTCL] %s' % _("No object is selected."))
            return

        self.clipboard.setText(name)
        self.inform.emit(_("Name copied to clipboard ..."))

    def on_mouse_click_over_plot(self, event):
        """
        Default actions are:
        :param event: Contains information about the event, like which button
            was clicked, the pixel coordinates and the axes coordinates.
        :return: None
        """
        event_pos = event.pos if self.use_3d_engine else (event.xdata, event.ydata)
        pos_canvas = self.plotcanvas.translate_coords(event_pos)

        # So it can receive key presses
        self.plotcanvas.native.setFocus()

        if self.grid_status():
            pos = self.geo_editor.snap(pos_canvas[0], pos_canvas[1])
        else:
            pos = (pos_canvas[0], pos_canvas[1])

        self.mouse_click_pos = [pos[0], pos[1]]

        try:
            if event.button == 1:
                # Reset here the relative coordinates so there is a new reference on the click position
                if self.rel_point1 is None:
                    self.rel_point1 = self.mouse_click_pos
                else:
                    self.rel_point2 = copy(self.rel_point1)
                    self.rel_point1 = self.mouse_click_pos

            self.on_mouse_move_over_plot(event, origin_click=True)
        except Exception as e:
            self.log.error("App.on_mouse_click_over_plot() --> Outside plot? --> %s" % str(e))

    def on_mouse_double_click_over_plot(self, event):
        if event.button == 1:
            self.doubleclick = True

    def on_mouse_move_over_plot(self, event, origin_click=None):
        """
        Callback for the mouse motion event over the plot.

        :param event:           Contains information about the event.
        :param origin_click:
        :return:                None
        """

        if self.use_3d_engine:
            event_pos = event.pos
            pan_button = 2 if self.options["global_pan_button"] == '2' else 3
            self.event_is_dragging = event.is_dragging
        else:
            event_pos = (event.xdata, event.ydata)
            # Matplotlib has the middle and right buttons mapped in reverse compared with VisPy
            pan_button = 3 if self.options["global_pan_button"] == '2' else 2
            self.event_is_dragging = self.plotcanvas.is_dragging

        # So it can receive key presses but not when the Tcl Shell is active
        if not self.ui.shell_dock.isVisible():
            if not self.plotcanvas.native.hasFocus():
                self.plotcanvas.native.setFocus()

        self.pos_jump = event_pos
        self.ui.popMenu.mouse_is_panning = False

        self.on_plugin_mouse_move(pos=event_pos)

        if origin_click is None:
            # if the RMB is clicked and mouse is moving over plot then 'panning_action' is True
            if event.button == pan_button and self.event_is_dragging == 1:

                # if a popup menu is active don't change mouse_is_panning variable because is not True
                if self.ui.popMenu.popup_active:
                    self.ui.popMenu.popup_active = False
                    return
                self.ui.popMenu.mouse_is_panning = True
                return

        if self.rel_point1 is not None:
            try:  # May fail in case mouse not within axes
                pos_canvas = self.plotcanvas.translate_coords(event_pos)

                if pos_canvas[0] is None or pos_canvas[1] is None:
                    return

                if self.grid_status():
                    pos = self.geo_editor.snap(pos_canvas[0], pos_canvas[1])

                    # Update cursor
                    self.app_cursor.set_data(np.asarray([(pos[0], pos[1])]),
                                             symbol='++', edge_color=self.plotcanvas.cursor_color,
                                             edge_width=self.options["global_cursor_width"],
                                             size=self.options["global_cursor_size"])
                else:
                    pos = (pos_canvas[0], pos_canvas[1])

                self.dx = pos[0] - float(self.rel_point1[0])
                self.dy = pos[1] - float(self.rel_point1[1])

                self.ui.update_location_labels(self.dx, self.dy, pos[0], pos[1])
                self.plotcanvas.on_update_text_hud(self.dx, self.dy, pos[0], pos[1])

                self.mouse_pos = [pos[0], pos[1]]

                if self.options['global_selection_shape'] is False:
                    self.selection_type = None
                    return

                # the object selection on canvas does not work for App Tools or for Editors
                if self.call_source != 'app':
                    self.selection_type = None
                    return

                # if the mouse is moved and the LMB is clicked then the action is a selection
                if self.event_is_dragging == 1 and event.button == 1:
                    self.delete_selection_shape()
                    if self.dx < 0:
                        self.draw_moving_selection_shape(self.mouse_click_pos, self.mouse_pos,
                                                         color=self.options['global_alt_sel_line'],
                                                         face_color=self.options['global_alt_sel_fill'])
                        self.selection_type = False
                    elif self.dx >= 0:
                        self.draw_moving_selection_shape(self.mouse_click_pos, self.mouse_pos)
                        self.selection_type = True
                    else:
                        self.selection_type = None
                else:
                    self.selection_type = None

                # hover effect - enabled in Preferences -> General -> appGUI Settings
                if self.options['global_hover_shape']:
                    for obj in self.collection.get_list():
                        try:
                            # select the object(s) only if it is enabled (plotted)
                            if obj.obj_options['plot']:
                                if obj not in self.collection.get_selected():
                                    poly_obj = Polygon(
                                        [(obj.obj_options['xmin'], obj.obj_options['ymin']),
                                         (obj.obj_options['xmax'], obj.obj_options['ymin']),
                                         (obj.obj_options['xmax'], obj.obj_options['ymax']),
                                         (obj.obj_options['xmin'], obj.obj_options['ymax'])]
                                    )
                                    if Point(pos).within(poly_obj):
                                        if obj.isHovering is False:
                                            obj.isHovering = True
                                            obj.notHovering = True
                                            # create the selection box around the selected object
                                            self.draw_hover_shape(obj, color='#d1e0e0FF')
                                    else:
                                        if obj.notHovering is True:
                                            obj.notHovering = False
                                            obj.isHovering = False
                                            self.delete_hover_shape()
                        except Exception:
                            # the Exception here will happen if we try to select on screen, and we have a
                            # newly (and empty) just created Geometry or Excellon object that do not have the
                            # xmin, xmax, ymin, ymax options.
                            # In this case poly_obj creation (see above) will fail
                            pass

            except Exception as e:
                self.log.error("App.on_mouse_move_over_plot() - rel_point1 is not None -> %s" % str(e))
                # self.ui.position_label.setText("")
                # self.ui.rel_position_label.setText("")
                self.ui.update_location_labels(0.0, 0.0, 0.0, 0.0)
                self.mouse_pos = [None, None]

    def on_mouse_click_release_over_plot(self, event):
        """
        Callback for the mouse click release over plot. This event is generated by the Matplotlib backend
        and has been registered in ''self.__init__()''.
        :param event: contains information about the event.
        :return:
        """

        if self.use_3d_engine:
            event_pos = event.pos
            right_button = 2
        else:
            event_pos = (event.xdata, event.ydata)
            # Matplotlib has the middle and right buttons mapped in reverse compared with VisPy
            right_button = 3

        pos_canvas = self.plotcanvas.translate_coords(event_pos)
        if self.grid_status():
            try:
                pos = self.geo_editor.snap(pos_canvas[0], pos_canvas[1])
            except TypeError:
                return
        else:
            pos = (pos_canvas[0], pos_canvas[1])

        # if the released mouse button was RMB then test if it was a panning motion or not, if not it was a context
        # canvas menu
        if event.button == right_button and self.ui.popMenu.mouse_is_panning is False:  # right click
            self.on_mouse_context_menu()

        # if the released mouse button was LMB then test if we had a right-to-left selection or a left-to-right
        # selection and then select a type of selection ("enclosing" or "touching")

        if event.button == 1:  # left click
            key_modifier = QtWidgets.QApplication.keyboardModifiers()
            shift_modifier_key = QtCore.Qt.KeyboardModifier.ShiftModifier
            ctrl_modifier_key = QtCore.Qt.KeyboardModifier.ControlModifier
            ctrl_shift_modifier_key = ctrl_modifier_key | shift_modifier_key

            # this will do click release action for the Plugins
            if key_modifier == shift_modifier_key or key_modifier == ctrl_shift_modifier_key:
                self.on_mouse_and_key_modifiers(position=self.mouse_click_pos, modifiers=key_modifier)
                self.on_plugin_mouse_click_release(pos=pos)
                self.mouse_click_pos = [pos[0], pos[1]]
                return
            else:
                self.on_plugin_mouse_click_release(pos=pos)

            # the object selection on canvas will not work for App Tools or for Editors
            if self.call_source != 'app':
                self.mouse_click_pos = [pos[0], pos[1]]
                return

            # it was a double click
            if self.doubleclick is True:
                self.doubleclick = False
                if self.collection.get_selected():
                    self.ui.notebook.setCurrentWidget(self.ui.properties_tab)
                    if self.ui.splitter.sizes()[0] == 0:
                        self.ui.splitter.setSizes([1, 1])
                    try:
                        # delete the selection shape(S) as it may be in the way
                        self.delete_selection_shape()
                        self.delete_hover_shape()
                    except Exception as e:
                        self.log.error("App.on_mouse_click_release_over_plot() double click --> Error: %s" % str(e))
                self.mouse_click_pos = [pos[0], pos[1]]
                return

            # WORKAROUND for LEGACY MODE
            if self.use_3d_engine is False:
                # if there is no move on canvas then we have no dragging selection
                if self.dx == 0 or self.dy == 0:
                    self.selection_type = None

            # End moving selection
            if self.selection_type is not None:
                # delete previous selection shape
                self.delete_selection_shape()

                try:
                    self.selection_area_handler(self.mouse_click_pos, pos, self.selection_type)
                    self.selection_type = None
                except Exception as e:
                    self.log.error("App.on_mouse_click_release_over_plot() select area --> Error: %s" % str(e))
                    self.mouse_click_pos = [pos[0], pos[1]]
                return

            if key_modifier == shift_modifier_key:
                mod_key = 'Shift'
            elif key_modifier == ctrl_modifier_key:
                mod_key = 'Control'
            else:
                mod_key = None

            try:
                if self.command_active is None:
                    if mod_key == self.options["global_mselect_key"]:
                        # If the modifier key is pressed when the LMB is clicked then if the object is selected it will
                        # deselect, and if it's not selected then it will be selected
                        self.select_objects(key='multisel')
                    else:
                        # If there is no active command (self.command_active is None) then we check if
                        # we clicked on an object by checking the bounding limits against mouse click position
                        self.select_objects()

                    self.delete_hover_shape()
            except Exception as e:
                self.log.error("App.on_mouse_click_release_over_plot() select click --> Error: %s" % str(e))
                self.mouse_click_pos = [pos[0], pos[1]]
                return

        self.mouse_click_pos = [pos[0], pos[1]]

    def on_mouse_and_key_modifiers(self, position, modifiers):
        """
        Called when the mouse is left-clicked on canvas and simultaneously a key modifier
        (Ctrl, AAlt, Shift) is pressed.

        :param position:        A tupple made of the clicked position x, y coordinates
        :param modifiers:       Key modifiers (Ctrl, Alt, Shift or a combination of them)
        :return:
        """

        # If the SHIFT key is pressed when LMB is clicked then the coordinates are copied to clipboard
        if modifiers == QtCore.Qt.KeyboardModifier.ShiftModifier:
            # do not auto open the Project Tab
            self.click_noproject = True

            self.clipboard.setText(self.options["global_point_clipboard_format"] %
                                   (self.decimals, position[0], self.decimals, position[1]))
            self.inform.emit('[success] %s' % _("Copied to clipboard."))
        elif modifiers == QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.ShiftModifier:
            try:
                old_clipb = eval(self.clipboard.text())
            except Exception:
                # self.log.error("App.on_mouse_and_key_modifiers() --> %s" % str(err))
                old_clipb = None

            clip_pos_val = (
                self.dec_format(position[0], self.decimals),
                self.dec_format(position[1], self.decimals)
            )
            clip_text = "(%s, %s)" % (str(clip_pos_val[0]), str(clip_pos_val[1]))

            if old_clipb is None or old_clipb == '':
                self.clipboard.setText(clip_text)
            else:
                if isinstance(old_clipb, list):
                    old_clipb.append(clip_pos_val)
                else:
                    old_clipb = [old_clipb, clip_pos_val]
                self.clipboard.setText(str(old_clipb))
            self.inform.emit('[success] %s' % _("Copied to clipboard."))

    def on_mouse_context_menu(self):
        """
        Display a context menu when mouse right-clicking on canvas.

        :return:
        """
        if self.inhibit_context_menu is False:
            self.cursor = QtGui.QCursor()
            self.populate_cmenu_grids()
            self.ui.popMenu.popup(self.cursor.pos())

            # if at least one object is Gerber or Excellon enable color changes
            sel_obj_list = self.collection.get_selected()
            self.ui.pop_menucolor.setDisabled(True)
            if sel_obj_list:
                self.ui.popmenu_copy.setDisabled(False)
                self.ui.popmenu_delete.setDisabled(False)
                self.ui.popmenu_edit.setDisabled(False)

                self.ui.popmenu_numeric_move.setDisabled(False)
                self.ui.popmenu_move2origin.setDisabled(False)
                self.ui.popmenu_move.setDisabled(False)
                for obj in sel_obj_list:
                    if obj.kind in ["gerber", "excellon"]:
                        self.ui.pop_menucolor.setDisabled(False)
                        break
            else:
                self.ui.popmenu_copy.setDisabled(True)
                self.ui.popmenu_delete.setDisabled(True)
                self.ui.popmenu_edit.setDisabled(True)

                self.ui.popmenu_numeric_move.setDisabled(True)
                self.ui.popmenu_move2origin.setDisabled(True)
                self.ui.popmenu_move.setDisabled(True)

    @property
    def mouse_click_pos(self) -> list[float]:
        return [self._mouse_click_pos[0], self._mouse_click_pos[1]]

    @mouse_click_pos.setter
    def mouse_click_pos(self, m_pos: Union[list[float], tuple[float]]):
        self._mouse_click_pos = m_pos

    @property
    def mouse_pos(self) -> list[float]:
        return [self._mouse_pos[0], self._mouse_pos[1]]

    @mouse_pos.setter
    def mouse_pos(self, m_pos: Union[list[float], tuple[float]]):
        self._mouse_pos = m_pos

    def selection_area_handler(self, start_pos, end_pos, sel_type):
        """
        Called when the mouse selects by dragging left mouse button on canvas.

        :param start_pos:   mouse position when the selection LMB click was done
        :param end_pos:     mouse position when the left mouse button is released
        :param sel_type:    if True it's a left to right selection (enclosure), if False it's a 'touch' selection
        :return:            None
        """
        # delete previous selection shape
        self.delete_selection_shape()

        poly_selection = Polygon([start_pos, (end_pos[0], start_pos[1]), end_pos, (start_pos[0], end_pos[1])])

        # make all objects inactive
        self.collection.set_all_inactive()

        for obj in self.collection.get_list():
            try:
                # select the object(s) only if it is enabled (plotted)
                if obj.obj_options['plot']:
                    # it's a line without area
                    if obj.obj_options['xmin'] == obj.obj_options['xmax'] or \
                            obj.obj_options['ymin'] == obj.obj_options['ymax']:
                        poly_obj = unary_union(obj.solid_geometry).buffer(0.001)
                    # it's a geometry with area
                    else:
                        poly_obj = Polygon([(obj.obj_options['xmin'], obj.obj_options['ymin']),
                                            (obj.obj_options['xmax'], obj.obj_options['ymin']),
                                            (obj.obj_options['xmax'], obj.obj_options['ymax']),
                                            (obj.obj_options['xmin'], obj.obj_options['ymax'])])
                    if poly_obj.is_empty or not poly_obj.is_valid:
                        continue

                    if sel_type is True:
                        if poly_obj.within(poly_selection):
                            # create the selection box around the selected object
                            if self.options['global_selection_shape'] is True:
                                self.draw_selection_shape(obj)
                            self.collection.set_active(obj.obj_options['name'])
                    else:
                        if poly_selection.intersects(poly_obj):
                            # create the selection box around the selected object
                            if self.options['global_selection_shape'] is True:
                                self.draw_selection_shape(obj)
                            self.collection.set_active(obj.obj_options['name'])
                    obj.selection_shape_drawn = True
            except Exception as e:
                # the Exception here will happen if we try to select on screen, and we have a newly (and empty)
                # just created Geometry or Excellon object that do not have the xmin, xmax, ymin, ymax options.
                # In this case poly_obj creation (see above) will fail
                self.log.error("App.selection_area_handler() --> %s" % str(e))

    def select_objects(self, key=None):
        """
        Will select objects clicked on canvas

        :param key:     a keyboard key. for future use in cumulative selection
        :return:        None
        """

        # list where we store the overlapped objects under our mouse left click position
        if key is None:
            self.objects_under_the_click_list = []

        # Populate the list with the overlapped objects on the click position
        curr_x, curr_y = self.mouse_click_pos

        try:
            for obj in self.all_objects_list:
                # ScriptObject and DocumentObject objects can't be selected
                if obj.kind == 'script' or obj.kind == 'document':
                    continue

                if key == 'multisel' and obj.obj_options['name'] in self.objects_under_the_click_list:
                    continue

                if (curr_x >= obj.obj_options['xmin']) and (curr_x <= obj.obj_options['xmax']) and \
                        (curr_y >= obj.obj_options['ymin']) and (curr_y <= obj.obj_options['ymax']):
                    if obj.obj_options['name'] not in self.objects_under_the_click_list:
                        if obj.obj_options['plot']:
                            # add objects to the objects_under_the_click list only if the object is plotted
                            # (active and not disabled)
                            self.objects_under_the_click_list.append(obj.obj_options['name'])
        except Exception as e:
            self.log.error(
                "Something went bad in App.select_objects(). Create a list of objects under click pos%s" % str(e))

        if self.objects_under_the_click_list:
            curr_sel_obj = self.collection.get_active()
            # case when there is only an object under the click, and we toggle it
            if len(self.objects_under_the_click_list) == 1:
                try:
                    if curr_sel_obj is None:
                        self.collection.set_active(self.objects_under_the_click_list[0])
                        curr_sel_obj = self.collection.get_active()

                        # create the selection box around the selected object
                        if self.options['global_selection_shape'] is True:
                            self.draw_selection_shape(curr_sel_obj)
                            curr_sel_obj.selection_shape_drawn = True
                    elif curr_sel_obj.obj_options['name'] not in self.objects_under_the_click_list:
                        self.collection.on_objects_selection(False)
                        self.delete_selection_shape()
                        curr_sel_obj.selection_shape_drawn = False

                        self.collection.set_active(self.objects_under_the_click_list[0])
                        curr_sel_obj = self.collection.get_active()
                        # create the selection box around the selected object
                        if self.options['global_selection_shape'] is True:
                            self.draw_selection_shape(curr_sel_obj)
                            curr_sel_obj.selection_shape_drawn = True
                        self.selected_message(curr_sel_obj=curr_sel_obj)
                    elif curr_sel_obj.selection_shape_drawn is False:
                        if self.options['global_selection_shape'] is True:
                            self.draw_selection_shape(curr_sel_obj)
                            curr_sel_obj.selection_shape_drawn = True
                    else:
                        self.collection.on_objects_selection(False)
                        self.delete_selection_shape()
                        if self.call_source != 'app':
                            self.call_source = 'app'
                    self.selected_message(curr_sel_obj=curr_sel_obj)
                except Exception as e:
                    self.log.error("Something went bad in App.select_objects(). Single click selection. %s" % str(e))
            else:
                # If there is no selected object
                try:
                    # make active the first element of the overlapped objects list
                    if self.collection.get_active() is None:
                        self.collection.set_active(self.objects_under_the_click_list[0])
                        self.collection.get_by_name(self.objects_under_the_click_list[0]).selection_shape_drawn = True

                    name_sel_obj = self.collection.get_active().obj_options['name']
                    # In case that there is a selected object, but it is not in the overlapped object list
                    # make that object inactive and activate the first element in the overlapped object list
                    if name_sel_obj not in self.objects_under_the_click_list:
                        self.collection.set_inactive(name_sel_obj)
                        name_sel_obj = self.objects_under_the_click_list[0]
                        self.collection.set_active(name_sel_obj)
                    else:
                        sel_idx = self.objects_under_the_click_list.index(name_sel_obj)
                        self.collection.set_all_inactive()
                        self.collection.set_active(
                            self.objects_under_the_click_list[(sel_idx + 1) % len(self.objects_under_the_click_list)])

                    curr_sel_obj = self.collection.get_active()
                    # delete the possible selection box around a possible selected object
                    self.delete_selection_shape()
                    curr_sel_obj.selection_shape_drawn = False

                    # create the selection box around the selected object
                    if self.options['global_selection_shape'] is True:
                        self.draw_selection_shape(curr_sel_obj)
                        curr_sel_obj.selection_shape_drawn = True
                    self.selected_message(curr_sel_obj=curr_sel_obj)
                except Exception as e:
                    self.log.error(
                        "Something went bad in App.select_objects(). Cycle the objects under cursor. %s" % str(e))
        else:
            try:
                # deselect everything
                self.collection.on_objects_selection(False)
                # delete the possible selection box around a possible selected object
                self.delete_selection_shape()

                for o in self.collection.get_list():
                    o.selection_shape_drawn = False

                # and as a convenience move the focus to the Project tab because Selected tab is now empty but
                # only when working on App
                if self.call_source == 'app':
                    if self.click_noproject is False:
                        # if the Tool Tab is in focus don't change focus to Project Tab
                        if not self.ui.notebook.currentWidget() is self.ui.plugin_tab:
                            self.ui.notebook.setCurrentWidget(self.ui.project_tab)
                    else:
                        # restore auto open the Project Tab
                        self.click_noproject = False

                    # delete any text in the status bar, implicitly the last object name that was selected
                    # self.inform.emit("")
                else:
                    self.call_source = 'app'
            except Exception as e:
                self.log.error("Something went bad in App.select_objects(). Deselect everything. %s" % str(e))

    def selected_message(self, curr_sel_obj):
        """
        Will print a colored message on status bar when the user selects an object on canvas.

        :param curr_sel_obj:    Application object that have geometry: Geometry, Gerber, Excellon, CNCJob
        :type curr_sel_obj:
        :return:
        :rtype:
        """
        if curr_sel_obj:
            if curr_sel_obj.kind == 'gerber':
                self.inform.emit('[selected] <span style="color:{color};">{name}</span> {tx}'.format(
                    color='green',
                    name=str(curr_sel_obj.obj_options['name']),
                    tx=_("selected"))
                )
            elif curr_sel_obj.kind == 'excellon':
                self.inform.emit('[selected] <span style="color:{color};">{name}</span> {tx}'.format(
                    color='brown',
                    name=str(curr_sel_obj.obj_options['name']),
                    tx=_("selected"))
                )
            elif curr_sel_obj.kind == 'cncjob':
                self.inform.emit('[selected] <span style="color:{color};">{name}</span> {tx}'.format(
                    color='blue',
                    name=str(curr_sel_obj.obj_options['name']),
                    tx=_("selected"))
                )
            elif curr_sel_obj.kind == 'geometry':
                self.inform.emit('[selected] <span style="color:{color};">{name}</span> {tx}'.format(
                    color='red',
                    name=str(curr_sel_obj.obj_options['name']),
                    tx=_("selected"))
                )

    def on_plugin_mouse_click_release(self, pos):
        """
        Handle specific tasks in the Plugins for the mouse click release

        :param pos:     mouse position
        :type pos:
        :return:
        """

        if self.ui.notebook.currentWidget().objectName() != "plugin_tab":
            return

        tab_idx = self.ui.notebook.currentIndex()
        for plugin in self.app_plugins:
            try:
                # execute this only for the current active plugin
                if self.ui.notebook.tabText(tab_idx) != plugin.pluginName:
                    continue
                try:
                    plugin.on_plugin_mouse_click_release(pos)
                except AttributeError:
                    # not all plugins have this implemented
                    # print("This does not have it", self.ui.notebook.tabText(tab_idx))
                    pass
            except AttributeError:
                pass

    def on_plugin_mouse_move(self, pos):
        """
        Handle specific tasks in the Plugins for the mouse move

        :param pos:     mouse position
        :return:
        :rtype:
        """

        if self.ui.notebook.currentWidget().objectName() != "plugin_tab":
            return

        tab_idx = self.ui.notebook.currentIndex()
        for plugin in self.app_plugins:
            # execute this only for the current active plugin
            try:
                if self.ui.notebook.tabText(tab_idx) != plugin.pluginName:
                    continue
                try:
                    plugin.on_plugin_mouse_move(pos)
                except AttributeError:
                    # not all plugins have this implemented
                    # print("This does not have it", self.ui.notebook.tabText(tab_idx))
                    pass
            except AttributeError:
                pass

    def delete_hover_shape(self):
        self.hover_shapes.clear()
        self.hover_shapes.redraw()

    def draw_hover_shape(self, sel_obj, color=None):
        """

        :param sel_obj: The object for which the hover shape must be drawn
        :param color:   The color of the hover shape
        :return:        None
        """

        pt1 = (float(sel_obj.obj_options['xmin']), float(sel_obj.obj_options['ymin']))
        pt2 = (float(sel_obj.obj_options['xmax']), float(sel_obj.obj_options['ymin']))
        pt3 = (float(sel_obj.obj_options['xmax']), float(sel_obj.obj_options['ymax']))
        pt4 = (float(sel_obj.obj_options['xmin']), float(sel_obj.obj_options['ymax']))

        hover_rect = Polygon([pt1, pt2, pt3, pt4])
        if self.app_units.upper() == 'MM':
            hover_rect = hover_rect.buffer(-0.1)
            hover_rect = hover_rect.buffer(0.2)

        else:
            hover_rect = hover_rect.buffer(-0.00393)
            hover_rect = hover_rect.buffer(0.00787)

        # if color:
        #     face = Color(color)
        #     face.alpha = 0.2
        #     outline = Color(color, alpha=0.8)
        # else:
        #     face = Color(self.options['global_sel_fill'])
        #     face.alpha = 0.2
        #     outline = self.options['global_sel_line']

        if color:
            face = color[:-2] + str(hex(int(0.2 * 255)))[2:]
            outline = color[:-2] + str(hex(int(0.8 * 255)))[2:]
        else:
            face = self.options['global_sel_fill'][:-2] + str(hex(int(0.2 * 255)))[2:]
            outline = self.options['global_sel_line']

        self.hover_shapes.add(hover_rect, color=outline, face_color=face, update=True, layer=0, tolerance=None)

        if self.use_3d_engine is False:
            self.hover_shapes.redraw()

    def delete_selection_shape(self):
        self.sel_shapes.clear()
        self.sel_shapes.redraw()

    def draw_selection_shape(self, sel_obj, color=None):
        """
        Will draw a selection shape around the selected object.

        :param sel_obj: The object for which the selection shape must be drawn
        :param color:   The color for the selection shape.
        :return:        None
        """

        if sel_obj is None:
            return

        # it's a line without area
        if sel_obj.obj_options['xmin'] == sel_obj.obj_options['xmax'] or \
                sel_obj.obj_options['ymin'] == sel_obj.obj_options['ymax']:
            sel_rect = unary_union(sel_obj.solid_geometry).buffer(0.100001)
        # it's a geometry with area
        else:
            pt1 = (float(sel_obj.obj_options['xmin']), float(sel_obj.obj_options['ymin']))
            pt2 = (float(sel_obj.obj_options['xmax']), float(sel_obj.obj_options['ymin']))
            pt3 = (float(sel_obj.obj_options['xmax']), float(sel_obj.obj_options['ymax']))
            pt4 = (float(sel_obj.obj_options['xmin']), float(sel_obj.obj_options['ymax']))

            sel_rect = Polygon([pt1, pt2, pt3, pt4])

        b_sel_rect = None
        try:
            if self.app_units.upper() == 'MM':
                b_sel_rect = sel_rect.buffer(-0.1)
                b_sel_rect = b_sel_rect.buffer(0.2)
            else:
                b_sel_rect = sel_rect.buffer(-0.00393)
                b_sel_rect = b_sel_rect.buffer(0.00787)
        except Exception:
            pass

        if b_sel_rect.is_empty or not b_sel_rect.is_valid or b_sel_rect is None:
            b_sel_rect = sel_rect

        if self.options['global_selection_shape_as_line'] is True:
            b_sel_rect = b_sel_rect.exterior

        if color:
            face = color[:-2] + str(hex(int(0.2 * 255)))[2:]
            outline = color[:-2] + str(hex(int(0.8 * 255)))[2:]
        else:
            if self.use_3d_engine:
                face = self.options['global_sel_fill'][:-2] + str(hex(int(0.2 * 255)))[2:]
                outline = self.options['global_sel_line'][:-2] + str(hex(int(0.8 * 255)))[2:]
            else:
                face = self.options['global_sel_fill'][:-2] + str(hex(int(0.4 * 255)))[2:]
                outline = self.options['global_sel_line'][:-2] + str(hex(int(1.0 * 255)))[2:]

        self.sel_objects_list.append(
            self.sel_shapes.add(b_sel_rect, color=outline, face_color=face, update=True, layer=0, tolerance=None)
        )
        if self.use_3d_engine is False:
            self.sel_shapes.redraw()

    def draw_moving_selection_shape(self, old_coords, coords, **kwargs):
        """
        Will draw a selection shape when dragging mouse on canvas.

        :param old_coords:  Old coordinates
        :param coords:      New coordinates
        :param kwargs:      Keyword arguments
        :return:
        """

        if 'color' in kwargs:
            color = kwargs['color']
        else:
            color = self.options['global_sel_line']

        if 'face_color' in kwargs:
            face_color = kwargs['face_color']
        else:
            face_color = self.options['global_sel_fill']

        if 'face_alpha' in kwargs:
            face_alpha = kwargs['face_alpha']
        else:
            face_alpha = 0.3

        x0, y0 = old_coords
        x1, y1 = coords

        pt1 = (x0, y0)
        pt2 = (x1, y0)
        pt3 = (x1, y1)
        pt4 = (x0, y1)
        sel_rect = Polygon([pt1, pt2, pt3, pt4])

        if self.options['global_selection_shape_as_line'] is True:
            sel_rect = sel_rect.exterior

        # color_t = Color(face_color)
        # color_t.alpha = face_alpha

        color_t = face_color[:-2] + str(hex(int(face_alpha * 255)))[2:]

        self.sel_shapes.add(sel_rect, color=color, face_color=color_t, update=True, layer=0, tolerance=None)
        if self.use_3d_engine is False:
            self.sel_shapes.redraw()

    def obj_properties(self):
        """
        Will launch the object Properties Tool

        :return:
        """
        sel_objs = self.collection.get_selected()
        if sel_objs:
            self.report_tool.run(toggle=True)
        else:
            # if the splitter is hidden, display it
            if self.ui.splitter.sizes()[0] == 0:
                self.ui.splitter.setSizes([1, 1])
            self.ui.notebook.setCurrentWidget(self.ui.properties_tab)

    def on_project_context_save(self):
        """
        Wrapper, will save the object function of it's type

        :return:
        """

        sel_objects = self.collection.get_selected()
        len_objects = len(sel_objects)

        cnt = 0
        if len_objects > 1:
            for o in sel_objects:
                if o.kind == 'cncjob':
                    cnt += 1

            if len_objects == cnt:
                # all selected objects are of type CNCJOB therefore we issue a multiple save
                _filter_ = self.options['cncjob_save_filters'] + \
                           ";;RML1 Files .rol (*.rol);;HPGL Files .plt (*.plt);;KNC Files .knc (*.knc)"

                dir_file_to_save = self.get_last_save_folder() + '/multi_save'

                try:
                    filename, _f = FCFileSaveDialog.get_saved_filename(
                        caption=_("Export Code ..."),
                        directory=dir_file_to_save,
                        ext_filter=_filter_
                    )
                except TypeError:
                    filename, _f = FCFileSaveDialog.get_saved_filename(
                        caption=_("Export Code ..."),
                        ext_filter=_filter_)

                path = filename.rpartition('/')[0]
                file_extension = filename.rpartition('.')[2]

                for ob in sel_objects:
                    ob.read_form()
                    fname = os.path.join(path, '%s.%s' % (ob.obj_options['name'], file_extension))
                    ob.export_gcode_handler(fname, is_gcode=True, rename_object=False)
                return

        obj = self.collection.get_active()
        if isinstance(obj, GeometryObject):
            self.f_handlers.on_file_export_dxf()
        elif isinstance(obj, ExcellonObject):
            self.f_handlers.on_file_save_excellon()
        elif isinstance(obj, CNCJobObject):
            obj.on_exportgcode_button_click()
        elif isinstance(obj, GerberObject):
            self.f_handlers.on_file_save_gerber()
        elif isinstance(obj, ScriptObject):
            self.f_handlers.on_file_save_script()
        elif isinstance(obj, DocumentObject):
            self.f_handlers.on_file_save_document()

    def obj_move(self):
        """
        Callback for the Move menu entry in various Context Menu's.

        :return:
        """

        self.defaults.report_usage("obj_move()")
        self.move_tool.run(toggle=False)

    # ###############################################################################################################
    # ### The following section has the functions that are displayed and call the Editor tab CNCJob Tab #############
    # ###############################################################################################################
    def init_code_editor(self, name):

        self.text_editor_tab = AppTextEditor(app=self, plain_text=True)

        # add the tab if it was closed
        self.ui.plot_tab_area.addTab(self.text_editor_tab, '%s' % name)
        self.text_editor_tab.setObjectName('text_editor_tab')

        # delete the absolute and relative position and messages in the infobar
        # self.ui.position_label.setText("")
        # self.ui.rel_position_label.setText("")
        # hide coordinates toolbars in the infobar while in DB
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        self.toggle_codeeditor = True
        self.text_editor_tab.code_editor.completer_enable = False
        self.text_editor_tab.buttonRun.hide()

        # make sure to keep a reference to the code editor
        self.reference_code_editor = self.text_editor_tab.code_editor

        # Switch plot_area to CNCJob tab
        self.ui.plot_tab_area.setCurrentWidget(self.text_editor_tab)

    def on_view_source(self):
        """
        Called when the user wants to see the source file of the selected object
        :return:
        """

        try:
            obj = self.collection.get_active()
        except Exception as e:
            self.log.debug("App.on_view_source() --> %s" % str(e))
            self.inform.emit('[WARNING_NOTCL] %s' % _("Select an Gerber or Excellon file to view it's source file."))
            return 'fail'

        if obj is None:
            self.inform.emit('[WARNING_NOTCL] %s' % _("Select an Gerber or Excellon file to view it's source file."))
            return 'fail'

        self.inform.emit('%s' % _("Viewing the source code of the selected object."))
        self.proc_container.view.set_busy('%s...' % _("Loading"))

        flt = "All Files (*.*)"
        if obj.kind == 'gerber':
            flt = "Gerber Files .gbr (*.GBR);;PDF Files .pdf (*.PDF);;All Files (*.*)"
        elif obj.kind == 'excellon':
            flt = "Excellon Files .drl (*.DRL);;PDF Files .pdf (*.PDF);;All Files (*.*)"
        elif obj.kind == 'cncjob':
            flt = "GCode Files .nc (*.NC);;PDF Files .pdf (*.PDF);;All Files (*.*)"

        self.source_editor_tab = AppTextEditor(app=self, plain_text=True)

        # add the tab if it was closed
        self.ui.plot_tab_area.addTab(self.source_editor_tab, '%s' % _("Source Editor"))
        self.source_editor_tab.setObjectName('source_editor_tab')

        # delete the absolute and relative position and messages in the infobar
        # self.ui.position_label.setText("")
        # self.ui.rel_position_label.setText("")
        # hide coordinates toolbars in the infobar while in DB
        self.ui.coords_toolbar.hide()
        self.ui.delta_coords_toolbar.hide()

        self.source_editor_tab.code_editor.completer_enable = False
        self.source_editor_tab.buttonRun.hide()

        # Switch plot_area to CNCJob tab
        self.ui.plot_tab_area.setCurrentWidget(self.source_editor_tab)

        try:
            self.source_editor_tab.buttonOpen.clicked.disconnect()
        except TypeError:
            pass
        self.source_editor_tab.buttonOpen.clicked.connect(lambda: self.source_editor_tab.handleOpen(filt=flt))

        try:
            self.source_editor_tab.buttonSave.clicked.disconnect()
        except TypeError:
            pass
        self.source_editor_tab.buttonSave.clicked.connect(lambda: self.source_editor_tab.handleSaveGCode(filt=flt))

        # then append the text from GCode to the text editor
        if obj.kind == 'cncjob':
            try:
                file = obj.export_gcode(to_file=True)
                if file == 'fail':
                    return 'fail'
            except AttributeError:
                self.inform.emit('[WARNING_NOTCL] %s' %
                                 _("There is no selected object for which to see it's source file code."))
                return 'fail'
        else:
            try:
                file = StringIO(obj.source_file)
            except (AttributeError, TypeError):
                self.inform.emit('[WARNING_NOTCL] %s' %
                                 _("There is no selected object for which to see it's source file code."))
                return 'fail'

        self.source_editor_tab.t_frame.hide()
        try:
            source_text = file.getvalue()
            self.source_editor_tab.load_text(source_text, clear_text=True, move_to_start=True)
        except Exception as e:
            self.log.error('App.on_view_source() -->%s' % str(e))
            self.inform.emit('[ERROR] %s: %s' % (_('Failed to load the source code for the selected object'), str(e)))
            return

        self.source_editor_tab.t_frame.show()
        self.proc_container.view.set_idle()
        # self.ui.show()

    def on_toggle_code_editor(self):
        self.defaults.report_usage("on_toggle_code_editor()")

        if self.toggle_codeeditor is False:
            self.init_code_editor(name=_("Code Editor"))

            self.text_editor_tab.buttonOpen.clicked.disconnect()
            self.text_editor_tab.buttonOpen.clicked.connect(self.text_editor_tab.handleOpen)
            self.text_editor_tab.buttonSave.clicked.disconnect()
            self.text_editor_tab.buttonSave.clicked.connect(self.text_editor_tab.handleSaveGCode)
        else:
            for idx in range(self.ui.plot_tab_area.count()):
                if self.ui.plot_tab_area.widget(idx).objectName() == "text_editor_tab":
                    self.ui.plot_tab_area.closeTab(idx)
                    break
            self.toggle_codeeditor = False

    def on_code_editor_close(self):
        self.toggle_codeeditor = False

    def plot_all(self, fit_view=True, muted=False, use_thread=True):
        """
        Re-generates all plots from all objects.

        :param fit_view:    if True will plot the objects and will adjust the zoom to fit all plotted objects into view
        :param muted:       if True don't print messages
        :param use_thread:  if True will use threading for plotting the objects
        :return:            None
        """
        self.log.debug("Plot_all()")
        obj_collection = self.collection.get_list()
        if not obj_collection:
            return

        if muted is not True:
            self.inform[str, bool].emit('%s...' % _("Redrawing all objects"), False)

        for plot_obj in obj_collection:
            if plot_obj.obj_options['plot'] is False:
                continue

            def worker_task(obj):
                with self.proc_container.new("Plotting"):
                    if obj.kind == 'cncjob':
                        try:
                            dia = obj.ui.tooldia_entry.get_value()
                        except AttributeError:
                            dia = self.options["cncjob_tooldia"]
                        obj.plot(kind=self.options["cncjob_plot_kind"], dia=dia)
                    else:
                        obj.plot()
                    if fit_view is True:
                        self.app_obj.object_plotted.emit(obj)

            if use_thread is True:
                # Send to worker
                self.worker_task.emit({'fcn': worker_task, 'params': [plot_obj]})
            else:
                worker_task(plot_obj)

    def register_folder(self, filename):
        """
        Register the last folder used by the app to open something

        :param filename:    the last folder is extracted from the filename
        :return:            None
        """
        self.options["global_last_folder"] = os.path.split(str(filename))[0]

    def register_save_folder(self, filename):
        """
        Register the last folder used by the app to save something

        :param filename:    the last folder is extracted from the filename
        :return:            None
        """
        self.options["global_last_save_folder"] = os.path.split(str(filename))[0]

    # def set_progress_bar(self, percentage, text=""):
    #     """
    #     Set a progress bar to a value (percentage)
    #
    #     :param percentage:  Value set to the progressbar
    #     :param text:        Not used
    #     :return:            None
    #     """
    #     self.ui.progress_bar.setValue(int(percentage))

    def setup_recent_items(self):
        """
        Set up a dictionary with the recent files accessed, organized by type

        :return:
        """
        icons = {
            "gerber":   self.resource_location + "/flatcam_icon16.png",
            "excellon": self.resource_location + "/drill16.png",
            'geometry': self.resource_location + "/geometry16.png",
            "cncjob":   self.resource_location + "/cnc16.png",
            "script":   self.resource_location + "/script_new24.png",
            "document": self.resource_location + "/notes16_1.png",
            "project":  self.resource_location + "/project16.png",
            "svg":      self.resource_location + "/geometry16.png",
            "dxf":      self.resource_location + "/dxf16.png",
            "pdf":      self.resource_location + "/pdf32.png",
            "image":    self.resource_location + "/image16.png"

        }

        try:
            image_opener = self.image_tool.import_image
        except AttributeError:
            image_opener = None

        openers = {
            'gerber': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.open_gerber, 'params': [fname]}),
            'excellon': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.open_excellon, 'params': [fname]}),
            'geometry': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.import_dxf, 'params': [fname]}),
            'cncjob': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.open_gcode, 'params': [fname]}),
            "script": lambda fname: self.worker_task.emit({'fcn': self.f_handlers.open_script, 'params': [fname]}),
            "document": None,
            'project': self.f_handlers.open_project,
            'svg': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.import_svg, 'params': [fname]}),
            'dxf': lambda fname: self.worker_task.emit({'fcn': self.f_handlers.import_dxf, 'params': [fname]}),
            'image': lambda fname: self.worker_task.emit({'fcn': image_opener, 'params': [fname]}),
            'pdf': self.f_handlers.import_pdf
        }

        # Open recent file for files
        try:
            f = open(os.path.join(self.data_path, 'recent.json'))
        except IOError:
            self.log.error("Failed to load recent item list.")
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed to load recent item list."))
            return

        try:
            self.recent = json.load(f)
        except json.JSONDecodeError:
            self.log.error("Failed to parse recent item list.")
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed to parse recent item list."))
            f.close()
            return
        f.close()

        # Open recent file for projects
        try:
            fp = open(os.path.join(self.data_path, 'recent_projects.json'))
        except IOError:
            self.log.error("Failed to load recent project item list.")
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed to load recent projects item list."))
            return

        try:
            self.recent_projects = json.load(fp)
        except json.JSONDecodeError:
            self.log.error("Failed to parse recent project item list.")
            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed to parse recent project item list."))
            fp.close()
            return
        fp.close()

        # Closure needed to create callbacks in a loop.
        # Otherwise, late binding occurs.
        def make_callback(func, fname):
            def opener():
                func(fname)

            return opener

        def reset_recent_files():
            # Reset menu
            self.ui.recent.clear()
            self.recent = []
            try:
                ff = open(os.path.join(self.data_path, 'recent.json'), 'w')
            except IOError:
                self.log.error("Failed to open recent items file for writing.")
                return

            json.dump(self.recent, ff)
            self.inform.emit('%s' % _("Recent files list was reset."))

        def reset_recent_projects():
            # Reset menu
            self.ui.recent_projects.clear()
            self.recent_projects = []

            try:
                frp = open(os.path.join(self.data_path, 'recent_projects.json'), 'w')
            except IOError:
                self.log.error("Failed to open recent projects items file for writing.")
                return

            json.dump(self.recent, frp)
            self.inform.emit('%s' % _("Recent projects list was reset."))

        # Reset menu
        self.ui.recent.clear()
        self.ui.recent_projects.clear()

        # Create menu items for projects
        for recent in self.recent_projects:
            filename = recent['filename'].split('/')[-1].split('\\')[-1]

            if recent['kind'] == 'project':
                try:
                    action = QtGui.QAction(QtGui.QIcon(icons[recent["kind"]]), filename, self)

                    # Attach callback
                    o = make_callback(openers[recent["kind"]], recent['filename'])
                    action.triggered.connect(o)

                    self.ui.recent_projects.addAction(action)

                except KeyError:
                    self.log.error("Unsupported file type: %s" % recent["kind"])

        # Last action in Recent Files menu is one that Clear the content
        clear_action_proj = QtGui.QAction(QtGui.QIcon(self.resource_location + '/trash32.png'),
                                          (_("Clear Recent projects")), self)
        clear_action_proj.triggered.connect(reset_recent_projects)
        self.ui.recent_projects.addSeparator()
        self.ui.recent_projects.addAction(clear_action_proj)

        # Create menu items for files
        for recent in self.recent:
            filename = recent['filename'].split('/')[-1].split('\\')[-1]

            if recent['kind'] != 'project':
                try:
                    action = QtGui.QAction(QtGui.QIcon(icons[recent["kind"]]), filename, self)

                    # Attach callback
                    o = make_callback(openers[recent["kind"]], recent['filename'])
                    action.triggered.connect(o)

                    self.ui.recent.addAction(action)

                except KeyError:
                    self.log.error("Unsupported file type: %s" % recent["kind"])

        # Last action in Recent Files menu is one that Clear the content
        clear_action = QtGui.QAction(QtGui.QIcon(self.resource_location + '/trash32.png'),
                                     (_("Clear Recent files")), self)
        clear_action.triggered.connect(reset_recent_files)
        self.ui.recent.addSeparator()
        self.ui.recent.addAction(clear_action)

        # self.builder.get_object('open_recent').set_submenu(recent_menu)
        # self.ui.menufilerecent.set_submenu(recent_menu)
        # recent_menu.show_all()
        # self.ui.recent.show()

        self.log.debug("Recent items list has been populated.")

    def on_properties_tab_click(self):
        tab_wdg = self.ui.properties_scroll_area.widget()
        if tab_wdg and tab_wdg.objectName() == 'default_properties':
            self.setup_default_properties_tab()

    def on_notebook_tab_changed(self):
        """
        Slot for current tab changed in self.ui.notebook

        :return:
        """
        if self.ui.notebook.tabText(self.ui.notebook.currentIndex()) == _("Properties"):
            active_obj = self.collection.get_active()
            if active_obj:
                try:
                    active_obj.build_ui()
                except RuntimeError:
                    active_obj.set_ui(active_obj.ui_type(app=self))
                    active_obj.build_ui()
                except Exception:
                    self.setup_default_properties_tab()
            else:
                self.setup_default_properties_tab()

    def setup_default_properties_tab(self):
        """
        Default text for the Properties tab when is not taken by the Object UI.

        :return:
        """

        # Tree Widget
        d_properties_tw = FCTree(columns=2)
        d_properties_tw.setObjectName("default_properties")
        d_properties_tw.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        d_properties_tw.setStyleSheet("QTreeWidget {border: 0px;}")

        root = d_properties_tw.invisibleRootItem()
        font = QtGui.QFont()
        font.setBold(True)
        p_color = QtGui.QColor("#000000") if self.options['global_theme'] in ['default', 'light'] else \
            QtGui.QColor("#FFFFFF")

        # main Items categories
        general_cat = d_properties_tw.addParent(root, _('General'), expanded=True, color=p_color, font=font)
        d_properties_tw.addChild(parent=general_cat,
                                 title=['%s:' % _("Name"), '%s' % _("FlatCAM Evo")], column1=True)
        d_properties_tw.addChild(parent=general_cat,
                                 title=['%s:' % _("Version"), '%s' % str(self.version)], column1=True)
        d_properties_tw.addChild(parent=general_cat,
                                 title=['%s:' % _("Release date"), '%s' % str(self.version_date)], column1=True)

        grid_cat = d_properties_tw.addParent(root, _('Grid'), expanded=True, color=p_color, font=font)
        d_properties_tw.addChild(parent=grid_cat,
                                 title=['%s:' % _("Displayed"), '%s' % str(self.options['global_grid_lines'])],
                                 column1=True)
        d_properties_tw.addChild(parent=grid_cat,
                                 title=['%s:' % _("Snap"), '%s' % str(self.options['global_grid_snap'])],
                                 column1=True)
        d_properties_tw.addChild(parent=grid_cat,
                                 title=['%s:' % _("X value"), '%s' % str(self.ui.grid_gap_x_entry.get_value())],
                                 column1=True)
        d_properties_tw.addChild(parent=grid_cat,
                                 title=['%s:' % _("Y value"), '%s' % str(self.ui.grid_gap_y_entry.get_value())],
                                 column1=True)

        canvas_cat = d_properties_tw.addParent(root, _('Canvas'), expanded=True, color=p_color, font=font)
        d_properties_tw.addChild(parent=canvas_cat,
                                 title=['%s:' % _("Axis"), '%s' % str(self.options['global_axis'])],
                                 column1=True)
        d_properties_tw.addChild(parent=canvas_cat,
                                 title=['%s:' % _("Workspace active"),
                                        '%s' % str(self.options['global_workspace'])],
                                 column1=True)
        d_properties_tw.addChild(parent=canvas_cat,
                                 title=['%s:' % _("Workspace size"),
                                        '%s' % str(self.options['global_workspaceT'])],
                                 column1=True)
        d_properties_tw.addChild(parent=canvas_cat,
                                 title=['%s:' % _("Workspace orientation"),
                                        '%s' % _("Portrait") if self.options[
                                                                    'global_workspace_orientation'] == 'p' else
                                        _("Landscape")],
                                 column1=True)
        d_properties_tw.addChild(parent=canvas_cat,
                                 title=['%s:' % _("HUD"), '%s' % str(self.options['global_hud'])],
                                 column1=True)
        self.ui.properties_scroll_area.setWidget(d_properties_tw)

    def setup_obj_classes(self):
        """
        Sets up application specifics on the FlatCAMObj class. This way the object.app attribute will point to the App
        class.

        :return: None
        """
        FlatCAMObj.app = self
        ObjectCollection.app = self
        Gerber.app = self
        Excellon.app = self
        Geometry.app = self
        CNCjob.app = self
        FCProcess.app = self
        FCProcessContainer.app = self
        OptionsGroupUI.app = self

    def version_check(self):
        """
        Checks for the latest version of the program. Alerts the
        user if theirs is outdated. This method is meant to be run
        in a separate thread.

        :return: None
        """

        self.log.debug("version_check()")

        if self.ui.general_pref_form.general_app_group.send_stats_cb.get_value() is True:
            full_url = "%s?s=%s&v=%s&os=%s&%s" % (
                App.version_url,
                str(self.options['global_serial']),
                str(self.version),
                str(self.os),
                urllib.parse.urlencode(self.options["global_stats"])
            )
            # full_url = App.version_url + "?s=" + str(self.options['global_serial']) + \
            #            "&v=" + str(self.version) + "&os=" + str(self.os) + "&" + \
            #            urllib.parse.urlencode(self.options["global_stats"])
        else:
            # no_stats dict; just so it won't break things on website
            no_ststs_dict = {"global_ststs": {}}
            full_url = App.version_url + "?s=" + str(self.options['global_serial']) + "&v=" + str(self.version)
            full_url += "&os=" + str(self.os) + "&" + urllib.parse.urlencode(no_ststs_dict["global_ststs"])

        self.log.debug("Checking for updates @ %s" % full_url)
        # ## Get the data
        try:
            f = urllib.request.urlopen(full_url)
        except Exception:
            # self.log.warning("Failed checking for latest version. Could not connect.")
            self.log.warning("Failed checking for latest version. Could not connect.")
            self.inform.emit('[WARNING_NOTCL] %s' % _("Failed checking for latest version. Could not connect."))
            return

        try:
            data = json.load(f)
        except Exception as e:
            self.log.error("Could not parse information about latest version.")
            self.inform.emit('[ERROR_NOTCL] %s' % _("Could not parse information about latest version."))
            self.log.error("json.load(): %s" % str(e))
            f.close()
            return

        f.close()

        # ## Latest version?
        if self.version >= data["version"]:
            self.log.debug("THe application is up to date!")
            self.inform.emit('[success] %s' % _("The application is up to date!"))
            return

        self.log.debug("Newer version available.")
        title = _("Newer Version Available")
        msg = '%s<br><br>><b>%s</b><br>%s' % (
            _("There is a newer version available for download:"),
            str(data["name"]),
            str(data["message"])
        )
        self.message.emit(title, msg, "info")

    def on_plotcanvas_setup(self):
        """
        This is doing the setup for the plot area (canvas).

        :return:            None
        """

        modifier = QtWidgets.QApplication.queryKeyboardModifiers()
        if modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
            self.options["global_graphic_engine"] = "2D"

        self.log.debug("Setting up canvas: %s" % str(self.options["global_graphic_engine"]))

        if modifier == QtCore.Qt.KeyboardModifier.ControlModifier:
            self.use_3d_engine = False

        if self.use_3d_engine:
            try:
                plotcanvas = PlotCanvas(self)
            except Exception as er:
                msg_txt = traceback.format_exc()
                self.log.error("App.on_plotcanvas_setup() failed -> %s" % str(er))
                self.log.error("OpenGL canvas initialization failed with the following error.\n" + msg_txt)
                msg = '[ERROR] %s' % _("An internal error has occurred. See shell.\n")
                msg += _("OpenGL canvas initialization failed. HW or HW configuration not supported."
                         "Change the graphic engine to Legacy(2D) in Edit -> Preferences -> General tab.\n\n")
                msg += msg_txt
                self.log.error(msg)
                self.inform.emit(msg)
                return 'fail'
        else:
            plotcanvas = PlotCanvasLegacy(self)
            if plotcanvas.status != 'ok':
                return 'fail'

        # So it can receive key presses
        plotcanvas.native.setFocus()

        if self.use_3d_engine:
            pan_button = 2 if self.options["global_pan_button"] == '2' else 3
            # Set the mouse button for panning
            plotcanvas.view.camera.pan_button_setting = pan_button

        self.mm = plotcanvas.graph_event_connect('mouse_move', self.on_mouse_move_over_plot)
        self.mp = plotcanvas.graph_event_connect('mouse_press', self.on_mouse_click_over_plot)
        self.mr = plotcanvas.graph_event_connect('mouse_release', self.on_mouse_click_release_over_plot)
        self.mdc = plotcanvas.graph_event_connect('mouse_double_click', self.on_mouse_double_click_over_plot)

        # Keys over plot enabled
        self.kp = plotcanvas.graph_event_connect('key_press', self.ui.keyPressEvent)

        if self.options['global_cursor_type'] == 'small':
            self.app_cursor = plotcanvas.new_cursor()
        else:
            self.app_cursor = plotcanvas.new_cursor(big=True)

        if self.ui.grid_snap_btn.isChecked():
            self.app_cursor.enabled = True
        else:
            self.app_cursor.enabled = False

        return plotcanvas

    @staticmethod
    def on_plotcanvas_add(plotcanvas_obj, container):
        """

        :param plotcanvas_obj:  the class that set up the canvas
        :type plotcanvas_obj:   class
        :param container:       a layout where to add the native widget of the plotcanvas_obj class
        :type container:
        :return:                Nothing
        :rtype:                 None
        """
        container.addWidget(plotcanvas_obj.native)

    def on_zoom_fit(self):
        """
        Callback for zoom-fit request. This can be either from the corresponding
        toolbar button or the '1' key when the canvas is focused. Calls ``self.adjust_axes()``
        with axes limits from the geometry bounds of all objects.

        :return:        None
        """
        if self.use_3d_engine:
            self.plotcanvas.fit_view()
        else:
            xmin, ymin, xmax, ymax = self.collection.get_bounds()
            width = xmax - xmin
            height = ymax - ymin
            xmin -= 0.05 * width
            xmax += 0.05 * width
            ymin -= 0.05 * height
            ymax += 0.05 * height
            self.plotcanvas.adjust_axes(xmin, ymin, xmax, ymax)

    def on_zoom_in(self):
        """
        Callback for zoom-in request.
        :return:
        """
        self.plotcanvas.zoom(1 / float(self.options['global_zoom_ratio']))

    def on_zoom_out(self):
        """
        Callback for zoom-out request.

        :return:
        """
        self.plotcanvas.zoom(float(self.options['global_zoom_ratio']))

    def disable_all_plots(self):
        self.defaults.report_usage("disable_all_plots()")

        self.disable_plots(self.collection.get_list())
        self.inform.emit('[success] %s' % _("All plots disabled."))

    def disable_other_plots(self):
        self.defaults.report_usage("disable_other_plots()")

        self.disable_plots(self.collection.get_non_selected())
        self.inform.emit('[success] %s' % _("All non selected plots disabled."))

    def enable_all_plots(self):
        self.defaults.report_usage("enable_all_plots()")

        self.enable_plots(self.collection.get_list())
        self.inform.emit('[success] %s' % _("All plots enabled."))

    def enable_other_plots(self):
        self.defaults.report_usage("enable_other_plots()")

        self.enable_plots(self.collection.get_non_selected())
        self.inform.emit('[success] %s' % _("All non selected plots enabled."))

    def on_enable_sel_plots(self, silent=False):
        if silent is False:
            self.log.debug("App.on_enable_sel_plots()")
        object_list = self.collection.get_selected()
        self.enable_plots(objects=object_list, silent=silent)
        if silent is False:
            self.inform.emit('[success] %s' % _("Selected plots enabled..."))

    def on_disable_sel_plots(self):
        self.log.debug("App.on_disable_sel_plot()")

        # self.inform.emit(_("Disabling plots ..."))
        object_list = self.collection.get_selected()
        self.disable_plots(objects=object_list)
        self.inform.emit('[success] %s' % _("Selected plots disabled..."))

    def enable_plots(self, objects, silent=False):
        """
        Enable plots

        :param objects: list of Objects to be enabled
        :param silent: If True there are no messages from this method
        :return:
        """
        if silent is False:
            self.log.debug("Enabling plots ...")
        # self.inform.emit('%s...' % _("Working"))

        for obj in objects:
            if obj.obj_options['plot'] is False:
                obj.obj_options.set_change_callback(lambda x: None)
                try:
                    obj.obj_options['plot'] = True
                    obj.ui.plot_cb.stateChanged.disconnect(obj.on_plot_cb_click)
                    # disable this cb while disconnected,
                    # in case the operation takes time the user is not allowed to change it
                    obj.ui.plot_cb.setDisabled(True)
                except AttributeError:
                    # try to build the ui
                    obj.build_ui()
                    # and try again
                    self.enable_plots(objects)

                obj.set_form_item("plot")
                try:
                    obj.ui.plot_cb.stateChanged.connect(obj.on_plot_cb_click)
                    obj.ui.plot_cb.setDisabled(False)
                except AttributeError:
                    # try to build the ui
                    obj.build_ui()
                    # and try again
                    self.enable_plots(objects)
                obj.obj_options.set_change_callback(obj.on_options_change)
        self.collection.update_view()

        def worker_task(objs):
            with self.proc_container.new(_("Enabling plots ...")):
                for plot_obj in objs:
                    # obj.obj_options['plot'] = True
                    if isinstance(plot_obj, CNCJobObject):
                        plot_obj.plot(visible=True, kind=self.options["cncjob_plot_kind"])
                    else:
                        plot_obj.plot(visible=True)

        self.worker_task.emit({'fcn': worker_task, 'params': [objects]})

    def disable_plots(self, objects):
        """
        Disables plots

        :param objects: list of Objects to be disabled
        :return:
        """

        self.log.debug("Disabling plots ...")
        # self.inform.emit('%s...' % _("Working"))

        for obj in objects:
            if obj.obj_options['plot'] is True:
                obj.obj_options.set_change_callback(lambda x: None)
                try:
                    obj.obj_options['plot'] = False
                    obj.ui.plot_cb.stateChanged.disconnect(obj.on_plot_cb_click)
                    obj.ui.plot_cb.setDisabled(True)
                except (AttributeError, TypeError):
                    # try to build the ui
                    obj.build_ui()
                    # and try again
                    self.disable_plots(objects)

                obj.set_form_item("plot")
                try:
                    obj.ui.plot_cb.stateChanged.connect(obj.on_plot_cb_click)
                    obj.ui.plot_cb.setDisabled(False)
                except (AttributeError, TypeError):
                    # try to build the ui
                    obj.build_ui()
                    # and try again
                    self.disable_plots(objects)
                obj.obj_options.set_change_callback(obj.on_options_change)

        try:
            self.delete_selection_shape()
        except Exception as e:
            self.log.error("App.disable_plots() --> %s" % str(e))

        self.collection.update_view()

        def worker_task(objs):
            with self.proc_container.new(_("Disabling plots ...")):
                for plot_obj in objs:
                    # obj.obj_options['plot'] = True
                    if isinstance(plot_obj, CNCJobObject):
                        plot_obj.plot(visible=False, kind=self.options["cncjob_plot_kind"])
                    else:
                        plot_obj.plot(visible=False)

        self.worker_task.emit({'fcn': worker_task, 'params': [objects]})

    def toggle_plots(self, objects):
        """
        Toggle plots visibility

        :param objects:     list of Objects for which to be toggled the visibility
        :return:            None
        """

        # if no objects selected then do nothing
        if not self.collection.get_selected():
            return

        self.log.debug("Toggling plots ...")
        # self.inform.emit('%s...' % _("Working"))
        for obj in objects:
            if obj.obj_options['plot'] is False:
                obj.obj_options['plot'] = True
            else:
                obj.obj_options['plot'] = False
        try:
            self.delete_selection_shape()
        except Exception:
            pass
        self.app_obj.plots_updated.emit()

    def clear_plots(self):
        """
        Clear the plots

        :return:            None
        """

        objects = self.collection.get_list()

        for obj in objects:
            obj.clear(obj == objects[-1])

        # Clear pool to free memory
        self.clear_pool()

    def gerber_redraw(self):
        # the Gerber redraw should work only if there is only one object of type Gerber and active in the selection
        sel_gerb_objs = [o for o in self.collection.get_selected() if o.kind == 'gerber' and o.obj_options['plot']]
        if len(sel_gerb_objs) > 1:
            return

        obj = self.collection.get_active()
        if not obj or (obj.obj_options['plot'] is False or obj.kind != 'gerber'):
            # we don't replot something that is disabled or if it is not Gerber type
            return

        def worker_task(plot_obj):
            plot_obj.plot(visible=True)

        self.worker_task.emit({'fcn': worker_task, 'params': [obj]})

    def on_set_color_action_triggered(self):
        """
        This slot gets called by clicking on the menu entry in the Set Color submenu of the context menu in Project Tab

        :return:
        """

        new_color = self.options['gerber_plot_fill']
        new_line_color = self.options['gerber_plot_line']

        clicked_action = self.sender()

        assert isinstance(clicked_action, QAction), "Expected a QAction, got %s" % type(clicked_action)
        act_name = clicked_action.text()
        sel_obj_list = self.collection.get_selected()

        if not sel_obj_list:
            return

        # a default value, I just chose this one
        alpha_level = 'BF'
        for sel_obj in sel_obj_list:
            if hasattr(sel_obj, "alpha_level"):
                alpha_level = sel_obj.alpha_level
            else:
                if sel_obj.kind == 'excellon':
                    alpha_level = str(hex(int(self.options['excellon_plot_fill'][7:9], 16))[2:])
                elif sel_obj.kind == 'gerber':
                    alpha_level = str(hex(int(self.options['gerber_plot_fill'][7:9], 16))[2:])
                elif sel_obj.kind == 'geometry':
                    alpha_level = 'FF'
                else:
                    self.log.debug(
                        "App.on_set_color_action_triggered() --> Default transparency level "
                        "for this object type not supported yet")
                    continue
                sel_obj.alpha_level = alpha_level

        if act_name == _('Red'):
            new_color = '#FF0000' + alpha_level
        if act_name == _('Blue'):
            new_color = '#0000FF' + alpha_level

        if act_name == _('Yellow'):
            new_color = '#FFDF00' + alpha_level
        if act_name == _('Green'):
            new_color = '#00FF00' + alpha_level
        if act_name == _('Purple'):
            new_color = '#FF00FF' + alpha_level
        if act_name == _('Brown'):
            new_color = '#A52A2A' + alpha_level
        if act_name == _('Indigo'):
            new_color = '#4B0082' + alpha_level
        if act_name == _('White'):
            new_color = '#FFFFFF' + alpha_level
        if act_name == _('Black'):
            new_color = '#000000' + alpha_level

        # selection of a custom color will open a QColor dialog
        if act_name == _('Custom'):
            new_color = QtGui.QColor(self.options['gerber_plot_fill'][:7])
            c_dialog = QtWidgets.QColorDialog()
            plot_fill_color = c_dialog.getColor(initial=new_color)

            if plot_fill_color.isValid() is False:
                return

            new_color = str(plot_fill_color.name()) + alpha_level

        # when it is desired the return to the default color set in Preferences
        if act_name == _("Default"):
            for sel_obj in sel_obj_list:
                if sel_obj.kind == 'excellon':
                    new_color = self.options['excellon_plot_fill']
                    new_line_color = self.options['excellon_plot_line']
                elif sel_obj.kind == 'gerber':
                    new_color = self.options['gerber_plot_fill']
                    new_line_color = self.options['gerber_plot_line']
                elif sel_obj.kind == 'geometry':
                    new_color = self.options['geometry_plot_line']
                    new_line_color = self.options['geometry_plot_line']
                else:
                    self.log.debug(
                        "App.on_set_color_action_triggered() --> Default color for this object type not supported yet")
                    continue

                sel_obj.fill_color = new_color
                sel_obj.outline_color = new_line_color
                sel_obj.shapes.redraw(
                    update_colors=(new_color, new_line_color)
                )

            self.set_obj_color_in_preferences_dict(sel_obj_list, new_color, new_line_color)
            return

        # set of a custom transparency level
        if act_name == _("Opacity"):
            # alpha_level, ok_button = QtWidgets.QInputDialog.getInt(self.ui, _("Set alpha level ..."),
            #                                                        '%s:' % _("Value"),
            #                                                        min=0, max=255, step=1, value=191)

            alpha_dialog = FCInputDialogSlider(
                self.ui, _("Set alpha level ..."), '%s:' % _("Value"), min=0, max=255, step=1, init_val=191)
            alpha_level, ok_button = alpha_dialog.get_results()

            if ok_button:
                group = self.collection.group_items["gerber"]
                group_index = self.collection.index(group.row(), 0, QtCore.QModelIndex())

                alpha_str = str(hex(alpha_level)[2:]) if alpha_level != 0 else '00'

                for sel_obj in sel_obj_list:
                    new_color = sel_obj.fill_color[:-2] + alpha_str
                    new_line_color = sel_obj.outline_color
                    sel_obj.alpha_level = alpha_str
                    sel_obj.fill_color = new_color
                    sel_obj.shapes.redraw(update_colors=(new_color, new_line_color))

                    if sel_obj.kind == 'gerber':
                        item = sel_obj.item
                        item_index = self.collection.index(item.row(), 0, group_index)
                        idx = item_index.row()
                        new_c = (new_line_color, new_color, '%s_%d' % (_("Layer"), int(idx + 1)))
                        try:
                            self.options["gerber_color_list"][idx] = new_c
                        except Exception as err_msg:
                            self.inform.emit('[ERROR_NOTCL] %s' % _("Failed."))
                            self.log.error(str(err_msg))
            return

        new_line_color = color_variant(new_color[:7], 0.7)
        if act_name == _("White"):
            new_line_color = color_variant("#dedede", 0.7)

        for sel_obj in sel_obj_list:
            if sel_obj.kind in ["excellon", "gerber"]:
                sel_obj.fill_color = new_color
                sel_obj.outline_color = new_line_color

                sel_obj.shapes.redraw(
                    update_colors=(new_color, new_line_color)
                )

        self.set_obj_color_in_preferences_dict(sel_obj_list, new_color, new_line_color)

    def set_obj_color_in_preferences_dict(self, list_of_obj, fill_color, outline_color):
        """
        Will save the set colors into a list that will be used next time when Gerber objects are loaded.
        First loaded Gerber will have the first color in the list, second loaded Gerber object will have set the second
        color in the list and so on.

        :param list_of_obj:         a list of App objects that are currently loaded and selected
        :type list_of_obj:          list
        :param fill_color:          the fill color that will be set for the selected objects
        :type fill_color:           str
        :param outline_color:       the outline color that will be set for the selected objects
        :type outline_color:        str
        :return:
        :rtype:
        """

        # make sure to set the color in the Gerber colors storage self.options["gerber_color_list"]
        group_gerber = self.collection.group_items["gerber"]
        group_gerber_index = self.collection.index(group_gerber.row(), 0, QtCore.QModelIndex())
        all_gerber_list = [x for x in self.collection.get_list() if x.kind == 'gerber']

        for sel_obj in list_of_obj:
            if sel_obj.kind == 'gerber':
                item = sel_obj.item
                item_index = self.collection.index(item.row(), 0, group_gerber_index)
                idx = item_index.row()
                new_c = (outline_color, fill_color, '%s_%d' % (_("Layer"), int(idx + 1)))
                try:
                    self.options["gerber_color_list"][idx] = new_c
                except IndexError:
                    for x in range(len(self.options["gerber_color_list"]), len(all_gerber_list)):
                        self.options["gerber_color_list"].append(
                            (
                                self.options["gerber_plot_fill"],  # content color
                                self.options["gerber_plot_line"],  # outline color
                                '%s_%d' % (_("Layer"), int(idx + 1)))  # layer name
                        )
                    self.options["gerber_color_list"][idx] = new_c
            elif sel_obj.kind == 'excellon':
                new_c = (outline_color, fill_color)
                self.options["excellon_color"] = new_c

    def start_delayed_quit(self, delay, filename, should_quit=None):
        """

        :param delay:           period of checking if project file size is more than zero; in seconds
        :param filename:        the name of the project file to be checked periodically for size more than zero
        :param should_quit:     if the task finished will be followed by an app quit; boolean
        :return:
        """
        to_quit = should_quit
        self.save_timer = QtCore.QTimer()
        self.save_timer.setInterval(delay)
        self.save_timer.timeout.connect(lambda: self.check_project_file_size(filename=filename, should_quit=to_quit))
        self.save_timer.start()

    def check_project_file_size(self, filename, should_quit=None):
        """

        :param filename:        the name of the project file to be checked periodically for size more than zero
        :param should_quit:     will quit the app if True; boolean
        :return:
        """

        try:
            if os.stat(filename).st_size > 0:
                self.save_in_progress = False
                self.save_timer.stop()
                if should_quit:
                    self.app_quit.emit()
        except Exception:
            traceback.print_exc()

    def save_project_auto(self):
        """
        Called periodically to save the project.
        It will save if there is no block on the save, if the project was saved at least once and if there is no save in
        # progress.

        :return:
        """

        if self.block_autosave is False and self.should_we_save is True and self.save_in_progress is False:
            self.f_handlers.on_file_save_project()

    def save_project_auto_update(self):
        """
        Update the auto save time interval value.
        :return:
        """
        self.log.debug("App.save_project_auto_update() --> updated the interval timeout.")
        try:
            if self.autosave_timer.isActive():
                self.autosave_timer.stop()
        except Exception:
            pass

        if self.options['global_autosave'] is True:
            self.autosave_timer.setInterval(int(self.options['global_autosave_timeout']))
            self.autosave_timer.start()

    def on_defaults2options(self):
        """
        Callback for Options->Transfer Options->App=>Project. Copy options
        from application defaults to project options.

        :return:    None
        """

        self.preferencesUiManager.defaults_read_form()
        self.options.update(self.defaults)

    def shell_message(self, msg, show=False, error=False, warning=False, success=False, selected=False, new_line=True):
        """
        Shows a message on the FlatCAM Shell

        :param new_line:
        :param msg:         Message to display.
        :param show:        Opens the shell.
        :param error:       Shows the message as an error.
        :param warning:     Shows the message as a warning.
        :param success:     Shows the message as a success.
        :param selected:    Indicate that something was selected on canvas
        :return: None
        """
        end = '\n' if new_line is True else ''

        if show:
            self.ui.shell_dock.show()
        try:
            if error:
                self.shell.append_error(msg + end)
            elif warning:
                self.shell.append_warning(msg + end)
            elif success:
                self.shell.append_success(msg + end)
            elif selected:
                self.shell.append_selected(msg + end)
            else:
                self.shell.append_output(msg + end)
        except AttributeError:
            self.log.debug("shell_message() is called before Shell Class is instantiated. The message is: %s", str(msg))

    def script_processing(self, script_code):
        # trying to run a Tcl command without having the Shell open will create some warnings because the Tcl Shell
        # tries to print on a hidden widget, therefore show the dock if hidden
        if self.ui.shell_dock.isHidden():
            self.ui.shell_dock.show()

        self.shell.open_processing()  # Disables input box.

        old_line = ''
        # set tcl info script to actual scriptfile

        set_tcl_script_name = '''proc procExists p {{
                            return uplevel 1 [expr {{[llength [info command $p]] > 0}}]
                        }}

                        if  {{[procExists "info_original"]==0}} {{
                            rename info info_original
                        }}

                        proc info args {{
                            switch [lindex $args 0] {{
                                script {{
                                    return "{0}"
                                }}
                                default {{
                                    return [uplevel info_original $args]
                                }}
                            }}
                        }}'''.format(script_code)

        for tcl_command_line in set_tcl_script_name.splitlines() + script_code.splitlines():
            # do not process lines starting with '#' = comment and empty lines
            if not tcl_command_line.startswith('#') and tcl_command_line != '':
                # if FlatCAM is run in Windows then replace all the slashes with
                # the UNIX style slash that TCL understands
                if sys.platform == 'win32':
                    tcl_command_line_lowered = tcl_command_line.lower()
                    if "open" in tcl_command_line_lowered or "path" in tcl_command_line_lowered:
                        tcl_command_line = tcl_command_line.replace('\\', '/')

                new_command = '%s%s\n' % (old_line, tcl_command_line) if old_line != '' else tcl_command_line

                # execute the actual Tcl command
                try:
                    result = self.shell.tcl.eval(str(new_command))
                    if result != 'None':
                        self.shell.append_output(result + '\n')
                    if result == 'fail':
                        # self.ui.fcinfo.lock_pmaps = False
                        self.shell.append_output(result.capitalize() + '\n')
                        self.shell.close_processing()
                        self.log.error("%s: %s" % ("Tcl Command failed", str(new_command)))
                        self.inform.emit("[ERROR] %s" % _("Aborting."))
                        return
                    old_line = ''
                except tk.TclError:
                    old_line = old_line + tcl_command_line + '\n'
                except Exception as e:
                    self.log.error("App.script_processing() --> %s" % str(e))

        if old_line != '':
            # it means that the script finished with an error
            result = self.shell.tcl.eval("set errorInfo")
            if "quit_app" not in result:
                self.log.error("Exec command Exception: %s\n" % result)
                self.shell.append_error('ERROR: %s\n' % result)

        # self.ui.fcinfo.lock_pmaps = False
        self.shell.close_processing()

    def dec_format(self, val, dec=None):
        """
        Returns a formatted float value with a certain number of decimals
        """
        dec_nr = dec if dec is not None else self.decimals

        return float('%.*f' % (dec_nr, float(val)))


class ArgsThread(QtCore.QObject):
    open_signal = pyqtSignal(list)
    start = pyqtSignal()
    stop = pyqtSignal()

    if sys.platform == 'win32':
        address = (r'\\.\pipe\NPtest', 'AF_PIPE')
    else:
        address = ('/tmp/testipc', 'AF_UNIX')

    def __init__(self):
        super().__init__()
        self.listener = None
        self.conn = None
        self.thread_exit = False

        self.start.connect(self.run)    # noqa
        self.stop.connect(self.close_listener, type=Qt.ConnectionType.QueuedConnection)  # noqa

    def my_loop(self, address):
        try:
            self.listener = Listener(*address)
            while self.thread_exit is False:
                self.conn = self.listener.accept()
                self.serve(self.conn)
        except socket.error:
            try:
                self.conn = Client(*address)
                self.conn.send(sys.argv)
                self.conn.send('close')
                # close the current instance only if there are args
                if len(sys.argv) > 1:
                    try:
                        self.listener.close()
                    except Exception:
                        pass
                    sys.exit()
            except ConnectionRefusedError:
                if sys.platform == 'win32':
                    pass
                else:
                    os.system('rm /tmp/testipc')
                    self.listener = Listener(*address)
                    while True:
                        conn = self.listener.accept()
                        self.serve(conn)
        except Exception:
            pass
            # print(str(gen_err))

    def serve(self, conn):
        while self.thread_exit is False:
            QtCore.QCoreApplication.processEvents()
            if QtCore.QThread.currentThread().isInterruptionRequested():
                break
            msg = conn.recv()
            if msg == 'close':
                break
            self.open_signal.emit(msg)  # noqa
        conn.close()

    # the decorator is a must; without it this technique will not work unless the start signal is connected
    # in the main thread (where this class is instantiated) after the instance is moved o the new thread
    @pyqtSlot()
    def run(self):
        self.my_loop(self.address)

    @pyqtSlot()
    def close_listener(self):
        self.thread_exit = True
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            self.listener.close()
        except Exception:
            pass

    def close_command(self):
        conn = Client(*self.address)
        conn.send(['quit'])
        try:
            self.listener.close()
        except Exception:
            pass

# end of file
